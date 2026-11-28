# Raspberry Pi and laptop camera setup

This is a prototype, not a validated safety system. Confirm site PPE rules, model labels and accuracy with the site safety team. A missed detection is not proof of a violation or compliance. In particular, glove detection at CCTV distances may be unreliable.

## Models needed

The repository does not contain trained weights or the chemical dataset images. Put independently trained PPE models at `weights/general.pt`, `weights/construction.pt`, `weights/road.pt`, `weights/chemical.pt`, and `weights/mining.pt` on the Pi. Each site type uses its own file; no generic COCO model is silently substituted. A model can be explicitly reused by copying it to multiple names, but it can only detect classes it was trained on. Site lists are editable in `backend/site_profiles.py`; they are illustrative, not a workplace safety specification.

Model class names must match the names/aliases in `backend/site_profiles.py`. Only explicitly trained negative classes such as `no_helmet` and `no_gloves` create alerts; a positive-only model cannot detect missing PPE just because an object was not detected. Chemical dataset template has positive labels only: it cannot trigger missing-equipment alerts without suitable negative labels and retraining. The model status displays which requested classes are supported.

## Pi backend (64-bit Raspberry Pi OS)

On the Pi, install Python, pip and venv, then:

```bash
cd octavision/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
OCTAVISION_HOST=0.0.0.0 python app.py
```

Find the Pi's address with `hostname -I`. Keep both devices on a trusted private network. The development API has no authentication and must not be exposed to the internet. It stores frames used as alert evidence locally. Setup and performance must be checked on the actual Pi. A Pi 5 needs adequate cooling and a working boot setup.

## Confirmed Working Hardware Integration (Verified)

### Network & Streaming Architecture
- **Raspberry Pi 5**: `172.20.10.7` (hostname: `abhay.local`, user: `abhay`, Debian 13 Trixie ARM64)
- **Laptop Host**: `172.20.10.5`
- **Laptop Camera Source Server**: `http://172.20.10.5:8085/video_feed`
- **Raspberry Pi 5 Relay Stream**: `http://172.20.10.7:8001/video_feed`
- **Raspberry Pi 5 Status Endpoint**: `http://172.20.10.7:8001/`

### Video Pipeline
1. Inbuilt Webcam -> Laptop Camera Server (`8085`)
2. Laptop Camera Server -> Raspberry Pi 5 (`/home/abhay/octavision-camera`)
3. Raspberry Pi 5 -> MJPEG Video Relay (`8001`)
4. OctaVision Backend -> Centralized `PiCameraWorker` (`backend/pi_camera_worker.py`) consuming `http://172.20.10.7:8001/video_feed` with auto-reconnection and single-frame buffer.
5. Live Stream Proxy & AI Model -> Backend feeds decoded Pi 5 frames directly to YOLO detection models with zero browser webcam conflict.
6. Evidence & Alert Dispatch -> Real-time deduplicated violation recording (20s cooldown), watermarked forensic evidence snapshots (`backend/data/snapshots/`), and dashboard alert notifications.

### Centralized Configuration
Configured in `backend/pi_config.py`. Override defaults using environment variables:
- `OCTAVISION_PI_HOST` (default: `172.20.10.7`)
- `OCTAVISION_PI_PORT` (default: `8001`)
- `OCTAVISION_LAPTOP_HOST` (default: `172.20.10.5`)
- `OCTAVISION_LAPTOP_CAM_PORT` (default: `8085`)

## Training

Prepare properly licensed and annotated data for each target site, including images representative of the intended cameras, lighting, distances and negative classes. Split by location/video to avoid leakage. Install `requirements-model.txt` in a training environment and use an Ultralytics training command, e.g. `yolo detect train model=yolov8n.pt data=/path/to/site/data.yaml epochs=80 imgsz=640`. This requires obtaining the base weights and dataset separately. Validate on held-out site footage, review false positives/negatives for each class, then copy the resulting `best.pt` to the corresponding `weights/<site>.pt` on the Pi. Do not treat the example dataset template as a trained model. Pi CPU inference speed is hardware and model dependent; test before relying on it.
