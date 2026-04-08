# Future MVP Notes

## Correct End-to-End Product Flow

This system should evolve into an automated municipal road-inspection review platform.

### Intended workflow

1. Government footage is collected through the approved field process.
2. The system ingests footage automatically at the end of the day.
3. The system extracts frames or inspection samples from the footage.
4. The detection pipeline scans those frames for road damage.
5. The system maps detections, using camera geolocation, to road segments and contracts.
6. The system checks whether the matched road segment is under Defect Liability Period (DLP).
7. If the road is under DLP, the case is flagged to the municipal engineer for review.
8. If the road is not under DLP, a future workflow should route it to a municipal repair team.
9. The system creates a draft case with evidence, severity, contract match, DLP status, and recommendation.
10. A municipal engineer reviews the draft and chooses an action.

### Engineer actions

- No action
- Issue notice
- Block payment
- Escalate for manual inspection

## MVP Direction

The MVP should not be centered around manual image upload as the main product flow.

The MVP should instead focus on:

- Automated ingestion of end-of-day footage or image batches
- Detection and severity scoring
- Geolocation-to-contract matching
- DLP-aware flagging
- Draft case generation
- Human review and approval workflow

## Frontend Direction

Replace the current Streamlit review experience with a proper municipal engineer web dashboard.

### Core pages

- Review Queue
  Shows flagged DLP-related cases that need engineer review
- Case Detail
  Shows evidence, location, road segment, contract, DLP status, severity, and recommended action
- Decision History
  Shows previously reviewed cases and audit trail
- Future: Non-DLP Repair Queue
  Shows cases that should be routed for municipal repair operations

## Backend Features To Add

### Data model

- `cases` table for draft reviewable cases
- `case_decisions` table for engineer actions and audit history
- Optional `ingestion_runs` table for tracking nightly processing jobs

### Processing pipeline

- Batch ingestion job for image folders first
- Video ingestion support later
- Frame extraction or sampling from video footage
- Automatic case creation from detections
- Recommendation engine based on severity + DLP status

### API additions

- Review queue endpoint
- Case detail endpoint
- Decision submit endpoint
- Decision history endpoint

## Demo MVP Plan

To make the system demo-stable:

1. Simulate end-of-day processing using a folder of curated demo images.
2. Run detection and contract matching automatically over that folder.
3. Create draft cases in the database.
4. Let the municipal engineer review those cases in the web dashboard.
5. Record engineer decisions for audit and demo playback.

## Notes

- Human review is required before enforcement action.
- Payment blocking should be an engineer-approved action, not an automatic system outcome.
- Non-DLP routing to municipal repair teams is a future update.
