# A.R.I.A GBA 4-Class Fine-Tuning Spec V4

## Changelog from V3
- GBA road-camera bucket reclassified: BBMP/ELCITA camera data confirmed **not publicly accessible** (no public dataset, API, or bulk export exists as of this spec). The V3 fallback clause is now the actual plan, not a contingency.
- Citizen-photo bucket sourced from BLR-potholes (`blr-potholes.pages.dev`, backed by `warlockdn/blr-potholes-data`, 1029 unannotated images). Confirmed pothole-heavy / possibly pothole-only — verify before use, do not assume from source name.
- Added a semi-supervised annotation pipeline (seed-label → pseudo-label → filter) to make the citizen bucket usable without hand-boxing all 1029 images.
- Added explicit anti-collapse controls, written directly against the Stage 2 failure mode (duplicated/symlinked class inflation invisible to an incomplete validation set).

## Stage 2 Diagnosis (carried over, still the root-cause reference)
Stage 2 collapsed because the fine-tune dataset and validation design broke the 4-class problem: transverse crack had 13 real images inflated to ~1,500 duplicate/symlinked copies, and IIT validation omitted transverse crack entirely, making the collapse invisible during model selection. Every control in this spec's "Anti-Collapse Controls" section exists to make sure this specific failure mode — and its structural cousins — cannot repeat silently.

## Base Model Decision
Fine-tune from `models/aria_stage1.pt`. Do not retrain Stage 1 from scratch.

Rationale: Stage 1 training data (RDD2022 all-country, ~26.8k images, all 4 classes represented) is unchanged. Stage 1 was not implicated in the Stage 2 collapse. Retraining it would consume compute for a result within noise of the existing checkpoint. `aria_stage1.pt` remains the fallback/rollback target until the new model wins side-by-side on every promotion gate below.

## Dataset Composition (corrected)
- **40% RDD2022 all-country** — unchanged, real, all 4 classes.
- **20% "GBA road-camera"** — labeled explicitly as an **RDD2022-India proxy**, not real municipal camera footage. BBMP/ELCITA data remains a one-time outreach attempt (email/RTI-style request), not a dependency of this training run. Document this substitution plainly in the model card — do not let the dataset table imply four independent domains when there are three.
- **30% citizen-photo composites** — sourced from BLR-potholes via the pseudo-labeling pipeline below. Treat as **pothole-only** unless Step 1 verification (below) finds genuine crack instances in the set. If citizen crack photos are not present, crack composites in this bucket are backfilled from RDD2022/IIT Madras annotated crops, not true citizen photos — label this substitution in the model card too.
- **10% hard negatives** — unchanged (manholes, patched asphalt, shadows, puddles, lane markings, debris, speed breakers, road joints, construction texture).

## Citizen-Photo Annotation Pipeline (semi-supervised, not full manual)
Rationale: this is a documented pattern (teacher-student pseudo-labeling with confidence filtering), not an improvisation — published results on RDD2022 and self-collected pavement datasets show meaningful mAP gains at 10-50% labeled fractions using this exact structure.

1. **Sample check (do first, ~30 min):** pull ~100 random BLR images, manually review. Confirm class composition (pothole-only vs. mixed), check for duplicate/near-duplicate submissions and non-road junk. This determines everything downstream — do not skip it.
2. **Seed annotation:** hand-box ~150-200 images (stratified by whatever Step 1 reveals). This seed set becomes the `citizen labeled val` set required by the evaluation gates below — it is not optional regardless of what happens in later steps.
3. **Pseudo-label the remainder:** use `aria_stage1.pt` (or a light fine-tune on the seed set) as teacher to auto-box the rest of the 1029 images. Apply a confidence threshold; discard low-confidence and abnormally small/noisy boxes.
4. **Manual audit of pseudo-labels:** spot-check a sample of the pseudo-labeled output before it enters training. Do not trust auto-labels blindly — this is where unfiltered pseudo-label noise typically corrupts training in the published pipelines this method is based on.
5. **Mask extraction for compositing:** box-prompted SAM on the confirmed **pothole** boxes only (SAM performs reliably on blob-shaped objects with box prompts). Do not route cracks through SAM — general-purpose segmentation models are documented to perform poorly on thin, low-contrast crack geometry without domain-specific fine-tuning. Crack masks come from RDD2022/IIT Madras annotated crops instead.
6. **Remainder stays in `BLR unlabeled smoke set`** — detection-rate and manual review only, per the evaluation gates, no ground truth required.

## Augmentation Method (unchanged from V3)
Cut-and-paste compositing per "Cut-and-Paste with Precision" (arXiv 2406.18586): extract/mask defect regions, paste onto real RDD2022/GBA-proxy backgrounds, match surface content and perspective, randomize scale to ~2-25% of frame area, apply perspective/blend/brightness/compression/wet-road/shadow variation, preserve transformed YOLO boxes, reject visually impossible composites.

## Anti-Collapse Controls (new — mandatory, not optional)
These exist specifically because the Stage 2 failure was invisible until it was too late. Every one of them is a check that would have caught that failure earlier.

1. **No class inflation via duplication.** If any class's real-image count is being padded with duplicate/symlinked copies rather than genuinely new instances, that is disclosed and capped — never silently accepted as "more data." Track and log real vs. duplicated vs. synthetic instance counts per class before every training run.
2. **Synthetic:real ratio cap per class.** Composite (copy-paste) instances must not exceed a fixed multiple of real instances for any single class (e.g. no more than 3-5x). This is the direct structural fix for the 13-real-to-1,500-fake ratio that caused the original collapse — a cap prevents any one class from becoming almost entirely synthetic without it being a visible, deliberate decision.
3. **Validation must contain all 4 classes, always.** No promotion decision is made against a validation set missing a class — this is exactly what hid the Stage 2 collapse. `citizen labeled val` (from the seed annotation step) must report per-class AP for all 4 classes before this model is compared to `aria_stage1.pt`.
4. **Pseudo-labels never enter a validation set.** Pseudo-labeled data is training-only. Validation/test sets are hand-annotated only, full stop — no exceptions, since pseudo-label noise in a validation set would make the promotion gates themselves unreliable.
5. **Per-class instance count logged at every stage** (raw → after pseudo-labeling → after compositing → final training set) so any collapse in a specific class is visible in a table before training starts, not discovered after evaluation.
6. **Conservative fine-tune hyperparameters retained:** `freeze=3`, low `lr0`, `mixup=0`, `erasing=0` — unchanged from the Stage 2 rehearsal-tuning approach, since these protect thin/rare features (transverse crack) from being overwritten during Indian-domain adaptation.

## Experiment Matrix (unchanged from V3)
1. Baseline: evaluate current `aria_stage1.pt`.
2. Data-only fine-tune: new dataset mix, conservative hyperparams.
3. Freeze comparison: `freeze=0` vs `freeze=3`.
4. Image-size comparison: `imgsz=640` vs `imgsz=960`.
5. Augmentation comparison: normal YOLO vs YOLO + content/perspective-aware copy-paste.

Default training: base `aria_stage1.pt`, epochs `80`, patience `20`, lr0 `0.0005`, optimizer `AdamW`, imgsz `960` (fallback `640`), seed fixed, output `aria_gba_4class_v1.pt`.

## Evaluation Gates (unchanged structure, now enforced by Anti-Collapse Controls above)
- `RDD2022 heldout`: catastrophic-forgetting check.
- `India/GBA road-camera val`: RDD2022-India proxy domain (explicitly labeled as such).
- `citizen labeled val`: hand-annotated BLR subset from the seed step — **must report AP for all 4 classes**, per Anti-Collapse Control #3.
- `hard_negative_val`: false-positive control.
- `BLR unlabeled smoke`: detection-rate and manual review only.

Promotion criteria (unchanged):
- all 4 classes report AP/recall;
- transverse crack does not collapse;
- citizen-photo pothole recall improves over `aria_stage1.pt`;
- RDD heldout mAP does not materially degrade;
- hard-negative false positives stay acceptable;
- backend upload path returns visible detections on known positives.

## Sources
- [RDD2022 / RoadDamageDetector](https://github.com/sekilab/RoadDamageDetector)
- [BLR Potholes live map](https://blr-potholes.pages.dev/)
- [BLR Potholes data source](https://github.com/warlockdn/blr-potholes-data)
- [Content/perspective-aware cut-and-paste paper (arXiv 2406.18586)](https://arxiv.org/abs/2406.18586)
- [YOLOv8-Semi semi-supervised pavement damage detection](https://www.sciencedirect.com/science/article/abs/pii/S0263224125022195)
- [PaveSAM — box-prompted SAM for pavement distress segmentation](https://www.tandfonline.com/doi/full/10.1080/14680629.2024.2374863)
- [BBMP 15 AI-camera vehicles (reference only — data not publicly accessible)](https://www.deccanherald.com/india/karnataka/bengaluru/bengaluru-civic-body-to-deploy-camera-mounted-vehicles-aito-identify-potholes-3040803)
- [ELCITA road metrics (reference only — data not publicly accessible)](https://elcita.in/elcita-initiatives/)
- [HRP4K Scientific Data paper](https://www.nature.com/articles/s41597-026-07317-w), used specifically to justify `imgsz=960`, not as training data.
