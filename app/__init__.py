from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

db = SQLAlchemy()


def create_app():
    app = Flask(__name__)

    app.config["SQLALCHEMY_DATABASE_URI"] = config.SQLALCHEMY_DATABASE_URI
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["MAX_CONTENT_LENGTH"] = config.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    app.config["UPLOAD_FOLDER"] = config.RECEIPTS_FOLDER
    app.secret_key = os.urandom(24)

    db.init_app(app)

    from .routes import main
    app.register_blueprint(main)

    import json

    @app.template_filter("fromjson")
    def fromjson_filter(value):
        try:
            return json.loads(value) if value else {}
        except (ValueError, TypeError):
            return {}

    with app.app_context():
        from . import models  # noqa: F401 — ensures tables are registered
        db.create_all()
        _migrate_db(db)
        _seed_list_items(db)

    return app


def _migrate_db(db):
    """Apply incremental schema changes that db.create_all() won't handle."""
    with db.engine.connect() as conn:
        # receipts table
        cols = [row[1] for row in conn.execute(db.text("PRAGMA table_info(receipts)"))]
        if "updated_at" not in cols:
            conn.execute(db.text("ALTER TABLE receipts ADD COLUMN updated_at DATETIME"))
            conn.commit()
        if "account_id" not in cols:
            conn.execute(db.text("ALTER TABLE receipts ADD COLUMN account_id INTEGER REFERENCES accounts(id)"))
            conn.commit()


def _seed_list_items(db):
    """Populate list_items with default values for each list, only if that list is empty."""
    from .models import ListItem
    import json

    def _seed_list(list_name, values, meta_map=None):
        if ListItem.query.filter_by(list_name=list_name).first():
            return
        for i, val in enumerate(values):
            meta = None
            if meta_map and val in meta_map:
                cats = meta_map[val]
                meta = json.dumps(cats) if cats else None
            db.session.add(ListItem(list_name=list_name, value=val, sort_order=i, meta=meta))
        db.session.commit()

    default_categories = [
        "food", "drink", "dairy", "meat", "fish", "bakery", "produce", "frozen",
        "household", "cleaning", "personal_care", "pet",
        "electricity", "water", "gas", "internet", "phone",
        "petrol", "odometer",
        "restaurant", "takeaway", "other",
    ]

    default_type_categories = {
        "Supermarket": ["food", "drink", "dairy", "meat", "fish", "bakery", "produce", "frozen",
                        "household", "cleaning", "personal_care", "pet", "other"],
        "Petrol":      ["petrol", "odometer", "other"],
        "Utility":     ["electricity", "water", "gas", "internet", "phone", "other"],
        "Restaurant":  ["food", "drink", "other"],
        "Pharmacy":    ["personal_care", "other"],
        "Household":   ["household", "cleaning", "other"],
        "Transport":   ["other"],
        "Other":       [],
    }

    _seed_list("categories", default_categories)
    _seed_list("company_types", list(default_type_categories.keys()), meta_map=default_type_categories)
    _seed_list("income_categories", ["Pension", "Interest", "Dividends", "Rental", "Other"])
    _seed_list("account_types", ["Current Account", "Savings Account", "Credit Card", "Cash", "Investment", "Other"])
