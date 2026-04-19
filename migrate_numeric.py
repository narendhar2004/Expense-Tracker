"""
migrate_numeric.py
==================
Migrates the `expenses.amount` column from FLOAT to NUMERIC(12, 2).

Why this is needed
------------------
IEEE-754 floats cannot represent many decimal fractions exactly.
Storing ₹0.10 as a float gives 0.1000000000000000055511151231257827021181583404541015625.
NUMERIC(12, 2) stores the value as-is with no rounding error.

How to run
----------
    python migrate_numeric.py                  # uses FLASK_ENV / DATABASE_URL
    FLASK_ENV=production python migrate_numeric.py

Strategy
--------
* SQLite  — Does NOT support ALTER COLUMN.  We recreate the table.
* PostgreSQL — Uses a single ALTER COLUMN … USING cast.

Both paths are wrapped in a transaction so they are fully atomic.
"""

import os
import sys

# ── Bootstrap Flask so we can read config ──────────────────────────────────
os.environ.setdefault('FLASK_ENV', 'development')
from app import create_app, db

app  = create_app(os.environ.get('FLASK_ENV', 'development'))
conn = None


def migrate_sqlite(connection):
    print("  Strategy: SQLite table-rebuild")

    connection.execute("PRAGMA foreign_keys = OFF")

    # 1. Create replacement table with NUMERIC column
    connection.execute("""
        CREATE TABLE expenses_new (
            id               INTEGER      PRIMARY KEY,
            description      VARCHAR(200) NOT NULL,
            amount           NUMERIC(12, 2) NOT NULL,
            category         VARCHAR(50)  NOT NULL,
            date             VARCHAR(10)  NOT NULL,
            notes            TEXT         DEFAULT '',
            receipt_filename VARCHAR(200),
            created_at       DATETIME,
            user_id          INTEGER      NOT NULL REFERENCES users(id)
        )
    """)

    # 2. Copy existing data (SQLite will cast REAL → NUMERIC)
    connection.execute("""
        INSERT INTO expenses_new
        SELECT id, description,
               ROUND(CAST(amount AS REAL), 2),
               category, date, notes, receipt_filename, created_at, user_id
        FROM expenses
    """)

    # 3. Swap tables
    connection.execute("DROP TABLE expenses")
    connection.execute("ALTER TABLE expenses_new RENAME TO expenses")

    connection.execute("PRAGMA foreign_keys = ON")
    print("  SQLite migration complete.")


def migrate_postgres(connection):
    print("  Strategy: PostgreSQL ALTER COLUMN")
    connection.execute("""
        ALTER TABLE expenses
        ALTER COLUMN amount TYPE NUMERIC(12, 2)
        USING amount::NUMERIC(12, 2)
    """)
    print("  PostgreSQL migration complete.")


with app.app_context():
    engine = db.engine
    dialect = engine.dialect.name
    print(f"\nDatabase dialect : {dialect}")
    print(f"Database URL     : {engine.url}\n")

    with engine.begin() as conn:   # auto-commits on success, rolls back on error
        if dialect == 'sqlite':
            migrate_sqlite(conn)
        elif dialect in ('postgresql', 'postgres'):
            migrate_postgres(conn)
        else:
            print(f"ERROR: Unsupported dialect '{dialect}'.")
            sys.exit(1)

    print("\n✅  Migration succeeded.  Restart the Flask server to pick up the new schema.\n")
