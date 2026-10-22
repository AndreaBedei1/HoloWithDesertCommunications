"""Personal YAML scenarios, separate from distributed examples and run results."""
from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import re
import tempfile
import threading
import time
import unicodedata
import uuid

import yaml

from .config import POWER_UNITS, Scenario


class ScenarioConflict(ValueError):
    pass


def default_directory():
    if os.environ.get("HOLO_DESERT_SCENARIOS_DIR"):
        return Path(os.environ["HOLO_DESERT_SCENARIOS_DIR"]).expanduser()
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "HoloOceanDESERT/scenarios"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "holo-desert/scenarios"


class ScenarioLibrary:
    MAX_BYTES = 262144
    ID = re.compile(r"user_[0-9a-f]{32}\Z")
    PREFIX = 'user_'
    MODEL = Scenario

    def __init__(self, directory=None, reserved_names=()):
        self.directory = Path(directory or default_directory()).expanduser().resolve()
        self.reserved = {self._key(n) for n in reserved_names}
        self.lock = threading.RLock()

    @staticmethod
    def _key(name):
        return unicodedata.normalize("NFKC", name.strip()).casefold()

    def _path(self, identifier):
        if not self.ID.fullmatch(identifier):
            raise ValueError("Identificativo personale non valido; gli esempi sono protetti")
        path = self.directory / (identifier + ".yaml")
        if path.is_symlink() or path.resolve().parent != self.directory:
            raise ValueError("Percorso dello scenario non consentito")
        return path

    @contextmanager
    def _write_lock(self):
        # Advisory OS lock releases even if a server crashes. It also covers two
        # local dashboard processes; atomic replace alone cannot prevent lost edits.
        self.directory.mkdir(parents=True, exist_ok=True)
        lock_path = self.directory / ".library.lock"
        if lock_path.is_symlink():
            raise ValueError("Percorso di lock non consentito")
        with self.lock, lock_path.open("a+b") as handle:
            if handle.seek(0, 2) == 0:
                handle.write(b"0")
                handle.flush()
            deadline = time.monotonic() + 5
            while True:
                try:
                    handle.seek(0)
                    if os.name == "nt":
                        import msvcrt
                        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise ScenarioConflict("Libreria occupata; riprova tra pochi secondi")
                    time.sleep(.05)
            try:
                yield
            finally:
                if os.name == "nt":
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(handle, fcntl.LOCK_UN)

    @staticmethod
    def _upgrade(data):
        """Read files saved before power events carried their medium's own unit.

        Back then an optical or EM ``tx_power_db`` value reached the PHY unchanged,
        as W or dBm, so the same value moves to that unit's field.
        """
        network = data.get("network") if isinstance(data, dict) else None
        events = data.get("power_events") if isinstance(network, dict) else None
        unit = POWER_UNITS.get(network.get("medium", "acoustic")) if isinstance(network, dict) else None
        if unit in (None, "tx_power_db") or not isinstance(events, list):
            return data
        legacy = lambda e: isinstance(e, dict) and "tx_power_db" in e and not set(e) & {"tx_power_w", "tx_power_dbm"}
        return {**data, "power_events": [{**{k: v for k, v in e.items() if k != "tx_power_db"}, unit: e["tx_power_db"]}
                                         if legacy(e) else e for e in events]}

    def _read_record(self, identifier):
        path = self._path(identifier)
        if path.stat().st_size > self.MAX_BYTES:
            raise ValueError("Scenario troppo grande (massimo 256 KiB)")
        raw = path.read_bytes()
        config = self.MODEL.model_validate(self._upgrade(yaml.safe_load(raw)))
        return {"id": identifier, "kind": "user", "revision": hashlib.sha256(raw).hexdigest(),
                "configuration": config.model_dump()}

    def get(self, identifier):
        self._path(identifier)
        with self._write_lock():
            return self._read_record(identifier)

    def list(self):
        if not self.directory.exists():
            return []
        with self._write_lock():
            return self._list_unlocked()

    def _list_unlocked(self):
        records = []
        for path in sorted(self.directory.glob(self.PREFIX + "*.yaml")):
            try:
                records.append(self._read_record(path.stem))
            except (ValueError, OSError, yaml.YAMLError):
                # A malformed external file never hides valid personal scenarios.
                continue
        return sorted(records, key=lambda r: self._key(r["configuration"]["name"]))

    def save(self, configuration, identifier=None, expected_revision=None):
        scenario = self.MODEL.model_validate(configuration)
        name = scenario.name.strip()
        if not 1 <= len(name) <= 100 or any(ord(c) < 32 for c in name):
            raise ValueError("Il nome deve contenere da 1 a 100 caratteri leggibili")
        scenario.name = name
        raw = yaml.safe_dump(scenario.model_dump(), allow_unicode=True, sort_keys=False).encode("utf-8")
        if len(raw) > self.MAX_BYTES:
            raise ValueError("Scenario troppo grande (massimo 256 KiB)")
        with self._write_lock():
            if identifier:
                current = self._read_record(identifier)
                if current["revision"] != expected_revision:
                    raise ScenarioConflict("Lo scenario è cambiato. Ricaricalo prima di salvare")
            key = self._key(name)
            if key in self.reserved or any(self._key(r["configuration"]["name"]) == key and r["id"] != identifier for r in self._list_unlocked()):
                raise ScenarioConflict("Esiste già uno scenario con questo nome")
            identifier = identifier or self.PREFIX + uuid.uuid4().hex
            target = self._path(identifier)
            descriptor, temporary = tempfile.mkstemp(prefix=".scenario-", suffix=".tmp", dir=self.directory)
            try:
                with os.fdopen(descriptor, "wb") as handle:
                    handle.write(raw)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, target)
            finally:
                Path(temporary).unlink(missing_ok=True)
            return self._read_record(identifier)

    def delete(self, identifier, expected_revision):
        with self._write_lock():
            if self._read_record(identifier)["revision"] != expected_revision:
                raise ScenarioConflict("Lo scenario è cambiato. Ricaricalo prima di eliminarlo")
            self._path(identifier).unlink()

    def parse_yaml(self, text):
        if len(text.encode("utf-8")) > self.MAX_BYTES:
            raise ValueError("Scenario troppo grande (massimo 256 KiB)")
        try:
            return self.MODEL.model_validate(yaml.safe_load(text)).model_dump()
        except yaml.YAMLError as exc:
            raise ValueError("YAML non valido: controlla sintassi e indentazione") from exc
