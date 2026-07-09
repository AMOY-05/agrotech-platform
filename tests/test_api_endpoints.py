import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_200(self):
        response = client.get("/api/v1/health")
        assert response.status_code == 200

    def test_health_returns_correct_fields(self):
        response = client.get("/api/v1/health")
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"

    def test_root_returns_200(self):
        response = client.get("/")
        assert response.status_code == 200


class TestYieldEndpoint:
    def test_yield_prediction_returns_200(self):
        response = client.post("/api/v1/yield/predict", json={
            "crop_type": "maize",
            "farm_size_hectares": 2.0,
            "region": "Lagos",
            "soil_type": "loamy",
            "rainfall_mm": 1200,
            "temperature_celsius": 27,
            "fertilizer_used": True
        })
        assert response.status_code == 200

    def test_yield_response_has_required_fields(self):
        response = client.post("/api/v1/yield/predict", json={
            "crop_type": "tomato",
            "farm_size_hectares": 1.0,
            "region": "Kano",
            "soil_type": "sandy",
            "rainfall_mm": 800,
            "temperature_celsius": 30,
            "fertilizer_used": False
        })
        data = response.json()
        assert data["success"] is True
        assert "predicted_yield_kg" in data
        assert "confidence_interval" in data
        assert "recommendation" in data

    def test_yield_missing_field_returns_422(self):
        response = client.post("/api/v1/yield/predict", json={
            "crop_type": "maize"
            # missing required fields
        })
        assert response.status_code == 422


class TestPriceEndpoint:
    def test_price_forecast_returns_200(self):
        response = client.post("/api/v1/price/forecast", json={
            "crop_type": "tomato",
            "region": "Lagos",
            "forecast_days": 7
        })
        assert response.status_code == 200

    def test_price_forecast_with_plural_crop(self):
        response = client.post("/api/v1/price/forecast", json={
            "crop_type": "tomatoes",
            "region": "Lagos",
            "forecast_days": 7
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_price_forecast_has_14_days_by_default(self):
        response = client.post("/api/v1/price/forecast", json={
            "crop_type": "maize",
            "region": "Kano"
        })
        data = response.json()
        assert len(data["forecast"]) == 14


class TestPestEndpoint:
    def test_pest_detection_returns_200(self):
        response = client.post("/api/v1/pest/detect", json={
            "crop_type": "tomato",
            "symptoms": "yellow spots on leaves, wilting",
            "region": "Lagos"
        })
        assert response.status_code == 200

    def test_pest_response_has_required_fields(self):
        response = client.post("/api/v1/pest/detect", json={
            "crop_type": "maize",
            "symptoms": "brown streaks and holes in leaves",
            "region": "Kano"
        })
        data = response.json()
        assert "detected_issue" in data
        assert "confidence" in data
        assert "treatment" in data
        assert "urgency" in data
        assert data["urgency"] in ["low", "medium", "high"]