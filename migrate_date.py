"""
migrate_date.py
===============
Migrates the `expenses.date` column from VARCHAR(10) / TEXT to DATE type.

Why
---
String columns cannot be indexed, range-queried, or sorted at the DB level
correctly in all cases. A proper DATE column enables native date arithmetic
and is required for PostgreSQL-compatible range queries.

Strategy
--------
* SQLite    — Rebuilds the table (SQLite has no ALTER COLUMN).
* PostgreSQL — Uses ALTER COLUMN … USING cast.

Run after migrate_numeric.py if both migrations are needed on an existing DB.

Usage
-----
    python migrate_date.py
    FLASK_ENV=production python migrate_date.py
"""

import os
import sys

os.environ.setdefault('FLASK_ENV', 'development')
from app import create_app, db

app = create_app(os.environ.get('FLASK_ENV', 'development'))


def migrate_sqlite(conn):
    print("  Strategy: SQLite table-rebuild")
    conn.execute("PRAGMA foreign_keys = OFF")

    conn.execute("""
        CREATE TABLE expenses_new (
            id               INTEGER        PRIMARY KEY,
            description      VARCHAR(200)   NOT NULL,
            amount           NUMERIC(12, 2) NOT NULL,
            category         VARCHAR(50)    NOT NULL,
            date             DATE           NOT NULL,
            notes            TEXT           DEFAULT '',
            receipt_filename VARCHAR(200),
            created_at       DATETIME,
            user_id          INTEGER        NOT NULL REFERENCES users(id)
        )
    """)

    # SQLite's date() function normalises 'YYYY-MM-DD' text → DATE affinity
    conn.execute("""
        INSERT INTO expenses_new
        SELECT id, description, amount, category,
               date(date),
               notes, receipt_filename, created_at, user_id
        FROM expenses
    """)

    conn.execute("DROP TABLE expenses")
    conn.execute("ALTER TABLE expenses_new RENAME TO expenses")
    conn.execute("PRAGMA foreign_keys = ON")
    print("  SQLite migration complete.")


def migrate_postgres(conn):
    print("  Strategy: PostgreSQL ALTER COLUMN")
    conn.execute("""
        ALTER TABLE expenses
        ALTER COLUMN date TYPE DATE
        USING date::DATE
    """)
    print("  PostgreSQL migration complete.")


with app.app_context():
    engine  = db.engine
    dialect = engine.dialect.name
    print(f"\nDialect : {dialect}")
    print(f"URL     : {engine.url}\n")

    with engine.begin() as conn:
        if dialect == 'sqlite':
            migrate_sqlite(conn)
        elif dialect in ('postgresql', 'postgres'):
            migrate_postgres(conn)
        else:
            print(f"Unsupported dialect: {dialect}")
            sys.exit(1)

    print("\n✅  Migration complete. Restart Flask to pick up the new schema.\n")
