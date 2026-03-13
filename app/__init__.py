from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
import os
import sys
import logging
from logging.handlers import RotatingFileHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

db = SQLAlchemy()
login_manager = LoginManager()


def create_app():
    app = Flask(__name__)

    # Logging — console + rotating file
    log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app.log')
    fmt = logging.Formatter('[%(asctime)s] %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    file_handler = RotatingFileHandler(log_path, maxBytes=1_000_000, backupCount=3, encoding='utf-8')
    file_handler.setFormatter(fmt)
    file_handler.setLevel(logging.INFO)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(fmt)
    console_handler.setLevel(logging.INFO)
    logging.getLogger().setLevel(logging.INFO)
    logging.getLogger().addHandler(file_handler)
    logging.getLogger().addHandler(console_handler)
    # Suppress noisy werkzeug request log at INFO — keep WARNING+
    logging.getLogger('werkzeug').setLevel(logging.WARNING)

    app.config["SQLALCHEMY_DATABASE_URI"] = config.SQLALCHEMY_DATABASE_URI
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["MAX_CONTENT_LENGTH"] = config.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    app.config["UPLOAD_FOLDER"] = config.RECEIPTS_FOLDER
    app.config["SECRET_KEY"] = config.SECRET_KEY

    db.init_app(app)

    login_manager.init_app(app)
    login_manager.login_view = "main.login"
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "error"

    from .routes import main
    app.register_blueprint(main)

    import json

    @app.template_filter("fromjson")
    def fromjson_filter(value):
        try:
            return json.loads(value) if value else {}
        except (ValueError, TypeError):
            return {}

    @login_manager.user_loader
    def load_user(user_id):
        from .models import Shopper
        return Shopper.query.get(int(user_id))

    @app.context_processor
    def inject_globals():
        from flask_login import current_user
        ctx = {}
        if current_user.is_authenticated and current_user.is_admin:
            from .models import Shopper
            try:
                ctx['all_shoppers'] = Shopper.query.filter_by(is_active=True).order_by(Shopper.nickname).all()
            except Exception:
                ctx['all_shoppers'] = []
        else:
            ctx['all_shoppers'] = []
        return ctx

    with app.app_context():
        from . import models  # noqa: F401 — ensures tables are registered
        db.create_all()
        _migrate_db(db)
        _seed_list_items(db)
        _seed_admin_shopper(db)

    return app


def _migrate_db(db):
    """Apply incremental schema changes that db.create_all() won't handle."""
    with db.engine.connect() as conn:
        # companies table
        cols = [row[1] for row in conn.execute(db.text("PRAGMA table_info(companies)"))]
        if "alias" not in cols:
            conn.execute(db.text("ALTER TABLE companies ADD COLUMN alias TEXT"))
            conn.execute(db.text("UPDATE companies SET alias = name WHERE alias IS NULL"))
            conn.commit()

        # shoppers table — add new columns
        for col_name, col_def in [
            ("login_id", "VARCHAR(20)"),
            ("gender",   "VARCHAR(20)"),
            ("age_range","VARCHAR(20)"),
        ]:
            cols = [row[1] for row in conn.execute(db.text("PRAGMA table_info(shoppers)"))]
            if col_name not in cols:
                conn.execute(db.text(f"ALTER TABLE shoppers ADD COLUMN {col_name} {col_def}"))
                conn.commit()

        # shoppers table — drop NOT NULL on email and full_name (SQLite requires table rebuild)
        create_sql = conn.execute(
            db.text("SELECT sql FROM sqlite_master WHERE type='table' AND name='shoppers'")
        ).scalar() or ""
        if "email VARCHAR(200) NOT NULL" in create_sql or "full_name VARCHAR(200) NOT NULL" in create_sql:
            conn.execute(db.text("PRAGMA foreign_keys=OFF"))
            conn.execute(db.text("""
                CREATE TABLE shoppers_new (
                    id            INTEGER       PRIMARY KEY AUTOINCREMENT,
                    login_id      VARCHAR(20)   UNIQUE,
                    email         VARCHAR(200)  UNIQUE,
                    full_name     VARCHAR(200),
                    nickname      VARCHAR(50)   NOT NULL,
                    password_hash VARCHAR(256)  NOT NULL,
                    is_admin      BOOLEAN       NOT NULL DEFAULT 0,
                    is_active     BOOLEAN       NOT NULL DEFAULT 1,
                    gender        VARCHAR(20),
                    age_range     VARCHAR(20),
                    created_at    DATETIME
                )
            """))
            conn.execute(db.text("""
                INSERT INTO shoppers_new
                    (id, login_id, email, full_name, nickname, password_hash,
                     is_admin, is_active, gender, age_range, created_at)
                SELECT id, login_id, email, full_name, nickname, password_hash,
                       is_admin, is_active, gender, age_range, created_at
                FROM shoppers
            """))
            conn.execute(db.text("DROP TABLE shoppers"))
            conn.execute(db.text("ALTER TABLE shoppers_new RENAME TO shoppers"))
            conn.execute(db.text("PRAGMA foreign_keys=ON"))
            conn.commit()

        # receipts table
        cols = [row[1] for row in conn.execute(db.text("PRAGMA table_info(receipts)"))]
        if "updated_at" not in cols:
            conn.execute(db.text("ALTER TABLE receipts ADD COLUMN updated_at DATETIME"))
            conn.commit()
        if "account_id" not in cols:
            conn.execute(db.text("ALTER TABLE receipts ADD COLUMN account_id INTEGER REFERENCES accounts(id)"))
            conn.commit()
        if "shopper_id" not in cols:
            conn.execute(db.text("ALTER TABLE receipts ADD COLUMN shopper_id INTEGER REFERENCES shoppers(id)"))
            conn.commit()


def _seed_admin_shopper(db):
    """Create the admin shopper if none exist, then assign all orphaned receipts to them."""
    from .models import Shopper
    if Shopper.query.first():
        return
    admin = Shopper(
        email=config.ADMIN_EMAIL,
        full_name=config.ADMIN_FULL_NAME,
        nickname=config.ADMIN_NICKNAME,
        is_admin=True,
        is_active=True,
    )
    admin.set_password(config.ADMIN_PASSWORD)
    db.session.add(admin)
    db.session.flush()
    db.session.execute(
        db.text(f"UPDATE receipts SET shopper_id = {admin.id} WHERE shopper_id IS NULL")
    )
    db.session.commit()


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
