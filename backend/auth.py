from datetime import datetime, timedelta
from typing import Optional #Optional[str] vuol dire che puo essere str o None
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

# Configuration
SECRET_KEY = "ricordatiDiSpostareQuestaVariabileInUnFileEnv"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30

# si salva cosa usare per l'hashing 
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto") # ho dovuto usare pbkdf2_sha256 perchè bcrypt mi dava problemi

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/token") # dove il client ottiene il token

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """input: passoword inserita e password presa dal db, output: booleano se sono uguali"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash della password"""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """crea un token JWT"""
    to_encode = data.copy() # copia il dizionario passato 
    if expires_delta:
        expire = datetime.utcnow() + expires_delta # data corrente + quanto dura il token in giorni
    else: # se non specificato
        expire = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    
    to_encode.update({"exp": expire}) # aggiunge la data di scadenza al token
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> Optional[str]:
    """verifica se il token è valido, restituisce l'email"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            return None
        return email
    except JWTError:
        return None

async def get_current_user(token: str = Depends(oauth2_scheme)): # Depends: prima di tutto prendo oauth2_scheme (che è dove ho il token)
    """Dal token restituisce l'utente"""

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # verifica token, prende email
    email = verify_token(token)
    if email is None:
        raise credentials_exception
    
    from backend.users import get_user_by_email
    from backend.RequestModels import User
    
    # prende l'utente dal db
    user = get_user_by_email(email)
    if user is None:
        raise credentials_exception
    
    return User(
        email=user["email"],
        preferences=user.get("preferences")
    )
