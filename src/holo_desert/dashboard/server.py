from __future__ import annotations

from contextlib import asynccontextmanager
import threading
import hashlib
import json
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict

from ..core.orchestrator import SimulationOrchestrator
from ..scenarios.config import ScenarioManager, Scenario


class StartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenario: str = "e01_chat"
    standalone: bool = False
    configuration: dict | None = None


class DashboardServer:
    def __init__(self, *, manage_docker=True, initial_run=None):
        self.manager = ScenarioManager()
        self.run = initial_run
        self.manage_docker = manage_docker
        self.control_lock = threading.Lock()
        self.comparisons = []

    def application(self):
        @asynccontextmanager
        async def lifespan(app):
            yield
            if self.run:
                self.run.close()

        app = FastAPI(title="HoloOcean-DESERT", lifespan=lifespan)
        static = Path(__file__).parent / "static"
        app.mount("/static", StaticFiles(directory=static), name="static")

        @app.get("/")
        def index():
            return FileResponse(static / "index.html")

        @app.get("/api/scenarios")
        def scenarios():
            return [{"id": name, "description": self.manager.load(name).description} for name in self.manager.list()]

        @app.get("/api/scenarios/{name}")
        def configuration(name: str):
            try:
                return self.manager.load(name).model_dump()
            except ValueError as exc:
                raise HTTPException(404, str(exc)) from exc

        @app.get("/api/state")
        def state():
            if self.run:
                return self.run.snapshot()
            return {"state": "idle", "services": {"holoocean": "not_started", "desert": "not_started"},
                    "fleet": {}, "packets": [], "series": [], "counts": {}, "events": [], "edges": [], "trails": {}}

        @app.post("/api/validate")
        def validate(configuration: dict):
            try:
                return Scenario.model_validate(configuration).model_dump()
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc

        @app.get("/api/comparisons")
        def comparisons():
            with self.control_lock:
                equivalent = (len(self.comparisons) == 2 and
                              self.comparisons[0]["fingerprint"] == self.comparisons[1]["fingerprint"] and
                              self.comparisons[0]["mac"] != self.comparisons[1]["mac"])
                return {"runs": self.comparisons, "equivalent": equivalent,
                        "note": "Equivalent means only MAC protocol differs; same configured seed and geometry, not identical measured trajectories."}

        @app.post("/api/comparison")
        def retain_comparison():
            with self.control_lock:
                if not self.run or self.run.state != "finished" or self.run.standalone:
                    raise HTTPException(409, "Complete an integrated E04 run before retaining its summary")
                config = self.run.scenario.model_dump()
                if config["name"] != "e04_congestion":
                    raise HTTPException(422, "Comparison is limited to E04")
                if any(r["run_id"] == self.run.run_id for r in self.comparisons):
                    return {"ok": True}
                mac = config["network"]["mac"].pop("protocol")
                fingerprint = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
                self.comparisons.append({"run_id": self.run.run_id, "mac": mac, "fingerprint": fingerprint,
                                         "configuration": self.run.scenario.model_dump(),
                                         "summary": self.run.telemetry.summary()})
                self.comparisons = self.comparisons[-2:]
                return {"ok": True}

        @app.post("/api/start")
        def start(request: StartRequest):
            with self.control_lock:
                if self.run and self.run.state in ("starting", "running", "paused", "stopping"):
                    raise HTTPException(409, "A run is already active")
                try:
                    scenario = Scenario.model_validate(request.configuration) if request.configuration else self.manager.load(request.scenario)
                    if self.run:
                        self.run.close()
                    self.run = SimulationOrchestrator(scenario, standalone=request.standalone,
                                                       manage_docker=self.manage_docker)
                    self.run.start_background()
                except (ValueError, RuntimeError) as exc:
                    raise HTTPException(422, str(exc)) from exc
            return {"state": self.run.state}

        @app.post("/api/{action}")
        def control(action: str):
            with self.control_lock:
                if not self.run:
                    raise HTTPException(409, "No simulation")
                try:
                    if action == "stop":
                        self.run.stop()
                    elif action == "pause":
                        self.run.pause()
                    elif action == "resume":
                        self.run.resume()
                    elif action == "reset":
                        if self.run.state in ("starting", "running", "paused", "stopping"):
                            raise RuntimeError("Stop the run before resetting")
                        self.run.close()
                        self.run = None
                    else:
                        raise HTTPException(404, "Unknown action")
                except RuntimeError as exc:
                    raise HTTPException(409, str(exc)) from exc
            return {"ok": True}

        @app.get("/api/export")
        def export():
            with self.control_lock:
                if self.run is None:
                    raise HTTPException(409, "No results to export")
                return Response(self.run.telemetry.export(), media_type="application/zip",
                                headers={"Content-Disposition": 'attachment; filename="holo-desert-results.zip"'})

        return app
