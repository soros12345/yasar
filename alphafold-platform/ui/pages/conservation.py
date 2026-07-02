"""Korunum analizi sayfası."""
import streamlit as st
from core.registry import ProviderRegistry
from analyzers.conservation import ConservationAnalyzer
import asyncio
from loguru import logger
import pandas as pd

def render(provider_name: str):
    """Korunum analizi sayfasını render et."""
    st.header("🔗 Aminoasit Korunumu")
    st.markdown("""Protein sekvansının korunum skorlarını hesapla.""")
    
    col1, col2 = st.columns(2)
    
    with col1:
        structure_id = st.text_input(
            "Yapı ID Girin",
            placeholder="örn: AF-P12345-F1",
            key="conservation_structure_id"
        )
    
    with col2:
        top_n = st.slider(
            "Gösterilecek Pozisyon Sayısı",
            5, 50, 20,
            key="conservation_top"
        )
    
    analyze_btn = st.button("🔍 Korunum Analizi Yap", key="conservation_analyze")
    
    if analyze_btn and structure_id:
        with st.spinner("⏳ Yapı indiriliyor ve korunum analizi yapılıyor..."):
            try:
                provider = ProviderRegistry.get(provider_name)
                prediction = asyncio.run(provider.fetch(structure_id))
                
                analyzer = ConservationAnalyzer()
                result = analyzer.analyze(prediction)
                
                st.success("✅ Analiz tamamlandı!")
                
                # Özet
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Sekans Uzunluğu", result.result['sequence_length'])
                with col2:
                    st.metric("Ortalama Korunum", f"{result.result['avg_conservation']:.3f}")
                with col3:
                    st.metric("Analiz Edilen Pozisyonlar", len(result.result['conservation_scores']))
                
                # Tablo
                if result.result['conservation_scores']:
                    st.subheader("🎯 En Korunan Pozisyonlar")
                    
                    df_data = result.result['conservation_scores'][:top_n]
                    df = pd.DataFrame(df_data)
                    st.dataframe(df, use_container_width=True)
                    
                    # İndirme
                    csv = df.to_csv(index=False)
                    st.download_button(
                        label="📥 CSV olarak indir",
                        data=csv,
                        file_name="conservation_scores.csv",
                        mime="text/csv"
                    )
                
                with st.expander("📊 Detaylı Sonuçlar"):
                    st.json(result.result)
            
            except Exception as e:
                st.error(f"❌ Hata: {str(e)}")
                logger.error(f"Korunum analizi hatası: {e}")
