"""The engine fingerprint must identify everything that defines the image."""
import json
from pathlib import Path
import re
import shutil

import pytest

from holo_desert import doctor as doctor_module
from holo_desert.resources.docker import stack_builder
from holo_desert.resources.docker.stack_builder import ENGINE_FILES, engine_fingerprint, expected_base_image

RESOURCES = Path(stack_builder.__file__).resolve().parents[1]
ROOT = Path(__file__).resolve().parents[2]
PINNED = 'uwsignet/desert:4.0.0@sha256:59c734d2980de64e4b36429c3fb4a60aceb1cb7efc5f9d605f9b7781fbc51ca6'


@pytest.fixture(autouse=True)
def no_base_override(monkeypatch):
    monkeypatch.delenv('DESERT_IMAGE', raising=False)


def source_copy(tmp_path):
    shutil.copytree(RESOURCES / 'docker', tmp_path / 'docker', ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copytree(RESOURCES / 'desert', tmp_path / 'desert', ignore=shutil.ignore_patterns('__pycache__'))
    return tmp_path / 'docker'


def test_dockerfile_change_changes_fingerprint(tmp_path):
    docker = source_copy(tmp_path)
    before = engine_fingerprint(docker)
    dockerfile = docker / 'Dockerfile'
    dockerfile.write_text(dockerfile.read_text(encoding='utf-8') + 'RUN true\n', encoding='utf-8')
    assert engine_fingerprint(docker) != before


def test_base_image_reference_changes_fingerprint(tmp_path, monkeypatch):
    docker = source_copy(tmp_path)
    pinned = engine_fingerprint(docker)
    other = 'uwsignet/desert:4.0.0@sha256:' + '0' * 64
    assert engine_fingerprint(docker, base_image=other) != pinned
    monkeypatch.setenv('DESERT_IMAGE', other)
    assert engine_fingerprint(docker) == engine_fingerprint(docker, base_image=other)


def test_default_base_image_is_the_locked_digest(monkeypatch):
    lock = json.loads((ROOT / 'dependencies.lock.json').read_text(encoding='utf-8'))['desert']
    assert expected_base_image() == lock['image'] + '@' + lock['image_digest'] == PINNED
    compose = (RESOURCES / 'docker/compose.yaml').read_text(encoding='utf-8')
    assert '${DESERT_IMAGE:-' + PINNED + '}' in compose
    monkeypatch.setenv('DESERT_IMAGE', 'example/desert@sha256:' + '1' * 64)
    assert expected_base_image() == 'example/desert@sha256:' + '1' * 64


def test_every_file_copied_from_docker_directory_is_fingerprinted():
    dockerfile = (RESOURCES / 'docker/Dockerfile').read_text(encoding='utf-8')
    copied = {Path(source).name for line in dockerfile.splitlines() if line.startswith('COPY ')
              for source in line.split()[1:-1] if source.startswith('docker/')}
    assert copied == set(ENGINE_FILES)


def test_image_layout_reproduces_host_fingerprint(tmp_path):
    # Inside the image the files live flat in /opt/holo with desert/ beside them.
    image = tmp_path / 'opt_holo'
    image.mkdir()
    for name in ENGINE_FILES:
        shutil.copy(RESOURCES / 'docker' / name, image / name)
    shutil.copytree(RESOURCES / 'desert', image / 'desert', ignore=shutil.ignore_patterns('__pycache__'))
    assert engine_fingerprint(image, base_image=PINNED) == engine_fingerprint()


def run_doctor(monkeypatch, reply):
    class Adapter:
        port = 5999
        def health(self): return reply is not None
        def health_info(self): return reply
    monkeypatch.setattr(doctor_module, 'DESERTAdapter', Adapter)
    monkeypatch.setattr(doctor_module, 'docker_command', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('no docker in unit test')))
    return {c['name']: c for c in doctor_module.doctor(library_only=True)}


def test_doctor_accepts_engine_built_from_expected_base(monkeypatch):
    checks = run_doctor(monkeypatch, {'event': 'health', 'engine_fingerprint': engine_fingerprint(),
                                      'desert_base_image': PINNED})
    assert checks['desert_engine']['ok']
    assert PINNED in checks['desert_engine']['detail']


def test_doctor_rejects_engine_built_from_another_base(monkeypatch):
    other = 'example/desert@sha256:' + '2' * 64
    checks = run_doctor(monkeypatch, {'event': 'health', 'engine_fingerprint': engine_fingerprint(base_image=other),
                                      'desert_base_image': other})
    assert not checks['desert_engine']['ok']
    assert other in checks['desert_engine']['detail'] and PINNED in checks['desert_engine']['detail']
