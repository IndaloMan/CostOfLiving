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
        # Add updated_at to receipts if missing
        cols = [row[1] for row in conn.execute(db.text("PRAGMA table_info(receipts)"))]
        if "updated_at" not in cols:
            conn.execute(db.text("ALTER TABLE receipts ADD COLUMN updated_at DATETIME"))
            conn.commit()


def _seed_list_items(db):
    """Populate list_items with default values if the table is empty."""
    from .models import ListItem
    if ListItem.query.first():
        return

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

    import json

    for i, cat in enumerate(default_categories):
        db.session.add(ListItem(list_name="categories", value=cat, sort_order=i))

    for i, (type_name, cats) in enumerate(default_type_categories.items()):
        db.session.add(ListItem(
            list_name="company_types",
            value=type_name,
            sort_order=i,
            meta=json.dumps(cats) if cats else None,
        ))

    db.session.commit()
