# Dimostrazioni

Comando comune: `holo-desert run <id>`. La dashboard apre il servizio locale
su http://127.0.0.1:8000; il mondo 3D è quello ufficiale HoloOcean.
I file YAML sono sotto `src/holo_desert/resources/examples/<id>/scenario.yaml`.

| ID | Cosa esegue | Evidenza da controllare |
|---|---|---|
| `e01_chat` | Richiesta e risposta, due veicoli fermi | `app_tx`, `rx`, `delivered` con stesso ID; timestamp e payload |
| `e02_multi_node` | Quattro sorgenti simultanee | Offerta, ricezioni, code MAC; nessuna collisione dedotta da timeout |
| `e03_mobility` | Due controller PD seguono target che si allontanano e tornano | Posizioni misurate, `position_applied`, distanza e PDR |
| `e04_congestion` | Tre flussi verso un sink, intervalli decrescenti | Code reali MAC, throughput e timeout distinti dagli errori bridge |
| `e05_multihop` | Route statiche A-B-C | Inoltro osservato su B e ricezione su C; controllo diretto a 1000 m verificato separatamente |
| `e06_coordination` | Heartbeat e follower con stati HOLD/PROCEED | Potenza PHY ridotta a 0 dB da 8 a 18 s; stati e ripresa dopo RX |

`e01`, `e02`, `e04`, `e05` possono usare `--standalone`: fixture spaziali fisse,
motore DESERT reale, nessun veicolo simulato da Python. Le demo mobili e la
coordinazione rifiutano questa modalità.

Per il confronto MAC:

```bash
holo-desert run e04_congestion
holo-desert run e04_congestion --mac aloha
```

I parametri di `e03` e `e05` sono specifici del modello e del seed:
un relay configurato non dimostra da solo l'impossibilità della ricezione diretta.
Per E05 il controllo è stato eseguito: a 132 dB SPL, due tratte da 500 m
consegnano tramite B, mentre la tratta diretta da 1000 m non consegna il payload.
La dashboard chiama gli archi “ricezioni applicative end-to-end” e non li
presenta come hop fisici. Il dettaglio del pacchetto elenca le osservazioni
di inoltro realmente prodotte nello stack.

La coordinazione non è un sistema di safety: è un esempio didattico di reazione
alla freschezza dei messaggi. L'interruzione avviene nel modello di potenza DESERT,
mai eliminando messaggi arbitrariamente nell'applicazione.

Consultare [evidence/validation.md](evidence/validation.md) per distinguere configurazioni
implementate da dimostrazioni effettivamente eseguite e verificate.
