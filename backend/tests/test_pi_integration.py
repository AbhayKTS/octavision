import unittest
from pi_config import get_pi_config, check_pi_status, PI_HOST, PI_PORT, PI_STREAM_URL
import app


class PiIntegrationTests(unittest.TestCase):
    def setUp(self):
        app.app.config["TESTING"] = True
        self.client = app.app.test_client()
        app.init_db()

    def test_pi_config_values(self):
        cfg = get_pi_config()
        self.assertEqual(cfg["pi_host"], PI_HOST)
        self.assertEqual(cfg["pi_port"], PI_PORT)
        self.assertIn("8001", cfg["pi_stream_url"])
        self.assertIn("172.20.10.7", cfg["pi_stream_url"])

    def test_pi_config_endpoint(self):
        res = self.client.get("/api/cameras/pi-config")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["config"]["pi_host"], PI_HOST)

    def test_pi_status_endpoint(self):
        res = self.client.get("/api/cameras/pi-status")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["ok"])
        self.assertIn("worker", data)
        self.assertIn("hardware", data)

    def test_rpi_camera_registered_in_db(self):
        with app.dbconn() as d:
            row = d.execute("SELECT * FROM cameras WHERE source_type='rpi'").fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["source_type"], "rpi")
            self.assertIn("172.20.10.7", row["source_url"])

    def test_add_camera_accepts_rpi(self):
        with app.dbconn() as d:
            site = d.execute("SELECT id FROM sites LIMIT 1").fetchone()
        res = self.client.post("/api/cameras", json={
            "site_id": site["id"],
            "name": "Test Secondary Pi 5",
            "source_type": "rpi",
            "source_url": ""
        })
        self.assertEqual(res.status_code, 201)
        cam = res.get_json()
        self.assertEqual(cam["source_type"], "rpi")
        self.assertEqual(cam["source_url"], PI_STREAM_URL)


if __name__ == "__main__":
    unittest.main()
