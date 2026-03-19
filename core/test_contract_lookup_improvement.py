import os
import pytest
from core.contract_lookup import find_contract_by_gps

# Define constants for the test database and mock data
DB_PATH = os.environ.get("ARIA_DB_PATH", "./aria.db")

# Sample data from db/seed.py for "Old Madras Road - KR Puram to Tin Factory"
# GPS Min Lat: 12.9694, Max Lat: 12.9975
# GPS Min Lon: 77.6780, Max Lon: 77.7143

def test_find_contract_success():
    """Test find_contract_by_gps with coordinates that are within a segment's boundaries."""
    # Central coordinate within the segment
    lat, lon = 12.9800, 77.6950
    contract = find_contract_by_gps(lat, lon, DB_PATH)

    assert contract is not None
    assert contract.segment_name == "Old Madras Road - KR Puram to Tin Factory"
    assert contract.contractor_name == "SkyBuild Infrastructure"

def test_find_contract_out_of_bounds():
    """Test find_contract_by_gps with coordinates that are completely out of bounds."""
    # Latitude and Longitude 0.0, 0.0 should not match any segment in Bengaluru
    lat, lon = 0.0, 0.0
    contract = find_contract_by_gps(lat, lon, DB_PATH)

    assert contract is None

def test_find_contract_just_outside_boundary_lat_low():
    """Test find_contract_by_gps with coordinates just below the minimum latitude of a segment."""
    # Min lat is 12.9694. Testing with 12.9693
    lat, lon = 12.9693, 77.6950
    contract = find_contract_by_gps(lat, lon, DB_PATH)

    assert contract is None

def test_find_contract_just_outside_boundary_lat_high():
    """Test find_contract_by_gps with coordinates just above the maximum latitude of a segment."""
    # Max lat is 12.9975. Testing with 12.9976
    lat, lon = 12.9976, 77.6950
    contract = find_contract_by_gps(lat, lon, DB_PATH)

    assert contract is None

def test_find_contract_just_outside_boundary_lon_low():
    """Test find_contract_by_gps with coordinates just below the minimum longitude of a segment."""
    # Min lon is 77.6780. Testing with 77.6779
    lat, lon = 12.9800, 77.6779
    contract = find_contract_by_gps(lat, lon, DB_PATH)

    assert contract is None

def test_find_contract_just_outside_boundary_lon_high():
    """Test find_contract_by_gps with coordinates just above the maximum longitude of a segment."""
    # Max lon is 77.7143. Testing with 77.7144
    lat, lon = 12.9800, 77.7144
    contract = find_contract_by_gps(lat, lon, DB_PATH)

    assert contract is None

def test_find_contract_exact_boundary_min():
    """Test find_contract_by_gps with coordinates exactly at the minimum boundary (inclusive)."""
    # Min lat: 12.9694, Min lon: 77.6780
    lat, lon = 12.9694, 77.6780
    contract = find_contract_by_gps(lat, lon, DB_PATH)

    assert contract is not None
    assert contract.segment_name == "Old Madras Road - KR Puram to Tin Factory"

def test_find_contract_exact_boundary_max():
    """Test find_contract_by_gps with coordinates exactly at the maximum boundary (inclusive)."""
    # Max lat: 12.9975, Max lon: 77.7143
    lat, lon = 12.9975, 77.7143
    contract = find_contract_by_gps(lat, lon, DB_PATH)

    assert contract is not None
    assert contract.segment_name == "Old Madras Road - KR Puram to Tin Factory"
