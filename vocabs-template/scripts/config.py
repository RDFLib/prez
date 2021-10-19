import os

DB_TYPE = "graphdb"  # options: "fuseki" | "graphdb"
DB_BASE_URI = os.environ.get(
    "DB_BASE_URI", "http://localhost:7200/repositories/vocprez-test"
)
DB_USERNAME = os.environ.get("DB_USERNAME", "user")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "password")
SHOW_WARNINGS = True
WARNINGS_INVALID = False  # Allows warnings to flag as invalid when true
MAX_REDIRECTS = 5