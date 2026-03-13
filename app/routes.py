import os
import json
import config
from datetime import date, datetime
from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, current_app, jsonify, session
)
import logging
from flask_login import login_required, current_user, login_user, logout_user
log = logging.getLogger(__name__)
from werkzeug.utils import secure_filename
from . import db
from .extractor import extract_from_file, ExtractionError
from .template_manager import (
    get_template_items, apply_template_hints,
    update_template, set_template_items
)
from .models import Company, Receipt, LineItem, ReceiptAnalysis, ListItem, CompanyTemplate, Income, Account, Transaction, Shopper
from .company_analysers import get_analyser_key, canonical_name
from .reports_data import (
    parse_date, default_start,
    get_summary, get_spending_over_time,
    get_by_category, get_by_company,
    get_price_trend, get_item_suggestions,
    get_spend_per_visit, get_top_items,
    get_item_analysis,
    get_income_report,
)

main = Blueprint("main", __name__)


# ---------------------------------------------------------------------------
# Shopper helpers
# ---------------------------------------------------------------------------

def _view_as_shopper_id():
    """Returns shopper_id to filter receipts by, or None for all receipts (admin only)."""
    if current_user.is_admin:
        v = session.get('view_as', 'all')
        if v == 'all':
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None
    return current_user.id


def _apply_shopper_filter(query):
    """Apply shopper filter to a Receipt query based on current user / view_as."""
    sid = _view_as_shopper_id()
    if sid is not None:
        query = query.filter(Receipt.shopper_id == sid)
    return query


def _admin_required():
    """Flash and redirect if current user is not admin. Returns redirect or None."""
    if not current_user.is_admin:
        flash("Admin access required.", "error")
        return redirect(url_for("main.index"))
    return None


def admin_required(f):
    """Decorator: restricts route to admin users only."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            flash("Admin access required.", "error")
            return redirect(url_for("main.index"))
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# List helpers
# ---------------------------------------------------------------------------

def _get_categories():
    """Return sorted list of category values from the DB."""
    return [
        item.value for item in
        ListItem.query.filter_by(list_name="categories").order_by(ListItem.value).all()
    ]


def _get_company_types():
    """Return sorted list of company type values from the DB."""
    return [
        item.value for item in
        ListItem.query.filter_by(list_name="company_types").order_by(ListItem.value).all()
    ]


def _get_type_categories():
    """Return dict of {company_type: [categories]} for types that have a non-empty meta_list."""
    result = {}
    for item in ListItem.query.filter_by(list_name="company_types").order_by(ListItem.value).all():
        cats = item.meta_list
        if cats:
            result[item.value] = cats
    return result


ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "pdf"}


def _allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ---------------------------------------------------------------------------
# Auth — login / logout
# ---------------------------------------------------------------------------

_PASSPHRASE_WORDS = [
    "apple", "beach", "brick", "cloud", "coral", "crane", "creek", "crown",
    "delta", "dunes", "eagle", "falls", "field", "flame", "flint", "frost",
    "grove", "haven", "heron", "hills", "ivory", "jewel", "karma", "knoll",
    "lakes", "lemon", "light", "lotus", "lunar", "maple", "marsh", "mirth",
    "misty", "moose", "mount", "night", "noble", "north", "oasis", "ocean",
    "olive", "onyx", "orbit", "otter", "pearl", "petal", "pilot", "pines",
    "pixel", "plaza", "plume", "polar", "poppy", "prism", "quail", "quest",
    "quiet", "raven", "reeds", "ridge", "rivet", "robin", "rocky", "rover",
    "royal", "rusty", "sable", "saint", "sandy", "shark", "shore", "sigma",
    "silky", "skies", "slate", "snowy", "solar", "sonic", "spark", "spire",
    "spray", "storm", "stone", "sunny", "surge", "swamp", "swirl", "swift",
    "talon", "thorn", "tiger", "titan", "torch", "tower", "trail", "trout",
    "tulip", "ultra", "umbra", "unity", "valor", "vapor", "vault", "verde",
    "villa", "viola", "vivid", "volta", "waltz", "whirl", "white", "winds",
    "woods", "xenon", "yacht", "zebra", "zesty", "zippy",
]


def _generate_login_id():
    """Return a unique anon-NNNNNN identifier."""
    import random
    for _ in range(100):
        candidate = f"anon-{random.randint(100000, 999999)}"
        if not Shopper.query.filter_by(login_id=candidate).first():
            return candidate
    raise RuntimeError("Could not generate a unique login ID after 100 attempts")


def _generate_passphrase():
    """Return a memorable two-word passphrase: word-word-NN."""
    import random
    w1, w2 = random.sample(_PASSPHRASE_WORDS, 2)
    return f"{w1}-{w2}-{random.randint(10, 99)}"


@main.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip().lower()
        password   = request.form.get("password", "")
        # Accept anon-NNNNNN login_id or legacy email
        shopper = Shopper.query.filter(
            db.func.lower(Shopper.login_id) == identifier
        ).first()
        if not shopper:
            shopper = Shopper.query.filter(
                db.func.lower(Shopper.email) == identifier
            ).first()
        if shopper and shopper.is_active and shopper.check_password(password):
            login_user(shopper, remember=True)
            log.info(f"LOGIN  {shopper.display_id} ({shopper.nickname}) from {request.remote_addr}")
            next_page = request.args.get("next")
            return redirect(next_page or url_for("main.index"))
        log.warning(f"LOGIN FAILED  {identifier} from {request.remote_addr}")
        flash("Invalid login ID or password.", "error")
    return render_template("login.html")


@main.route("/logout")
def logout():
    log.info(f"LOGOUT {current_user.display_id if current_user.is_authenticated else '?'} from {request.remote_addr}")
    logout_user()
    return redirect(url_for("main.login"))


# ---------------------------------------------------------------------------
# Self-registration
# ---------------------------------------------------------------------------

_GENDER_OPTIONS    = ["Male", "Female"]
_AGE_RANGE_OPTIONS = ["Under 18", "18–24", "25–34", "35–44", "45–54", "55–64", "65–74", "75–84", "85+"]


@main.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    if request.method == "GET":
        return render_template(
            "register.html",
            login_id=_generate_login_id(),
            passphrase=_generate_passphrase(),
            gender_options=_GENDER_OPTIONS,
            age_range_options=_AGE_RANGE_OPTIONS,
        )

    # POST — create account
    login_id        = request.form.get("login_id", "").strip()
    passphrase      = request.form.get("passphrase", "").strip()
    custom_password = request.form.get("custom_password", "").strip()
    nickname        = request.form.get("nickname", "").strip()
    email           = request.form.get("email", "").strip().lower() or None
    gender          = request.form.get("gender", "").strip() or None
    age_range       = request.form.get("age_range", "").strip() or None
    consent         = request.form.get("consent")
    # Use custom password if provided and long enough, otherwise fall back to generated passphrase
    password_to_use = custom_password if len(custom_password) >= 6 else passphrase

    def _redisplay(error):
        flash(error, "error")
        return render_template(
            "register.html",
            login_id=login_id,
            passphrase=passphrase,
            gender_options=_GENDER_OPTIONS,
            age_range_options=_AGE_RANGE_OPTIONS,
            form=request.form,
        )

    if not consent:
        return _redisplay("You must accept the data usage terms to create an account.")
    if custom_password and len(custom_password) < 6:
        return _redisplay("Your chosen password must be at least 6 characters.")
    if not nickname:
        return _redisplay("Please choose a nickname.")
    if len(nickname) > 50:
        return _redisplay("Nickname must be 50 characters or fewer.")

    # Ensure login_id is still unique (race condition guard)
    if Shopper.query.filter_by(login_id=login_id).first():
        login_id   = _generate_login_id()
        passphrase = _generate_passphrase()
        return _redisplay("A collision occurred — new credentials have been generated. Please review and submit again.")

    if email and Shopper.query.filter(db.func.lower(Shopper.email) == email).first():
        return _redisplay("That email address is already registered.")

    shopper = Shopper(
        login_id=login_id,
        nickname=nickname,
        email=email,
        gender=gender,
        age_range=age_range,
        is_admin=False,
        is_active=True,
    )
    shopper.set_password(password_to_use)
    db.session.add(shopper)
    db.session.commit()

    login_user(shopper, remember=True)
    log.info(f"REGISTER  {login_id} ({nickname}) from {request.remote_addr}")

    if email:
        from .mailer import send_welcome_email
        send_welcome_email(current_app._get_current_object(), email, nickname, login_id, password_to_use)

    # Store credentials in session for one-time display on welcome page
    session["new_creds"] = {"login_id": login_id, "passphrase": password_to_use, "email": email}
    return redirect(url_for("main.register_welcome"))


@main.route("/register/welcome")
@login_required
def register_welcome():
    creds = session.pop("new_creds", None)
    if not creds:
        return redirect(url_for("main.index"))
    return render_template("register_welcome.html",
                           login_id=creds["login_id"],
                           passphrase=creds["passphrase"],
                           email_sent_to=creds.get("email"))


# ---------------------------------------------------------------------------
# Account self-deletion (GDPR Article 17 — soft delete)
# ---------------------------------------------------------------------------

@main.route("/account/delete", methods=["POST"])
@login_required
def account_delete():
    if current_user.is_admin:
        flash("Admin accounts cannot be self-deleted. Ask another admin to deactivate your account.", "error")
        return redirect(url_for("main.change_password"))
    confirm = request.form.get("confirm_delete", "").strip()
    if confirm.lower() != current_user.nickname.lower():
        flash("Confirmation did not match your nickname. Account not deleted.", "error")
        return redirect(url_for("main.change_password"))
    shopper = Shopper.query.get(current_user.id)
    shopper.is_active = False
    db.session.commit()
    log.info(f"ACCOUNT DEACTIVATED (self)  {shopper.display_id} ({shopper.nickname})")
    logout_user()
    flash("Your account has been deactivated. Contact an admin if you change your mind.", "info")
    return redirect(url_for("main.login"))


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@main.route("/")
@login_required
def index():
    sid = _view_as_shopper_id()
    q = Receipt.query.filter_by(status="confirmed")
    if sid is not None:
        q = q.filter(Receipt.shopper_id == sid)
    total_receipts = q.count()
    total_companies = Company.query.count() if current_user.is_admin else 0
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

    ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else "jpg"
    filename = datetime.now().strftime(f"%Y%m%d%H%M%S.{ext}")

    # Duplicate check — skip API call entirely if already in DB
    existing = Receipt.query.filter_by(filename=filename).first()
    if existing:
        if existing.status == "pending":
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
        shopper_id=current_user.id,
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
@login_required
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
                    f"Template applied: {matched} item(s) auto-categorised from previous {company.display_name} receipts.",
                    "info"
                )

    db.session.commit()
    log.info(f"UPLOAD  receipt#{receipt.id} {receipt.filename} by {current_user.nickname}")
    flash("Receipt scanned. Review and confirm the details below.", "info")
    return redirect(url_for("main.review", receipt_id=receipt.id))


@main.route("/quick-scan", methods=["GET", "POST"])
@login_required
def quick_scan():
    if request.method == "GET":
        return render_template("quick_scan.html")

    if "file" not in request.files or request.files["file"].filename == "":
        flash("No file selected.", "error")
        return redirect(url_for("main.quick_scan"))

    receipt, error = _process_one_file(request.files["file"])
    if error:
        flash(error, "error")
        return redirect(url_for("main.quick_scan"))

    db.session.commit()
    log.info(f"UPLOAD  receipt#{receipt.id} {receipt.filename} by {current_user.nickname} (quick-scan)")
    return redirect(url_for("main.review", receipt_id=receipt.id))


@main.route("/scan/batch", methods=["GET", "POST"])
@login_required
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
@login_required
def review(receipt_id):
    receipt = Receipt.query.get_or_404(receipt_id)
    companies = Company.query.order_by(Company.name).all()
    companies_data = [{"name": c.name, "type": c.type or ""} for c in companies]
    return render_template(
        "review.html",
        receipt=receipt,
        categories=_get_categories(),
        companies=companies,
        companies_data=companies_data,
        company_types=_get_company_types(),
        type_categories=_get_type_categories(),
        accounts=Account.query.order_by(Account.name).all(),
    )


# ---------------------------------------------------------------------------
# Confirm — save edits, mark confirmed, update template
# ---------------------------------------------------------------------------

@main.route("/scan/confirm/<int:receipt_id>", methods=["POST"])
@login_required
def confirm(receipt_id):
    receipt = Receipt.query.get_or_404(receipt_id)

    # Update or create company
    company_name = request.form.get("company_name", "").strip()
    company_type = request.form.get("company_type", "").strip() or None
    company = None
    if company_name:
        company = Company.query.filter(
            db.func.lower(Company.name) == company_name.lower()
        ).first()
        if not company:
            company = Company(name=company_name, type=company_type)
            db.session.add(company)
            db.session.flush()
        else:
            company.type = company_type
        receipt.company = company

    # Update receipt header fields
    receipt.document_type = request.form.get("document_type", "receipt")
    receipt.currency = request.form.get("currency", "EUR")
    receipt.account_id = request.form.get("account_id", type=int) or None
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

    # Odometer reading (Petrol receipts) — stored as a zero-cost line item
    odometer_km = request.form.get("odometer_km", "").strip()
    if odometer_km:
        try:
            km = float(odometer_km)
            li = LineItem(
                receipt_id=receipt.id,
                description="Odometer Reading",
                quantity=km,
                unit_price=0.0,
                total_price=0.0,
                category="odometer",
            )
            db.session.add(li)
            saved_items.append(li)
        except ValueError:
            pass

    db.session.flush()

    # Update company template with categorised items
    if company and saved_items:
        update_template(company.id, saved_items)

    receipt.updated_at = datetime.now()
    db.session.commit()

    # Run company-specific analysis if one exists for this company
    if company:
        analyser_key = get_analyser_key(company.name, company.type)
        if analyser_key == "electricity":
            from .company_analysers.electricity import analyse, AnalysisError
            filepath = os.path.join(current_app.config["UPLOAD_FOLDER"], receipt.filename)
            if os.path.exists(filepath):
                try:
                    data = analyse(filepath)
                    if receipt.analysis:
                        receipt.analysis.data = json.dumps(data)
                    else:
                        db.session.add(ReceiptAnalysis(
                            receipt_id=receipt.id,
                            analyser="electricity",
                            data=json.dumps(data),
                        ))
                    db.session.commit()
                    flash("Electricity analysis updated automatically.", "info")
                except AnalysisError as e:
                    flash(f"Analysis could not run: {e}", "error")

    log.info(f"CONFIRM receipt#{receipt.id} {receipt.filename} by {current_user.nickname}")
    flash("Receipt confirmed and saved.", "success")
    if request.form.get("from_grouped"):
        return redirect(url_for("main.receipts", view="grouped"))
    return redirect(url_for("main.receipts"))


# ---------------------------------------------------------------------------
# Receipts list
# ---------------------------------------------------------------------------

@main.route("/receipts")
@login_required
def receipts():
    sid = _view_as_shopper_id()
    confirmed_q = Receipt.query.filter_by(status="confirmed")
    pending_q   = Receipt.query.filter_by(status="pending")
    if sid is not None:
        confirmed_q = confirmed_q.filter(Receipt.shopper_id == sid)
        pending_q   = pending_q.filter(Receipt.shopper_id == sid)
    confirmed = confirmed_q.order_by(Receipt.receipt_date.desc()).all()
    pending   = pending_q.order_by(Receipt.created_at.desc()).all()
    return render_template("receipts.html", receipts=confirmed, pending=pending)


# ---------------------------------------------------------------------------
# Delete a pending receipt
# ---------------------------------------------------------------------------

@main.route("/receipts/<int:receipt_id>/delete", methods=["POST"])
@login_required
def delete_receipt(receipt_id):
    receipt = Receipt.query.get_or_404(receipt_id)
    LineItem.query.filter_by(receipt_id=receipt.id).delete()
    # Remove uploaded file
    filepath = os.path.join(current_app.config["UPLOAD_FOLDER"], receipt.filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    log.info(f"DELETE  receipt#{receipt.id} {receipt.filename} by {current_user.nickname}")
    db.session.delete(receipt)
    db.session.commit()
    flash(f"Receipt '{receipt.filename}' deleted.", "success")
    return redirect(url_for("main.receipts"))


# ---------------------------------------------------------------------------
# Process all pending receipts without individual review
# ---------------------------------------------------------------------------

@main.route("/receipts/process-all-pending", methods=["POST"])
@login_required
def process_all_pending():
    sid = _view_as_shopper_id()
    q = Receipt.query.filter_by(status="pending")
    if sid is not None:
        q = q.filter(Receipt.shopper_id == sid)
    pending = q.all()

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
            analyser_key = get_analyser_key(company.name, company.type)
            if analyser_key == "electricity":
                from .company_analysers.electricity import analyse, AnalysisError
                filepath = os.path.join(current_app.config["UPLOAD_FOLDER"], receipt.filename)
                if os.path.exists(filepath):
                    try:
                        data = analyse(filepath)
                        if receipt.analysis:
                            receipt.analysis.data = json.dumps(data)
                        else:
                            db.session.add(ReceiptAnalysis(
                                receipt_id=receipt.id,
                                analyser="electricity",
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
@login_required
def edit_receipt(receipt_id):
    receipt = Receipt.query.get_or_404(receipt_id)
    companies = Company.query.order_by(Company.name).all()
    companies_data = [{"name": c.name, "type": c.type or ""} for c in companies]
    return render_template(
        "review.html",
        receipt=receipt,
        categories=_get_categories(),
        companies=companies,
        companies_data=companies_data,
        company_types=_get_company_types(),
        type_categories=_get_type_categories(),
        editing=True,
        from_grouped=bool(request.args.get("grouped")),
        accounts=Account.query.order_by(Account.name).all(),
    )


# ---------------------------------------------------------------------------
# Companies — list
# ---------------------------------------------------------------------------

@main.route("/companies")
@login_required
def companies():
    if current_user.is_admin:
        all_companies = Company.query.order_by(Company.name).all()
    else:
        sid = current_user.id
        company_ids = db.session.query(Receipt.company_id).filter(
            Receipt.shopper_id == sid, Receipt.status == "confirmed",
            Receipt.company_id.isnot(None)
        ).distinct()
        all_companies = Company.query.filter(Company.id.in_(company_ids)).order_by(Company.name).all()
    return render_template(
        "companies.html",
        companies=all_companies,
    )


# ---------------------------------------------------------------------------
# Company detail — view and edit template
# ---------------------------------------------------------------------------

@main.route("/companies/<int:company_id>", methods=["GET", "POST"])
@login_required
def company_detail(company_id):
    company = Company.query.get_or_404(company_id)

    if request.method == "POST":
        # Save company type and alias
        company.type = request.form.get("company_type", "").strip() or None
        company.alias = request.form.get("company_alias", "").strip() or None

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
        flash(f"Template for {company.display_name} updated ({len(items)} items).", "success")
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
        categories=_get_categories(),
        company_types=_get_company_types(),
    )


# ---------------------------------------------------------------------------
# Reports page
# ---------------------------------------------------------------------------

@main.route("/reports")
@login_required
def reports():
    sid = _view_as_shopper_id()
    if sid is not None:
        company_ids = db.session.query(Receipt.company_id).filter(
            Receipt.shopper_id == sid, Receipt.status == "confirmed",
            Receipt.company_id.isnot(None)
        ).distinct()
        companies    = Company.query.filter(Company.id.in_(company_ids)).order_by(Company.name).all()
        supermarkets = [c for c in companies if c.type == "Supermarket"]
    else:
        companies    = Company.query.order_by(Company.name).all()
        supermarkets = Company.query.filter_by(type="Supermarket").order_by(Company.name).all()
    return render_template("reports.html", companies=companies, supermarkets=supermarkets)


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
@login_required
def api_summary():
    start      = parse_date(request.args.get("start"), default_start())
    end        = parse_date(request.args.get("end"),   date.today())
    company_id = _company_id_arg()
    return jsonify(get_summary(start, end, company_id, shopper_id=_view_as_shopper_id()))


@main.route("/api/spending-over-time")
@login_required
def api_spending_over_time():
    start      = parse_date(request.args.get("start"), default_start())
    end        = parse_date(request.args.get("end"),   date.today())
    group_by   = request.args.get("group_by", "month")
    company_id = _company_id_arg()
    return jsonify(get_spending_over_time(start, end, group_by, company_id, shopper_id=_view_as_shopper_id()))


@main.route("/api/by-category")
@login_required
def api_by_category():
    start      = parse_date(request.args.get("start"), default_start())
    end        = parse_date(request.args.get("end"),   date.today())
    company_id = _company_id_arg()
    return jsonify(get_by_category(start, end, company_id, shopper_id=_view_as_shopper_id()))


@main.route("/api/by-company")
@login_required
def api_by_company():
    start      = parse_date(request.args.get("start"), default_start())
    end        = parse_date(request.args.get("end"),   date.today())
    company_id = _company_id_arg()
    return jsonify(get_by_company(start, end, company_id=company_id, shopper_id=_view_as_shopper_id()))


@main.route("/api/price-trend")
@login_required
def api_price_trend():
    description = request.args.get("description", "").strip()
    start       = parse_date(request.args.get("start"), default_start())
    end         = parse_date(request.args.get("end"),   date.today())
    company_id  = _company_id_arg()
    if not description:
        return jsonify({"labels": [], "values": [], "description": ""})
    return jsonify(get_price_trend(description, start, end, company_id, shopper_id=_view_as_shopper_id()))


@main.route("/api/item-suggestions")
@login_required
def api_item_suggestions():
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify([])
    return jsonify(get_item_suggestions(q, shopper_id=_view_as_shopper_id()))




# ---------------------------------------------------------------------------
# Generic company analysis — works for any company
# ---------------------------------------------------------------------------

@main.route('/analysis/company/<int:company_id>')
@login_required
@admin_required
def analysis_company(company_id):
    company = Company.query.get_or_404(company_id)
    return render_template('analysis_company.html', company=company)


@main.route('/api/company/<int:company_id>/per-visit')
@login_required
def api_company_per_visit(company_id):
    Company.query.get_or_404(company_id)
    start = parse_date(request.args.get('start'), default_start())
    end   = parse_date(request.args.get('end'),   date.today())
    return jsonify(get_spend_per_visit(start, end, company_id))


@main.route('/api/company/<int:company_id>/top-items')
@login_required
def api_company_top_items(company_id):
    Company.query.get_or_404(company_id)
    start = parse_date(request.args.get('start'), default_start())
    end   = parse_date(request.args.get('end'),   date.today())
    limit = int(request.args.get('limit', 15))
    return jsonify(get_top_items(start, end, company_id, limit))


# ---------------------------------------------------------------------------
# Item Search (admin only)
# ---------------------------------------------------------------------------

@main.route('/items/search')
@login_required
@admin_required
def item_search():
    companies = Company.query.order_by(Company.name).all()
    return render_template('item_search.html', companies=companies)


@main.route('/api/item-search')
@login_required
@admin_required
def api_item_search():
    q          = request.args.get('q', '')
    company_id = request.args.get('company_id', type=int)

    query = (
        db.session.query(LineItem, Receipt, Company)
        .join(Receipt, LineItem.receipt_id == Receipt.id)
        .join(Company, Receipt.company_id == Company.id)
        .filter(Receipt.status == 'confirmed')
    )

    if q.strip():
        query = query.filter(LineItem.description.ilike('%' + q.strip() + '%'))
    else:
        query = query.filter(
            db.or_(LineItem.description == '', LineItem.description == None)
        )

    if company_id:
        query = query.filter(Receipt.company_id == company_id)

    query = query.order_by(Receipt.receipt_date.desc()).limit(200)

    results = []
    for li, r, c in query.all():
        results.append({
            'id':           li.id,
            'description':  li.description,
            'quantity':     li.quantity,
            'unit_price':   li.unit_price,
            'total_price':  li.total_price,
            'category':     li.category,
            'receipt_id':   r.id,
            'receipt_date': r.receipt_date.isoformat() if r.receipt_date else None,
            'company_name': c.alias or c.name,
        })

    return jsonify(results)


# ---------------------------------------------------------------------------
# Electricity analysis — works for any "Utility - Electric" company
# ---------------------------------------------------------------------------

@main.route("/analysis/electricity/<int:company_id>")
@login_required
@admin_required
def analysis_electricity(company_id):
    company = Company.query.get_or_404(company_id)

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

    pending = [r for r in all_receipts if not r.analysis]

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
        "analysis_electricity.html",
        company=company,
        analysed=analysed,
        pending=pending,
        total_receipts=len(receipts),
        start=start_str,
        end=end_str,
    )


@main.route("/analysis/electricity/<int:company_id>/run", methods=["POST"])
@login_required
@admin_required
def analysis_electricity_run(company_id):
    from .company_analysers.electricity import analyse, AnalysisError
    company = Company.query.get_or_404(company_id)

    receipts = Receipt.query.filter_by(
        company_id=company.id, status="confirmed"
    ).all()

    done = 0
    errors = []

    for r in receipts:
        filepath = os.path.join(current_app.config["UPLOAD_FOLDER"], r.filename)
        if not os.path.exists(filepath):
            errors.append(f"{r.filename}: file not found")
            continue

        try:
            data = analyse(filepath)
        except AnalysisError as e:
            errors.append(f"{r.filename}: {e}")
            continue

        if r.analysis:
            r.analysis.data = json.dumps(data)
        else:
            db.session.add(ReceiptAnalysis(
                receipt_id=r.id,
                analyser="electricity",
                data=json.dumps(data),
            ))
        done += 1

    db.session.commit()

    if errors:
        for err in errors:
            flash(err, "error")
    flash(f"Analysis complete: {done} bill(s) processed.", "success")
    return redirect(url_for("main.analysis_electricity", company_id=company_id))


# Backward-compat redirects for old /analysis/energy-nordic URLs
@main.route("/analysis/energy-nordic")
@login_required
@admin_required
def analysis_energy_nordic():
    company = Company.query.filter(
        db.func.lower(Company.name) == "energy nordic"
    ).first_or_404()
    return redirect(url_for("main.analysis_electricity", company_id=company.id))


@main.route("/analysis/energy-nordic/run", methods=["POST"])
@login_required
@admin_required
def analysis_energy_nordic_run():
    company = Company.query.filter(
        db.func.lower(Company.name) == "energy nordic"
    ).first_or_404()
    return redirect(url_for("main.analysis_electricity", company_id=company.id))


# ---------------------------------------------------------------------------
# Serve uploaded receipt files
# ---------------------------------------------------------------------------

@main.route("/uploads/<path:filename>")
@login_required
def uploaded_file(filename):
    from flask import send_from_directory
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)


# ---------------------------------------------------------------------------
# Settings — manage dropdown lists
# ---------------------------------------------------------------------------

@main.route("/settings")
@login_required
@admin_required
def settings():
    company_types = (
        ListItem.query
        .filter_by(list_name="company_types")
        .order_by(ListItem.value)
        .all()
    )
    categories = (
        ListItem.query
        .filter_by(list_name="categories")
        .order_by(ListItem.value)
        .all()
    )
    income_categories = (
        ListItem.query
        .filter_by(list_name="income_categories")
        .order_by(ListItem.value)
        .all()
    )
    account_types = (
        ListItem.query
        .filter_by(list_name="account_types")
        .order_by(ListItem.value)
        .all()
    )
    return render_template(
        "settings.html",
        company_types=company_types,
        categories=categories,
        income_categories=income_categories,
        account_types=account_types,
        app_version=config.APP_VERSION,
    )


@main.route("/settings/lists/<list_name>/add", methods=["POST"])
@login_required
@admin_required
def settings_list_add(list_name):
    if list_name not in ("company_types", "categories", "income_categories", "account_types"):
        flash("Unknown list.", "error")
        return redirect(url_for("main.settings"))

    value = request.form.get("value", "").strip()
    if not value:
        flash("Value cannot be empty.", "error")
        return redirect(url_for("main.settings"))

    existing = ListItem.query.filter_by(list_name=list_name, value=value).first()
    if existing:
        flash(f"'{value}' already exists in {list_name}.", "error")
        return redirect(url_for("main.settings"))

    max_order = db.session.query(db.func.max(ListItem.sort_order)).filter_by(list_name=list_name).scalar() or 0
    db.session.add(ListItem(list_name=list_name, value=value, sort_order=max_order + 1))
    db.session.commit()
    flash(f"Added '{value}' to {list_name.replace('_', ' ')}.", "success")
    return redirect(url_for("main.settings"))


@main.route("/settings/lists/<int:item_id>/delete", methods=["POST"])
@login_required
@admin_required
def settings_list_delete(item_id):
    item = ListItem.query.get_or_404(item_id)
    value = item.value
    list_name = item.list_name

    if list_name == "categories":
        # Clear category from line items
        LineItem.query.filter_by(category=value).update({"category": None})
        # Patch template JSON blobs
        for tmpl in CompanyTemplate.query.all():
            try:
                items = json.loads(tmpl.known_items) if tmpl.known_items else []
                patched = [
                    {**it, "category": None} if it.get("category") == value else it
                    for it in items
                ]
                if patched != items:
                    tmpl.known_items = json.dumps(patched)
            except (ValueError, TypeError):
                pass
        # Remove from company type meta lists
        for ct in ListItem.query.filter_by(list_name="company_types").all():
            cats = ct.meta_list
            if value in cats:
                ct.meta = json.dumps([c for c in cats if c != value])

    elif list_name == "company_types":
        # Clear type from companies
        Company.query.filter_by(type=value).update({"type": None})

    elif list_name == "income_categories":
        Income.query.filter_by(category=value).update({"category": None})

    elif list_name == "account_types":
        Account.query.filter_by(account_type=value).update({"account_type": None})

    db.session.delete(item)
    db.session.commit()
    flash(f"Deleted '{value}' from {list_name.replace('_', ' ')}.", "success")
    return redirect(url_for("main.settings"))


@main.route("/settings/lists/<int:item_id>/rename", methods=["POST"])
@login_required
@admin_required
def settings_list_rename(item_id):
    item = ListItem.query.get_or_404(item_id)
    old_value = item.value
    new_value = request.form.get("value", "").strip()

    if not new_value:
        flash("New name cannot be empty.", "error")
        return redirect(url_for("main.settings"))

    if new_value == old_value:
        return redirect(url_for("main.settings"))

    existing = ListItem.query.filter_by(list_name=item.list_name, value=new_value).first()
    if existing:
        flash(f"'{new_value}' already exists.", "error")
        return redirect(url_for("main.settings"))

    if item.list_name == "categories":
        # Cascade: line items
        LineItem.query.filter_by(category=old_value).update({"category": new_value})
        # Cascade: template JSON blobs
        for tmpl in CompanyTemplate.query.all():
            try:
                items = json.loads(tmpl.known_items) if tmpl.known_items else []
                patched = [
                    {**it, "category": new_value} if it.get("category") == old_value else it
                    for it in items
                ]
                if patched != items:
                    tmpl.known_items = json.dumps(patched)
            except (ValueError, TypeError):
                pass
        # Cascade: company type meta lists
        for ct in ListItem.query.filter_by(list_name="company_types").all():
            cats = ct.meta_list
            if old_value in cats:
                ct.meta = json.dumps([new_value if c == old_value else c for c in cats])

    elif item.list_name == "company_types":
        # Cascade: companies
        Company.query.filter_by(type=old_value).update({"type": new_value})

    elif item.list_name == "income_categories":
        Income.query.filter_by(category=old_value).update({"category": new_value})

    elif item.list_name == "account_types":
        Account.query.filter_by(account_type=old_value).update({"account_type": new_value})

    item.value = new_value
    db.session.commit()
    flash(f"Renamed '{old_value}' to '{new_value}'.", "success")
    return redirect(url_for("main.settings"))


@main.route("/settings/types/<int:item_id>/categories", methods=["POST"])
@login_required
@admin_required
def settings_type_categories(item_id):
    item = ListItem.query.get_or_404(item_id)
    if item.list_name != "company_types":
        flash("Not a company type.", "error")
        return redirect(url_for("main.settings"))

    selected = request.form.getlist("categories")
    item.meta = json.dumps(selected) if selected else None
    db.session.commit()
    flash(f"Categories updated for '{item.value}'.", "success")
    return redirect(url_for("main.settings"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@main.route("/price-tracker")
@login_required
def price_tracker():
    return render_template("price_tracker.html")


def _float_or(lst, i, default):
    try:
        val = lst[i].strip() if i < len(lst) else ""
        return float(val) if val else default
    except (ValueError, AttributeError):
        return default

# ---------------------------------------------------------------------------
# Income helpers
# ---------------------------------------------------------------------------

def _get_income_categories():
    return [
        item.value for item in
        ListItem.query.filter_by(list_name="income_categories").order_by(ListItem.value).all()
    ]


def _get_account_types():
    return [
        item.value for item in
        ListItem.query.filter_by(list_name="account_types").order_by(ListItem.value).all()
    ]


# ---------------------------------------------------------------------------
# Income — manage entries
# ---------------------------------------------------------------------------

@main.route("/income")
@login_required
@admin_required
def income():
    entries = Income.query.order_by(Income.date.desc()).all()
    income_cats = _get_income_categories()
    return render_template("income.html", entries=entries, income_cats=income_cats)


@main.route("/income/add", methods=["POST"])
@login_required
@admin_required
def income_add():
    try:
        entry = Income(
            date=date.fromisoformat(request.form["date"]),
            source=request.form["source"].strip(),
            amount=float(request.form["amount"]),
            category=request.form.get("category", "").strip() or None,
            notes=request.form.get("notes", "").strip() or None,
        )
        db.session.add(entry)
        db.session.commit()
        flash("Income entry added.", "success")
    except (ValueError, KeyError) as e:
        flash(f"Error adding entry: {e}", "error")
    return redirect(url_for("main.income"))


@main.route("/income/<int:entry_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def income_edit(entry_id):
    entry = Income.query.get_or_404(entry_id)
    income_cats = _get_income_categories()
    if request.method == "POST":
        try:
            entry.date     = date.fromisoformat(request.form["date"])
            entry.source   = request.form["source"].strip()
            entry.amount   = float(request.form["amount"])
            entry.category = request.form.get("category", "").strip() or None
            entry.notes    = request.form.get("notes", "").strip() or None
            db.session.commit()
            flash("Income entry updated.", "success")
        except (ValueError, KeyError) as e:
            flash(f"Error updating entry: {e}", "error")
        return redirect(url_for("main.income"))
    return render_template("income_edit.html", entry=entry, income_cats=income_cats)


@main.route("/income/<int:entry_id>/delete", methods=["POST"])
@login_required
@admin_required
def income_delete(entry_id):
    entry = Income.query.get_or_404(entry_id)
    db.session.delete(entry)
    db.session.commit()
    flash("Income entry deleted.", "success")
    return redirect(url_for("main.income"))


# ---------------------------------------------------------------------------
# Accounts — manage opening balances
# ---------------------------------------------------------------------------

@main.route("/accounts")
@login_required
@admin_required
def accounts():
    accts = Account.query.order_by(Account.name).all()
    account_types = _get_account_types()
    total_assets      = round(sum(a.opening_balance for a in accts if a.opening_balance > 0), 2)
    total_liabilities = round(sum(a.opening_balance for a in accts if a.opening_balance < 0), 2)
    net_worth         = round(sum(a.opening_balance for a in accts), 2)
    return render_template(
        "accounts.html",
        accounts=accts,
        account_types=account_types,
        total_assets=total_assets,
        total_liabilities=total_liabilities,
        net_worth=net_worth,
    )


@main.route("/accounts/add", methods=["POST"])
@login_required
@admin_required
def accounts_add():
    try:
        acct = Account(
            name=request.form["name"].strip(),
            account_type=request.form.get("account_type", "").strip() or None,
            opening_balance=float(request.form["opening_balance"]),
            opening_date=date.fromisoformat(request.form["opening_date"]),
            notes=request.form.get("notes", "").strip() or None,
        )
        db.session.add(acct)
        db.session.commit()
        flash("Account added.", "success")
    except (ValueError, KeyError) as e:
        flash(f"Error adding account: {e}", "error")
    return redirect(url_for("main.accounts"))


@main.route("/accounts/<int:account_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def accounts_edit(account_id):
    acct = Account.query.get_or_404(account_id)
    account_types = _get_account_types()
    if request.method == "POST":
        try:
            acct.name            = request.form["name"].strip()
            acct.account_type    = request.form.get("account_type", "").strip() or None
            acct.opening_balance = float(request.form["opening_balance"])
            acct.opening_date    = date.fromisoformat(request.form["opening_date"])
            acct.notes           = request.form.get("notes", "").strip() or None
            db.session.commit()
            flash("Account updated.", "success")
        except (ValueError, KeyError) as e:
            flash(f"Error updating account: {e}", "error")
        return redirect(url_for("main.accounts"))
    return render_template("accounts_edit.html", account=acct, account_types=account_types)


@main.route("/accounts/<int:account_id>/delete", methods=["POST"])
@login_required
@admin_required
def accounts_delete(account_id):
    acct = Account.query.get_or_404(account_id)
    db.session.delete(acct)
    db.session.commit()
    flash("Account deleted.", "success")
    return redirect(url_for("main.accounts"))


# ---------------------------------------------------------------------------
# Income Report
# ---------------------------------------------------------------------------

@main.route("/income-reports")
@login_required
@admin_required
def income_reports():
    return render_template("income_reports.html")


@main.route("/api/income-report")
@login_required
@admin_required
def api_income_report():
    start = parse_date(request.args.get("start"), default_start())
    end   = parse_date(request.args.get("end"),   date.today())
    return jsonify(get_income_report(start, end))

# ---------------------------------------------------------------------------
# Income Dashboard
# ---------------------------------------------------------------------------

@main.route("/income-dashboard")
@login_required
@admin_required
def income_dashboard():
    from .models import Income, Account
    total_entries = Income.query.count()
    total_accounts = Account.query.count()
    accounts = Account.query.order_by(Account.name).all()
    net_worth = round(sum(a.opening_balance for a in accounts), 2)
    return render_template(
        "income_dashboard.html",
        total_entries=total_entries,
        total_accounts=total_accounts,
        net_worth=net_worth,
    )

# ---------------------------------------------------------------------------
# Statement import helper
# ---------------------------------------------------------------------------

def _find_matching_receipt(description, txn_date, amount):
    """Return a confirmed receipt that likely matches this transaction, or None."""
    from datetime import timedelta
    words = [w for w in description.split() if len(w) >= 4]
    if not words:
        return None
    for word in words[:2]:
        matches = Company.query.filter(
            db.func.lower(Company.name).contains(word.lower())
        ).all()
        for company in matches:
            for r in Receipt.query.filter(
                Receipt.company_id == company.id,
                Receipt.status == "confirmed",
                Receipt.receipt_date >= txn_date - timedelta(days=2),
                Receipt.receipt_date <= txn_date + timedelta(days=2),
            ).all():
                if r.total_amount and abs(r.total_amount - amount) / max(amount, 0.01) <= 0.05:
                    return r
    return None


# ---------------------------------------------------------------------------
# Statement import — upload → preview → confirm
# ---------------------------------------------------------------------------

@main.route("/import")
@login_required
@admin_required
def import_statement():
    accounts = Account.query.order_by(Account.name).all()
    categories = _get_categories()
    return render_template("import_statement.html", accounts=accounts, categories=categories)


@main.route("/import/preview", methods=["POST"])
@login_required
@admin_required
def import_preview():
    f = request.files.get("file")
    if not f or not f.filename:
        flash("No file selected.", "error")
        return redirect(url_for("main.import_statement"))

    account_id = request.form.get("account_id", type=int)
    accounts   = Account.query.order_by(Account.name).all()
    categories = _get_categories()

    filename   = f.filename.lower()
    file_bytes = f.read()

    try:
        if filename.endswith(".csv"):
            from .statement_parsers import wise_csv
            rows = wise_csv.parse(file_bytes)
            source_label = "Wise CSV"
        elif filename.endswith(".pdf"):
            from .statement_parsers import sabadell_pdf
            rows = sabadell_pdf.parse(file_bytes)
            source_label = "Banco Sabadell PDF"
        else:
            flash("Unsupported file type. Upload a .csv or .pdf statement.", "error")
            return redirect(url_for("main.import_statement"))
    except Exception as e:
        flash(f"Error parsing file: {e}", "error")
        return redirect(url_for("main.import_statement"))

    if not rows:
        flash("No transactions found in file.", "error")
        return redirect(url_for("main.import_statement"))

    for row in rows:
        row["suggested_skip"] = False
        row["skip_reason"]    = ""
        # Already imported?
        if row.get("transaction_id"):
            if Transaction.query.filter_by(transaction_id=row["transaction_id"]).first():
                row["suggested_skip"] = True
                row["skip_reason"]    = "Already imported"
                continue
        # Auto-detect matching scanned receipt (OUT only)
        if row["direction"] == "out":
            match = _find_matching_receipt(
                row["description"], date.fromisoformat(row["date"]), row["amount"]
            )
            if match:
                company_name = match.company.name if match.company else "?"
                row["suggested_skip"] = True
                row["skip_reason"] = (
                    f"Matches receipt #{match.id} "
                    f"({company_name}, {match.receipt_date}, €{match.total_amount:.2f})"
                )

    return render_template(
        "import_preview.html",
        rows=rows,
        row_count=len(rows),
        account_id=account_id,
        accounts=accounts,
        categories=categories,
        source_label=source_label,
    )


@main.route("/import/confirm", methods=["POST"])
@login_required
@admin_required
def import_confirm():
    account_id = request.form.get("account_id", type=int)
    row_count  = request.form.get("row_count", type=int, default=0)

    imported       = 0
    income_added   = 0
    skipped_dupe   = 0

    for i in range(row_count):
        if not request.form.get(f"include_{i}"):
            continue

        direction      = request.form.get(f"direction_{i}", "out")
        date_str       = request.form.get(f"date_{i}", "")
        description    = request.form.get(f"description_{i}", "").strip()
        amount_str     = request.form.get(f"amount_{i}", "0")
        category       = request.form.get(f"category_{i}", "").strip() or None
        notes          = request.form.get(f"notes_{i}", "").strip() or None
        transaction_id = request.form.get(f"transaction_id_{i}", "").strip() or None
        source         = request.form.get(f"source_{i}", "")

        if not date_str:
            continue
        try:
            txn_date = date.fromisoformat(date_str)
            amount   = float(amount_str)
        except (ValueError, TypeError):
            continue
        if amount == 0:
            continue

        # Duplicate check
        if transaction_id and Transaction.query.filter_by(transaction_id=transaction_id).first():
            skipped_dupe += 1
            continue

        if direction == "in":
            db.session.add(Income(
                date=txn_date, source=description, amount=amount,
                category="Other", notes=notes,
            ))
            income_added += 1
        else:
            db.session.add(Transaction(
                account_id=account_id, date=txn_date, description=description,
                amount=amount, direction=direction, category=category,
                notes=notes, transaction_id=transaction_id, source=source,
            ))
            imported += 1

    db.session.commit()

    parts = []
    if imported:     parts.append(f"{imported} transaction(s)")
    if income_added: parts.append(f"{income_added} income entry(ies)")
    if skipped_dupe: parts.append(f"{skipped_dupe} duplicate(s) skipped")
    flash("Imported: " + (", ".join(parts) or "nothing") + ".", "success")
    return redirect(url_for("main.transactions"))


# ---------------------------------------------------------------------------
# Transactions — list, edit, delete
# ---------------------------------------------------------------------------

@main.route("/transactions")
@login_required
@admin_required
def transactions():
    txns     = Transaction.query.order_by(Transaction.date.desc()).all()
    accounts = Account.query.order_by(Account.name).all()
    account_map = {a.id: a.name for a in accounts}
    return render_template("transactions.html", transactions=txns, account_map=account_map)


@main.route("/transactions/<int:txn_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def transaction_edit(txn_id):
    txn        = Transaction.query.get_or_404(txn_id)
    categories = _get_categories()
    accounts   = Account.query.order_by(Account.name).all()
    if request.method == "POST":
        try:
            txn.date        = date.fromisoformat(request.form["date"])
            txn.description = request.form["description"].strip()
            txn.amount      = float(request.form["amount"])
            txn.category    = request.form.get("category", "").strip() or None
            txn.notes       = request.form.get("notes", "").strip() or None
            txn.account_id  = request.form.get("account_id", type=int) or None
            db.session.commit()
            flash("Transaction updated.", "success")
        except (ValueError, KeyError) as e:
            flash(f"Error: {e}", "error")
        return redirect(url_for("main.transactions"))
    return render_template("transaction_edit.html", txn=txn, categories=categories, accounts=accounts)


@main.route("/transactions/<int:txn_id>/delete", methods=["POST"])
@login_required
@admin_required
def transaction_delete(txn_id):
    txn = Transaction.query.get_or_404(txn_id)
    db.session.delete(txn)
    db.session.commit()
    flash("Transaction deleted.", "success")
    return redirect(url_for("main.transactions"))


# ---------------------------------------------------------------------------
# Shopper management (admin only)
# ---------------------------------------------------------------------------

@main.route("/shoppers")
@login_required
def shoppers():
    redir = _admin_required()
    if redir:
        return redir
    all_shoppers = Shopper.query.order_by(Shopper.nickname).all()
    for s in all_shoppers:
        s.receipt_count = Receipt.query.filter_by(shopper_id=s.id, status="confirmed").count()
    return render_template("shoppers.html", shoppers=all_shoppers)


@main.route("/shoppers/new", methods=["GET", "POST"])
@login_required
def shopper_new():
    redir = _admin_required()
    if redir:
        return redir
    if request.method == "POST":
        email     = request.form.get("email", "").strip().lower() or None
        full_name = request.form.get("full_name", "").strip() or None
        nickname  = request.form.get("nickname", "").strip()
        password  = request.form.get("password", "")
        is_admin  = bool(request.form.get("is_admin"))
        gender    = request.form.get("gender", "").strip() or None
        age_range = request.form.get("age_range", "").strip() or None
        if not nickname or not password:
            flash("Nickname and password are required.", "error")
            return render_template("shopper_edit.html", shopper=None,
                                   gender_options=_GENDER_OPTIONS,
                                   age_range_options=_AGE_RANGE_OPTIONS)
        if email and Shopper.query.filter(db.func.lower(Shopper.email) == email).first():
            flash(f"Email '{email}' is already registered.", "error")
            return render_template("shopper_edit.html", shopper=None,
                                   gender_options=_GENDER_OPTIONS,
                                   age_range_options=_AGE_RANGE_OPTIONS)
        s = Shopper(email=email, full_name=full_name, nickname=nickname,
                    gender=gender, age_range=age_range,
                    is_admin=is_admin, is_active=True)
        s.set_password(password)
        db.session.add(s)
        db.session.commit()
        log.info(f"SHOPPER ADD  {email or nickname} ({nickname}) by {current_user.nickname}")
        flash(f"Shopper '{nickname}' added.", "success")
        return redirect(url_for("main.shoppers"))
    return render_template("shopper_edit.html", shopper=None,
                           gender_options=_GENDER_OPTIONS,
                           age_range_options=_AGE_RANGE_OPTIONS)


@main.route("/shoppers/<int:shopper_id>/edit", methods=["GET", "POST"])
@login_required
def shopper_edit(shopper_id):
    redir = _admin_required()
    if redir:
        return redir
    s = Shopper.query.get_or_404(shopper_id)
    if request.method == "POST":
        email     = request.form.get("email", "").strip().lower() or None
        full_name = request.form.get("full_name", "").strip() or None
        nickname  = request.form.get("nickname", "").strip()
        is_admin  = bool(request.form.get("is_admin"))
        new_pw    = request.form.get("password", "").strip()
        gender    = request.form.get("gender", "").strip() or None
        age_range = request.form.get("age_range", "").strip() or None
        if not nickname:
            flash("Nickname is required.", "error")
            return render_template("shopper_edit.html", shopper=s,
                                   gender_options=_GENDER_OPTIONS,
                                   age_range_options=_AGE_RANGE_OPTIONS)
        # Check for email conflict with another shopper (only if email provided)
        if email:
            conflict = Shopper.query.filter(
                db.func.lower(Shopper.email) == email,
                Shopper.id != s.id
            ).first()
            if conflict:
                flash(f"Email '{email}' is already in use.", "error")
                return render_template("shopper_edit.html", shopper=s,
                                       gender_options=_GENDER_OPTIONS,
                                       age_range_options=_AGE_RANGE_OPTIONS)
        s.email     = email
        s.full_name = full_name
        s.nickname  = nickname
        s.is_admin  = is_admin
        s.gender    = gender
        s.age_range = age_range
        if new_pw:
            s.set_password(new_pw)
        db.session.commit()
        log.info(f"SHOPPER UPDATED  {s.display_id} ({s.nickname}) by {current_user.nickname}")
        flash(f"Shopper '{s.nickname}' updated.", "success")
        return redirect(url_for("main.shoppers"))
    return render_template("shopper_edit.html", shopper=s,
                           gender_options=_GENDER_OPTIONS,
                           age_range_options=_AGE_RANGE_OPTIONS)


@main.route("/shoppers/<int:shopper_id>/toggle-active", methods=["POST"])
@login_required
def shopper_toggle_active(shopper_id):
    redir = _admin_required()
    if redir:
        return redir
    s = Shopper.query.get_or_404(shopper_id)
    if s.id == current_user.id:
        flash("You cannot deactivate your own account.", "error")
        return redirect(url_for("main.shoppers"))
    s.is_active = not s.is_active
    db.session.commit()
    status = "activated" if s.is_active else "deactivated"
    log.info(f"SHOPPER {status.upper()}  {s.email} ({s.nickname}) by {current_user.nickname}")
    flash(f"Shopper '{s.nickname}' {status}.", "success")
    return redirect(url_for("main.shoppers"))


@main.route('/shoppers/<int:shopper_id>/delete', methods=['POST'])
@login_required
def shopper_delete(shopper_id):
    redir = _admin_required()
    if redir:
        return redir
    s = Shopper.query.get_or_404(shopper_id)
    if s.id == current_user.id:
        flash('You cannot delete your own account.', 'error')
        return redirect(url_for('main.shoppers'))
    if s.is_admin:
        flash('Admin accounts cannot be hard-deleted. Deactivate instead.', 'error')
        return redirect(url_for('main.shoppers'))
    nickname = s.nickname
    # Delete uploaded receipt files then receipts (LineItems + ReceiptAnalysis cascade)
    upload_folder = current_app.config['UPLOAD_FOLDER']
    for r in s.receipts:
        if r.filename:
            try:
                os.remove(os.path.join(upload_folder, r.filename))
            except OSError:
                pass
        db.session.delete(r)
    db.session.delete(s)
    db.session.commit()
    log.info(f'SHOPPER DELETED  {s.display_id} ({nickname}) by {current_user.nickname}')
    flash(f"Shopper '{nickname}' and all their data have been permanently deleted.", 'success')
    return redirect(url_for('main.shoppers'))


# ---------------------------------------------------------------------------
# Change password — self-service for all logged-in users
# ---------------------------------------------------------------------------

@main.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "GET":
        return render_template("change_password.html")
    current_pw  = request.form.get("current_password", "")
    new_pw      = request.form.get("new_password", "")
    confirm_pw  = request.form.get("confirm_password", "")
    if not current_user.check_password(current_pw):
        flash("Current password is incorrect.", "error")
        return render_template("change_password.html")
    if new_pw != confirm_pw:
        flash("New passwords do not match.", "error")
        return render_template("change_password.html")
    if len(new_pw) < 6:
        flash("Password must be at least 6 characters.", "error")
        return render_template("change_password.html")
    current_user.set_password(new_pw)
    db.session.commit()
    log.info(f"PASSWORD CHANGED {current_user.display_id} ({current_user.nickname})")
    flash("Password changed successfully.", "success")
    return redirect(url_for("main.index"))


# ---------------------------------------------------------------------------
# Reset password — admin resets any shopper's password
# ---------------------------------------------------------------------------

@main.route("/shoppers/<int:shopper_id>/reset-password", methods=["POST"])
@login_required
def shopper_reset_password(shopper_id):
    redir = _admin_required()
    if redir:
        return redir
    s = Shopper.query.get_or_404(shopper_id)
    new_pw = request.form.get("new_password", "")
    if len(new_pw) < 6:
        flash("Password must be at least 6 characters.", "error")
        return redirect(url_for("main.shopper_edit", shopper_id=shopper_id))
    s.set_password(new_pw)
    db.session.commit()
    log.info(f"PASSWORD RESET  {s.email} ({s.nickname}) by {current_user.nickname}")
    flash(f"Password reset for '{s.nickname}'.", "success")
    return redirect(url_for("main.shoppers"))


# ---------------------------------------------------------------------------
# View-as — admin switches whose receipts they're viewing
# ---------------------------------------------------------------------------

@main.route("/view-as", methods=["POST"])
@login_required
def set_view_as():
    if not current_user.is_admin:
        return redirect(url_for("main.index"))
    session["view_as"] = request.form.get("view_as", "all")
    return redirect(request.referrer or url_for("main.index"))
