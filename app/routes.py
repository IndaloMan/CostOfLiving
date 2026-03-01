import os
import json
from datetime import date
from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, current_app, jsonify
)
from werkzeug.utils import secure_filename
from . import db
from .extractor import extract_from_file, ExtractionError
from .template_manager import (
    get_template_items, apply_template_hints,
    update_template, set_template_items
)
from .models import Company, Receipt, LineItem, ReceiptAnalysis
from .company_analysers import get_analyser_key, canonical_name, get_analysis_endpoint
from .reports_data import (
    parse_date, default_start,
    get_summary, get_spending_over_time,
    get_by_category, get_by_company,
    get_price_trend, get_item_suggestions,
    get_spend_per_visit, get_top_items,
)

main = Blueprint("main", __name__)

CATEGORIES = [
    "food", "drink", "dairy", "meat", "fish", "bakery", "produce", "frozen",
    "household", "cleaning", "personal_care", "pet",
    "electricity", "water", "gas", "internet", "phone",
    "restaurant", "takeaway", "other",
]

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "pdf"}


def _allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@main.route("/")
def index():
    total_receipts = Receipt.query.filter_by(status="confirmed").count()
    total_companies = Company.query.count()
    return render_template("index.html", total_receipts=total_receipts, total_companies=total_companies)


# ---------------------------------------------------------------------------
# Scan — upload
# ---------------------------------------------------------------------------

def _process_one_file(f):
    """
    Save, extract and persist a single uploaded file as a pending receipt.
    Returns (receipt, error_string) — one of which will be None.
    Does NOT commit; caller must call db.session.commit().
    """
    if not _allowed_file(f.filename):
        return None, f"Unsupported file type: {f.filename}"

    filename = secure_filename(f.filename)

    # Duplicate check — skip API call entirely if already in DB
    existing = Receipt.query.filter_by(filename=filename).first()
    if existing:
        if existing.status == "pending":
            # Return the receipt so the caller can offer a Review link
            return existing, f"'{filename}' already uploaded (pending — not yet reviewed)"
        return None, f"'{filename}' already uploaded (confirmed)"

    upload_folder = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_folder, exist_ok=True)
    filepath = os.path.join(upload_folder, filename)
    f.save(filepath)

    try:
        extracted = extract_from_file(filepath)
    except ExtractionError as e:
        return None, f"{f.filename}: extraction failed — {e}"
    except Exception as e:
        return None, f"{f.filename}: unexpected error — {e}"

    company_name = canonical_name(extracted.get("company_name") or "Unknown")
    company = Company.query.filter(
        db.func.lower(Company.name) == company_name.lower()
    ).first()

    receipt_date = None
    raw_date = extracted.get("date")
    if raw_date:
        try:
            receipt_date = date.fromisoformat(raw_date)
        except ValueError:
            pass

    receipt = Receipt(
        company=company,
        receipt_date=receipt_date,
        total_amount=extracted.get("total_amount"),
        currency=extracted.get("currency", "EUR"),
        filename=filename,
        document_type=extracted.get("document_type", "receipt"),
        raw_extraction=json.dumps(extracted),
        status="pending",
    )
    db.session.add(receipt)
    db.session.flush()

    line_items = []
    for item in extracted.get("line_items", []):
        li = LineItem(
            receipt_id=receipt.id,
            description=item.get("description", ""),
            quantity=item.get("quantity") or 1.0,
            unit_price=item.get("unit_price"),
            total_price=item.get("total_price"),
            category=item.get("category"),
        )
        db.session.add(li)
        line_items.append(li)

    if company:
        template_items = get_template_items(company.id)
        if template_items:
            apply_template_hints(line_items, template_items)

    return receipt, None


@main.route("/scan", methods=["GET", "POST"])
def scan():
    if request.method == "GET":
        return render_template("scan.html")

    if "file" not in request.files or request.files["file"].filename == "":
        flash("No file selected.", "error")
        return redirect(url_for("main.scan"))

    receipt, error = _process_one_file(request.files["file"])
    if error:
        flash(error, "error")
        return redirect(url_for("main.scan"))

    company = receipt.company
    if company:
        template_items = get_template_items(company.id)
        if template_items:
            matched = sum(1 for li in receipt.line_items if li.category)
            if matched:
                flash(
                    f"Template applied: {matched} item(s) auto-categorised from previous {company.name} receipts.",
                    "info"
                )

    db.session.commit()
    flash("Receipt scanned. Review and confirm the details below.", "info")
    return redirect(url_for("main.review", receipt_id=receipt.id))


@main.route("/scan/batch", methods=["GET", "POST"])
def scan_batch():
    if request.method == "GET":
        return render_template("scan_batch.html")

    files = [f for f in request.files.getlist("files") if f.filename]
    if not files:
        flash("No files selected.", "error")
        return redirect(url_for("main.scan_batch"))

    results = []
    for f in files:
        receipt, error = _process_one_file(f)
        results.append({
            "filename": f.filename,
            "receipt": receipt,
            "error": error,
        })

    db.session.commit()

    ok_count      = sum(1 for r in results if r["receipt"] and not r["error"])
    pending_count = sum(1 for r in results if r["receipt"] and r["error"])
    err_count     = sum(1 for r in results if not r["receipt"] and r["error"])
    return render_template("scan_batch.html", results=results,
                           ok_count=ok_count, pending_count=pending_count,
                           err_count=err_count)


# ---------------------------------------------------------------------------
# Review — inspect and edit extracted data
# ---------------------------------------------------------------------------

@main.route("/scan/review/<int:receipt_id>")
def review(receipt_id):
    receipt = Receipt.query.get_or_404(receipt_id)
    companies = Company.query.order_by(Company.name).all()
    return render_template(
        "review.html",
        receipt=receipt,
        categories=CATEGORIES,
        companies=companies,
    )


# ---------------------------------------------------------------------------
# Confirm — save edits, mark confirmed, update template
# ---------------------------------------------------------------------------

@main.route("/scan/confirm/<int:receipt_id>", methods=["POST"])
def confirm(receipt_id):
    receipt = Receipt.query.get_or_404(receipt_id)

    # Update or create company
    company_name = request.form.get("company_name", "").strip()
    company = None
    if company_name:
        company = Company.query.filter(
            db.func.lower(Company.name) == company_name.lower()
        ).first()
        if not company:
            company = Company(name=company_name, type=request.form.get("company_type"))
            db.session.add(company)
            db.session.flush()
        receipt.company = company

    # Update receipt header fields
    receipt.document_type = request.form.get("document_type", "receipt")
    receipt.currency = request.form.get("currency", "EUR")
    receipt.status = "confirmed"

    raw_date = request.form.get("receipt_date", "").strip()
    if raw_date:
        try:
            receipt.receipt_date = date.fromisoformat(raw_date)
        except ValueError:
            pass

    raw_total = request.form.get("total_amount", "").strip()
    if raw_total:
        try:
            receipt.total_amount = float(raw_total)
        except ValueError:
            pass

    # Replace line items with form values
    LineItem.query.filter_by(receipt_id=receipt.id).delete()

    descriptions = request.form.getlist("description[]")
    quantities   = request.form.getlist("quantity[]")
    unit_prices  = request.form.getlist("unit_price[]")
    total_prices = request.form.getlist("total_price[]")
    categories   = request.form.getlist("category[]")

    saved_items = []
    for i, desc in enumerate(descriptions):
        if not desc.strip():
            continue
        li = LineItem(
            receipt_id=receipt.id,
            description=desc.strip(),
            quantity=_float_or(quantities, i, 1.0),
            unit_price=_float_or(unit_prices, i, None),
            total_price=_float_or(total_prices, i, None),
            category=categories[i].strip() if i < len(categories) else None,
        )
        db.session.add(li)
        saved_items.append(li)

    db.session.flush()

    # Update company template with categorised items
    if company and saved_items:
        update_template(company.id, saved_items)

    db.session.commit()

    # Run company-specific analysis if one exists for this company
    if company:
        analyser_key = get_analyser_key(company.name)
        if analyser_key == "energy_nordic":
            from .company_analysers.energy_nordic import analyse, AnalysisError
            filepath = os.path.join(current_app.config["UPLOAD_FOLDER"], receipt.filename)
            if os.path.exists(filepath):
                try:
                    data = analyse(filepath)
                    if receipt.analysis:
                        receipt.analysis.data = json.dumps(data)
                    else:
                        db.session.add(ReceiptAnalysis(
                            receipt_id=receipt.id,
                            analyser="energy_nordic",
                            data=json.dumps(data),
                        ))
                    db.session.commit()
                    flash("Electricity analysis updated automatically.", "info")
                except AnalysisError as e:
                    flash(f"Analysis could not run: {e}", "error")

    flash("Receipt confirmed and saved.", "success")
    return redirect(url_for("main.receipts"))


# ---------------------------------------------------------------------------
# Receipts list
# ---------------------------------------------------------------------------

@main.route("/receipts")
def receipts():
    confirmed = (
        Receipt.query
        .filter_by(status="confirmed")
        .order_by(Receipt.receipt_date.desc())
        .all()
    )
    pending = (
        Receipt.query
        .filter_by(status="pending")
        .order_by(Receipt.created_at.desc())
        .all()
    )
    return render_template("receipts.html", receipts=confirmed, pending=pending)


# ---------------------------------------------------------------------------
# Process all pending receipts without individual review
# ---------------------------------------------------------------------------

@main.route("/receipts/process-all-pending", methods=["POST"])
def process_all_pending():
    pending = Receipt.query.filter_by(status="pending").all()
    if not pending:
        flash("No pending receipts to process.", "info")
        return redirect(url_for("main.receipts"))

    done = 0
    analysis_done = 0
    analysis_errors = []

    for receipt in pending:
        receipt.status = "confirmed"
        company = receipt.company

        # Update company template with the extracted line items
        if company and receipt.line_items:
            update_template(company.id, receipt.line_items)

        db.session.commit()

        # Run company-specific analysis
        if company:
            analyser_key = get_analyser_key(company.name)
            if analyser_key == "energy_nordic":
                from .company_analysers.energy_nordic import analyse, AnalysisError
                filepath = os.path.join(current_app.config["UPLOAD_FOLDER"], receipt.filename)
                if os.path.exists(filepath):
                    try:
                        data = analyse(filepath)
                        if receipt.analysis:
                            receipt.analysis.data = json.dumps(data)
                        else:
                            db.session.add(ReceiptAnalysis(
                                receipt_id=receipt.id,
                                analyser="energy_nordic",
                                data=json.dumps(data),
                            ))
                        db.session.commit()
                        analysis_done += 1
                    except AnalysisError as e:
                        analysis_errors.append(f"{receipt.filename}: {e}")

        done += 1

    msg = f"{done} receipt(s) confirmed."
    if analysis_done:
        msg += f" {analysis_done} energy analysis run."
    flash(msg, "success")
    for err in analysis_errors:
        flash(f"Analysis error — {err}", "error")

    return redirect(url_for("main.receipts"))


# ---------------------------------------------------------------------------
# Edit a confirmed receipt (re-opens the review form)
# ---------------------------------------------------------------------------

@main.route("/receipts/<int:receipt_id>/edit")
def edit_receipt(receipt_id):
    receipt = Receipt.query.get_or_404(receipt_id)
    companies = Company.query.order_by(Company.name).all()
    return render_template(
        "review.html",
        receipt=receipt,
        categories=CATEGORIES,
        companies=companies,
        editing=True,
    )


# ---------------------------------------------------------------------------
# Companies — list
# ---------------------------------------------------------------------------

@main.route("/companies")
def companies():
    all_companies = Company.query.order_by(Company.name).all()
    return render_template(
        "companies.html",
        companies=all_companies,
        get_analysis_endpoint=get_analysis_endpoint,
    )


# ---------------------------------------------------------------------------
# Company detail — view and edit template
# ---------------------------------------------------------------------------

@main.route("/companies/<int:company_id>", methods=["GET", "POST"])
def company_detail(company_id):
    company = Company.query.get_or_404(company_id)

    if request.method == "POST":
        # Save manually edited template
        descs = request.form.getlist("tmpl_description[]")
        cats  = request.form.getlist("tmpl_category[]")
        items = []
        for desc, cat in zip(descs, cats):
            desc = desc.strip()
            cat  = cat.strip()
            if desc:
                items.append({"description": desc, "category": cat})
        set_template_items(company.id, items)
        db.session.commit()
        flash(f"Template for {company.name} updated ({len(items)} items).", "success")
        return redirect(url_for("main.company_detail", company_id=company.id))

    template_items = get_template_items(company.id)
    receipt_count = Receipt.query.filter_by(
        company_id=company.id, status="confirmed"
    ).count()
    return render_template(
        "company_detail.html",
        company=company,
        template_items=template_items,
        receipt_count=receipt_count,
        categories=CATEGORIES,
    )


# ---------------------------------------------------------------------------
# Reports page
# ---------------------------------------------------------------------------

@main.route("/reports")
def reports():
    companies = Company.query.order_by(Company.name).all()
    return render_template("reports.html", companies=companies)


# ---------------------------------------------------------------------------
# Reports JSON API
# ---------------------------------------------------------------------------

def _company_id_arg():
    """Parse optional company_id from query string. Returns int or None."""
    val = request.args.get("company_id", "").strip()
    try:
        return int(val) if val else None
    except ValueError:
        return None


@main.route("/api/summary")
def api_summary():
    start      = parse_date(request.args.get("start"), default_start())
    end        = parse_date(request.args.get("end"),   date.today())
    company_id = _company_id_arg()
    return jsonify(get_summary(start, end, company_id))


@main.route("/api/spending-over-time")
def api_spending_over_time():
    start      = parse_date(request.args.get("start"), default_start())
    end        = parse_date(request.args.get("end"),   date.today())
    group_by   = request.args.get("group_by", "month")
    company_id = _company_id_arg()
    return jsonify(get_spending_over_time(start, end, group_by, company_id))


@main.route("/api/by-category")
def api_by_category():
    start      = parse_date(request.args.get("start"), default_start())
    end        = parse_date(request.args.get("end"),   date.today())
    company_id = _company_id_arg()
    return jsonify(get_by_category(start, end, company_id))


@main.route("/api/by-company")
def api_by_company():
    start      = parse_date(request.args.get("start"), default_start())
    end        = parse_date(request.args.get("end"),   date.today())
    company_id = _company_id_arg()
    return jsonify(get_by_company(start, end, company_id=company_id))


@main.route("/api/price-trend")
def api_price_trend():
    description = request.args.get("description", "").strip()
    start       = parse_date(request.args.get("start"), default_start())
    end         = parse_date(request.args.get("end"),   date.today())
    company_id  = _company_id_arg()
    if not description:
        return jsonify({"labels": [], "values": [], "description": ""})
    return jsonify(get_price_trend(description, start, end, company_id))


@main.route("/api/item-suggestions")
def api_item_suggestions():
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify([])
    return jsonify(get_item_suggestions(q))


# ---------------------------------------------------------------------------
# Company-specific analysis — Mercadona
# ---------------------------------------------------------------------------

def _get_mercadona():
    """Return the Mercadona company record or 404."""
    company = Company.query.filter(
        db.func.lower(Company.name).like("%mercadona%")
    ).first_or_404()
    return company


@main.route("/analysis/mercadona")
def analysis_mercadona():
    company = _get_mercadona()
    return render_template("analysis_mercadona.html", company=company)


@main.route("/api/analysis/mercadona/summary")
def api_mercadona_summary():
    company = _get_mercadona()
    start = parse_date(request.args.get("start"), default_start())
    end   = parse_date(request.args.get("end"),   date.today())
    base  = get_summary(start, end, company.id)

    # Add visit count and total items
    from .models import LineItem as LI
    total_items = (
        db.session.query(db.func.count(LI.id))
        .join(Receipt, LI.receipt_id == Receipt.id)
        .filter(
            Receipt.company_id == company.id,
            Receipt.status == "confirmed",
            Receipt.receipt_date >= start,
            Receipt.receipt_date <= end,
        )
        .scalar() or 0
    )
    base["total_items"] = total_items
    return jsonify(base)


@main.route("/api/analysis/mercadona/per-visit")
def api_mercadona_per_visit():
    company = _get_mercadona()
    start = parse_date(request.args.get("start"), default_start())
    end   = parse_date(request.args.get("end"),   date.today())
    return jsonify(get_spend_per_visit(start, end, company.id))


@main.route("/api/analysis/mercadona/by-category")
def api_mercadona_by_category():
    company = _get_mercadona()
    start = parse_date(request.args.get("start"), default_start())
    end   = parse_date(request.args.get("end"),   date.today())
    return jsonify(get_by_category(start, end, company.id))


@main.route("/api/analysis/mercadona/top-items")
def api_mercadona_top_items():
    company = _get_mercadona()
    start = parse_date(request.args.get("start"), default_start())
    end   = parse_date(request.args.get("end"),   date.today())
    limit = int(request.args.get("limit", 15))
    return jsonify(get_top_items(start, end, company.id, limit))


@main.route("/api/analysis/mercadona/price-trend")
def api_mercadona_price_trend():
    company     = _get_mercadona()
    description = request.args.get("description", "").strip()
    start = parse_date(request.args.get("start"), default_start())
    end   = parse_date(request.args.get("end"),   date.today())
    if not description:
        return jsonify({"labels": [], "values": [], "description": ""})
    return jsonify(get_price_trend(description, start, end, company.id))


@main.route("/api/analysis/mercadona/item-suggestions")
def api_mercadona_item_suggestions():
    company = _get_mercadona()
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify([])
    return jsonify(get_item_suggestions(q, company_id=company.id))


# ---------------------------------------------------------------------------
# Company-specific analysis — Energy Nordic
# ---------------------------------------------------------------------------

@main.route("/analysis/energy-nordic")
def analysis_energy_nordic():
    company = Company.query.filter(
        db.func.lower(Company.name) == "energy nordic"
    ).first_or_404()

    # Date range — default last 12 months
    today = date.today()
    start_str = request.args.get("start", default_start().isoformat())
    end_str   = request.args.get("end",   today.isoformat())
    start_date = parse_date(start_str, default_start())
    end_date   = parse_date(end_str,   today)

    all_receipts = (
        Receipt.query
        .filter_by(company_id=company.id, status="confirmed")
        .order_by(Receipt.receipt_date)
        .all()
    )

    # Pending = any confirmed receipt across ALL dates that has no analysis
    pending = [r for r in all_receipts if not r.analysis]

    # Apply date filter for stats, table and charts
    receipts = [
        r for r in all_receipts
        if r.receipt_date and start_date <= r.receipt_date <= end_date
    ]

    analysed = []
    for r in receipts:
        if r.analysis:
            try:
                analysed.append({
                    "receipt_id": r.id,
                    "date": r.receipt_date.isoformat() if r.receipt_date else None,
                    "filename": r.filename,
                    "data": json.loads(r.analysis.data),
                })
            except (ValueError, TypeError):
                pass

    return render_template(
        "analysis_energy_nordic.html",
        company=company,
        analysed=analysed,
        pending=pending,
        total_receipts=len(receipts),
        start=start_str,
        end=end_str,
    )


@main.route("/analysis/energy-nordic/run", methods=["POST"])
def analysis_energy_nordic_run():
    """Run (or re-run) analysis on all Energy Nordic receipts that lack it."""
    from .company_analysers.energy_nordic import analyse, AnalysisError

    company = Company.query.filter(
        db.func.lower(Company.name) == "energy nordic"
    ).first_or_404()

    receipts = Receipt.query.filter_by(
        company_id=company.id, status="confirmed"
    ).all()

    done = 0
    errors = []

    for r in receipts:
        filepath = os.path.join(current_app.config["UPLOAD_FOLDER"], r.filename)
        if not os.path.exists(filepath):
            errors.append(f"{r.filename}: file not found in Receipts folder")
            continue

        try:
            data = analyse(filepath)
        except AnalysisError as e:
            errors.append(f"{r.filename}: {e}")
            continue

        # Upsert analysis record
        if r.analysis:
            r.analysis.data = json.dumps(data)
        else:
            ra = ReceiptAnalysis(
                receipt_id=r.id,
                analyser="energy_nordic",
                data=json.dumps(data),
            )
            db.session.add(ra)

        done += 1

    db.session.commit()

    if errors:
        for err in errors:
            flash(err, "error")
    flash(f"Analysis complete: {done} bill(s) processed.", "success")
    return redirect(url_for("main.analysis_energy_nordic"))


# ---------------------------------------------------------------------------
# Serve uploaded receipt files
# ---------------------------------------------------------------------------

@main.route("/uploads/<path:filename>")
def uploaded_file(filename):
    from flask import send_from_directory
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _float_or(lst, i, default):
    try:
        val = lst[i].strip() if i < len(lst) else ""
        return float(val) if val else default
    except (ValueError, AttributeError):
        return default
