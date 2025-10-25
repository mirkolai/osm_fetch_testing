# questo file gestisce le operazioni relative agli utenti nel db

from typing import Optional 
from pymongo.errors import DuplicateKeyError
from backend.db import db
from backend.auth import get_password_hash, verify_password
from backend.RequestModels import User, UserCreate

def create_user(user: UserCreate) -> Optional[User]:
    """Create a new user in the database."""
    try:
        # Cerca l'user nel db
        existing_user = get_user_by_email(user.email)
        # se trova qualcosa, esiste gia l'user e ferma tutto
        if existing_user:
            return None
        
        # Hash della password
        hashed_password = get_password_hash(user.password)
        
        # documento utente, da mettere nel db
        user_doc = {
            "email": user.email,  
            "hashed_password": hashed_password
        }
        
        # Inserisce il nuovo utente nella tabella "users" di MongoDB
        result = db["users"].insert_one(user_doc)
        
        # Se l'inserimento è riuscito (ha un ID), restituisce l'oggetto User
        if result.inserted_id:
            return User(email=user.email)
        # Se l'inserimento non è riuscito, restituisce None
        return None
        
    except DuplicateKeyError: # email già esistente
        return None
    except Exception as e: # qualunque altro errore
        print(f"Error creating user: {e}")
        return None

def get_user_by_email(email: str) -> Optional[dict]:
    """Get user by email from the database."""
    try:
        # Cerca utente
        user = db["users"].find_one({"email": email})
        return user # None se non lo trova

    except Exception as e:
        print(f"Error getting user by email: {e}")
        return None

def authenticate_user(email: str, password: str) -> Optional[User]:
    """Authenticate a user with email and password."""
    try:
        # Recupera l'utente 
        user = get_user_by_email(email)

        if not user: #se non lo trova
            return None
        
        # Verifica la password fornita
        if verify_password(password, user["hashed_password"]):
            # Se corretta, restituisce l'oggetto User con preferences se presenti
            return User(
                email=user["email"], 
                preferences=user.get("preferences")
            )
        # altrimenti None
        return None
        
    except Exception as e:
        print(f"Error authenticating user: {e}")
        return None

def update_user_preferences(email: str, preferences: dict) -> bool:
    """aggiorna le preferenze dell'utente nel db"""
    try:
        result = db["users"].update_one( #nella tabella users, aggiorna le preferenze dell'utente con la email passata
            {"email": email},
            {"$set": {"preferences": preferences}}
        )
        return result.modified_count > 0
    except Exception as e:
        print(f"Error updating user preferences: {e}")
        return False

def get_user_preferences(email: str) -> Optional[dict]:
    """prende le preferenze dell'utente dal db"""
    try:
        user = get_user_by_email(email)
        if user:
            return user.get("preferences")
        return None
    except Exception as e:
        print(f"Error getting user preferences: {e}")
        return None
