"""Varyant analizi sayfası."""
import streamlit as st
from core.registry import ProviderRegistry
from analyzers.variants import VariantAnalyzer
import asyncio
from loguru import logger

def render(provider_name: str):
    """Varyant analizi sayfasını render et."""
    st.header("🧪 Aminoasit Varyantları")
    st.markdown("""Aminoasit varyantlarının etkisini analiz et.""")
    
    col1, col2 = st.columns(2)
    
    with col1:
        structure_id = st.text_input(
            "Yapı ID Girin",
            placeholder="örn: AF-P12345-F1",
            key="variant_structure_id"
        )
    
    with col2:
        position = st.number_input(
            "Pozisyon",
            min_value=1,
            value=100,
            key="variant_position"
        )
    
    col1, col2 = st.columns(2)
    
    with col1:
        original_aa = st.selectbox(
            "Orijinal Aminoasit",
            ["A", "R", "N", "D", "C", "E", "Q", "G", "H", "I", "L", "K", "M", "F", "P", "S", "T", "W", "Y", "V"],
            key="variant_orig"
        )
    
    with col2:
        variant_aa = st.selectbox(
            "Varyant Aminoasit",
            ["A", "R", "N", "D", "C", "E", "Q", "G", "H", "I", "L", "K", "M", "F", "P", "S", "T", "W", "Y", "V"],
            key="variant_var"
        )
    
    analyze_btn = st.button("🔍 Varyant Etkisini Analiz Et", key="variant_analyze")
    
    if analyze_btn and structure_id:
        with st.spinner("⏳ Yapı indiriliyor ve varyant analizi yapılıyor..."):
            try:
                provider = ProviderRegistry.get(provider_name)
                prediction = asyncio.run(provider.fetch(structure_id))
                
                analyzer = VariantAnalyzer()
                result = analyzer.analyze(prediction, position, original_aa, variant_aa)
                
                st.success("✅ Analiz tamamlandı!")
                
                # Sonuç
                st.subheader(f"Varyant: {original_aa}{position}{variant_aa}")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("BLOSUM62 Skoru", f"{result.result['blosum_score']:.1f}")
                with col2:
                    st.metric("Fizikokimyasal", f"{result.result['physicochemical_score']:.1f}")
                with col3:
                    prediction_type = result.result['prediction']
                    if prediction_type == "benign":
                        st.success(f"✅ {prediction_type.upper()}")
                    elif prediction_type == "deleterious":
                        st.error(f"⚠️ {prediction_type.upper()}")
                    else:
                        st.info(f"❓ {prediction_type.upper()}")
                
                with st.expander("📊 Detaylı Sonuçlar"):
                    st.json(result.result)
            
            except Exception as e:
                st.error(f"❌ Hata: {str(e)}")
                logger.error(f"Varyant analizi hatası: {e}")
