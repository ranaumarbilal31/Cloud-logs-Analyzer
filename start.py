#!/usr/bin/env python3
"""
Startup script: initializes the database schema, then starts the Flask app.
Railway runs: python start.py
"""
import os
from dotenv import load_dotenv
load_dotenv()

# Init DB before gunicorn forks
from app import init_db
init_db()
print("✓ Database initialized")

# Hand off to gunicorn (Railway uses Procfile for prod)
# For local dev:
from app import app
app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
