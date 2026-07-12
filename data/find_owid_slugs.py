"""
Finds correct OWID slugs for African crops by searching their API.
"""
import httpx
import asyncio

# Crops we need to find
CROPS_TO_FIND = [
    "yam", "sorghum", "millet", "groundnut", "plantain",
    "sweet potato", "palm oil", "ginger", "okra", "mango",
    "pineapple", "coconut", "watermelon", "cotton", "sesame", "rubber"
]

async def search_owid_charts(crop: str, client: httpx.AsyncClient):
    """Searches OWID for charts related to a crop."""
    try:
        response = await client.get(
            "https://ourworldindata.org/search",
            params={"q": f"{crop} yield"},
            timeout=15.0,
            follow_redirects=True
        )

        # Also try direct grapher search
        response2 = await client.get(
            "https://ourworldindata.org/grapher/search",
            params={"q": f"{crop} yield Nigeria"},
            timeout=15.0,
            follow_redirects=True
        )

        return response.status_code, response2.status_code

    except Exception as e:
        return None, str(e)


async def try_slug_variations(crop: str, client: httpx.AsyncClient):
    """Tries multiple slug variations for a crop."""
    # Generate slug variations
    crop_slug = crop.lower().replace(" ", "-")

    variations = [
        f"{crop_slug}-yield",
        f"{crop_slug}-yields",
        f"{crop_slug}-production",
        f"yield-{crop_slug}",
        f"{crop_slug}s-yield",
        f"{crop_slug}s-yields",
    ]

    # Special cases
    special = {
        "yam": ["yam-yield", "yams-yield", "yam-yields"],
        "sorghum": ["sorghum-yield", "sorghum-yields", "sorghum-production"],
        "millet": ["millet-yield", "millet-yields", "pearl-millet-yield"],
        "groundnut": ["groundnut-yield", "groundnuts-yield", "peanut-yield", "groundnut-yields"],
        "plantain": ["plantain-yield", "plantains-yield", "banana-plantain-yield"],
        "sweet potato": ["sweet-potato-yields", "sweet-potatoes-yield", "sweetpotato-yield"],
        "palm oil": ["palm-oil-yield", "oil-palm-yield", "palm-oil-yields", "oil-palm-yields"],
        "ginger": ["ginger-yield", "ginger-yields", "ginger-production"],
        "okra": ["okra-yield", "okra-yields"],
        "mango": ["mango-yield", "mango-yields", "mangoes-yield"],
        "pineapple": ["pineapple-yield", "pineapples-yield", "pineapple-yields"],
        "coconut": ["coconut-yield", "coconut-yields", "coconuts-yield"],
        "watermelon": ["watermelon-yield", "watermelon-yields"],
        "cotton": ["cotton-yield", "cotton-yields", "cotton-lint-yield"],
        "sesame": ["sesame-yield", "sesame-yields", "sesameseed-yield"],
        "rubber": ["rubber-yield", "natural-rubber-yields", "rubber-yields"],
    }

    all_variations = special.get(crop, []) + variations

    for slug in all_variations:
        try:
            response = await client.get(
                f"https://ourworldindata.org/grapher/{slug}.csv",
                params={"country": "Nigeria"},
                timeout=10.0,
                follow_redirects=True
            )

            if response.status_code == 200:
                lines = [l for l in response.text.strip().split("\n")
                         if "Nigeria" in l]
                if lines:
                    # Get a sample
                    sample = lines[-1].split(",")
                    if len(sample) >= 4:
                        return slug, float(sample[3]) * 1000
                    return slug, "found but no numeric data"

        except Exception:
            continue

    return None, None


async def main():
    print("🔍 Searching for correct OWID slugs for African crops...")
    print("="*60)

    found = {}
    not_found = []

    async with httpx.AsyncClient(follow_redirects=True) as client:
        for crop in CROPS_TO_FIND:
            print(f"\nSearching: {crop}...")
            slug, value = await try_slug_variations(crop, client)

            if slug:
                found[crop] = {"slug": slug, "sample_kg_ha": value}
                print(f"  ✅ Found: '{slug}' → {value:.0f} kg/ha" if isinstance(value, float) else f"  ✅ Found: '{slug}'")
            else:
                not_found.append(crop)
                print(f"  ❌ Not found on OWID")

    print("\n" + "="*60)
    print("RESULTS SUMMARY")
    print("="*60)
    print(f"\n✅ Found ({len(found)}):")
    for crop, data in found.items():
        print(f"  '{crop}': '{data['slug']}'")

    print(f"\n❌ Not on OWID ({len(not_found)}):")
    for crop in not_found:
        print(f"  - {crop}")

    print("\n💡 For crops not on OWID, we'll use:")
    print("   - WFP price data (already downloaded)")
    print("   - NASA weather for yield estimation")
    print("   - LLM agricultural knowledge as fallback")


asyncio.run(main())