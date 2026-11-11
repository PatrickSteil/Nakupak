from app.cli import create_household
from app.ratelimit import FailureLimiter


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_limiter_blocks_after_max_failures_and_expires():
    clock = FakeClock()
    limiter = FailureLimiter(max_failures=3, window_seconds=60, clock=clock)
    for _ in range(2):
        limiter.record_failure("k")
    assert limiter.retry_after("k") == 0
    limiter.record_failure("k")
    assert 0 < limiter.retry_after("k") <= 61
    clock.now += 61
    assert limiter.retry_after("k") == 0


def test_limiter_keys_are_independent_and_reset_works():
    limiter = FailureLimiter(max_failures=1, window_seconds=60, clock=FakeClock())
    limiter.record_failure("a")
    assert limiter.retry_after("a") > 0
    assert limiter.retry_after("b") == 0
    limiter.reset("a")
    assert limiter.retry_after("a") == 0


def _login(client, name, password):
    return client.post("/api/auth/login", json={"name": name, "password": password})


def test_login_blocked_after_five_failures_even_with_right_password(client, db_session):
    create_household(db_session, "Home", "secret")
    for _ in range(5):
        assert _login(client, "Home", "wrong").status_code == 401
    resp = _login(client, "Home", "secret")
    assert resp.status_code == 429
    assert int(resp.headers["Retry-After"]) > 0


def test_block_is_per_household_name(client, db_session):
    create_household(db_session, "Home", "secret")
    create_household(db_session, "Other", "secret2")
    for _ in range(5):
        _login(client, "Home", "wrong")
    assert _login(client, "Other", "secret2").status_code == 200


def test_name_is_case_insensitive_for_limiting(client, db_session):
    create_household(db_session, "Home", "secret")
    for name in ["Home", "HOME", "home", "hOmE", "Home"]:
        _login(client, name, "wrong")
    assert _login(client, "home", "secret").status_code == 429


def test_successful_login_resets_name_counter(client, db_session):
    create_household(db_session, "Home", "secret")
    for _ in range(4):
        _login(client, "Home", "wrong")
    assert _login(client, "Home", "secret").status_code == 200
    for _ in range(4):
        assert _login(client, "Home", "wrong").status_code == 401


def test_ip_limit_across_names(client):
    for i in range(20):
        assert _login(client, f"nobody{i}", "x").status_code == 401
    assert _login(client, "nobody-new", "x").status_code == 429


def test_unknown_names_are_limited_too(client):
    for _ in range(5):
        assert _login(client, "ghost", "x").status_code == 401
    assert _login(client, "ghost", "x").status_code == 429
