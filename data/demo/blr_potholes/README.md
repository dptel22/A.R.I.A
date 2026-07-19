# BLR potholes demo data

This folder keeps lightweight metadata in git. Downloaded images and generated predictions are local artifacts and are ignored by git.

Populate a small local sample:

```bash
python -m scripts.download_blr_potholes --limit 50
```

Run a bounded benchmark:

```bash
python -m scripts.run_benchmark --limit 50
```
