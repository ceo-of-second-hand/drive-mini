"""Accounts: register, log in, current user."""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from common.schemas import ErrorOut, RegisterIn, TokenOut, UserOut
from server.db import get_db
from server.models import User
from server.security import create_token, get_current_user, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED,
             responses={409: {"model": ErrorOut}})
def register(body: RegisterIn, db: Session = Depends(get_db)):
    user = User(username=body.username, display_name=body.display_name,
                password_hash=hash_password(body.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:  # username column is unique
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, f"Username '{body.username}' is already taken.")
    return user


@router.post("/login", response_model=TokenOut, responses={401: {"model": ErrorOut}})
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Standard OAuth2 password form (username + password), so /docs can log in too."""
    user = db.scalar(select(User).where(User.username == form.username.lower()))
    # Same message for "no such user" and "wrong password": don't reveal which usernames exist.
    if user is None or not verify_password(form.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong username or password.",
                            headers={"WWW-Authenticate": "Bearer"})
    return TokenOut(access_token=create_token(user.id))


@router.get("/me", response_model=UserOut, responses={401: {"model": ErrorOut}})
def me(user: User = Depends(get_current_user)):
    return user
