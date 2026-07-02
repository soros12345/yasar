"""AlphaFold DB Provider."""
import re
from typing import Any, Optional
from core.interfaces.provider import StructureProvider
from core.models import StructurePrediction, StructureMetadata
from core.registry import ProviderRegistry
from core.exceptions import InvalidStructure
from loguru import logger
from .client import AlphaFoldDBClient
from .config import AlphaFoldDBConfig


@ProviderRegistry.register("alphafold_db")
class AlphaFoldDBProvider(StructureProvider):
    """AlphaFold Database Provider."""
    
    name = "alphafold_db"
    description = "AlphaFold Structure Database"
    version = "1.0.0"
    
    def __init__(self):
        self.config = AlphaFoldDBConfig()
        self.client = AlphaFoldDBClient(self.config)
    
    async def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """AlphaFold DB'de yapı ara."""
        try:
            async with self.client as client:
                results = await client.search(query, limit)
                return results
        except Exception as e:
            logger.error(f"Arama hatası: {e}")
            return []
    
    async def fetch(self, structure_id: str) -> StructurePrediction:
        """Yapıyı indir.
        
        Args:
            structure_id: AlphaFold ID (örn: AF-P12345-F1)
        """
        async with self.client as client:
            # PDB dosyasını indir
            pdb_data = await client.fetch_structure(structure_id)
            if not pdb_data:
                raise InvalidStructure(f"Yapı indirilemedi: {structure_id}")
            
            pdb_content = pdb_data.decode("utf-8")
            
            # PAE al
            pae_scores = await client.fetch_pae(structure_id)
            
            # PDB'den metaveri çıkar
            atoms, residues, chains = self._parse_pdb(pdb_content)
            plddt_scores = self._extract_plddt(pdb_content)
            
            metadata = StructureMetadata(
                protein_name=self._extract_protein_name(pdb_content),
                source=self.name,
                pdb_id=structure_id
            )
            
            return StructurePrediction(
                metadata=metadata,
                pdb_content=pdb_content,
                atoms_count=atoms,
                residues_count=residues,
                chains=chains,
                plddt_scores=plddt_scores,
                pae_scores=pae_scores
            )
    
    async def validate(self) -> bool:
        """Provider'ı doğrula."""
        try:
            async with self.client as client:
                # Basit bir arama ile test et
                results = await client.search("insulin", limit=1)
                return len(results) > 0
        except Exception as e:
            logger.error(f"Doğrulama hatası: {e}")
            return False
    
    def _parse_pdb(self, pdb_content: str) -> tuple[int, int, list[str]]:
        """PDB dosyasından atom, rezidü ve chain bilgisi çıkar."""
        atoms = 0
        residues = set()
        chains = set()
        
        for line in pdb_content.split("\n"):
            if line.startswith("ATOM") or line.startswith("HETATM"):
                atoms += 1
                chain = line[21].strip()
                res_num = line[22:26].strip()
                if chain:
                    chains.add(chain)
                if res_num:
                    residues.add(res_num)
        
        return atoms, len(residues), sorted(list(chains))
    
    def _extract_plddt(self, pdb_content: str) -> list[float]:
        """PDB'den pLDDT skorlarını çıkar (B-factor sütunundan)."""
        scores = []
        for line in pdb_content.split("\n"):
            if line.startswith("ATOM"):
                try:
                    b_factor = float(line[60:66].strip())
                    scores.append(b_factor)
                except (ValueError, IndexError):
                    pass
        return scores
    
    def _extract_protein_name(self, pdb_content: str) -> str:
        """PDB başlığından protein adını çıkar."""
        for line in pdb_content.split("\n"):
            if line.startswith("TITLE"):
                return line[10:].strip()
        return "Unknown Protein"
