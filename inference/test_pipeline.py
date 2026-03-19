import logging
from inference.pipeline import run_pipeline

def test_run_pipeline_no_model(caplog):
    """
    Test that when run_pipeline is called with model=None, it safely returns
    an empty list and logs the expected warning message without attempting to
    load PIL, numpy, or YOLO.
    """
    img_bytes = b"dummy_bytes"

    with caplog.at_level(logging.WARNING):
        result = run_pipeline(img_bytes, model=None)

    assert result == []

    # Assert that the correct log message is present in the caplog records
    assert "run_pipeline called with no model loaded" in [rec.message for rec in caplog.records]
