# OctaVision Local Starter — Milestone 2

React + Flask + SQLite dashboard with simulated events plus a model-independent detection ingestion API and an optional YOLO adapter scaffold.

## Requirements
- Windows 10/11
- Python 3.10+
- Node.js 18+ and npm
- VS Code

## Start backend
Open the project folder in VS Code, then Terminal → New Terminal:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

If PowerShell blocks activation, run:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Backend: http://127.0.0.1:5000  
Health check: http://127.0.0.1:5000/api/health

## Start frontend
Open a second VS Code terminal, leaving Flask running:

```powershell
cd frontend
npm install
npm run dev
```

Open the URL printed by Vite, usually http://localhost:5173.

## New endpoint: POST /api/detections

The endpoint is model-independent. It accepts normalized predictions from any detector. Only `no_helmet` creates a violation and alert; `helmet` is accepted as a non-violation observation.

Example PowerShell test (with backend running). Use IDs from the seeded demo site/camera; the starter normally seeds site ID `1` and camera ID `1` in a fresh database:

```powershell
$body = @{
  site_id = 1
  camera_id = 1
  class_name = "no_helmet"
  confidence = 0.93
  event_key = "manual-test-no-helmet-001"
  source = "api_test"
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:5000/api/detections" -ContentType "application/json" -Body $body
```

Repeat the exact request to verify duplicate handling: it should return `duplicate = true` instead of creating another violation.

Test the helmet class by changing `class_name` to `"helmet"` and using a new `event_key`. It should not create a violation or alert.

The API also validates site/camera/optional zone IDs, class names, confidence (`0`–`1`), timestamp format and source. Use the same `event_key` for retries of one detection event to prevent duplicate violations.

## Automated API tests
In the backend terminal with the virtual environment active:

```powershell
python -m unittest discover -s tests -v
```

The tests use a temporary SQLite database and cover no-helmet violation creation, helmet non-violation handling, duplicate-event idempotency, and invalid confidence rejection.

## Optional YOLO adapter (only once weights are trained)
The API itself does not require Ultralytics. Install adapter dependencies separately:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements-model.txt
```

When you have a trained `best.pt` and a test image, run from the `backend` folder:

```powershell
python model_adapter\yolo_adapter.py --image "C:\path\to\test.jpg" --weights "C:\path\to\best.pt" --site-id 1 --camera-id 1
```

Optional zone:
```powershell
python model_adapter\yolo_adapter.py --image "C:\path\to\test.jpg" --weights "C:\path\to\best.pt" --site-id 1 --camera-id 1 --zone-id 1
```

Before running it, edit `backend\model_adapter\yolo_adapter.py` → `CLASS_MAP` to match the exact class names shown by your model. For example, if your dataset classes are `helmet` and `no-helmet`, add `"no-helmet": "no_helmet"` to the map. The adapter currently handles a single image, not webcam or RTSP streams.

## Existing dashboard workflow
- Dashboard → **Simulate violation** still works.
- Events are saved to SQLite and create alerts.
- Check Violations and Alert Center; resolve/acknowledge items.
- Add sites, cameras and hazard zones under Configuration.
- Reports displays daily totals from SQLite.

## Important scope notes
- Existing simulated workflow remains available.
- The API records a missing-helmet event as a violation and creates an alert; a helmet-present prediction does not.
- The YOLO adapter is a scaffold until model weights are trained and class labels are confirmed.
- Image evidence is not uploaded by this adapter yet; `snapshot_path` is only an optional reference field.
- No live webcam/RTSP processing, authentication, polygon zone drawing, PDF export, or production security yet.
- Flask listens on localhost only.
