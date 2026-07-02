# Database Modülü - Başlangıç Implementasyonu

## 📦 Kurulum

```bash
pip install sqlalchemy psycopg2-binary alembic python-dotenv
```

## 📁 Klasör Yapısı

```
database/
├── __init__.py
├── connection.py       # Session & Engine
├── models.py           # ORM Models
├── repositories.py     # CRUD operations
├── migrations/         # Alembic
└── seeds.py           # Örnek veri
```

## 🔧 Implementasyon

### 1. connection.py

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
from core.config import Config

config = Config()

# Veritabanı bağlantı stringi
DATABASE_URL = f"postgresql://user:password@localhost/alphafold"

# Engine oluştur
engine = create_engine(
    DATABASE_URL,
    echo=config.DEBUG,
    pool_size=20,
    max_overflow=40,
    pool_recycle=3600
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()

# Dependency injection
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### 2. models.py

```python
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from database.connection import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    full_name = Column(String, nullable=True)
    role = Column(String, default="user")  # admin, user, researcher
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relations
    structures = relationship("ProteinStructure", back_populates="owner")
    analyses = relationship("Analysis", back_populates="user")
    api_keys = relationship("APIKey", back_populates="user")

class ProteinStructure(Base):
    __tablename__ = "protein_structures"
    
    id = Column(Integer, primary_key=True, index=True)
    alphafold_id = Column(String, unique=True, index=True)
    protein_name = Column(String, index=True)
    organism = Column(String, nullable=True)
    sequence = Column(Text)
    pdb_content = Column(Text)
    pdb_file_path = Column(String, nullable=True)  # S3 path
    
    # Quality metrics
    avg_plddt = Column(Float, nullable=True)
    avg_pae = Column(Float, nullable=True)
    plddt_scores = Column(JSON)  # Full array
    pae_scores = Column(JSON)
    quality_assessment = Column(String)  # excellent, good, fair, poor
    
    # Structure info
    atoms_count = Column(Integer)
    residues_count = Column(Integer)
    chains = Column(JSON)  # ["A", "B", "C"]
    
    # Metadata
    resolution = Column(Float, nullable=True)
    pdb_id = Column(String, nullable=True)
    organism_taxid = Column(Integer, nullable=True)
    
    # Relationships
    owner_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="structures")
    
    analyses = relationship("Analysis", back_populates="structure", cascade="all, delete-orphan")
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_analyzed = Column(DateTime, nullable=True)

class Analysis(Base):
    __tablename__ = "analyses"
    
    id = Column(Integer, primary_key=True, index=True)
    structure_id = Column(Integer, ForeignKey("protein_structures.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    
    analysis_type = Column(String, index=True)  # quality, conservation, superposition, etc.
    status = Column(String, default="pending")  # pending, processing, completed, failed
    
    # Results
    results = Column(JSON)
    metrics = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Parameters
    parameters = Column(JSON)  # Input parameters
    
    # Performance
    execution_time_ms = Column(Integer, nullable=True)  # Execution duration
    
    # Relationships
    structure = relationship("ProteinStructure", back_populates="analyses")
    user = relationship("User", back_populates="analyses")
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

class Task(Base):
    __tablename__ = "tasks"
    
    id = Column(String, primary_key=True, index=True)  # Celery task ID
    user_id = Column(Integer, ForeignKey("users.id"))
    structure_id = Column(Integer, ForeignKey("protein_structures.id"), nullable=True)
    
    task_type = Column(String)  # fetch, analyze_quality, docking, etc.
    status = Column(String)  # PENDING, PROGRESS, SUCCESS, FAILURE
    progress = Column(Float, default=0.0)  # 0-100%
    
    result = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

class APIKey(Base):
    __tablename__ = "api_keys"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    key = Column(String, unique=True, index=True)
    name = Column(String)
    is_active = Column(Boolean, default=True)
    last_used = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    
    user = relationship("User", back_populates="api_keys")

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String)  # create, update, delete, analyze, etc.
    resource_type = Column(String)  # structure, analysis, etc.
    resource_id = Column(Integer)
    old_values = Column(JSON, nullable=True)
    new_values = Column(JSON, nullable=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
```

### 3. repositories.py

```python
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from database.models import (
    User, ProteinStructure, Analysis, Task, APIKey, AuditLog
)

class ProteinStructureRepository:
    """Protein structures için CRUD operations."""
    
    @staticmethod
    def create(db: Session, **kwargs) -> ProteinStructure:
        structure = ProteinStructure(**kwargs)
        db.add(structure)
        db.commit()
        db.refresh(structure)
        return structure
    
    @staticmethod
    def get_by_id(db: Session, structure_id: int):
        return db.query(ProteinStructure).filter(
            ProteinStructure.id == structure_id
        ).first()
    
    @staticmethod
    def get_by_alphafold_id(db: Session, alphafold_id: str):
        return db.query(ProteinStructure).filter(
            ProteinStructure.alphafold_id == alphafold_id
        ).first()
    
    @staticmethod
    def list_by_user(db: Session, user_id: int, skip: int = 0, limit: int = 100):
        return db.query(ProteinStructure).filter(
            ProteinStructure.owner_id == user_id
        ).offset(skip).limit(limit).all()
    
    @staticmethod
    def update(db: Session, structure_id: int, **kwargs):
        structure = db.query(ProteinStructure).filter(
            ProteinStructure.id == structure_id
        ).first()
        if structure:
            for key, value in kwargs.items():
                setattr(structure, key, value)
            structure.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(structure)
        return structure
    
    @staticmethod
    def delete(db: Session, structure_id: int):
        structure = db.query(ProteinStructure).filter(
            ProteinStructure.id == structure_id
        ).first()
        if structure:
            db.delete(structure)
            db.commit()
        return structure

class AnalysisRepository:
    """Analysis results için CRUD operations."""
    
    @staticmethod
    def create(db: Session, **kwargs) -> Analysis:
        analysis = Analysis(**kwargs)
        db.add(analysis)
        db.commit()
        db.refresh(analysis)
        return analysis
    
    @staticmethod
    def get_by_id(db: Session, analysis_id: int):
        return db.query(Analysis).filter(
            Analysis.id == analysis_id
        ).first()
    
    @staticmethod
    def list_by_structure(db: Session, structure_id: int):
        return db.query(Analysis).filter(
            Analysis.structure_id == structure_id
        ).order_by(Analysis.created_at.desc()).all()
    
    @staticmethod
    def list_by_type(db: Session, analysis_type: str, skip: int = 0, limit: int = 100):
        return db.query(Analysis).filter(
            Analysis.analysis_type == analysis_type
        ).offset(skip).limit(limit).all()
    
    @staticmethod
    def update_status(db: Session, analysis_id: int, status: str, **kwargs):
        analysis = db.query(Analysis).filter(
            Analysis.id == analysis_id
        ).first()
        if analysis:
            analysis.status = status
            if status == "completed":
                analysis.completed_at = datetime.utcnow()
            for key, value in kwargs.items():
                setattr(analysis, key, value)
            db.commit()
            db.refresh(analysis)
        return analysis

class TaskRepository:
    """Async tasks için operations."""
    
    @staticmethod
    def create(db: Session, **kwargs) -> Task:
        task = Task(**kwargs)
        db.add(task)
        db.commit()
        db.refresh(task)
        return task
    
    @staticmethod
    def get_by_id(db: Session, task_id: str):
        return db.query(Task).filter(Task.id == task_id).first()
    
    @staticmethod
    def update_progress(db: Session, task_id: str, progress: float, **kwargs):
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.progress = progress
            task.updated_at = datetime.utcnow()
            for key, value in kwargs.items():
                setattr(task, key, value)
            db.commit()
            db.refresh(task)
        return task
    
    @staticmethod
    def mark_completed(db: Session, task_id: str, result: dict):
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = "SUCCESS"
            task.result = result
            task.completed_at = datetime.utcnow()
            task.progress = 100.0
            db.commit()
            db.refresh(task)
        return task

class AuditLogRepository:
    """Audit logging."""
    
    @staticmethod
    def create(db: Session, **kwargs):
        log = AuditLog(**kwargs)
        db.add(log)
        db.commit()
        return log
    
    @staticmethod
    def list_recent(db: Session, limit: int = 100):
        return db.query(AuditLog).order_by(
            AuditLog.created_at.desc()
        ).limit(limit).all()
```

## 🔄 Alembic Migrations

```bash
# Alembic initialize
alembic init -t async database/migrations

# Migration oluştur
alembic revision --autogenerate -m "Initial schema"

# Migration uygula
alembic upgrade head
```

## 📝 .env Configuration

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/alphafold
DATABASE_ECHO=false
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=40
```

## 🧪 Test Örneği

```python
def test_create_structure():
    from database.connection import SessionLocal
    from database.models import ProteinStructure
    from database.repositories import ProteinStructureRepository
    
    db = SessionLocal()
    
    # Oluştur
    structure = ProteinStructureRepository.create(
        db,
        alphafold_id="AF-P12345-F1",
        protein_name="Test Protein",
        sequence="MKTAYIAKQ",
        pdb_content="ATOM  1",
        atoms_count=100,
        residues_count=10,
        chains=["A"]
    )
    
    assert structure.id is not None
    assert structure.alphafold_id == "AF-P12345-F1"
    
    # Al
    fetched = ProteinStructureRepository.get_by_alphafold_id(
        db, "AF-P12345-F1"
    )
    assert fetched.id == structure.id
    
    db.close()
```

## 🚀 FastAPI Entegrasyonu

```python
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from database.connection import get_db
from database.repositories import ProteinStructureRepository

app = FastAPI()

@app.post("/api/structures")
async def create_structure(
    data: dict,
    db: Session = Depends(get_db)
):
    structure = ProteinStructureRepository.create(db, **data)
    return structure

@app.get("/api/structures/{structure_id}")
async def get_structure(
    structure_id: int,
    db: Session = Depends(get_db)
):
    return ProteinStructureRepository.get_by_id(db, structure_id)
```

## 📊 Örnek Sorgular

```python
# En yüksek kaliteli yapılar
top_structures = db.query(ProteinStructure).order_by(
    ProteinStructure.avg_plddt.desc()
).limit(10).all()

# Son 7 günde analiz edilen yapılar
from datetime import datetime, timedelta
week_ago = datetime.utcnow() - timedelta(days=7)
recent = db.query(ProteinStructure).filter(
    ProteinStructure.last_analyzed >= week_ago
).all()

# En çok analiz edilen yapılar
from sqlalchemy import func
most_analyzed = db.query(
    ProteinStructure,
    func.count(Analysis.id).label('analysis_count')
).join(Analysis).group_by(ProteinStructure.id).order_by(
    func.count(Analysis.id).desc()
).limit(10).all()
```

---

**Sonraki adım:** FastAPI routes'ta Dependency Injection kullanarak database'i entegre et!
