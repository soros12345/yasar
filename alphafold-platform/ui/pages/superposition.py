"""Süperpozisyon analizi sayfası."""
import streamlit as st
from core.registry import ProviderRegistry
from analyzers.superposition import SuperpositionAnalyzer
import asyncio
from loguru import logger

def render(provider_name: str):
    """Süperpozisyon analizi sayfasını render et."""
    st.header("📐 Süperpozisyon Analizi")
    st.markdown("""İki yapıyı hizala ve RMSD/TM-score hesapla.""")
    
    col1, col2 = st.columns(2)
    
    with col1:
        structure_id1 = st.text_input(
            "Birinci Yapı ID",
            placeholder="örn: AF-P12345-F1",
            key="super_struct1"
        )
    
    with col2:
        structure_id2 = st.text_input(
            "İkinci Yapı ID",
            placeholder="örn: AF-P12345-F2",
            key="super_struct2"
        )
    
    analyze_btn = st.button("🔍 Hizala ve Analiz Et", key="super_analyze")
    
    if analyze_btn and structure_id1 and structure_id2:
        with st.spinner("⏳ Yapılar indiriliyor ve hizalanıyor..."):
            try:
                provider = ProviderRegistry.get(provider_name)
                
                pred1 = asyncio.run(provider.fetch(structure_id1))
                pred2 = asyncio.run(provider.fetch(structure_id2))
                
                analyzer = SuperpositionAnalyzer()
                result = analyzer.analyze(pred1, pred2)
                
                st.success("✅ Hizalama tamamlandı!")
                
                # Metrikler
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("RMSD (Å)", f"{result.result['rmsd']:.2f}")
                with col2:
                    st.metric("TM-score", f"{result.result['tm_score']:.3f}")
                with col3:
                    st.metric("Hizalı Atomlar", result.result['aligned_atoms'])
                
                st.info(f"📌 Benzerlik: {result.result['similarity']}")
                
                with st.expander("📊 Detaylı Sonuçlar"):
                    st.json(result.result)
            
            except Exception as e:
                st.error(f"❌ Hata: {str(e)}")
                logger.error(f"Süperpozisyon hatası: {e}")
