import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from add_topic_requirements import apply


class SchemaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / 'project.db'
        self.backup = Path(self.temp.name) / 'backup.db'
        with self.connect(self.db) as conn:
            conn.execute('CREATE TABLE Topics (TopicId TEXT PRIMARY KEY, TopicName TEXT, MajorId TEXT)')
            conn.execute("INSERT INTO Topics VALUES ('T1','Existing','M1')")

    def connect(self, path):
        conn = sqlite3.connect(path)
        self.addCleanup(conn.close)
        return conn

    def test_backup_defaults_constraints_and_repeat(self):
        self.assertEqual(apply(self.db, self.backup)['preexisting_fk_violations'], 0)
        with self.connect(self.db) as conn:
            self.assertEqual(conn.execute('SELECT * FROM Topics').fetchone(), ('T1', 'Existing', 'M1', 0, 1))
            for assignment in ('studentQuota=0', 'studentQuota=1.5', 'studentQuota=2147483648', 'req_GPA=-1', 'req_GPA=4.1'):
                with self.assertRaises(sqlite3.IntegrityError):
                    conn.execute('UPDATE Topics SET ' + assignment)
        with self.connect(self.backup) as conn:
            self.assertEqual(conn.execute('SELECT * FROM Topics').fetchone(), ('T1', 'Existing', 'M1'))
        self.assertIsNone(apply(self.db, self.backup))

    def test_refuses_overwrite_and_incompatible_definition(self):
        self.backup.write_bytes(b'keep')
        with self.assertRaises(FileExistsError):
            apply(self.db, self.backup)
        self.assertEqual(self.backup.read_bytes(), b'keep')
        with self.connect(self.db) as conn:
            conn.execute('ALTER TABLE Topics ADD COLUMN req_GPA TEXT')
        with self.assertRaisesRegex(ValueError, 'Incompatible'):
            apply(self.db, self.backup)

    def test_lock_fails_without_change_or_backup(self):
        with self.connect(self.db) as writer:
            writer.execute('BEGIN IMMEDIATE')
            with self.assertRaises(sqlite3.OperationalError):
                apply(self.db, self.backup)
        self.assertFalse(self.backup.exists())

    def test_failed_validation_rolls_back_schema_and_keeps_backup(self):
        import add_topic_requirements as helper
        original = helper.validate_existing
        with patch.object(helper, 'validate_existing', side_effect=[original(self.connect(self.db)), ValueError('injected')]):
            with self.assertRaisesRegex(ValueError, 'injected'):
                apply(self.db, self.backup)
        with self.connect(self.db) as conn:
            self.assertEqual(len(conn.execute('PRAGMA table_info(Topics)').fetchall()), 3)
        self.assertTrue(self.backup.exists())
