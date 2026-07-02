from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="AlphaFold MVP API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ProteinLookupRequest(BaseModel):
    query: str


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "alphafold-mvp-api"}


@app.post("/api/proteins/search")
def search_proteins(payload: ProteinLookupRequest):
    return {
        "query": payload.query,
        "source": "mock",
        "results": [
            {
                "id": "AF-P12345-F1",
                "name": "Example protein structure",
                "organism": "Mock organism",
                "confidence": "placeholder"
            }
        ]
    }


@app.get("/api/structures/{structure_id}")
def get_structure(structure_id: str):
    return {
        "id": structure_id,
        "source": "mock",
        "viewer_ready": False,
        "message": "Faz 2 icinde gercek yapi dosyasi baglantisi eklenecek."
    }
