import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app.main import app
from app.models import Household
from app.ratelimit import login_by_ip, login_by_name
from app.auth import create_access_token, get_current_household

# In-memory SQLite with StaticPool so all connections share the same database
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

# Enable WAL-like behaviour: SQLite needs PRAGMA foreign_keys per connection
@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def reset_login_limits():
    login_by_ip.clear()
    login_by_name.clear()
    yield


@pytest.fixture(autouse=True)
def setup_database():
    """Create all tables before each test, drop after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session):
    """TestClient with get_db overridden to use test DB."""
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def household(db_session):
    """Pre-created household."""
    h = Household(name="AAAA-BBBB")
    db_session.add(h)
    db_session.commit()
    db_session.refresh(h)
    return h


@pytest.fixture
def auth_headers(household):
    token = create_access_token(data={"sub": str(household.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def authed_client(db_session, household):
    """Client where get_current_household is overridden to return the test household."""
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    def _override_auth():
        return household

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_household] = _override_auth
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def second_household(db_session):
    h = Household(name="CCCC-DDDD")
    db_session.add(h)
    db_session.commit()
    db_session.refresh(h)
    return h


@pytest.fixture
def second_auth_headers(second_household):
    token = create_access_token(data={"sub": str(second_household.id)})
    return {"Authorization": f"Bearer {token}"}
