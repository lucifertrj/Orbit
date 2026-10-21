def secret(name):
    """Read provider credentials from Streamlit secrets only."""
    try:
        import streamlit as st
        return st.secrets.get(name, "")
    except Exception:
        return ""
