"""Streamlit UI."""
import streamlit as st
from streamlit_option_menu import option_menu
import sys
from pathlib import Path

# Path ayarı
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import Config
from core.registry import ProviderRegistry
from ui.components.provider_selector import ProviderSelector
from ui.components.structure_viewer import StructureViewer
from ui.pages import quality, superposition, pockets, variants, conservation, metadata

# Sayfa konfigürasyonu
st.set_page_config(
    page_title="AlphaFold Platform",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .main {
        padding: 1rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    </style>
    """, unsafe_allow_html=True)

# Başlık
st.title("🧬 AlphaFold Platform")
st.markdown("Protein yapıları analiz et ve araştır")

# Sidebar - Provider seçimi
with st.sidebar:
    st.header("⚙️ Ayarlar")
    st.divider()
    
    # Provider seçimi
    config = Config()
    ProviderRegistry.auto_discover(config.PROVIDERS_DIR)
    available_providers = ProviderRegistry.list_available()
    
    selected_provider = st.selectbox(
        "Provider Seçin",
        options=available_providers,
        default="alphafold_db" if "alphafold_db" in available_providers else None
    )
    
    st.divider()
    st.info(f"✅ {selected_provider} seçildi")

# Ana menü
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🎯 Kalite",
    "📐 Süperpozisyon",
    "🕳️ Cepler",
    "🧪 Varyantlar",
    "🔗 Korunum",
    "📋 Metaveri"
])

with tab1:
    quality.render(selected_provider)

with tab2:
    superposition.render(selected_provider)

with tab3:
    pockets.render(selected_provider)

with tab4:
    variants.render(selected_provider)

with tab5:
    conservation.render(selected_provider)

with tab6:
    metadata.render(selected_provider)
