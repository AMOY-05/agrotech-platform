"""
Downloads Tier 2 crop yield data from OWID/FAO.
Runs independently — doesn't re-download WFP data.
"""
import httpx
import asyncio
import json
from pathlib import Path

DATA_DIR = Path("data/real")
DATA_DIR.mkdir(parents=True, exist_ok=True)

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
    "ginger": "ginger-yield",
    "coffee": "coffee-yields",
    "soybean": "soybean-yields",
    "pineapple": "pineapple-yield",
    "mango": "mango-yield",
    "coconut": "coconut-yield",
    "watermelon": "watermelon-yield",
    "okra": "okra-yield",
    "cocoa": "cocoa-bean-yields",
    "rubber": "natural-rubber-yield",
}


async def download_tier2_yields():
    """Downloads Tier 2 yield data only."""
    print("📥 Fetching Tier 2 yield data from OWID/FAO...")
    print("(Testing each crop slug — this may take 2-3 minutes)\n")

    # Load existing yield data
    yield_file = DATA_DIR / "real_yields_nigeria.json"
    if yield_file.exists():
        with open(yield_file) as f:
            existing_yields = json.load(f)
        print(f"Existing yields: {list(existing_yields.keys())}\n")
    else:
        existing_yields = {}

    new_yields = 0
    failed = []

    async with httpx.AsyncClient(
        timeout=30.0,
        follow_redirects=True
    ) as client:
        for crop, slug in OWID_CROPS_TIER2.items():
            if crop in existing_yields:
                print(f"⏭️  {crop}: already have data — skipping")
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
                            print(f"✅ {crop}: {recent}")
                            new_yields += 1
                        else:
                            failed.append(f"{crop} (empty)")
                            print(f"⚠️  {crop}: no Nigeria data")
                    else:
                        failed.append(f"{crop} (no Nigeria rows)")
                        print(f"⚠️  {crop}: not found for Nigeria")
                else:
                    failed.append(f"{crop} ({response.status_code})")
                    print(f"❌ {crop}: HTTP {response.status_code} — slug '{slug}' may be wrong")

            except Exception as e:
                failed.append(f"{crop} (error)")
                print(f"❌ {crop}: {e}")

    # Save updated yields
    with open(yield_file, "w") as f:
        json.dump(existing_yields, f, indent=2)

    print("\n" + "="*50)
    print(f"✅ {new_yields} new crops added")
    print(f"📊 Total crops with real yield data: {len(existing_yields)}")
    print(f"All crops: {sorted(existing_yields.keys())}")

    if failed:
        print(f"\n⚠️  Failed/missing ({len(failed)}):")
        for f in failed:
            print(f"   - {f}")
        print("\nThese will use LLM knowledge fallback in the agent.")

    print("="*50)


asyncio.run(download_tier2_yields())