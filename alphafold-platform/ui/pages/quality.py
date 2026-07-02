"""Kalite analizi sayfası."""
import streamlit as st
from core.registry import ProviderRegistry
from analyzers.quality import QualityAnalyzer
import asyncio
from loguru import logger

def render(provider_name: str):
    """Kalite analizi sayfasını render et."""
    st.header("🎯 Yapı Kalitesi Analizi")
    st.markdown("""Yapının kalitesini pLDDT ve PAE skorlarına göre değerlendir.""")
    
    col1, col2 = st.columns(2)
    
    with col1:
        structure_id = st.text_input(
            "Yapı ID Girin",
            placeholder="örn: AF-P12345-F1",
            key="quality_structure_id"
        )
    
    with col2:
        analyze_btn = st.button("🔍 Analiz Et", key="quality_analyze")
    
    if analyze_btn and structure_id:
        with st.spinner("⏳ Yapı indiriliyor ve analiz ediliyor..."):
            try:
                provider = ProviderRegistry.get(provider_name)
                prediction = asyncio.run(provider.fetch(structure_id))
                
                analyzer = QualityAnalyzer()
                result = analyzer.analyze(prediction)
                
                # Sonuçları göster
                st.success("✅ Analiz tamamlandı!")
                
                # Metrikler
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Avg pLDDT", f"{result.metrics.avg_plddt:.1f}")
                with col2:
                    st.metric("Avg PAE", f"{result.metrics.avg_pae:.1f}" if result.metrics.avg_pae else "N/A")
                with col3:
                    st.metric("Kalite", result.metrics.quality_assessment)
                with col4:
                    st.metric("Toplam Atom", prediction.atoms_count)
                
                # Dağılım
                st.subheader("pLDDT Dağılımı")
                col1, col2, col3, col4 = st.columns(4)
                dist = result.metrics.plddt_distribution
                with col1:
                    st.metric("Çok Yüksek (90-100)", dist.get("very_high (90-100)", 0))
                with col2:
                    st.metric("Yüksek (70-89)", dist.get("high (70-89)", 0))
                with col3:
                    st.metric("Orta (50-69)", dist.get("medium (50-69)", 0))
                with col4:
                    st.metric("Düşük (0-49)", dist.get("low (0-49)", 0))
                
                # Detaylar
                with st.expander("📊 Detaylı Sonuçlar"):
                    st.json(result.result)
            
            except Exception as e:
                st.error(f"❌ Hata: {str(e)}")
                logger.error(f"Kalite analizi hatası: {e}")
