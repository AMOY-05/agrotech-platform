import streamlit as st
import requests
from datetime import datetime
import os

# --- Config ---
API_BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000/api/v1")
try:
    API_BASE_URL = st.secrets.get("API_BASE_URL", API_BASE_URL)
except Exception:
    pass

APP_TITLE = "🌾 AgroTech Intelligence Platform"

st.set_page_config(
    page_title="AgroTech AI",
    page_icon="🌾",
    layout="centered"
)

st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #2d5a27, #4a9e3f);
        color: white;
        padding: 20px;
        border-radius: 10px;
        text-align: center;
        margin-bottom: 20px;
    }
    .farmer-bubble {
        background: #dcf8c6;
        padding: 12px 16px;
        border-radius: 18px 18px 4px 18px;
        margin: 8px 0;
        margin-left: 20%;
        color: #000;
    }
    .bot-bubble {
        background: #ffffff;
        padding: 12px 16px;
        border-radius: 18px 18px 18px 4px;
        margin: 8px 0;
        margin-right: 20%;
        border: 1px solid #e0e0e0;
        color: #000;
    }
    .tool-badge {
        background: #4a9e3f;
        color: white;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.75em;
        margin-right: 4px;
    }
    .welcome-card {
        background: #f0f7ee;
        border-radius: 10px;
        padding: 20px;
        margin: 10px 0;
        border-left: 4px solid #4a9e3f;
    }
    .google-btn {
        background: white;
        border: 2px solid #4285f4;
        color: #4285f4;
        border-radius: 8px;
        padding: 10px;
        text-align: center;
        font-weight: bold;
        text-decoration: none;
        display: block;
        margin: 10px 0;
    }
    .divider-text {
        text-align: center;
        color: #888;
        margin: 10px 0;
        font-size: 0.85em;
    }
</style>
""", unsafe_allow_html=True)

# --- Session State Init ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "access_token" not in st.session_state:
    st.session_state.access_token = None
if "farmer_id" not in st.session_state:
    st.session_state.farmer_id = None
if "full_name" not in st.session_state:
    st.session_state.full_name = None
if "preferred_language" not in st.session_state:
    st.session_state.preferred_language = "english"
if "messages" not in st.session_state:
    st.session_state.messages = []
if "session_context" not in st.session_state:
    st.session_state.session_context = {}


# ─────────────────────────────────────────────
# AUTO-LOGIN FROM URL PARAMS (Google OAuth)
# ─────────────────────────────────────────────

def _set_auth_state(data: dict):
    st.session_state.authenticated = True
    st.session_state.access_token = data.get("access_token", "")
    st.session_state.farmer_id = data.get("farmer_id", "")
    st.session_state.full_name = data.get("full_name", "Farmer")
    st.session_state.preferred_language = data.get("preferred_language", "english")
    st.session_state.messages = []
    st.session_state.session_context = {}


def _logout():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()


# Check URL params for Google OAuth token
if not st.session_state.authenticated:
    try:
        params = st.query_params
        token = params.get("token", None)
        farmer_id = params.get("farmer_id", None)

        if token and farmer_id:
            _set_auth_state({
                "access_token": token,
                "farmer_id": farmer_id,
                "full_name": params.get("name", "Farmer"),
                "preferred_language": params.get("language", "english")
            })
            st.query_params.clear()
            st.rerun()
    except Exception as e:
        pass  # No params present, show auth page normally


# ─────────────────────────────────────────────
# AUTH PAGE
# ─────────────────────────────────────────────

def show_auth_page():
    st.markdown(f"""
    <div class="main-header">
        <h1>{APP_TITLE}</h1>
        <p>AI-powered assistant for Nigerian farmers</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="welcome-card">
        <h4>🌱 Welcome to AgroTech!</h4>
        <p>Get smart advice on crop yields, pest detection, market prices,
        and nearby agro stores — all powered by AI.</p>
    </div>
    """, unsafe_allow_html=True)

    # Get the backend URL for Google OAuth
    backend_url = API_BASE_URL.replace("/api/v1", "")

    tab1, tab2 = st.tabs(["🔑 Login", "📝 Sign Up"])

    # ── LOGIN TAB ──
    with tab1:
        st.markdown("### Welcome Back!")

        # Google Login
        st.markdown(f"""
        <a href="{backend_url}/api/v1/auth/google" target="_self" class="google-btn">
            🔵 &nbsp; Continue with Google
        </a>
        """, unsafe_allow_html=True)

        st.markdown(
            '<div class="divider-text">── or login with email ──</div>',
            unsafe_allow_html=True
        )

        login_email = st.text_input(
            "Email", key="login_email",
            placeholder="Enter your email"
        )
        login_password = st.text_input(
            "Password", type="password",
            key="login_password",
            placeholder="Enter your password"
        )

        if st.button("Login", use_container_width=True,
                     type="primary", key="login_btn"):
            if login_email and login_password:
                try:
                    response = requests.post(
                        f"{API_BASE_URL}/auth/login",
                        json={
                            "email": login_email,
                            "password": login_password
                        },
                        timeout=15
                    )
                    if response.status_code == 200:
                        data = response.json()
                        _set_auth_state(data)
                        st.success(data["message"])
                        st.rerun()
                    else:
                        error = response.json().get("detail", "Login failed")
                        st.error(f"❌ {error}")
                except requests.exceptions.ConnectionError:
                    st.error("❌ Cannot connect to AgroTech API.")
                except Exception as e:
                    st.error(f"❌ Error: {e}")
            else:
                st.warning("⚠️ Please enter your email and password")

    # ── SIGN UP TAB ──
    with tab2:
        st.markdown("### Create Your Account")

        # Google Signup
        st.markdown(f"""
        <a href="{backend_url}/api/v1/auth/google" target="_self" class="google-btn">
            🔵 &nbsp; Sign Up with Google
        </a>
        """, unsafe_allow_html=True)

        st.markdown(
            '<div class="divider-text">── or sign up with email ──</div>',
            unsafe_allow_html=True
        )

        full_name = st.text_input(
            "Full Name", key="signup_name",
            placeholder="Full Name"
        )
        signup_email = st.text_input(
            "Email", key="signup_email",
            placeholder="Enter your email"
        )
        signup_password = st.text_input(
            "Password", type="password",
            key="signup_password",
            placeholder="Min. 6 characters"
        )
        confirm_password = st.text_input(
            "Confirm Password", type="password",
            key="confirm_password",
            placeholder="Repeat your password"
        )

        if st.button("🌱 Create Account", use_container_width=True,
                     type="primary", key="signup_btn"):
            if not all([full_name, signup_email,
                        signup_password, confirm_password]):
                st.warning("⚠️ Please fill in all fields")
            elif signup_password != confirm_password:
                st.error("❌ Passwords do not match")
            elif len(signup_password) < 6:
                st.error("❌ Password must be at least 6 characters")
            else:
                try:
                    response = requests.post(
                        f"{API_BASE_URL}/auth/signup",
                        json={
                            "email": signup_email,
                            "full_name": full_name,
                            "password": signup_password,
                            "preferred_language": "english"
                        },
                        timeout=15
                    )
                    if response.status_code == 200:
                        data = response.json()
                        _set_auth_state(data)
                        st.success(f"✅ {data['message']}")
                        st.rerun()
                    else:
                        error = response.json().get("detail", "Signup failed")
                        st.error(f"❌ {error}")
                except requests.exceptions.ConnectionError:
                    st.error("❌ Cannot connect to AgroTech API.")
                except Exception as e:
                    st.error(f"❌ Error: {e}")


# Show auth page if not logged in
if not st.session_state.authenticated:
    show_auth_page()
    st.stop()