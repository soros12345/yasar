# Authentication Modülü - JWT + OAuth2 Implementasyonu

## 📦 Kurulum

```bash
pip install fastapi[security] python-jose[cryptography] passlib[bcrypt] python-multipart
pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client
```

## 📁 Klasör Yapısı

```
auth/
├── __init__.py
├── models.py           # Pydantic schemas
├── password.py         # Password hashing
├── jwt_handler.py      # Token generation/validation
├── oauth_provider.py   # OAuth2 (Google, GitHub)
├── middleware.py       # FastAPI security
├── permissions.py      # RBAC decorators
└── dependencies.py     # FastAPI Depends
```

## 🔧 Implementasyon

### 1. password.py - Parola Hashleme

```python
from passlib.context import CryptContext
from typing import Optional

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class PasswordManager:
    """Parola hashleme ve doğrulama."""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Parolayı hashle."""
        return pwd_context.hash(password)
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Parolayı doğrula."""
        return pwd_context.verify(plain_password, hashed_password)
    
    @staticmethod
    def generate_password(length: int = 12) -> str:
        """Random parola oluştur."""
        import secrets
        import string
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*()"
        return ''.join(secrets.choice(alphabet) for i in range(length))
```

### 2. jwt_handler.py - Token Yönetimi

```python
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from core.config import Config

config = Config()

class JWTHandler:
    """JWT token işlemleri."""
    
    SECRET_KEY = config.SECRET_KEY if hasattr(config, 'SECRET_KEY') else "your-secret-key-change-in-production"
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 30
    REFRESH_TOKEN_EXPIRE_DAYS = 7
    
    @classmethod
    def create_access_token(
        cls,
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Access token oluştur."""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(
                minutes=cls.ACCESS_TOKEN_EXPIRE_MINUTES
            )
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(
            to_encode,
            cls.SECRET_KEY,
            algorithm=cls.ALGORITHM
        )
        return encoded_jwt
    
    @classmethod
    def create_refresh_token(cls, data: Dict[str, Any]) -> str:
        """Refresh token oluştur."""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=cls.REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode.update({"exp": expire, "type": "refresh"})
        encoded_jwt = jwt.encode(
            to_encode,
            cls.SECRET_KEY,
            algorithm=cls.ALGORITHM
        )
        return encoded_jwt
    
    @classmethod
    def verify_token(cls, token: str) -> Optional[Dict[str, Any]]:
        """Token'ı doğrula ve decode et."""
        try:
            payload = jwt.decode(
                token,
                cls.SECRET_KEY,
                algorithms=[cls.ALGORITHM]
            )
            return payload
        except JWTError:
            return None
    
    @classmethod
    def extract_user_id(cls, token: str) -> Optional[int]:
        """Token'dan user_id'yi çıkar."""
        payload = cls.verify_token(token)
        if payload:
            return payload.get("sub")
        return None
```

### 3. models.py - Pydantic Schemas

```python
from pydantic import BaseModel, EmailStr
from typing import Optional, List

class TokenRequest(BaseModel):
    """Token İsteği."""
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    """Token Yanıtı."""
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: int

class UserRegister(BaseModel):
    """Kullanıcı Kaydı."""
    email: EmailStr
    username: str
    password: str
    full_name: Optional[str] = None

class UserResponse(BaseModel):
    """Kullanıcı Yanıtı."""
    id: int
    email: str
    username: str
    full_name: Optional[str]
    role: str
    is_active: bool
    
    class Config:
        from_attributes = True

class UserUpdate(BaseModel):
    """Kullanıcı Güncellemesi."""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None

class Permission(BaseModel):
    """İzin Modeli."""
    resource: str  # structure, analysis, etc.
    action: str    # read, write, delete

class Role(BaseModel):
    """Rol Modeli."""
    name: str
    description: str
    permissions: List[Permission]
```

### 4. oauth_provider.py - Google OAuth2

```python
from google.oauth2 import id_token
from google.auth.transport import requests
from typing import Optional, Dict

class GoogleOAuth:
    """Google OAuth2 entegrasyonu."""
    
    GOOGLE_CLIENT_ID = "your-google-client-id.apps.googleusercontent.com"
    
    @classmethod
    def verify_token(cls, token: str) -> Optional[Dict[str, str]]:
        """Google token'ını doğrula."""
        try:
            idinfo = id_token.verify_oauth2_token(
                token,
                requests.Request(),
                cls.GOOGLE_CLIENT_ID
            )
            
            if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
                raise ValueError('Wrong issuer.')
            
            return {
                'email': idinfo.get('email'),
                'name': idinfo.get('name'),
                'picture': idinfo.get('picture'),
                'provider': 'google'
            }
        except Exception as e:
            return None

class GitHubOAuth:
    """GitHub OAuth2 entegrasyonu."""
    
    GITHUB_CLIENT_ID = "your-github-client-id"
    GITHUB_CLIENT_SECRET = "your-github-client-secret"
    
    @classmethod
    def get_user_info(cls, access_token: str) -> Optional[Dict[str, str]]:
        """GitHub'dan kullanıcı bilgisi al."""
        import requests
        
        headers = {
            'Authorization': f'token {access_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        try:
            response = requests.get(
                'https://api.github.com/user',
                headers=headers
            )
            response.raise_for_status()
            
            user_data = response.json()
            return {
                'email': user_data.get('email'),
                'username': user_data.get('login'),
                'name': user_data.get('name'),
                'picture': user_data.get('avatar_url'),
                'provider': 'github'
            }
        except Exception as e:
            return None
```

### 5. middleware.py - FastAPI Security

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthCredentials
from typing import Optional
from auth.jwt_handler import JWTHandler
from database.repositories import UserRepository
from sqlalchemy.orm import Session
from database.connection import get_db

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Mevcut kullanıcıyı al."""
    token = credentials.credentials
    
    # Token'ı doğrula
    payload = JWTHandler.verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
    
    # Veritabanından kullanıcıyı al
    user = UserRepository.get_by_id(db, user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    
    return user

async def get_current_admin_user(
    current_user = Depends(get_current_user)
):
    """Admin kullanıcı kontrolü."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user
```

### 6. permissions.py - RBAC

```python
from functools import wraps
from fastapi import HTTPException, status, Depends
from auth.middleware import get_current_user

def require_role(*allowed_roles: str):
    """Belirli rol gerektir."""
    async def role_checker(current_user = Depends(get_current_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action requires one of these roles: {', '.join(allowed_roles)}"
            )
        return current_user
    return role_checker

def require_permission(resource: str, action: str):
    """Belirli izin gerektir."""
    async def permission_checker(current_user = Depends(get_current_user)):
        # Kullanıcının izinlerini kontrol et
        # (Database'den alın veya cache'den)
        user_permissions = current_user.get_permissions()  # Custom method
        
        if not any(p.resource == resource and p.action == action for p in user_permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {resource}:{action}"
            )
        return current_user
    return permission_checker
```

### 7. API Routes

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from auth.models import TokenRequest, TokenResponse, UserRegister, UserResponse
from auth.jwt_handler import JWTHandler
from auth.password import PasswordManager
from auth.middleware import get_current_user, get_current_admin_user
from auth.permissions import require_role
from database.connection import get_db
from database.repositories import UserRepository
from database.models import User
from datetime import timedelta

router = APIRouter(prefix="/api/auth", tags=["authentication"])

@router.post("/register", response_model=UserResponse)
async def register(
    user_data: UserRegister,
    db: Session = Depends(get_db)
):
    """Yeni kullanıcı kaydı."""
    
    # Email zaten var mı?
    existing = UserRepository.get_by_email(db, user_data.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Parola hashle ve kullanıcı oluştur
    hashed_password = PasswordManager.hash_password(user_data.password)
    
    user = UserRepository.create(
        db,
        email=user_data.email,
        username=user_data.username,
        hashed_password=hashed_password,
        full_name=user_data.full_name,
        role="user"
    )
    
    return user

@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: TokenRequest,
    db: Session = Depends(get_db)
):
    """Kullanıcı girişi (JWT token döner)."""
    
    # Kullanıcıyı email ile bul
    user = UserRepository.get_by_email(db, credentials.email)
    if not user or not PasswordManager.verify_password(
        credentials.password,
        user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Token'ları oluştur
    access_token = JWTHandler.create_access_token(
        data={"sub": user.id, "email": user.email},
        expires_delta=timedelta(minutes=30)
    )
    refresh_token = JWTHandler.create_refresh_token(
        data={"sub": user.id}
    )
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": 1800  # 30 dakika
    }

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_token: str,
    db: Session = Depends(get_db)
):
    """Refresh token kullanarak yeni access token al."""
    
    payload = JWTHandler.verify_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    user_id = payload.get("sub")
    user = UserRepository.get_by_id(db, user_id)
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    new_access_token = JWTHandler.create_access_token(
        data={"sub": user.id, "email": user.email}
    )
    
    return {
        "access_token": new_access_token,
        "token_type": "bearer",
        "expires_in": 1800
    }

@router.post("/google")
async def google_login(
    token: str,
    db: Session = Depends(get_db)
):
    """Google OAuth2 girişi."""
    from auth.oauth_provider import GoogleOAuth
    
    user_info = GoogleOAuth.verify_token(token)
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google token"
        )
    
    # Kullanıcı var mı?
    user = UserRepository.get_by_email(db, user_info['email'])
    if not user:
        # Yeni kullanıcı oluştur
        user = UserRepository.create(
            db,
            email=user_info['email'],
            username=user_info['email'].split('@')[0],
            full_name=user_info['name'],
            hashed_password="oauth_no_password",
            role="user"
        )
    
    access_token = JWTHandler.create_access_token(
        data={"sub": user.id, "email": user.email}
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": 1800
    }

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user = Depends(get_current_user)
):
    """Mevcut kullanıcı bilgilerini al."""
    return current_user

@router.post("/logout")
async def logout(
    current_user = Depends(get_current_user)
):
    """Çıkış yap (token blacklist'e ekle)."""
    # Redis'e token'ı blacklist'e ekle
    # Token expire olana kadar geçersiz say
    return {"message": "Logged out successfully"}

@router.delete("/users/{user_id}", dependencies=[Depends(get_current_admin_user)])
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db)
):
    """Kullanıcı sil (Admin)."""
    user = UserRepository.delete(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return {"message": "User deleted successfully"}
```

## 🧪 Test Örneği

```python
import pytest
from auth.password import PasswordManager
from auth.jwt_handler import JWTHandler

def test_password_hashing():
    password = "SecurePassword123!"
    hashed = PasswordManager.hash_password(password)
    
    assert PasswordManager.verify_password(password, hashed)
    assert not PasswordManager.verify_password("WrongPassword", hashed)

def test_jwt_token_creation():
    data = {"sub": 1, "email": "test@example.com"}
    token = JWTHandler.create_access_token(data)
    
    payload = JWTHandler.verify_token(token)
    assert payload["sub"] == 1
    assert payload["email"] == "test@example.com"

def test_jwt_token_expiration():
    from datetime import timedelta
    data = {"sub": 1}
    token = JWTHandler.create_access_token(
        data,
        expires_delta=timedelta(seconds=-1)  # Already expired
    )
    
    payload = JWTHandler.verify_token(token)
    assert payload is None  # Expired token
```

---

**Sonraki Adım:** Task Queue (Celery) modülünü implement et!
