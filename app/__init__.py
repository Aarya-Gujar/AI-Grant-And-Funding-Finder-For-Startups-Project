"""
app/__init__.py — Flask application factory
"""

import os
import logging
from flask import Flask, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()


def create_app() -> Flask:
    app = Flask(__name__, static_folder="../static", static_url_path="/static")
    app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key")

    # CORS — allow all origins in dev
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Logging
    log_level = os.getenv("LOG_LEVEL", "INFO")
    os.makedirs("logs", exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(os.getenv("LOG_FILE", "logs/app.log"), encoding="utf-8"),
        ],
    )

    # Register blueprints
    from app.routes import grants_bp
    app.register_blueprint(grants_bp)

    # Health check
    @app.route("/api/health")
    def health():
        from flask import jsonify
        return jsonify({"status": "ok", "service": "AI Grant Finder", "powered_by": "IBM Granite"})

    # Serve SPA index for all non-API routes
    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_spa(path):
        static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
        if path and os.path.exists(os.path.join(static_dir, path)):
            return send_from_directory(static_dir, path)
        return send_from_directory(static_dir, "index.html")

    return app
