# Sviluppo

Python 3.10–3.12, package layout `src`, installazione `pip install -e '.[test]'`.
Avviare `holo-desert test` per i test senza motori. `holo-desert test --integration`
richiede Docker e compila l'estensione contro i veri header DESERT.
`holo-desert test --end-to-end` richiede inoltre HoloOcean/Ocean/GPU.
I marker pytest impediscono di confondere test unitari con prove reali.

## Nuovo scenario

1. Copiare `resources/examples/e01_chat/scenario.yaml` in un nuovo percorso.
2. Cambiare nodi, posizioni, flussi e `network`, rispettando lo schema Pydantic.
3. Eseguire `holo-desert run percorso/scenario.yaml`.
4. Per aggiungerlo al menu, inserirlo sotto `resources/examples/<id>/scenario.yaml`.

Gli ID `auv_NN` vengono mappati stabilmente agli indirizzi DESERT 1..N nell'ordine
del file. Le route usano nomi, convertiti in indirizzi solo dall'adattatore.

## Nuova applicazione / nuovo backend

Le applicazioni in `core/applications.py` ricevono tempo, posa propria e messaggi
effettivamente consegnati. Non passare loro l'adattatore fisico o il collector.
Un backend deve implementare `CommunicationBackend` e riportare tempi simulati
autentici. La CLI iniziale ammette solo il backend DESERT; non esiste un fallback
che simuli consegne in Python.

L'orchestratore accetta `application_factory(node, communication, scenario)`
per costruire applicazioni personalizzate senza cambiare il suo ciclo:

```python
from holo_desert.core.orchestrator import SimulationOrchestrator
from holo_desert.scenarios.config import ScenarioManager

class DepthReporter:
    def __init__(self, comm, peer):
        self.comm, self.peer, self.next_send = comm, peer, 1.0

    def update(self, now, own_pose, received):
        if now >= self.next_send:
            self.comm.send(self.peer, {"depth_m": -own_pose.z}, ttl=8)
            self.next_send = now + 3
        return None

scenario = ScenarioManager().load("e01_chat")
def factory(node, comm, configuration):
    peer = next(n.id for n in configuration.nodes if n.id != node.id)
    return DepthReporter(comm, peer)

run = SimulationOrchestrator(scenario, application_factory=factory)
try:
    run.run()
finally:
    run.close()
```

La factory riceve configurazione statica per il wiring; l'applicazione conserva
solo il proprio handle e i parametri necessari. `update` non riceve backend,
collector o ground truth altrui. Un eventuale `snapshot(now)` restituisce
metadati locali leggibili dalla dashboard; non deve mutare stato applicativo.
Il limite dell'envelope è passato al CommunicationManager come configurazione
generica: gli algoritmi non consultano più proprietà dell'adattatore DESERT.

## Profili di rete e veicoli

Un profilo YAML è validato da `Network`. Copiare un profilo esistente e
modificare solo parametri realmente collegati alle proprietà Tcl documentate.
La CLI `--profile` sostituisce tutto `network`; `--mac` e il selettore della
dashboard cambiano soltanto il MAC. Per un protocollo aggiuntivo servono schema
dedicato, mapping esplicito nel server Docker, librerie reali, test di consegna
e compatibilità PHY/ACK/queue. Aggiungere un nome al menu non è un'integrazione.

`Node.vehicle` è opzionale e default `HoveringAUV`: gli YAML precedenti restano
validi. `holoocean_adapter/vehicles.py` isola configurazione HoloOcean, decoding
del sensore e conversione dell'azione. Per un veicolo futuro aggiungere un
profilo con `configuration(node)`, `pose(sensors)`, `action(target)` e aggiornare
lo schema dei valori ammessi. Non occorre cambiare l'orchestratore. Verificare
unità, orientamento, frame, sensori e controller con il vero nuovo veicolo.
Al momento viene accettato soltanto HoveringAUV; nessun modello aggiuntivo è
stato introdotto o dichiarato verificato.

## Estensione DESERT

`resources/desert/extensions/bridge.cc` deriva dall'applicazione ufficiale.
Non cambia i sorgenti upstream. `build-extension.sh` trova gli include dentro
l'immagine fissata; `Dockerfile` compila solo la libreria aggiunta.
`server.py` non trasporta pacchetti tra veicoli: collega il client al processo
NS di una sessione. Il canale simulato è l'unico percorso tra applicazioni.

Per ispezionare gli eventi usare il Packet Inspector e l'esportazione ZIP.
Il trace applicativo contiene ID, header applicativi e UID NS. I UID NS non
sono univoci globalmente tra sorgenti: correlare sempre con l'ID applicativo.

Le risorse devono restare dati distribuibili del package. Verificare anche
`pip wheel . --no-deps` e il contenuto del wheel prima di una release.
Non aggiungere binary Ocean, copie DESERT, output generati o venv al repository.

Le prove qualitative riproducibili sono `scripts/validate_channel.py` (solo
rete reale DESERT) e `scripts/validate_examples.py` (droni HoloOcean reali).
Richiedono prima `holo-desert engine up`. `--output` salva solo un riepilogo
compatto esplicito; i log delle esecuzioni rimangono temporanei.
Per il confronto controllato: `python scripts/validate_examples.py e04_congestion --mac aloha`.

Per verificare lo stesso percorso HTTP dell'interfaccia: avviare la dashboard
inattiva, poi `python scripts/validate_dashboard.py`. Esegue solo E03, le due
varianti MAC di E04, E05 ed E06, in sequenza. Controlla pausa, reset, identità
dei next hop, eventi/ZIP e confronto; non è una prova del rendering browser.
`--output file.json` è l'unico salvataggio esplicito. Non eseguirlo mentre altre
simulazioni usano il servizio DESERT.

## Libreria personale e test del browser

`ScenarioManager` mantiene `list()` limitato ai sei esempi; `list_user()`,
`get_user()`, `save_user()` e `delete_user()` delegano a `ScenarioLibrary`.
La directory si configura con `HOLO_DESERT_SCENARIOS_DIR` oppure `user_root`
nel gestore. Non salvare configurazioni nel package. `load()` continua ad
accettare percorsi YAML della CLI e accetta gli ID personali `user_…`.

Gli endpoint `/api/user-scenarios` gestiscono la libreria; PUT e DELETE
richiedono la revisione corrente. Una revisione obsoleta o un nome duplicato
produce 409. `/api/user-scenarios/import` valida una bozza senza salvarla;
`/api/scenarios/{id}/yaml` esporta lo schema esistente. Le modifiche sono
bloccate durante starting/running/paused/stopping sotto lo stesso lock dei
controlli della simulazione. L'API HTTP non accetta percorsi arbitrari.
La CLI conserva invece il suo accesso esplicito ai file YAML locali.

I test browser sono in `tests/frontend`: `npm ci`, quindi `npm test`.
Richiedono Edge su Windows o `npx playwright install --with-deps chromium`
su Linux. Il server di test usa porta 8011 e libreria `.local/ui-test-library`:
non puntarlo alla libreria personale reale. Le fixture di presentazione
intercettano le richieste solo nel browser e mostrano una fascia esplicita;
non provano fisica o rete. La prova reale e gli screenshot ispezionati sono
descritti in [ui-review.md](ui-review.md).
