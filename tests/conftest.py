import os
import pytest
from holo_desert.desert_adapter.backend import DESERTAdapter, COMPOSE, docker_command


@pytest.fixture(scope="session")
def engine(request):
    if not request.config.getoption("-m") or "desert" not in request.config.getoption("-m") and "holoocean" not in request.config.getoption("-m"):
        pytest.skip("Select -m desert or -m holoocean to run real simulator tests")
    owned = not DESERTAdapter().health()
    if owned:
        docker_command(*COMPOSE, "up", "-d", "--build", timeout=1200)
        import time
        deadline = time.monotonic() + 30
        while not DESERTAdapter().health():
            if time.monotonic() > deadline:
                pytest.fail("Real DESERT engine failed health check")
            time.sleep(.25)
    yield
    if owned:
        docker_command(*COMPOSE, "down", timeout=30)
