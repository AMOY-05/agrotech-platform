import pandas as pd
import numpy as np

np.random.seed(42)

CROPS = ["maize", "tomato", "cassava", "rice", "yam", "pepper", "cowpea"]
SOIL_TYPES = ["loamy", "sandy", "clay", "silty"]
REGIONS = ["Lagos", "Kano", "Oyo", "Kaduna", "Rivers", "Plateau", "Benue", "Bauchi"]

# Base yield (kg per hectare) under ideal conditions, per crop
BASE_YIELD_PER_HECTARE = {
    "maize": 2500,
    "tomato": 15000,
    "cassava": 12000,
    "rice": 3500,
    "yam": 10000,
    "pepper": 8000,
    "cowpea": 1200
}

# Soil quality multiplier
SOIL_MULTIPLIER = {
    "loamy": 1.15,
    "sandy": 0.85,
    "clay": 0.95,
    "silty": 1.05
}

def generate_sample(n_samples=5000):
    rows = []

    for _ in range(n_samples):
        crop = np.random.choice(CROPS)
        farm_size = round(np.random.uniform(0.5, 10.0), 2)
        region = np.random.choice(REGIONS)
        soil = np.random.choice(SOIL_TYPES)
        rainfall = round(np.random.normal(1200, 400), 1)
        rainfall = max(200, min(rainfall, 2500))  # realistic bounds for Nigeria
        temperature = round(np.random.normal(27, 3), 1)
        temperature = max(18, min(temperature, 38))
        fertilizer = np.random.choice([0, 1], p=[0.35, 0.65])

        base = BASE_YIELD_PER_HECTARE[crop]
        soil_mult = SOIL_MULTIPLIER[soil]

        # Rainfall effect: yield peaks around 1000-1500mm, drops outside that range
        rainfall_factor = 1.0 - (abs(rainfall - 1250) / 2500)
        rainfall_factor = max(0.4, rainfall_factor)

        # Temperature effect: most crops prefer 24-30°C
        temp_factor = 1.0 - (abs(temperature - 27) / 25)
        temp_factor = max(0.5, temp_factor)

        fertilizer_boost = 1.25 if fertilizer == 1 else 1.0

        # Some random noise to simulate real-world variability
        noise = np.random.normal(1.0, 0.1)

        yield_per_hectare = base * soil_mult * rainfall_factor * temp_factor * fertilizer_boost * noise
        total_yield_kg = round(yield_per_hectare * farm_size, 1)

        rows.append({
            "crop_type": crop,
            "farm_size_hectares": farm_size,
            "region": region,
            "soil_type": soil,
            "rainfall_mm": rainfall,
            "temperature_celsius": temperature,
            "fertilizer_used": fertilizer,
            "yield_kg": max(0, total_yield_kg)
        })

    return pd.DataFrame(rows)


if __name__ == "__main__":
    df = generate_sample(5000)
    df.to_csv("data/yield_training_data.csv", index=False)
    print(f"Generated {len(df)} samples")
    print(df.head())
    print(f"\nYield stats:\n{df['yield_kg'].describe()}")