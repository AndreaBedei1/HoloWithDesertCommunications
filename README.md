# HoloOcean-DESERT

Laboratorio di co-simulazione per flotte subacquee, senza ROS.
**HoloOcean 2.3.0** gestisce veicoli, fisica e sensori; **DESERT Underwater 4.0.0**
gestisce propagazione, interferenza, MAC e routing dei pacchetti acustici.
La dashboard locale mostra flotta, ricezioni, pacchetti e metriche osservate.

Il motore DESERT gira in Docker. HoloOcean resta sull'host con accesso alla GPU.
Su Windows non è richiesta una distribuzione Ubuntu personale: si usa Docker
Desktop con il suo normale backend per container Linux.

Verificati: chat end-to-end, sei demo eseguite, due MAC e 31 test superati.
Numeri, esperimenti di controllo e confini della verifica: [validazione](docs/validation.md).

## Avvio Windows

Da questa directory, con Python 3.10 e Docker Desktop Linux containers:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup.ps1 -HoloOceanClient "<HoloOcean-2.3.0>\client"
.venv\Scripts\holo-desert.exe doctor
.venv\Scripts\holo-desert.exe run e01_chat
```

Ocean 2.3.0 deve essere già installato nel percorso ufficiale HoloOcean.
Aprire **http://127.0.0.1:8000**. Il primo avvio scarica l'immagine DESERT
e compila l'estensione; non servono terminali separati per motore e dashboard.

## Avvio Ubuntu 24.04

Con Docker Engine/Compose, Python 3.12, Git e rendering GPU configurati:

```bash
bash scripts/setup.sh
.venv/bin/python scripts/install_holoocean.py
.venv/bin/python -c 'import holoocean; holoocean.install("Ocean")'
.venv/bin/holo-desert doctor
.venv/bin/holo-desert run e01_chat
```

Dettagli, client locale alternativo e troubleshooting: [installazione](docs/installation.md).
La matrice delle prove realmente eseguite è in [validazione](docs/validation.md).

## Uso

```text
holo-desert examples
holo-desert run e01_chat
holo-desert run e02_multi_node
holo-desert run e03_mobility
holo-desert run e04_congestion --mac aloha
holo-desert run e05_multihop
holo-desert run e06_coordination
holo-desert dashboard
holo-desert run e01_chat --standalone
holo-desert official-sample
holo-desert test
holo-desert test --integration
holo-desert test --end-to-end
```

Senza ambiente attivato, anteporre `.venv/bin/` su Linux o `.venv\Scripts\`
su Windows. `--no-dashboard` esegue un esperimento e restituisce conteggi ed
esito; `--fast` rimuove il pacing reale mantenendo gli orologi sincronizzati.

I risultati ordinari sono temporanei. Il pulsante **Export** scarica ZIP con
JSONL, CSV e configurazione; `--persist results/nome-esperimento` abilita il
salvataggio esplicito. I messaggi in volo restano pending fino al proprio TTL.
I timeout non vengono automaticamente attribuiti a collisioni o rumore.

## Esperimenti e sviluppo

Gli scenari sono YAML sotto `src/holo_desert/resources/examples/`, i profili
MAC sotto `resources/profiles/`, Tcl e C++ sotto `resources/desert/`.
Gli studenti lavorano tramite `CommunicationManager`, senza accedere a Tcl:

```python
drone_a.send(destination="auv_02", payload={"message": "hello"})
messages = drone_b.receive()
```

Ogni applicazione vede solo il proprio stato e messaggi consegnati. I waypoint
sono target del controller HoloOcean; le posizioni del canale provengono sempre
dai sensori, mai dai target desiderati.

- [Architettura e sincronizzazione](docs/architecture.md)
- [Interfacce DESERT e estensione](docs/desert-integration.md)
- [API comunicazione](docs/communication-api.md)
- [Protocolli e parametri](docs/protocols.md)
- [Sei dimostrazioni](docs/scenarios.md)
- [Guida sviluppatori](docs/developer-guide.md)
- [Limitazioni](docs/limitations.md)
- [Dipendenze esterne](dependencies.lock.json)

HoloOcean e DESERT sono distribuzioni esterne con le rispettive licenze.
Questo repository non include binary Ocean, copie DESERT, immagini Docker o venv.
