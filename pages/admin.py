import streamlit as st
import requests
import os
from datetime import datetime

API_BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000/api/v1")
try:
    API_BASE_URL = st.secrets.get("API_BASE_URL", API_BASE_URL)
except Exception:
    pass

st.set_page_config(
    page_title="AgroTech Admin",
    page_icon="📊",
    layout="wide"
)

# Simple admin password protection
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "agrotech_admin_2024")
try:
    ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", ADMIN_PASSWORD)
except Exception:
    pass

st.markdown("""
<style>
    .metric-card {
        background: white;
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 20px;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .admin-header {
        background: linear-gradient(135deg, #1a3a1a, #2d5a27);
        color: white;
        padding: 20px;
        border-radius: 10px;
        text-align: center;
        margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="admin-header">
    <h1>📊 AgroTech Admin Dashboard</h1>
    <p>Platform monitoring and analytics</p>
</div>
""", unsafe_allow_html=True)

# Admin authentication
if "admin_authenticated" not in st.session_state:
    st.session_state.admin_authenticated = False

if not st.session_state.admin_authenticated:
    st.markdown("### 🔐 Admin Login")
    password = st.text_input("Admin Password", type="password")
    if st.button("Login", type="primary"):
        if password == ADMIN_PASSWORD:
            st.session_state.admin_authenticated = True
            st.rerun()
        else:
            st.error("❌ Invalid password")
    st.stop()

# ── Admin Dashboard ──
st.success("✅ Logged in as Admin")

if st.button("🚪 Logout", key="admin_logout"):
    st.session_state.admin_authenticated = False
    st.rerun()

st.divider()

# Fetch stats from API
try:
    stats_response = requests.get(
        f"{API_BASE_URL}/admin/stats",
        timeout=10
    )
    if stats_response.status_code == 200:
        stats = stats_response.json()
    else:
        stats = {}
except Exception:
    stats = {}

# ── Key Metrics ──
st.markdown("## 📈 Key Metrics")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        label="👥 Total Users",
        value=stats.get("total_users", "N/A"),
        delta=f"+{stats.get('new_users_today', 0)} today"
    )

with col2:
    st.metric(
        label="💬 Total Messages",
        value=stats.get("total_messages", "N/A"),
        delta=f"+{stats.get('messages_today', 0)} today"
    )

with col3:
    st.metric(
        label="🤖 Agent Calls",
        value=stats.get("total_agent_calls", "N/A"),
    )

with col4:
    st.metric(
        label="📱 Telegram Users",
        value=stats.get("telegram_users", "N/A"),
    )

st.divider()

# ── Recent Users ──
st.markdown("## 👥 Recent Users")

try:
    users_response = requests.get(
        f"{API_BASE_URL}/admin/users",
        timeout=10
    )
    if users_response.status_code == 200:
        users = users_response.json().get("users", [])
        if users:
            for user in users:
                with st.expander(
                    f"👨‍🌾 {user['full_name']} — {user['email']}"
                ):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.write(f"**Farmer ID:** `{user['farmer_id']}`")
                        st.write(f"**Provider:** {user['auth_provider']}")
                    with col2:
                        st.write(f"**Language:** {user['preferred_language']}")
                        st.write(f"**Active:** {'✅' if user['is_active'] else '❌'}")
                    with col3:
                        st.write(f"**Joined:** {user['created_at'][:10]}")
                        st.write(f"**Last Login:** {user.get('last_login', 'Never')[:10] if user.get('last_login') else 'Never'}")
        else:
            st.info("No users yet")
except Exception as e:
    st.error(f"Could not fetch users: {e}")

st.divider()

# ── Platform Health ──
st.markdown("## 🟢 Platform Health")

col1, col2 = st.columns(2)

with col1:
    try:
        health = requests.get(
            f"{API_BASE_URL}/health",
            timeout=5
        )
        if health.status_code == 200:
            data = health.json()
            st.success(f"✅ API Online — v{data.get('version', 'N/A')}")
        else:
            st.error("❌ API Error")
    except Exception:
        st.error("❌ API Offline")

with col2:
    st.info(f"🕐 Dashboard refreshed at {datetime.now().strftime('%H:%M:%S')}")

if st.button("🔄 Refresh Dashboard"):
    st.rerun()


# Hide sidebar navigation on admin page
st.markdown("""
<style>
    [data-testid="stSidebarNav"] {display: none;}
</style>
""", unsafe_allow_html=True)