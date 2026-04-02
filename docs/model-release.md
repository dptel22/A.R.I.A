# Model Release Note

The production YOLO weights for A.R.I.A. are intentionally **not committed to git**.

## Recommended release asset

Upload the trained model as a GitHub Release asset named:

`aria_stage1.pt`

Recommended location for reviewers:

- Latest release asset URL:
  `https://github.com/dptel22/A.R.I.A/releases/latest/download/aria_stage1.pt`

## Local download

From the project root:

```bash
python -m tools.download_model
```

This writes the file to the current `ARIA_MODEL_PATH` default:

`./aria_stage1.pt`

## Why this stays out of git

- Keeps the repository lightweight
- Avoids large-binary churn in source control
- Lets reviewers run the seeded demo without downloading the model first
- Makes the GitHub repo feel more professional and maintainable
