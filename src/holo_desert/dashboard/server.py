from __future__ import annotations

from contextlib import asynccontextmanager
import threading
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

        @app.post("/api/start")
        def start(request: StartRequest):
            with self.control_lock:
                if self.run and self.run.state in ("starting", "running", "paused"):
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
                        if self.run.state in ("starting", "running", "paused"):
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
            if self.run is None:
                raise HTTPException(409, "No results to export")
            return Response(self.run.telemetry.export(), media_type="application/zip",
                            headers={"Content-Disposition": 'attachment; filename="holo-desert-results.zip"'})

        return app
