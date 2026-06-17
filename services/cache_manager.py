import streamlit as st

class CacheManager:
    @staticmethod
    def clear_cache():
        """Clears all cached data in Streamlit."""
        st.cache_data.clear()
        
    @staticmethod
    def get_ttl() -> int:
        """Returns the default TTL for query caches (in seconds: 1 hour)."""
        return 3600
