"""Probe unmodified official UW/APPLICATION TCP/UDP socket implementations.

Builds a temporary harness from the official sample in the installed image.
No upstream files are written. A UDP ingress-only result is reported honestly.
"""
import json
from pathlib import Path
import socket
import subprocess
import tempfile
import time

ROOT = Path("/home/DESERT_Underwater")
SAMPLE = ROOT / "DESERT_Framework/DESERT/samples/desert_samples/Application/test_uwApplication.tcl"


def probe(protocol):
    original = SAMPLE.read_text()
    # Drop the final run, retain official topology/library construction.
    script = original.rsplit("$ns run", 1)[0]
    script = script.replace("set ns [new Simulator]", "set ns [new Simulator]\n$ns use-scheduler RealTime")
    script += '''
$app(0) set period_ 0.02
$app_sink(0) set period_ 0.02
$app(0) set drop_out_of_order_ 0
$app_sink(0) set drop_out_of_order_ 0
$app(0) set max_read_length 4096
$app(0) set Socket_Port_ 4000
$app_sink(0) set Socket_Port_ 4001
$app(0) SetSocketProtocol %s
$app_sink(0) SetSocketProtocol %s
$ipr_sink addRoute 1 1
$ns at 0.01 "$app(0) start; $app_sink(0) start"
$ns at 4.0 {puts "PROBE_SENT=[$app(0) getsentpkts],[$app_sink(0) getsentpkts]"; puts "PROBE_RX=[$app(0) getrecvpkts],[$app_sink(0) getrecvpkts]"; flush stdout; exit 0}
$ns run
''' % (protocol, protocol)
    with tempfile.TemporaryDirectory(prefix="official-socket-") as directory:
        path = Path(directory) / "probe.tcl"
        path.write_text(script)
        process = subprocess.Popen(["ns", str(path)], cwd=directory, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        sockets = []
        received = []
        try:
            time.sleep(.5)
            for port in (4000, 4001):
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM if protocol == "TCP" else socket.SOCK_DGRAM)
                sock.settimeout(1.3)
                sock.connect(("127.0.0.1", port))
                sockets.append(sock)
            for index, sock in enumerate(sockets):
                sock.send(("official-%s-%s" % (protocol, index)).encode())
            for sock in sockets:
                try:
                    received.append(sock.recv(4096).decode(errors="replace"))
                except socket.timeout:
                    received.append(None)
            stdout, stderr = process.communicate(timeout=7)
            return {"protocol": protocol, "received_external": received,
                    "engine_summary": [line for line in stdout.decode(errors="replace").splitlines() if line.startswith("PROBE_")],
                    "exit_code": process.returncode, "stderr_tail": stderr.decode(errors="replace")[-1000:]}
        finally:
            for sock in sockets:
                sock.close()
            if process.poll() is None:
                process.kill()
                process.wait()


if __name__ == "__main__":
    print(json.dumps([probe("TCP"), probe("UDP")], indent=2))
