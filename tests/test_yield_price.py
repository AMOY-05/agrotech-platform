import pytest
from app.services.yield_service import predict_yield_ml


class TestYieldPrediction:
    """Tests for XGBoost yield prediction."""

    @pytest.mark.asyncio
    async def test_basic_prediction_returns_value(self):
        result = await predict_yield_ml(
            crop_type="maize",
            farm_size_hectares=2.0,
            region="Kano",
            soil_type="loamy",
            rainfall_mm=1200,
            temperature_celsius=27,
            fertilizer_used=True
        )
        assert result["predicted_yield_kg"] > 0

    @pytest.mark.asyncio
    async def test_larger_farm_gives_higher_yield(self):
        small = await predict_yield_ml(
            crop_type="maize", farm_size_hectares=1.0,
            region="Lagos", soil_type="loamy",
            rainfall_mm=1200, temperature_celsius=27,
            fertilizer_used=True
        )
        large = await predict_yield_ml(
            crop_type="maize", farm_size_hectares=5.0,
            region="Lagos", soil_type="loamy",
            rainfall_mm=1200, temperature_celsius=27,
            fertilizer_used=True
        )
        assert large["predicted_yield_kg"] > small["predicted_yield_kg"]

    @pytest.mark.asyncio
    async def test_fertilizer_improves_yield(self):
        without = await predict_yield_ml(
            crop_type="tomato", farm_size_hectares=2.0,
            region="Lagos", soil_type="loamy",
            rainfall_mm=1200, temperature_celsius=27,
            fertilizer_used=False
        )
        with_fert = await predict_yield_ml(
            crop_type="tomato", farm_size_hectares=2.0,
            region="Lagos", soil_type="loamy",
            rainfall_mm=1200, temperature_celsius=27,
            fertilizer_used=True
        )
        assert with_fert["predicted_yield_kg"] > without["predicted_yield_kg"]

    @pytest.mark.asyncio
    async def test_confidence_interval_is_valid(self):
        result = await predict_yield_ml(
            crop_type="rice", farm_size_hectares=3.0,
            region="Rivers", soil_type="clay",
            rainfall_mm=1500, temperature_celsius=28,
            fertilizer_used=True
        )
        assert result["confidence_interval"]["lower"] < result["predicted_yield_kg"]
        assert result["confidence_interval"]["upper"] > result["predicted_yield_kg"]

    @pytest.mark.asyncio
    async def test_plural_crop_name_works(self):
        result = await predict_yield_ml(
            crop_type="tomatoes",
            farm_size_hectares=1.0,
            region="Lagos",
            soil_type="loamy",
            rainfall_mm=1200,
            temperature_celsius=27,
            fertilizer_used=True
        )
        assert result["predicted_yield_kg"] > 0

    @pytest.mark.asyncio
    async def test_all_supported_crops(self):
        crops = ["maize", "tomato", "cassava", "rice", "yam"]
        for crop in crops:
            result = await predict_yield_ml(
                crop_type=crop, farm_size_hectares=2.0,
                region="Lagos", soil_type="loamy",
                rainfall_mm=1200, temperature_celsius=27,
                fertilizer_used=True
            )
            assert result["predicted_yield_kg"] > 0, f"Yield prediction failed for {crop}"