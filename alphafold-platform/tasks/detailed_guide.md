# Task Queue Modülü - Celery + Redis Implementasyonu

## 📦 Kurulum

```bash
pip install celery redis flower

# Redis server
brew install redis  # macOS
apt-get install redis-server  # Ubuntu
redis-server  # Start server
```

## 📁 Klasör Yapısı

```
tasks/
├── __init__.py
├── celery_app.py       # Celery configuration
├── prediction_tasks.py  # Fetch & analyze
├── analysis_tasks.py    # Heavy computations
├── monitoring.py        # Task monitoring
└── utils.py            # Helper functions
```

## 🔧 Implementasyon

### 1. celery_app.py - Celery Yapılandırması

```python
from celery import Celery
from kombu import Exchange, Queue
from core.config import Config

config = Config()

# Celery app
app = Celery(
    'alphafold_platform',
    broker=f'redis://{config.REDIS_HOST}:{config.REDIS_PORT}/0',
    backend=f'redis://{config.REDIS_HOST}:{config.REDIS_PORT}/1'
)

# Configuration
app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 min hard limit
    task_soft_time_limit=25 * 60,  # 25 min soft limit
    broker_connection_retry_on_startup=True,
    
    # Queues
    task_queues=(
        Queue('default', Exchange('default'), routing_key='default'),
        Queue('predictions', Exchange('predictions'), routing_key='prediction.*'),
        Queue('analyses', Exchange('analyses'), routing_key='analysis.*'),
        Queue('priority', Exchange('priority'), routing_key='priority.*'),
    ),
    
    # Routing
    task_routes={
        'tasks.prediction_tasks.*': {'queue': 'predictions'},
        'tasks.analysis_tasks.*': {'queue': 'analyses'},
    },
    
    # Retry policy
    task_autoretry_for=(Exception,),
    task_max_retries=3,
    task_default_retry_delay=60,
)

# Auto-discover tasks
app.autodiscover_tasks(['tasks'])

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
```

### 2. prediction_tasks.py - Yapı İndirme

```python
from celery import shared_task, current_task
from datetime import datetime
from loguru import logger
import asyncio
import time

from core.registry import ProviderRegistry
from database.repositories import (
    ProteinStructureRepository,
    TaskRepository,
    AnalysisRepository
)
from database.connection import SessionLocal
from analyzers.quality import QualityAnalyzer
from analyzers.conservation import ConservationAnalyzer

@shared_task(bind=True, name='tasks.prediction_tasks.fetch_structure')
def fetch_structure(self, structure_id: str, provider: str = 'alphafold_db'):
    """Yapıyı indir (async task)."""
    db = SessionLocal()
    task_id = self.request.id
    
    try:
        # Task'ı veritabanına kaydet
        TaskRepository.create(
            db,
            id=task_id,
            task_type='fetch_structure',
            status='PROGRESS',
            structure_id=structure_id
        )
        db.commit()
        
        # Progres güncelle
        self.update_state(
            state='PROGRESS',
            meta={'current': 1, 'total': 3, 'status': '📥 İndiriliyor...'}
        )
        
        # Provider'dan çek
        logger.info(f"Fetching {structure_id} from {provider}")
        provider_obj = ProviderRegistry.get(provider)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        prediction = loop.run_until_complete(provider_obj.fetch(structure_id))
        loop.close()
        
        # Veritabanına kaydet
        self.update_state(
            state='PROGRESS',
            meta={'current': 2, 'total': 3, 'status': '💾 Kaydediliyor...'}
        )
        
        structure = ProteinStructureRepository.create(
            db,
            alphafold_id=structure_id,
            protein_name=prediction.metadata.protein_name,
            sequence='',  # TODO: Extract from PDB
            pdb_content=prediction.pdb_content,
            atoms_count=prediction.atoms_count,
            residues_count=prediction.residues_count,
            chains=prediction.chains,
            avg_plddt=float(sum(prediction.plddt_scores) / len(prediction.plddt_scores)) if prediction.plddt_scores else None,
            plddt_scores=prediction.plddt_scores,
            pae_scores=prediction.pae_scores
        )
        db.commit()
        
        # Task'ı tamamla
        TaskRepository.mark_completed(
            db,
            task_id,
            {'structure_id': structure.id, 'alphafold_id': structure_id}
        )
        db.commit()
        
        logger.info(f"Successfully fetched {structure_id}")
        return {'status': 'completed', 'structure_id': structure.id}
    
    except Exception as e:
        logger.error(f"Error fetching {structure_id}: {str(e)}")
        TaskRepository.update_progress(
            db,
            task_id,
            status='FAILURE',
            error=str(e)
        )
        db.commit()
        raise
    
    finally:
        db.close()

@shared_task(bind=True, name='tasks.prediction_tasks.analyze_and_fetch')
def analyze_and_fetch(self, structure_id: str, provider: str = 'alphafold_db'):
    """Yapıyı indir ve analiz et (comprehensive pipeline)."""
    db = SessionLocal()
    task_id = self.request.id
    
    try:
        TaskRepository.create(
            db,
            id=task_id,
            task_type='analyze_and_fetch',
            status='PROGRESS'
        )
        db.commit()
        
        # 1. İndir
        self.update_state(
            state='PROGRESS',
            meta={'progress': 10, 'status': '1/5: İndiriliyor...'}
        )
        
        provider_obj = ProviderRegistry.get(provider)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        prediction = loop.run_until_complete(provider_obj.fetch(structure_id))
        loop.close()
        
        # 2. Yapıyı kaydet
        self.update_state(
            state='PROGRESS',
            meta={'progress': 20, 'status': '2/5: Kaydediliyor...'}
        )
        
        structure = ProteinStructureRepository.create(
            db,
            alphafold_id=structure_id,
            protein_name=prediction.metadata.protein_name,
            pdb_content=prediction.pdb_content,
            atoms_count=prediction.atoms_count,
            residues_count=prediction.residues_count,
            chains=prediction.chains,
            avg_plddt=float(sum(prediction.plddt_scores) / len(prediction.plddt_scores)) if prediction.plddt_scores else None,
            plddt_scores=prediction.plddt_scores,
            pae_scores=prediction.pae_scores
        )
        db.commit()
        
        # 3. Kalite analizi
        self.update_state(
            state='PROGRESS',
            meta={'progress': 40, 'status': '3/5: Kalite analizi...'}
        )
        
        quality_analyzer = QualityAnalyzer()
        quality_result = quality_analyzer.analyze(prediction)
        
        AnalysisRepository.create(
            db,
            structure_id=structure.id,
            analysis_type='quality',
            status='completed',
            results=quality_result.result,
            metrics=quality_result.metrics.dict() if quality_result.metrics else None
        )
        db.commit()
        
        # 4. Korunum analizi
        self.update_state(
            state='PROGRESS',
            meta={'progress': 60, 'status': '4/5: Korunum analizi...'}
        )
        
        conservation_analyzer = ConservationAnalyzer()
        conservation_result = conservation_analyzer.analyze(prediction)
        
        AnalysisRepository.create(
            db,
            structure_id=structure.id,
            analysis_type='conservation',
            status='completed',
            results=conservation_result.result
        )
        db.commit()
        
        # 5. Tamamla
        self.update_state(
            state='PROGRESS',
            meta={'progress': 90, 'status': '5/5: Tamamlanıyor...'}
        )
        
        # Task'ı tamamla
        TaskRepository.mark_completed(
            db,
            task_id,
            {
                'structure_id': structure.id,
                'quality': quality_result.result,
                'conservation': conservation_result.result
            }
        )
        db.commit()
        
        logger.info(f"Completed full analysis for {structure_id}")
        return {'status': 'completed', 'structure_id': structure.id}
    
    except Exception as e:
        logger.error(f"Error in analyze_and_fetch: {str(e)}")
        TaskRepository.update_progress(
            db,
            task_id,
            status='FAILURE',
            error=str(e)
        )
        db.commit()
        raise
    
    finally:
        db.close()
```

### 3. analysis_tasks.py - Ağır Analizler

```python
from celery import shared_task
from loguru import logger
import asyncio

from database.repositories import AnalysisRepository
from database.connection import SessionLocal
from analyzers.superposition import SuperpositionAnalyzer
from analyzers.pockets import PocketAnalyzer
from analyzers.variants import VariantAnalyzer

@shared_task(bind=True, name='tasks.analysis_tasks.analyze_superposition')
def analyze_superposition(self, structure_id1: int, structure_id2: int):
    """Süperpozisyon analizi (CPU-intensive)."""
    db = SessionLocal()
    task_id = self.request.id
    
    try:
        self.update_state(state='PROGRESS', meta={'status': 'Yüklemeniyor...'})
        
        # Yapıları yükle
        from database.repositories import ProteinStructureRepository
        pred1 = ProteinStructureRepository.get_by_id(db, structure_id1)
        pred2 = ProteinStructureRepository.get_by_id(db, structure_id2)
        
        if not pred1 or not pred2:
            raise ValueError("One or both structures not found")
        
        self.update_state(state='PROGRESS', meta={'status': 'Analiz ediliyor...'})
        
        # Convert to StructurePrediction objects
        from core.models import StructurePrediction, StructureMetadata
        pred1_obj = StructurePrediction(
            metadata=StructureMetadata(
                protein_name=pred1.protein_name,
                source='database'
            ),
            pdb_content=pred1.pdb_content,
            atoms_count=pred1.atoms_count,
            residues_count=pred1.residues_count,
            chains=pred1.chains,
            plddt_scores=pred1.plddt_scores
        )
        
        pred2_obj = StructurePrediction(
            metadata=StructureMetadata(
                protein_name=pred2.protein_name,
                source='database'
            ),
            pdb_content=pred2.pdb_content,
            atoms_count=pred2.atoms_count,
            residues_count=pred2.residues_count,
            chains=pred2.chains,
            plddt_scores=pred2.plddt_scores
        )
        
        # Analiz et
        analyzer = SuperpositionAnalyzer()
        result = analyzer.analyze(pred1_obj, pred2_obj)
        
        # Kaydet
        analysis = AnalysisRepository.create(
            db,
            structure_id=structure_id1,
            analysis_type='superposition',
            status='completed',
            results=result.result
        )
        db.commit()
        
        return {'status': 'completed', 'analysis_id': analysis.id}
    
    except Exception as e:
        logger.error(f"Error in superposition analysis: {str(e)}")
        raise
    
    finally:
        db.close()

@shared_task(bind=True, name='tasks.analysis_tasks.detect_pockets')
def detect_pockets(self, structure_id: int, grid_size: float = 1.0):
    """Cep tespiti (heavy computation)."""
    db = SessionLocal()
    
    try:
        self.update_state(state='PROGRESS', meta={'status': 'Cepler tespit ediliyor...'})
        
        from database.repositories import ProteinStructureRepository
        from core.models import StructurePrediction, StructureMetadata
        
        structure = ProteinStructureRepository.get_by_id(db, structure_id)
        
        pred_obj = StructurePrediction(
            metadata=StructureMetadata(
                protein_name=structure.protein_name,
                source='database'
            ),
            pdb_content=structure.pdb_content,
            atoms_count=structure.atoms_count,
            residues_count=structure.residues_count,
            chains=structure.chains,
            plddt_scores=structure.plddt_scores
        )
        
        analyzer = PocketAnalyzer(grid_size=grid_size)
        result = analyzer.analyze(pred_obj)
        
        analysis = AnalysisRepository.create(
            db,
            structure_id=structure_id,
            analysis_type='pocket_detection',
            status='completed',
            results=result.result
        )
        db.commit()
        
        return {'status': 'completed', 'analysis_id': analysis.id}
    
    except Exception as e:
        logger.error(f"Error in pocket detection: {str(e)}")
        raise
    
    finally:
        db.close()
```

### 4. FastAPI Entegrasyonu

```python
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from database.connection import get_db
from tasks.prediction_tasks import fetch_structure, analyze_and_fetch
from tasks.monitoring import get_task_status

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

@router.post("/fetch-structure")
async def start_fetch(
    structure_id: str,
    provider: str = "alphafold_db",
    db: Session = Depends(get_db)
):
    """Yapı indirmeyi arka planda başlat."""
    task = fetch_structure.delay(structure_id, provider)
    return {"task_id": task.id, "status": "queued"}

@router.post("/analyze-structure")
async def start_analysis(
    structure_id: str,
    provider: str = "alphafold_db",
    db: Session = Depends(get_db)
):
    """Tam analiz pipeline'ını başlat."""
    task = analyze_and_fetch.delay(structure_id, provider)
    return {"task_id": task.id, "status": "queued"}

@router.get("/status/{task_id}")
async def task_status(task_id: str):
    """Task durumunu kontrol et."""
    status = get_task_status(task_id)
    return status
```

### 5. Worker'ı Başlatma

```bash
# Ana worker
celery -A tasks.celery_app worker --loglevel=info

# Spesifik queue'yu
celery -A tasks.celery_app worker -Q predictions,priority --loglevel=info

# Flower (monitoring)
celery -A tasks.celery_app flower --port=5555
# http://localhost:5555

# Docker'da
docker-compose -f docker-compose.yml run celery
```

### 6. docker-compose.yml Güncelleme

```yaml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    container_name: alphafold-redis
    ports:
      - "6379:6379"
    networks:
      - alphafold-net

  celery:
    build:
      context: .
      dockerfile: alphafold-platform/Dockerfile
    container_name: alphafold-celery
    command: celery -A tasks.celery_app worker --loglevel=info
    depends_on:
      - redis
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/1
    volumes:
      - ./alphafold-platform:/app
    networks:
      - alphafold-net

  flower:
    build:
      context: .
      dockerfile: alphafold-platform/Dockerfile
    container_name: alphafold-flower
    command: celery -A tasks.celery_app flower
    ports:
      - "5555:5555"
    depends_on:
      - redis
      - celery
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/1
    networks:
      - alphafold-net

networks:
  alphafold-net:
    driver: bridge
```

---

**Sonraki Adım:** WebSocket real-time updates modülünü implement et!
