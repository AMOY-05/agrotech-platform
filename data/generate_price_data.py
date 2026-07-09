import pandas as pd
import numpy as np
from datetime import datetime, timedelta

np.random.seed(42)

# Realistic base prices in Naira per kg (2024-2025 Nigerian market estimates)
BASE_PRICES = {
    "tomato":   {"lagos": 800,  "kano": 600,  "oyo": 700,  "rivers": 900,  "kaduna": 650},
    "maize":    {"lagos": 450,  "kano": 380,  "oyo": 420,  "rivers": 480,  "kaduna": 400},
    "cassava":  {"lagos": 200,  "kano": 180,  "oyo": 190,  "rivers": 220,  "kaduna": 185},
    "rice":     {"lagos": 950,  "kano": 880,  "oyo": 920,  "rivers": 980,  "kaduna": 900},
    "yam":      {"lagos": 600,  "kano": 500,  "oyo": 550,  "rivers": 650,  "kaduna": 520},
    "pepper":   {"lagos": 1200, "kano": 1000, "oyo": 1100, "rivers": 1300, "kaduna": 1050},
    "cowpea":   {"lagos": 700,  "kano": 580,  "oyo": 650,  "rivers": 750,  "kaduna": 600},
    "plantain": {"lagos": 400,  "kano": 350,  "oyo": 380,  "rivers": 450,  "kaduna": 360},
}

# Seasonal multipliers by month (1=Jan ... 12=Dec)
# Prices tend to rise in dry season (Dec-Mar) and fall post-harvest (Oct-Nov)
SEASONAL_PATTERN = {
    1:  1.15,  # Jan — dry season, high prices
    2:  1.20,  # Feb — peak dry season
    3:  1.10,  # Mar — easing
    4:  0.95,  # Apr — early rains, planting begins
    5:  0.90,  # May — supply increasing
    6:  0.88,  # Jun — rainy season, good supply
    7:  0.92,  # Jul
    8:  0.95,  # Aug
    9:  1.00,  # Sep — harvest approaching
    10: 0.85,  # Oct — post-harvest glut, lowest prices
    11: 0.88,  # Nov — supply stabilizing
    12: 1.10,  # Dec — festive demand spike
}

def generate_price_history(days=730):  # 2 years of daily data
    rows = []
    start_date = datetime.now() - timedelta(days=days)

    for crop, region_prices in BASE_PRICES.items():
        for region, base_price in region_prices.items():
            price = base_price
            for i in range(days):
                date = start_date + timedelta(days=i)
                month = date.month

                # Apply seasonal multiplier
                seasonal = SEASONAL_PATTERN[month]

                # Add realistic market noise (±8%)
                noise = np.random.normal(1.0, 0.08)

                # Add a slow upward trend (inflation ~15% annually in Nigeria)
                inflation = 1 + (0.15 * i / 365)

                # Occasional supply shock (e.g., flood, drought, transport strike)
                shock = 1.0
                if np.random.random() < 0.02:  # 2% chance per day
                    shock = np.random.choice([0.75, 1.35])  # sudden drop or spike

                daily_price = round(base_price * seasonal * noise * inflation * shock, 2)
                daily_price = max(daily_price, base_price * 0.4)  # floor at 40% of base

                rows.append({
                    "date": date.strftime("%Y-%m-%d"),
                    "crop_type": crop,
                    "region": region,
                    "price_ngn_per_kg": daily_price,
                    "month": month,
                    "day_of_year": date.timetuple().tm_yday,
                    "day_of_week": date.weekday(),
                    "seasonal_factor": seasonal
                })

    df = pd.DataFrame(rows)
    df.to_csv("data/price_history.csv", index=False)
    print(f"Generated {len(df)} price records")
    print(df.groupby("crop_type")["price_ngn_per_kg"].mean().round(0))
    return df

if __name__ == "__main__":
    generate_price_history()