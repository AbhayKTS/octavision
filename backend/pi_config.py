"""
Centralized Hardware & Raspberry Pi Configuration for OctaVision.

Centralizes network endpoints and camera settings for:
- Raspberry Pi 5 (relay server)
- Laptop camera server
Avoids hardcoding IP addresses across multiple files.
"""

import os
import urllib.request
import json
import logging

logger = logging.getLogger("octavision.pi_config")

# Network configuration with environment variable overrides
PI_HOST = os.environ.get("OCTAVISION_PI_HOST", "172.20.10.7").strip()
PI_PORT = int(os.environ.get("OCTAVISION_PI_PORT", "8001"))
LAPTOP_HOST = os.environ.get("OCTAVISION_LAPTOP_HOST", "172.20.10.5").strip()
LAPTOP_CAM_PORT = int(os.environ.get("OCTAVISION_LAPTOP_CAM_PORT", "8085"))

# Derived stream endpoints
PI_STREAM_URL = f"http://{PI_HOST}:{PI_PORT}/video_feed"
PI_STATUS_URL = f"http://{PI_HOST}:{PI_PORT}/"
LAPTOP_STREAM_URL = f"http://{LAPTOP_HOST}:{LAPTOP_CAM_PORT}/video_feed"


def get_pi_config() -> dict:
    """Return the complete centralized configuration dictionary."""
    return {
        "pi_host": PI_HOST,
        "pi_port": PI_PORT,
        "pi_stream_url": PI_STREAM_URL,
        "pi_status_url": PI_STATUS_URL,
        "laptop_host": LAPTOP_HOST,
        "laptop_cam_port": LAPTOP_CAM_PORT,
        "laptop_stream_url": LAPTOP_STREAM_URL,
    }


def check_pi_status(timeout: float = 2.5) -> dict:
    """
    Query the Raspberry Pi 5 health/status endpoint.
    Returns status dict with 'online' flag, response body, or error.
    """
    try:
        req = urllib.request.Request(PI_STATUS_URL, headers={"User-Agent": "OctaVision-Server"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                body = resp.read().decode("utf-8", errors="replace")
                try:
                    data = json.loads(body)
                except Exception:
                    data = {"raw": body}
                return {
                    "online": True,
                    "status_code": resp.status,
                    "device": data.get("device", "Raspberry Pi 5"),
                    "camera": data.get("camera", "Online"),
                    "project": data.get("project", "OctaVision"),
                    "url": PI_STATUS_URL,
                    "error": None,
                }
    except Exception as exc:
        return {
            "online": False,
            "status_code": None,
            "device": "Raspberry Pi 5",
            "camera": "Offline",
            "project": "OctaVision",
            "url": PI_STATUS_URL,
            "error": str(exc),
        }
