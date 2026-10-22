"""The running engine identifies its base image and build content."""
import pytest

from holo_desert.desert_adapter.backend import DESERTAdapter
from holo_desert.doctor import doctor
from holo_desert.resources.docker.stack_builder import engine_fingerprint, expected_base_image
from holo_desert.scenarios.config import ScenarioManager

pytestmark = pytest.mark.desert


def test_engine_reports_its_base_image_and_the_package_fingerprint(engine):
    health = DESERTAdapter().health_info()
    assert health['desert_base_image'] == expected_base_image()
    assert health['engine_fingerprint'] == engine_fingerprint()
    backend = DESERTAdapter(manage_docker=False)
    try:
        backend.start(ScenarioManager().load('e01_chat'))
        assert backend.versions['desert_base_image'] == expected_base_image()
    finally:
        backend.stop()


def test_doctor_flags_an_engine_built_from_another_base(engine, monkeypatch):
    checks = {c['name']: c for c in doctor(library_only=True)}
    assert checks['desert_engine']['ok'] and checks['desert_base_image']['ok'], checks
    monkeypatch.setenv('DESERT_IMAGE', 'uwsignet/desert:4.0.0@sha256:' + '0' * 64)
    checks = {c['name']: c for c in doctor(library_only=True)}
    assert not checks['desert_engine']['ok']
    assert not checks['desert_base_image']['ok']
