# Documentation

HoloOcean–DESERT couples HoloOcean 2.3 vehicles with the DESERT Underwater 4.0 /
NS-MIRACLE network simulator running in Docker. HoloOcean computes vehicle
physics; DESERT takes every network decision.

| Document | Content |
|---|---|
| [installation.md](installation.md) | Requirements, installation on Windows and Ubuntu 24.04, engine image, ports, directories, `doctor`, updates |
| [api.md](api.md) | Public Python API: `NetworkSession`, `HoloOceanLink`, `ManagedSimulation` |
| [capabilities.md](capabilities.md) | Verified capabilities, their status and limitations |
| [project-status.md](project-status.md) | Release status, decisions, verification results and open items |
| [stack-configuration.md](stack-configuration.md) | Scenario YAML format and network stack: MAC, routing (static, Flooding, SUN, Position-Based), PHY, WOSS, optical/EM, acoustic/optical multi-PHY (controller power units), ranging (TokenBus, TDMA), native applications, power events, non-integrated modules |
| [telemetry-and-reproducibility.md](telemetry-and-reproducibility.md) | Events, metric definitions, time quantities, exports, provenance, reproducing E01–E06 |
| [reproducibility.md](reproducibility.md) | Pinned versions, step-by-step reproduction, what each run records, citation (`CITATION.cff`) |
| [dashboard.md](dashboard.md) | Web dashboard, Network Designer (media, WOSS, acoustic/optical multi-PHY, Position-Based Routing, native generators), interface and ranging views, personal scenarios, communication profiles |
| [developer-guide.md](developer-guide.md) | Architecture, bridge protocol, tests, adding a DESERT adapter |
| [troubleshooting.md](troubleshooting.md) | Known problems on Windows and Linux and their fixes |
| [limitations.md](limitations.md) | Modelling and verification boundaries |
| [evidence/](evidence/README.md) | Dated validation records (Italian), kept for provenance |
| [scenarios.md](scenarios.md) | The bundled reference experiments (E01–E06) and demos |

Images used by the documentation are in [images/](images/) and
[assets/](assets/).
