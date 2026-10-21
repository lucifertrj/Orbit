from serpapi import Client

from config import secret


def serp_search(params):
    api_key = secret("SERPAPI_API_KEY")
    if not api_key:
        raise RuntimeError("Add SERPAPI_API_KEY to .streamlit/secrets.toml.")
    return Client(api_key=api_key).search(params)


def places_search(destination, query):
    """Search Google Maps for places and coordinates through SerpApi."""
    location = destination if "south africa" in destination.casefold() else f"{destination}, South Africa"
    payload = serp_search({
        "engine": "google_maps",
        "type": "search",
        "q": f"{query} in {location}",
        "hl": "en",
    })
    return normalize_places(payload)


def nearby_places_search(destination, place_name, query, latitude=None, longitude=None):
    """Search for preference-matched places near the selected result."""
    location = destination if "south africa" in destination.casefold() else f"{destination}, South Africa"
    params = {
        "engine": "google_maps",
        "type": "search",
        "q": f"{query} near {place_name}, {location}",
        "hl": "en",
    }
    if latitude is not None and longitude is not None:
        params["ll"] = f"@{latitude},{longitude},14z"
    return normalize_places(serp_search(params))


def normalize_places(payload):
    places = payload.get("local_results", []) or []
    normalized = []
    for place in places:
        coordinates = place.get("gps_coordinates") or {}
        normalized.append({
            "name": place.get("title") or "Place",
            "address": place.get("address") or "",
            "category": place.get("type") or "",
            "rating": place.get("rating"),
            "reviews": place.get("reviews"),
            "price": place.get("price") or "",
            "description": place.get("description") or "",
            "latitude": coordinates.get("latitude"),
            "longitude": coordinates.get("longitude"),
            "link": (place.get("links") or {}).get("website") or place.get("link") or "",
        })
    return normalized
