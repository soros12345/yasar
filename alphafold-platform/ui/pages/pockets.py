"""Cep tespiti sayfası."""
import streamlit as st
from core.registry import ProviderRegistry
from analyzers.pockets import PocketAnalyzer
import asyncio
from loguru import logger

def render(provider_name: str):
    """Cep tespiti sayfasını render et."""
    st.header("🕳️ Ligand Binding Cepleri")
    st.markdown("""Potansiyel ligand binding ceplerini tespit et.""")
    
    col1, col2 = st.columns(2)
    
    with col1:
        structure_id = st.text_input(
            "Yapı ID Girin",
            placeholder="örn: AF-P12345-F1",
            key="pocket_structure_id"
        )
    
    with col2:
        grid_size = st.slider("Grid Boyutu (Å)", 0.5, 5.0, 1.0, step=0.5, key="pocket_grid")
    
    analyze_btn = st.button("🔍 Cepleri Tespit Et", key="pocket_analyze")
    
    if analyze_btn and structure_id:
        with st.spinner("⏳ Yapı indiriliyor ve cepler tespit ediliyor..."):
            try:
                provider = ProviderRegistry.get(provider_name)
                prediction = asyncio.run(provider.fetch(structure_id))
                
                analyzer = PocketAnalyzer(grid_size=grid_size)
                result = analyzer.analyze(prediction)
                
                st.success("✅ Cep tespiti tamamlandı!")
                
                # Özet
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Tespit Edilen Cep Sayısı", result.result['pocket_count'])
                with col2:
                    st.metric("Grid Boyutu", f"{grid_size} Å")
                
                # Cep listesi
                if result.result['pockets']:
                    st.subheader("🎯 Tespit Edilen Ceplar")
                    for pocket in result.result['pockets'][:5]:  # İlk 5
                        with st.expander(f"Cep #{pocket['id']}"):
                            st.json(pocket)
                else:
                    st.info("Belirgin cep tespit edilemedi.")
                
                with st.expander("📊 Detaylı Sonuçlar"):
                    st.json(result.result)
            
            except Exception as e:
                st.error(f"❌ Hata: {str(e)}")
                logger.error(f"Cep tespiti hatası: {e}")
