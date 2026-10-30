from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from pathlib import Path
from datetime import datetime, date
import sqlite3, uuid

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
SNAPS = DATA / "snapshots"
DB_PATH = DATA / "octavision.db"
SNAPS.mkdir(parents=True, exist_ok=True)
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": ["http://localhost:5173", "http://127.0.0.1:5173"]}})

def now():
    return datetime.now().astimezone().isoformat(timespec="seconds")

def dbconn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c

def init_db():
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
        d.commit()

def obj(r): return dict(r) if r else None
def err(msg, code=400): return jsonify({"error":msg}),code


# Model-independent detection ingestion.
# Only a normalized "no_helmet" prediction creates a violation and alert.
HELMET_LABELS = {"helmet", "with_helmet", "helmet_detected", "hardhat"}
NO_HELMET_LABELS = {"no_helmet", "no-helmet", "without_helmet", "helmet_missing", "no_hardhat"}

def normalize_label(value):
    label = str(value or "").strip().lower().replace(" ", "_")
    if label in HELMET_LABELS:
        return "helmet_detected"
    if label in NO_HELMET_LABELS:
        return "helmet_missing"
    return None

@app.get("/api/health")
def health(): return jsonify({"ok":True,"service":"OctaVision API","time":now()})

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
    name=str(x.get("name","")).strip(); typ=str(x.get("source_type","simulated")); url=str(x.get("source_url","")).strip()
    if not name: return err("Camera name is required.")
    if typ not in {"simulated","webcam","rtsp"}: return err("Invalid source type.")
    if typ=="rtsp" and not url: return err("RTSP URL is required.")
    with dbconn() as d:
        if not d.execute("SELECT id FROM sites WHERE id=?",(sid,)).fetchone(): return err("Site not found.")
        cur=d.execute("INSERT INTO cameras(site_id,name,source_type,source_url,status,created_at) VALUES(?,?,?,?,?,?)",(sid,name,typ,url,"Demo" if typ=="simulated" else "Configured",now())); d.commit()
        return jsonify(obj(d.execute("SELECT c.*,s.name site_name FROM cameras c JOIN sites s ON s.id=c.site_id WHERE c.id=?",(cur.lastrowid,)).fetchone())),201

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
    status=request.args.get("status"); sid=request.args.get("site_id"); q=request.args.get("q","").strip()
    where=[]; args=[]
    if status in {"Open","Resolved"}: where.append("v.status=?"); args.append(status)
    if sid:
        try: where.append("v.site_id=?"); args.append(int(sid))
        except ValueError: return err("Invalid site id.")
    if q:
        where.append("(s.name LIKE ? OR c.name LIKE ? OR z.name LIKE ? OR v.ppe_type LIKE ?)")
        args += [f"%{q}%"]*4
    sql="SELECT v.*,s.name site_name,c.name camera_name,z.name zone_name FROM violations v JOIN sites s ON s.id=v.site_id LEFT JOIN cameras c ON c.id=v.camera_id LEFT JOIN zones z ON z.id=v.zone_id"
    if where: sql+=" WHERE "+" AND ".join(where)
    sql+=" ORDER BY v.id DESC LIMIT 500"
    with dbconn() as d: rows=d.execute(sql,args).fetchall()
    return jsonify([obj(x) for x in rows])

@app.patch("/api/violations/<int:vid>")
def resolve_violation(vid):
    x=request.get_json(silent=True) or {}; status=x.get("status")
    if status not in {"Open","Resolved"}: return err("Status must be Open or Resolved.")
    with dbconn() as d:
        cur=d.execute("UPDATE violations SET status=? WHERE id=?",(status,vid))
        if not cur.rowcount: return err("Violation not found.",404)
        d.commit()
        return jsonify(obj(d.execute("SELECT * FROM violations WHERE id=?",(vid,)).fetchone()))

@app.get("/api/alerts")
def alerts():
    with dbconn() as d: rows=d.execute("""SELECT a.*,v.site_id,v.camera_id,v.zone_id,v.ppe_type,v.snapshot_path,s.name site_name,c.name camera_name,z.name zone_name FROM alerts a JOIN violations v ON v.id=a.violation_id JOIN sites s ON s.id=v.site_id LEFT JOIN cameras c ON c.id=v.camera_id LEFT JOIN zones z ON z.id=v.zone_id ORDER BY a.id DESC LIMIT 200""").fetchall()
    return jsonify([obj(x) for x in rows])

@app.post("/api/alerts/<int:aid>/acknowledge")
def acknowledge(aid):
    with dbconn() as d:
        cur=d.execute("UPDATE alerts SET status='Acknowledged',acknowledged_at=? WHERE id=?",(now(),aid))
        if not cur.rowcount: return err("Alert not found.",404)
        d.commit()
        return jsonify(obj(d.execute("SELECT * FROM alerts WHERE id=?",(aid,)).fetchone()))

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
def snapshot(filename): return send_from_directory(SNAPS,filename)

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
    app.run(host="127.0.0.1",port=5000,debug=True)
