"""
OctaVision YOLO adapter (starter).

This script runs a YOLO model on one image and forwards detections to the
model-independent Flask API. It expects class names that can be mapped to
"helmet" and "no_helmet". Edit CLASS_MAP to match your dataset's exact names.

Example:
  python yolo_adapter.py --image ..\\sample.jpg --weights ..\\runs\\detect\\train\\weights\\best.pt --site-id 1 --camera-id 1
"""
import argparse
import hashlib
from datetime import datetime, timezone
from pathlib import Path

import requests
from ultralytics import YOLO

# Change the keys to exactly match the names in your trained model's results.
# Values are the normalized API labels.
CLASS_MAP = {
    "helmet": "helmet",
    "with_helmet": "helmet",
    "hardhat": "helmet",
    "no_helmet": "no_helmet",
    "without_helmet": "no_helmet",
    "helmet_missing": "no_helmet",
}

def main():
    parser = argparse.ArgumentParser(description="Send YOLO helmet predictions to OctaVision.")
    parser.add_argument("--image", required=True, help="Path to one image file")
    parser.add_argument("--weights", required=True, help="Path to trained YOLO .pt weights")
    parser.add_argument("--api", default="http://127.0.0.1:5000", help="OctaVision API base URL")
    parser.add_argument("--site-id", type=int, required=True, help="Existing OctaVision site ID")
    parser.add_argument("--camera-id", type=int, required=True, help="Existing camera ID belonging to the site")
    parser.add_argument("--zone-id", type=int, default=None, help="Optional existing zone ID")
    parser.add_argument("--confidence", type=float, default=0.35, help="YOLO confidence threshold (0..1)")
    parser.add_argument("--iou", type=float, default=0.45, help="YOLO NMS IoU threshold")
    args = parser.parse_args()

    image_path = Path(args.image).expanduser().resolve()
    weights_path = Path(args.weights).expanduser().resolve()
    if not image_path.is_file():
        raise SystemExit(f"Image file not found: {image_path}")
    if not weights_path.is_file():
        raise SystemExit(f"Weights file not found: {weights_path}")
    if not 0 <= args.confidence <= 1:
        raise SystemExit("--confidence must be between 0 and 1")

    model = YOLO(str(weights_path))
    results = model.predict(source=str(image_path), conf=args.confidence, iou=args.iou, verbose=False)
    result = results[0]
    names = result.names
    boxes = result.boxes

    if boxes is None or len(boxes) == 0:
        print("No objects detected; nothing sent to OctaVision.")
        return

    api = args.api.rstrip("/")
    sent = 0
    for i, box in enumerate(boxes):
        class_id = int(box.cls.item())
        raw_name = str(names[class_id]).strip().lower().replace(" ", "_")
        mapped = CLASS_MAP.get(raw_name)
        if not mapped:
            print(f"Skipping unknown model class '{raw_name}'. Add it to CLASS_MAP.")
            continue

        confidence = float(box.conf.item())
        # Stable per-image/per-box event key: re-running the same image does not
        # accidentally create repeated no-helmet violations.
        digest = hashlib.sha256(f"{image_path}|{image_path.stat().st_mtime_ns}|{i}|{class_id}".encode()).hexdigest()[:32]
        payload = {
            "site_id": args.site_id,
            "camera_id": args.camera_id,
            "zone_id": args.zone_id,
            "event_key": f"yolo-{digest}",
            "class_name": mapped,
            "confidence": round(confidence, 6),
            "occurred_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source": "adapter",
            # Local file paths are informational only; the API does not upload files yet.
            "snapshot_path": ""
        }
        response = requests.post(f"{api}/api/detections", json=payload, timeout=15)
        try:
            body = response.json()
        except ValueError:
            body = {"response_text": response.text[:500]}
        if not response.ok:
            print(f"API rejected detection ({response.status_code}): {body}")
        else:
            print(f"Sent {raw_name} ({confidence:.1%}) -> {body.get('message', 'accepted')}")
        sent += 1

    if sent == 0:
        print("No recognized helmet classes were sent. Check CLASS_MAP against the dataset class names.")

if __name__ == "__main__":
    main()
