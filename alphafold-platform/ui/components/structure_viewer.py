"""Yapı görüntüleyici komponenti."""
import streamlit as st
from streamlit_3dmol import _3dmol

class StructureViewer:
    """3D yapı görüntüleyicisi."""
    
    @staticmethod
    def render(pdb_content: str, height: int = 400):
        """PDB içeriğini 3D olarak görüntüle."""
        if not pdb_content:
            st.error("❌ PDB içeriği boş!")
            return
        
        try:
            # 3Dmol viewer
            _3dmol(
                data=pdb_content,
                style={"cartoon": {}},
                height=height,
                width="100%"
            )
        except Exception as e:
            st.warning(f"3D görüntüleme hatası: {e}")
            st.text("PDB dosyası indirildiyse manual olarak görüntüle:")
            st.code(pdb_content[:500] + "...", language="text")
