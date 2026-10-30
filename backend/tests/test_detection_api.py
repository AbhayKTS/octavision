import json
import os
import tempfile
import unittest
from pathlib import Path

# Isolate test DB before importing the Flask app.
tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
os.environ["OCTAVISION_TEST_DB"] = str(Path(tmp.name) / "test.db")

import app as octa_app  # noqa: E402

# The app currently defines DB_PATH at import. Redirect it to test database.
octa_app.DB_PATH = Path(os.environ["OCTAVISION_TEST_DB"])
octa_app.app.config["TESTING"] = True
octa_app.init_db()

class DetectionApiTests(unittest.TestCase):
    def setUp(self):
        self.client = octa_app.app.test_client()
        with octa_app.dbconn() as db:
            db.execute("DELETE FROM alerts")
            db.execute("DELETE FROM violations")
            db.execute("DELETE FROM zones")
            db.execute("DELETE FROM cameras")
            db.execute("DELETE FROM sites")
            db.execute("INSERT INTO sites(name,site_type,location,created_at) VALUES('Test Site','construction','test',?)", (octa_app.now(),))
            self.site_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            db.execute("INSERT INTO cameras(site_id,name,source_type,status,created_at) VALUES(?, 'Test Camera','simulated','Demo',?)", (self.site_id, octa_app.now()))
            self.camera_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            db.execute("INSERT INTO zones(site_id,camera_id,name,required_ppe,created_at) VALUES(?,?, 'Test Zone','helmet',?)", (self.site_id, self.camera_id, octa_app.now()))
            self.zone_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            db.commit()

    def payload(self, **extra):
        data = {"site_id": self.site_id, "camera_id": self.camera_id, "zone_id": self.zone_id, "class_name": "no_helmet", "confidence": 0.91, "event_key": "test-event-001"}
        data.update(extra)
        return data

    def test_no_helmet_creates_violation_and_alert(self):
        response = self.client.post("/api/detections", json=self.payload())
        self.assertEqual(response.status_code, 201)
        body = response.get_json()
        self.assertTrue(body["is_violation"])
        with octa_app.dbconn() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM violations").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM alerts").fetchone()[0], 1)

    def test_helmet_does_not_create_violation(self):
        response = self.client.post("/api/detections", json=self.payload(class_name="helmet"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["is_violation"])
        with octa_app.dbconn() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM violations").fetchone()[0], 0)

    def test_duplicate_event_is_idempotent(self):
        first = self.client.post("/api/detections", json=self.payload())
        second = self.client.post("/api/detections", json=self.payload())
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.get_json()["duplicate"])
        with octa_app.dbconn() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM violations").fetchone()[0], 1)

    def test_invalid_confidence_rejected(self):
        response = self.client.post("/api/detections", json=self.payload(confidence=1.4))
        self.assertEqual(response.status_code, 400)

if __name__ == "__main__":
    unittest.main()
