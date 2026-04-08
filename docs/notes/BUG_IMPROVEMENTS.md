# Bug Improvements

This file captures the main code review findings that should be addressed to make A.R.I.A. more correct, reliable, and easier to evolve into a stable MVP.

## Priority P1

### 1. Inference failures are reported as clean inspections

- File: `api/routes.py`
- Area: `/detect` flow
- Problem:
  `run_pipeline()` returns an empty list when inference fails, and `/detect` treats an empty list as "No road damage detected".
  This means bad images, PIL decode errors, model failures, or inference bugs can silently become false negatives.
- Improvement:
  Separate "no detections" from "pipeline failure".
  The inference layer should return a structured success/error result or raise a controlled exception.
  The API should return an operational error when inference fails instead of reporting a clean inspection.

### 2. Inspection events do not snapshot contract or DLP state

- File: `db/schema.py`
- Area: inspection persistence design
- Problem:
  `inspection_events` stores only segment and coordinates, while contract and DLP status are recomputed later from the current contracts table.
  If contracts are edited or replaced, old inspections can be associated with the wrong contractor or DLP state.
- Improvement:
  Snapshot contract-related state at inspection time.
  Store fields such as:
  - `contract_id`
  - `contractor_name`
  - `dlp_end_date`
  - `is_dlp_active`
  - optional decision/recommendation snapshot fields

## Priority P2

### 3. Dashboard notice link cannot satisfy API auth

- File: `frontend/pages/dashboard.py`
- Area: notice access flow
- Problem:
  The dashboard renders a plain browser link to `/api/v1/notices/{id}`, but that endpoint requires `x-api-key`.
  Opening the link directly in the browser will usually return `401`.
- Improvement:
  Do one of the following:
  - fetch the PDF through the frontend with the API key and expose it as a download
  - add a backend proxy route for authenticated frontend use
  - redesign notice access so browser navigation does not depend on custom headers

### 4. Frontend upload path defeats backend MIME validation

- File: `frontend/utils.py`
- Area: upload request construction
- Problem:
  The UI accepts `webp` uploads, but the client posts every file as `image/jpeg`.
  The backend then trusts the submitted content type.
  This makes validation inconsistent and allows unsupported inputs to reach the pipeline.
- Improvement:
  Preserve the actual file MIME type from the uploaded file.
  Align frontend allowed file types with backend allowed file types.
  Add server-side content validation beyond the provided MIME header where possible.

### 5. Zero-detection inspections are dropped from history

- File: `api/routes.py`
- Area: inspection audit trail
- Problem:
  When no detections are returned, `/detect` exits early without inserting an `inspection_events` row.
  This removes evidence that the road was processed at all.
- Improvement:
  Always persist an inspection event, even when there are zero detections.
  This is important for audit history, coverage reporting, and future automated footage ingestion workflows.

### 6. PDF shows internal enum names instead of public severity labels

- File: `core/notice_generator.py`
- Area: user-facing PDF output
- Problem:
  The PDF uses `detection_data.severity.value.upper()`.
  Because enum values are `damage_low`, `damage_high`, and so on, the PDF shows internal labels like `DAMAGE_CRITICAL`.
- Improvement:
  Render business-facing labels such as:
  - `LOW`
  - `MEDIUM`
  - `HIGH`
  - `CRITICAL`
  Keep internal enum representation separate from display formatting.

## Priority P3

### 7. Detector hardcodes class-id mapping instead of reading model metadata

- File: `inference/detector.py`
- Area: model integration
- Problem:
  The detector assumes YOLO class IDs `0-3` always map to the current four defect labels.
  If the model is retrained or exported with a different class order, detections can be silently mislabeled.
- Improvement:
  Read labels from model metadata such as `model.names` instead of hardcoding them in the code.
  Add validation on startup to ensure the expected classes are present.

## Broader Improvement Themes

### Reliability

- Distinguish pipeline failures from successful no-defect results
- Improve auditability by persisting every inspection attempt
- Ensure contract/DLP logic is historically stable

### Architecture

- Reduce recomputation of contract state after inspections are stored
- Keep user-facing display labels separate from internal enum values
- Avoid hardcoded ML metadata when the model already provides it

### Frontend/API Contract

- Make auth-compatible PDF access work in the UI
- Keep accepted file formats and posted MIME types consistent
- Improve the interface so review actions match actual engineer workflows

## Suggested Fix Order

1. Fix inference failure handling
2. Snapshot contract and DLP state at inspection time
3. Persist zero-detection inspections
4. Fix PDF access flow in the frontend
5. Fix MIME/type handling for uploads
6. Fix severity label rendering in notices
7. Replace hardcoded detector class mapping with model metadata

## Additional Review Findings

### 8. Contracts schema cannot represent repeat awards cleanly

- File: `db/schema.py`
- Area: contract history modeling
- Problem:
  The `contracts` table enforces `UNIQUE (road_segment_id, contractor_name)`.
  That prevents storing multiple contracts over time for the same contractor on the same road segment.
  This conflicts with the code path that tries to retrieve the "latest" contract.
- Improvement:
  Redesign contract uniqueness around a real contract identifier or time-bounded contract period.
  Allow repeated awards to the same contractor on the same segment when they represent different contract records.

### 9. Detections endpoint reports page size as the total

- File: `api/routes.py`
- Area: dashboard pagination and summary metrics
- Problem:
  `/detections` returns `total_returned = len(results)` after `LIMIT/OFFSET`.
  The frontend treats that value like the total number of matching inspections.
  Once there are more results than a single page, totals and pagination hints become misleading.
- Improvement:
  Return both:
  - current page size
  - full total count of matching rows
  Add a separate count query for the filtered dataset.

### 10. Claimed GPS tolerance is never applied

- File: `api/routes.py`
- Area: road segment lookup
- Problem:
  The route defines latitude and longitude tolerance constants and the docs/UI describe a 20m tolerance.
  But the SQL query only checks strict bounding-box containment and never uses those tolerance values.
- Improvement:
  Either:
  - actually apply the tolerance in the SQL lookup
  - or remove the claim from the docs/UI if strict containment is the intended behavior

### 11. Detect response exposes raw contractor email

- File: `api/routes.py`
- Area: API response design and privacy
- Problem:
  The `/detect` response returns raw `contractor_email`.
  This expands PII exposure unnecessarily, especially since the domain model already supports masked public output.
- Improvement:
  Return masked contractor contact details in normal API responses.
  Reserve raw contractor email for internal-only workflows where it is explicitly needed.

### 12. Frontend hardcodes the backend origin

- File: `frontend/utils.py`
- Area: deployment configuration
- Problem:
  The frontend assumes `http://localhost:8000`, and page code also rebuilds absolute backend URLs directly.
  This makes staging, reverse-proxy deployment, containerization, and port changes brittle.
- Improvement:
  Move backend base URL into configuration.
  Use one shared source for backend origin instead of repeating absolute URLs in page components.

### 13. Severity-to-action policy is not part of runtime behavior

- File: `core/severity.py`
- Area: business policy integration
- Problem:
  `determine_action()` defines the mapping from severity to business action, but it is only used in tests and a smoke script.
  The main API flow does not expose or depend on this policy.
- Improvement:
  Integrate severity-to-action policy into the runtime pipeline.
  Use it when building detection results, draft cases, or recommendations so the business logic has one authoritative implementation.
