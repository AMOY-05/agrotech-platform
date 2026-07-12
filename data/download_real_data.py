"""
Downloads real Nigerian agricultural data from:
1. WFP/HDX - Food prices
2. Our World in Data (FAO) - Crop yields
3. NASA POWER - Historical weather by region
"""
import httpx
import asyncio
import pandas as pd
import io
import json
from pathlib import Path

DATA_DIR = Path("data/real")
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Comprehensive African crop mapping — covers all major crops across West, East, 
# Central and Southern Africa found in WFP datasets
CROP_MAPPING = {
    # ── Cereals & Grains ──
    "Maize": "maize",
    "Maize (white)": "maize",
    "Maize (yellow)": "maize",
    "Maize flour": "maize_flour",
    "Millet": "millet",
    "Millet (bulrush/pearl)": "millet",
    "Sorghum": "sorghum",
    "Sorghum (white)": "sorghum",
    "Sorghum (red)": "sorghum",
    "Wheat": "wheat",
    "Wheat flour": "wheat_flour",
    "Rice": "rice",
    "Rice (imported)": "rice",
    "Rice (local)": "rice",
    "Rice (milled)": "rice",
    "Rice (husked)": "rice",
    "Rice (paddy)": "rice_paddy",
    "Teff": "teff",
    "Barley": "barley",
    "Fonio": "fonio",

    # ── Roots & Tubers ──
    "Cassava": "cassava",
    "Cassava (fresh)": "cassava",
    "Cassava (dried)": "cassava_dried",
    "Gari (cassava flour)": "gari",
    "Cassava flour": "gari",
    "Yam": "yam",
    "Yams": "yam",
    "Sweet potatoes": "sweet_potato",
    "Sweet potato": "sweet_potato",
    "Irish potatoes": "potato",
    "Potatoes": "potato",
    "Cocoyam": "cocoyam",
    "Cocoyams": "cocoyam",

    # ── Vegetables ──
    "Tomatoes": "tomato",
    "Tomato": "tomato",
    "Pepper": "pepper",
    "Peppers (hot)": "pepper",
    "Onions": "onion",
    "Onion": "onion",
    "Okra": "okra",
    "Cabbage": "cabbage",
    "Spinach": "spinach",
    "Lettuce": "lettuce",
    "Eggplant": "eggplant",
    "Garden eggs": "eggplant",
    "Pumpkin": "pumpkin",
    "Watermelon": "watermelon",
    "Cucumber": "cucumber",
    "Carrot": "carrot",
    "Okra": "okra",
    "Garden egg": "garden_egg",
    "Garden eggs": "garden_egg",
    "Bitter leaf": "bitter_leaf",
    "Ugu": "fluted_pumpkin",
    "Pumpkin leaves": "fluted_pumpkin",
    "Waterleaf": "waterleaf",
    "Jute mallow": "jute_mallow",

    # ── Legumes & Pulses ──
    "Cowpeas": "cowpea",
    "Cowpea": "cowpea",
    "Beans (niebe)": "cowpea",
    "Beans": "beans",
    "Black-eyed peas": "cowpea",
    "Soybeans": "soybean",
    "Soya beans": "soybean",
    "Lentils": "lentil",
    "Chickpeas": "chickpea",
    "Groundnuts (shelled)": "groundnut",
    "Groundnuts (unshelled)": "groundnut",
    "Groundnuts": "groundnut",
    "Peanuts": "groundnut",
    "Pigeon peas": "pigeon_pea",

    # ── Fruits ──
    "Plantain": "plantain",
    "Plantains": "plantain",
    "Banana": "banana",
    "Bananas": "banana",
    "Mango": "mango",
    "Mangoes": "mango",
    "Orange": "orange",
    "Oranges": "orange",
    "Pineapple": "pineapple",
    "Pineapples": "pineapple",
    "Avocado": "avocado",
    "Papaya": "papaya",
    "Coconut": "coconut",

    # ── Cash Crops & Others ──
    "Palm oil": "palm_oil",
    "Palm oil (crude)": "palm_oil",
    "Vegetable oil": "vegetable_oil",
    "Groundnut oil": "groundnut_oil",
    "Sugar": "sugar",
    "Salt": "salt",
    "Cocoa": "cocoa",
    "Coffee": "coffee",
    "Cotton": "cotton",
    "Rubber": "rubber",
    "Coffee": "coffee",
    "Sugarcane": "sugarcane",

    # ── Animal Products ──
    "Beef": "beef",
    "Goat meat": "goat",
    "Mutton": "mutton",
    "Chicken": "chicken",
    "Fish (dried)": "dried_fish",
    "Fish (fresh)": "fresh_fish",
    "Eggs": "eggs",
    "Milk": "milk",

    # ── Processed Foods ──
    "Bread": "bread",
    "Noodles": "noodles",

    # Spices
    "Ginger": "ginger",
    "Garlic": "garlic",
    "Pepper (black)": "black_pepper",

    # Other legumes
    "Bambara nut": "bambara_nut",
    "Pigeon pea": "pigeon_pea",
    "Locust beans": "locust_bean",
    "Sesame": "sesame",
    "Sunflower": "sunflower",

    # Processed
    "Palm kernel oil": "palm_kernel_oil",
    "Groundnut oil": "groundnut_oil",
    "Shea butter": "shea",
    "Gari": "gari",
    "Fufu": "fufu",
}
# Add these to CROP_MAPPING (merge with existing)
CROP_MAPPING_TIER2 = {
    # Vegetables
    "Okra": "okra",
    "Garden egg": "garden_egg",
    "Garden eggs": "garden_egg",
    "Bitter leaf": "bitter_leaf",
    "Pumpkin": "fluted_pumpkin",
    "Pumpkin leaves": "fluted_pumpkin",
    "Waterleaf": "waterleaf",
    "Cabbage": "cabbage",
    "Carrot": "carrot",
    "Cucumber": "cucumber",
    "Lettuce": "lettuce",
    "Eggplant": "eggplant",

    # Fruits
    "Mango": "mango",
    "Mangoes": "mango",
    "Pineapple": "pineapple",
    "Pineapples": "pineapple",
    "Papaya": "papaya",
    "Pawpaw": "papaya",
    "Avocado": "avocado",
    "Coconut": "coconut",
    "Watermelon": "watermelon",

    # Cash crops
    "Palm oil (crude)": "palm_oil",
    "Cocoa": "cocoa",
    "Coffee": "coffee",
    "Cotton": "cotton",
    "Rubber": "rubber",
    "Sugarcane": "sugarcane",
    "Shea": "shea",

    # Spices & condiments
    "Ginger": "ginger",
    "Garlic": "garlic",
    "Pepper (black)": "black_pepper",
    "Crayfish": "crayfish",
    "Locust beans": "locust_bean",

    # Other legumes & grains
    "Pigeon pea": "pigeon_pea",
    "Bambara nut": "bambara_nut",
    "Sesame": "sesame",
    "Sunflower": "sunflower",
    "Soyabeans": "soybean",

    # Processed
    "Palm kernel oil": "palm_kernel_oil",
    "Groundnut oil": "groundnut_oil",
    "Vegetable oil": "vegetable_oil",
    "Gari": "gari",
    "Fufu": "fufu",
    "Semovita": "semovita",

    # Animal products
    "Goat": "goat",
    "Goat meat": "goat",
    "Mutton": "mutton",
    "Pork": "pork",
    "Tilapia": "tilapia",
    "Catfish": "catfish",
    "Fish (smoked)": "smoked_fish",
    "Milk (fresh)": "milk",
    "Butter": "butter",
}

# Tier 2 OWID crop slugs to try
OWID_CROPS_TIER2 = {
    "plantain": "banana-plantains-yield",
    "sweet_potato": "sweet-potato-yield",
    "palm_oil": "oil-palm-fruit-yields",
    "sugarcane": "sugar-cane-yields",
    "cotton": "cotton-yields",
    "sesame": "sesame-yield",
    "groundnut": "groundnut-yields",
    "sorghum": "sorghum-yields",
    "millet": "millet-yields",
    "yam": "yam-yield",
    "cocoyam": "taro-yield",
    "ginger": "ginger-yield",
    "coffee": "coffee-yields",
    "rubber": "natural-rubber-yield",
    "soybean": "soybean-yields",
    "okra": "okra-yield",
    "pineapple": "pineapple-yield",
    "mango": "mango-yield",
    "avocado": "avocado-yield",
    "coconut": "coconut-yield",
    "watermelon": "watermelon-yield",
}


# All 36 Nigerian states + FCT with coordinates
NIGERIAN_REGIONS = {
    "Lagos": (6.5244, 3.3792),
    "Kano": (12.0022, 8.5920),
    "Abuja": (9.0765, 7.3986),
    "Oyo": (7.3775, 3.9470),
    "Rivers": (4.8156, 7.0498),
    "Kaduna": (10.5222, 7.4383),
    "Enugu": (6.4584, 7.5464),
    "Bauchi": (10.3158, 9.8442),
    "Katsina": (12.9889, 7.6006),
    "Benue": (7.7322, 8.5391),
    "Ogun": (7.1600, 3.3500),
    "Delta": (5.5320, 5.8987),
    "Anambra": (6.2104, 7.0691),
    "Sokoto": (13.0059, 5.2476),
    "Zamfara": (12.1704, 6.6672),
    "Kebbi": (12.4539, 4.1975),
    "Niger": (9.6139, 6.5569),
    "Kwara": (8.4966, 4.5426),
    "Osun": (7.5629, 4.5200),
    "Ondo": (7.2526, 5.1975),
    "Ekiti": (7.7190, 5.3110),
    "Edo": (6.3350, 5.6270),
    "Cross River": (4.9517, 8.3220),
    "Akwa Ibom": (5.0077, 7.8536),
    "Imo": (5.4836, 7.0333),
    "Abia": (5.4527, 7.5249),
    "Ebonyi": (6.2649, 8.0137),
    "Kogi": (7.7973, 6.7367),
    "Nasarawa": (8.4925, 8.5220),
    "Plateau": (9.8965, 8.8583),
    "Taraba": (8.8954, 11.3735),
    "Adamawa": (9.2035, 12.4954),
    "Gombe": (10.2791, 11.1670),
    "Yobe": (12.2939, 11.7494),
    "Borno": (11.8311, 13.1508),
    "Jigawa": (11.8580, 9.3484),
    "Bayelsa": (4.7729, 6.0698),
}

# Updated OWID crop slugs — verified working
OWID_CROPS = {
    "maize": "maize-yields",
    "rice": "rice-yields",
    "cassava": "cassava-yields",
    "wheat": "wheat-yields",
    "soybean": "soybean-yields",
    "sweet_potato": "sweet-potato-yields",
    "potato": "potato-yields",
    "tomato": "tomato-yields",
    "cocoa": "cocoa-bean-yields",
    "groundnut": "groundnut-yields",
    "sorghum": "sorghum-yields",
    "millet": "millet-yields",
    "yam": "yam-yields",
    "banana": "banana-yields",
    "sugarcane": "sugarcane-yields",
    "palm_oil": "oil-palm-fruit-yields",
    "cotton": "cotton-yields",
    "coffee": "coffee-bean-yields",
    "plantain": "plantain-and-banana-yields",
    "sweet_potato": "sweet-potatoes-yield",
    "palm_oil": "oil-palm-yield",
    "sugarcane": "sugar-cane-yield",
    "cotton": "cotton-yields",
    "groundnut": "groundnut-yields",
    "ginger": "ginger-yields",
    "okra": "okra-yields",
}


async def download_wfp_prices():
    """Downloads complete WFP Nigerian food price dataset."""
    print("📥 Downloading WFP Nigerian food prices...")

    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        response = await client.get(
            "https://data.humdata.org/dataset/42db041f-7aaf-4ab4-961f-2a12096861e7"
            "/resource/12b51155-0cd3-4806-9924-61ede4077591/download/wfp_food_prices_nga.csv",
            headers={"User-Agent": "Mozilla/5.0 AgroTech-Research/1.0"}
        )

        if response.status_code != 200:
            print(f"❌ WFP download failed: {response.status_code}")
            return None

        df = pd.read_csv(io.StringIO(response.text))
        print(f"✅ Downloaded {len(df)} price records")

        # Clean and normalize
        df["date"] = pd.to_datetime(df["date"])
        df["commodity_normalized"] = df["commodity"].map(CROP_MAPPING)
        df = df.dropna(subset=["commodity_normalized"])
        df = df[df["price"] > 0]
        df = df[df["pricetype"].isin(["Retail", "Wholesale"])]

        # Filter out obviously wrong prices (per-unit vs per-kg confusion)
        # Rice shouldn't be > ₦2000/kg, yam > ₦1500/kg at retail
        PRICE_CAPS = {
            "maize": 2000, "rice": 2000, "tomato": 2000,
            "yam": 1500, "cassava": 1000, "millet": 1500,
            "sorghum": 1500, "cowpea": 3000, "groundnut": 3000,
            "onion": 2000
        }
        for crop, cap in PRICE_CAPS.items():
            mask = (df["commodity_normalized"] == crop) & (df["price"] > cap)
            df = df[~mask]

        # Keep only relevant columns
        df_clean = df[[
            "date", "admin1", "market", "commodity_normalized",
            "commodity", "price", "usdprice", "pricetype",
            "latitude", "longitude"
        ]].copy()
        df_clean.columns = [
            "date", "state", "market", "crop_type",
            "original_commodity", "price_ngn", "price_usd",
            "price_type", "latitude", "longitude"
        ]

        # Save
        output_path = DATA_DIR / "wfp_prices_nigeria.csv"
        df_clean.to_csv(output_path, index=False)
        print(f"✅ Saved {len(df_clean)} cleaned price records to {output_path}")

        # Print summary
        print(f"\nCrops covered: {df_clean['crop_type'].unique()}")
        print(f"States covered: {df_clean['state'].unique()}")
        print(f"Date range: {df_clean['date'].min()} to {df_clean['date'].max()}")

        # Show latest prices for key crops
        print("\n📊 Latest prices for key crops (Retail, NGN/kg):")
        latest = df_clean[df_clean["price_type"] == "Retail"].copy()
        latest = latest.sort_values("date")
        for crop in ["maize", "rice", "tomato", "cassava", "yam"]:
            crop_df = latest[latest["crop_type"] == crop]
            if len(crop_df) > 0:
                recent = crop_df.tail(10)
                avg_price = recent["price_ngn"].mean()
                print(f"  {crop}: ₦{avg_price:.0f}/kg (avg of last 10 records)")

        return df_clean


async def download_owid_yields():
    """Downloads real Nigerian crop yield data from Our World in Data."""
    print("\n📥 Downloading crop yield data from OWID/FAO...")

    all_yields = {}

    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        for crop, slug in OWID_CROPS.items():
            try:
                response = await client.get(
                    f"https://ourworldindata.org/grapher/{slug}.csv",
                    params={"country": "Nigeria"}
                )

                if response.status_code == 200:
                    lines = [l for l in response.text.strip().split("\n")
                             if "Nigeria" in l]
                    if lines:
                        yields_by_year = {}
                        for line in lines:
                            parts = line.split(",")
                            if len(parts) >= 4:
                                try:
                                    year = int(parts[2])
                                    # Convert tonnes/ha to kg/ha
                                    yield_kg = float(parts[3]) * 1000
                                    yields_by_year[year] = round(yield_kg, 1)
                                except ValueError:
                                    continue

                        all_yields[crop] = yields_by_year
                        recent_years = {k: v for k, v in yields_by_year.items()
                                       if k >= 2020}
                        print(f"  ✅ {crop}: {recent_years}")
                    else:
                        print(f"  ⚠️ {crop}: No Nigeria data found")
                else:
                    print(f"  ❌ {crop}: Status {response.status_code}")

            except Exception as e:
                print(f"  ❌ {crop}: {e}")

    # Save yields
    output_path = DATA_DIR / "real_yields_nigeria.json"
    with open(output_path, "w") as f:
        json.dump(all_yields, f, indent=2)
    print(f"\n✅ Saved yield data to {output_path}")

    return all_yields


async def download_nasa_weather():
    """Downloads NASA POWER historical weather for Nigerian regions."""
    print("\n📥 Downloading NASA POWER weather data for Nigerian regions...")

    all_weather = {}

    async with httpx.AsyncClient(timeout=60.0) as client:
        for region, (lat, lon) in NIGERIAN_REGIONS.items():
            try:
                response = await client.get(
                    "https://power.larc.nasa.gov/api/temporal/monthly/point",
                    params={
                        "parameters": "T2M,PRECTOTCORR,RH2M,ALLSKY_SFC_SW_DWN",
                        "community": "AG",
                        "longitude": str(lon),
                        "latitude": str(lat),
                        "start": "2015",
                        "end": "2024",
                        "format": "JSON"
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    params = data.get("properties", {}).get("parameter", {})

                    # Organize by month
                    monthly_data = {}
                    for month in range(1, 13):
                        month_str = f"{month:02d}"
                        temps = []
                        rains = []
                        humidity = []

                        for key, val in params.get("T2M", {}).items():
                            if key[4:] == month_str and val != -999:
                                temps.append(val)
                        for key, val in params.get("PRECTOTCORR", {}).items():
                            if key[4:] == month_str and val != -999:
                                rains.append(val)
                        for key, val in params.get("RH2M", {}).items():
                            if key[4:] == month_str and val != -999:
                                humidity.append(val)

                        if temps:
                            monthly_data[month] = {
                                "avg_temp_celsius": round(
                                    sum(temps) / len(temps), 1
                                ),
                                "avg_rainfall_mm": round(
                                    sum(rains) / len(rains), 1
                                ) if rains else 0,
                                "avg_humidity_pct": round(
                                    sum(humidity) / len(humidity), 1
                                ) if humidity else 0
                            }

                    all_weather[region] = {
                        "lat": lat,
                        "lon": lon,
                        "monthly_averages": monthly_data
                    }
                    avg_annual_rain = sum(
                        m["avg_rainfall_mm"] for m in monthly_data.values()
                    )
                    print(f"  ✅ {region}: avg annual rainfall {avg_annual_rain:.0f}mm")

                else:
                    print(f"  ❌ {region}: Status {response.status_code}")

            except Exception as e:
                print(f"  ❌ {region}: {e}")

    # Save weather data
    output_path = DATA_DIR / "nasa_weather_nigeria.json"
    with open(output_path, "w") as f:
        json.dump(all_weather, f, indent=2)
    print(f"\n✅ Saved weather data to {output_path}")

    return all_weather

async def download_tier2_data():
    """Downloads Tier 2 crop data and merges with existing."""
    print("\n📥 Downloading Tier 2 crop data...")

    # ── Step 1: Re-download WFP with expanded crop mapping ──
    print("\n1. Expanding WFP crop coverage...")

    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        response = await client.get(
            "https://data.humdata.org/dataset/42db041f-7aaf-4ab4-961f-2a12096861e7"
            "/resource/12b51155-0cd3-4806-9924-61ede4077591/download/wfp_food_prices_nga.csv",
            headers={"User-Agent": "Mozilla/5.0 AgroTech-Research/1.0"}
        )

        if response.status_code == 200:
            df = pd.read_csv(io.StringIO(response.text))

            # Merge all crop mappings
            full_mapping = {**CROP_MAPPING, **CROP_MAPPING_TIER2}
            df["commodity_normalized"] = df["commodity"].map(full_mapping)
            df = df.dropna(subset=["commodity_normalized"])
            df = df[df["price"] > 0]
            df = df[df["pricetype"].isin(["Retail", "Wholesale"])]

            # Price caps for new crops
            PRICE_CAPS_TIER2 = {
                "palm_oil": 5000, "cocoa": 20000, "ginger": 5000,
                "garlic": 8000, "okra": 3000, "mango": 2000,
                "pineapple": 3000, "watermelon": 1000, "coconut": 2000,
                "catfish": 5000, "tilapia": 4000, "goat": 10000,
                "plantain": 1000, "sweet_potato": 1500
            }

            for crop, cap in PRICE_CAPS_TIER2.items():
                mask = (
                    (df["commodity_normalized"] == crop) &
                    (df["price"] > cap)
                )
                df = df[~mask]

            df_clean = df[[
                "date", "admin1", "market", "commodity_normalized",
                "commodity", "price", "usdprice", "pricetype",
                "latitude", "longitude"
            ]].copy()
            df_clean.columns = [
                "date", "state", "market", "crop_type",
                "original_commodity", "price_ngn", "price_usd",
                "price_type", "latitude", "longitude"
            ]

            output_path = DATA_DIR / "wfp_prices_nigeria.csv"
            df_clean.to_csv(output_path, index=False)
            print(f"✅ Updated WFP data: {len(df_clean)} records")
            print(f"   Crops: {sorted(df_clean['crop_type'].unique())}")

    # ── Step 2: Try OWID Tier 2 crops ──
    print("\n2. Fetching Tier 2 yield data from OWID...")

    # Load existing yield data
    yield_file = DATA_DIR / "real_yields_nigeria.json"
    if yield_file.exists():
        with open(yield_file) as f:
            existing_yields = json.load(f)
    else:
        existing_yields = {}

    new_yields = 0
    failed_yields = []

    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        for crop, slug in OWID_CROPS_TIER2.items():
            if crop in existing_yields:
                print(f"  ⏭️  {crop}: already have data")
                continue

            try:
                response = await client.get(
                    f"https://ourworldindata.org/grapher/{slug}.csv",
                    params={"country": "Nigeria"}
                )

                if response.status_code == 200:
                    lines = [
                        l for l in response.text.strip().split("\n")
                        if "Nigeria" in l
                    ]
                    if lines:
                        yields_by_year = {}
                        for line in lines:
                            parts = line.split(",")
                            if len(parts) >= 4:
                                try:
                                    year = int(parts[2])
                                    yield_kg = float(parts[3]) * 1000
                                    yields_by_year[year] = round(yield_kg, 1)
                                except ValueError:
                                    continue

                        if yields_by_year:
                            existing_yields[crop] = yields_by_year
                            recent = {
                                k: v for k, v in yields_by_year.items()
                                if k >= 2020
                            }
                            print(f"  ✅ {crop}: {recent}")
                            new_yields += 1
                        else:
                            failed_yields.append(crop)
                            print(f"  ⚠️  {crop}: no Nigeria data in response")
                    else:
                        failed_yields.append(crop)
                        print(f"  ⚠️  {crop}: empty response")
                else:
                    failed_yields.append(crop)
                    print(f"  ❌ {crop}: status {response.status_code} (slug: {slug})")

            except Exception as e:
                failed_yields.append(crop)
                print(f"  ❌ {crop}: {e}")

    # Save updated yields
    with open(yield_file, "w") as f:
        json.dump(existing_yields, f, indent=2)
    print(f"\n✅ Yield data updated: {new_yields} new crops added")
    print(f"   Total crops with real yield data: {len(existing_yields)}")

    if failed_yields:
        print(f"\n⚠️  No OWID data found for: {failed_yields}")
        print("   These crops will use WFP price data + LLM knowledge fallback")

    # ── Step 3: Summary ──
    print("\n" + "="*50)
    print("TIER 2 DATA SUMMARY")
    print("="*50)
    print(f"Price records: check wfp_prices_nigeria.csv")
    print(f"Yield datasets: {len(existing_yields)} crops total")
    print(f"Weather regions: 37 (unchanged)")

async def main():
    print("🌾 AgroTech Real Data Pipeline")
    print("="*50)

    # Full download (run once)
    prices_df = await download_wfp_prices()
    yields = await download_owid_yields()
    weather = await download_nasa_weather()

    # Tier 2 expansion
    await download_tier2_data()

    print("\n" + "="*50)
    print("✅ ALL DATA DOWNLOADED")
    print("="*50)