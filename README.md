# 🌾 AgroTech Intelligence Platform

AI-powered platform helping Nigerian farmers predict yields, detect pests,
and time their market sales optimally.

## Features
- 🐛 Pest & Disease Detection (LLM-powered)
- 📊 Crop Yield Prediction (XGBoost + live weather)
- 💰 Market Price Forecasting (seasonal model)
- 💬 Multi-turn AI Chat with session memory
- 📍 Nearby Agro-store Finder (OpenStreetMap)

## Tech Stack
- **Backend:** FastAPI, Python 3.11
- **AI:** Groq (LLaMA 3.1), LangChain
- **ML:** XGBoost, scikit-learn
- **Frontend:** Streamlit
- **APIs:** OpenWeather, Overpass (OSM)

## Setup

### 1. Clone and install
```bash
git clone <your-repo-url>
cd agrotech-platform
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env with your API keys
```

### 3. Train ML models
```bash
python data/generate_yield_data.py
python data/train_yield_model.py
```

### 4. Run locally
```bash
# Terminal 1 - API
uvicorn app.main:app --reload

# Terminal 2 - UI
streamlit run streamlit_app.py
```

### 5. Run with Docker
```bash
docker-compose up --build
```

## API Documentation
Visit `http://localhost:8000/docs` for interactive API docs.

## Testing
```bash
pytest tests/ -v
```# agrotech-platform
# agrotech-platform
# agrotech-platform
