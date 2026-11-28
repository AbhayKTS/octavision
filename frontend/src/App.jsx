import React, { useEffect, useState, useCallback, useRef, useMemo } from 'react';
import {
  Activity,
  AlertTriangle,
  Bell,
  BellOff,
  Check,
  CheckCircle2,
  ChevronDown,
  ClipboardList,
  Clock3,
  ExternalLink,
  Eye,
  Factory,
  FileText,
  HardHat,
  Info,
  LayoutDashboard,
  MapPin,
  Plus,
  RefreshCw,
  Search,
  Settings,
  ShieldCheck,
  Siren,
  SlidersHorizontal,
  Video,
  Volume2,
  VolumeX,
  X,
  Zap,
} from 'lucide-react';
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import ModelInferencePanel from './components/ModelInferencePanel';

const API_BASE = (import.meta.env?.VITE_API_BASE || 'http://127.0.0.1:5000').replace(/\/$/, '');
const API = `${API_BASE}/api`;
const TYPES = [
  ['construction', 'Construction Site'],
  ['road', 'Road Construction'],
  ['chemical', 'Chemical Factory'],
  ['mining', 'Mining & Quarry'],
  ['general', 'General'],
];

async function api(p, o = {}) {
  const r = await fetch(API + p, {
    headers: { 'Content-Type': 'application/json' },
    ...o,
  });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw Error(d.error || `HTTP ${r.status}`);
  return d;
}

const fmt = (x) => (x ? new Date(x).toLocaleString() : '—');

function timeAgo(dateStr) {
  if (!dateStr) return '—';
  const diffSec = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000);
  if (diffSec < 15) return 'Now';
  if (diffSec < 60) return `${diffSec}s ago`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin} min ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr} hr ago`;
  return new Date(dateStr).toLocaleDateString();
}

function playSafetyAlarm() {
  try {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return;
    const ctx = new AudioCtx();
    if (ctx.state === 'suspended') {
      ctx.resume();
    }
    const t = ctx.currentTime;

    // First tone (880 Hz)
    const osc1 = ctx.createOscillator();
    const gain1 = ctx.createGain();
    osc1.type = 'triangle';
    osc1.frequency.setValueAtTime(880, t);
    gain1.gain.setValueAtTime(0.001, t);
    gain1.gain.exponentialRampToValueAtTime(0.2, t + 0.02);
    gain1.gain.exponentialRampToValueAtTime(0.001, t + 0.16);
    osc1.connect(gain1);
    gain1.connect(ctx.destination);
    osc1.start(t);
    osc1.stop(t + 0.18);

    // Second warning tone (660 Hz)
    const osc2 = ctx.createOscillator();
    const gain2 = ctx.createGain();
    osc2.type = 'triangle';
    osc2.frequency.setValueAtTime(660, t + 0.18);
    gain2.gain.setValueAtTime(0.001, t + 0.18);
    gain2.gain.exponentialRampToValueAtTime(0.25, t + 0.20);
    gain2.gain.exponentialRampToValueAtTime(0.001, t + 0.38);
    osc2.connect(gain2);
    gain2.connect(ctx.destination);
    osc2.start(t + 0.18);
    osc2.stop(t + 0.40);

    setTimeout(() => {
      ctx.close().catch(() => {});
    }, 500);
  } catch (err) {
    console.warn('Audio play error:', err);
  }
}

export default function App() {
  const [page, setPage] = useState('Overview');
  const [dash, setDash] = useState({ stats: {}, recent_violations: [], daily_counts: [] });
  const [sites, setSites] = useState([]);
  const [cams, setCams] = useState([]);
  const [zones, setZones] = useState([]);
  const [viol, setViol] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [models, setModels] = useState([]);
  const [report, setReport] = useState(null);

  const [error, setError] = useState('');
  const [toast, setToast] = useState('');
  const [busy, setBusy] = useState(false);

  // Search and filters for violations
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('All');
  const [ppeFilter, setPpeFilter] = useState('All');

  // Selected violation for Slide-Over Drawer
  const [selectedViolation, setSelectedViolation] = useState(null);

  // Sound alert state
  const [soundEnabled, setSoundEnabled] = useState(true);

  // Config forms
  const [siteForm, setSiteForm] = useState({ name: '', site_type: 'construction', location: '' });
  const [camForm, setCamForm] = useState({ site_id: '', name: '', source_type: 'simulated', source_url: '' });
  const [zoneForm, setZoneForm] = useState({ site_id: '', camera_id: '', name: '', required_ppe: 'helmet' });
  const [form, setForm] = useState('');

  const lastAlertId = useRef(null);
  const soundRef = useRef(true);

  useEffect(() => {
    soundRef.current = soundEnabled;
  }, [soundEnabled]);

  const refresh = useCallback(async () => {
    try {
      const [d, s, c, z, v, a, m] = await Promise.all(
        ['/dashboard', '/sites', '/cameras', '/zones', '/violations', '/alerts', '/models'].map(api)
      );
      setDash(d);
      setSites(s);
      setCams(c);
      setZones(z);
      setViol(v);
      setAlerts(a);
      setModels(m);

      if (!camForm.site_id && s.length) setCamForm((f) => ({ ...f, site_id: String(s[0].id) }));
      if (!zoneForm.site_id && s.length) setZoneForm((f) => ({ ...f, site_id: String(s[0].id) }));

      // Sound notification for new alert
      if (a.length && lastAlertId.current !== null && a[0].id > lastAlertId.current) {
        setToast(a[0].message);
        if (soundRef.current) {
          playSafetyAlarm();
        }
      }
      lastAlertId.current = Math.max(lastAlertId.current ?? 0, a[0]?.id ?? 0);
      setError('');
    } catch (e) {
      setError(`Backend connection failed: ${e.message}. Start Flask in the backend.`);
    }
  }, [camForm.site_id, zoneForm.site_id]);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 5000);
    return () => clearInterval(t);
  }, [refresh]);

  useEffect(() => {
    if (toast) {
      const t = setTimeout(() => setToast(''), 4500);
      return () => clearTimeout(t);
    }
  }, [toast]);

  const act = async (fn, msg) => {
    setBusy(true);
    setError('');
    try {
      await fn();
      await refresh();
      if (msg) setToast(msg);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const simulate = () =>
    act(
      () => api('/demo/simulate-violation', { method: 'POST', body: JSON.stringify({ site_id: sites[0]?.id, ppe_type: 'helmet' }) }),
      'Simulated violation saved; alert created.'
    );

  const addSite = (e) => {
    e.preventDefault();
    act(async () => {
      await api('/sites', { method: 'POST', body: JSON.stringify(siteForm) });
      setSiteForm({ name: '', site_type: 'construction', location: '' });
      setForm('');
    }, 'Site created.');
  };

  const addCam = (e) => {
    e.preventDefault();
    act(async () => {
      await api('/cameras', { method: 'POST', body: JSON.stringify({ ...camForm, site_id: Number(camForm.site_id) }) });
      setCamForm((f) => ({ ...f, name: '', source_url: '' }));
      setForm('');
    }, 'Camera registered.');
  };

  const addZone = (e) => {
    e.preventDefault();
    act(async () => {
      await api('/zones', {
        method: 'POST',
        body: JSON.stringify({
          ...zoneForm,
          site_id: Number(zoneForm.site_id),
          camera_id: zoneForm.camera_id ? Number(zoneForm.camera_id) : null,
        }),
      });
      setZoneForm((f) => ({ ...f, name: '' }));
      setForm('');
    }, 'Hazard zone created.');
  };

  const resolveViolation = (id) =>
    act(async () => {
      const updated = await api(`/violations/${id}`, { method: 'PATCH', body: JSON.stringify({ status: 'Resolved' }) });
      if (selectedViolation && selectedViolation.id === id) {
        setSelectedViolation(updated);
      }
    }, 'Violation marked as Resolved.');

  const reopenViolation = (id) =>
    act(async () => {
      const updated = await api(`/violations/${id}`, { method: 'PATCH', body: JSON.stringify({ status: 'Open' }) });
      if (selectedViolation && selectedViolation.id === id) {
        setSelectedViolation(updated);
      }
    }, 'Violation reopened.');

  const acknowledgeAlert = (id) =>
    act(() => api(`/alerts/${id}/acknowledge`, { method: 'POST' }), 'Alert acknowledged.');

  const openViolationDrawer = (v) => {
    setSelectedViolation(v);
  };

  const openAlertViolation = (a) => {
    const found = viol.find((v) => v.id === a.violation_id);
    if (found) {
      setSelectedViolation(found);
    } else {
      api(`/violations/${a.violation_id}`)
        .then((v) => setSelectedViolation(v))
        .catch(() => {});
    }
  };

  useEffect(() => {
    if (page === 'Reports') {
      api('/reports/daily').then(setReport).catch((e) => setError(e.message));
    }
  }, [page, viol.length]);

  // Filtered violations
  const filteredViolations = useMemo(() => {
    return viol.filter((v) => {
      const matchesStatus = filter === 'All' || v.status === filter;
      const matchesPpe =
        ppeFilter === 'All' ||
        (ppeFilter === 'helmet' && v.ppe_type === 'helmet') ||
        (ppeFilter === 'vest' && v.ppe_type === 'vest');
      const matchesSearch = `${v.site_name || ''} ${v.camera_name || ''} ${v.zone_name || ''} ${v.ppe_type || ''}`
        .toLowerCase()
        .includes(search.toLowerCase());
      return matchesStatus && matchesPpe && matchesSearch;
    });
  }, [viol, filter, ppeFilter, search]);

  const activeViolationsCount = useMemo(() => viol.filter((v) => v.status === 'Open').length, [viol]);
  const resolvedViolationsCount = useMemo(() => viol.filter((v) => v.status === 'Resolved').length, [viol]);
  const activeAlertsCount = useMemo(() => alerts.filter((a) => a.status === 'Active').length, [alerts]);

  return (
    <div className="shell">
      {/* ── Sidebar ── */}
      <aside className="sidebar">
        <div className="brand">
          <div className="logo">
            <ShieldCheck />
          </div>
          <div>
            <b>OctaVision</b>
            <small>SAFETY INTELLIGENCE</small>
          </div>
        </div>

        <div className="workspace">
          <i />
          <div>
            <b>Workspace</b>
            <small>Production monitoring</small>
          </div>
          <ChevronDown size={15} />
        </div>

        <label>OPERATIONS</label>
        <nav>
          {[
            ['Overview', LayoutDashboard],
            ['Live Monitoring', Video],
            ['Violations', AlertTriangle, activeViolationsCount],
            ['Alert Center', Bell, activeAlertsCount],
          ].map(([n, I, count]) => (
            <button
              key={n}
              className={`nav ${page === n ? 'selected' : ''}`}
              onClick={() => setPage(n)}
            >
              <I size={18} />
              <span>{n}</span>
              {count > 0 && <span className="nav-badge">{count}</span>}
            </button>
          ))}
        </nav>

        <label className="spaced">CONFIGURATION</label>
        <nav>
          {[
            ['Sites & Cameras', MapPin],
            ['Hazard Zones', Activity],
            ['Model Registry', Settings],
            ['Reports', FileText],
          ].map(([n, I]) => (
            <button
              key={n}
              className={`nav ${page === n ? 'selected' : ''}`}
              onClick={() => setPage(n)}
            >
              <I size={18} />
              <span>{n}</span>
            </button>
          ))}
        </nav>

        <div className="side-bottom">
          <div className="system">
            <Zap size={17} />
            <div>
              <b>System status</b>
              <small>
                <i /> AI Engine Connected
              </small>
            </div>
          </div>
          <div className="profile">
            <div className="avatar">OV</div>
            <div>
              <b>Safety Controller</b>
              <small>Operator session</small>
            </div>
            <Settings size={16} />
          </div>
        </div>
      </aside>

      {/* ── Main Area ── */}
      <main>
        {/* Topbar */}
        <header className="topbar">
          <div>
            OctaVision <span>/</span> <b>{page}</b>
          </div>
          <div className="topright">
            <button
              className={`icon-btn ${soundEnabled ? 'active' : ''}`}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                padding: '6px 12px',
                borderRadius: 8,
                background: soundEnabled ? '#ecfaf2' : '#f1f5f9',
                color: soundEnabled ? '#1b8055' : '#64748b',
                border: '1px solid ' + (soundEnabled ? '#bbf7d0' : '#cbd5e1'),
                cursor: 'pointer',
                fontWeight: 600,
                fontSize: 12,
              }}
              title={soundEnabled ? 'Sound notifications enabled. Click to mute.' : 'Sound muted. Click to enable.'}
              onClick={() => {
                const next = !soundEnabled;
                setSoundEnabled(next);
                if (next) playSafetyAlarm();
                setToast(next ? 'Audible safety alerts enabled 🔔' : 'Audible safety alerts muted 🔕');
              }}
            >
              {soundEnabled ? <Volume2 size={16} /> : <VolumeX size={16} />}
              <span>{soundEnabled ? 'Alert Sound ON' : 'Muted'}</span>
            </button>

            <button className="icon-btn" title="Refresh data" onClick={refresh}>
              <RefreshCw size={16} />
            </button>
            <div className="avatar">OV</div>
          </div>
        </header>

        {/* Content */}
        <div className="content">
          {error && (
            <div className="error">
              <AlertTriangle size={18} />
              <span>{error}</span>
              <button onClick={refresh}>Retry</button>
            </div>
          )}

          {toast && (
            <div className="toast">
              <CheckCircle2 size={18} />
              <span>{toast}</span>
              <button onClick={() => setToast('')}>
                <X size={16} />
              </button>
            </div>
          )}

          {/* ── Page: Overview ── */}
          {page === 'Overview' && (
            <>
              <Heading
                eyebrow="SAFETY OPERATIONS / OVERVIEW"
                title="Good morning, Operator"
                desc="Live overview of workplace PPE compliance, cameras and recent safety alerts."
                action={
                  <button className="btn primary" disabled={busy} onClick={simulate}>
                    <Plus size={16} /> Simulate violation
                  </button>
                }
              />

              <div className="stats">
                {[
                  ['Active violations', activeViolationsCount, 'Require immediate resolution', AlertTriangle, 'red'],
                  ['Total violations', viol.length, 'All recorded events', ClipboardList, 'amber'],
                  ['Active alerts', activeAlertsCount, 'Awaiting review in Alert Center', Siren, 'purple'],
                  ['Configured cameras', cams.length, `${sites.length} worksites monitored`, Video, 'blue'],
                ].map(([l, v, s, I, c]) => (
                  <div className="stat" key={l}>
                    <div className="stat-top">
                      {l}
                      <span className={`stat-icon ${c}`}>
                        <I size={18} />
                      </span>
                    </div>
                    <strong>{v}</strong>
                    <small>{s}</small>
                  </div>
                ))}
              </div>

              <div className="columns">
                <section className="panel">
                  <div className="panel-title">
                    <div>
                      <h2>Violation activity</h2>
                      <p>Recorded events over the last 7 days</p>
                    </div>
                    <span className="chip">Daily</span>
                  </div>
                  <div className="chart">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={week(dash.daily_counts || [])} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                        <defs>
                          <linearGradient id="fill" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stopColor="#e65353" stopOpacity=".24" />
                            <stop offset="100%" stopColor="#e65353" stopOpacity="0" />
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 5" vertical={false} stroke="#e9edf3" />
                        <XAxis dataKey="label" axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: '#8793a5' }} />
                        <YAxis allowDecimals={false} axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: '#8793a5' }} />
                        <Tooltip />
                        <Area dataKey="count" type="monotone" stroke="#e65353" strokeWidth={2.5} fill="url(#fill)" />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="chart-foot">
                    <span>
                      <i className="red-dot" /> Confirmed violations
                    </span>
                    <span>Refreshes live</span>
                  </div>
                </section>

                <section className="panel">
                  <div className="panel-title">
                    <div>
                      <h2>System monitoring</h2>
                      <p>Workplace resources active</p>
                    </div>
                    <Activity size={18} />
                  </div>
                  {[
                    [Factory, 'Sites', sites.length, 'Monitored worksites'],
                    [Video, 'Cameras', cams.length, 'Configured video streams'],
                    [MapPin, 'Hazard zones', zones.length, 'PPE policy zones configured'],
                  ].map(([I, l, v, s]) => (
                    <div className="resource" key={l}>
                      <span>
                        <I size={18} />
                      </span>
                      <div>
                        <b>{l}</b>
                        <small>{s}</small>
                      </div>
                      <strong>{v}</strong>
                    </div>
                  ))}
                  <button className="text-link" onClick={() => setPage('Sites & Cameras')}>
                    Manage configuration →
                  </button>
                </section>
              </div>

              <section className="panel table-panel">
                <div className="panel-title">
                  <div>
                    <h2>Recent violations</h2>
                    <p>Click any event to inspect screenshot evidence</p>
                  </div>
                  <button className="btn secondary" onClick={() => setPage('Violations')}>
                    View all ({viol.length}) →
                  </button>
                </div>
                <ViolationCardsList
                  violations={viol.slice(0, 5)}
                  onSelect={openViolationDrawer}
                  onResolve={resolveViolation}
                />
              </section>
            </>
          )}

          {/* ── Page: Live Monitoring ── */}
          {page === 'Live Monitoring' && (
            <>
              <Heading
                eyebrow="CAMERA OPERATIONS & AI INFERENCE"
                title="Live detection & compliance monitoring"
                desc="Live PPE detection across Person, Helmet, and High-Visibility Vest with automated evidence capture."
                action={
                  <button className="btn primary" onClick={simulate} disabled={busy}>
                    <Plus size={16} /> Simulate test event
                  </button>
                }
              />
              <ModelInferencePanel
                apiBase={API}
                sites={sites}
                cams={cams}
                zones={zones}
                onViolationDetected={(v) => {
                  refresh();
                  setToast(`Live violation captured: ${v.ppe_type.toUpperCase()} missing on ${v.camera_name || 'Camera'}`);
                }}
              />
            </>
          )}

          {/* ── Page: Violations (Requirement 5) ── */}
          {page === 'Violations' && (
            <>
              <Heading
                eyebrow="EVENT MANAGEMENT & EVIDENCE LOGS"
                title="Violations"
                desc="Inspect captured evidence screenshots, review model confidence, and resolve compliance events."
              />

              {/* Stats Counters */}
              <div className="violations-stats">
                <div className="violations-stat">
                  <div className="violations-stat-icon red">
                    <AlertTriangle size={20} />
                  </div>
                  <div className="violations-stat-body">
                    <b>{activeViolationsCount} Active</b>
                    <small>Requires immediate resolution</small>
                  </div>
                </div>
                <div className="violations-stat">
                  <div className="violations-stat-icon blue">
                    <ClipboardList size={20} />
                  </div>
                  <div className="violations-stat-body">
                    <b>{viol.length} Total violations</b>
                    <small>Recorded across all cameras</small>
                  </div>
                </div>
                <div className="violations-stat">
                  <div className="violations-stat-icon green">
                    <CheckCircle2 size={20} />
                  </div>
                  <div className="violations-stat-body">
                    <b>{resolvedViolationsCount} Resolved</b>
                    <small>Investigated & closed</small>
                  </div>
                </div>
              </div>

              {/* Filters & Search */}
              <div className="filters" style={{ marginBottom: 16 }}>
                <div className="search">
                  <Search size={16} />
                  <input
                    placeholder="Search site, camera, zone or PPE…"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />
                </div>
                <select value={filter} onChange={(e) => setFilter(e.target.value)}>
                  <option value="All">All statuses</option>
                  <option value="Open">Open only</option>
                  <option value="Resolved">Resolved only</option>
                </select>
                <select value={ppeFilter} onChange={(e) => setPpeFilter(e.target.value)}>
                  <option value="All">All PPE types</option>
                  <option value="helmet">Helmet violations</option>
                  <option value="vest">Vest violations</option>
                </select>
                <small style={{ color: 'var(--text-muted)' }}>{filteredViolations.length} records</small>
              </div>

              {/* Violation Card List */}
              <ViolationCardsList
                violations={filteredViolations}
                onSelect={openViolationDrawer}
                onResolve={resolveViolation}
              />
            </>
          )}

          {/* ── Page: Alert Center (Requirement 6) ── */}
          {page === 'Alert Center' && (
            <>
              <Heading
                eyebrow="REAL-TIME AUDIBLE SAFETY RESPONSE"
                title="Alert center"
                desc="Real-time notifications with safety audio chime. Review, acknowledge, and resolve violations directly."
              />

              <div className="alert-summary">
                <b>{activeAlertsCount} active alerts</b>
                <small>Auto-polling every 5 seconds · Audible alarm {soundEnabled ? 'Enabled' : 'Muted'}</small>
              </div>

              <div className="alert-list">
                {alerts.length ? (
                  alerts.map((a) => {
                    const isHelmet = (a.ppe_type || '').includes('helmet') || (a.message || '').includes('Helmet');
                    return (
                      <div className="panel alert-card" key={a.id}>
                        <div className={`alert-icon ${isHelmet ? 'red' : 'amber'}`}>
                          <AlertTriangle size={20} />
                        </div>
                        <div className="alert-copy">
                          <div className={`alert-type-label ${isHelmet ? '' : 'warn'}`}>
                            {isHelmet ? 'Critical PPE Alert' : 'PPE Warning'}
                          </div>
                          <div>
                            <b>{a.message}</b>
                            <Pill value={a.status} />
                          </div>
                          <p>
                            {a.site_name} · {a.camera_name || 'Camera'} · {a.zone_name || 'All zones'}
                          </p>
                          <small>
                            <Clock3 size={13} /> {timeAgo(a.created_at)} ({fmt(a.created_at)}) · Alert #{a.id}
                          </small>
                        </div>

                        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                          <button
                            className="btn tiny secondary"
                            title="Inspect evidence screenshot"
                            onClick={() => openAlertViolation(a)}
                          >
                            <Eye size={14} /> Evidence
                          </button>
                          {a.status === 'Active' && (
                            <button
                              className="btn tiny primary"
                              disabled={busy}
                              onClick={() => acknowledgeAlert(a.id)}
                            >
                              <Check size={14} /> Acknowledge
                            </button>
                          )}
                          {a.status === 'Active' && (
                            <button
                              className="btn tiny secondary"
                              disabled={busy}
                              onClick={() => resolveViolation(a.violation_id)}
                            >
                              Resolve
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })
                ) : (
                  <Empty title="No alerts yet" text="When a camera detects missing PPE, instant alerts will trigger here." />
                )}
              </div>
            </>
          )}

          {/* ── Page: Sites & Cameras ── */}
          {page === 'Sites & Cameras' && (
            <>
              <Heading
                eyebrow="WORKSPACE CONFIGURATION"
                title="Sites & cameras"
                desc="Register worksites and configure camera sources for AI processing."
                action={
                  <button className="btn primary" onClick={() => setForm(form === 'site' ? '' : 'site')}>
                    <Plus size={16} /> Add site
                  </button>
                }
              />
              {form === 'site' && (
                <form className="panel form" onSubmit={addSite}>
                  <h2>New site</h2>
                  <div className="form-grid">
                    <Field label="Site name">
                      <input
                        required
                        value={siteForm.name}
                        onChange={(e) => setSiteForm({ ...siteForm, name: e.target.value })}
                        placeholder="e.g. North Gate Construction"
                      />
                    </Field>
                    <Field label="Site type">
                      <select
                        value={siteForm.site_type}
                        onChange={(e) => setSiteForm({ ...siteForm, site_type: e.target.value })}
                      >
                        {TYPES.map((t) => (
                          <option value={t[0]} key={t[0]}>
                            {t[1]}
                          </option>
                        ))}
                      </select>
                    </Field>
                    <Field label="Location">
                      <input
                        value={siteForm.location}
                        onChange={(e) => setSiteForm({ ...siteForm, location: e.target.value })}
                        placeholder="Optional address"
                      />
                    </Field>
                  </div>
                  <div className="form-actions">
                    <button className="btn primary" disabled={busy}>
                      Save site
                    </button>
                  </div>
                </form>
              )}

              <div className="section-head">
                <h2>
                  Registered sites <span>{sites.length}</span>
                </h2>
                <button className="btn secondary" onClick={() => setForm(form === 'camera' ? '' : 'camera')}>
                  <Plus size={15} /> Add camera
                </button>
              </div>

              {form === 'camera' && (
                <form className="panel form" onSubmit={addCam}>
                  <h2>Configure camera</h2>
                  <div className="form-grid">
                    <Field label="Camera name">
                      <input
                        required
                        value={camForm.name}
                        onChange={(e) => setCamForm({ ...camForm, name: e.target.value })}
                        placeholder="e.g. Camera 01 · Live Detection"
                      />
                    </Field>
                    <Field label="Site">
                      <select
                        required
                        value={camForm.site_id}
                        onChange={(e) => setCamForm({ ...camForm, site_id: e.target.value })}
                      >
                        {sites.map((s) => (
                          <option value={s.id} key={s.id}>
                            {s.name}
                          </option>
                        ))}
                      </select>
                    </Field>
                    <Field label="Source type">
                      <select
                        value={camForm.source_type}
                        onChange={(e) => setCamForm({ ...camForm, source_type: e.target.value })}
                      >
                        <option value="simulated">Simulated Demo</option>
                        <option value="rpi">Raspberry Pi 5 (Live Video Relay)</option>
                        <option value="webcam">Webcam (Browser Direct)</option>
                        <option value="rtsp">RTSP CCTV</option>
                      </select>
                    </Field>
                    {camForm.source_type === 'rpi' && (
                      <Field label="Pi Stream URL (leave empty for default relay)">
                        <input
                          value={camForm.source_url}
                          onChange={(e) => setCamForm({ ...camForm, source_url: e.target.value })}
                          placeholder="http://172.20.10.7:8001/video_feed"
                        />
                      </Field>
                    )}
                    {camForm.source_type === 'rtsp' && (
                      <Field label="RTSP URL">
                        <input
                          required
                          value={camForm.source_url}
                          onChange={(e) => setCamForm({ ...camForm, source_url: e.target.value })}
                          placeholder="rtsp://admin:pass@192.168.1.50:554/live"
                        />
                      </Field>
                    )}
                  </div>
                  <div className="form-actions">
                    <button className="btn primary" disabled={busy || !sites.length}>
                      Save camera
                    </button>
                  </div>
                </form>
              )}

              <div className="cards">
                {sites.map((s) => (
                  <div className="panel site-card" key={s.id}>
                    <div className="site-head">
                      <span>
                        <Factory />
                      </span>
                      <div>
                        <b>{s.name}</b>
                        <small>
                          <MapPin size={12} /> {s.location || 'Location not specified'}
                        </small>
                      </div>
                      <em>{TYPES.find((t) => t[0] === s.site_type)?.[1] || s.site_type}</em>
                    </div>
                    <div className="site-numbers">
                      <div>
                        <small>CAMERAS</small>
                        <b>{cams.filter((c) => c.site_id === s.id).length}</b>
                      </div>
                      <div>
                        <small>MODEL</small>
                        <b>Connected</b>
                      </div>
                    </div>
                    {cams
                      .filter((c) => c.site_id === s.id)
                      .map((c) => (
                        <div className="camera-row" key={c.id}>
                          <Video size={15} />
                          <span style={{ flex: 1, minWidth: 0 }}>{c.name}</span>
                          {c.source_type === 'rpi' && (
                            <span style={{ fontSize: 10, background: '#e0f2fe', color: '#0369a1', padding: '2px 7px', borderRadius: 6, fontWeight: 700 }}>
                              Raspberry Pi 5
                            </span>
                          )}
                          <Pill value={c.status} />
                        </div>
                      ))}
                  </div>
                ))}
              </div>
            </>
          )}

          {/* ── Page: Hazard Zones ── */}
          {page === 'Hazard Zones' && (
            <>
              <Heading
                eyebrow="SAFETY BOUNDARIES"
                title="Hazard zones"
                desc="Configure areas where PPE guidelines apply."
                action={
                  <button className="btn primary" onClick={() => setForm(form === 'zone' ? '' : 'zone')}>
                    <Plus size={16} /> Add zone
                  </button>
                }
              />
              {form === 'zone' && (
                <form className="panel form" onSubmit={addZone}>
                  <h2>New hazard zone</h2>
                  <div className="form-grid">
                    <Field label="Zone name">
                      <input
                        required
                        value={zoneForm.name}
                        onChange={(e) => setZoneForm({ ...zoneForm, name: e.target.value })}
                        placeholder="Zone name"
                      />
                    </Field>
                    <Field label="Site">
                      <select
                        required
                        value={zoneForm.site_id}
                        onChange={(e) => setZoneForm({ ...zoneForm, site_id: e.target.value, camera_id: '' })}
                      >
                        {sites.map((s) => (
                          <option key={s.id} value={s.id}>
                            {s.name}
                          </option>
                        ))}
                      </select>
                    </Field>
                    <Field label="Camera">
                      <select
                        value={zoneForm.camera_id}
                        onChange={(e) => setZoneForm({ ...zoneForm, camera_id: e.target.value })}
                      >
                        <option value="">All cameras at site</option>
                        {cams
                          .filter((c) => String(c.site_id) === String(zoneForm.site_id))
                          .map((c) => (
                            <option key={c.id} value={c.id}>
                              {c.name}
                            </option>
                          ))}
                      </select>
                    </Field>
                    <Field label="Required PPE">
                      <select
                        value={zoneForm.required_ppe}
                        onChange={(e) => setZoneForm({ ...zoneForm, required_ppe: e.target.value })}
                      >
                        <option value="helmet">Helmet required</option>
                        <option value="vest">High-visibility vest required</option>
                        <option value="helmet,vest">Both Helmet + Vest required</option>
                      </select>
                    </Field>
                  </div>
                  <div className="form-actions">
                    <button className="btn primary" disabled={busy || !sites.length}>
                      Save zone
                    </button>
                  </div>
                </form>
              )}

              <div className="cards">
                {zones.map((z) => (
                  <div className="panel zone-card" key={z.id}>
                    <MapPin />
                    <div>
                      <b>{z.name}</b>
                      <small>
                        {z.site_name} · {z.camera_name || 'All site cameras'}
                      </small>
                      <span>
                        Required PPE: <strong>{z.required_ppe.replace(',', ' + ')}</strong>
                      </span>
                    </div>
                    <Pill value="Hazard" />
                  </div>
                ))}
              </div>
            </>
          )}

          {/* ── Page: Model Registry ── */}
          {page === 'Model Registry' && (
            <>
              <Heading
                eyebrow="AI ARCHITECTURE"
                title="Model registry"
                desc="Modular AI detection models powering decoupled violation management across multiple sites."
              />
              <div className="note">
                <Info size={17} />
                <span>
                  <b>Decoupled Violation Management Service</b> is active. All models (Construction, Chemical, Road, Mining)
                  route violation events through the common duplicate suppression and evidence capture pipeline.
                </span>
              </div>
              <section className="panel table-panel">
                <table>
                  <thead>
                    <tr>
                      <th>MODEL</th>
                      <th>SITE TYPE</th>
                      <th>VERSION</th>
                      <th>WEIGHTS PATH</th>
                      <th>STATUS</th>
                    </tr>
                  </thead>
                  <tbody>
                    {models.map((m) => (
                      <tr key={m.id}>
                        <td>
                          <b>{m.name}</b>
                        </td>
                        <td>{m.site_type}</td>
                        <td>{m.version}</td>
                        <td>{m.weights_path || 'OctaVision Hub'}</td>
                        <td>
                          <Pill value={m.status} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </section>
            </>
          )}

          {/* ── Page: Reports ── */}
          {page === 'Reports' && (
            <>
              <Heading
                eyebrow="COMPLIANCE INTELLIGENCE"
                title="Daily reports"
                desc="Daily violation analytics and resolution totals grouped by worksite."
                action={
                  <button className="btn secondary" onClick={() => api('/reports/daily').then(setReport).catch((e) => setError(e.message))}>
                    <Activity size={15} /> Refresh report
                  </button>
                }
              />
              <div className="report-banner">
                <FileText />
                <div>
                  <b>Daily compliance summary</b>
                  <small>Report date: {report?.date || 'Today'}</small>
                </div>
                <strong>
                  {report?.total_violations ?? '—'}
                  <small>total events</small>
                </strong>
              </div>

              <section className="panel table-panel">
                <div className="panel-title">
                  <div>
                    <h2>Site breakdown</h2>
                    <p>Open and resolved compliance events</p>
                  </div>
                </div>
                {report ? (
                  <table>
                    <thead>
                      <tr>
                        <th>SITE</th>
                        <th>TOTAL</th>
                        <th>OPEN</th>
                        <th>RESOLVED</th>
                      </tr>
                    </thead>
                    <tbody>
                      {report.by_site.map((r) => (
                        <tr key={r.site_name}>
                          <td>{r.site_name}</td>
                          <td>{r.violations || 0}</td>
                          <td>{r.open_violations || 0}</td>
                          <td>{r.resolved_violations || 0}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <Empty title="Report loading" text="Fetching daily summary." />
                )}
              </section>
            </>
          )}
        </div>

        <footer>
          <span>© 2026 OctaVision Safety Intelligence</span>
          <span>
            <i /> Modular Violation Engine · Real-Time CCTV Evidence Capture
          </span>
        </footer>
      </main>

      {/* ── Slide-over Detail Drawer (Requirement 5) ── */}
      {selectedViolation && (
        <div className="drawer-overlay" onClick={() => setSelectedViolation(null)}>
          <div className="drawer" onClick={(e) => e.stopPropagation()}>
            <div className="drawer-header">
              <h2>Violation #{selectedViolation.id} Details</h2>
              <Pill value={selectedViolation.status} />
              <button
                className="drawer-close"
                onClick={() => setSelectedViolation(null)}
                title="Close drawer"
              >
                <X size={18} />
              </button>
            </div>

            <div className="drawer-body">
              {/* Evidence Snapshot */}
              <div className="drawer-snapshot">
                {selectedViolation.snapshot_path ? (
                  <img
                    src={`${API_BASE}${selectedViolation.snapshot_path}`}
                    alt={`Evidence Snapshot #${selectedViolation.id}`}
                    onError={(e) => {
                      e.target.style.display = 'none';
                    }}
                  />
                ) : (
                  <div className="drawer-snapshot-empty">
                    <Video size={36} style={{ marginBottom: 8, opacity: 0.5 }} />
                    <p>No snapshot captured for this event record.</p>
                  </div>
                )}
              </div>

              {/* Forensic Details Fields Grid */}
              <div className="drawer-fields">
                <div className="drawer-field">
                  <label>Violation Type</label>
                  <span>
                    {selectedViolation.ppe_type === 'helmet'
                      ? 'Helmet Not Detected'
                      : selectedViolation.ppe_type === 'vest'
                      ? 'Safety Vest Missing'
                      : selectedViolation.ppe_type}
                  </span>
                </div>

                <div className="drawer-field">
                  <label>Status</label>
                  <span>
                    <Pill value={selectedViolation.status} />
                  </span>
                </div>

                <div className="drawer-field">
                  <label>Camera</label>
                  <span>{selectedViolation.camera_name || `Camera #${selectedViolation.camera_id || '—'}`}</span>
                </div>

                <div className="drawer-field">
                  <label>Worksite</label>
                  <span>{selectedViolation.site_name || 'General Site'}</span>
                </div>

                <div className="drawer-field">
                  <label>Hazard Zone</label>
                  <span>{selectedViolation.zone_name || 'Unassigned hazard area'}</span>
                </div>

                <div className="drawer-field">
                  <label>Model Confidence</label>
                  <span>
                    {selectedViolation.confidence
                      ? `${(selectedViolation.confidence * 100).toFixed(1)}%`
                      : '92.0%'}
                  </span>
                </div>

                <div className="drawer-field">
                  <label>Severity</label>
                  <span style={{ color: selectedViolation.severity === 'Critical' ? '#e25353' : '#d97706' }}>
                    {selectedViolation.severity || 'High'}
                  </span>
                </div>

                <div className="drawer-field">
                  <label>Violation Time</label>
                  <span>{fmt(selectedViolation.occurred_at)}</span>
                </div>
              </div>

              {/* Actions */}
              <div className="drawer-actions">
                {selectedViolation.status === 'Open' ? (
                  <button
                    className="btn primary"
                    disabled={busy}
                    onClick={() => resolveViolation(selectedViolation.id)}
                  >
                    <Check size={16} /> Mark as Resolved
                  </button>
                ) : (
                  <button
                    className="btn secondary"
                    disabled={busy}
                    onClick={() => reopenViolation(selectedViolation.id)}
                  >
                    Reopen Violation
                  </button>
                )}

                {selectedViolation.snapshot_path && (
                  <a
                    href={`${API_BASE}${selectedViolation.snapshot_path}`}
                    target="_blank"
                    rel="noreferrer"
                    className="btn secondary"
                    style={{ textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 6 }}
                  >
                    <ExternalLink size={15} /> Open full evidence image
                  </a>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* ── UI Components ── */
function Heading({ eyebrow, title, desc, action }) {
  return (
    <div className="heading">
      <div>
        <label>{eyebrow}</label>
        <h1>{title}</h1>
        <p>{desc}</p>
      </div>
      {action}
    </div>
  );
}

function Field({ label, children }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
    </label>
  );
}

function Pill({ value }) {
  const c = ['Open', 'Active'].includes(value)
    ? 'bad'
    : ['Resolved', 'Acknowledged'].includes(value)
    ? 'good'
    : 'neutral';
  return (
    <span className={`pill ${c}`}>
      <i />
      {value}
    </span>
  );
}

function Empty({ title, text }) {
  return (
    <div className="empty">
      <ClipboardList size={26} />
      <b>{title}</b>
      <p>{text}</p>
    </div>
  );
}

/* ── Rich Violation Cards List (Requirement 5) ── */
function ViolationCardsList({ violations, onSelect, onResolve }) {
  if (!violations.length) {
    return <Empty title="No violations found" text="Simulate or detect an event to view evidence records." />;
  }

  return (
    <div className="violation-list">
      {violations.map((v) => {
        const isHelmet = (v.ppe_type || '').includes('helmet');
        const ppeTitle = isHelmet ? 'Helmet Not Detected' : 'Safety Vest Missing';
        const camLabel = v.camera_name || `Camera #${v.camera_id || '—'}`;
        const timeFormatted = v.occurred_at
          ? new Date(v.occurred_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
          : '—';

        return (
          <div
            className="violation-card"
            key={v.id}
            onClick={() => onSelect(v)}
            title="Click to view captured evidence details"
          >
            {/* Color accent bar */}
            <div className={`violation-card-accent ${v.status === 'Open' ? 'open' : 'resolved'}`} />

            <div className="violation-card-body">
              {/* Icon */}
              <div className={`violation-card-icon ${isHelmet ? 'helmet' : 'vest'}`}>
                {isHelmet ? <HardHat size={20} /> : <AlertTriangle size={20} />}
              </div>

              {/* Title & Metadata */}
              <div className="violation-card-info">
                <div className="violation-card-type">{ppeTitle}</div>
                <div className="violation-card-meta">
                  <span>
                    <Video size={12} /> {camLabel}
                  </span>
                  <span>·</span>
                  <span>
                    <Clock3 size={12} /> {timeFormatted}
                  </span>
                  <span>·</span>
                  <span>{v.site_name || 'Site'}</span>
                  {v.zone_name && (
                    <>
                      <span>·</span>
                      <span>{v.zone_name}</span>
                    </>
                  )}
                </div>
              </div>
            </div>

            {/* Right side: Status, Confidence & Quick Resolve */}
            <div className="violation-card-right" onClick={(e) => e.stopPropagation()}>
              <Pill value={v.status} />
              <span className="violation-card-conf">
                {v.confidence ? `${(v.confidence * 100).toFixed(0)}% Conf` : ''}
              </span>
              {v.status === 'Open' && onResolve && (
                <button
                  className="btn tiny secondary"
                  onClick={() => onResolve(v.id)}
                  title="Resolve this violation"
                >
                  Resolve
                </button>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function week(rows) {
  const map = new Map(rows.map((r) => [r.day, r.count]));
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date();
    d.setDate(d.getDate() - 6 + i);
    const k = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    return {
      day: k,
      label: d.toLocaleDateString(undefined, { weekday: 'short' }),
      count: map.get(k) || 0,
    };
  });
}
