import re


PRIORITY_SEARCH_TERMS = {
    "Well-lit central areas": "central visitor areas",
    "Close to transport": "near public transport",
    "Quiet residential areas": "quiet neighbourhoods",
    "Family-friendly areas": "family friendly",
}

INTEREST_TERMS = {
    "Food and culture": {"food", "restaurant", "cafe", "market", "culture", "local", "art"},
    "Nature and beaches": {"nature", "beach", "coast", "garden", "park", "hike", "trail"},
    "History and museums": {"history", "museum", "heritage", "historic", "monument", "culture"},
    "Nightlife": {"nightlife", "bar", "music", "show", "club", "theatre"},
    "Markets and shopping": {"market", "shop", "craft", "store", "mall", "boutique"},
    "Quiet local spots": {"quiet", "local", "neighbourhood", "cafe", "garden", "park"},
}

STOP_WORDS = {"and", "the", "for", "in", "of", "to", "near", "with", "a", "an", "on"}


def _tokens(value):
    words = re.findall(r"[a-z]+", str(value).casefold())
    return {word[:-1] if len(word) > 4 and word.endswith("s") else word for word in words} - STOP_WORDS


def _ratio(matches, expected):
    return len(matches & expected) / len(matches) if matches else 0.0


def _review_confidence(rating, reviews):
    try:
        score = float(rating)
        digits = re.sub(r"\D", "", str(reviews or "0"))
        count = max(0, int(digits or 0))
    except (TypeError, ValueError):
        return 0.0
    prior_rating, prior_reviews = 4.0, 20
    adjusted_rating = (score * count + prior_rating * prior_reviews) / (count + prior_reviews)
    return min(1.0, max(0.0, adjusted_rating / 5))


def rank_places(places, query, profile):
    """Rank results by search fit, Mem0 profile fit, review confidence and listing completeness."""
    query_terms = _tokens(query)
    interests = profile.get("interests", [])
    preference_terms = set().union(*(INTEREST_TERMS.get(interest, _tokens(interest)) for interest in interests)) if interests else set()

    ranked = []
    for place in places:
        listing_text = " ".join(str(place.get(field) or "") for field in ("name", "category", "description", "address"))
        listing_terms = _tokens(listing_text)
        search_fit = _ratio(query_terms, listing_terms)
        profile_fit = _ratio(preference_terms, listing_terms)
        review_confidence = _review_confidence(place.get("rating"), place.get("reviews"))
        complete_fields = sum(bool(place.get(field)) for field in ("address", "category", "latitude", "longitude", "link"))
        data_completeness = complete_fields / 5
        score = round(100 * (
            0.40 * search_fit
            + 0.30 * profile_fit
            + 0.20 * review_confidence
            + 0.10 * data_completeness
        ))
        ranked.append({
            **place,
            "orbit_score": score,
            "score_breakdown": {
                "search_fit": round(100 * search_fit),
                "profile_fit": round(100 * profile_fit),
                "review_confidence": round(100 * review_confidence),
                "listing_completeness": round(100 * data_completeness),
            },
        })
    return sorted(ranked, key=lambda place: place["orbit_score"], reverse=True)
