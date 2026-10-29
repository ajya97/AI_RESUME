"""
ResumeAI — AI Resume & Career Copilot
Entry point for local development:  python run.py
(production: gunicorn -w 4 -b 0.0.0.0:8000 "run:app")
"""

import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(
        debug=app.config["DEBUG"],
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "10000")),
    )
