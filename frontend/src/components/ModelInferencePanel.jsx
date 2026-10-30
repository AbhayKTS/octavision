import React, { useEffect, useMemo, useRef, useState } from 'react';

const BOX_COLORS = {
  helmet: '#36b37e',
  vest: '#2f80ed',
  no_helmet: '#eb5757',
  no_vest: '#f2994a',
};

function boxColor(label) {
  return BOX_COLORS[label] || '#9aa4b3';
}

function drawOverlay(canvas, detections, imageSize) {
  const ctx = canvas.getContext('2d');
  const width = canvas.width;
  const height = canvas.height;
  ctx.clearRect(0, 0, width, height);

  if (!imageSize?.width || !imageSize?.height) {
    return;
  }

  const sx = width / imageSize.width;
  const sy = height / imageSize.height;
  ctx.lineWidth = 2;
  ctx.font = '12px DM Sans, sans-serif';

  detections.forEach((det) => {
    const { x1, y1, x2, y2 } = det.bbox;
    const color = boxColor(det.normalized_label);
    const px = x1 * sx;
    const py = y1 * sy;
    const pw = Math.max((x2 - x1) * sx, 2);
    const ph = Math.max((y2 - y1) * sy, 2);
    const title = `${det.normalized_label} ${(det.confidence * 100).toFixed(1)}%`;

    ctx.strokeStyle = color;
    ctx.strokeRect(px, py, pw, ph);

    const textWidth = ctx.measureText(title).width + 10;
    const textY = py > 22 ? py - 22 : py + 4;
    ctx.fillStyle = color;
    ctx.fillRect(px, textY, textWidth, 18);
    ctx.fillStyle = '#ffffff';
    ctx.fillText(title, px + 5, textY + 13);
  });
}

function CountPill({ label, value, tone }) {
  return (
    <div className={`model-pill ${tone}`}>
      <span>{label}</span>
      <b>{value || 0}</b>
    </div>
  );
}

export default function ModelInferencePanel({ apiBase }) {
  const [modelStatus, setModelStatus] = useState(null);
  const [statusError, setStatusError] = useState('');

  const [selectedFile, setSelectedFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState('');
  const [uploadBusy, setUploadBusy] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const [uploadResult, setUploadResult] = useState(null);

  const [liveEnabled, setLiveEnabled] = useState(false);
  const [liveBusy, setLiveBusy] = useState(false);
  const [liveError, setLiveError] = useState('');
  const [liveResult, setLiveResult] = useState(null);
  const [liveRunning, setLiveRunning] = useState(false);

  const videoRef = useRef(null);
  const overlayRef = useRef(null);
  const captureRef = useRef(null);
  const streamRef = useRef(null);
  const loopRef = useRef(false);

  useEffect(() => {
    let alive = true;
    fetch(`${apiBase}/model/status`)
      .then(async (res) => {
        const data = await res.json();
        if (!res.ok) {
          throw new Error(data.error || `HTTP ${res.status}`);
        }
        if (alive) {
          setModelStatus(data);
          setStatusError('');
        }
      })
      .catch((error) => {
        if (alive) {
          setStatusError(error.message);
        }
      });
    return () => {
      alive = false;
    };
  }, [apiBase]);

  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
      stopCamera();
    };
  }, [previewUrl]);

  const uploadCounts = useMemo(() => uploadResult?.counts || {}, [uploadResult]);
  const liveCounts = useMemo(() => liveResult?.counts || {}, [liveResult]);

  async function inferUploadedImage() {
    if (!selectedFile) {
      setUploadError('Choose an image first.');
      return;
    }

    setUploadBusy(true);
    setUploadError('');
    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('confidence', '0.2');
      formData.append('iou', '0.45');

      const response = await fetch(`${apiBase}/model/infer`, {
        method: 'POST',
        body: formData,
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || `HTTP ${response.status}`);
      }
      setUploadResult(data);
    } catch (error) {
      setUploadError(error.message || 'Inference failed.');
    } finally {
      setUploadBusy(false);
    }
  }

  async function startCamera() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      streamRef.current = stream;
      const video = videoRef.current;
      video.srcObject = stream;
      await video.play();
      setLiveEnabled(true);
      setLiveError('');
    } catch (error) {
      setLiveError(error.message || 'Unable to access camera.');
    }
  }

  function stopCamera() {
    loopRef.current = false;
    setLiveRunning(false);
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    const video = videoRef.current;
    if (video) {
      video.srcObject = null;
    }
    const overlay = overlayRef.current;
    if (overlay) {
      const ctx = overlay.getContext('2d');
      ctx.clearRect(0, 0, overlay.width, overlay.height);
    }
    setLiveEnabled(false);
  }

  async function inferLiveFrame() {
    const video = videoRef.current;
    const capture = captureRef.current;
    const overlay = overlayRef.current;
    if (!video || !capture || !overlay || video.videoWidth === 0 || video.videoHeight === 0) {
      return;
    }

    setLiveBusy(true);
    try {
      capture.width = video.videoWidth;
      capture.height = video.videoHeight;
      const captureCtx = capture.getContext('2d');
      captureCtx.drawImage(video, 0, 0, capture.width, capture.height);
      const imageData = capture.toDataURL('image/jpeg', 0.72);

      const response = await fetch(`${apiBase}/model/infer`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image_data: imageData, confidence: 0.2, iou: 0.45 }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || `HTTP ${response.status}`);
      }

      overlay.width = video.videoWidth;
      overlay.height = video.videoHeight;
      drawOverlay(overlay, data.detections || [], data.image || { width: video.videoWidth, height: video.videoHeight });
      setLiveResult(data);
      setLiveError('');
    } catch (error) {
      setLiveError(error.message || 'Live detection failed.');
      loopRef.current = false;
      setLiveRunning(false);
    } finally {
      setLiveBusy(false);
    }
  }

  function runLoop() {
    if (!loopRef.current) {
      return;
    }
    inferLiveFrame().finally(() => {
      if (!loopRef.current) {
        return;
      }
      window.setTimeout(runLoop, 900);
    });
  }

  function startLiveDetection() {
    if (!liveEnabled) {
      return;
    }
    loopRef.current = true;
    setLiveRunning(true);
    runLoop();
  }

  function stopLiveDetection() {
    loopRef.current = false;
    setLiveRunning(false);
  }

  return (
    <div className="model-grid">
      <section className="panel model-panel">
        <div className="panel-title">
          <div>
            <h2>Image PPE detection</h2>
            <p>Upload one image to detect helmet, vest, no-helmet, and no-vest boxes.</p>
          </div>
        </div>

        <div className="model-status-row">
          <span className={modelStatus?.ready ? 'status-ok' : 'status-bad'}>
            {modelStatus?.ready ? 'Model connected' : 'Model not ready'}
          </span>
          <small>{modelStatus?.weights_path || statusError || 'No weights configured yet.'}</small>
        </div>

        <div className="model-actions">
          <input
            type="file"
            accept="image/png,image/jpeg,image/jpg"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (!file) {
                return;
              }
              if (previewUrl) {
                URL.revokeObjectURL(previewUrl);
              }
              setSelectedFile(file);
              setPreviewUrl(URL.createObjectURL(file));
              setUploadResult(null);
              setUploadError('');
            }}
          />
          <button className="btn primary" disabled={!selectedFile || uploadBusy} onClick={inferUploadedImage}>
            {uploadBusy ? 'Detecting…' : 'Run PPE detection'}
          </button>
        </div>

        {uploadError && <div className="model-error">{uploadError}</div>}

        {previewUrl && (
          <div className="upload-preview-wrap">
            <img src={previewUrl} alt="Upload preview" className="upload-preview" />
            {uploadResult?.detections?.map((det, idx) => {
              const w = uploadResult?.image?.width || 1;
              const h = uploadResult?.image?.height || 1;
              const left = (det.bbox.x1 / w) * 100;
              const top = (det.bbox.y1 / h) * 100;
              const width = ((det.bbox.x2 - det.bbox.x1) / w) * 100;
              const height = ((det.bbox.y2 - det.bbox.y1) / h) * 100;
              return (
                <div
                  key={`${det.class_name}-${idx}`}
                  className="upload-box"
                  style={{
                    left: `${left}%`,
                    top: `${top}%`,
                    width: `${width}%`,
                    height: `${height}%`,
                    borderColor: boxColor(det.normalized_label),
                  }}
                >
                  <span style={{ background: boxColor(det.normalized_label) }}>
                    {det.normalized_label} {(det.confidence * 100).toFixed(1)}%
                  </span>
                </div>
              );
            })}
          </div>
        )}

        <div className="model-pill-row">
          <CountPill label="Helmet" value={uploadCounts.helmet} tone="ok" />
          <CountPill label="Vest" value={uploadCounts.vest} tone="info" />
          <CountPill label="No Helmet" value={uploadCounts.no_helmet} tone="bad" />
          <CountPill label="No Vest" value={uploadCounts.no_vest} tone="warn" />
        </div>
      </section>

      <section className="panel model-panel">
        <div className="panel-title">
          <div>
            <h2>Live camera detection</h2>
            <p>Use webcam stream for near real-time PPE bounding boxes.</p>
          </div>
        </div>

        <div className="model-actions">
          {!liveEnabled ? (
            <button className="btn secondary" onClick={startCamera}>Start camera</button>
          ) : (
            <button className="btn secondary" onClick={stopCamera}>Stop camera</button>
          )}

          {liveEnabled && !liveRunning && (
            <button className="btn primary" onClick={startLiveDetection} disabled={liveBusy}>
              Start live detection
            </button>
          )}

          {liveEnabled && liveRunning && (
            <button className="btn secondary" onClick={stopLiveDetection}>
              Pause detection
            </button>
          )}
        </div>

        {liveError && <div className="model-error">{liveError}</div>}

        <div className="live-stage">
          <video ref={videoRef} autoPlay muted playsInline className="live-video" />
          <canvas ref={overlayRef} className="live-overlay" />
          {!liveEnabled && <div className="live-placeholder">Camera is off. Start camera to begin.</div>}
        </div>
        <canvas ref={captureRef} className="hidden-capture" />

        <div className="model-pill-row">
          <CountPill label="Helmet" value={liveCounts.helmet} tone="ok" />
          <CountPill label="Vest" value={liveCounts.vest} tone="info" />
          <CountPill label="No Helmet" value={liveCounts.no_helmet} tone="bad" />
          <CountPill label="No Vest" value={liveCounts.no_vest} tone="warn" />
        </div>
      </section>
    </div>
  );
}
