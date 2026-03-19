"""
pipeline/setup_model.py — A.R.I.A. Model Setup
Clones the RoadDamageDetection repo and copies the pre-trained best.pt
weights to pipeline/aria_best_v0.pt.
"""

import glob
import os
import shutil
import subprocess
import sys
import tempfile

# ─────────────────────────────────────────────────────────────
# Configuration — defined once, never hardcoded elsewhere
# ─────────────────────────────────────────────────────────────
MODEL_DEST = "pipeline/aria_best_v0.pt"
REPO_URL = "https://github.com/oracl4/RoadDamageDetection"


def setup_model(dest_path: str = MODEL_DEST) -> str:
    """
    Download the pre-trained road damage detection model.

    Clones the oracl4/RoadDamageDetection repository into a temporary
    directory, searches for any 'best.pt' checkpoint file, and copies
    it to the destination path inside the pipeline/ directory.

    If the model file already exists at dest_path, the function skips
    all network operations and returns immediately.

    Args:
        dest_path (str): Target path for the downloaded model weights.

    Returns:
        str: Absolute path to the model file.

    Raises:
        FileNotFoundError: If no best.pt is found after cloning the repo.
        RuntimeError: If git clone fails.
    """
    # Guard: skip if model already downloaded
    if os.path.exists(dest_path):
        print(f"✅ Model already exists at '{dest_path}' — skipping download.")
        return os.path.abspath(dest_path)

    # Ensure destination directory exists
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        clone_target = os.path.join(tmpdir, "RoadDamageDetection")
        print(f"📥 Cloning {REPO_URL} …")

        result = subprocess.run(
            ["git", "clone", "--depth", "1", REPO_URL, clone_target],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"git clone failed (exit {result.returncode}):\n{result.stderr}"
            )

        print("✅ Clone complete. Searching for best.pt …")

        # Search recursively for any .pt file, looking for YOLOv8_Small_RDD.pt or similar
        matches = glob.glob(os.path.join(
            clone_target, "**", "YOLOv8_Small_RDD.pt"), recursive=True)

        if not matches:
            # Fallback to any .pt if we can't find that specific one
            matches = glob.glob(os.path.join(
                clone_target, "**", "*.pt"), recursive=True)
            if not matches:
                raise FileNotFoundError(
                    "No '.pt' model file found inside the cloned repository. "
                    "The repo structure may have changed — please check manually."
                )

        # Use the first match (typically there's only one)
        src_pt = matches[0]
        print(f"📂 Found weights: {src_pt}")

        shutil.copy2(src_pt, dest_path)
        print(f"✅ Model ready at '{dest_path}'")

    return os.path.abspath(dest_path)


if __name__ == "__main__":
    try:
        path = setup_model()
        size_mb = os.path.getsize(path) / (1024 * 1024)
        print(f"   File size: {size_mb:.1f} MB")
    except Exception as e:
        print(f"❌ Model setup failed: {e}", file=sys.stderr)
        sys.exit(1)
