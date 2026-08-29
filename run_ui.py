import os
import sys

# Ensure the project root is in the python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.ui.app import app
from app.db.canonical_store import init_db, DEFAULT_DB_PATH, check_and_rebuild_stale_db

if __name__ == "__main__":
    print("Initializing SQLite database...")
    init_db(DEFAULT_DB_PATH)
    # Avoid duplicate executions in the Werkzeug reloader parent process
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not app.debug:
        check_and_rebuild_stale_db(DEFAULT_DB_PATH)
    print(f"Database initialized at: {DEFAULT_DB_PATH}")
    print("Starting Flask web server on http://127.0.0.1:5000/")
    print("Press Ctrl+C to stop.")
    app.run(debug=True, host="127.0.0.1", port=5000)
