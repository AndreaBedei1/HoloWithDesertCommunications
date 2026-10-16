from __future__ import annotations

import importlib.util
import platform
import socket
import sys
import subprocess
from .desert_adapter.backend import docker_command, DESERTAdapter, BackendError


def doctor():
    checks = []
    def check(name, function):
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
    check("docker", lambda: docker_command("version", "--format", "{{.Server.Version}}", timeout=12).stdout.strip())
    check("compose", lambda: docker_command("compose", "version", timeout=12).stdout.strip())
    def holo():
        import holoocean
        if holoocean.__version__ != "2.3.0":
            raise RuntimeError(f"Expected 2.3.0, found {holoocean.__version__}")
        return holoocean.__version__
    check("holoocean", holo)
    def ocean():
        import holoocean
        packages = holoocean.packagemanager.installed_packages()
        if "Ocean" not in packages:
            raise RuntimeError("Ocean package missing")
        return ", ".join(packages)
    check("ocean_package", ocean)
    def gpu():
        result = subprocess.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"], capture_output=True, text=True, timeout=10)
        if result.returncode:
            raise RuntimeError("nvidia-smi failed; use holo-desert probe-holo for an actual renderer test")
        return result.stdout.strip() + "; rendering still requires probe-holo"
    check("gpu", gpu)
    for port in (8000, 5555):
        def available(port=port):
            try:
                with socket.socket() as s:
                    s.bind(("127.0.0.1", port))
            except OSError:
                if port == 5555 and DESERTAdapter().health():
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
        return docker_command("image", "inspect", "uwsignet/desert:4.0.0", "--format", "{{json .RepoDigests}}", timeout=12).stdout.strip()
    check("desert_image", image)
    def service():
        if not DESERTAdapter().health():
            raise RuntimeError("Service not running; use holo-desert engine up")
        return "TCP health reply through published Docker port"
    check("host_container_tcp", service)
    return checks
