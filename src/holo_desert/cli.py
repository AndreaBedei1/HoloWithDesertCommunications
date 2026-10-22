from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import socket
from .api import ManagedSimulation, SessionError
from .desert_adapter.backend import docker_command, COMPOSE, BackendError
from .doctor import doctor
from .scenarios.config import ScenarioManager, RESOURCE_ROOT, Network
from .resources.docker.stack_builder import MACS, pinned_base_image


def dashboard_server(**options):
    try:
        from .dashboard.server import DashboardServer
    except ImportError as exc:
        raise RuntimeError("The web laboratory needs the dashboard extra: "
                           "pip install 'holoocean-desert[dashboard]'") from exc
    return DashboardServer(**options)


def serve_dashboard(application, port, before_start=None):
    """Reserve the port before starting either simulator; fail without side effects."""
    import uvicorn
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", port))
        listener.listen(128)
        if before_start:
            before_start()
        uvicorn.Server(uvicorn.Config(application, host="127.0.0.1", port=port,
                                      log_level="warning")).run(sockets=[listener])


def parser():
    p = argparse.ArgumentParser(prog="holo-desert", description="HoloOcean 2.3 + real DESERT 4.0, without ROS")
    sub = p.add_subparsers(dest="command", required=True)
    doctor_parser = sub.add_parser("doctor", help="Check prerequisites, engine image and ports")
    doctor_parser.add_argument("--library-only", action="store_true",
                               help="Skip HoloOcean/GPU/dashboard checks (standalone DESERT use)")
    doctor_parser.add_argument("--json", action="store_true")
    sub.add_parser("examples")
    run = sub.add_parser("run")
    run.add_argument("scenario", nargs="?", default="e01_chat")
    run.add_argument("--standalone", action="store_true", help="DESERT with fixed network fixtures; no HoloOcean")
    run.add_argument("--no-dashboard", action="store_true")
    run.add_argument("--no-manage-docker", action="store_true")
    run.add_argument("--duration", type=float)
    run.add_argument("--fast", action="store_true", help="Skip wall-clock pacing; logical clocks remain synchronized")
    run.add_argument("--profile", choices=["acoustic_default", "acoustic_aloha"])
    run.add_argument("--mac", choices=list(MACS), help="Change only MAC protocol, preserving other scenario parameters")
    run.add_argument("--persist", type=Path)
    run.add_argument("--port", type=int, default=8000)
    run.add_argument("--headless", action="store_true")
    dashboard = sub.add_parser("dashboard")
    dashboard.add_argument("--port", type=int, default=8000)
    dashboard.add_argument("--no-manage-docker", action="store_true")
    engine = sub.add_parser("engine")
    engine.add_argument("action", choices=["up", "down", "status"])
    sub.add_parser("logs")
    sub.add_parser("official-sample")
    sub.add_parser("official-sockets")
    sub.add_parser("probe-holo")
    test = sub.add_parser("test")
    test.add_argument("--integration", action="store_true")
    test.add_argument("--end-to-end", action="store_true")
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    manager = ScenarioManager()
    try:
        if args.command == "examples":
            for name in manager.list():
                print(f"{name:20} {manager.load(name).description}")
        elif args.command == "doctor":
            results = doctor(library_only=args.library_only)
            if args.json:
                print(json.dumps(results, indent=2))
            for r in results if not args.json else []:
                status = "SKIP" if r.get("skipped") else "OK" if r["ok"] else "FAIL"
                print(f"{status:4} {r['name']:20} {r['detail']}")
            return 0 if all(r["ok"] for r in results) else 1
        elif args.command in ("engine", "logs"):
            if args.command == "logs":
                cmd = [*COMPOSE, "logs", "--tail", "100"]
            else:
                cmd = [*COMPOSE, *{"up": ["up", "-d", "--build"], "down": ["down"], "status": ["ps"]}[args.action]]
            result = docker_command(*cmd, timeout=1200)
            print(result.stdout)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
        elif args.command == "official-sample":
            # Read when used: importing the library never depends on the bundled Dockerfile.
            result = docker_command("run", "--rm", pinned_base_image(), "bash", "-lc",
                "source /home/DESERT_Underwater/DESERT_buildCopy_LOCAL/environment && cd /tmp && ns /home/DESERT_Underwater/DESERT_Framework/DESERT/samples/desert_samples/Application/test_uwApplication.tcl", timeout=120)
            print(result.stdout)
            print(result.stderr, file=sys.stderr)
        elif args.command == "official-sockets":
            result = docker_command(*COMPOSE, "exec", "-T", "desert", "bash", "-lc",
                "source /home/DESERT_Underwater/DESERT_buildCopy_LOCAL/environment && python3 /opt/holo/probe-sockets.py", timeout=30)
            print(result.stdout)
            print(result.stderr, file=sys.stderr)
        elif args.command == "probe-holo":
            from .holoocean_adapter.adapter import HoloOceanAdapter
            scenario = manager.load("e01_chat")
            adapter = HoloOceanAdapter(scenario)
            try:
                print(json.dumps({k: vars(v) for k, v in adapter.start().items()}, indent=2))
                for _ in range(30):
                    adapter.tick()
                print("HoloOcean rendering, sensors and 30 physics ticks verified")
            finally:
                adapter.stop()
        elif args.command == "dashboard":
            application = dashboard_server(manage_docker=not args.no_manage_docker).application()
            print(f"Dashboard: http://127.0.0.1:{args.port}")
            serve_dashboard(application, args.port)
        elif args.command == "run":
            scenario = manager.load(args.scenario)
            overrides = {}
            if args.duration is not None:
                overrides["duration"] = args.duration
            if args.fast:
                overrides["realtime"] = False
            if args.profile:
                import yaml
                data = yaml.safe_load((RESOURCE_ROOT / "profiles" / (args.profile + ".yaml")).read_text())
                overrides["network"] = Network.model_validate(data)
            if args.mac:
                network = Network.model_validate(overrides.get("network", scenario.network).model_dump())
                network.mac.protocol = args.mac
                overrides["network"] = network
            scenario = type(scenario).model_validate({**scenario.model_dump(), **overrides})
            run = ManagedSimulation(scenario, holoocean=not args.standalone, show_viewport=not args.headless,
                                    manage_engine=not args.no_manage_docker, persist=args.persist)
            try:
                if args.no_dashboard:
                    try:
                        run.run()
                    except SessionError:
                        pass  # reported below with the counts observed so far
                    print(json.dumps({"state": run.state, "error": run.error, "counts": run.snapshot()["counts"]}, indent=2))
                    return 1 if run.error else 0
                print(f"Dashboard: http://127.0.0.1:{args.port} (Ctrl+C to close and clean up)")
                serve_dashboard(dashboard_server(initial_run=run, manage_docker=not args.no_manage_docker).application(),
                                args.port, run.start_background)
                return 1 if run.error else 0
            finally:
                # The dashboard lifespan may already have closed it; closing twice is harmless.
                run.close()
        elif args.command == "test":
            marker = "holoocean" if args.end_to_end else "desert and not holoocean" if args.integration else "not desert and not holoocean"
            return subprocess.call([sys.executable, "-m", "pytest", "-q", "-m", marker])
    except (BackendError, ValueError, OSError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
