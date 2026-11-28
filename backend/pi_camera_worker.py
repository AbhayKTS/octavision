"""
Raspberry Pi 5 MJPEG Stream Consumer & Camera Worker.

Features:
- Singleton background capture worker (prevents duplicate capture threads).
- Connects to the Raspberry Pi 5 MJPEG stream (http://172.20.10.7:8001/video_feed).
- Automatic reconnection with backoff if network drops or Pi restarts.
- Zero-latency buffer management (always retains only the most recent frame).
- Provides decoded frames to AI models without re-encoding.
- Serves proxied MJPEG stream to web clients with clean multipart boundaries.
"""

import cv2
import time
import threading
import logging
from typing import Tuple, Optional
import numpy as np
from pi_config import PI_STREAM_URL, check_pi_status

logger = logging.getLogger("octavision.pi_worker")


class PiCameraWorker:
    _instance: Optional["PiCameraWorker"] = None
    _singleton_lock = threading.Lock()

    @classmethod
    def get_instance(cls, stream_url: Optional[str] = None) -> "PiCameraWorker":
        """Get or create the singleton PiCameraWorker instance."""
        with cls._singleton_lock:
            if cls._instance is None:
                cls._instance = cls(stream_url or PI_STREAM_URL)
            elif stream_url and stream_url != cls._instance.stream_url:
                cls._instance.update_stream_url(stream_url)
            return cls._instance

    def __init__(self, stream_url: str = PI_STREAM_URL):
        self.stream_url = stream_url
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None

        # State tracking
        self._latest_frame: Optional[np.ndarray] = None
        self._latest_jpeg: Optional[bytes] = None
        self._last_frame_time: float = 0.0
        self._is_online: bool = False
        self._error_msg: str = ""
        self._frame_count: int = 0
        self._fps: float = 0.0
        self._last_fps_calc: float = time.time()
        self._frames_since_calc: int = 0

        # Start the background capture thread
        self.start()

    def update_stream_url(self, new_url: str):
        with self._lock:
            if self.stream_url != new_url:
                logger.info(f"Updating Pi stream URL from {self.stream_url} to {new_url}")
                self.stream_url = new_url
                self._is_online = False

    def start(self):
        """Start the background stream capture thread if not already running."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(target=self._capture_loop, name="PiCameraWorkerThread", daemon=True)
            self._thread.start()
            logger.info(f"PiCameraWorker started capturing from: {self.stream_url}")

    def stop(self):
        """Stop the background stream capture worker."""
        with self._lock:
            self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        logger.info("PiCameraWorker stopped.")

    def _capture_loop(self):
        """Continuously capture frames from the Pi stream with auto-reconnection."""
        retry_delay = 1.0
        max_retry_delay = 10.0

        while self._running:
            cap = None
            try:
                logger.info(f"Opening stream connection to: {self.stream_url}")
                cap = cv2.VideoCapture(self.stream_url)
                
                # Set smaller internal buffer to minimize lag
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

                if not cap.isOpened():
                    raise RuntimeError(f"Unable to open video stream at {self.stream_url}")

                logger.info("Connected to Raspberry Pi 5 video stream.")
                retry_delay = 1.0  # Reset delay on success

                while self._running:
                    ret, frame = cap.read()
                    if not ret or frame is None:
                        logger.warning("Frame read returned False. Stream may have interrupted.")
                        break

                    now = time.time()
                    with self._lock:
                        self._latest_frame = frame
                        self._latest_jpeg = None  # Invalidate cached JPEG
                        self._last_frame_time = now
                        self._is_online = True
                        self._error_msg = ""
                        self._frame_count += 1
                        self._frames_since_calc += 1

                        # FPS calculation every 1 second
                        if now - self._last_fps_calc >= 1.0:
                            self._fps = round(self._frames_since_calc / (now - self._last_fps_calc), 1)
                            self._last_fps_calc = now
                            self._frames_since_calc = 0

                    # Yield CPU briefly to prevent thread starvation
                    time.sleep(0.005)

            except Exception as exc:
                with self._lock:
                    self._is_online = False
                    self._error_msg = str(exc)
                logger.warning(f"Error in Pi capture worker: {exc}. Reconnecting in {retry_delay:.1f}s...")
            finally:
                if cap is not None:
                    cap.release()

            if self._running:
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 1.5, max_retry_delay)

    def get_status(self) -> dict:
        """Return real-time stream metrics and health status."""
        with self._lock:
            now = time.time()
            stale = (now - self._last_frame_time) > 4.0 if self._last_frame_time > 0 else True
            online = self._is_online and not stale
            resolution = None
            if self._latest_frame is not None:
                h, w = self._latest_frame.shape[:2]
                resolution = f"{w}x{h}"

            return {
                "online": online,
                "stream_url": self.stream_url,
                "fps": self._fps if online else 0.0,
                "frame_count": self._frame_count,
                "last_frame_age_secs": round(now - self._last_frame_time, 2) if self._last_frame_time else None,
                "resolution": resolution,
                "error": self._error_msg if not online else None,
            }

    def get_latest_frame(self) -> Tuple[bool, Optional[np.ndarray], float]:
        """
        Return the most recent decoded video frame as a numpy array.
        Returns: (success: bool, frame: np.ndarray | None, timestamp: float)
        """
        with self._lock:
            if self._latest_frame is not None and (time.time() - self._last_frame_time) < 4.0:
                return True, self._latest_frame.copy(), self._last_frame_time
            return False, None, 0.0

    def get_latest_jpeg(self) -> Tuple[bool, Optional[bytes]]:
        """Return the most recent frame encoded as JPEG bytes."""
        with self._lock:
            if self._latest_frame is None or (time.time() - self._last_frame_time) > 4.0:
                return False, None
            if self._latest_jpeg is None:
                ret, buf = cv2.imencode(".jpg", self._latest_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                if ret:
                    self._latest_jpeg = buf.tobytes()
            return True, self._latest_jpeg

    def generate_mjpeg_stream(self):
        """
        Generator yielding MJPEG multipart chunks for live HTTP streaming to browsers.
        Maintains connection and yields fallback frames if stream is temporarily offline.
        """
        boundary = "frame"
        while True:
            success, jpeg_bytes = self.get_latest_jpeg()
            if success and jpeg_bytes:
                yield (
                    b"--" + boundary.encode("utf-8") + b"\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + jpeg_bytes + b"\r\n"
                )
                time.sleep(0.04)  # ~25 FPS
            else:
                # If offline, generate a clean placeholder frame
                placeholder = np.zeros((480, 640, 3), dtype=np.uint8)
                placeholder[:] = (20, 24, 33)  # Dark slate background
                cv2.putText(
                    placeholder,
                    "RASPBERRY PI 5 STREAM OFFLINE",
                    (65, 220),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (70, 90, 220),
                    2,
                    cv2.LINE_AA,
                )
                cv2.putText(
                    placeholder,
                    f"Reconnecting to {self.stream_url}...",
                    (110, 265),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    (160, 175, 200),
                    1,
                    cv2.LINE_AA,
                )
                _, p_buf = cv2.imencode(".jpg", placeholder)
                yield (
                    b"--" + boundary.encode("utf-8") + b"\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + p_buf.tobytes() + b"\r\n"
                )
                time.sleep(0.5)
