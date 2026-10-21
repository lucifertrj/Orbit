import json

from anthropic import Anthropic
from mem0 import MemoryClient

from config import secret
from tools import nearby_places_search

MODEL = "claude-haiku-5-5"

PLACE_SEARCH_TOOL = {
    "name": "search_nearby_places",
    "description": (
        "Search Google Maps for real places and activities near the traveler's selected place. "
        "Choose a focused query from their interests and travel preferences. Use this before making recommendations."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "A focused Google Maps search such as local food experiences, coastal nature walks, or history sites.",
            }
        },
        "required": ["query"],
    },
}


def _memory_client():
    api_key = secret("MEM0_API_KEY")
    if not api_key:
        raise RuntimeError("Add MEM0_API_KEY to .streamlit/secrets.toml.")
    return MemoryClient(api_key=api_key)


def load_traveler_memory(user_id: str):
    """Retrieve saved travel preferences from Mem0."""
    response = _memory_client().search(
        "Travel interests, accommodation budget, safety priorities, preferred pace and transport",
        filters={"user_id": user_id},
    )
    return response.get("results", [])


def save_traveler_memory(user_id: str, profile: dict):
    """Persist onboarding preferences in Mem0."""
    profile_text = (
        f"Travel preferences: interests={', '.join(profile['interests'])}; "
        f"accommodation budget={profile['stay_budget']}; safety priority={profile['safety_priority']}; "
        f"pace={profile['travel_pace']}; getting around={profile['getting_around']}."
    )
    _memory_client().add(profile_text, user_id=user_id)


def explore_place(user_id: str, destination: str, place: dict, memories: list):
    """Use Claude tool calling to find real nearby options, then explain what fits."""
    api_key = secret("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("Add ANTHROPIC_API_KEY to .streamlit/secrets.toml.")
    preference_context = "\n".join(item.get("memory", "") for item in memories)
    prompt = (
        "The traveler selected a place and asked what is unique or worthwhile to explore nearby. First use the "
        "search_nearby_places tool with a focused query derived from their saved preferences. Choose a query that "
        "returns actual, named places, not a generic category. Use the returned listings as evidence; do not invent "
        "places, events, facilities, opening hours, or safety claims. Give a short, useful explanation of the best "
        "matches and why they suit this traveler. These search listings are not a safety assessment.\n\n"
        f"Destination: {destination}\nSelected place: {json.dumps(place, ensure_ascii=False)}\n"
        f"Mem0 preferences for traveler {user_id}: {preference_context or 'No saved preferences'}"
    )
    client = Anthropic(api_key=api_key)
    messages = [{"role": "user", "content": prompt}]
    search_count = 0

    for _ in range(3):
        response = client.messages.create(
            model=MODEL,
            max_tokens=900,
            tools=[PLACE_SEARCH_TOOL],
            tool_choice={"type": "any"} if search_count == 0 else {"type": "auto"},
            messages=messages,
        )
        tool_calls = [block for block in response.content if block.type == "tool_use"]
        if not tool_calls:
            return "\n".join(block.text for block in response.content if block.type == "text")

        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for call in tool_calls:
            if call.name != "search_nearby_places" or search_count >= 2:
                result = {"error": "Search limit reached for this Explore more request."}
                is_error = True
            else:
                search_count += 1
                try:
                    matches = nearby_places_search(
                        destination=destination,
                        place_name=place.get("name", "selected place"),
                        query=call.input["query"],
                        latitude=place.get("latitude"),
                        longitude=place.get("longitude"),
                    )
                    result = {"places": matches[:8]}
                    is_error = False
                except Exception as exc:
                    result = {"error": str(exc)}
                    is_error = True
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": call.id,
                "content": json.dumps(result, ensure_ascii=False),
                "is_error": is_error,
            })
        messages.append({"role": "user", "content": tool_results})

    return "I found nearby options, but couldn’t finish summarizing them. Please try Explore more again."
