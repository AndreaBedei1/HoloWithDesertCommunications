"""Local TCP transport. It never implements network simulation or delivery.

One client owns one NS process. JSON config first; then newline-framed commands
and simulator JSON events. Disconnect kills the owned NS process.
"""
import json
import math
import os
import socketserver
import socket
import subprocess
import tempfile
import threading
import time


def finite(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("Non-finite configuration")
    return format(result, ".15g")


# The builder is pure stdlib, shared with host-side schema validation.
try:
    from holo_desert.resources.docker.stack_builder import render, validate, CATALOG_VERSION, effective_nodes
except ImportError:
    from stack_builder import render, validate, CATALOG_VERSION, effective_nodes


def _image_file(name):
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), name)) as f:
            return f.read().strip()
    except OSError:
        return None


ENGINE_FINGERPRINT = _image_file("engine-fingerprint")
# DESERT base image reference (DESERT_IMAGE build argument) of this image.
ENGINE_BASE_IMAGE = _image_file("engine-base-image")


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        first = self.rfile.readline(131072)
        if first == b'HEALTH\n':
            self.wfile.write((json.dumps({"event": "health", "backend": "desert", "release": "4.0.0",
                                          "engine_fingerprint": ENGINE_FINGERPRINT,
                                          "desert_base_image": ENGINE_BASE_IMAGE}) + "\n").encode())
            return
        # A stopped predecessor can still be reaping its child for a moment.
        if not self.server.owner.acquire(timeout=2):
            self.wfile.write(b'{"event":"error","reason":"DESERT is busy"}\n')
            return
        process = None
        try:
            config = validate(json.loads(first))
            commit = subprocess.check_output(["git", "-C", "/home/DESERT_Underwater", "rev-parse", "HEAD"], text=True).strip()
            self.wfile.write((json.dumps({"event": "engine_info", "time": 0,
                "desert_release": "4.0.0", "desert_source_commit": commit, "desert_base_image": ENGINE_BASE_IMAGE,
                "stack_builder": CATALOG_VERSION, "engine_fingerprint": ENGINE_FINGERPRINT, "phy_patch": {"optical":"native-optical-lambert-beer-body-frame-v1","em":"em-power-lut-v1"}.get(config['network'].get('medium'), "conditional-bpsk-v1" if any(n["acoustic"].get("phy")=="bpsk_corrected" for n in effective_nodes(config)) else "upstream-original"),
                "effective_network": config["network"], "effective_nodes": effective_nodes(config)}) + "\n").encode())
            self.wfile.flush()
            with tempfile.TemporaryDirectory(prefix="holo-desert-") as temp:
                path = os.path.join(temp, "config.tcl")
                with open(path, "w") as f:
                    f.write(render(config))
                process = subprocess.Popen(["ns", "/opt/holo/desert/tcl/bridge.tcl", path],
                                           stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                           stderr=None, cwd=temp, bufsize=0)

                def output():
                    try:
                        for line in process.stdout:
                            # NS/library banners go only to container logs.
                            if line.startswith(b'{"event":'):
                                self.wfile.write(line)
                                self.wfile.flush()
                            else:
                                print(line.decode(errors="replace").rstrip(), flush=True)
                        self.wfile.write((json.dumps({"event": "engine_exit", "code": process.wait()}) + "\n").encode())
                    except (OSError, ValueError):
                        pass
                    finally:
                        try:
                            self.connection.shutdown(2)
                        except OSError:
                            pass

                pump = threading.Thread(target=output, daemon=True)
                pump.start()
                for line in self.rfile:
                    if len(line) > 20000:
                        raise ValueError("Bridge command too large")
                    process.stdin.write(line)
                    process.stdin.flush()
                process.terminate()
                process.wait(timeout=5)
                pump.join(timeout=5)
        except (ValueError, KeyError, OSError, subprocess.SubprocessError) as exc:
            print("Session error:", repr(exc), flush=True)
            try:
                self.wfile.write((json.dumps({"event": "error", "reason": str(exc)}) + "\n").encode())
            except OSError:
                pass
        finally:
            if process is not None and process.poll() is None:
                process.kill()
                process.wait()
            self.server.owner.release()


if __name__ == "__main__":
    class Server(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = True
        owner = threading.Lock()
    with Server(("0.0.0.0", 5555), Handler) as server:
        print("DESERT transport listening on 5555", flush=True)
        server.serve_forever()
