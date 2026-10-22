# Laboratory completion implementation plan

> **For agentic workers:** Use superpowers:subagent-driven-development for independent probes and reviews; execute dependent shared-stack changes inline. Steps use checkboxes for tracking.

**Goal:** Extend the existing laboratory with native DESERT capabilities demonstrated by real packets, while preserving historical experiments.

**Architecture:** Keep the typed scenario, shared whitelist Stack Builder, Tcl adapters, observational C++ bridge and existing dashboard. Extend these boundaries together for each supported capability. Installed modules remain unavailable until their complete chain is verified.

**Tech Stack:** Python/Pydantic, JavaScript/Playwright, Tcl/C++, pinned DESERT/NS-MIRACLE Docker image, host HoloOcean 2.3.

**Spec:** User attachment `f6b397ab-fab4-49e7-983e-1c4a3661d6fa/Pasted text.txt`, phases 0–18; authoritative requirements retained in the conversation.

## Global constraints

- Work on `feat/desert-laboratory`; no push, merge or changes to main.
- Preserve original E01–E06 YAML and upstream BPSK behavior.
- No Python substitute for DESERT propagation, MAC, routing or ranging.
- Use temporary isolated native processes and compact evidence; never interrupt an existing user run.
- One synchronized simulation timeline; effective settings and model identities must be observable.
- No arbitrary Tcl or user-controlled lookup paths through the dashboard.
- Enabled UI controls must bind real native parameters with correct units, constraints and help.

## Review focus

- Constructor-dependent settings must take effect, with explicit historical compatibility.
- Loader success alone does not prove a usable protocol; verify actual data and native control traffic.
- Geographic and transducer coordinate transforms must preserve native geometry and measured movement.
- Native applications, broadcast recipients and retransmissions must not inflate application denominators.
- Stop/restart, invalid configurations and incompatible stacks must fail cleanly without process leaks.

## Tasks

- [ ] **0. CI editor:** reproduce Ubuntu failure using Docker, identify blocked operation, fix root cause and robust selectors; run whole frontend suite and Python CI equivalent. Files: `tests/frontend`, editor JS if necessary, `.github/workflows/tests.yml` for retained failure evidence.
- [ ] **1. Parameter audit:** trace catalog → typed model → builder → Tcl → compiled bindings; correct ineffective options with explicit legacy mode. Add focused host/native/UI checks.
- [ ] **2. Native protocols:** probe installed additional MAC/routing/ranging examples and dependencies in isolated processes; implement verified adapters, roles, typed parameters and stats; reject unverified combinations.
- [ ] **3. Environmental and alternative PHY:** run installed no-database WOSS/Bellhop and optical/EM examples; implement complete viable chains with native units, geometry, movement and provenance. Document exact blockers for the remaining chains.
- [ ] **4. Applications/interfaces:** integrate native applications and true broadcast where supported; extend per-interface configuration and native controllers only with real interface events and honest denominators.
- [ ] **5. UI and comparisons:** extend existing conditional Designer and centralized help, effective-config inspection and comparisons of arbitrary communication configurations; save/export/reload tests and desktop/reduced screenshots inspected visually.
- [ ] **6. Validation and deliverables:** targeted real native and HoloOcean tests, stop/restart, six original regressions; independent review, packaging checks, compact final report and few verified demos; local commits by functional group.

## Execution ledger

- Baseline: clean `feat/desert-laboratory`, commit `4b27cc8`; remote run `39475450557` has passing Python jobs and one frontend timeout. No remote failure artifacts were uploaded.
- Ruling: work in the existing requested branch/workspace, preserve existing local services and serialize shared-source changes — the user explicitly requested continuation, not a new checkout.
- Ruling: the user authorizes autonomous implementation; design/plan confirmation gates do not require another permission request. Add functionality only after a concrete native proof; precise failed probes remain useful evidence.
- CI implementer owns frontend tests/editor and workflow; environmental and protocol auditors initially use read-only source access and isolated temporary probes.
