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
