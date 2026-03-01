from . import db
from datetime import datetime


class Company(db.Model):
    """A company or vendor that issues receipts/invoices."""
    __tablename__ = "companies"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, unique=True)
    # Type: supermarket, utility, restaurant, pharmacy, household, other
    type = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    receipts = db.relationship("Receipt", back_populates="company")
    template = db.relationship("CompanyTemplate", back_populates="company", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Company {self.name}>"


class CompanyTemplate(db.Model):
    """Stores known line item patterns for a company to aid future extraction."""
    __tablename__ = "company_templates"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    # JSON string: list of known products with default categories
    known_items = db.Column(db.Text, default="[]")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    company = db.relationship("Company", back_populates="template")


class Receipt(db.Model):
    """A single scanned receipt or invoice."""
    __tablename__ = "receipts"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=True)
    # Date on the receipt itself
    receipt_date = db.Column(db.Date, nullable=True)
    # Total amount on receipt
    total_amount = db.Column(db.Float, nullable=True)
    currency = db.Column(db.String(10), default="EUR")
    # Original file stored in Receipts/
    filename = db.Column(db.String(500))
    # Type: receipt, invoice, utility_bill
    document_type = db.Column(db.String(50), default="receipt")
    # raw JSON response from Claude for reference
    raw_extraction = db.Column(db.Text)
    # pending = extracted but not yet confirmed; confirmed = saved by user
    status = db.Column(db.String(20), default="pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    company = db.relationship("Company", back_populates="receipts")
    line_items = db.relationship("LineItem", back_populates="receipt", cascade="all, delete-orphan")
    analysis   = db.relationship("ReceiptAnalysis", back_populates="receipt", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Receipt {self.id} {self.receipt_date}>"


class ReceiptAnalysis(db.Model):
    """Stores company-specific deep analysis data for a receipt."""
    __tablename__ = "receipt_analyses"

    id = db.Column(db.Integer, primary_key=True)
    receipt_id = db.Column(db.Integer, db.ForeignKey("receipts.id"), nullable=False, unique=True)
    analyser = db.Column(db.String(50), nullable=False)   # e.g. "energy_nordic"
    data = db.Column(db.Text, nullable=False)              # JSON blob
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    receipt = db.relationship("Receipt", back_populates="analysis")


class LineItem(db.Model):
    """A single line item extracted from a receipt."""
    __tablename__ = "line_items"

    id = db.Column(db.Integer, primary_key=True)
    receipt_id = db.Column(db.Integer, db.ForeignKey("receipts.id"), nullable=False)
    description = db.Column(db.String(500), nullable=False)
    quantity = db.Column(db.Float, default=1.0)
    unit_price = db.Column(db.Float, nullable=True)
    total_price = db.Column(db.Float, nullable=True)
    # e.g. dairy, bread, meat, electricity, water, cleaning, etc.
    category = db.Column(db.String(100), nullable=True)
    # Date of this specific item if different from receipt date
    item_date = db.Column(db.Date, nullable=True)

    receipt = db.relationship("Receipt", back_populates="line_items")

    def __repr__(self):
        return f"<LineItem {self.description} {self.total_price}>"
