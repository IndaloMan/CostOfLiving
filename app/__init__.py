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

    return app
