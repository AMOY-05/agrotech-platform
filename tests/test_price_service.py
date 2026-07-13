import pytest
from datetime import datetime
from app.services.price_service import (
    _normalize_crop,
    _get_base_price,
    _estimate_price,
    forecast_crop_price
)


class TestCropNormalization:
    """Tests for crop name normalization."""

    def test_tomatoes_normalized(self):
        assert _normalize_crop("tomatoes") == "tomato"

    def test_uppercase_normalized(self):
        assert _normalize_crop("TOMATO") == "tomato"

    def test_maize_variants(self):
        assert _normalize_crop("corn") == "maize"
        assert _normalize_crop("maize corn") == "maize"

    def test_pepper_variants(self):
        assert _normalize_crop("peppers") == "pepper"
        assert _normalize_crop("chili") == "pepper"

    def test_yam_plural(self):
        assert _normalize_crop("yams") == "yam"

    def test_valid_crop_unchanged(self):
        assert _normalize_crop("maize") == "maize"
        assert _normalize_crop("rice") == "rice"


class TestBasePriceLookup:
    """Tests for base price lookup logic."""

    def test_known_crop_and_region(self):
        price = _get_base_price("tomato", "lagos")
        assert price == 800

    def test_unknown_region_returns_average(self):
        # Should return average across all regions, not crash
        price = _get_base_price("tomato", "unknown_region")
        assert price is not None
        assert price > 0

    def test_unknown_crop_returns_none(self):
        price = _get_base_price("unknowncrop123", "lagos")
        assert price is None

    def test_case_insensitive_region(self):
        price1 = _get_base_price("tomato", "Lagos")
        price2 = _get_base_price("tomato", "lagos")
        assert price1 == price2

    def test_all_base_crops_have_prices(self):
        crops = ["tomato", "maize", "cassava", "rice", "yam", "pepper", "cowpea", "plantain"]
        for crop in crops:
            price = _get_base_price(crop, "lagos")
            assert price is not None, f"No price for {crop}"
            assert price > 0, f"Price for {crop} must be positive"


class TestPriceEstimation:
    """Tests for price estimation logic."""

    def test_price_is_positive(self):
        price = _estimate_price("tomato", "lagos", datetime.now())
        assert price > 0

    def test_price_includes_inflation(self):
        # Price today should be higher than base price (due to inflation since 2024)
        from app.services.price_service import FALLBACK_BASE_PRICES
        from app.services.price_service import _estimate_price
        from datetime import datetime

        # Get base price for tomato in Lagos
        base = FALLBACK_BASE_PRICES["tomato"]["lagos"]
        # Get current estimated price (should include inflation)
        current = _estimate_price("tomato", "lagos", datetime.now())
        assert current > base  # inflation since 2024 should push price up

    def test_seasonal_variation_exists(self):
        # Feb (peak dry season) should be more expensive than Oct (post-harvest glut)
        feb_date = datetime(2026, 2, 15)
        oct_date = datetime(2026, 10, 15)
        feb_price = _estimate_price("tomato", "lagos", feb_date)
        oct_price = _estimate_price("tomato", "lagos", oct_date)
        assert feb_price > oct_price


class TestPriceForecast:
    """Tests for the full forecast function."""

    @pytest.mark.asyncio
    async def test_forecast_returns_correct_structure(self):
        result = await forecast_crop_price("tomato", "Lagos", forecast_days=7)
        assert "current_price_ngn" in result
        assert "forecast" in result
        assert "best_sell_day" in result
        assert "trend" in result
        assert "recommendation" in result

    @pytest.mark.asyncio
    async def test_forecast_has_correct_number_of_days(self):
        result = await forecast_crop_price("tomato", "Lagos", forecast_days=7)
        assert len(result["forecast"]) == 7

    @pytest.mark.asyncio
    async def test_forecast_trend_is_valid(self):
        result = await forecast_crop_price("maize", "Kano")
        assert result["trend"] in ["rising", "falling", "stable"]

    @pytest.mark.asyncio
    async def test_forecast_works_with_plural_crop(self):
        result = await forecast_crop_price("tomatoes", "Lagos")
        assert result["crop_type"] == "tomato"  # normalized
        assert result["current_price_ngn"] > 0

    @pytest.mark.asyncio
    async def test_forecast_prices_are_positive(self):
        result = await forecast_crop_price("rice", "Kano")
        assert result["current_price_ngn"] > 0
        for day in result["forecast"]:
            assert day["estimated_price_ngn"] > 0