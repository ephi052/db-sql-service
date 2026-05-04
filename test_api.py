#!/usr/bin/env python3
"""
Test script for SQLite Ingestion Service API
"""

import requests
import json
import sys
import os
from pathlib import Path

__test__ = False

BASE_URL = os.getenv("BASE_URL", "https://stability-armored-friction.ngrok-free.dev")
API_KEY = os.getenv("API_KEY", "test-api-key-12345")

headers = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}
EVENT_STID = "12345"
EVENT_EXNUM = "EX001"

def test_create_event():
    """Test POST /v1/events"""
    print("\n" + "="*60)
    print("TEST 1: Create Event (POST /v1/events)")
    print("="*60)
    
    payload = {
        "source": "test-source",
        "payload": {
            "stid": EVENT_STID,
            "exnum": EVENT_EXNUM,
            "table": {
                "name": "test_table",
                "rows": 100,
                "columns": ["id", "name", "value"]
            }
        }
    }
    
    print(f"\nRequest Body:")
    print(json.dumps(payload, indent=2))
    
    response = requests.post(
        f"{BASE_URL}/v1/events",
        json=payload,
        headers=headers
    )
    
    print(f"\nStatus Code: {response.status_code}")
    print(f"Response:")
    data = response.json()
    print(json.dumps(data, indent=2))
    
    if response.status_code == 200:
        print("\n✓ Event created successfully!")
        return data.get("id")
    else:
        print("\n✗ Failed to create event")
        return None


def test_get_event():
    """Test GET /v1/events/{event_id}"""
    print("\n" + "="*60)
    print("TEST 2: Retrieve Event (GET /v1/events/{event_id})")
    print("="*60)
    
    url = f"{BASE_URL}/v1/events/{EVENT_STID}?exnum={EVENT_EXNUM}"
    print(f"\nRequest URL: {url}")
    
    response = requests.get(
        url,
        headers=headers
    )
    
    print(f"\nStatus Code: {response.status_code}")
    print(f"Response:")
    print(json.dumps(response.json(), indent=2))
    
    if response.status_code == 200:
        print("\n✓ Event retrieved successfully!")
    else:
        print("\n✗ Failed to retrieve event")


def test_list_events():
    """Test GET /v1/events"""
    print("\n" + "="*60)
    print("TEST 3: List Events (GET /v1/events)")
    print("="*60)
    
    url = f"{BASE_URL}/v1/events?limit=10&offset=0"
    print(f"\nRequest URL: {url}")
    
    response = requests.get(
        url,
        headers=headers
    )
    
    print(f"\nStatus Code: {response.status_code}")
    print(f"Response (showing first 2 events):")
    data = response.json()
    print(json.dumps(data[:2] if len(data) > 2 else data, indent=2))
    print(f"Total events in response: {len(data)}")
    
    if response.status_code == 200:
        print("\n✓ Events listed successfully!")
    else:
        print("\n✗ Failed to list events")


def test_health():
    """Test GET /health"""
    print("\n" + "="*60)
    print("TEST 0: Health Check (GET /health)")
    print("="*60)
    
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        print(f"\nStatus Code: {response.status_code}")
        
        if response.status_code == 502:
            print("✗ Got 502 Bad Gateway")
            print("  - Make sure docker-compose is running: docker-compose ps")
            print("  - Make sure ngrok is running: ngrok http 80")
            print("  - Update BASE_URL in test script with the ngrok URL")
            return False
        
        try:
            data = response.json()
            print(f"Response: {data}")
            return response.status_code == 200
        except:
            print(f"Response (raw): {response.text[:200]}")
            return response.status_code == 200
            
    except requests.exceptions.ConnectionError as e:
        print(f"\n✗ Connection failed: {e}")
        print("  Make sure ngrok is running: ngrok http 80")
        return False
    except Exception as e:
        print(f"\n✗ Error: {e}")
        return False


def create_test_image(filename="test_image.png"):
    """Create a minimal test PNG image"""
    # Minimal 1x1 PNG (red pixel)
    png_data = bytes([
        0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,  # PNG signature
        0x00, 0x00, 0x00, 0x0D,                            # IHDR chunk size
        0x49, 0x48, 0x44, 0x52,                            # IHDR
        0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,  # 1x1
        0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,  # 8-bit RGB
        0xDE,                                              # CRC
        0x00, 0x00, 0x00, 0x0C,                            # IDAT chunk size
        0x49, 0x44, 0x41, 0x54,                            # IDAT
        0x08, 0xD7, 0x63, 0xF8, 0xCF, 0xC0, 0x00, 0x00,
        0x03, 0x01, 0x01, 0x00,
        0x18, 0xDD, 0x8D, 0xB4,                            # CRC
        0x00, 0x00, 0x00, 0x00,                            # IEND chunk size
        0x49, 0x45, 0x4E, 0x44,                            # IEND
        0xAE, 0x42, 0x60, 0x82                             # CRC
    ])
    
    with open(filename, "wb") as f:
        f.write(png_data)
    
    return filename


def test_upload_image():
    """Test POST /v1/images"""
    print("\n" + "="*60)
    print("TEST 2: Upload Image (POST /v1/images)")
    print("="*60)
    
    # Create a test image
    image_file = create_test_image()
    
    try:
        with open(image_file, "rb") as f:
            files = {"file": (image_file, f, "image/png")}
            response = requests.post(
                f"{BASE_URL}/v1/images",
                files=files,
                headers={"X-API-Key": API_KEY},
            )
        
        print(f"\nStatus Code: {response.status_code}")
        print(f"Response:")
        data = response.json()
        print(json.dumps(data, indent=2))
        
        if response.status_code == 201:
            print("\n✓ Image uploaded successfully!")
            return data.get("image_id"), data.get("image_url")
        else:
            print("\n✗ Failed to upload image")
            return None, None
    finally:
        # Clean up test image
        Path(image_file).unlink(missing_ok=True)


def test_retrieve_image(image_id):
    """Test GET /v1/images/{image_id}"""
    print("\n" + "="*60)
    print("TEST 3: Retrieve Image (GET /v1/images/{image_id})")
    print("="*60)
    
    url = f"{BASE_URL}/v1/images/{image_id}"
    print(f"\nRequest URL: {url}")
    
    response = requests.get(url)
    
    print(f"\nStatus Code: {response.status_code}")
    print(f"Content-Type: {response.headers.get('content-type')}")
    print(f"Content-Length: {len(response.content)} bytes")
    
    if response.status_code == 200:
        print("✓ Image retrieved successfully!")
        return True
    else:
        print("✗ Failed to retrieve image")
        print(f"Response: {response.text}")
        return False


def test_delete_image(image_id):
    """Test DELETE /v1/images/{image_id}"""
    print("\n" + "="*60)
    print("TEST 4: Delete Image (DELETE /v1/images/{image_id})")
    print("="*60)

    response = requests.delete(
        f"{BASE_URL}/v1/images/{image_id}",
        headers={"X-API-Key": API_KEY},
    )

    print(f"\nStatus Code: {response.status_code}")
    if response.status_code == 204:
        print("✓ Image deleted")
        return True

    print(f"✗ Failed to delete image: {response.text}")
    return False


if __name__ == "__main__":
    print("\n🧪 SQLite Ingestion Service - API Tests")
    print(f"Base URL: {BASE_URL}")
    print(f"API Key: {API_KEY}")
    
    # Check health first
    if not test_health():
        sys.exit(1)
    
    # Test image upload
    print("\n" + "="*60)
    print("IMAGE TESTS")
    print("="*60)
    image_id, image_url = test_upload_image()
    
    if image_id:
        # Retrieve the image
        test_retrieve_image(image_id)
        test_delete_image(image_id)
    
    # Test events
    print("\n" + "="*60)
    print("EVENT TESTS")
    print("="*60)
    
    # Create an event
    event_id = test_create_event()
    
    if event_id:
        # Retrieve the event
        test_get_event()
        
        # List all events
        test_list_events()
    
    print("\n" + "="*60)
    print("✓ Test script completed")
    print("="*60 + "\n")
