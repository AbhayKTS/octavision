# OctaVision — Master Implementation Roadmap
## IDE Source of Truth: Current Milestone to Full Project Completion

**Last updated:** 2026-10-30

**Purpose:** Use this document as the implementation roadmap for the IDE/coding agent. Work in small phases, verify each phase, and do not start the next phase until the current phase's acceptance criteria pass or a blocker is explicitly documented.

## Current baseline
- React + Vite frontend and Flask + SQLite backend run locally on Windows through VS Code.
- Dashboard and simulated violation workflow work.
- `POST /api/detections` is implemented in `backend/app.py`.
- `no_helmet` creates a violation and alert; `helmet` does not.
- Repeated `event_key` requests are idempotent.
- The user reports all four API unit tests pass.
- YOLO/Ultralytics is the chosen model technology, but dataset preparation/training is still underway.
- Real trained-model-to-dashboard inference is not yet verified.
- The end goal is four different models for four site types. The current model target is the general helmet model.
- Exact site types, requirements, and not-goals must be taken from the approved final synopsis. Do not invent them.

---

# A. Instructions to the IDE / Coding Agent

1. **Inspect before editing.** Check the actual repository, current routes, database schema, frontend pages, tests, requirements, and README before making changes.
2. **Use canonical files.** `backend/app.py` is the expected Flask entry point unless inspection proves otherwise. Do not let `app copy.py` or other duplicates become competing implementations. Never delete a copy until its contents have been checked and backed up.
3. **Preserve the working app.** Keep the dashboard, simulated violation flow, alert acknowledgement/resolution, and existing data working through all phases.
4. **Keep platform and model separate.** The platform must start and operate without Ultralytics or trained weights. Model code must use a documented API/adapter contract and must not write directly to the platform database.
5. **Use adapters.** Map YOLO's raw class names to normalized OctaVision labels in one documented location. Unknown classes must be skipped with a clear reason or rejected; never silently treat an unknown class as a violation.
6. **Keep simulation explicit.** Mark simulated/API-test/model data distinctly. Do not present simulated data as real camera/model detections.
7. **No violation for helmet-present.** `helmet` / `helmet_detected` is a compliant observation. `no_helmet` / `helmet_missing` is a violation candidate subject to validation and policy.
8. **Build for four models without integrating four models now.** The model registry and site-to-model mapping should support future models, but only the general helmet model is the current training target. Never silently run a model intended for another site type.
9. **Respect the synopsis.** Read the final approved synopsis and its explicit not-goals. If this roadmap conflicts with it, report the conflict and ask for clarification. Do not expand scope silently.
10. **Windows + VS Code first.** Give PowerShell commands, Windows path examples, and repeatable setup steps.
11. **Avoid unnecessary dependencies.** Keep model/training dependencies separate from core platform requirements.
12. **Validate and protect data.** Use parameterized SQL, transactions for related writes, clear errors, bounded inputs, and safe file handling. Do not expose the development server publicly.
13. **Test claims must be truthful.** Never claim tests passed unless they were actually run and the output confirms it.
14. **No large rewrites for small features.** Prefer incremental, backward-compatible changes and explicit database migrations.
15. **Document every phase.** Update README, API/schema docs, and a phase log. Record limitations honestly.
16. **Phase gate.** At the end of each phase, report changed files, behavior, commands/tests/results, manual checks, limitations, and next steps. Do not proceed past a failed gate without fixing it or recording a blocker.

### Standard process for every phase
1. Inspect repository and summarize current behavior.
2. State intended change, affected files, schema/API/UI impact, and risks.
3. Implement the smallest complete change.
4. Add/update automated tests.
5. Run backend tests and frontend checks as applicable.
6. Manually verify browser behavior when UI changes.
7. Update docs and `docs/PHASE_LOG.md`.
8. Report pass/fail against acceptance criteria and provide exact Windows commands.

---

# B. Target Architecture

## Platform layer — must work with no model installed
- **Frontend:** React/Vite screens, navigation, forms, tables, charts, filters, loading/error/empty/success states.
- **Flask API:** validation, business rules, response serialization, health endpoints.
- **Database:** SQLite for local development; migrations and data-access logic; avoid silently resetting existing databases.
- **Detection event service:** stores normalized observations and decides whether an observation becomes a violation.
- **Violation/alert service:** creates and tracks incidents, status changes, severity, acknowledgement, resolution, and deduplication.
- **Evidence service:** controlled storage/retrieval for snapshots/clips if required by scope.
- **Reporting service:** accurate date-range and site/camera aggregates.
- **Configuration/registry:** sites, site types, cameras, zones, model versions, class maps, confidence thresholds, and policies.
- **Observability:** logs, health/readiness, and clear failure states.

## Model layer — independently testable and optional
- Dataset validator and class-name checker.
- Reproducible YOLO training configuration and commands.
- Evaluation pipeline and model release report.
- Still-image inference adapter first.
- Later stream runner for webcam/RTSP if included in approved scope.
- Model registry integration and explicit model/version/site compatibility.

## Expected event flow
Source (simulation/image/stream) → model inference → adapter maps raw class → normalized event sent to Flask API → backend validates site/camera/zone/time/confidence/event key → deduplication/policy → event stored → violation/alert created only when appropriate → evidence linked if supported → dashboard/reports read persisted state.

---

# C. Stable Detection Event Contract

Inspect the current contract first and evolve it compatibly.

Expected fields:
- `site_id` (required; must exist)
- `camera_id` (required; must belong to site)
- `zone_id` (optional; must be compatible with site/camera)
- `class_name` or `label` (required)
- `confidence` (required number from 0 to 1)
- `event_key` (stable idempotency key for retries)
- `occurred_at` (ISO-8601; timezone policy documented)
- `source` (`api_test`, `simulated`, `adapter`, or `model`, as applicable)
- `model_id` / `model_version` (add when registry exists)
- `bounding_box` / `frame_id` / `track_id` (optional for future video use)
- `snapshot_id` or evidence reference only when the evidence service actually supports it.

Normalization:
- `helmet` → `helmet_detected`
- `no_helmet` or `no-helmet` → `helmet_missing`
- Preserve raw label as metadata when practical.
- Unknown label: clear rejection/skip, never automatic violation.

Rules:
- Helmet-present observations do not create a violation/alert.
- No-helmet observations can create a violation/alert after validation and policy checks.
- Invalid fields/references return clear 4xx errors and must not change the database.
- Same `event_key` retry must not create duplicate records.
- Related event/violation/alert writes should be transactional.
- Idempotency protects retries of the same event, but **does not** stop repeated frame detections with different event keys. Temporal deduplication is a separate later phase.
- Decide and implement whether compliant observations are persisted. Prefer a `detection_events`/observation table before live streams so all detections are auditable.

---

# D. Phased Implementation Plan

## Phase 0 — Baseline, scope, and repository truth
**Status:** Partially complete; verify again before further changes.

Tasks:
- Inspect root, backend, frontend, requirements, database, tests, and README.
- Confirm the active Flask entry point and actual Vite frontend folder.
- Confirm `/api/health`, routes, database initialization, and where SQLite files live.
- Compare any duplicate files (e.g. `app copy.py`) without deleting them blindly.
- Read the final synopsis and record goals, non-goals, exact four site types, constraints, and expected deliverables.
- Create `docs/PROJECT_SCOPE.md` and `docs/PHASE_LOG.md`.
- Capture baseline test commands and actual results.

Acceptance:
- One canonical entry point documented.
- Dashboard and simulated workflow work.
- Existing four ingestion tests pass on the active code.
- Scope/non-goals are recorded from the synopsis, not guessed.
- No data or files were destructively removed.

## Phase 1 — Ingestion API hardening
**Status:** Endpoint works; hardening remains.

Tasks:
- Review `POST /api/detections` and its response schema.
- Centralize label normalization.
- Test missing fields, unknown labels, invalid confidence, malformed timestamp, invalid site/camera, camera/site mismatch, invalid zone, duplicate event, helmet event, no-helmet event, and transaction rollback where practical.
- Add consistent JSON error responses.
- Add database uniqueness/indexing for `event_key` as appropriate; handle race conditions safely.
- Ensure invalid requests leave no partial database changes.
- Keep simulated workflow backward-compatible.
- Document payloads, responses, errors, and PowerShell tests.

Acceptance:
- Existing tests continue to pass; new validation tests pass.
- Duplicate requests cannot create a second violation/alert.
- Invalid requests do not mutate data.
- API contract is documented.

## Phase 2 — Detection observation persistence
**Status:** Verify whether current schema stores only violations.

Tasks:
- If needed, add a `detection_events` table through a migration (do not reset the database).
- Store normalized and raw class, confidence, source, site/camera/zone, event/received timestamps, event key, model/version, bounding box, and evidence reference when available.
- Store both helmet-present and no-helmet observations.
- Link violations to the event that caused them.
- Add indexes for event key, site, camera, timestamp, and class.
- Add paginated/filterable read APIs if required by the synopsis.
- Define retention policy; do not silently delete records.

Acceptance:
- Both compliant and non-compliant detections are queryable.
- Helmet-present never creates a violation.
- No-helmet links to exactly one violation and corresponding alert.
- Existing records survive migrations.

## Phase 3 — Alert lifecycle and temporal alert policy
**Status:** Basic creation/acknowledgement exists; verify full behavior.

Tasks:
- Define valid alert transitions aligned with existing UI (e.g. Active → Acknowledged → Resolved).
- Validate acknowledgement/resolution actions and record timestamps.
- Record actor identity when authentication exists; until then, label actions as local/demo.
- Link alert to violation and evidence.
- Add severity, site/camera, created/updated times, and filtering as needed.
- Add configurable grouping/cooldown to prevent one person being alerted every frame later.
- Keep notification delivery behind an interface; implement external email/SMS only if in scope.
- Ensure notification failure does not undo a valid stored violation.

Acceptance:
- UI and API agree on statuses and transitions.
- Invalid transitions return clear errors.
- Alert Center still works with simulated and API-ingested events.
- Cooldown/grouping behavior is tested before stream processing.

## Phase 4 — Model-independent dashboard and UX audit
**Status:** Basic dashboard exists; comprehensive audit required.

Tasks:
- Audit every page, button, form, navigation item, filter, chart, table, and status label.
- Ensure counts/charts come from backend data, not hardcoded examples.
- Add loading, empty, error, success, and retry states.
- Add validation and confirmation for destructive actions.
- Check responsive behavior and keyboard/accessibility basics.
- Clearly label simulated, API-test, and model-generated records.
- Ensure refresh shows persisted state.
- Do not add features marked as not-goals.

Acceptance:
- Every visible action works or is explicitly marked unavailable/planned.
- Dashboard totals match backend data.
- Simulated/API ingestion work without model packages or weights.
- Frontend build and manual smoke test pass.

## Phase 5 — Sites, cameras, zones, and policies
**Status:** Basic CRUD exists; completeness/validation required.

Tasks:
- Review CRUD for sites, cameras, zones and all form validation.
- Prevent invalid site-camera-zone references.
- Record site type using the approved synopsis' exact categories.
- Define configured/reachable/processing statuses separately.
- Define camera source types; never call a camera “online” simply because it is registered.
- Add confirmation/dependency errors for delete operations.
- Keep geometry/polygon editing out unless the synopsis requires it.

Acceptance:
- Configurations persist and relationships validate.
- Site type can map to a future model/policy.
- Status labels reflect actual checks.

## Phase 6 — Evidence and snapshot storage
**Status:** Not verified; adapter's local path is not uploaded evidence.

Tasks:
- Confirm whether snapshots/clips are in scope.
- If required, create controlled evidence storage and metadata.
- Validate file size/type and generate safe filenames.
- Prevent path traversal; never trust arbitrary client paths.
- Store file references, not arbitrary local paths.
- Add upload/retrieval endpoints and link evidence to event/violation/alert.
- Add UI preview and missing-evidence fallback.
- Define access and retention policy.
- If out of scope, document the limitation clearly.

Acceptance:
- Evidence can be retrieved through a controlled endpoint.
- Invalid/unsafe files are rejected.
- Missing evidence does not break screens.

## Phase 7 — Reports and analytics
**Status:** Basic daily report exists; validate totals.

Tasks:
- Define metrics from the synopsis: event totals, violation totals, severity/status breakdowns, site/camera comparisons, and rates only where denominators are meaningful.
- Prevent duplicate counting due to multiple alerts/frames.
- Add date-range filters and explicit timezone rules.
- Support empty periods and partial data gracefully.
- Add drill-down to underlying events/violations.
- Add CSV/PDF export only if approved scope requires it.
- Test with deterministic fixtures and boundary dates.

Acceptance:
- Report totals match expected database queries.
- Filters and timezone boundaries are correct.
- Compliant observations and violations are not conflated.

## Phase 8 — Model registry and platform/model contract
**Status:** Placeholder registry exists; make it functional.

Tasks:
- Define model metadata: ID/name/version, framework, artifact reference, checksum, class map, supported site type, threshold, status, training dataset/version, metrics, and timestamps.
- Define lifecycle states (e.g. Draft, Validated, Active, Deprecated, Failed) and valid transitions.
- Add site-type → approved model mapping.
- Keep large weights outside source control; store artifact reference and checksum.
- Record model/version on every real detection.
- Do not import Ultralytics into Flask core routes.
- If no model is active, platform remains usable and reports that model inference is unavailable.
- Block incompatible model/site combinations and support rollback.

Acceptance:
- Model metadata and lifecycle are testable.
- Site/model mapping is validated.
- Platform starts without Ultralytics/weights.
- Model provenance is traceable from events.

## Phase 9 — General helmet dataset readiness and training
**Status:** Dataset/training in progress outside the platform.

Tasks:
- Inspect actual dataset YAML, class IDs/names, directory structure, labels, and splits.
- Validate missing/corrupt images, missing labels, invalid boxes, duplicate images, class mismatches, class imbalance, and potential train/test leakage.
- Review difficult cases: occlusion, small helmets, low light, distance, crowded scenes, and varied viewpoints where represented in scope.
- Confirm annotation format and task match YOLO detection training.
- Record data provenance/licensing.
- Make training config reproducible: base model, image size, batch, epochs, seed where relevant, augmentation, device, and output location.
- Train the general helmet model separately from the dashboard.
- Save logs, weights, dataset version, configuration, and environment versions.
- Do not call a model ready just because training finished.

Acceptance:
- Dataset validation report exists.
- Class mapping is consistent across YAML, labels, training, and adapter.
- Training command/config is reproducible.
- Best weights and training metadata are stored in a known path.
- Platform can run without training dependencies.

## Phase 10 — General model evaluation and release gate
**Status:** Blocked until trained weights and held-out data are available.

Tasks:
- Evaluate on a held-out test set that was not used to tune training.
- Record precision, recall, mAP at appropriate IoU thresholds, per-class metrics, error examples, and inference speed where relevant.
- Inspect false positives/negatives, especially missed no-helmet cases.
- Select confidence thresholds from evaluation evidence and safety requirements; keep thresholds configurable.
- Test lighting, distance, angle, occlusion, and other relevant variations.
- Document limitations and known failure cases.
- Define release thresholds with the project owner; do not invent universal acceptance numbers.
- Store evaluation report against the model version.

Acceptance:
- Held-out evaluation is documented.
- Per-class performance and failure cases are reviewed.
- Model becomes Validated only after agreed criteria pass.
- Failed models cannot be activated silently.

## Phase 11 — YOLO still-image adapter integration
**Status:** Starter adapter exists; real inference is not yet verified.

Tasks:
- Inspect `backend/model_adapter/yolo_adapter.py`, API schema, actual dataset YAML, and `model.names`.
- Update `CLASS_MAP` to exact trained labels; test mappings.
- Load weights from an explicit path/configuration.
- Run inference on a still image first.
- Send site/camera/zone, normalized class, confidence, timestamp, stable event key, source, model/version, and bounding box when API supports them.
- Handle no detections, unknown labels, unreadable images, missing weights, model-load failures, API timeouts, HTTP errors, and malformed responses.
- Retry only transient failures, reusing the same event key for the same event.
- Do not claim local `snapshot_path` is uploaded evidence.
- Add mocked tests that do not require downloading weights.
- Prepare one known helmet image and one known no-helmet image for manual integration testing.

Acceptance:
- Adapter runs with trained weights and a test image.
- Class mapping is correct.
- Helmet sample creates no violation; no-helmet sample creates a violation/alert.
- API failures are surfaced clearly.
- Dashboard and platform tests still pass.
- Integration is documented as still-image-only.

## Phase 12 — Temporal deduplication and tracking
**Status:** Required before continuous camera processing.

Tasks:
- Separate same-request idempotency from repeated detection across different video frames.
- Choose and document grouping strategy: tracker ID if reliable, otherwise camera/zone/class/time window or another justified policy.
- Configure cooldown, grouping window, and escalation policy.
- Do not merge separate people into one incident without a justified rule.
- Preserve raw observation traceability.
- Handle tracker resets, timestamp gaps, and camera reconnects.
- Test consecutive frames, multiple people, and incidents after cooldown expires.

Acceptance:
- Same ongoing incident does not create an alert per frame.
- Distinct incidents remain distinguishable.
- Cooldown is configurable and covered by tests.

## Phase 13 — Live camera/video processing
**Status:** Future phase; only start after image-based integration is reliable.

Tasks:
- Confirm supported sources from the synopsis: webcam, RTSP/IP camera, recorded video, or only a subset.
- Run long-lived capture/inference in a worker/service, not inside Flask request handlers.
- Implement start/stop/status, reconnect/backoff, frame sampling, bounded queues, cleanup, and graceful shutdown.
- Isolate per-camera worker state.
- Show actual last-frame/last-inference/connectivity status.
- Configure inference interval, confidence threshold, and concurrency.
- Protect camera credentials; never commit them or log them.
- Test with recorded fixtures in automated tests; physical cameras must not be required for CI.
- Ensure unavailable streams do not crash the platform.

Acceptance:
- Supported stream can start/stop and reports honest status.
- Disconnect/reconnect and resource cleanup work.
- Events flow through the same normalized API contract.
- Temporal deduplication prevents alert storms.

## Phase 14 — Four site-specific models, staged rollout
**Status:** Future phase. Do not train/integrate all four at this stage.

Tasks:
- Extract the exact four site types and requirements from the approved synopsis.
- Create a matrix for each: safety hazards, PPE classes, expected outputs, data needs, confidence thresholds, policies, evidence, and reports.
- Decide with evidence whether each site requires a separate model, fine-tuned model, or shared model plus site-specific policy. Do not assume this design choice in advance.
- Collect/annotate data, train, evaluate, version, and release each site model independently.
- Register each model and map it only to compatible site types.
- Roll out one model/site at a time, beginning in a controlled test environment.
- Preserve model/version/policy provenance for every event.
- Support rollback or a safe “no active model” state.

Acceptance:
- Four categories match the synopsis exactly.
- Each model has separate dataset, training, evaluation, version, and release records.
- Wrong-model selection is blocked.
- Adding a model does not require rewriting the dashboard/API.

## Phase 15 — Security, privacy, resilience, and deployment readiness
**Status:** Not production-ready until verified.

Tasks:
- Determine authentication/roles based on approved scope.
- Protect state-changing endpoints and sensitive evidence.
- Configure CORS for intended origins only.
- Use environment configuration for secrets and deployment settings.
- Add request/upload size limits, safe validation, and rate limiting where appropriate.
- Do not deploy Flask's development server as production.
- Document and test database/evidence backup and restore.
- Define evidence retention/access policy.
- Add structured logs with request/event IDs, avoiding unnecessary personal data/secrets.
- Handle DB errors, disk-full conditions, worker failures, and camera failures.
- Review dependency versions and deployment-specific risks.
- Separate local Windows instructions from any server deployment instructions.
- Only implement external notifications, remote deployment, or authentication if required by scope.

Acceptance:
- Security checklist is completed for the actual target environment.
- Backup/restore is tested.
- Failure states are observable and recoverable.
- No secrets are committed; development-only assumptions are documented.

## Phase 16 — Final end-to-end acceptance and documentation
**Status:** Final phase.

Tasks:
- Run all backend tests, frontend tests/lint/build, migration tests, API contract tests, and adapter mocked tests.
- Run adapter integration with validated weights when available.
- Verify the full path:
  1. Create/configure site, camera, and optional zone.
  2. Register/activate a validated compatible model if model inference is in scope.
  3. Process a known helmet-present sample.
  4. Verify observation and no violation/alert.
  5. Process a known no-helmet sample.
  6. Verify event, violation, alert, evidence if enabled, and dashboard update.
  7. Retry same event and verify idempotency.
  8. Acknowledge/resolve the alert.
  9. Verify dashboard metrics and filtered reports.
  10. Restart services and verify persistence.
  11. Test model/API unavailable, invalid input, and camera disconnect as applicable.
  12. Verify all four site/model mappings once all models exist.
- Compare delivered functionality against the approved synopsis and every not-goal.
- Update README, architecture, API contract, training/evaluation guide, troubleshooting, and known limitations.
- Produce a final acceptance report separating Passed, Failed, and Deferred.

Acceptance:
- All agreed checks pass or are explicitly approved as deferred.
- No critical known defect is hidden.
- A new developer can set up the project from docs.
- Platform/model separation remains intact.

---

# E. Global Definition of Done

A phase/feature is complete only when applicable items are satisfied:
- [ ] Implemented in canonical module/file.
- [ ] API/UI behavior and errors documented.
- [ ] Validation and persistence behavior tested.
- [ ] Unit tests added/updated and actually run.
- [ ] Integration checks run where applicable.
- [ ] Existing dashboard and simulated workflow still work.
- [ ] UI loading/empty/error/success states handled.
- [ ] Data relationships and migrations are correct.
- [ ] README and phase log updated.
- [ ] No unapproved scope creep or not-goal violation.
- [ ] Limitations and unverified behavior stated honestly.
- [ ] Windows/VS Code verification commands provided.

# F. Immediate priority order

Do not jump directly to live streams or all four models. Use this order:
1. Re-verify Phase 0 baseline and active files.
2. Complete Phase 1 ingestion hardening.
3. Implement Phase 2 observation persistence if compliant observations are not stored.
4. Complete alert lifecycle/cooldown foundations.
5. Audit the model-independent dashboard, configuration, and reports.
6. Implement evidence storage if required by the approved scope.
7. Make the model registry/contract functional.
8. Continue dataset validation and train the general helmet model separately.
9. Evaluate and approve the general model.
10. Verify YOLO still-image adapter end-to-end.
11. Add temporal deduplication before continuous video.
12. Add stream processing only after image integration is reliable.
13. Train/register/validate the four site-specific models independently when their data are ready.
14. Complete deployment/security readiness appropriate to scope.
15. Run final acceptance.

# G. Required phase handoff report

At the end of every phase, the IDE must report:

## Phase [number] — [name]
- **Status:** Passed / Blocked / Partially complete
- **Files inspected and entry points confirmed:**
- **Files changed:**
- **Database/API changes:**
- **User-visible behavior:**
- **Tests run:** exact commands
- **Actual test results:** no fabricated claims
- **Manual verification:**
- **Regression checks:** dashboard, simulation, alerts, reports as applicable
- **Known limitations:**
- **Scope/not-goal check:**
- **Next phase:**
- **Blockers / decisions needed:**

Do not mark a phase Passed if tests were not run, the active app uses a different file than the edited file, or core functionality regressed.

# H. Immediate IDE instruction — start here

**Do repository inspection first; do not start a large refactor yet.**
1. Confirm the canonical backend file and frontend root.
2. Confirm `POST /api/detections` and inspect the actual schema/database file.
3. Run the four existing tests and report the real output.
4. Confirm dashboard and simulated violation flow still work.
5. Inspect `backend/model_adapter/yolo_adapter.py` and optional model requirements.
6. Inspect the real dataset YAML/class names if present; do not guess them.
7. Read the approved final synopsis and its explicit not-goals.
8. Produce a baseline report and list discrepancies between repository and roadmap.
9. Then start Phase 1 hardening.

**Immediate objective:** keep the verified ingestion endpoint stable, finish the model-independent platform foundation, and integrate trained models only after dataset/class mapping and evaluation are ready. Do not integrate untrained weights, do not start live camera processing yet, and do not train four models simultaneously.
