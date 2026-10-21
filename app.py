from html import escape
import re

import pydeck as pdk
import streamlit as st

from agent import explore_place, load_traveler_memory, save_traveler_memory
from config import secret
from tools import places_search


st.set_page_config(page_title="Orbit · South Africa travel safety", page_icon="◌", layout="wide")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');
:root { --ink:#202137; --muted:#73768b; --line:#e8e7f0; --violet:#6c5ce7; }
html, body, [class*="css"] { font-family:'DM Sans',sans-serif; color:var(--ink); }
.stApp { background:linear-gradient(180deg,#f8f7fc 0%,#fbfbfd 42%,#fff 100%); }
.block-container { max-width:1360px; padding-top:1.4rem; padding-bottom:4rem; }
.topline { display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--line); padding-bottom:1rem; margin-bottom:2rem; }
.brand { font:800 1.15rem Manrope,sans-serif; letter-spacing:-.06em; color:#25243b; }
.eyebrow { color:#7365d8; font-size:.72rem; letter-spacing:.14em; text-transform:uppercase; font-weight:700; }
.hero-title { color:#24243c; font:800 clamp(2.2rem,5vw,3.6rem)/1.04 Manrope,sans-serif; letter-spacing:-.065em; margin:.55rem 0 .75rem; }
.hero-copy { color:#71748a; font-size:1rem; max-width:760px; line-height:1.65; }
.section-title { color:#292941; font:700 1.3rem Manrope,sans-serif; letter-spacing:-.04em; margin:.3rem 0; }
.subtle { color:#77798d; font-size:.88rem; }
.card { border:1px solid #e8e7f0; border-radius:16px; background:white; padding:1rem 1.1rem; margin:.65rem 0; box-shadow:0 6px 20px #26234b08; }
.card-title { font:700 1.02rem Manrope,sans-serif; color:#292941; }
div[data-testid="stForm"] { border:0; padding:0; }
button[kind="primary"] { background:#6c5ce7; border-color:#6c5ce7; border-radius:10px; font-weight:600; min-height:2.7rem; }
</style>
""", unsafe_allow_html=True)


def init_state():
    defaults = {
        "onboarded": False,
        "traveler_memory": {},
        "traveler_id": "",
        "traveler_id_input": "",
        "profile_checked": False,
        "memories": [],
        "places": [],
        "has_searched": False,
        "destination": "",
        "place_query": "",
        "place_error": "",
        "place_insight": "",
        "insight_for": "",
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def personalized_terms(profile):
    interests = ", ".join(profile.get("interests", [])) or "local culture and attractions"
    return (
        f"{interests}; {profile.get('stay_budget', 'Mid-range')} budget; "
        f"{profile.get('safety_priority', 'well-lit central areas')}; "
        f"{profile.get('travel_pace', 'Balanced')} pace; "
        f"{profile.get('getting_around', 'Mostly walkable areas')}"
    )


def profile_from_memories(memories):
    profile = {
        "interests": [],
        "stay_budget": "Mid-range",
        "safety_priority": "Well-lit central areas",
        "travel_pace": "Balanced",
        "getting_around": "Mostly walkable areas",
    }
    fields = {
        "interests": "interests",
        "accommodation budget": "stay_budget",
        "safety priority": "safety_priority",
        "pace": "travel_pace",
        "getting around": "getting_around",
    }
    for item in memories:
        text = item.get("memory", "")
        for source, target in fields.items():
            match = re.search(rf"(?:^|;\s*){re.escape(source)}=([^;.]*)", text, flags=re.IGNORECASE)
            if not match:
                continue
            value = match.group(1).strip()
            if target == "interests":
                profile[target] = [interest.strip() for interest in value.split(",") if interest.strip()]
            elif target == "stay_budget" and value in ["Budget", "Mid-range", "Comfort", "Luxury"]:
                profile[target] = value
            elif target == "safety_priority" and value in ["Well-lit central areas", "Close to transport", "Quiet residential areas", "Family-friendly areas"]:
                profile[target] = value
            elif target == "travel_pace" and value in ["Relaxed", "Balanced", "See as much as possible"]:
                profile[target] = value
            elif target == "getting_around" and value in ["Mostly walkable areas", "Public transport nearby", "I plan to drive", "No preference"]:
                profile[target] = value
    if not profile["interests"]:
        profile["interests"] = ["Food and culture", "Nature and beaches"]
    return profile


def onboarding():
    st.markdown('<div class="eyebrow">Traveler profile</div><div class="hero-title">Explore South Africa<br>with safety in mind.</div>', unsafe_allow_html=True)
    st.markdown('<div class="hero-copy">Continue with your saved profile, or set your preferences once. Orbit remembers them in Mem0 and uses them to personalize place discovery.</div>', unsafe_allow_html=True)
    st.info("Place listings and ratings help you compare options; they do not guarantee that a place or route is safe. Check current local advice and confirm safety arrangements with the venue or operator.")
    st.text_input("Your name", key="traveler_id_input", placeholder="Add your name", help="Use the same name when you return to retrieve your saved preferences.")
    if not st.session_state.profile_checked:
        continue_col, new_col = st.columns(2)
        with continue_col:
            continue_clicked = st.button("Continue with saved profile", type="primary", width="stretch")
        with new_col:
            create_clicked = st.button("Create a profile", width="stretch")
        if continue_clicked:
            traveler_id = st.session_state.traveler_id_input.strip()
            if not traveler_id:
                st.error("Enter the same name you used when you saved your profile.")
                return
            try:
                memories = load_traveler_memory(traveler_id)
            except Exception as exc:
                st.error(f"Could not check Mem0 for a saved profile: {exc}")
                return
            if memories:
                st.session_state.traveler_id = traveler_id
                st.session_state.memories = memories
                st.session_state.traveler_memory = profile_from_memories(memories)
                st.session_state.onboarded = True
                st.rerun()
            st.session_state.profile_checked = True
            st.info("No saved profile was found for that name. Set your preferences below and save them once.")
        elif create_clicked:
            if not st.session_state.traveler_id_input.strip():
                st.error("Add your name before creating a profile.")
                return
            st.session_state.profile_checked = True
        else:
            return

    traveler_id = st.session_state.traveler_id_input.strip()
    saved = st.session_state.traveler_memory
    with st.form("traveler_onboarding"):
        left, right = st.columns(2)
        with left:
            interests = st.multiselect(
                "What would you like to explore?",
                ["Food and culture", "Nature and beaches", "History and museums", "Nightlife", "Markets and shopping", "Quiet local spots"],
                default=saved.get("interests", ["Food and culture", "Nature and beaches"]),
            )
            stay_budget = st.selectbox("Typical accommodation budget", ["Budget", "Mid-range", "Comfort", "Luxury"], index=["Budget", "Mid-range", "Comfort", "Luxury"].index(saved.get("stay_budget", "Mid-range")))
        with right:
            safety_options = ["Well-lit central areas", "Close to transport", "Quiet residential areas", "Family-friendly areas"]
            safety_priority = st.selectbox("What helps you feel safer?", safety_options, index=safety_options.index(saved.get("safety_priority", safety_options[0])))
            travel_pace = st.selectbox("Preferred pace", ["Relaxed", "Balanced", "See as much as possible"], index=["Relaxed", "Balanced", "See as much as possible"].index(saved.get("travel_pace", "Balanced")))
            getting_around = st.selectbox("Getting around", ["Mostly walkable areas", "Public transport nearby", "I plan to drive", "No preference"], index=["Mostly walkable areas", "Public transport nearby", "I plan to drive", "No preference"].index(saved.get("getting_around", "Mostly walkable areas")))
        submitted = st.form_submit_button("Save my preferences", type="primary", width="stretch")
    if submitted:
        if not traveler_id.strip():
            st.error("Add your name so Mem0 can associate your preferences with you.")
            return
        profile = {
            "interests": interests,
            "stay_budget": stay_budget,
            "safety_priority": safety_priority,
            "travel_pace": travel_pace,
            "getting_around": getting_around,
        }
        st.session_state.traveler_id = traveler_id.strip()
        try:
            save_traveler_memory(st.session_state.traveler_id, profile)
            st.session_state.memories = load_traveler_memory(st.session_state.traveler_id)
        except Exception as exc:
            st.error(f"Could not save or retrieve your preferences from Mem0: {exc}")
            return
        st.session_state.traveler_memory = profile
        st.session_state.onboarded = True
        st.rerun()


def normalized_price(value):
    if not value:
        return ""
    return "$" * min(str(value).count("$"), 4)


def filtered_places(places, minimum_rating, price_filter):
    visible = []
    for place in places:
        rating = place.get("rating")
        if minimum_rating:
            try:
                if rating is None or float(rating) < minimum_rating:
                    continue
            except (TypeError, ValueError):
                continue
        price = normalized_price(place.get("price"))
        if price_filter != "Any" and price != price_filter:
            continue
        visible.append(place)
    return visible


def render_map(places, selected_place):
    mapped = []
    for place in places:
        lat, lon = place.get("latitude"), place.get("longitude")
        if lat is None or lon is None:
            continue
        mapped.append({
            "name": place["name"], "lat": float(lat), "lon": float(lon),
            "fill": [255, 119, 82, 230] if place == selected_place else [108, 92, 231, 190],
        })
    if not mapped:
        st.info("No coordinates were returned for these results, so there are no map pins to show.")
        return
    center_lat = sum(item["lat"] for item in mapped) / len(mapped)
    center_lon = sum(item["lon"] for item in mapped) / len(mapped)
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=mapped,
        get_position="[lon, lat]",
        get_radius=180,
        get_fill_color="fill",
        pickable=True,
    )
    view = pdk.ViewState(latitude=center_lat, longitude=center_lon, zoom=11, pitch=0)
    st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view, map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json", tooltip={"text": "{name}\n{lat}, {lon}"}), width="stretch", height=480)


def dashboard():
    profile = st.session_state.traveler_memory
    st.markdown('<div class="eyebrow">Personalized place discovery · South Africa</div><div class="hero-title">Find a place that fits<br>how you travel.</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="hero-copy">Your saved preferences guide place discovery: {escape(personalized_terms(profile))}. Search any destination in South Africa, compare ratings and price indicators, and view place coordinates on the map.</div>', unsafe_allow_html=True)
    with st.expander("South Africa travel safety measures", expanded=True):
        st.markdown(
            "Plan transport with a reliable, pre-booked provider; avoid walking alone after dark or through isolated areas; "
            "keep valuables out of sight; and check current advice for your destination before setting out. Place ratings "
            "and listings are not a safety assessment, and no listing can guarantee a safe visit."
        )
        st.link_button("Read official South Africa safety advice ↗", "https://www.gov.uk/foreign-travel-advice/south-africa/safety-and-security")
    with st.expander("Your saved preferences"):
        st.write(personalized_terms(profile))
        if st.button("Update preferences"):
            st.session_state.onboarded = False
            st.rerun()

    st.markdown('<div class="section-title">Where would you like to explore?</div>', unsafe_allow_html=True)
    destination_col, category_col = st.columns([1.2, 1])
    with destination_col:
        destination = st.text_input("Destination", value=st.session_state.destination, placeholder="Add a destination in South Africa", help="For example: Cape Town, Johannesburg, Durban, or Stellenbosch.")
    with category_col:
        category = st.selectbox("What are you looking for?", ["Pick for me from my interests", "Things to do", "Food and local restaurants", "Nature and outdoors", "History and museums", "Markets and local shops", "Custom search"])
    custom_query = st.text_input("Describe what you want to find", placeholder="e.g. quiet coastal walks") if category == "Custom search" else ""
    if st.button("Find places", type="primary", width="stretch"):
        st.session_state.has_searched = True
        st.session_state.places = []
        st.session_state.place_error = ""
        if not destination.strip():
            st.session_state.place_error = "Enter a destination in South Africa first."
        elif not secret("SERPAPI_API_KEY"):
            st.session_state.place_error = "Add SERPAPI_API_KEY to .streamlit/secrets.toml to search places."
        else:
            if category == "Pick for me from my interests":
                request = ", ".join(profile.get("interests", [])) or "interesting local places"
            elif category == "Custom search":
                request = custom_query.strip()
            else:
                request = {
                    "Things to do": "tourist attractions and things to do",
                    "Food and local restaurants": "local restaurants and food markets",
                    "Nature and outdoors": "parks, gardens and nature reserves",
                    "History and museums": "museums and historic sites",
                    "Markets and local shops": "markets",
                }.get(category, category)
            if not request:
                st.session_state.place_error = "Describe what you want to find."
            else:
                try:
                    with st.spinner("Finding places that fit your preferences…"):
                        st.session_state.places = places_search(destination.strip(), request)
                    st.session_state.destination = destination.strip()
                    st.session_state.place_query = request
                    st.session_state.place_insight = ""
                    st.session_state.insight_for = ""
                except Exception as exc:
                    st.session_state.place_error = f"Place search could not complete: {exc}"
    if st.session_state.place_error:
        st.error(st.session_state.place_error)

    if not st.session_state.places:
        if st.session_state.has_searched and not st.session_state.place_error:
            st.info("No places came back for that search. Try a shorter phrase, a nearby area, or a broader category.")
        elif not st.session_state.has_searched:
            st.info("Choose a destination and what you want to find. Your saved interests are used by ‘Pick for me’ and by Claude when you explore a selected place.")
        return

    st.markdown(f'<div class="section-title">Places for {escape(st.session_state.destination)}</div><div class="subtle">Search: {escape(st.session_state.place_query)} · Results come from Google Maps via SerpApi.</div>', unsafe_allow_html=True)
    filter_a, filter_b = st.columns(2)
    with filter_a:
        min_rating_label = st.selectbox("Minimum rating", ["Any", "3.5+", "4.0+", "4.5+"], index=0)
    with filter_b:
        price_filter = st.selectbox("Price indicator", ["Any", "$", "$$", "$$$", "$$$$"], index=0)
    min_rating = float(min_rating_label[:-1]) if min_rating_label != "Any" else None
    visible = filtered_places(st.session_state.places, min_rating, price_filter)
    if not visible:
        st.info("No places match these filters. Try lowering the rating or clearing the price filter.")
        return

    map_col, detail_col = st.columns([1.15, 1], gap="large")
    with detail_col:
        place_options = [f"{place['name']} · {place.get('address') or place.get('category') or 'Place'}" for place in visible]
        selected_label = st.selectbox("Choose a place", place_options)
        selected = visible[place_options.index(selected_label)]
        st.markdown(f'<div class="card"><div class="card-title">{escape(selected["name"])}</div><div class="subtle">{escape(selected.get("category", ""))} · {escape(selected.get("address", ""))}</div><p>Rating: {escape(str(selected.get("rating") or "Not listed"))} · Reviews: {escape(str(selected.get("reviews") or "Not listed"))} · Price: {escape(str(selected.get("price") or "Not listed"))}</p><div class="subtle">Coordinates: {escape(str(selected.get("latitude") if selected.get("latitude") is not None else "Not listed"))}, {escape(str(selected.get("longitude") if selected.get("longitude") is not None else "Not listed"))}</div></div>', unsafe_allow_html=True)
        if str(selected.get("link") or "").startswith("https://"):
            st.link_button("Open place source ↗", selected["link"])
        st.caption("Ratings and search listings are comparison signals, not a safety guarantee. Verify current conditions and the venue's safety arrangements before you go.")
        if st.button("Explore more · what’s unique here?", type="primary"):
            try:
                with st.spinner("Finding ideas for this place and your interests…"):
                    st.session_state.place_insight = explore_place(
                        st.session_state.traveler_id,
                        st.session_state.destination,
                        selected,
                        st.session_state.memories,
                    )
                    st.session_state.insight_for = selected["name"]
            except Exception as exc:
                st.error(f"Could not generate place ideas: {exc}")
        if st.session_state.place_insight and st.session_state.insight_for == selected["name"]:
            st.markdown('<div class="section-title">What makes it worth exploring</div>', unsafe_allow_html=True)
            st.write(st.session_state.place_insight)
    with map_col:
        st.markdown('<div class="section-title">Places on the map</div><div class="subtle">Pins show the coordinates returned for matching places.</div>', unsafe_allow_html=True)
        render_map(visible, selected)


def main():
    init_state()
    st.markdown('<div class="topline"><div class="brand">◌ ORBIT <span style="color:#8175de">/ SOUTH AFRICA</span></div><div class="subtle">Safety-aware place discovery</div></div>', unsafe_allow_html=True)
    if st.session_state.onboarded:
        dashboard()
    else:
        onboarding()


main()
