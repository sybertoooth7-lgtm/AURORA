"""Registration and access-token endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.user import TokenRequest, TokenResponse, UserCreate, UserResponse
from app.security import (
    _DUMMY_PASSWORD_HASH,
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user: UserCreate, db: Session = Depends(get_db)):
    email = str(user.email).casefold()
    if db.query(User).filter(
        (User.email == email) | (User.username == user.username)
    ).first():
        raise HTTPException(status_code=409, detail="Email or username already registered")
    db_user = User(
        email=email,
        username=user.username,
        full_name=user.full_name,
        hashed_password=hash_password(user.password),
    )
    db.add(db_user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email or username already registered")
    db.refresh(db_user)
    return db_user


@router.post("/token", response_model=TokenResponse)
def token(credentials: TokenRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == credentials.username).first()
    password_hash = user.hashed_password if user else _DUMMY_PASSWORD_HASH
    if not verify_password(credentials.password, password_hash) or (
        user is not None and not user.is_active
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenResponse(access_token=create_access_token(user))


@router.get("/me", response_model=UserResponse)
def current_user_profile(
    current_user: User = Depends(get_current_user),
):
    """Return the authenticated user's profile from the database."""
    return current_user