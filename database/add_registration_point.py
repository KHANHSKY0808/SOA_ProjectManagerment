"""Add nullable Registrations.Point to the existing database-first SQLite schema.

Usage: py database/add_registration_point.py --db database/DB_ProjectManagerment.db --backup D:/backups/registration-before-point.db
The script makes a consistent backup at the supplied path before changing the database.
"""

import argparse
import sqlite3
from pathlib import Path


def apply(database: Path, backup: Path) -> None:
    if not database.is_file():
        raise SystemExit(f"Database does not exist: {database}")
    connection = sqlite3.connect(database, timeout=3)
    try:
        columns = {row[1] for row in connection.execute('PRAGMA table_info("Registrations")')}
        if "RegistrationId" not in columns:
            raise SystemExit("Expected Registrations schema was not found")
        if "Point" in columns:
            print("Registrations.Point already exists; no change made")
            return
        if backup.exists():
            raise SystemExit(f"Backup already exists; inspect it before proceeding: {backup}")
        with sqlite3.connect(backup) as target:
            connection.backup(target)
        try:
            connection.execute('BEGIN IMMEDIATE')
            connection.execute('ALTER TABLE "Registrations" ADD COLUMN "Point" NUMERIC')
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        print(f"Added Registrations.Point; backup: {backup}")
    finally:
        connection.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--backup", type=Path, required=True)
    args = parser.parse_args()
    apply(args.db, args.backup)
