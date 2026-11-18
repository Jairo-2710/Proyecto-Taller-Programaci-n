import pytest

from app.api.rate_limit import LoginRateLimiter, login_limiter


def test_rate_limiter_bloquea_despues_de_cinco_intentos():
    limiter = LoginRateLimiter(
        max_attempts=5,
        window_seconds=60,
        lockout_seconds=300,
    )
    key = ("127.0.0.1", "usuario@test.com")

    for _ in range(4):
        assert limiter.check(key) == 0
        limiter.record_failure(key)

    assert limiter.check(key) == 0

    limiter.record_failure(key)

    assert limiter.check(key) > 0


def test_rate_limiter_permite_reintentar_despues_del_bloqueo():
    limiter = LoginRateLimiter(
        max_attempts=2,
        window_seconds=60,
        lockout_seconds=1,
    )
    key = ("127.0.0.1", "usuario@test.com")

    limiter.record_failure(key)
    limiter.record_failure(key)

    assert limiter.check(key) > 0

    import time
    time.sleep(1.1)

    assert limiter.check(key) == 0


def test_rate_limiter_reset_limpia_intentos():
    limiter = LoginRateLimiter(max_attempts=2)
    key = ("127.0.0.1", "usuario@test.com")

    limiter.record_failure(key)
    limiter.reset(key)

    assert limiter.check(key) == 0


def test_api_bloquea_login_despues_de_cinco_fallos(client):
    key = ("testclient", "admin@umb.local")
    login_limiter.clear()

    try:
        for _ in range(5):
            response = client.post(
                "/auth/login",
                json={
                    "email": "admin@umb.local",
                    "password": "incorrecta",
                },
            )
            assert response.status_code == 401

        response = client.post(
            "/auth/login",
            json={
                "email": "admin@umb.local",
                "password": "Admin12345!",
            },
        )

        assert response.status_code == 429
        assert int(response.headers["Retry-After"]) > 0

    finally:
        login_limiter.clear()
