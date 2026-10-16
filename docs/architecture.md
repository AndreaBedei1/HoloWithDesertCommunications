# Architettura

HoloOcean 2.3.0 esegue fisica, sensori, collisioni e controllo PD dei veicoli.
DESERT 4.0.0 esegue l'intero stack acustico. Python non calcola consegne,
perdite, interferenze o tempi di propagazione.

```text
HoloOcean host <-> HoloOceanAdapter
                         |
                SimulationOrchestrator <-> CommunicationManager <-> applicazioni locali
                         |
                    DESERTAdapter (TCP framed)
                         |
                 container Docker / server.py
                         |
                NS-MIRACLE / bridge.tcl / libholobridge
                         |
 APPLICATION -> UDP -> StaticRouting -> IP -> Probe -> MLL -> MAC -> BPSK/Underwater
                         |
             UnderwaterChannel + Underwater propagation + MIV interference
```

Gli eventi alimentano `TelemetryCollector` e le quattro viste di `DashboardServer`.
La dashboard legge snapshot HTTP ogni 500 ms, senza server frontend separato.
Gli algoritmi ricevono unicamente la propria `Pose` e il proprio oggetto
`DroneCommunication`; la ground truth della flotta rimane nell'orchestratore.

## Timeline e barriera

`ClockSynchronizer` usa tick interi: `t = tick / physics_hz`. NS utilizza il
proprio scheduler a eventi, fermo all'interno della callback Tcl `barrier`.
La callback legge comandi dal trasporto, aggiorna `Position/BM`, inserisce
pacchetti nello stack e programma la successiva barriera. Restituisce quindi
il controllo allo scheduler originale, che esegue **tutti** gli eventi interni
fino alla barriera. Nessun reset dello scheduler o sostituzione dei ritardi.

A ogni iterazione:

1. Posizioni misurate HoloOcean a `t_k` inviate a DESERT con timestamp `t_k`.
2. Comandi applicativi generati a `t_k`, poi inseriti nello stack DESERT.
3. HoloOcean esegue un tick fisico fino a `t_(k+1)`.
4. DESERT avanza fino a `t_(k+1)`; gli eventi conservano il loro timestamp NS.
5. L'applicazione riceve solo eventi con tempo <= tempo fisico corrente.

Geometria mantenuta costante nell'intervallo di un tick: aggiornamento causale
a campionamento sinistro. Gli eventi NS già programmati esattamente sulla
barriera vengono processati prima del successivo campione spaziale. Nessuna
interpolazione fisica in Python o DESERT. Le applicazioni reagiscono entro un
tick dalla ricezione; la latenza riportata resta quella NS, non il tempo di polling.

Il tempo reale serve solo per pacing e misura della deriva. `--fast` elimina
il pacing, mantenendo la stessa timeline logica. La pausa ferma entrambi i
motori su una barriera; non esiste una modalità in cui avanza solo DESERT.
L'arresto termina il processo NS di proprietà della sessione e il mondo HoloOcean.
Il reset crea una nuova sessione con tempo zero e nuove code.

## Coordinate

`DynamicsSensor` con `UseCOM=true` fornisce metri nel riferimento HoloOcean:
X avanti, Y sinistra, Z alto. DESERT usa coordinate cartesiane in metri con
Z negativo sotto la superficie. `CoordinateConverter` applica esplicitamente
questa identità, con eventuale traslazione comune dell'origine.
Non usa centimetri Unreal né l'orientamento NED del socket IMU.

## Posizione dei file

I moduli Python sono sotto `src/holo_desert/`, separati per responsabilità.
Le risorse distribuibili sono sotto `src/holo_desert/resources/`: `desert/`,
`docker/`, `profiles/`, `examples/`. Questa scelta include tutti gli scenari,
Tcl e file Docker anche nel wheel, senza percorsi del computer di sviluppo.
I test finti risiedono esclusivamente in `tests/unit`; nessun mock è selezionabile
dalla CLI.
