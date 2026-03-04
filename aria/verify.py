"""Quick verification script for A.R.I.A. API endpoints."""
import requests
import json

BASE = "http://localhost:8000"

# 1. Health
r = requests.get(f"{BASE}/health")
print("Health:", r.json())

# 2. Segments
r = requests.get(f"{BASE}/segments")
segs = r.json()
print(f"Segments ({len(segs)}):", [s["segment_name"] for s in segs])

# 3. POST detection — MG Road coordinates, inside SEG001
payload = {
    "gps_lat": 12.9735,
    "gps_lon": 77.6130,
    "confidence": 0.87,
    "bbox": [340, 480, 640, 620],
    "frame_width": 1280,
    "frame_height": 720,
    "frame_path": None,
}
r = requests.post(f"{BASE}/detections", json=payload)
det = r.json()
print("Detection created:")
print(json.dumps(det, indent=2))

det_id = det["detection_id"]

# 4. List detections
r = requests.get(f"{BASE}/detections")
print(f"All detections: {len(r.json())}")

# 5. Approve
r = requests.post(f"{BASE}/detections/{det_id}/approve",
                  json={"approved_by": "Engineer Priya"})
notice = r.json()
print("Approved notice:")
print(json.dumps(notice, indent=2))

# 6. List notices
r = requests.get(f"{BASE}/notices")
notices = r.json()
print(f"Total notices: {len(notices)}")
if notices:
    print("PDF path:", notices[0]["pdf_path"])

# 7. Test reject another detection
payload2 = {
    "gps_lat": 12.9600,
    "gps_lon": 77.7020,
    "confidence": 0.55,
    "bbox": [100, 500, 200, 560],
    "frame_width": 1280,
    "frame_height": 720,
}
r = requests.post(f"{BASE}/detections", json=payload2)
det2 = r.json()
det2_id = det2["detection_id"]
r = requests.post(f"{BASE}/detections/{det2_id}/reject")
print("Rejected:", r.json())
