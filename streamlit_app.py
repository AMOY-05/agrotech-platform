import streamlit as st
import requests
from datetime import datetime
import os

# --- Config ---
try:
    import streamlit as st
    API_BASE_URL = st.secrets.get("API_BASE_URL", os.environ.get("API_BASE_URL", "http://127.0.0.1:8000/api/v1"))
except Exception:
    API_BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000/api/v1")
APP_TITLE = "🌾 AgroTech Intelligence Platform"

# --- Page Setup ---
st.set_page_config(
    page_title="AgroTech AI",
    page_icon="🌾",
    layout="centered"
)

# --- Custom CSS ---
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
    .metric-card {
        background: white;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 15px;
        text-align: center;
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
# AUTH HELPERS
# ─────────────────────────────────────────────

def _set_auth_state(data: dict):
    st.session_state.authenticated = True
    st.session_state.access_token = data["access_token"]
    st.session_state.farmer_id = data["farmer_id"]
    st.session_state.full_name = data["full_name"]
    st.session_state.preferred_language = data.get("preferred_language", "english")
    st.session_state.messages = []
    st.session_state.session_context = {}


def _logout():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()


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

    tab1, tab2 = st.tabs(["🔑 Login", "📝 Sign Up"])

    # ── LOGIN TAB ──
    with tab1:
        st.markdown("### Welcome Back!")

        # Google Login — prominent at the top
        st.markdown(f"""
        <a href="{API_BASE_URL}/auth/google" target="_blank" class="google-btn">
            🔵 &nbsp; Continue with Google
        </a>
        """, unsafe_allow_html=True)

        st.markdown('<div class="divider-text">── or login with email ──</div>',
                    unsafe_allow_html=True)

        login_email = st.text_input(
            "Email", key="login_email",
            placeholder="Enter your email"
        )
        login_password = st.text_input(
            "Password", type="password",
            key="login_password",
            placeholder="Enter your password"
        )

        if st.button("Login", use_container_width=True, type="primary", key="login_btn"):
            if login_email and login_password:
                try:
                    response = requests.post(
                        f"{API_BASE_URL}/auth/login",
                        json={"email": login_email, "password": login_password},
                        timeout=10
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
                    st.error("❌ Cannot connect to AgroTech API. Make sure the server is running.")
                except Exception as e:
                    st.error(f"❌ Error: {e}")
            else:
                st.warning("⚠️ Please enter your email and password")

        st.divider()
        st.caption("After Google login, paste your token below to continue:")
        google_token = st.text_input(
            "Token",
            key="google_token_input",
            placeholder="Paste token from Google login..."
        )
        if google_token and st.button("✅ Verify Token", key="verify_token_btn"):
            try:
                response = requests.get(
                    f"{API_BASE_URL}/auth/me",
                    params={"token": google_token},
                    timeout=10
                )
                if response.status_code == 200:
                    profile = response.json()
                    st.session_state.authenticated = True
                    st.session_state.access_token = google_token
                    st.session_state.farmer_id = profile["farmer_id"]
                    st.session_state.full_name = profile["full_name"]
                    st.session_state.preferred_language = profile.get("preferred_language", "english")
                    st.session_state.messages = []
                    st.session_state.session_context = {}
                    st.success(f"✅ Welcome, {profile['full_name']}!")
                    st.rerun()
                else:
                    st.error("❌ Invalid or expired token")
            except Exception as e:
                st.error(f"❌ Error: {e}")

    # ── SIGN UP TAB ──
    with tab2:
        st.markdown("### Create Your Account")

        # Google Signup — prominent at the top
        st.markdown(f"""
        <a href="{API_BASE_URL}/auth/google" target="_blank" class="google-btn">
            🔵 &nbsp; Sign Up with Google
        </a>
        """, unsafe_allow_html=True)

        st.markdown('<div class="divider-text">── or sign up with email ──</div>',
                    unsafe_allow_html=True)

        full_name = st.text_input(
            "Full Name",
            key="signup_name",
            placeholder="Full Name"
        )
        signup_email = st.text_input(
            "Email",
            key="signup_email",
            placeholder="Enter your email"
        )
        signup_password = st.text_input(
            "Password",
            type="password",
            key="signup_password",
            placeholder="Min. 6 characters"
        )
        confirm_password = st.text_input(
            "Confirm Password",
            type="password",
            key="confirm_password",
            placeholder="Repeat your password"
        )

        if st.button("🌱 Create Account", use_container_width=True,
                     type="primary", key="signup_btn"):
            if not all([full_name, signup_email, signup_password, confirm_password]):
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
                            "preferred_language": "english"  # default, changeable in chat
                        },
                        timeout=10
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
                    st.error("❌ Cannot connect to AgroTech API. Make sure the server is running.")
                except Exception as e:
                    st.error(f"❌ Error: {e}")


# ─────────────────────────────────────────────
# SHOW AUTH PAGE IF NOT LOGGED IN
# ─────────────────────────────────────────────

if not st.session_state.authenticated:
    show_auth_page()
    st.stop()


# ─────────────────────────────────────────────
# MAIN APP (only shown after login)
# ─────────────────────────────────────────────

# --- Header ---
st.markdown(f"""
<div class="main-header">
    <h1>{APP_TITLE}</h1>
    <p>AI-powered assistant for Nigerian farmers</p>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────

with st.sidebar:
    st.image("https://img.icons8.com/color/96/farm.png", width=80)

    st.markdown(f"### 👨‍🌾 {st.session_state.full_name}")
    st.caption(f"🪪 ID: `{st.session_state.farmer_id}`")

    if st.button("🚪 Logout", use_container_width=True, key="logout_btn"):
        _logout()

    st.divider()

    # Language preference — in the chat sidebar, not signup
    st.markdown("### 🌐 Response Language")
    selected_language = st.selectbox(
        "AgroBot will respond in:",
        ["english", "yoruba", "hausa", "igbo", "pidgin"],
        index=["english", "yoruba", "hausa", "igbo", "pidgin"].index(
            st.session_state.preferred_language
        ),
        key="language_selector"
    )
    if selected_language != st.session_state.preferred_language:
        st.session_state.preferred_language = selected_language
        st.success(f"✅ Language set to {selected_language.title()}")

    st.divider()

    # Known context display
    st.markdown("### 🧠 What I Know About You")
    ctx = st.session_state.session_context
    if ctx.get("crop_type"):
        st.success(f"🌱 Crop: **{ctx['crop_type'].title()}**")
    if ctx.get("region"):
        st.info(f"📍 Region: **{ctx['region']}**")
    if ctx.get("farm_size_hectares"):
        st.info(f"📐 Farm Size: **{ctx['farm_size_hectares']} hectares**")
    if ctx.get("soil_type"):
        st.info(f"🪨 Soil: **{ctx['soil_type']}**")
    if not any(ctx.values()):
        st.caption("Tell me about your farm to get started!")

    st.divider()

    # Quick action buttons
    st.markdown("### ⚡ Quick Questions")
    quick_questions = [
        "What's the best time to sell my crops?",
        "What pests should I watch out for?",
        "How can I improve my yield?",
        "Where can I buy fertilizer nearby?",
        "What's the weather like for farming?",
    ]
    for q in quick_questions:
        if st.button(q, use_container_width=True, key=f"quick_{q[:20]}"):
            st.session_state.pending_message = q

    st.divider()

    # API health check
    try:
        health = requests.get(f"{API_BASE_URL}/health", timeout=3)
        if health.status_code == 200:
            st.success("🟢 API Connected")
        else:
            st.error("🔴 API Error")
    except:
        st.error("🔴 API Offline")

    if st.button("🗑️ Clear Chat", use_container_width=True, key="clear_chat_btn"):
        st.session_state.messages = []
        st.session_state.session_context = {}
        st.rerun()


# ─────────────────────────────────────────────
# CHAT HISTORY DISPLAY
# ─────────────────────────────────────────────

chat_container = st.container()

with chat_container:
    if not st.session_state.messages:
        first_name = st.session_state.full_name.split()[0]
        st.markdown(f"""
        <div class="bot-bubble">
        👋 Hello <strong>{first_name}</strong>! I'm <strong>AgroBot</strong>,
        your AI farming assistant.<br><br>
        I can help you with:
        <ul>
            <li>🐛 <strong>Pest & Disease Detection</strong></li>
            <li>📈 <strong>Crop Yield Prediction</strong></li>
            <li>💰 <strong>Market Price Forecasting</strong></li>
            <li>📍 <strong>Nearby Agro Stores</strong></li>
            <li>🌦️ <strong>Weather-based Advice</strong></li>
        </ul>
        You can change my response language anytime from the sidebar.<br>
        Tell me about your farm to get started!
        </div>
        """, unsafe_allow_html=True)

    for msg in st.session_state.messages:
        if msg["role"] == "user":
            st.markdown(f"""
            <div class="farmer-bubble">
                👨‍🌾 {msg["content"]}
            </div>
            """, unsafe_allow_html=True)
        else:
            tools_html = ""
            if msg.get("tools_used"):
                for tool in msg["tools_used"]:
                    label = {
                        "detect_pest_disease": "🐛 Pest Detection",
                        "forecast_price": "💰 Price Forecast",
                        "predict_yield": "📊 Yield Prediction",
                        "find_nearby_stores": "📍 Store Finder",
                        "image_analysis": "📸 Photo Analysis",
                        "voice_transcription": "🎤 Voice Note"
                    }.get(tool, tool)
                    tools_html += f'<span class="tool-badge">{label}</span>'

            st.markdown(f"""
            <div class="bot-bubble">
                🤖 {msg["content"]}
                {"<br><br><small>" + tools_html + "</small>" if tools_html else ""}
            </div>
            """, unsafe_allow_html=True)

# ─────────────────────────────────────────────
# VOICE NOTE SECTION
# ─────────────────────────────────────────────

with st.expander("🎤 Send a Voice Note", expanded=False):
    st.caption(
        "Record your question in English, Yoruba, Hausa, Igbo, or Pidgin "
        "and AgroBot will understand and respond."
    )

    voice_language = st.selectbox(
        "Language of your voice note",
        ["english", "yoruba", "hausa", "igbo", "pidgin"],
        index=["english", "yoruba", "hausa", "igbo", "pidgin"].index(
            st.session_state.preferred_language
        ),
        key="voice_language_selector"
    )

    uploaded_audio = st.file_uploader(
        "Upload your voice note",
        type=["mp3", "mp4", "wav", "m4a", "ogg", "webm", "flac"],
        key="voice_uploader",
        help="Record a voice note on your phone and upload it here"
    )

    if uploaded_audio is not None:
        st.audio(uploaded_audio, format=uploaded_audio.type)
        st.caption(f"📁 {uploaded_audio.name} — "
                  f"{len(uploaded_audio.getvalue()) / 1024:.1f} KB")

        if st.button("🎤 Send Voice Note", type="primary", key="send_voice_btn"):

            # Add user message first
            st.session_state.messages.append({
                "role": "user",
                "content": f"🎤 [Voice note in {voice_language.title()}]"
            })

            with st.spinner(
                f"Transcribing your {voice_language} voice note and generating response..."
            ):
                try:
                    files = {
                        "file": (
                            uploaded_audio.name,
                            uploaded_audio.getvalue(),
                            uploaded_audio.type
                        )
                    }
                    form_data = {
                        "farmer_id": st.session_state.farmer_id,
                        "preferred_language": voice_language
                    }
                    ctx = st.session_state.session_context
                    if ctx.get("crop_type"):
                        form_data["crop_context"] = ctx["crop_type"]

                    response = requests.post(
                        f"{API_BASE_URL}/voice/process",
                        files=files,
                        data=form_data,
                        timeout=60  # Voice processing takes longer
                    )

                    if response.status_code == 200:
                        result = response.json()

                        if result["success"]:
                            transcribed = result.get("transcribed_text", "")
                            detected_lang = result.get("detected_language", voice_language)
                            reply = result.get("reply", "")
                            tools_used = result.get("tools_used", [])
                            session_context = result.get("session_context", {})

                            # Update session context
                            if session_context:
                                st.session_state.session_context = session_context

                            # Show transcription + response
                            full_reply = f"""🎤 *Transcribed ({detected_lang}):* "{transcribed}"

{reply}"""

                            st.session_state.messages.append({
                                "role": "assistant",
                                "content": full_reply,
                                "tools_used": tools_used
                            })
                            st.rerun()

                        else:
                            error = result.get("error", "Voice processing failed")
                            st.session_state.messages.append({
                                "role": "assistant",
                                "content": f"⚠️ {error}",
                                "tools_used": []
                            })
                            st.rerun()

                    else:
                        detail = response.json().get("detail", "Server error")
                        st.error(f"❌ {detail}")

                except requests.exceptions.Timeout:
                    st.error("⚠️ Voice processing timed out. Please try a shorter recording.")
                except Exception as e:
                    st.error(f"❌ Error: {e}")

    else:
        st.info(
            "💡 **Tip:** Record a voice note on your phone using the Voice Recorder app, "
            "then upload it here. Speak clearly and mention your crop and location for "
            "the best results."
        )

# ─────────────────────────────────────────────
# IMAGE UPLOAD SECTION
# ─────────────────────────────────────────────

with st.expander("📸 Upload Crop Photo for Disease Detection", expanded=False):
    st.caption("Take a clear photo of affected leaves, stem, or fruit and upload it here.")

    col1, col2 = st.columns(2)
    with col1:
        img_crop_type = st.text_input(
            "Crop type",
            placeholder="e.g. tomato, maize",
            key="img_crop_type"
        )
    with col2:
        img_region = st.text_input(
            "Your region",
            placeholder="e.g. Lagos, Kano",
            key="img_region"
        )

    uploaded_file = st.file_uploader(
        "Choose a crop photo",
        type=["jpg", "jpeg", "png", "webp"],
        key="crop_image_uploader"
    )

    if uploaded_file is not None:
        # Show preview
        st.image(uploaded_file, caption="Uploaded crop photo", width=400)

        if st.button("🔍 Analyze This Photo", type="primary", key="analyze_image_btn"):
            # Add user message FIRST before analysis
            st.session_state.messages.append({
                "role": "user",
                "content": f"[Uploaded crop photo{f' of {img_crop_type}' if img_crop_type else ''}]"
            })
            with st.spinner("Analyzing your crop photo with AI vision..."):
                try:
                    files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                    data = {}
                    if img_crop_type:
                        data["crop_type"] = img_crop_type
                    if img_region:
                        data["region"] = img_region

                    response = requests.post(
                        f"{API_BASE_URL}/image/analyze",
                        files=files,
                        data=data,
                        timeout=30
                    )

                    if response.status_code == 200:
                        result = response.json()

                        if result["success"]:
                            # Add result as a chat message
                            crop_name = result.get("crop_identified", "Unknown crop")
                            issue = result.get("detected_issue", "Unknown issue")
                            confidence = result.get("confidence", 0)
                            severity = result.get("severity", "unknown")
                            urgency = result.get("urgency", "medium")
                            treatment = result.get("treatment", "")
                            prevention = result.get("prevention", "")
                            yield_impact = result.get("estimated_yield_impact", "")
                            symptoms = result.get("symptoms_visible", [])

                            # Format urgency with emoji
                            urgency_emoji = {
                                "low": "🟢", "medium": "🟡", "high": "🔴"
                            }.get(urgency, "🟡")

                            severity_emoji = {
                                "mild": "😐", "moderate": "😟", "severe": "😱"
                            }.get(severity, "😟")

                            reply = f"""📸 **Photo Analysis Complete**

**Crop Identified:** {crop_name.title()}
**Issue Detected:** {issue}
**Confidence:** {confidence:.0%}
**Severity:** {severity_emoji} {severity.title()}
**Urgency:** {urgency_emoji} {urgency.title()}

**Symptoms Visible:**
{chr(10).join(f"• {s}" for s in symptoms) if symptoms else "• See image"}

**Treatment:**
{treatment}

**Prevention for Future:**
{prevention}

**Estimated Yield Impact if Untreated:** {yield_impact}"""

                            st.session_state.messages.append({
                                "role": "assistant",
                                "content": reply,
                                "tools_used": ["image_analysis"]
                            })
                            st.rerun()

                        else:
                            st.error(f"❌ {result.get('error', 'Analysis failed')}")
                    else:
                        st.error(f"❌ Server error: {response.status_code}")

                except requests.exceptions.Timeout:
                    st.error("⚠️ Analysis timed out. Please try again with a smaller image.")
                except Exception as e:
                    st.error(f"❌ Error: {e}")

# ─────────────────────────────────────────────
# SEND MESSAGE FUNCTION
# ─────────────────────────────────────────────

def send_message(user_input: str):
    if not user_input.strip():
        return

    st.session_state.messages.append({
        "role": "user",
        "content": user_input
    })

    try:
        with st.spinner("AgroBot is thinking..."):
            response = requests.post(
                f"{API_BASE_URL}/agent/chat",
                json={
                    "message": user_input,
                    "farmer_id": st.session_state.farmer_id,
                    "preferred_language": st.session_state.preferred_language
                },
                timeout=30
            )

        if response.status_code == 200:
            data = response.json()
            reply = data.get("reply", "Sorry, I couldn't process that.")
            tools_used = data.get("sources", [])
            session_context = data.get("session_context", {})

            st.session_state.session_context = session_context
            st.session_state.messages.append({
                "role": "assistant",
                "content": reply,
                "tools_used": tools_used
            })

        elif response.status_code == 401:
            st.session_state.messages.append({
                "role": "assistant",
                "content": "⚠️ Your session has expired. Please log in again.",
                "tools_used": []
            })
            st.session_state.authenticated = False
            st.rerun()

        else:
            st.session_state.messages.append({
                "role": "assistant",
                "content": f"⚠️ Server error ({response.status_code}). Please try again.",
                "tools_used": []
            })

    except requests.exceptions.ConnectionError:
        st.session_state.messages.append({
            "role": "assistant",
            "content": "⚠️ Cannot connect to the AgroTech API. Please make sure your FastAPI server is running.",
            "tools_used": []
        })
    except requests.exceptions.Timeout:
        st.session_state.messages.append({
            "role": "assistant",
            "content": "⚠️ The request timed out. Please try again.",
            "tools_used": []
        })
    except Exception as e:
        st.session_state.messages.append({
            "role": "assistant",
            "content": f"⚠️ Unexpected error: {str(e)}",
            "tools_used": []
        })


# ─────────────────────────────────────────────
# HANDLE INPUT
# ─────────────────────────────────────────────

if hasattr(st.session_state, "pending_message"):
    pending = st.session_state.pending_message
    del st.session_state.pending_message
    send_message(pending)
    st.rerun()

user_input = st.chat_input("Ask AgroBot anything about your farm...")
if user_input:
    send_message(user_input)
    st.rerun()


# ─────────────────────────────────────────────
# VOICE RECORDER COMPONENT
# ─────────────────────────────────────────────

st.markdown("#### 🎤 Or speak your question")

voice_col1, voice_col2 = st.columns([3, 1])

with voice_col2:
    voice_lang = st.selectbox(
        "Language",
        ["english", "yoruba", "hausa", "igbo", "pidgin"],
        index=["english", "yoruba", "hausa", "igbo", "pidgin"].index(
            st.session_state.preferred_language
        ),
        key="voice_lang_select",
        label_visibility="collapsed"
    )

with voice_col1:
    # Custom HTML mic recorder
    recorder_html = f"""
    <div style="display: flex; align-items: center; gap: 10px; margin: 5px 0;">
        <button id="recordBtn" onclick="toggleRecording()"
            style="background: #4a9e3f; color: white; border: none;
                   border-radius: 50%; width: 50px; height: 50px;
                   font-size: 20px; cursor: pointer; display: flex;
                   align-items: center; justify-content: center;
                   box-shadow: 0 2px 5px rgba(0,0,0,0.2);">
            🎤
        </button>
        <div id="statusText" style="color: #666; font-size: 0.85em;">
            Press mic to start recording
        </div>
        <div id="timer" style="color: #e74c3c; font-weight: bold; display: none;">
            ⏺ 0s
        </div>
    </div>

    <div id="audioPlayback" style="margin: 10px 0; display: none;">
        <audio id="audioPlayer" controls style="width: 100%; height: 35px;"></audio>
        <div style="display: flex; gap: 8px; margin-top: 8px;">
            <button onclick="sendAudio()"
                style="background: #2d5a27; color: white; border: none;
                       border-radius: 8px; padding: 8px 20px;
                       cursor: pointer; font-size: 0.9em;">
                ✅ Send Voice Note
            </button>
            <button onclick="discardAudio()"
                style="background: #e74c3c; color: white; border: none;
                       border-radius: 8px; padding: 8px 16px;
                       cursor: pointer; font-size: 0.9em;">
                🗑️ Discard
            </button>
        </div>
    </div>

    <div id="resultBox" style="display: none; background: #f0f7ee;
         border-left: 4px solid #4a9e3f; padding: 10px; border-radius: 4px;
         margin-top: 10px; font-size: 0.85em;">
    </div>

    <script>
        let mediaRecorder = null;
        let audioChunks = [];
        let isRecording = false;
        let timerInterval = null;
        let seconds = 0;
        let audioBlob = null;

        function toggleRecording() {{
            if (!isRecording) {{
                startRecording();
            }} else {{
                stopRecording();
            }}
        }}

        async function startRecording() {{
            try {{
                const stream = await navigator.mediaDevices.getUserMedia({{ audio: true }});
                mediaRecorder = new MediaRecorder(stream);
                audioChunks = [];

                mediaRecorder.ondataavailable = (event) => {{
                    audioChunks.push(event.data);
                }};

                mediaRecorder.onstop = () => {{
                    audioBlob = new Blob(audioChunks, {{ type: 'audio/webm' }});
                    const audioUrl = URL.createObjectURL(audioBlob);
                    document.getElementById('audioPlayer').src = audioUrl;
                    document.getElementById('audioPlayback').style.display = 'block';
                    stream.getTracks().forEach(track => track.stop());
                }};

                mediaRecorder.start();
                isRecording = true;

                // Update UI
                document.getElementById('recordBtn').innerHTML = '⏹️';
                document.getElementById('recordBtn').style.background = '#e74c3c';
                document.getElementById('statusText').textContent = 'Recording... Press to stop';
                document.getElementById('timer').style.display = 'block';
                document.getElementById('audioPlayback').style.display = 'none';

                // Start timer
                seconds = 0;
                timerInterval = setInterval(() => {{
                    seconds++;
                    document.getElementById('timer').textContent = '⏺ ' + seconds + 's';
                    if (seconds >= 120) {{  // Max 2 minutes
                        stopRecording();
                    }}
                }}, 1000);

            }} catch (err) {{
                document.getElementById('statusText').textContent =
                    '❌ Microphone access denied. Please allow microphone access.';
                console.error('Mic error:', err);
            }}
        }}

        function stopRecording() {{
            if (mediaRecorder && isRecording) {{
                mediaRecorder.stop();
                isRecording = false;
                clearInterval(timerInterval);

                // Update UI
                document.getElementById('recordBtn').innerHTML = '🎤';
                document.getElementById('recordBtn').style.background = '#4a9e3f';
                document.getElementById('statusText').textContent =
                    'Recording complete. Listen back and send.';
                document.getElementById('timer').style.display = 'none';
            }}
        }}

        async function sendAudio() {{
            if (!audioBlob) return;

            document.getElementById('statusText').textContent = '⏳ Processing...';
            document.getElementById('audioPlayback').style.display = 'none';

            const formData = new FormData();
            formData.append('file', audioBlob, 'voice_note.webm');
            formData.append('farmer_id', '{st.session_state.farmer_id}');
            formData.append('preferred_language', '{voice_lang}');

            try {{
                const response = await fetch('{API_BASE_URL}/voice/process', {{
                    method: 'POST',
                    body: formData
                }});

                const result = await response.json();

                if (result.success) {{
                    const resultBox = document.getElementById('resultBox');
                    resultBox.style.display = 'block';
                    resultBox.innerHTML =
                        '<strong>🎤 You said:</strong> ' + result.transcribed_text +
                        '<br><br><strong>🤖 AgroBot:</strong> ' + result.reply;

                    document.getElementById('statusText').textContent =
                        '✅ Done! Scroll up to see full response.';

                    // Store result for Streamlit to pick up
                    window.voiceResult = result;

                }} else {{
                    document.getElementById('statusText').textContent =
                        '❌ ' + (result.error || result.detail || 'Processing failed');
                    document.getElementById('audioPlayback').style.display = 'block';
                }}
            }} catch (err) {{
                document.getElementById('statusText').textContent =
                    '❌ Connection error. Make sure the API server is running.';
                document.getElementById('audioPlayback').style.display = 'block';
                console.error(err);
            }}
        }}

        function discardAudio() {{
            audioBlob = null;
            document.getElementById('audioPlayback').style.display = 'none';
            document.getElementById('resultBox').style.display = 'none';
            document.getElementById('statusText').textContent = 'Press mic to start recording';
            document.getElementById('audioPlayer').src = '';
        }}
    </script>
    """

    st.components.v1.html(recorder_html, height=220)