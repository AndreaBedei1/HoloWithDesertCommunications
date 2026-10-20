# DESERT Laboratory Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development for isolated PHY and UI tasks; parent implements dependent schema/builder and validation. Track completed work here to avoid repeating it.

**Goal:** laboratorio configurabile con soli moduli DESERT reali e verificati.
**Architecture:** catalogo centralizzato, adapter tipizzati e builder Tcl whitelist;
server valido anche su TCP diretto, frontend guidato e profili persistenti.
**Tech Stack:** Python/Pydantic/FastAPI, Tcl/C++ NS-MIRACLE/DESERT4, JS nativo.
**Spec:** ../specs/2026-10-20-desert-laboratory-design.md

## Global constraints

HoloOcean gestisce tutta la fisica. DESERT gestisce tutta la rete. E01–E06
invariati; default storici riproducibili. No input Tcl arbitrario. No nuove
dipendenze runtime se schema/librerie esistenti bastano. Nessun push/merge.

## Review focus

Reject JSON diretto che aggira Pydantic; override che cambiano altri nodi;
ritrasmissioni e pacchetti controllo senza envelope; slot incompatibili con
durata/propagazione; rischi PER e classificazione corretta con I=0 e I>0.

## Tasks

- [x] A: inventario reale container, default, classi e campioni ufficiali; matrice
  e motivazioni. Esaminare baseline e test esistenti prima delle estensioni.
- [x] B/C: test inizialmente fallenti per nuovi schema/builder e input ostili;
  adapter TDMA, poi MAC compatibili e Flooding con prova nativa; riutilizzare
  le procedure dei campioni ufficiali, non solo cambiare classe.
- [x] D: estensione PHY separata, test analitici e native errori isolati/
  interferenti; parametri effettivi per istanza e telemetria. Preservare
  upstream, build separabile e ID patch nei run.
- [x] B: modelli traffico tipizzati e riproducibili (periodico/variabile,
  Poisson, burst, eventi espliciti), senza simulazione rete Python.
- [x] E/F/G: valutare dipendenze native e dati; implementare combinazioni
  realmente dimostrabili, classificare precisamente le altre nel catalogo.
- [x] H: profili CRUD con revisioni/import/export, catalogo API e Designer,
  selettori dipendenti, spiegazioni centralizzate e confronto generalizzato.
- [x] H: prove integrate e browser per nuovi adapter, arresto/reset/riavvio;
  regressioni originali; ispezione screenshot 1920/1440/finestra ridotta;
  report tecnico, README e commit locali.

## Execution ledger

Ruling: lavorare nella directory esistente su ramo locale `feat/desert-laboratory`
per preservare installazione/launcher e rendere immediatamente verificabile
il risultato; nessun nuovo worktree richiesto per lo stesso ambiente portabile.
Ruling: il mandato esplicito «procedi direttamente» sostituisce le conferme
intermedie di spec/piano. Dipendenze non verificabili bloccano solo il modulo.

Execution complete: real native stack matrix, integrated HoloOcean tests, original E01-E06 regression, six actual browser-driven MAC runs, profile API/browser tests and responsive screenshots. Phases E-G completed as installation audit and explicit integration gates; WOSS, optical/EM, multi-PHY and ranging are not implemented. No full DESERT4 support claimed. Windows IPC startup race and rerun configuration bug reproduced, isolated and fixed with regression checks.
