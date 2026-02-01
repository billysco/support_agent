"""
Test script for monitoring endpoints.
"""

from fastapi.testclient import TestClient
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

os.environ["OPENAI_API_KEY"] = "test-key-for-testing"

from src.server import app

client = TestClient(app)

def test_monitoring_endpoints():
    print("Testing Monitoring API Endpoints...")
    print("=" * 60)
    
    print("\n1. Testing GET /api/monitoring/status (should be stopped initially)")
    response = client.get("/api/monitoring/status")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
    assert response.status_code == 200
    assert response.json()["running"] == False
    
    print("\n2. Testing POST /api/monitoring/start")
    response = client.post("/api/monitoring/start")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
    assert response.status_code == 200
    assert response.json()["success"] == True
    
    print("\n3. Testing GET /api/monitoring/status (should be running)")
    response = client.get("/api/monitoring/status")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
    assert response.status_code == 200
    assert response.json()["running"] == True
    
    print("\n4. Testing POST /api/monitoring/start again (should fail)")
    response = client.post("/api/monitoring/start")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
    assert response.status_code == 400
    
    print("\n5. Waiting 5 seconds for events to generate...")
    import time
    time.sleep(5)
    
    print("\n6. Testing GET /api/monitoring/events")
    response = client.get("/api/monitoring/events?limit=10")
    print(f"   Status: {response.status_code}")
    events = response.json()
    print(f"   Received {len(events)} events")
    if events:
        print(f"   First event: {events[0]['service_name']} - {events[0]['message']}")
    assert response.status_code == 200
    assert len(events) > 0
    
    print("\n7. Testing GET /api/monitoring/flagged")
    response = client.get("/api/monitoring/flagged")
    print(f"   Status: {response.status_code}")
    flagged = response.json()
    print(f"   Received {len(flagged)} flagged events")
    assert response.status_code == 200
    
    print("\n8. Testing GET /api/monitoring/ai-actions")
    response = client.get("/api/monitoring/ai-actions")
    print(f"   Status: {response.status_code}")
    actions = response.json()
    print(f"   Issues: {len(actions['issues'])}, Alerts: {len(actions['alerts'])}")
    assert response.status_code == 200
    assert "issues" in actions
    assert "alerts" in actions
    
    print("\n9. Testing POST /api/monitoring/clear")
    response = client.post("/api/monitoring/clear")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
    assert response.status_code == 200
    assert response.json()["success"] == True
    
    print("\n10. Testing GET /api/monitoring/events after clear (should have new events)")
    response = client.get("/api/monitoring/events?limit=10")
    print(f"   Status: {response.status_code}")
    events = response.json()
    print(f"   Received {len(events)} events (after clear)")
    assert response.status_code == 200
    
    print("\n11. Testing POST /api/monitoring/stop")
    response = client.post("/api/monitoring/stop")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
    assert response.status_code == 200
    assert response.json()["success"] == True
    
    print("\n12. Testing POST /api/monitoring/stop again (should fail)")
    response = client.post("/api/monitoring/stop")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
    assert response.status_code == 400
    
    print("\n" + "=" * 60)
    print("All tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    test_monitoring_endpoints()
