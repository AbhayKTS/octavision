# YOLO adapter (development scaffold)

This adapter is optional and is installed separately from the dashboard API.

## Important
- It requires trained YOLO weights (`best.pt`) and an image. Your model is still being trained, so use this only once weights are ready.
- `CLASS_MAP` must match the exact class names in your dataset/model. Unknown classes are skipped.
- It posts predictions to `POST /api/detections`.
- `helmet` predictions do not create violations; `no_helmet` predictions create a violation and alert.
- The adapter currently processes one image at a time. It does not open a webcam or RTSP stream.
- Image files are not uploaded yet; snapshot evidence support is a separate follow-up.

See the root README for Windows setup and API test instructions.
