"""The web laboratory is a client of the public library API only."""
import ast
import io
import json
from pathlib import Path
import zipfile

from fastapi.testclient import TestClient

import holo_desert
from holo_desert import ScenarioManager, network_catalog, network_inventory
from holo_desert.dashboard.server import DashboardServer

DASHBOARD = Path(holo_desert.__file__).parent / 'dashboard'


def test_dashboard_imports_nothing_but_the_public_api():
    for path in DASHBOARD.glob('*.py'):
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
            if isinstance(node, ast.ImportFrom) and node.level >= 2:
                assert node.module in (None, 'api'), (path.name, node.module)
            modules = ([a.name for a in node.names] if isinstance(node, ast.Import) else
                       [node.module] if isinstance(node, ast.ImportFrom) and not node.level else [])
            assert not [m for m in modules if m and m.startswith('holo_desert.') and m != 'holo_desert.api'], path.name


def test_public_catalogue_and_inventory_are_the_served_documents():
    catalog, inventory = network_catalog(), network_inventory()
    assert {'csma_aloha', 'tdma', 'ranging_tokenbus', 'sun'} <= {m['id'] for m in catalog['modules'] if m['operational']}
    assert inventory['libraries']
    with TestClient(DashboardServer(manage_docker=False).application()) as client:
        assert client.get('/api/network-catalog').json() == catalog
        assert client.get('/api/network-inventory').json() == inventory


class PublicRun:
    """Implements only the ManagedSimulation members the dashboard may use."""
    def __init__(self, run_id, scenario, state='finished', holoocean=True):
        self.run_id, self.scenario, self.state, self.holoocean = run_id, scenario, state, holoocean
        self.error, self.closed = None, False
        self.versions = {'engine': {'engine_fingerprint': 'public-api-fixture'}}

    def summary(self): return {'generated': 1, 'received': 1}
    def trajectory_fingerprint(self): return {'nodes': {}, 'run': self.run_id}
    def snapshot(self): return {'state': self.state, 'run_id': self.run_id, 'configuration': self.scenario.model_dump()}
    def export_bytes(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            archive.writestr('summary.json', json.dumps(self.summary()))
        return buffer.getvalue()
    def close(self): self.closed = True


def test_dashboard_comparison_export_and_reset_use_public_members():
    server = DashboardServer(manage_docker=False)
    with TestClient(server.application()) as client:
        run = server.run = PublicRun('public-1', ScenarioManager().load('e04_congestion'))
        server.scenario_id = 'e04_congestion'
        assert client.get('/api/state').json()['scenario_id'] == 'e04_congestion'
        assert client.post('/api/comparison').status_code == 200
        retained = client.get('/api/comparisons').json()['runs'][0]
        assert retained['versions']['engine']['engine_fingerprint'] == 'public-api-fixture'
        assert retained['observed_trajectory'] == {'nodes': {}, 'run': 'public-1'}
        assert zipfile.ZipFile(io.BytesIO(client.get('/api/export').content)).namelist() == ['summary.json']
        assert client.post('/api/reset').status_code == 200 and run.closed
        server.run = PublicRun('standalone', ScenarioManager().load('e01_chat'), holoocean=False)
        assert client.post('/api/comparison').status_code == 409
