# Orbit

Orbit helps travelers explore places across South Africa with their safety priorities in mind. Travelers save interests and preferences to Mem0, then use the same name to continue with that saved profile on later visits without repeating onboarding. They can search any destination, filter Google Maps place results by rating and price indicator, and see returned coordinates on a map. After selecting a place, they can choose **Explore more** to ask Claude Haiku for ideas tailored to their saved preferences.

Listings and ratings are comparison signals, not guarantees of safety. Travelers should check current local guidance and confirm safety arrangements with venues or operators.

## Setup

Add provider credentials to `.streamlit/secrets.toml`:

```toml
SERPAPI_API_KEY = "your-serpapi-key"
ANTHROPIC_API_KEY = "your-anthropic-key"
MEM0_API_KEY = "your-mem0-platform-key"
```

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), install dependencies, and start Orbit:

```bash
uv sync
uv run streamlit run app.py
```

`app.py` owns the Streamlit flow and map. `tools.py` searches Google Maps through SerpApi for place listings and coordinates. `agent.py` stores and retrieves traveler preferences with Mem0. Only after the traveler selects a place and clicks **Explore more**, Claude (`claude-haiku-5-5`) uses Anthropic's tool-use loop to choose a preference-based nearby search, execute it through SerpApi, and explain the real results.

## License

Orbit is licensed under the [MIT License](LICENSE).
