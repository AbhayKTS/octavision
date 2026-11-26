"""
OctaVision Violation Management Service (Decoupled Module).

Encapsulates:
- Violation event processing & ingestion
- Real-time duplicate event suppression & cooldown tracking
- Evidence screenshot capture with annotated bounding boxes & forensic watermark
- Real-time alert dispatch (Critical Helmet alerts vs PPE Warnings for vests)
- Lifecycle management (Resolve violations, acknowledge alerts)
"""

import base64
import os
import sqlite3
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np


class ViolationManagementService:
    def __init__(self, db_path: Path, snaps_dir: Path, cooldown_secs: int = 25):
        self._db_path = Path(db_path)
        self.snaps_dir = Path(snaps_dir)
        self.snaps_dir.mkdir(parents=True, exist_ok=True)
        self.cooldown_secs = cooldown_secs

        # In-memory cooldown tracker: {camera_id: {ppe_type: last_unix_time}}
        self._cooldowns: dict = {}
        self._cooldown_lock = threading.Lock()

    @property
    def db_path(self):
        return self._db_path

    @db_path.setter
    def db_path(self, val):
        self._db_path = Path(val)

    def _dbconn(self):
        c = sqlite3.connect(self._db_path)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        return c

    @staticmethod
    def _now_iso():
        return datetime.now().astimezone().isoformat(timespec="seconds")

    def is_suppressed(self, camera_id: int, ppe_type: str) -> bool:
        """Check if this camera and PPE type was already alerted within the cooldown period."""
        now_unix = time.time()
        with self._cooldown_lock:
            cam_map = self._cooldowns.get(camera_id, {})
            last_ts = cam_map.get(ppe_type, 0)
            return (now_unix - last_ts) < self.cooldown_secs

    def touch_cooldown(self, camera_id: int, ppe_type: str):
        """Update last alerted timestamp for camera and PPE type."""
        now_unix = time.time()
        with self._cooldown_lock:
            cam_map = self._cooldowns.setdefault(camera_id, {})
            cam_map[ppe_type] = now_unix

    def save_annotated_evidence(
        self,
        image_input,
        detections: list,
        camera_name: str = "Camera",
        ppe_label: str = "PPE Violation",
        confidence: float = 0.90,
        occurred_at: str = "",
    ) -> str:
        """
        Draws bounding boxes and forensic watermark on the violation frame,
        and saves it to snapshots/ as a high-quality JPEG evidence record.
        """
        img = None
        if isinstance(image_input, np.ndarray):
            img = image_input.copy()
        elif isinstance(image_input, (bytes, bytearray)):
            arr = np.frombuffer(image_input, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        elif isinstance(image_input, str) and image_input.strip():
            raw_b64 = image_input.split(",", 1)[1] if "," in image_input else image_input
            try:
                binary = base64.b64decode(raw_b64)
                arr = np.frombuffer(binary, dtype=np.uint8)
                img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            except Exception:
                img = None

        if img is None:
            return ""

        h, w = img.shape[:2]
        canvas = img.copy()

        # BGR Color palette
        COLORS = {
            "no_helmet": (60, 60, 235),     # Bold Red
            "no_vest": (30, 130, 240),      # Bold Orange
            "helmet": (70, 180, 50),        # Green
            "vest": (230, 140, 40),         # Blue/Cyan
            "person": (180, 160, 100),      # Slate Gray
        }

        # 1. Draw detection bounding boxes
        for det in detections or []:
            b = det.get("bbox", {})
            try:
                x1 = max(0, min(w - 1, int(b.get("x1", 0))))
                y1 = max(0, min(h - 1, int(b.get("y1", 0))))
                x2 = max(0, min(w - 1, int(b.get("x2", 0))))
                y2 = max(0, min(h - 1, int(b.get("y2", 0))))
            except (ValueError, TypeError):
                continue

            lbl = det.get("normalized_label", det.get("class_name", "object"))
            is_viol = det.get("is_violation", False) or lbl in {"no_helmet", "no_vest"}
            color = COLORS.get(lbl, (0, 0, 240) if is_viol else (200, 200, 200))
            thickness = 3 if is_viol else 1

            cv2.rectangle(canvas, (x1, y1), (x2, y2), color, thickness)

            # Label badge
            conf = det.get("confidence", 0)
            tag = f"{lbl.upper()} {conf:.0%}" if conf else lbl.upper()
            font = cv2.FONT_HERSHEY_SIMPLEX
            scale = 0.5
            (tw, th), _ = cv2.getTextSize(tag, font, scale, 1)

            # Badge background
            by1 = max(0, y1 - th - 8)
            by2 = y1
            bx2 = min(w - 1, x1 + tw + 8)
            cv2.rectangle(canvas, (x1, by1), (bx2, by2), color, -1)
            cv2.putText(canvas, tag, (x1 + 4, y1 - 4), font, scale, (255, 255, 255), 1, cv2.LINE_AA)

        # 2. Forensic Evidence Watermark Bar at Top and Bottom
        ts_display = occurred_at or self._now_iso()
        top_bar_h = 32
        cv2.rectangle(canvas, (0, 0), (w, top_bar_h), (20, 20, 30), -1)
        cv2.putText(
            canvas,
            "OCTAVISION SAFETY AI - EVIDENCE SNAPSHOT",
            (12, 22),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )

        bot_bar_h = 28
        cv2.rectangle(canvas, (0, h - bot_bar_h), (w, h), (15, 18, 26), -1)
        sub_text = f"CAM: {camera_name} | VIOLATION: {ppe_label.upper()} ({confidence:.1%}) | TIME: {ts_display}"
        cv2.putText(
            canvas,
            sub_text,
            (12, h - 9),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (180, 210, 255),
            1,
            cv2.LINE_AA,
        )

        # Save to disk
        ts_slug = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"evidence_{ts_slug}_{uuid.uuid4().hex[:8]}.jpg"
        file_path = self.snaps_dir / filename
        cv2.imwrite(str(file_path), canvas, [cv2.IMWRITE_JPEG_QUALITY, 90])

        return f"/api/snapshots/{filename}"

    def record_violation(
        self,
        site_id: int,
        camera_id: int,
        ppe_type: str,
        confidence: float,
        zone_id: int | None = None,
        image_input=None,
        detections: list | None = None,
        source: str = "model",
        event_key: str | None = None,
        occurred_at: str | None = None,
        check_cooldown: bool = True,
    ) -> dict:
        """
        Record a violation and generate its alert.
        Handles duplicate suppression via cooldown or unique event_key.
        """
        ppe_normalized = "helmet" if "helmet" in ppe_type.lower() else "vest" if "vest" in ppe_type.lower() else ppe_type
        occurred_ts = occurred_at or self._now_iso()

        # Check duplicate suppression cooldown
        if check_cooldown and self.is_suppressed(camera_id, ppe_normalized):
            return {
                "created": False,
                "suppressed": True,
                "reason": f"Suppressed by cooldown ({self.cooldown_secs}s) for camera {camera_id} - {ppe_normalized}.",
                "violation": None,
                "alert": None,
            }

        # Check existing event_key if provided
        key = event_key or str(uuid.uuid4())
        with self._dbconn() as d:
            existing = d.execute("SELECT * FROM violations WHERE event_key=?", (key,)).fetchone()
            if existing:
                alert = d.execute(
                    "SELECT * FROM alerts WHERE violation_id=? ORDER BY id DESC LIMIT 1",
                    (existing["id"],),
                ).fetchone()
                return {
                    "created": False,
                    "duplicate": True,
                    "suppressed": False,
                    "violation": dict(existing),
                    "alert": dict(alert) if alert else None,
                }

            # Verify site & camera
            site = d.execute("SELECT name FROM sites WHERE id=?", (site_id,)).fetchone()
            if not site:
                return {"created": False, "error": f"Site #{site_id} not found."}
            camera = d.execute("SELECT name FROM cameras WHERE id=? AND site_id=?", (camera_id, site_id)).fetchone()
            if not camera:
                return {"created": False, "error": f"Camera #{camera_id} not found for site #{site_id}."}

            cam_name = camera["name"]

        # Capture & annotate evidence screenshot
        snapshot_url = ""
        if image_input is not None:
            try:
                snapshot_url = self.save_annotated_evidence(
                    image_input=image_input,
                    detections=detections or [],
                    camera_name=cam_name,
                    ppe_label="Helmet Not Detected" if ppe_normalized == "helmet" else "Safety Vest Missing",
                    confidence=confidence,
                    occurred_at=occurred_ts,
                )
            except Exception as e:
                snapshot_url = ""

        # Update cooldown timestamp
        if check_cooldown:
            self.touch_cooldown(camera_id, ppe_normalized)

        # Alert configuration
        is_critical = ppe_normalized == "helmet"
        severity = "Critical" if is_critical else "High"
        if is_critical:
            alert_message = f"Critical PPE Alert: Helmet Not Detected ({cam_name}) · Conf: {confidence:.0%}"
        else:
            alert_message = f"PPE Warning: Safety Vest Missing ({cam_name}) · Conf: {confidence:.0%}"

        with self._dbconn() as d:
            cur = d.execute(
                """INSERT INTO violations(event_key, site_id, camera_id, zone_id, ppe_type, severity, confidence, status, snapshot_path, occurred_at, source)
                   VALUES(?, ?, ?, ?, ?, ?, ?, 'Open', ?, ?, ?)""",
                (key, site_id, camera_id, zone_id, ppe_normalized, severity, round(confidence, 4), snapshot_url, occurred_ts, source),
            )
            vid = cur.lastrowid

            cur_alert = d.execute(
                """INSERT INTO alerts(violation_id, message, status, created_at)
                   VALUES(?, ?, 'Active', ?)""",
                (vid, alert_message, occurred_ts),
            )
            aid = cur_alert.lastrowid
            d.commit()

            v = d.execute(
                """SELECT v.*, s.name as site_name, c.name as camera_name, z.name as zone_name
                   FROM violations v
                   JOIN sites s ON s.id=v.site_id
                   LEFT JOIN cameras c ON c.id=v.camera_id
                   LEFT JOIN zones z ON z.id=v.zone_id
                   WHERE v.id=?""",
                (vid,),
            ).fetchone()

            a = d.execute(
                """SELECT a.*, v.site_id, v.camera_id, v.zone_id, v.ppe_type, v.snapshot_path,
                          s.name as site_name, c.name as camera_name, z.name as zone_name
                   FROM alerts a
                   JOIN violations v ON v.id=a.violation_id
                   JOIN sites s ON s.id=v.site_id
                   LEFT JOIN cameras c ON c.id=v.camera_id
                   LEFT JOIN zones z ON z.id=v.zone_id
                   WHERE a.id=?""",
                (aid,),
            ).fetchone()

        return {
            "created": True,
            "suppressed": False,
            "violation": dict(v) if v else None,
            "alert": dict(a) if a else None,
            "snapshot_path": snapshot_url,
        }

    def process_frame_detections(
        self,
        site_id: int,
        camera_id: int,
        detections: list,
        image_input=None,
        zone_id: int | None = None,
    ) -> dict:
        """
        Process a list of detections from a live frame.
        Extracts violations (no_helmet, no_vest), applies duplicate suppression per PPE type,
        creates evidence snapshots and persists violation + alert records.
        """
        violation_dets = [d for d in (detections or []) if d.get("is_violation")]
        if not violation_dets:
            return {"created": [], "suppressed": 0, "message": "No violations detected."}

        # Check unique PPE types missing in this frame
        ppe_types_present = {}
        for det in violation_dets:
            lbl = det.get("normalized_label", "")
            ppe = "helmet" if lbl == "no_helmet" else "vest" if lbl == "no_vest" else None
            if ppe:
                if ppe not in ppe_types_present or det.get("confidence", 0) > ppe_types_present[ppe].get("confidence", 0):
                    ppe_types_present[ppe] = det

        created_records = []
        suppressed_count = 0

        for ppe_type, det in ppe_types_present.items():
            conf = float(det.get("confidence", 0.90))
            result = self.record_violation(
                site_id=site_id,
                camera_id=camera_id,
                ppe_type=ppe_type,
                confidence=conf,
                zone_id=zone_id,
                image_input=image_input,
                detections=detections,
                source="model",
                check_cooldown=True,
            )

            if result.get("created"):
                created_records.append(result)
            elif result.get("suppressed"):
                suppressed_count += 1

        return {
            "created": created_records,
            "suppressed": suppressed_count,
            "total_violations_in_frame": len(ppe_types_present),
        }

    def resolve_violation(self, vid: int, status: str = "Resolved") -> dict | None:
        """Resolve or reopen a violation record and acknowledge its associated alerts."""
        with self._dbconn() as d:
            cur = d.execute("UPDATE violations SET status=? WHERE id=?", (status, vid))
            if not cur.rowcount:
                return None
            if status == "Resolved":
                d.execute(
                    "UPDATE alerts SET status='Acknowledged', acknowledged_at=? WHERE violation_id=? AND status='Active'",
                    (self._now_iso(), vid),
                )
            d.commit()
            row = d.execute(
                """SELECT v.*, s.name as site_name, c.name as camera_name, z.name as zone_name
                   FROM violations v
                   JOIN sites s ON s.id=v.site_id
                   LEFT JOIN cameras c ON c.id=v.camera_id
                   LEFT JOIN zones z ON z.id=v.zone_id
                   WHERE v.id=?""",
                (vid,),
            ).fetchone()
            return dict(row) if row else None

    def acknowledge_alert(self, aid: int) -> dict | None:
        """Acknowledge an alert."""
        with self._dbconn() as d:
            cur = d.execute(
                "UPDATE alerts SET status='Acknowledged', acknowledged_at=? WHERE id=?",
                (self._now_iso(), aid),
            )
            if not cur.rowcount:
                return None
            d.commit()
            row = d.execute("SELECT * FROM alerts WHERE id=?", (aid,)).fetchone()
            return dict(row) if row else None

    def get_violation(self, vid: int) -> dict | None:
        """Fetch full details for one violation."""
        with self._dbconn() as d:
            row = d.execute(
                """SELECT v.*, s.name as site_name, c.name as camera_name, z.name as zone_name
                   FROM violations v
                   JOIN sites s ON s.id=v.site_id
                   LEFT JOIN cameras c ON c.id=v.camera_id
                   LEFT JOIN zones z ON z.id=v.zone_id
                   WHERE v.id=?""",
                (vid,),
            ).fetchone()
            return dict(row) if row else None

    def get_violations(self, status: str | None = None, site_id: int | None = None, q: str = "", limit: int = 500) -> list:
        """Query violations with optional filters."""
        where = []
        args = []
        if status in {"Open", "Resolved"}:
            where.append("v.status=?")
            args.append(status)
        if site_id:
            where.append("v.site_id=?")
            args.append(site_id)
        if q:
            where.append("(s.name LIKE ? OR c.name LIKE ? OR z.name LIKE ? OR v.ppe_type LIKE ?)")
            args.extend([f"%{q}%"] * 4)

        sql = """SELECT v.*, s.name as site_name, c.name as camera_name, z.name as zone_name
                 FROM violations v
                 JOIN sites s ON s.id=v.site_id
                 LEFT JOIN cameras c ON c.id=v.camera_id
                 LEFT JOIN zones z ON z.id=v.zone_id"""
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += f" ORDER BY v.id DESC LIMIT {limit}"

        with self._dbconn() as d:
            rows = d.execute(sql, args).fetchall()
            return [dict(r) for r in rows]

    def get_alerts(self, limit: int = 200) -> list:
        """Query alerts with violation context."""
        sql = """SELECT a.*, v.site_id, v.camera_id, v.zone_id, v.ppe_type, v.snapshot_path,
                        s.name as site_name, c.name as camera_name, z.name as zone_name
                 FROM alerts a
                 JOIN violations v ON v.id=a.violation_id
                 JOIN sites s ON s.id=v.site_id
                 LEFT JOIN cameras c ON c.id=v.camera_id
                 LEFT JOIN zones z ON z.id=v.zone_id
                 ORDER BY a.id DESC LIMIT ?"""
        with self._dbconn() as d:
            rows = d.execute(sql, (limit,)).fetchall()
            return [dict(r) for r in rows]
