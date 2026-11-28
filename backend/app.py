from flask import Flask, jsonify, request, send_from_directory, Response
from flask_cors import CORS
from pathlib import Path
from datetime import datetime, date
import base64
import logging
import threading
import sqlite3, uuid
import math

import cv2
import numpy as np
# Ultralytics is lazy-loaded on first inference request
from violation_service import ViolationManagementService
from site_profiles import SITE_PPE, supported, process_boxes
from pi_config import get_pi_config, check_pi_status, PI_STREAM_URL
from pi_camera_worker import PiCameraWorker

logger = logging.getLogger("octavision.api")

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
SNAPS = DATA / "snapshots"
DB_PATH = DATA / "octavision.db"
SNAPS.mkdir(parents=True, exist_ok=True)
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Modular Violation Management Service
violation_service = ViolationManagementService(DB_PATH, SNAPS, cooldown_secs=20)

def now():
    return datetime.now().astimezone().isoformat(timespec="seconds")

def dbconn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c

def init_db():
    violation_service.db_path = DB_PATH
    with dbconn() as d:
        d.executescript("""
        CREATE TABLE IF NOT EXISTS sites(id INTEGER PRIMARY KEY, name TEXT NOT NULL, site_type TEXT NOT NULL, location TEXT DEFAULT '', created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS cameras(id INTEGER PRIMARY KEY, site_id INTEGER NOT NULL REFERENCES sites(id) ON DELETE CASCADE, name TEXT NOT NULL, source_type TEXT NOT NULL DEFAULT 'simulated', source_url TEXT DEFAULT '', status TEXT NOT NULL DEFAULT 'Demo', created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS zones(id INTEGER PRIMARY KEY, site_id INTEGER NOT NULL REFERENCES sites(id) ON DELETE CASCADE, camera_id INTEGER REFERENCES cameras(id) ON DELETE SET NULL, name TEXT NOT NULL, required_ppe TEXT NOT NULL DEFAULT 'helmet', created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS violations(id INTEGER PRIMARY KEY, event_key TEXT NOT NULL UNIQUE, site_id INTEGER NOT NULL REFERENCES sites(id), camera_id INTEGER REFERENCES cameras(id) ON DELETE SET NULL, zone_id INTEGER REFERENCES zones(id) ON DELETE SET NULL, ppe_type TEXT NOT NULL, severity TEXT NOT NULL DEFAULT 'High', confidence REAL NOT NULL DEFAULT .93, status TEXT NOT NULL DEFAULT 'Open', snapshot_path TEXT DEFAULT '', occurred_at TEXT NOT NULL, source TEXT NOT NULL DEFAULT 'simulated');
        CREATE TABLE IF NOT EXISTS alerts(id INTEGER PRIMARY KEY, violation_id INTEGER NOT NULL REFERENCES violations(id) ON DELETE CASCADE, message TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Active', created_at TEXT NOT NULL, acknowledged_at TEXT);
        CREATE TABLE IF NOT EXISTS model_registry(id INTEGER PRIMARY KEY, name TEXT NOT NULL, site_type TEXT NOT NULL, version TEXT NOT NULL, status TEXT NOT NULL, weights_path TEXT DEFAULT '');
        """)
        if d.execute("SELECT COUNT(*) FROM sites").fetchone()[0] == 0:
            t=now()
            d.execute("INSERT INTO sites(name,site_type,location,created_at) VALUES(?,?,?,?)",("Demo Construction Site","construction","Local demo",t))
            sid=d.execute("SELECT last_insert_rowid()").fetchone()[0]
            d.execute("INSERT INTO cameras(site_id,name,source_type,status,created_at) VALUES(?,?,?,?,?)",(sid,"Camera 01 — Demo","simulated","Demo",t))
            cid=d.execute("SELECT last_insert_rowid()").fetchone()[0]
            d.execute("INSERT INTO zones(site_id,camera_id,name,required_ppe,created_at) VALUES(?,?,?,?,?)",(sid,cid,"Main Hazard Zone","helmet",t))
            for name,typ in [("General Model","general"),("Construction Site Model","construction"),("Road Construction Model","road"),("Chemical Factory Model","chemical"),("Mining & Quarry Model","mining")]:
                d.execute("INSERT INTO model_registry(name,site_type,version,status) VALUES(?,?,?,?)",(name,typ,"not-connected","Planned"))

        # Auto-register Raspberry Pi 5 hardware relay camera if not present
        rpi_cam = d.execute("SELECT id FROM cameras WHERE source_type='rpi'").fetchone()
        if not rpi_cam:
            first_site = d.execute("SELECT id FROM sites ORDER BY id ASC LIMIT 1").fetchone()
            if first_site:
                t = now()
                d.execute(
                    "INSERT INTO cameras(site_id,name,source_type,source_url,status,created_at) VALUES(?,?,?,?,?,?)",
                    (first_site[0], "Raspberry Pi 5 — Live Video Relay", "rpi", PI_STREAM_URL, "Active", t)
                )
        d.commit()

def obj(r): return dict(r) if r else None
def err(msg, code=400): return jsonify({"error":msg}),code


# Model-independent detection ingestion.
# Only a normalized "no_helmet" prediction creates a violation and alert.
HELMET_LABELS = {"helmet", "with_helmet", "helmet_detected", "hardhat"}
NO_HELMET_LABELS = {"no_helmet", "no-helmet", "without_helmet", "helmet_missing", "no_hardhat"}
VEST_LABELS = {"vest", "safety_vest", "with_vest"}
NO_VEST_LABELS = {"no_vest", "no-vest", "without_vest", "vest_missing"}
INFERENCE_LABEL_MAP = {
    "helmet": "helmet",
    "hardhat": "helmet",
    "with_helmet": "helmet",
    "helmet_detected": "helmet",
    "no_helmet": "no_helmet",
    "no-helmet": "no_helmet",
    "without_helmet": "no_helmet",
    "helmet_missing": "no_helmet",
    "vest": "vest",
    "safety_vest": "vest",
    "with_vest": "vest",
    "no_vest": "no_vest",
    "no-vest": "no_vest",
    "without_vest": "no_vest",
    "vest_missing": "no_vest",
    "person": "person",
    "human": "person",
    "worker": "person",
}

MODEL_RUNTIME = {
    "instances": {},
    "lock": threading.Lock(),
}

# In-memory cooldown store: {camera_id: {ppe_type: last_event_unix_time}}
# Prevents duplicate violations for the same camera+PPE within 30 seconds.
VIOLATION_COOLDOWNS: dict = {}
VIOLATION_COOLDOWN_SECS = 30
COOLDOWN_LOCK = threading.Lock()

SUPPORTED_SITE_TYPES = {"construction", "chemical", "road", "mining", "general"}

SITE_MODEL_CANDIDATES = {
    "construction": [
        ROOT.parent / "runs" / "detect" / "runs" / "octavision" / "construction_v1" / "weights" / "best.pt",
    ],
    "chemical": [
        ROOT.parent / "runs" / "detect" / "runs" / "octavision" / "chemical_v1" / "weights" / "best.pt",
    ],
    "road": [
        ROOT.parent / "runs" / "detect" / "runs" / "octavision" / "road_v1" / "weights" / "best.pt",
    ],
    "mining": [
        ROOT.parent / "runs" / "detect" / "runs" / "octavision" / "mining_v1" / "weights" / "best.pt",
    ],
    "general": [
        ROOT.parent / "runs" / "detect" / "runs" / "octavision" / "general_v1" / "weights" / "best.pt",
    ],
}

def normalize_label(value):
    label = str(value or "").strip().lower().replace(" ", "_")
    if label in HELMET_LABELS:
        return "helmet_detected"
    if label in NO_HELMET_LABELS:
        return "helmet_missing"
    return None


def _resolve_site_type(value):
    site_type = str(value or "construction").strip().lower()
    return site_type if site_type in SUPPORTED_SITE_TYPES else None


def _connected_weights(site_type):
    with dbconn() as d:
        row = d.execute(
            "SELECT weights_path FROM model_registry WHERE site_type=? ORDER BY id LIMIT 1",
            (site_type,),
        ).fetchone()
    if row:
        configured = Path(str(row["weights_path"] or "")).expanduser()
        if configured and configured.is_file():
            return configured

    candidates = [ROOT.parent / "weights" / f"{site_type}.pt"] + SITE_MODEL_CANDIDATES.get(site_type, [])
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _get_model(site_type="construction"):
    weights_path = _connected_weights(site_type)
    if not weights_path:
        return None, None, f"No model weights found for site_type='{site_type}'. Run python tools/install_ppe_model.py from the project root for general, construction and road. Chemical/mining require separate trained weights."

    resolved = str(weights_path.resolve())
    with MODEL_RUNTIME["lock"]:
        key = f"{site_type}|{resolved}"
        if key not in MODEL_RUNTIME["instances"]:
            MODEL_RUNTIME["instances"] = {k: v for k, v in MODEL_RUNTIME["instances"].items() if not k.startswith(f"{site_type}|")}
            try:
                from ultralytics import YOLO
                MODEL_RUNTIME["instances"] = {key: YOLO(resolved)}
            except Exception as exc:
                return None, resolved, f"Could not load {site_type} model: {exc}"
        model = MODEL_RUNTIME["instances"][key]
    return model, resolved, None


def _is_rpi_camera(cid):
    if not cid:
        return False
    try:
        with dbconn() as d:
            row = d.execute("SELECT source_type FROM cameras WHERE id=?", (int(cid),)).fetchone()
            return bool(row and row["source_type"] == "rpi")
    except Exception:
        return False


def _decode_image_from_request():
    if "file" in request.files:
        uploaded = request.files["file"]
        raw = uploaded.read()
        if not raw:
            return None, "Uploaded file is empty."
        array = np.frombuffer(raw, dtype=np.uint8)
        image = cv2.imdecode(array, cv2.IMREAD_COLOR)
        if image is None:
            return None, "Unable to decode uploaded image."
        return image, None

    payload = request.get_json(silent=True) or {}
    if request.form:
        payload = request.form.to_dict()

    source = str(payload.get("source") or "").strip().lower()
    cid = payload.get("camera_id")

    # If stream source is Raspberry Pi 5
    if source in {"rpi", "pi", "raspberry_pi"} or (cid and _is_rpi_camera(cid)):
        worker = PiCameraWorker.get_instance()
        success, frame, _ = worker.get_latest_frame()
        if not success or frame is None:
            return None, "Raspberry Pi stream is currently offline or unreachable."
        return frame, None

    image_data = str(payload.get("image_data") or "").strip()
    if not image_data:
        return None, "Send multipart file, base64 image_data, or source='rpi'."

    try:
        base64_part = image_data.split(",", 1)[1] if "," in image_data else image_data
        binary = base64.b64decode(base64_part)
        array = np.frombuffer(binary, dtype=np.uint8)
        image = cv2.imdecode(array, cv2.IMREAD_COLOR)
    except Exception:
        return None, "Invalid base64 image_data."

    if image is None:
        return None, "Unable to decode image_data."
    return image, None


def _normalize_inference_label(raw_label):
    key = str(raw_label or "").strip().lower().replace(" ", "_")
    return INFERENCE_LABEL_MAP.get(key, key)


def _run_inference(image, site_type="construction", conf=0.25, iou=0.45):
    model, weights_path, model_error = _get_model(site_type=site_type)
    if model_error:
        return None, model_error

    # Dynamic threshold: reject noise < 0.22 while ensuring workers in profile are detected
    effective_conf = max(float(conf or 0.25), 0.22)
    result = model.predict(source=image, conf=effective_conf, iou=iou, verbose=False, max_det=60)[0]
    counts, detections = process_boxes(result.boxes, result.names, site_type)
    return {
        "site_type": site_type,
        "weights_path": weights_path,
        "image": {"width": int(result.orig_shape[1]), "height": int(result.orig_shape[0])},
        "required_ppe": list(SITE_PPE[site_type]),
        "capabilities": supported(result.names, site_type),
        "counts": counts,
        "has_violation": any(d["is_violation"] for d in detections),
        "detections": detections,
    }, None

@app.get("/api/health")
def health(): return jsonify({"ok":True,"service":"OctaVision API","time":now()})


@app.get("/api/model/status")
def model_status():
    site_type = _resolve_site_type(request.args.get("site_type", "construction"))
    if not site_type:
        return err("site_type must be one of construction, chemical, road, mining, general.")

    model, path, model_error = _get_model(site_type=site_type)
    if model_error:
        return jsonify({"ready": False, "site_type": site_type, "error": model_error}), 200
    return jsonify({
        "ready": model is not None,
        "site_type": site_type,
        "weights_path": path,
        "required_ppe": list(SITE_PPE[site_type]),
        "capabilities": supported(model.names, site_type),
    })


@app.post("/api/model/infer")
def model_infer():
    image, decode_error = _decode_image_from_request()
    if decode_error:
        return err(decode_error)

    payload = request.get_json(silent=True) or {}
    if request.form:
        payload = request.form.to_dict()

    try:
        conf = float(payload.get("confidence", 0.25))
        iou = float(payload.get("iou", 0.45))
    except (ValueError, TypeError):
        return err("confidence and iou must be numbers.")

    site_type = _resolve_site_type(payload.get("site_type", "construction"))
    if not site_type:
        return err("site_type must be one of construction, chemical, road, mining, general.")

    if not 0 <= conf <= 1:
        return err("confidence must be between 0 and 1.")
    if not 0 <= iou <= 1:
        return err("iou must be between 0 and 1.")

    try:
        inference, infer_error = _run_inference(image, site_type=site_type, conf=conf, iou=iou)
    except Exception as exc:
        return err(f"Inference failed: {exc}", 503)
    if infer_error:
        return err(infer_error, 503)

    # Automatic violation recording & forensic evidence capture if camera_id provided
    recorded_violations = []
    cid = payload.get("camera_id")
    if cid and inference.get("has_violation"):
        try:
            with dbconn() as d:
                cam = d.execute("SELECT * FROM cameras WHERE id=?", (int(cid),)).fetchone()
            if cam:
                res = violation_service.process_frame_detections(
                    site_id=cam["site_id"],
                    camera_id=cam["id"],
                    detections=inference.get("detections", []),
                    image_input=image,
                )
                recorded_violations = res.get("created", [])
        except Exception as exc:
            logger.warning(f"Error processing inference violations: {exc}")

    return jsonify({"ok": True, **inference, "recorded_violations": recorded_violations})

@app.get("/api/dashboard")
def dashboard():
    today=date.today().isoformat()
    with dbconn() as d:
        stats={
            "violations_today":d.execute("SELECT COUNT(*) FROM violations WHERE date(occurred_at)=?",(today,)).fetchone()[0],
            "open_violations":d.execute("SELECT COUNT(*) FROM violations WHERE status='Open'").fetchone()[0],
            "active_alerts":d.execute("SELECT COUNT(*) FROM alerts WHERE status='Active'").fetchone()[0],
            "sites":d.execute("SELECT COUNT(*) FROM sites").fetchone()[0],
            "cameras":d.execute("SELECT COUNT(*) FROM cameras").fetchone()[0]}
        recent=d.execute("""SELECT v.*,s.name site_name,c.name camera_name,z.name zone_name FROM violations v JOIN sites s ON s.id=v.site_id LEFT JOIN cameras c ON c.id=v.camera_id LEFT JOIN zones z ON z.id=v.zone_id ORDER BY v.id DESC LIMIT 8""").fetchall()
        daily=d.execute("""SELECT date(occurred_at) day,COUNT(*) count FROM violations WHERE occurred_at >= datetime('now','-6 days') GROUP BY date(occurred_at) ORDER BY day""").fetchall()
    return jsonify({"stats":stats,"recent_violations":[obj(x) for x in recent],"daily_counts":[obj(x) for x in daily]})

@app.get("/api/sites")
def sites():
    with dbconn() as d: rows=d.execute("SELECT s.*, (SELECT COUNT(*) FROM cameras c WHERE c.site_id=s.id) camera_count FROM sites s ORDER BY id").fetchall()
    return jsonify([obj(x) for x in rows])

@app.post("/api/sites")
def add_site():
    x=request.get_json(silent=True) or {}; name=str(x.get("name","")).strip(); typ=str(x.get("site_type","construction")); loc=str(x.get("location","")).strip()
    if not name: return err("Site name is required.")
    if typ not in {"construction","road","chemical","mining","general"}: return err("Invalid site type.")
    with dbconn() as d:
        cur=d.execute("INSERT INTO sites(name,site_type,location,created_at) VALUES(?,?,?,?)",(name,typ,loc,now())); d.commit()
        return jsonify(obj(d.execute("SELECT * FROM sites WHERE id=?",(cur.lastrowid,)).fetchone())),201

@app.get("/api/cameras")
def cameras():
    with dbconn() as d: rows=d.execute("SELECT c.*,s.name site_name FROM cameras c JOIN sites s ON s.id=c.site_id ORDER BY c.id").fetchall()
    return jsonify([obj(x) for x in rows])

@app.post("/api/cameras")
def add_camera():
    x=request.get_json(silent=True) or {}
    try: sid=int(x.get("site_id"))
    except (ValueError,TypeError): return err("Choose a site.")
    name=str(x.get("name","")).strip(); typ=str(x.get("source_type","simulated")).lower(); url=str(x.get("source_url","")).strip()
    if not name: return err("Camera name is required.")
    if typ not in {"simulated","webcam","rtsp","rpi"}: return err("Invalid source type. Expected simulated, webcam, rtsp, or rpi.")
    if typ=="rtsp" and not url: return err("RTSP URL is required.")
    if typ=="rpi" and not url: url=PI_STREAM_URL
    with dbconn() as d:
        if not d.execute("SELECT id FROM sites WHERE id=?",(sid,)).fetchone(): return err("Site not found.")
        status = "Active" if typ in {"webcam", "rpi"} else ("Demo" if typ=="simulated" else "Configured")
        cur=d.execute("INSERT INTO cameras(site_id,name,source_type,source_url,status,created_at) VALUES(?,?,?,?,?,?)",(sid,name,typ,url,status,now())); d.commit()
        return jsonify(obj(d.execute("SELECT c.*,s.name site_name FROM cameras c JOIN sites s ON s.id=c.site_id WHERE c.id=?",(cur.lastrowid,)).fetchone())),201


@app.get("/api/cameras/pi-config")
def camera_pi_config():
    """Return centralized Raspberry Pi configuration."""
    return jsonify({"ok": True, "config": get_pi_config()})


@app.get("/api/cameras/pi-status")
def camera_pi_status():
    """Return real-time stream status and Pi hardware health."""
    worker = PiCameraWorker.get_instance()
    worker_stat = worker.get_status()
    hw_stat = check_pi_status(timeout=1.5)
    return jsonify({
        "ok": True,
        "online": worker_stat["online"] or hw_stat["online"],
        "worker": worker_stat,
        "hardware": hw_stat,
    })


@app.get("/api/cameras/pi-stream")
def camera_pi_stream():
    """Proxy live MJPEG stream from Raspberry Pi 5 to clients."""
    worker = PiCameraWorker.get_instance()
    return Response(
        worker.generate_mjpeg_stream(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )


@app.get("/api/cameras/<int:cid>/stream")
def camera_stream_by_id(cid):
    """Generic stream endpoint by camera ID."""
    with dbconn() as d:
        cam = d.execute("SELECT * FROM cameras WHERE id=?", (cid,)).fetchone()
    if not cam:
        return err("Camera not found.", 404)
    if cam["source_type"] == "rpi":
        worker = PiCameraWorker.get_instance()
        return Response(
            worker.generate_mjpeg_stream(),
            mimetype="multipart/x-mixed-replace; boundary=frame"
        )
    return err("Streaming only available for Raspberry Pi / MJPEG sources.", 400)

@app.get("/api/zones")
def zones():
    with dbconn() as d: rows=d.execute("SELECT z.*,s.name site_name,c.name camera_name FROM zones z JOIN sites s ON s.id=z.site_id LEFT JOIN cameras c ON c.id=z.camera_id ORDER BY z.id").fetchall()
    return jsonify([obj(x) for x in rows])

@app.post("/api/zones")
def add_zone():
    x=request.get_json(silent=True) or {}
    try: sid=int(x.get("site_id"))
    except (ValueError,TypeError): return err("Choose a site.")
    cid=x.get("camera_id")
    try: cid=int(cid) if cid not in ("",None) else None
    except (ValueError,TypeError): return err("Invalid camera.")
    name=str(x.get("name","")).strip(); ppe=str(x.get("required_ppe","helmet"))
    if not name: return err("Zone name is required.")
    if ppe not in {"helmet","vest","helmet,vest"}: return err("Invalid PPE requirement.")
    with dbconn() as d:
        if not d.execute("SELECT id FROM sites WHERE id=?",(sid,)).fetchone(): return err("Site not found.")
        if cid and not d.execute("SELECT id FROM cameras WHERE id=? AND site_id=?",(cid,sid)).fetchone(): return err("Camera must belong to selected site.")
        cur=d.execute("INSERT INTO zones(site_id,camera_id,name,required_ppe,created_at) VALUES(?,?,?,?,?)",(sid,cid,name,ppe,now())); d.commit()
        return jsonify(obj(d.execute("SELECT z.*,s.name site_name,c.name camera_name FROM zones z JOIN sites s ON s.id=z.site_id LEFT JOIN cameras c ON c.id=z.camera_id WHERE z.id=?",(cur.lastrowid,)).fetchone())),201

@app.get("/api/violations")
def violations():
    status = request.args.get("status")
    sid = request.args.get("site_id")
    q = request.args.get("q", "").strip()
    site_int = None
    if sid:
        try:
            site_int = int(sid)
        except ValueError:
            return err("Invalid site id.")
    violation_service.db_path = DB_PATH
    rows = violation_service.get_violations(status=status, site_id=site_int, q=q)
    return jsonify(rows)

@app.patch("/api/violations/<int:vid>")
def resolve_violation(vid):
    x = request.get_json(silent=True) or {}
    status = x.get("status")
    if status not in {"Open", "Resolved"}:
        return err("Status must be Open or Resolved.")
    violation_service.db_path = DB_PATH
    row = violation_service.resolve_violation(vid, status)
    if not row:
        return err("Violation not found.", 404)
    return jsonify(row)

@app.get("/api/alerts")
def alerts():
    violation_service.db_path = DB_PATH
    rows = violation_service.get_alerts()
    return jsonify(rows)

@app.post("/api/alerts/<int:aid>/acknowledge")
def acknowledge(aid):
    violation_service.db_path = DB_PATH
    row = violation_service.acknowledge_alert(aid)
    if not row:
        return err("Alert not found.", 404)
    return jsonify(row)

@app.post("/api/demo/simulate-violation")
def simulate():
    x=request.get_json(silent=True) or {}
    try: sid=int(x.get("site_id"))
    except (ValueError,TypeError):
        with dbconn() as d:
            r=d.execute("SELECT id FROM sites ORDER BY id LIMIT 1").fetchone()
            if not r: return err("Create a site first.",409)
            sid=r["id"]
    ppe=str(x.get("ppe_type","helmet"))
    if ppe not in {"helmet","vest","helmet,vest"}: return err("Invalid PPE type.")
    event_key=str(uuid.uuid4()); ts=now()
    with dbconn() as d:
        if not d.execute("SELECT id FROM sites WHERE id=?",(sid,)).fetchone(): return err("Site not found.",404)
        cam=d.execute("SELECT id FROM cameras WHERE site_id=? ORDER BY id LIMIT 1",(sid,)).fetchone()
        zone=d.execute("SELECT id FROM zones WHERE site_id=? ORDER BY id LIMIT 1",(sid,)).fetchone()
        if not cam: return err("Add a camera to this site first.",409)
        if not zone: return err("Add a hazard zone to this site first.",409)
        filename=f"demo_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{event_key[:8]}.svg"
        svg=f"""<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540"><rect width="960" height="540" fill="#101827"/><rect x="24" y="24" width="912" height="492" rx="18" fill="#1d293b" stroke="#64748b"/><text x="56" y="76" fill="#f8fafc" font-size="28" font-family="Arial">OctaVision - SIMULATED EVENT</text><rect x="56" y="112" width="848" height="260" rx="12" fill="#26364c"/><rect x="420" y="155" width="120" height="175" rx="18" fill="none" stroke="#f87171" stroke-width="5"/><circle cx="480" cy="190" r="28" fill="#cbd5e1"/><path d="M445 223 L515 223 L535 315 L425 315 Z" fill="#64748b"/><text x="56" y="418" fill="#fca5a5" font-size="25" font-family="Arial">PPE missing: {ppe}</text><text x="56" y="458" fill="#cbd5e1" font-size="18" font-family="Arial">Placeholder image - not a real camera snapshot.</text><text x="56" y="488" fill="#94a3b8" font-size="16" font-family="Arial">{ts}</text></svg>"""
        (SNAPS/filename).write_text(svg,encoding="utf-8")
        cur=d.execute("INSERT INTO violations(event_key,site_id,camera_id,zone_id,ppe_type,snapshot_path,occurred_at) VALUES(?,?,?,?,?,?,?)",(event_key,sid,cam["id"],zone["id"],ppe,f"/api/snapshots/{filename}",ts))
        vid=cur.lastrowid; message=f"Confirmed simulated PPE violation: {ppe.replace(',', ' + ')} missing."
        ac=d.execute("INSERT INTO alerts(violation_id,message,created_at) VALUES(?,?,?)",(vid,message,ts))
        d.commit()
        v=d.execute("SELECT * FROM violations WHERE id=?",(vid,)).fetchone(); a=d.execute("SELECT * FROM alerts WHERE id=?",(ac.lastrowid,)).fetchone()
    return jsonify({"violation":obj(v),"alert":obj(a),"simulated":True}),201


@app.post("/api/violations/from-inference")
def violation_from_inference():
    """
    Called by the frontend live loop when has_violation=true.
    Accepts: site_id, camera_id, zone_id (opt), detections[], image_data (base64 JPEG).
    Delegates to decoupled ViolationManagementService for duplicate suppression,
    evidence snapshot capture and database persistence.
    """
    x = request.get_json(silent=True)
    if not isinstance(x, dict):
        return err("Send a JSON object.")

    try:
        sid = int(x.get("site_id"))
        cid = int(x.get("camera_id"))
    except (ValueError, TypeError):
        return err("site_id and camera_id are required integers.")

    zid = x.get("zone_id")
    try:
        zid = int(zid) if zid not in ("", None) else None
    except (ValueError, TypeError):
        return err("zone_id must be an integer.")

    detections = x.get("detections", [])
    if not isinstance(detections, list) or len(detections) > 100:
        return err("detections must be a list of at most 100 objects.")
    with dbconn() as d:
        site = d.execute("SELECT site_type FROM sites WHERE id=?", (sid,)).fetchone()
        if not site:
            return err("Site not found.", 404)
        if not d.execute("SELECT id FROM cameras WHERE id=? AND site_id=?", (cid, sid)).fetchone():
            return err("Camera must belong to selected site.")
        if zid and not d.execute("SELECT id FROM zones WHERE id=? AND site_id=? AND (camera_id IS NULL OR camera_id=?)", (zid, sid, cid)).fetchone():
            return err("Zone must belong to selected site and camera.")
        allowed = SITE_PPE.get(site["site_type"], ())
    for detection in detections:
        if not isinstance(detection, dict):
            return err("Each detection must be an object.")
        try:
            confidence = float(detection.get("confidence"))
        except (ValueError, TypeError):
            return err("Detection confidence must be a number between 0 and 1.")
        if not math.isfinite(confidence) or not 0 <= confidence <= 1:
            return err("Detection confidence must be a number between 0 and 1.")
        label = detection.get("normalized_label")
        if not isinstance(label, str):
            return err("Detection normalized_label must be a string.")
        if detection.get("is_violation") and (not label.startswith("no_") or label[3:] not in allowed):
            return err("Violation class is not supported by the selected site.")
    image_data = str(x.get("image_data") or "").strip()

    violation_service.db_path = DB_PATH
    result = violation_service.process_frame_detections(
        site_id=sid,
        camera_id=cid,
        detections=detections,
        image_input=image_data,
        zone_id=zid,
    )

    created_results = []
    snapshot_path = ""
    for r in result.get("created", []):
        created_results.append({
            "violation": r.get("violation"),
            "alert": r.get("alert"),
        })
        if r.get("snapshot_path"):
            snapshot_path = r.get("snapshot_path")

    return jsonify({
        "created": created_results,
        "suppressed": result.get("suppressed", 0),
        "snapshot_path": snapshot_path,
    }), 201


@app.post("/api/detections")
def ingest_detection():
    """
    Model-independent ingestion contract.
    JSON fields: site_id, camera_id, zone_id (optional), event_key (optional),
    class_name, confidence (0..1), occurred_at (optional ISO-8601),
    source (default "model"), snapshot_path (optional reference).
    A helmet_detected prediction is recorded as a non-violation observation in
    the response but does not create a violation/alert. helmet_missing creates both.
    """
    x = request.get_json(silent=True)
    if not isinstance(x, dict):
        return err("Send a JSON object.")

    try:
        sid = int(x.get("site_id"))
        cid = int(x.get("camera_id"))
    except (ValueError, TypeError):
        return err("site_id and camera_id must be integers.")

    zid = x.get("zone_id")
    try:
        zid = int(zid) if zid not in ("", None) else None
    except (ValueError, TypeError):
        return err("zone_id must be an integer or null.")

    normalized = normalize_label(x.get("class_name", x.get("label")))
    if normalized is None:
        return err("Unsupported class_name. Expected helmet or no_helmet (or documented aliases).")

    try:
        confidence = float(x.get("confidence"))
    except (ValueError, TypeError):
        return err("confidence must be a number between 0 and 1.")
    if not 0 <= confidence <= 1:
        return err("confidence must be between 0 and 1.")

    event_key = str(x.get("event_key") or uuid.uuid4()).strip()
    if not event_key or len(event_key) > 160:
        return err("event_key must contain 1–160 characters.")

    occurred_at = str(x.get("occurred_at") or now()).strip()
    # Accept ISO timestamps; normalize Z to an explicit UTC offset for validation.
    try:
        datetime.fromisoformat(occurred_at.replace("Z", "+00:00"))
    except ValueError:
        return err("occurred_at must be an ISO-8601 timestamp.")

    source = str(x.get("source") or "model").strip()
    if source not in {"model", "adapter", "api_test"}:
        return err("source must be model, adapter, or api_test.")

    snapshot_path = str(x.get("snapshot_path") or "").strip()
    if len(snapshot_path) > 500:
        return err("snapshot_path is too long.")

    with dbconn() as d:
        site = d.execute("SELECT id FROM sites WHERE id=?", (sid,)).fetchone()
        if not site:
            return err("Site not found.", 404)
        camera = d.execute("SELECT id FROM cameras WHERE id=? AND site_id=?", (cid, sid)).fetchone()
        if not camera:
            return err("Camera not found for this site.", 404)
        if zid is not None:
            zone = d.execute("SELECT id FROM zones WHERE id=? AND site_id=? AND (camera_id IS NULL OR camera_id=?)", (zid, sid, cid)).fetchone()
            if not zone:
                return err("Zone not found for this site/camera.", 404)

        if normalized == "helmet_detected":
            return jsonify({
                "accepted": True,
                "is_violation": False,
                "normalized_class": normalized,
                "message": "Helmet detected; no violation or alert created.",
                "event_key": event_key
            }), 200

        existing = d.execute("SELECT * FROM violations WHERE event_key=?", (event_key,)).fetchone()
        if existing:
            alert = d.execute("SELECT * FROM alerts WHERE violation_id=? ORDER BY id DESC LIMIT 1", (existing["id"],)).fetchone()
            return jsonify({
                "accepted": True,
                "duplicate": True,
                "is_violation": True,
                "violation": obj(existing),
                "alert": obj(alert)
            }), 200

        ts = occurred_at
        cur = d.execute(
            """INSERT INTO violations(event_key,site_id,camera_id,zone_id,ppe_type,severity,confidence,status,snapshot_path,occurred_at,source)
               VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (event_key, sid, cid, zid, "helmet", "High", confidence, "Open", snapshot_path, ts, source)
        )
        vid = cur.lastrowid
        message = f"Helmet missing detected (confidence {confidence:.0%})."
        ac = d.execute("INSERT INTO alerts(violation_id,message,created_at) VALUES(?,?,?)", (vid, message, now()))
        d.commit()
        violation = d.execute("SELECT * FROM violations WHERE id=?", (vid,)).fetchone()
        alert = d.execute("SELECT * FROM alerts WHERE id=?", (ac.lastrowid,)).fetchone()

    return jsonify({
        "accepted": True,
        "duplicate": False,
        "is_violation": True,
        "normalized_class": normalized,
        "violation": obj(violation),
        "alert": obj(alert)
    }), 201

@app.get("/api/snapshots/<path:filename>")
def snapshot(filename): return send_from_directory(SNAPS, filename)


@app.get("/api/violations/<int:vid>")
def violation_detail(vid):
    violation_service.db_path = DB_PATH
    row = violation_service.get_violation(vid)
    if not row:
        return err("Violation not found.", 404)
    return jsonify(row)


@app.get("/api/alerts/unread-count")
def alerts_unread_count():
    with dbconn() as d:
        count = d.execute("SELECT COUNT(*) FROM alerts WHERE status='Active'").fetchone()[0]
    return jsonify({"unread": count})

@app.get("/api/reports/daily")
def report():
    day=request.args.get("date",date.today().isoformat())
    try: date.fromisoformat(day)
    except ValueError: return err("Date must be YYYY-MM-DD.")
    with dbconn() as d:
        rows=d.execute("""SELECT s.name site_name,COUNT(v.id) violations,SUM(CASE WHEN v.status='Open' THEN 1 ELSE 0 END) open_violations,SUM(CASE WHEN v.status='Resolved' THEN 1 ELSE 0 END) resolved_violations FROM sites s LEFT JOIN violations v ON v.site_id=s.id AND date(v.occurred_at)=? GROUP BY s.id ORDER BY s.name""",(day,)).fetchall()
        total=d.execute("SELECT COUNT(*) FROM violations WHERE date(occurred_at)=?",(day,)).fetchone()[0]
    return jsonify({"date":day,"total_violations":total,"by_site":[obj(x) for x in rows]})

@app.get("/api/models")
def models():
    with dbconn() as d: rows=d.execute("SELECT * FROM model_registry ORDER BY id").fetchall()
    return jsonify([obj(x) for x in rows])

@app.errorhandler(404)
def missing(_): return jsonify({"error":"Endpoint not found."}),404

if __name__=="__main__":
    init_db()
    print(f"OctaVision API running; database: {DB_PATH}")
    import sys, os
    port = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else int(os.environ.get("PORT", 5000))
    app.run(host=os.environ.get("OCTAVISION_HOST", "127.0.0.1"), port=port, debug=False, threaded=True)
