"""Provider arayüzü."""
from abc import ABC, abstractmethod
from typing import Optional, Any
from ..models import StructurePrediction


class StructureProvider(ABC):
    """Yapı sağlayıcı soyut sınıfı."""
    
    name: str
    description: str
    version: str = "1.0.0"
    
    @abstractmethod
    async def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Yapı ara.
        
        Args:
            query: Arama sorgusu (protein adı, PDB ID, UniProt ID)
            limit: Sonuç limiti
            
        Returns:
            Arama sonuçları
        """
        pass
    
    @abstractmethod
    async def fetch(self, structure_id: str) -> StructurePrediction:
        """Yapıyı indir.
        
        Args:
            structure_id: Yapı ID
            
        Returns:
            StructurePrediction nesnesi
        """
        pass
    
    @abstractmethod
    async def validate(self) -> bool:
        """Provider'ı doğrula (API erişimi vb).
        
        Returns:
            Geçerli ise True
        """
        pass
    
    async def get_metadata(self, structure_id: str) -> dict[str, Any]:
        """Yapı metaveri al.
        
        Args:
            structure_id: Yapı ID
            
        Returns:
            Metaveri sözlüğü
        """
        prediction = await self.fetch(structure_id)
        return prediction.metadata.dict()
