"""
app.py — WSGI entry point for the AI Grant & Funding Finder
Run: python app.py
"""

import os
from app import create_app

application = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "True").lower() == "true"
    print(f"""
╔══════════════════════════════════════════════════════════╗
║   AI Grant & Funding Finder for Startups                 ║
║   Powered by IBM Granite (watsonx.ai) + IBM Cloud Lite   ║
╠══════════════════════════════════════════════════════════╣
║   URL  : http://localhost:{port:<30}║
║   API  : http://localhost:{port}/api/grants{" " * 19}║
╚══════════════════════════════════════════════════════════╝
    """)
    application.run(host="0.0.0.0", port=port, debug=debug)
