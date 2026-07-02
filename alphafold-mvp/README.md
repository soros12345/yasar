# AlphaFold Protein 3D Viewer MVP

Bu klasor, mevcut alphafold-platform yapisini bozmadan eklenen modern MVP alanidir.

Amac:
- FastAPI backend
- Next.js frontend
- AlphaFold DB, UniProt ve PDB icin connector katmani
- Protein 3D viewer entegrasyonu
- Mock-first ve guvenli gelistirme

Calistirma hedefi:

cd alphafold-mvp
docker compose up --build

Portlar:
- Web: 3000
- API: 8000

Not: Bu MVP AlphaFold modelini lokal calistirmak yerine acik veri kaynaklarindan protein yapi verisi cekip gosterme ve analiz etme hedefindedir.
