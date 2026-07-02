"""Metaveri sayfası."""
import streamlit as st
from core.registry import ProviderRegistry
import asyncio
from loguru import logger

def render(provider_name: str):
    """Metaveri sayfasını render et."""
    st.header("📋 Yapı Metaveri")
    st.markdown("""Yapı hakkında detaylı bilgiler ve istatistikler.""")
    
    col1, col2 = st.columns(2)
    
    with col1:
        structure_id = st.text_input(
            "Yapı ID Girin",
            placeholder="örn: AF-P12345-F1",
            key="metadata_structure_id"
        )
    
    with col2:
        fetch_btn = st.button("🔍 Bilgileri Getir", key="metadata_fetch")
    
    if fetch_btn and structure_id:
        with st.spinner("⏳ Yapı indiriliyor..."):
            try:
                provider = ProviderRegistry.get(provider_name)
                prediction = asyncio.run(provider.fetch(structure_id))
                
                st.success("✅ Yapı yüklendi!")
                
                # Genel bilgiler
                st.subheader("📌 Genel Bilgiler")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Protein Adı", prediction.metadata.protein_name)
                with col2:
                    st.metric("Kaynak", prediction.metadata.source)
                with col3:
                    st.metric("PDB ID", prediction.metadata.pdb_id or "N/A")
                
                # Yapı istatistikleri
                st.subheader("🔬 Yapı İstatistikleri")
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Toplam Atom", prediction.atoms_count)
                with col2:
                    st.metric("Rezidü Sayısı", prediction.residues_count)
                with col3:
                    st.metric("Chain Sayısı", len(prediction.chains))
                with col4:
                    st.metric("Chain'ler", ", ".join(prediction.chains))
                
                # Kalite metrikleri
                st.subheader("📊 Kalite Metrikleri")
                col1, col2 = st.columns(2)
                
                with col1:
                    if prediction.plddt_scores:
                        import numpy as np
                        avg_plddt = np.mean(prediction.plddt_scores)
                        st.metric("Ortalama pLDDT", f"{avg_plddt:.1f}")
                
                with col2:
                    if prediction.pae_scores:
                        import numpy as np
                        avg_pae = np.mean(prediction.pae_scores)
                        st.metric("Ortalama PAE", f"{avg_pae:.1f}")
                
                # Metaveri detayları
                st.subheader("📝 Tam Metaveri")
                st.json(prediction.metadata.dict())
                
                # PDB dosya önizlemesi
                st.subheader("📄 PDB Dosya Önizlemesi")
                pdb_preview = prediction.pdb_content.split('\n')[:20]
                st.code('\n'.join(pdb_preview) + '\n...', language='text')
                
                # İndirme
                st.subheader("📥 İndirmeler")
                col1, col2 = st.columns(2)
                
                with col1:
                    st.download_button(
                        label="PDB Dosyasını İndir",
                        data=prediction.pdb_content,
                        file_name=f"{structure_id}.pdb",
                        mime="text/plain"
                    )
                
                with col2:
                    import json
                    json_data = json.dumps(prediction.metadata.dict(), indent=2)
                    st.download_button(
                        label="Metaveri (JSON) İndir",
                        data=json_data,
                        file_name=f"{structure_id}_metadata.json",
                        mime="application/json"
                    )
            
            except Exception as e:
                st.error(f"❌ Hata: {str(e)}")
                logger.error(f"Metaveri hatası: {e}")
