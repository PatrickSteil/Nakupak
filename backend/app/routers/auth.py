from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..ratelimit import login_by_ip, login_by_name
from ..models import Household
from ..schemas import HouseholdCredentials, HouseholdResponse, HouseholdUpdate, Token
from ..auth import (
    create_access_token,
    get_current_household,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _find_by_name(db: Session, name: str) -> Household | None:
    return db.query(Household).filter(func.lower(Household.name) == name.lower()).first()


def _token_for(household: Household) -> dict:
    access_token = create_access_token(data={"sub": str(household.id)})
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/login", response_model=Token)
def login(data: HouseholdCredentials, request: Request, db: Session = Depends(get_db)):
    # Behind Caddy uvicorn restores the real client IP from X-Forwarded-For
    ip = request.client.host if request.client else "unknown"
    name_key = f"{ip}|{data.name.lower()}"

    wait = max(login_by_ip.retry_after(ip), login_by_name.retry_after(name_key))
    if wait:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed attempts. Try again later.",
            headers={"Retry-After": str(wait)},
        )

    household = _find_by_name(db, data.name)
    if not household or not verify_password(data.password, household.password_hash):
        login_by_ip.record_failure(ip)
        login_by_name.record_failure(name_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid name or password"
        )
    login_by_name.reset(name_key)
    return _token_for(household)


@router.get("/me", response_model=HouseholdResponse)
def get_me(current_household: Annotated[Household, Depends(get_current_household)]):
    return current_household


@router.patch("/me", response_model=HouseholdResponse)
def update_me(
    data: HouseholdUpdate,
    current_household: Annotated[Household, Depends(get_current_household)],
    db: Session = Depends(get_db),
):
    if data.new_password is not None:
        if not verify_password(data.current_password or "", current_household.password_hash):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Current password is incorrect")
        if not data.new_password:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must not be empty")
        current_household.password_hash = hash_password(data.new_password)

    if data.name is not None and data.name != current_household.name:
        existing = _find_by_name(db, data.name)
        if existing and existing.id != current_household.id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Household name already taken")
        current_household.name = data.name

    db.commit()
    db.refresh(current_household)
    return current_household
