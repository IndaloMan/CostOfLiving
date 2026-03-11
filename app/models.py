from . import db
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash


class Shopper(db.Model, UserMixin):
    """A registered user of the app."""
    __tablename__ = "shoppers"

    id            = db.Column(db.Integer,     primary_key=True)
    email         = db.Column(db.String(200), nullable=False, unique=True)
    full_name     = db.Column(db.String(200), nullable=False)
    nickname      = db.Column(db.String(50),  nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin      = db.Column(db.Boolean,     default=False, nullable=False)
    is_active     = db.Column(db.Boolean,     default=True,  nullable=False)
    created_at    = db.Column(db.DateTime,    default=datetime.utcnow)

    receipts = db.relationship("Receipt", back_populates="shopper")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<Shopper {self.email}>"


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
    shopper_id = db.Column(db.Integer, db.ForeignKey("shoppers.id"), nullable=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=True)
    # Date on the receipt itself
    receipt_date = db.Column(db.Date, nullable=True)
    # Total amount on receipt
    total_amount = db.Column(db.Float, nullable=True)
    currency = db.Column(db.String(10), default="EUR")
    # Account this receipt was paid from (optional)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=True)
    # Original file stored in Receipts/
    filename = db.Column(db.String(500))
    # Type: receipt, invoice, utility_bill
    document_type = db.Column(db.String(50), default="receipt")
    # raw JSON response from Claude for reference
    raw_extraction = db.Column(db.Text)
    # pending = extracted but not yet confirmed; confirmed = saved by user
    status = db.Column(db.String(20), default="pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=True)

    shopper = db.relationship("Shopper", back_populates="receipts")
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


class ListItem(db.Model):
    """Stores user-manageable dropdown list values (categories, company types)."""
    __tablename__ = "list_items"

    id         = db.Column(db.Integer, primary_key=True)
    list_name  = db.Column(db.String(50), nullable=False, index=True)
    value      = db.Column(db.String(100), nullable=False)
    sort_order = db.Column(db.Integer, default=0)
    meta       = db.Column(db.Text)   # JSON: categories linked to a company type

    @property
    def meta_list(self):
        import json
        try:
            return json.loads(self.meta) if self.meta else []
        except Exception:
            return []

    def __repr__(self):
        return f"<ListItem {self.list_name}:{self.value}>"

class Income(db.Model):
    """A single income entry (pension, interest, etc.)."""
    __tablename__ = 'income'

    id         = db.Column(db.Integer, primary_key=True)
    date       = db.Column(db.Date, nullable=False)
    source     = db.Column(db.String(200), nullable=False)
    amount     = db.Column(db.Float, nullable=False)
    category   = db.Column(db.String(100), nullable=True)
    notes      = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Income {self.date} {self.source} {self.amount}>'


class Account(db.Model):
    """A bank account or credit card with an opening balance."""
    __tablename__ = 'accounts'

    id              = db.Column(db.Integer, primary_key=True)
    name            = db.Column(db.String(200), nullable=False)
    account_type    = db.Column(db.String(100), nullable=True)
    opening_balance = db.Column(db.Float, nullable=False, default=0.0)
    opening_date    = db.Column(db.Date, nullable=False)
    notes           = db.Column(db.String(500), nullable=True)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Account {self.name}>'

class Transaction(db.Model):
    """A single imported bank statement transaction."""
    __tablename__ = 'transactions'

    id             = db.Column(db.Integer, primary_key=True)
    account_id     = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=True)
    date           = db.Column(db.Date, nullable=False)
    description    = db.Column(db.String(500), nullable=False)
    amount         = db.Column(db.Float, nullable=False)
    direction      = db.Column(db.String(10), nullable=False, default='out')  # 'in' or 'out'
    category       = db.Column(db.String(100), nullable=True)
    notes          = db.Column(db.String(500), nullable=True)
    transaction_id = db.Column(db.String(200), nullable=True, unique=True)
    source         = db.Column(db.String(50), nullable=True)   # wise_csv, sabadell_pdf, manual
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

    account = db.relationship('Account', backref='transactions', foreign_keys=[account_id])

    def __repr__(self):
        return f'<Transaction {self.date} {self.description} {self.amount}>'
