# Bug Improvements & Resolved Issues

This file documents the status of code quality issues, bug fixes, and improvements in the A.R.I.A. codebase.

---

## 🔴 ACTIVE ISSUES

### 1. Model Artifact Mismatch & Missing Checkpoint in Release
- **Status:** **OPEN / WORK IN PROGRESS**
- **File(s):** `aria/api/app.py`, `scripts/download_model.py`, `scripts/demo_infer.py`
- **Problem:** The project had conflicting defaults between `aria_stage1.pt` and `aria_best_v1.pt`, and some release/documentation paths pointed to missing assets.
- **Remediation:** Runtime and docs now standardize on the current stable `aria_stage1.pt` model while keeping experimental/future weights local or explicitly configured through `ARIA_MODEL_PATH`.

### 2. Diagnostic Script Crops Close-up Images
- **Status:** **RESOLVED**
- **File:** `scripts/demo_infer.py`
- **Problem:** `crop_bottom_80_percent` was unconditionally applied to images in the diagnostic script. This cropped out defect areas in close-up images.
- **Remediation:** Gated crop behind a CLI `--crop` flag and disabled it by default to support close-up evaluation cleanly.

### 3. Misleading GPS Error Message
- **Status:** **RESOLVED**
- **File:** `aria/services/inspection_service.py:366-374`
- **Problem:** If a coordinate falls outside the mapped road segments, the system returned a 404 with the suggestion "Verify GPS signal and retry outdoors." This is a false suggestion since the issue is lack of database coverage, not GPS quality.
- **Remediation:** Changed error message detail to "No mapped road segment found at these coordinates" and suggestion to contact the administrator to add database coverage.

---

## 🟢 RESOLVED ISSUES (HISTORICAL REFRACTOR STATUS)

### 4. Inference failures reported as clean inspections
- **Status:** **RESOLVED**
- **File:** `aria/services/inspection_service.py`
- **Fix:** Pipeline execution returns structured status. If status is `FAILED`, `raise_file_too_large` or operational errors are returned rather than persisting 0 detections.

### 5. Inspection events do not snapshot contract state
- **Status:** **RESOLVED**
- **File:** `aria/db/schema.py`
- **Fix:** Added `contract_id_snapshot`, `contractor_name_snapshot`, `contractor_email_snapshot`, `dlp_end_date_snapshot`, and `is_dlp_active_snapshot` to the `inspection_events` table schema to prevent historical inspections from breaking when contracts change.

### 6. Frontend upload path defeats backend MIME validation
- **Status:** **RESOLVED**
- **Fix:** Native `File.type` is preserved in the React frontend upload payload instead of posting everything as `image/jpeg`.

### 7. Zero-detection inspections dropped from history
- **Status:** **RESOLVED**
- **Fix:** Persisted all inspections in `inspection_events` regardless of whether detections were found, ensuring audit trail integrity.

### 8. PDF shows internal enum values
- **Status:** **RESOLVED**
- **Fix:** PDF generators render clean display labels (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`) rather than internal database strings.

### 9. Detector hardcodes class-id mapping
- **Status:** **RESOLVED**
- **Fix:** Model metadata is read dynamically using `model.names`.

### 10. GPS tolerance is never applied
- **Status:** **RESOLVED**
- **Fix:** Lookup query in `_find_segment` correctly utilizes `_LAT_DELTA` and `_LNG_DELTA` constants.

### 11. Raw contractor email exposed
- **Status:** **RESOLVED**
- **Fix:** Added `_mask_email()` logic in notice serialization routes to protect contractor PII.

### 12. Frontend hardcodes localhost:8000
- **Status:** **RESOLVED**
- **Fix:** Frontend consumes backend URL via `VITE_ARIA_API_URL` environment configuration.
