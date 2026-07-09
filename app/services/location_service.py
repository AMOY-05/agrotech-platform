import httpx
from loguru import logger
from typing import Optional

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Headers required by Nominatim (they require a User-Agent)
HEADERS = {
    "User-Agent": "AgroTechPlatform/1.0 (Nigerian Farmer Assistant)"
}

# OSM tags that actually work for Nigerian locations
OVERPASS_TAGS = {
  "insecticide": [
      '["amenity"="marketplace"]',
      '["shop"="supermarket"]',
      '["shop"="convenience"]',
      '["shop"="general"]',
  ],
  "fertilizer": [
      '["amenity"="marketplace"]',
      '["shop"="supermarket"]',
      '["shop"="general"]',
  ],
  "pesticide": [
      '["amenity"="marketplace"]',
      '["shop"="supermarket"]',
      '["shop"="convenience"]',
  ],
  "herbicide": [
      '["amenity"="marketplace"]',
      '["shop"="general"]',
  ],
  "seeds": [
      '["amenity"="marketplace"]',
      '["shop"="supermarket"]',
      '["shop"="general"]',
  ],
  "equipment": [
      '["shop"="machinery"]',
      '["amenity"="marketplace"]',
      '["shop"="hardware"]',
  ],
  "feed": [
      '["amenity"="marketplace"]',
      '["shop"="general"]',
      '["shop"="supermarket"]',
  ],
  "veterinary": [
      '["amenity"="veterinary"]',
      '["healthcare"="veterinary"]',
      '["amenity"="marketplace"]',
  ],
  "market": [
      '["amenity"="marketplace"]',
      '["shop"="supermarket"]',
  ],
  "general": [
      '["amenity"="marketplace"]',
      '["shop"="supermarket"]',
      '["shop"="general"]',
      '["shop"="convenience"]',
  ]
}

# Nigerian city coordinates fallback
NIGERIAN_CITY_COORDS = {
    "lagos": (6.5244, 3.3792),
    "kano": (12.0022, 8.5920),
    "abuja": (9.0765, 7.3986),
    "ibadan": (7.3775, 3.9470),
    "oyo": (7.3775, 3.9470),
    "rivers": (4.8156, 7.0498),
    "port harcourt": (4.8156, 7.0498),
    "kaduna": (10.5222, 7.4383),
    "enugu": (6.4584, 7.5464),
    "bauchi": (10.3158, 9.8442),
    "jos": (9.8965, 8.8583),
    "plateau": (9.8965, 8.8583),
    "benue": (7.7322, 8.5391),
    "makurdi": (7.7322, 8.5391),
    "ogun": (7.1600, 3.3500),
    "abeokuta": (7.1600, 3.3500),
    "delta": (5.5320, 5.8987),
    "asaba": (6.1983, 6.7534),
    "anambra": (6.2104, 7.0691),
    "awka": (6.2104, 7.0691),
    "katsina": (12.9889, 7.6006),
    "sokoto": (13.0059, 5.2476),
    "maiduguri": (11.8311, 13.1508),
    "borno": (11.8311, 13.1508),
    "yola": (9.2035, 12.4954),
    "adamawa": (9.2035, 12.4954),
    "owerri": (5.4836, 7.0333),
    "imo": (5.4836, 7.0333),
    "calabar": (4.9517, 8.3220),
    "cross river": (4.9517, 8.3220),
    "akure": (7.2526, 5.1975),
    "ondo": (7.2526, 5.1975),
    "ilorin": (8.4966, 4.5426),
    "kwara": (8.4966, 4.5426),
    "benin city": (6.3350, 5.6270),
    "edo": (6.3350, 5.6270),
    "warri": (5.5167, 5.7500),
    "gombe": (10.2791, 11.1670),
    "minna": (9.6139, 6.5569),
    "niger": (9.6139, 6.5569),
    "lokoja": (7.7973, 6.7367),
    "kogi": (7.7973, 6.7367),
    "sokoto": (13.0059, 5.2476),
    "dutse": (11.8580, 9.3484),
    "jigawa": (11.8580, 9.3484),
    "yenagoa": (4.9267, 6.2676),
    "bayelsa": (4.7729, 6.0698),
    "uyo": (5.0377, 7.9128),
    "akwa ibom": (5.0077, 7.8536),
    "osogbo": (7.7827, 4.5418),
    "osun": (7.5629, 4.5200),
    "ekiti": (7.7190, 5.3110),
    "ado ekiti": (7.7190, 5.3110),
    "lafia": (8.4925, 8.5220),
    "nasarawa": (8.4925, 8.5220),
    "jalingo": (8.8954, 11.3735),
    "taraba": (8.8954, 11.3735),
    "gusau": (12.1704, 6.6672),
    "zamfara": (12.1704, 6.6672),
    "birnin kebbi": (12.4539, 4.1975),
    "kebbi": (12.4539, 4.1975),
}


def _detect_intent(query: str) -> str:
    """Detects what type of agro-input the farmer needs."""
    query_lower = query.lower()
    for keyword in OVERPASS_TAGS:
        if keyword in query_lower:
            return keyword
    return "general"


async def _geocode_region(client: httpx.AsyncClient, region: str) -> Optional[tuple]:
    """Converts region name to coordinates using Nominatim."""
    # First try our static lookup (faster, no API call needed)
    coords = NIGERIAN_CITY_COORDS.get(region.lower().strip())
    if coords:
        return coords

    # Fall back to Nominatim geocoding
    try:
        response = await client.get(
            NOMINATIM_URL,
            params={
                "q": f"{region}, Nigeria",
                "format": "json",
                "limit": 1,
                "countrycodes": "ng"
            },
            headers=HEADERS
        )
        data = response.json()
        if data:
            lat = float(data[0]["lat"])
            lng = float(data[0]["lon"])
            logger.info(f"Geocoded '{region}' → ({lat}, {lng})")
            return (lat, lng)
    except Exception as e:
        logger.warning(f"Geocoding failed for '{region}': {e}")

    return None


async def _overpass_search(client: httpx.AsyncClient, tag: str, lat: float, lng: float, radius: int = 15000) -> list:
    """Searches for places using Overpass API (OpenStreetMap)."""
    query = f"""
    [out:json][timeout:10];
    (
        node{tag}(around:{radius},{lat},{lng});
        way{tag}(around:{radius},{lat},{lng});
    );
    out center 5;
    """
    try:
        response = await client.post(
            OVERPASS_URL,
            content=f"data={query}",
            headers={**HEADERS, "Content-Type": "application/x-www-form-urlencoded"},
            timeout=15.0
        )
        data = response.json()
        return data.get("elements", [])
    except Exception as e:
        logger.warning(f"Overpass search failed for tag '{tag}': {e}")
        return []


def _parse_osm_element(element: dict, city_lat: float, city_lng: float) -> dict:
    """Parses an OSM element into a clean store dict."""
    tags = element.get("tags", {})

    if element.get("type") == "node":
        el_lat = element.get("lat", city_lat)
        el_lng = element.get("lon", city_lng)
    else:
        center = element.get("center", {})
        el_lat = center.get("lat", city_lat)
        el_lng = center.get("lon", city_lng)

    dist_deg = ((el_lat - city_lat)**2 + (el_lng - city_lng)**2)**0.5
    dist_km = round(dist_deg * 111, 1)

    address_parts = []
    for field in ["addr:housenumber", "addr:street", "addr:city", "addr:state"]:
        if tags.get(field):
            address_parts.append(tags[field])
    address = ", ".join(address_parts) if address_parts else "Address not listed — ask locals for directions"

    place_type = tags.get("amenity") or tags.get("shop") or "store"

    # Give farmers context about what they'll find there
    type_hint = {
        "marketplace": "market — look for agro-input sections inside",
        "supermarket": "supermarket — check the agro/chemical section",
        "hardware": "hardware store — may stock farm chemicals",
        "general": "general store — ask for farm inputs",
        "convenience": "convenience store — may stock basic farm inputs",
        "machinery": "machinery dealer — farm equipment available",
        "veterinary": "veterinary clinic",
    }.get(place_type, place_type)

    return {
        "name": tags.get("name") or tags.get("brand") or "Unnamed Location",
        "address": address,
        "phone": tags.get("phone") or tags.get("contact:phone") or "Not listed",
        "opening_hours": tags.get("opening_hours") or "Not listed",
        "distance_km": dist_km,
        "type": type_hint
    }


async def find_nearby_agro_stores(region: str, query: str) -> dict:
    """
    Finds nearby agro-input stores using OpenStreetMap (Nominatim + Overpass).
    Completely free, no API key required.
    """
    async with httpx.AsyncClient(timeout=15.0) as client:

        # Step 1: Get coordinates
        coords = await _geocode_region(client, region)
        if not coords:
            return {
                "found": False,
                "region": region,
                "message": f"Could not find location '{region}'. Please use a major Nigerian city name like Lagos, Kano, or Abuja.",
                "stores": []
            }

        lat, lng = coords
        intent = _detect_intent(query)
        tags_to_try = OVERPASS_TAGS[intent]

        logger.info(f"Searching OSM for '{intent}' near {region} ({lat}, {lng})")

        # Step 2: Try each OSM tag until we get results
        all_results = []
        for tag in tags_to_try:
            results = await _overpass_search(client, tag, lat, lng)
            if results:
                all_results.extend(results)
                logger.info(f"Found {len(results)} OSM results with tag: {tag}")
                if len(all_results) >= 5:
                    break

        # Step 3: If still nothing, widen radius to 30km
        if not all_results:
            logger.info(f"No results within 15km — widening to 30km")
            for tag in tags_to_try[:2]:
                results = await _overpass_search(client, tag, lat, lng, radius=30000)
                if results:
                    all_results.extend(results)
                    if len(all_results) >= 3:
                        break

        # Step 4: If still nothing, return honest message
        if not all_results:
            return {
                "found": False,
                "region": region,
                "message": (
                    f"No agro-input stores are currently mapped on OpenStreetMap near {region}. "
                    f"This is common in smaller Nigerian cities where stores aren't yet listed online. "
                    f"Try visiting the main market in {region} or asking local farmers."
                ),
                "stores": []
            }

        # Step 5: Parse, deduplicate, sort by distance
        stores = []
        seen_names = set()
        for element in all_results:
            store = _parse_osm_element(element, lat, lng)
            if store["name"] not in seen_names:
                seen_names.add(store["name"])
                stores.append(store)

        stores.sort(key=lambda x: x.get("distance_km", 999))
        stores = stores[:5]

        logger.info(f"Returning {len(stores)} stores near {region}")

        return {
            "found": True,
            "region": region,
            "query_type": intent,
            "stores": stores,
            "message": f"Found {len(stores)} store(s) near {region}"
        }