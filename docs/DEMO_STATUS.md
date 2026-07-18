# A.R.I.A Demo Status: Pre-Release Overview

This document outlines the current state of the A.R.I.A (Automated Road Inspection & Analytics) model prior to the Bengaluru stakeholder demo, specifically detailing model accuracy, known limitations, and the immediate roadmap.

## 1. Current Model Performance (aria_stage1.pt)

The `aria_stage1.pt` YOLOv11 model has been benchmarked against the `blr_potholes` demo dataset (1,049 images).

**Benchmark Results:**
- **Total Test Images:** 1,049
- **At Confidence ≥ 0.25:** 607 images (57.9%) had at least one valid detection (1,101 total bounding boxes).
- **At Confidence ≥ 0.12:** 790 images (75.3%) had at least one valid detection (2,301 total bounding boxes).

*Note: The demo inference script disables the dashcam top-crop (`crop=False`) as these are close-up images.*

## 2. The Domain Gap (Dashcam vs. Close-up)

While the system is functional, there is a measurable drop in confidence scores (necessitating a lower 0.12 threshold to capture 75% of the images). This is due to a **domain gap**:

1. **Training Data:** `aria_stage1.pt` was trained primarily on dashcam-style road imagery (wide-angle, lower angle, capturing the whole road surface).
2. **Demo Data (`blr_potholes`):** The demo images represent citizen-submitted photos (close-up, taken by pedestrians or two-wheeler riders, pointing directly downwards at the defect).

Because the scale, aspect ratio, and background context of the defects differ heavily from the training distribution, the model is less confident. **We do not recommend artificially lowering the threshold in production** just to increase the detection count, as this introduces false positives. For the purpose of the demo, running at `conf=0.12` or `0.25` is acceptable to demonstrate the end-to-end pipeline, provided stakeholders understand the context.

## 3. Civic Authority Reorganization

As of September 2025, the Bruhat Bengaluru Mahanagara Palike (BBMP) was dissolved. A.R.I.A has been fully updated to support the new civic structure:
- **Apex Body:** Greater Bengaluru Authority (GBA)
- **City Corporations:** The system dynamically supports the five new corporations (Bengaluru North, South, East, West, Central).
- Hardcoded BBMP strings have been removed from the PDF Notice generator.

## 4. Roadmap (Stage 2)

To bridge the domain gap and improve citizen-submitted photo analysis:
- **Stage 2 Retraining:** Fine-tune `aria_stage1.pt` using a mix of dashcam and the `blr_potholes` close-up dataset.
- **Target Metrics:** Achieve >90% recall on close-up imagery at a standard `0.25` or `0.50` confidence threshold.
- **Productionization:** Restrict production deployments to `conf=0.25` minimum to prevent automated notices being generated for false positives.
