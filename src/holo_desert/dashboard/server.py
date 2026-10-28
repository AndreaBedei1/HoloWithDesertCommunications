from __future__ import annotations

from contextlib import asynccontextmanager
import threading
import hashlib
import json
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

# The web laboratory is a client of the public library API only.
from .. import (ManagedSimulation, ProfileLibrary, Scenario, ScenarioConflict, ScenarioManager, builtin_profiles,
                network_catalog, network_inventory)
from .comparison import experiment, differences


class StartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenario: str = "e01_chat"
    standalone: bool = False
    configuration: dict | None = None


class SaveScenarioRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    configuration: dict
    revision: str | None = None


class ImportScenarioRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    yaml: str = Field(max_length=262144)


class DashboardAssets(StaticFiles):
    """ES modules require a JavaScript MIME even with a broken Windows registry."""
    def file_response(self, full_path, stat_result, scope, status_code=200):
        response = super().file_response(full_path, stat_result, scope, status_code)
        media = {".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8"}
        if Path(full_path).suffix in media:
            response.headers["content-type"] = media[Path(full_path).suffix]
        return response


class DashboardServer:
    def __init__(self, *, manage_docker=True, initial_run=None, scenario_directory=None):
        self.manager = ScenarioManager(user_root=scenario_directory)
        self.profiles = ProfileLibrary(self.manager.library.directory / 'profiles',
                                       [p['name'] for p in builtin_profiles()])
        self.run = initial_run
        self.scenario_id = initial_run.scenario.name if initial_run else None
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
        app.mount("/static", DashboardAssets(directory=static), name="static")

        @app.get("/")
        def index():
            return FileResponse(static / "index.html")

        @app.get("/api/scenarios")
        def scenarios():
            return [{"id": name, "group": self.manager.group(name), "description": self.manager.load(name).description} for name in self.manager.list()]

        @app.get("/api/scenarios/{name}")
        def configuration(name: str):
            try:
                if name not in self.manager.list() and not self.manager.library.ID.fullmatch(name):
                    raise ValueError("Scenario non disponibile")
                return self.manager.load(name).model_dump()
            except (ValueError, FileNotFoundError) as exc:
                raise HTTPException(404, str(exc)) from exc

        def editable():
            if self.run and self.run.state in ("starting", "running", "paused", "stopping"):
                raise HTTPException(409, "Arresta la simulazione prima di modificare gli scenari")

        def storage_error(exc):
            if isinstance(exc, ScenarioConflict):
                raise HTTPException(409, str(exc)) from exc
            if isinstance(exc, FileNotFoundError):
                raise HTTPException(404, "Scenario personale non trovato") from exc
            raise HTTPException(422, str(exc)) from exc

        @app.get('/api/network-catalog')
        def catalog():
            return network_catalog()

        @app.get('/api/network-inventory')
        def inventory():
            return network_inventory()

        @app.get('/api/network-profiles')
        def network_profiles():
            return {'builtins': builtin_profiles(),
                    'personal': [self.profiles.public(p) for p in self.profiles.list()]}

        @app.post('/api/network-profiles/import')
        def import_profile(request: ImportScenarioRequest):
            try:
                return self.profiles.parse_yaml(request.yaml)
            except (ValueError, OSError) as exc:
                storage_error(exc)

        @app.post('/api/network-profiles')
        def create_profile(request: dict):
            with self.control_lock:
                editable()
                try:
                    data={k:v for k,v in request.items() if k!='revision'}
                    return self.profiles.public(self.profiles.save(data))
                except (ValueError,OSError) as exc:
                    storage_error(exc)

        @app.put('/api/network-profiles/{identifier}')
        def update_profile(identifier: str, request: dict):
            with self.control_lock:
                editable()
                try:
                    data={k:v for k,v in request.items() if k!='revision'}
                    return self.profiles.public(self.profiles.save(data,identifier,request.get('revision')))
                except (ValueError,OSError) as exc:
                    storage_error(exc)

        @app.delete('/api/network-profiles/{identifier}')
        def delete_profile(identifier: str, revision: str):
            with self.control_lock:
                editable()
                try:
                    self.profiles.delete(identifier,revision)
                    return {'ok':True}
                except (ValueError,OSError) as exc:
                    storage_error(exc)

        @app.get('/api/network-profiles/{identifier}/yaml')
        def export_profile(identifier: str):
            try:
                import yaml
                predefined=next((p for p in builtin_profiles() if p['id']==identifier),None)
                data=({k:predefined[k] for k in ('name','description','network')} if predefined else self.profiles.get(identifier)['configuration'])
                return Response(yaml.safe_dump(data,allow_unicode=True,sort_keys=False),
                    media_type='application/yaml',headers={'Content-Disposition':'attachment; filename="network-profile.yaml"'})
            except (ValueError,OSError) as exc:
                storage_error(exc)

        @app.get("/api/capabilities")
        def capabilities():
            return {"worlds": ["OpenWater"], "vehicles": ["HoveringAUV"], "max_nodes": 32,
                    "note": "Editor limitato all'ambiente e al veicolo verificati; YAML CLI invariati."}

        @app.get("/api/user-scenarios")
        def user_scenarios():
            return [{"id": r["id"], "revision": r["revision"], "kind": "user",
                     "name": r["configuration"]["name"], "description": r["configuration"]["description"],
                     "duration": r["configuration"]["duration"], "node_count": len(r["configuration"]["nodes"])}
                    for r in self.manager.list_user()]

        @app.post("/api/user-scenarios/import")
        def import_scenario(request: ImportScenarioRequest):
            try:
                return self.manager.library.parse_yaml(request.yaml)
            except ValueError as exc:
                storage_error(exc)

        @app.post("/api/user-scenarios")
        def create_scenario(request: SaveScenarioRequest):
            with self.control_lock:
                editable()
                try:
                    return self.manager.save_user(request.configuration)
                except (ValueError, OSError) as exc:
                    storage_error(exc)

        @app.get("/api/user-scenarios/{identifier}")
        def get_scenario(identifier: str):
            try:
                return self.manager.get_user(identifier)
            except (ValueError, OSError) as exc:
                storage_error(exc)

        @app.put("/api/user-scenarios/{identifier}")
        def save_scenario(identifier: str, request: SaveScenarioRequest):
            with self.control_lock:
                editable()
                try:
                    return self.manager.save_user(request.configuration, identifier, request.revision)
                except (ValueError, OSError) as exc:
                    storage_error(exc)

        @app.delete("/api/user-scenarios/{identifier}")
        def delete_scenario(identifier: str, revision: str):
            with self.control_lock:
                editable()
                try:
                    self.manager.delete_user(identifier, revision)
                    return {"ok": True}
                except (ValueError, OSError) as exc:
                    storage_error(exc)

        @app.get("/api/scenarios/{identifier}/yaml")
        def export_scenario(identifier: str):
            try:
                if identifier not in self.manager.list() and not self.manager.library.ID.fullmatch(identifier):
                    raise ValueError("Scenario non disponibile")
                import yaml
                configuration = self.manager.load(identifier).model_dump()
                return Response(yaml.safe_dump(configuration, allow_unicode=True, sort_keys=False),
                                media_type="application/yaml",
                                headers={"Content-Disposition": 'attachment; filename="scenario.yaml"'})
            except (ValueError, FileNotFoundError) as exc:
                storage_error(exc)

        @app.get("/api/state")
        def state():
            if self.run:
                return {**self.run.snapshot(), "scenario_id": self.scenario_id}
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
                equivalent = (len(self.comparisons) >= 2 and
                              len({r["fingerprint"] for r in self.comparisons}) == 1 and
                              len({r["mac"] for r in self.comparisons}) == len(self.comparisons))
                changed_fields,changed_sections=differences([r['configuration'] for r in self.comparisons])
                same_experiment=len(self.comparisons)>=2 and len({r['experiment'] for r in self.comparisons})==1
                return {"runs": self.comparisons, "equivalent": equivalent,
                        "same_experiment":same_experiment,"changed_fields":changed_fields,"changed_sections":changed_sections,
                        "note": "Common inputs match; protocol-specific parameters remain in each configuration. Same configured seed and geometry do not imply identical measured trajectories."}

        @app.post("/api/comparison")
        def retain_comparison():
            with self.control_lock:
                if not self.run or self.run.state != "finished" or not self.run.holoocean:
                    raise HTTPException(409, "Complete an integrated run before retaining its summary")
                config = self.run.scenario.model_dump()
                if any(r["run_id"] == self.run.run_id for r in self.comparisons):
                    return {"ok": True}
                mac_config = config['network']['mac']
                mac = mac_config['protocol']
                config['network']['mac'] = {key:mac_config[key] for key in ('ack','buffer_packets','max_tx_tries')}
                config['network'].pop('profile_id',None)
                fingerprint = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
                self.comparisons.append({"run_id": self.run.run_id, "mac": mac, "fingerprint": fingerprint,
                                         "configuration": self.run.scenario.model_dump(),
                                         "experiment":experiment(self.run.scenario.model_dump()),
                                         "versions":self.run.versions,
                                         "observed_trajectory":self.run.trajectory_fingerprint(),
                                         "summary": self.run.summary()})
                self.comparisons = self.comparisons[-6:]
                return {"ok": True}

        @app.post("/api/start")
        def start(request: StartRequest):
            with self.control_lock:
                if self.run and self.run.state in ("starting", "running", "paused", "stopping"):
                    raise HTTPException(409, "A run is already active")
                try:
                    if request.configuration is None and request.scenario not in self.manager.list() and not self.manager.library.ID.fullmatch(request.scenario):
                        raise ValueError("Scenario non disponibile")
                    scenario = Scenario.model_validate(request.configuration) if request.configuration is not None else self.manager.load(request.scenario)
                    if self.run:
                        self.run.close()
                    self.run = ManagedSimulation(scenario, holoocean=not request.standalone, show_viewport=True,
                                                 manage_engine=self.manage_docker)
                    self.scenario_id = request.scenario
                    self.run.annotate('run_selection', scenario_id=request.scenario,
                                      profile_id=scenario.network.profile_id)
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
                return Response(self.run.export_bytes(), media_type="application/zip",
                                headers={"Content-Disposition": 'attachment; filename="holo-desert-results.zip"'})

        return app
