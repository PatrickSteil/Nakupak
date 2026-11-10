"""Admin commands. Households can only be created here, not through the public API.

Docker:  docker exec -it nakupak python -m backend.app.cli create-household "Name"
Dev:     cd backend && uv run python -m app.cli create-household "Name"
"""
import argparse
import getpass
import sys

from sqlalchemy import func
from sqlalchemy.orm import Session

from .auth import hash_password
from .database import SessionLocal
from .models import Household
from .schemas import HouseholdCredentials


def create_household(db: Session, name: str, password: str) -> Household:
    creds = HouseholdCredentials(name=name, password=password)  # strips and validates the name
    if not creds.password:
        raise ValueError("Password must not be empty")
    if db.query(Household).filter(func.lower(Household.name) == creds.name.lower()).first():
        raise ValueError(f'Household "{creds.name}" already exists')
    household = Household(name=creds.name, password_hash=hash_password(creds.password))
    db.add(household)
    db.commit()
    db.refresh(household)
    return household


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="cli")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create-household", help="Create a household")
    create.add_argument("name")
    create.add_argument("--password", help="Prompted for if omitted (keeps it out of shell history)")
    args = parser.parse_args(argv)

    password = args.password or getpass.getpass("Password: ")
    with SessionLocal() as db:
        try:
            household = create_household(db, args.name, password)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
    print(f'Created household "{household.name}" (id {household.id})')
    return 0


if __name__ == "__main__":
    sys.exit(main())
