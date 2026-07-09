import pytest
from app.agent.memory import (
    get_session,
    FarmerSession,
    get_active_session_count
)


class TestFarmerSession:
    """Tests for individual session behavior."""

    def test_new_session_has_empty_context(self):
        session = FarmerSession("test_farmer_001")
        assert session.context["crop_type"] is None
        assert session.context["region"] is None
        assert session.context["farm_size_hectares"] is None

    def test_context_update_works(self):
        session = FarmerSession("test_farmer_002")
        session.update_context(crop_type="tomato", region="Lagos")
        assert session.context["crop_type"] == "tomato"
        assert session.context["region"] == "Lagos"

    def test_context_update_ignores_none_values(self):
        session = FarmerSession("test_farmer_003")
        session.update_context(crop_type="maize")
        session.update_context(crop_type=None)  # should NOT overwrite
        assert session.context["crop_type"] == "maize"

    def test_message_history_stores_correctly(self):
        session = FarmerSession("test_farmer_004")
        session.add_message("user", "Hello")
        session.add_message("assistant", "Hi there!")
        assert len(session.messages) == 2
        assert session.messages[0]["role"] == "user"
        assert session.messages[1]["content"] == "Hi there!"

    def test_message_history_capped_at_10(self):
        session = FarmerSession("test_farmer_005")
        for i in range(15):
            session.add_message("user", f"Message {i}")
        assert len(session.messages) == 10

    def test_context_summary_with_data(self):
        session = FarmerSession("test_farmer_006")
        session.update_context(crop_type="tomato", region="Lagos", farm_size_hectares=3.0)
        summary = session.get_context_summary()
        assert "tomato" in summary
        assert "Lagos" in summary
        assert "3.0" in summary

    def test_context_summary_empty_when_no_data(self):
        session = FarmerSession("test_farmer_007")
        summary = session.get_context_summary()
        assert summary == ""

    def test_session_not_expired_immediately(self):
        session = FarmerSession("test_farmer_008")
        assert not session.is_expired()


class TestSessionStore:
    """Tests for the global session store."""

    def test_get_session_creates_new(self):
        session = get_session("brand_new_farmer_xyz")
        assert session is not None
        assert session.farmer_id == "brand_new_farmer_xyz"

    def test_get_session_returns_same_session(self):
        session1 = get_session("persistent_farmer_abc")
        session1.update_context(crop_type="maize")
        session2 = get_session("persistent_farmer_abc")
        assert session2.context["crop_type"] == "maize"

    def test_different_farmers_have_separate_sessions(self):
        s1 = get_session("farmer_alpha")
        s2 = get_session("farmer_beta")
        s1.update_context(crop_type="tomato")
        s2.update_context(crop_type="maize")
        assert s1.context["crop_type"] == "tomato"
        assert s2.context["crop_type"] == "maize"