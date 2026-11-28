import React, { useEffect, useMemo, useRef, useState } from 'react';

const BOX_COLORS = {
  helmet: '#36b37e',
  vest: '#2f80ed',
  gloves: '#10b981',
  boots: '#8b5cf6',
  goggles: '#06b6d4',
  no_helmet: '#eb5757',
  no_vest: '#f2994a',
  no_gloves: '#ec4899',
  no_boots: '#f43f5e',
  no_goggle: '#e11d48',
  person: '#38bdf8',
};

function boxColor(label) {
  return BOX_COLORS[label] || '#9aa4b3';
}

function drawOverlay(canvas, detections, imageSize) {
  const ctx = canvas.getContext('2d');
  const width = canvas.width;
  const height = canvas.height;
  ctx.clearRect(0, 0, width, height);
  if (!imageSize?.width || !imageSize?.height) return;
  const sx = width / imageSize.width;
  const sy = height / imageSize.height;

  const scale = Math.max(1, width / 800);
  ctx.lineWidth = Math.max(2, Math.round(2 * scale));
  const fontSize = Math.max(11, Math.round(12 * scale));
  ctx.font = `bold ${fontSize}px Inter, DM Sans, sans-serif`;

  detections.forEach((det) => {
    const { x1, y1, x2, y2 } = det.bbox;
    const color = boxColor(det.normalized_label);
    const px = x1 * sx;
    const py = y1 * sy;
    const pw = Math.max((x2 - x1) * sx, 2);
    const ph = Math.max((y2 - y1) * sy, 2);
    const labelText = (det.normalized_label || det.class_name || '').replace('_', ' ');
    const title = `${labelText} ${(det.confidence * 100).toFixed(1)}%`;

    ctx.strokeStyle = color;
    ctx.strokeRect(px, py, pw, ph);

    const textWidth = ctx.measureText(title).width + 8;
    const badgeHeight = fontSize + 6;
    const textY = py > badgeHeight + 2 ? py - badgeHeight : py + 2;

    ctx.fillStyle = color;
    ctx.fillRect(px, textY, textWidth, badgeHeight);
    ctx.fillStyle = '#ffffff';
    ctx.fillText(title, px + 4, textY + fontSize - 1);
  });
}

/* ── SVG Icons ──────────────────────────────────────────────────── */
function HardHatIcon({ size = 18 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 18h20v2H2z" /><path d="M12 2a9 9 0 0 1 9 9H3a9 9 0 0 1 9-9z" />
    </svg>
  );
}
function VestIcon({ size = 18 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 2l4 5v15H4V2z" /><path d="M20 2l-4 5v15h4V2z" /><path d="M8 7l4-5 4 5" />
    </svg>
  );
}
function NoHelmetIcon({ size = 18 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" /><line x1="4.93" y1="4.93" x2="19.07" y2="19.07" />
    </svg>
  );
}
function NoVestIcon({ size = 18 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
      <line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  );
}
function PersonIcon({ size = 18 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </svg>
  );
}
function CameraOffIcon({ size = 22 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" />
      <circle cx="12" cy="13" r="4" />
    </svg>
  );
}
function UploadIcon({ size = 28 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="16 16 12 12 8 16" /><line x1="12" y1="12" x2="12" y2="21" />
      <path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3" />
    </svg>
  );
}
function FileIcon({ size = 12 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" />
      <polyline points="13 2 13 9 20 9" />
    </svg>
  );
}
function AlertTriIcon({ size = 18 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
      <line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  );
}
function XIcon({ size = 16 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
      <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}
function ClockIcon({ size = 12 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" />
    </svg>
  );
}
function CamIcon({ size = 12 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M23 7l-7 5 7 5V7z" /><rect x="1" y="5" width="15" height="14" rx="2" />
    </svg>
  );
}

/* ── PPE Icon Tile ──────────────────────────────────────────────── */
function PpeTile({ label, value, tone, Icon }) {
  return (
    <div className={`ppe-tile ${tone}`}>
      <div className="ppe-tile-dot" />
      <div className="ppe-tile-icon"><Icon size={16} /></div>
      <div className="ppe-tile-label">{label}</div>
      <div className="ppe-tile-count">{value ?? '—'}</div>
    </div>
  );
}

/* ── Radar Placeholder ──────────────────────────────────────────── */
function RadarPlaceholder({ isRpi, piOnline }) {
  return (
    <div className="radar-placeholder">
      <div className="radar-rings">
        <div className="radar-ring" /><div className="radar-ring" /><div className="radar-ring" />
        <div className="radar-icon"><CamIcon size={20} /></div>
      </div>
      <p>
        <strong>{isRpi ? 'Raspberry Pi 5 Relay Stream' : 'Camera is offline.'}</strong><br />
        {isRpi
          ? (piOnline ? 'Physical Pi 5 relay online (172.20.10.7:8001). Press "Start camera" to view feed.' : 'Connecting to Raspberry Pi 5 (172.20.10.7:8001)...')
          : 'Press "Start camera" to begin stream.'}
      </p>
    </div>
  );
}

/* ── Violation Banner ───────────────────────────────────────────── */
function ViolationBanner({ violation, onClose }) {
  const ppeLabel = violation.ppe_type === 'helmet' ? 'Helmet Not Detected' : 'Safety Vest Missing';
  const time = new Date(violation.occurred_at).toLocaleTimeString();
  const camName = violation.camera_name || `Camera #${violation.camera_id}`;
  return (
    <div className="violation-banner">
      <div className="violation-banner-icon"><AlertTriIcon size={18} /></div>
      <div className="violation-banner-body">
        <div className="violation-banner-title">LIVE MONITORING · VIOLATION DETECTED</div>
        <div className="violation-banner-type">PPE VIOLATION — {ppeLabel}</div>
        <div className="violation-banner-meta">
          <span><CamIcon /> {camName} · Live Detection</span>
          <span><ClockIcon /> Violation time {time}</span>
          <span className="violation-banner-status">Unresolved</span>
        </div>
      </div>
      <button className="violation-banner-close" onClick={onClose} title="Dismiss"><XIcon size={14} /></button>
    </div>
  );
}

/* ── Main Component ─────────────────────────────────────────────── */
export default function ModelInferencePanel({
  apiBase,
  sites = [],
  cams = [],
  zones = [],
  onViolationDetected,
}) {
  const [selectedSiteId, setSelectedSiteId] = useState('');
  const siteType = sites.find((site) => String(site.id) === String(selectedSiteId))?.site_type || 'construction';
  const [selectedCamId, setSelectedCamId] = useState('');

  const [modelStatus, setModelStatus] = useState(null);
  const [statusError, setStatusError] = useState('');

  const [selectedFile, setSelectedFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState('');
  const [uploadBusy, setUploadBusy] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const [uploadResult, setUploadResult] = useState(null);
  const [dragOver, setDragOver] = useState(false);

  const [liveEnabled, setLiveEnabled] = useState(false);
  const [liveBusy, setLiveBusy] = useState(false);
  const [liveError, setLiveError] = useState('');
  const [liveResult, setLiveResult] = useState(null);
  const [liveRunning, setLiveRunning] = useState(false);

  // Violation banner state
  const [liveViolation, setLiveViolation] = useState(null);
  const bannerTimerRef = useRef(null);

  const fileInputRef = useRef(null);
  const videoRef = useRef(null);
  const rpiImgRef = useRef(null);
  const overlayRef = useRef(null);
  const captureRef = useRef(null);
  const streamRef = useRef(null);
  const loopRef = useRef(false);

  // Raspberry Pi status
  const [piStatus, setPiStatus] = useState({ online: false, fps: 0, resolution: null });
  const activeSiteCams = cams.filter((c) => String(c.site_id) === String(selectedSiteId));
  const activeCam = cams.find((c) => String(c.id) === String(selectedCamId));
  const isRpi = activeCam?.source_type === 'rpi';

  // Poll Pi status when an RPi camera is selected
  useEffect(() => {
    let alive = true;
    if (!isRpi) return;

    function checkStatus() {
      fetch(`${apiBase}/cameras/pi-status`)
        .then((r) => r.json())
        .then((data) => {
          if (alive && data.ok) {
            setPiStatus({
              online: Boolean(data.online),
              fps: data.worker?.fps || 0,
              resolution: data.worker?.resolution || null,
            });
          }
        })
        .catch(() => {
          if (alive) setPiStatus((prev) => ({ ...prev, online: false }));
        });
    }

    checkStatus();
    const interval = setInterval(checkStatus, 4000);
    return () => {
      alive = false;
      clearInterval(interval);
    };
  }, [apiBase, isRpi, selectedCamId]);

  // Sync selected site and camera from props
  useEffect(() => {
    if (!selectedSiteId && sites.length > 0) {
      setSelectedSiteId(String(sites[0].id));
    }
  }, [sites, selectedSiteId]);

  useEffect(() => {
    const siteCams = cams.filter((c) => String(c.site_id) === String(selectedSiteId));
    if (siteCams.length > 0) {
      if (!selectedCamId || !siteCams.some((c) => String(c.id) === String(selectedCamId))) {
        setSelectedCamId(String(siteCams[0].id));
      }
    } else {
      setSelectedCamId('');
    }
  }, [cams, selectedSiteId, selectedCamId]);

  // Automatically reset stream if camera changes
  const prevCamIdRef = useRef(selectedCamId);
  useEffect(() => {
    if (prevCamIdRef.current && prevCamIdRef.current !== selectedCamId) {
      stopCamera();
    }
    prevCamIdRef.current = selectedCamId;
  }, [selectedCamId]);

  /* fetch model status */
  useEffect(() => {
    let alive = true;
    fetch(`${apiBase}/model/status?site_type=${encodeURIComponent(siteType)}`)
      .then(async (res) => {
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
        if (alive) {
          setModelStatus(data);
          setStatusError('');
        }
      })
      .catch((err) => {
        if (alive) setStatusError(err.message);
      });
    return () => {
      alive = false;
    };
  }, [apiBase, siteType]);

  useEffect(() => () => { if (previewUrl) URL.revokeObjectURL(previewUrl); }, [previewUrl]);
  useEffect(() => () => {
    loopRef.current = false;
    if (streamRef.current) streamRef.current.getTracks().forEach((track) => track.stop());
    if (bannerTimerRef.current) clearTimeout(bannerTimerRef.current);
  }, []);

  const uploadCounts = useMemo(() => uploadResult?.counts || {}, [uploadResult]);
  const liveCounts = useMemo(() => liveResult?.counts || {}, [liveResult]);

  /* ── show violation banner with auto-dismiss ── */
  function showViolation(v) {
    setLiveViolation(v);
    if (bannerTimerRef.current) clearTimeout(bannerTimerRef.current);
    bannerTimerRef.current = setTimeout(() => setLiveViolation(null), 9000);
  }

  /* ── file helpers ── */
  function pickFile(file) {
    if (!file) return;
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setSelectedFile(file);
    setPreviewUrl(URL.createObjectURL(file));
    setUploadResult(null);
    setUploadError('');
  }

  function handleDrop(e) {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file && file.type.startsWith('image/')) pickFile(file);
  }

  /* ── image inference ── */
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
      formData.append('site_type', siteType);
      formData.append('confidence', '0.25');
      formData.append('iou', '0.45');
      const response = await fetch(`${apiBase}/model/infer`, { method: 'POST', body: formData });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
      setUploadResult(data);
    } catch (err) {
      setUploadError(err.message || 'Inference failed.');
    } finally {
      setUploadBusy(false);
    }
  }

  /* ── camera stream controls ── */
  async function startCamera() {
    if (isRpi) {
      // Connect to Raspberry Pi 5 MJPEG relay stream - no browser webcam access needed
      setLiveEnabled(true);
      setLiveError('');
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      streamRef.current = stream;
      videoRef.current.srcObject = stream;
      await videoRef.current.play();
      setLiveEnabled(true);
      setLiveError('');
    } catch (err) {
      setLiveError(err.message || 'Unable to access camera.');
    }
  }

  function stopCamera() {
    loopRef.current = false;
    setLiveRunning(false);
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    if (videoRef.current) videoRef.current.srcObject = null;
    if (overlayRef.current) {
      overlayRef.current.getContext('2d').clearRect(0, 0, overlayRef.current.width, overlayRef.current.height);
    }
    setLiveEnabled(false);
  }

  /* ── send violation event to backend ── */
  async function reportViolation(detections, imageData) {
    const sId = selectedSiteId || (sites[0]?.id ? String(sites[0].id) : null);
    const cId = selectedCamId || null;
    if (!sId || !cId) throw new Error('Select a site and a camera belonging to it before starting detection.');

    try {
      const response = await fetch(`${apiBase}/violations/from-inference`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          site_id: Number(sId),
          camera_id: Number(cId),
          detections,
          image_data: imageData,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
      if (data.created && data.created.length > 0) {
        const v = data.created[0].violation;
        showViolation(v);
        if (onViolationDetected) {
          onViolationDetected(v);
        }
      }
    } catch (err) {
      throw new Error(`Could not save violation: ${err.message}`);
    }
  }

  /* ── live frame inference loop ── */
  async function inferLiveFrame() {
    const overlay = overlayRef.current;
    if (!overlay) return;

    setLiveBusy(true);
    try {
      let data;
      if (isRpi) {
        // Stream directly from Raspberry Pi 5 - backend processes latest frame with zero lag
        const response = await fetch(`${apiBase}/model/infer`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            source: 'rpi',
            camera_id: Number(selectedCamId),
            site_type: siteType,
            confidence: 0.25,
            iou: 0.45,
          }),
        });
        data = await response.json();
        if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);

        const imgWidth = data.image?.width || 640;
        const imgHeight = data.image?.height || 480;
        overlay.width = imgWidth;
        overlay.height = imgHeight;
        drawOverlay(overlay, data.detections || [], data.image || { width: imgWidth, height: imgHeight });
      } else {
        // Local webcam capture
        const video = videoRef.current;
        const capture = captureRef.current;
        if (!video || !capture || video.videoWidth === 0 || video.videoHeight === 0) return;

        capture.width = video.videoWidth;
        capture.height = video.videoHeight;
        capture.getContext('2d').drawImage(video, 0, 0, capture.width, capture.height);
        const imageData = capture.toDataURL('image/jpeg', 0.75);

        const response = await fetch(`${apiBase}/model/infer`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            image_data: imageData,
            camera_id: Number(selectedCamId) || null,
            site_type: siteType,
            confidence: 0.25,
            iou: 0.45,
          }),
        });
        data = await response.json();
        if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);

        overlay.width = video.videoWidth;
        overlay.height = video.videoHeight;
        drawOverlay(overlay, data.detections || [], data.image || { width: video.videoWidth, height: video.videoHeight });

        if (data.has_violation && data.detections && (!data.recorded_violations || data.recorded_violations.length === 0)) {
          await reportViolation(data.detections, imageData);
        }
      }

      setLiveResult(data);
      setLiveError('');

      // If violation was recorded by backend, display banner and trigger alert sound
      if (data.recorded_violations && data.recorded_violations.length > 0) {
        const v = data.recorded_violations[0].violation;
        if (v) {
          showViolation(v);
          if (onViolationDetected) onViolationDetected(v);
        }
      }
    } catch (err) {
      setLiveError(err.message || 'Live detection failed.');
      loopRef.current = false;
      setLiveRunning(false);
    } finally {
      setLiveBusy(false);
    }
  }

  function runLoop() {
    if (!loopRef.current) return;
    inferLiveFrame().finally(() => {
      if (loopRef.current) window.setTimeout(runLoop, 850);
    });
  }

  function startLiveDetection() {
    if (!liveEnabled) return;
    if (!selectedSiteId || !selectedCamId) { setLiveError('Select a site and its camera before starting detection.'); return; }
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
      {/* ── Image PPE Detection ── */}
      <section className="panel model-panel">
        <div className="panel-title">
          <div>
            <h2>Static image PPE analysis</h2>
            <p>Detect PPE classes supported by the selected site model. An unseen item is not automatically a violation.</p>
          </div>
        </div>

        <div className="model-actions">
          <label className="field model-site-field">
            <span>Site model</span>
            <strong>{siteType} (from selected site)</strong>
          </label>
        </div>

        <div className={`model-status-row${statusError ? ' err' : ''}`}>
          <span className={modelStatus?.ready ? 'status-ok' : 'status-bad'}>
            {modelStatus?.ready ? 'Model connected' : 'Model not ready'}
          </span>
          <small>{modelStatus?.error || modelStatus?.weights_path || statusError || 'No weights configured yet.'}</small>
          {modelStatus?.capabilities && <small>Model classes: {Object.entries(modelStatus.capabilities).map(([ppe, support]) => `${ppe}: ${support.present ? 'present' : 'not supported'} / ${support.missing ? 'missing supported' : 'missing not supported'}`).join(' · ')}</small>}
        </div>

        <div
          className={`drag-zone${dragOver ? ' over' : ''}`}
          onClick={() => fileInputRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
        >
          <UploadIcon size={28} />
          <p>Drag-drop or click to pick an image</p>
          <small>PNG, JPG — max recommended 4 MB</small>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/png,image/jpeg,image/jpg"
            onClick={(e) => e.stopPropagation()}
            onChange={(e) => pickFile(e.target.files?.[0])}
          />
        </div>

        {selectedFile && (
          <div style={{ marginBottom: 10 }}>
            <span className="drag-filename">
              <FileIcon /> {selectedFile.name}
            </span>
          </div>
        )}

        <div className="model-actions">
          <button className="btn primary" disabled={!selectedFile || uploadBusy} onClick={inferUploadedImage}>
            {uploadBusy ? 'Detecting…' : 'Run PPE detection'}
          </button>
        </div>

        {uploadError && <div className="model-error">{uploadError}</div>}

        {previewUrl && (
          <div className="upload-stage">
            <div className="upload-media-wrap">
              <img src={previewUrl} alt="Upload preview" className="upload-preview" />
              {uploadResult?.detections?.map((det, idx) => {
                const w = uploadResult?.image?.width || 1;
                const h = uploadResult?.image?.height || 1;
                const topPct = (det.bbox.y1 / h) * 100;
                const isNearTop = topPct < 7;
                const label = (det.normalized_label || det.class_name || '').replace('_', ' ');
                return (
                  <div
                    key={`${det.class_name}-${idx}`}
                    className="upload-box"
                    style={{
                      left: `${(det.bbox.x1 / w) * 100}%`,
                      top: `${topPct}%`,
                      width: `${((det.bbox.x2 - det.bbox.x1) / w) * 100}%`,
                      height: `${((det.bbox.y2 - det.bbox.y1) / h) * 100}%`,
                      borderColor: boxColor(det.normalized_label),
                    }}
                  >
                    <span
                      style={{
                        background: boxColor(det.normalized_label),
                        top: isNearTop ? '2px' : '-22px',
                      }}
                    >
                      {label} {(det.confidence * 100).toFixed(1)}%
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        <div className="ppe-tile-grid">
          <PpeTile label="Persons" value={uploadCounts.person} tone="info" Icon={PersonIcon} />
          {(modelStatus?.required_ppe || []).map((ppe) => (
            <div key={ppe}>
              <PpeTile label={ppe.replaceAll('_', ' ')} value={modelStatus?.capabilities?.[ppe]?.present ? uploadCounts[ppe] : '—'} tone="ok" Icon={HardHatIcon} />
              <PpeTile label={`No ${ppe.replaceAll('_', ' ')}`} value={modelStatus?.capabilities?.[ppe]?.missing ? uploadCounts[`no_${ppe}`] : '—'} tone="bad" Icon={NoHelmetIcon} />
            </div>
          ))}
        </div>
      </section>

      {/* ── Live Camera Detection ── */}
      <section className="panel model-panel">
        <div className="panel-title">
          <div>
            <h2>Live camera detection & evidence capture</h2>
            <p>Continuous AI monitoring with automatic screenshot capture and duplicate suppression.</p>
          </div>
        </div>

        {/* Camera and site picker */}
        <div className="form-grid" style={{ marginBottom: 12 }}>
          <label className="field">
            <span>Worksite</span>
            <select disabled={liveRunning} value={selectedSiteId} onChange={(e) => setSelectedSiteId(e.target.value)}>
              {sites.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Camera source</span>
            <select disabled={liveRunning} value={selectedCamId} onChange={(e) => setSelectedCamId(e.target.value)}>
              {activeSiteCams.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} {c.source_type === 'rpi' ? '— (Raspberry Pi 5)' : ''}
                </option>
              ))}
            </select>
          </label>
        </div>

        {/* Raspberry Pi Hardware Status Bar */}
        {isRpi && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '7px 12px', background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 8, marginBottom: 14, fontSize: 11 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: piStatus.online ? '#10b981' : '#f59e0b', display: 'inline-block' }} />
              <b style={{ color: '#1e293b' }}>Hardware Source:</b>
              <span style={{ color: piStatus.online ? '#059669' : '#d97706', fontWeight: 700 }}>
                {piStatus.online ? `Raspberry Pi 5 Relay Online · ${piStatus.fps || '25+'} FPS` : 'Raspberry Pi 5 Connecting…'}
              </span>
            </div>
            <small style={{ color: '#64748b' }}>{activeCam?.source_url || 'http://172.20.10.7:8001/video_feed'}</small>
          </div>
        )}

        <div className="model-actions">
          {!liveEnabled ? (
            <button className="btn primary" onClick={startCamera}>
              <CamIcon size={14} /> {isRpi ? 'Start Pi 5 stream' : 'Start camera'}
            </button>
          ) : (
            <button className="btn secondary" onClick={stopCamera}>
              {isRpi ? 'Stop Pi 5 stream' : 'Stop camera'}
            </button>
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
          <div className="live-media-wrap" style={{ display: liveEnabled ? 'inline-block' : 'none' }}>
            {isRpi ? (
              <img
                ref={rpiImgRef}
                src={liveEnabled ? `${apiBase}/cameras/pi-stream` : ''}
                alt="Raspberry Pi 5 Live Stream"
                className="live-video"
                onLoad={(e) => {
                  if (overlayRef.current) {
                    overlayRef.current.width = e.target.naturalWidth || 640;
                    overlayRef.current.height = e.target.naturalHeight || 480;
                  }
                }}
              />
            ) : (
              <video ref={videoRef} autoPlay muted playsInline className="live-video" />
            )}
            <canvas ref={overlayRef} className="live-overlay" />
          </div>
          {!liveEnabled && <RadarPlaceholder isRpi={isRpi} piOnline={piStatus.online} />}
          {liveViolation && <ViolationBanner violation={liveViolation} onClose={() => setLiveViolation(null)} />}
        </div>
        <canvas ref={captureRef} className="hidden-capture" />

        <div className="ppe-tile-grid">
          <PpeTile label="Persons" value={liveCounts.person} tone="info" Icon={PersonIcon} />
          {(modelStatus?.required_ppe || []).map((ppe) => (
            <div key={ppe}>
              <PpeTile label={ppe.replaceAll('_', ' ')} value={modelStatus?.capabilities?.[ppe]?.present ? liveCounts[ppe] : '—'} tone="ok" Icon={HardHatIcon} />
              <PpeTile label={`No ${ppe.replaceAll('_', ' ')}`} value={modelStatus?.capabilities?.[ppe]?.missing ? liveCounts[`no_${ppe}`] : '—'} tone="bad" Icon={NoHelmetIcon} />
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
