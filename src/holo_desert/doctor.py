from __future__ import annotations

import importlib.util
import platform
import socket
import sys
import subprocess
from .desert_adapter.backend import docker_command, DESERTAdapter, BackendError, BASE_IMAGE


def doctor(library_only=False):
    """Check prerequisites; ``library_only`` skips HoloOcean, GPU and dashboard checks."""
    checks = []
    def check(name, function, skip=False):
        if skip:
            checks.append({"name": name, "ok": True, "skipped": True, "detail": "not needed for library-only use"})
            return
        try:
            value = function()
            checks.append({"name": name, "ok": True, "detail": str(value)})
        except Exception as exc:
            checks.append({"name": name, "ok": False, "detail": str(exc)})

    check("os", lambda: f"{platform.system()} {platform.release()}; target Ubuntu 24.04 / native Windows + Docker Desktop")
    def python():
        if not (3, 10) <= sys.version_info < (3, 13):
            raise RuntimeError("Python 3.10..3.12 required")
        return sys.version.split()[0]
    check("python", python)
    def package():
        import importlib.metadata
        import holo_desert
        return f"holoocean-desert {importlib.metadata.version('holoocean-desert')} (module {holo_desert.__version__})"
    check("package", package)
    def dashboard_extra():
        missing = [m for m in ("fastapi", "uvicorn") if importlib.util.find_spec(m) is None]
        if missing:
            raise RuntimeError(f"Missing {', '.join(missing)}: pip install 'holoocean-desert[dashboard]'")
        return "fastapi and uvicorn importable"
    check("dashboard_extra", dashboard_extra, skip=library_only)
    check("docker", lambda: docker_command("version", "--format", "{{.Server.Version}}", timeout=12).stdout.strip())
    check("compose", lambda: docker_command("compose", "version", timeout=12).stdout.strip())
    def holo():
        import holoocean
        if holoocean.__version__ != "2.3.0":
            raise RuntimeError(f"Expected 2.3.0, found {holoocean.__version__}")
        return holoocean.__version__
    check("holoocean", holo, skip=library_only)
    def ocean():
        import holoocean
        packages = holoocean.packagemanager.installed_packages()
        if "Ocean" not in packages:
            raise RuntimeError("Ocean package missing")
        return ", ".join(packages)
    check("ocean_package", ocean, skip=library_only)
    def gpu():
        result = subprocess.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"], capture_output=True, text=True, timeout=10)
        if result.returncode:
            raise RuntimeError("nvidia-smi failed; use holo-desert probe-holo for an actual renderer test")
        return result.stdout.strip() + "; rendering still requires probe-holo"
    check("gpu", gpu, skip=library_only)
    desert_port = DESERTAdapter().port
    for port in ((desert_port,) if library_only else (8000, desert_port)):
        def available(port=port):
            try:
                with socket.socket() as s:
                    s.bind(("127.0.0.1", port))
            except OSError:
                if port == desert_port and DESERTAdapter().health():
                    return "Port belongs to healthy DESERT service"
                if port == 8000:
                    import json
                    import urllib.request
                    with urllib.request.urlopen("http://127.0.0.1:8000/openapi.json", timeout=2) as r:
                        if json.load(r).get("info", {}).get("title") == "HoloOcean-DESERT":
                            return "Port belongs to HoloOcean-DESERT dashboard"
                raise RuntimeError(f"Port {port} is occupied by another service")
            return f"127.0.0.1:{port} available"
        check(f"port_{port}", available)
    def image():
        reference = BASE_IMAGE.split("@")[0]
        return docker_command("image", "inspect", reference, "--format", "{{json .RepoDigests}}", timeout=12).stdout.strip()
    check("desert_base_image", image)
    def service():
        info = DESERTAdapter().health_info()
        if info is None:
            raise RuntimeError(f"No DESERT service on port {desert_port}; run holo-desert engine up")
        from .resources.docker.stack_builder import engine_fingerprint
        expected = engine_fingerprint()
        if info.get("engine_fingerprint") != expected:
            raise RuntimeError(f"Engine image is outdated (service {info.get('engine_fingerprint')}, "
                               f"package {expected}); run holo-desert engine up")
        return f"healthy on port {desert_port}, engine {expected}"
    check("desert_engine", service)
    return checks
