"""
Authentication Service
Simple JWT-based authentication
"""
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.services.firestore_client import db
from app.models.auth import UserCreate, Token, TokenData

logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings (should be in env vars in production)
SECRET_KEY = "your-secret-key-change-in-production"  # TODO: Move to env var
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_user(user_data: UserCreate) -> dict:
    """Create a new user"""
    # Check if user exists
    user_ref = db.collection("users").where("email", "==", user_data.email).limit(1).stream()
    if list(user_ref):
        raise ValueError("User with this email already exists")
    
    # Hash password
    hashed_password = get_password_hash(user_data.password)
    
    # Create user document
    user_id = db.collection("users").document().id
    user_doc = {
        "user_id": user_id,
        "email": user_data.email,
        "password_hash": hashed_password,
        "full_name": user_data.full_name,
        "created_at": datetime.now().isoformat(),
    }
    
    db.collection("users").document(user_id).set(user_doc)
    logger.info(f"Created user: {user_id}")
    
    return {
        "user_id": user_id,
        "email": user_data.email,
        "full_name": user_data.full_name
    }


def authenticate_user(email: str, password: str) -> Optional[dict]:
    """Authenticate a user and return user data"""
    try:
        # Find user by email
        query = db.collection("users").where("email", "==", email).limit(1)
        docs = query.stream()
        
        user_doc = None
        for doc in docs:
            user_doc = doc
            break
        
        if not user_doc:
            return None
        
        data = user_doc.to_dict()
        hashed_password = data.get("password_hash")
        
        if not verify_password(password, hashed_password):
            return None
        
        return {
            "user_id": data.get("user_id"),
            "email": data.get("email"),
            "full_name": data.get("full_name")
        }
    except Exception as e:
        logger.error(f"Error authenticating user: {e}")
        return None


def get_user_by_id(user_id: str) -> Optional[dict]:
    """Get user by ID"""
    try:
        doc = db.collection("users").document(user_id).get()
        if not doc.exists:
            return None
        
        data = doc.to_dict()
        return {
            "user_id": data.get("user_id"),
            "email": data.get("email"),
            "full_name": data.get("full_name")
        }
    except Exception as e:
        logger.error(f"Error getting user: {e}")
        return None

