"""Add Topics requirements, with a consistent backup and no Django migrations.

Stop application writers first. Run with --db PATH --backup NEW_BACKUP_PATH.
An already compatible schema is a read-only no-op. Never overwrite a backup.
"""
import argparse
from contextlib import closing
import hashlib
import sqlite3
from pathlib import Path


COLUMNS = {
    "req_GPA": ('REAL', '0', 'REAL NOT NULL DEFAULT 0 CHECK (typeof("req_GPA") IN (\'real\', \'integer\') AND "req_GPA" >= 0 AND "req_GPA" <= 4)'),
    "studentQuota": ('INTEGER', '1', 'INTEGER NOT NULL DEFAULT 1 CHECK (typeof("studentQuota") = \'integer\' AND "studentQuota" BETWEEN 1 AND 2147483647)'),
}


def snapshot(conn):
    """Fingerprint all existing values, excluding the two additive columns."""
    result = {}
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
    for (name,) in tables:
        quoted = '"' + name.replace('"', '""') + '"'
        fields = [row[1] for row in conn.execute(f'PRAGMA table_info({quoted})')
                  if name != 'Topics' or row[1] not in COLUMNS]
        selection = ','.join('"' + field.replace('"', '""') + '"' for field in fields)
        hashes = sorted(hashlib.sha256(repr(row).encode()).digest()
                        for row in conn.execute(f'SELECT {selection} FROM {quoted}'))
        result[name] = (len(hashes), hashlib.sha256(b''.join(hashes)).hexdigest())
    return result


def validate_existing(conn):
    columns = {row[1]: row for row in conn.execute('PRAGMA table_info("Topics")')}
    if not {'TopicId', 'TopicName', 'MajorId'} <= columns.keys():
        raise ValueError('Expected Topics schema was not found')
    for name, (sql_type, default, _) in COLUMNS.items():
        if name not in columns:
            continue
        row = columns[name]
        if row[2].upper() != sql_type or row[3] != 1 or row[4] != default:
            raise ValueError(f'Incompatible Topics.{name} definition')
        invalid = ('typeof("req_GPA") NOT IN (\'real\', \'integer\') OR "req_GPA" < 0 OR "req_GPA" > 4'
                   if name == 'req_GPA' else 'typeof("studentQuota") != \'integer\' OR "studentQuota" < 1 OR "studentQuota" > 2147483647')
        if conn.execute(f'SELECT 1 FROM "Topics" WHERE {invalid} LIMIT 1').fetchone():
            raise ValueError(f'Invalid Topics.{name} data')
    return columns


def apply(database: Path, backup: Path):
    database, backup = database.resolve(), backup.resolve()
    if not database.is_file():
        raise ValueError(f'Database does not exist: {database}')
    conn = sqlite3.connect(database.as_uri() + '?mode=rw', uri=True, timeout=3)
    try:
        conn.execute('BEGIN IMMEDIATE')  # Reserve the writer before snapshot/backup.
        columns = validate_existing(conn)
        missing = [name for name in COLUMNS if name not in columns]
        if not missing:
            conn.rollback()
            return None
        if conn.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
            raise ValueError('Database integrity check failed')
        fk_before = set(conn.execute('PRAGMA foreign_key_check').fetchall())
        before = snapshot(conn)
        # A second read connection backs up the committed state while the writer
        # reservation prevents other writers changing it. backup() on the writer
        # connection itself would wait on its own active write transaction.
        with backup.open('xb'):
            pass
        with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True, timeout=3)) as source:
            with closing(sqlite3.connect(backup)) as target:
                source.backup(target)
                if target.execute('PRAGMA integrity_check').fetchall() != [('ok',)] or snapshot(target) != before:
                    raise ValueError('Backup validation failed')
        for name in missing:
            conn.execute(f'ALTER TABLE "Topics" ADD COLUMN "{name}" {COLUMNS[name][2]}')
        validate_existing(conn)
        if snapshot(conn) != before or set(conn.execute('PRAGMA foreign_key_check').fetchall()) != fk_before:
            raise ValueError('Existing data or foreign keys changed')
        if conn.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
            raise ValueError('Post-change integrity check failed')
        conn.commit()
        return {'backup': str(backup), 'preexisting_fk_violations': len(fk_before), 'tables': len(before)}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, required=True)
    parser.add_argument('--backup', type=Path, required=True)
    args = parser.parse_args()
    print(apply(args.db, args.backup) or 'Already compatible; no change made')
