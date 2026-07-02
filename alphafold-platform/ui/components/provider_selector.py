"""Provider seçici komponenti."""
import streamlit as st
from core.registry import ProviderRegistry
from loguru import logger

class ProviderSelector:
    """Provider seçici."""
    
    @staticmethod
    def render():
        """Render et."""
        st.header("Provider Seçimi")
        
        available = ProviderRegistry.list_available()
        
        if not available:
            st.error("❌ Hiçbir provider kullanılabilir değil!")
            return None
        
        provider_name = st.selectbox("Provider seçin:", available)
        
        try:
            provider = ProviderRegistry.get(provider_name)
            is_valid = st.session_state.get(f"provider_valid_{provider_name}")
            
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"📌 **{provider.name}**")
                st.caption(provider.description)
            with col2:
                if is_valid:
                    st.success("✅ Aktif")
                else:
                    st.warning("⚠️ İnaktif")
            
            return provider_name
        except Exception as e:
            st.error(f"Provider hatası: {e}")
            return None
