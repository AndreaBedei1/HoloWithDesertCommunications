# Installazione

## Distribuzione e dipendenze

Il codice host richiede Python 3.10–3.12, Git, HoloOcean 2.3.0 e il package Ocean
della **stessa versione e piattaforma**. DESERT gira esclusivamente in Docker;
non serve installarlo in una distribuzione WSL né compilare NS sull'host.
Ubuntu 24.04 è il target Linux. Windows nativo usa Docker Desktop in modalità
Linux containers e il binary Ocean Windows.

Su Windows Docker Desktop necessita del proprio backend di virtualizzazione
(WSL2 o Hyper-V, secondo edizione e configurazione). Il progetto non esegue
comandi `wsl` e non dipende da una distribuzione Ubuntu personale. Non può
eliminare il requisito di virtualizzazione di Docker Desktop.

## Windows

In PowerShell, dalla root del repository, con un Python 3.10 installato:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup.ps1 -HoloOceanClient "<cartella-HoloOcean-2.3.0>\client"
.venv\Scripts\holo-desert.exe doctor
.venv\Scripts\holo-desert.exe probe-holo
.venv\Scripts\holo-desert.exe run e01_chat
```

Se il Python non è registrato con `py`, passare `-Python "<percorso-python.exe>"`.
Non serve attivare l'ambiente virtuale. `ExecutionPolicy Bypass` vale soltanto
per quel processo: non modifica la policy di sistema.

## Ubuntu 24.04

Prerequisiti host: Python 3.12 con venv, Git, driver GPU adatti al rendering
HoloOcean, Docker Engine e Compose con accesso al daemon. Per compilare
`posix_ipc` possono servire `build-essential` e `python3-dev`.
I prerequisiti di sistema vanno installati seguendo le istruzioni ufficiali;
gli script del progetto non cambiano gruppi, servizi o policy dell'host.

```bash
bash scripts/setup.sh
.venv/bin/python scripts/install_holoocean.py
# Installare Ocean nel percorso gestito ufficialmente da HoloOcean 2.3.0:
.venv/bin/python -c 'import holoocean; holoocean.install("Ocean")'
.venv/bin/holo-desert doctor
.venv/bin/holo-desert probe-holo
.venv/bin/holo-desert run e01_chat
```

In alternativa, usare un client già scaricato:
`HOLOOCEAN_CLIENT=/percorso/HoloOcean/client bash scripts/setup.sh`.
`scripts/install_holoocean.py` installa un commit fissato oppure lavora su una
copia temporanea del client locale: non modifica il repository sorgente esistente.
Il setup host applica `requirements-lock.txt`, con marker per pywin32/posix_ipc.

## Motore e sviluppo standalone

Il primo `run` compila automaticamente un'immagine derivata dalla distribuzione
ufficiale `uwsignet/desert:4.0.0`. Il download upstream supera 1 GB compresso.
HoloOcean e Unreal rimangono sull'host.

```bash
holo-desert engine up
holo-desert official-sample
holo-desert run e01_chat --standalone
holo-desert engine status
holo-desert logs
holo-desert engine down
```

Un `run` arresta il servizio se lo ha avviato lui; riutilizza senza abbatterlo
un servizio avviato esplicitamente con `engine up`. Ogni connessione possiede
un nuovo processo NS; chiudendola, il processo viene terminato. Una sola
simulazione per servizio; health check e dashboard restano disponibili.
`--no-manage-docker` collega un servizio esistente senza gestirne il ciclo di vita.

TCP DESERT: `127.0.0.1:5555`. Dashboard: `127.0.0.1:8000`.
`DESERT_PORT` cambia la porta host del motore; `--port` quella dashboard.
Non vengono pubblicate porte sulla rete esterna. Nessun volume di risultati
persistenti viene creato da Docker.

## Troubleshooting

- HTTP 500 di Docker prima del pull: verificare `docker version`; provare il
  normale riavvio Docker Desktop. Non è un errore del canale acustico.
- `docker-credential-desktop` assente: aggiungere la directory bin di Docker
  al PATH del terminale. La CLI Python gestisce automaticamente questo caso.
- Timeout del binary HoloOcean: controllare GPU, versione Ocean, ambiente
  grafico e `holo-desert probe-holo`. La presenza di `nvidia-smi` da sola
  non certifica il funzionamento del renderer.
- Porta occupata: `doctor` segnala i conflitti e riconosce il proprio servizio
  DESERT e la propria dashboard già attivi sulle porte default.
- Sessione `failed`: leggere l'errore dashboard ed eseguire `holo-desert logs`.
  Nessuna consegna alternativa in Python viene attivata.
- Il backend richiede Docker Linux amd64. GPU macOS, ARM e rendering WSLg
  non sono certificati da questa implementazione.

Lo stato preciso delle verifiche è in [validation.md](validation.md).
Il setup host Python e i test senza rendering sono stati eseguiti anche in
un container Ubuntu 24.04 pulito tramite `scripts/check_linux_package.sh`.
Questa prova non certifica il rendering GPU HoloOcean nativo su Linux.
