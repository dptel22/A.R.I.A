# A.R.I.A GBA 4-Class Fine-Tuning Spec V3

## Summary
Fine-tune one production model from `models/aria_stage1.pt` for Bengaluru/GBA road-defect detection across all 4 RDD classes:

- `0 longitudinal_crack` / RDD `D00`
- `1 transverse_crack` / RDD `D10`
- `2 alligator_crack` / RDD `D20`
- `3 pothole` / RDD `D40`

Optimize one product stream for Bengaluru’s real input mix: citizen photo uploads plus municipal road-camera imagery. Keep `aria_stage1.pt` as the fallback until the new model wins side-by-side.

## Stage 2 Diagnosis
Document this in the notebook before training:

Stage 2 likely collapsed because the fine-tune dataset and validation design broke the 4-class problem. Evidence: transverse cracks had only 13 real images but were inflated to ~1,500 duplicate/symlinked copies; IIT validation omitted transverse cracks, so collapse was invisible during model selection; the fine-tune narrowed from broad RDD2022 to IIT/RDD-India and then degraded on held-out RDD generalization. Hyperparameters may have contributed, but invalid balancing plus incomplete validation is the primary failure.

## Dataset Composition
Use this fixed mix:

- 40% RDD2022 all-country 4-class data.
- 20% real India/GBA road-camera data.
- 30% citizen-photo-derived defect data using content/perspective-aware compositing.
- 10% hard negatives.

Rules:
- Citizen-photo data is a primary domain, not a minor supplement.
- If GBA road-camera data is unavailable, use RDD2022 India only as a weak proxy and label it clearly.
- Chase the BBMP/ELCITA vehicle-camera source once before falling back.
- BLR unlabeled photos remain an unseen smoke set unless a separate subset is manually annotated.
- Hard negatives must include manholes, patched asphalt, shadows, puddles, lane markings, debris, speed breakers, road joints, and construction texture.

## Augmentation Method
Implement citizen-photo adaptation using copy-paste compositing, not simple resize/crop.

Reference method:
- Cite “Cut-and-Paste with Precision: a Content and Perspective-aware Data Augmentation for Road Damage Detection,” arXiv `2406.18586`.

Implementation:
- Extract/mask citizen-photo defect regions.
- Paste defects onto real RDD2022/GBA road-scene backgrounds.
- Match road surface content and perspective before accepting a composite.
- Randomize defect scale to roughly 2-25% of frame area.
- Apply perspective transform, edge blending, brightness/contrast matching, compression, blur, wet-road effects, and shadow variation.
- Preserve transformed YOLO boxes.
- Reject visually impossible composites.

## Experiment Matrix
Run controlled experiments:

1. Baseline: evaluate current `aria_stage1.pt`.
2. Data-only fine-tune: new dataset mix, conservative hyperparams.
3. Freeze comparison: `freeze=0` vs `freeze=3`.
4. Image-size comparison: `imgsz=640` vs `imgsz=960`.
5. Augmentation comparison: normal YOLO vs YOLO + content/perspective-aware copy-paste.

Default training:
- base: `aria_stage1.pt`
- epochs: `80`
- patience: `20`
- lr0: `0.0005`
- optimizer: `AdamW`
- imgsz: `960`, fallback `640`
- seed: fixed
- output: `aria_gba_4class_v1.pt`

## Evaluation Gates
Evaluate every candidate on:

- `RDD2022 heldout`: catastrophic-forgetting check.
- `India/GBA road-camera val`: municipal camera domain.
- `citizen labeled val`: primary upload domain.
- `hard_negative_val`: false-positive control.
- `BLR unlabeled smoke`: detection-rate and manual review only.

Promotion criteria:
- all 4 classes report AP/recall;
- transverse crack does not collapse;
- citizen-photo pothole recall improves over `aria_stage1.pt`;
- RDD heldout mAP does not materially degrade;
- hard-negative false positives stay acceptable;
- backend upload path returns visible detections on known positives.

## Sources
- [RDD2022 / RoadDamageDetector](https://github.com/sekilab/RoadDamageDetector)
- [BBMP Raste Gundi Gamana app](https://play.google.com/store/apps/details?id=com.indigo.bbmp.fixpothole)
- [Indian Express on Raste Gundi Gamana](https://indianexpress.com/article/cities/bangalore/road-pothole-attention-bengaluru-new-app-reporting-potholes-9479340/)
- [BBMP 15 AI-camera vehicles](https://www.deccanherald.com/india/karnataka/bengaluru/bengaluru-civic-body-to-deploy-camera-mounted-vehicles-aito-identify-potholes-3040803)
- [ELCITA road metrics](https://elcita.in/elcita-initiatives/)
- [Content/perspective-aware cut-and-paste paper](https://arxiv.org/abs/2406.18586)
- [2025 road damage detection survey](https://link.springer.com/article/10.1007/s11554-025-01683-1)
- [HRP4K Scientific Data paper](https://www.nature.com/articles/s41597-026-07317-w), used specifically to justify preserving high-resolution perspective-view detail and testing `imgsz=960`, not as Indian/citizen training data.
