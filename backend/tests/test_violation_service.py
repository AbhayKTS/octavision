import os
import tempfile
import unittest
from pathlib import Path

# Setup test DB
tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
os.environ["OCTAVISION_TEST_DB"] = str(Path(tmp.name) / "test.db")

import app as octa_app
octa_app.DB_PATH = Path(os.environ["OCTAVISION_TEST_DB"])
octa_app.violation_service.db_path = octa_app.DB_PATH
octa_app.app.config["TESTING"] = True
octa_app.init_db()


class ViolationServiceTests(unittest.TestCase):
    def setUp(self):
        self.client = octa_app.app.test_client()
        with octa_app.dbconn() as db:
            db.execute("DELETE FROM alerts")
            db.execute("DELETE FROM violations")
            db.execute("DELETE FROM zones")
            db.execute("DELETE FROM cameras")
            db.execute("DELETE FROM sites")
            now = octa_app.now()
            db.execute("INSERT INTO sites(name,site_type,location,created_at) VALUES('Alpha Site','construction','Sector 4',?)", (now,))
            self.site_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            db.execute("INSERT INTO cameras(site_id,name,source_type,status,created_at) VALUES(?, 'Camera 01 · Live Detection','simulated','Active',?)", (self.site_id, now))
            self.camera_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            db.execute("INSERT INTO zones(site_id,camera_id,name,required_ppe,created_at) VALUES(?,?, 'Zone 1','helmet,vest',?)", (self.site_id, self.camera_id, now))
            self.zone_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            db.commit()

        # Clear cooldowns between tests
        octa_app.violation_service._cooldowns.clear()

    def test_live_inference_violation_with_cooldown(self):
        # Frame with both no_helmet and no_vest
        payload = {
            "site_id": self.site_id,
            "camera_id": self.camera_id,
            "zone_id": self.zone_id,
            "detections": [
                {"normalized_label": "no_helmet", "confidence": 0.94, "is_violation": True, "bbox": {"x1": 10, "y1": 10, "x2": 50, "y2": 50}},
                {"normalized_label": "no_vest", "confidence": 0.88, "is_violation": True, "bbox": {"x1": 10, "y1": 50, "x2": 50, "y2": 120}},
                {"normalized_label": "person", "confidence": 0.96, "is_violation": False, "bbox": {"x1": 5, "y1": 5, "x2": 60, "y2": 150}},
            ]
        }

        # 1st call: should create both helmet and vest violations
        res1 = self.client.post("/api/violations/from-inference", json=payload)
        self.assertEqual(res1.status_code, 201)
        data1 = res1.get_json()
        self.assertEqual(len(data1["created"]), 2)
        self.assertEqual(data1["suppressed"], 0)

        # 2nd immediate call: should be suppressed by cooldown (no duplicates in 20s)
        res2 = self.client.post("/api/violations/from-inference", json=payload)
        self.assertEqual(res2.status_code, 201)
        data2 = res2.get_json()
        self.assertEqual(len(data2["created"]), 0)
        self.assertEqual(data2["suppressed"], 2)

    def test_violation_resolution_lifecycle(self):
        payload = {
            "site_id": self.site_id,
            "camera_id": self.camera_id,
            "detections": [
                {"normalized_label": "no_helmet", "confidence": 0.95, "is_violation": True, "bbox": {"x1": 0, "y1": 0, "x2": 20, "y2": 20}}
            ]
        }
        res = self.client.post("/api/violations/from-inference", json=payload)
        vid = res.get_json()["created"][0]["violation"]["id"]

        # Check detail
        detail = self.client.get(f"/api/violations/{vid}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.get_json()["status"], "Open")

        # Resolve
        resolve_res = self.client.patch(f"/api/violations/{vid}", json={"status": "Resolved"})
        self.assertEqual(resolve_res.status_code, 200)
        self.assertEqual(resolve_res.get_json()["status"], "Resolved")

        # Alerts should be acknowledged automatically upon resolution
        alerts = self.client.get("/api/alerts").get_json()
        matching_alert = next((a for a in alerts if a["violation_id"] == vid), None)
        self.assertIsNotNone(matching_alert)
        self.assertEqual(matching_alert["status"], "Acknowledged")


if __name__ == "__main__":
    unittest.main()

