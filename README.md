# HoloOcean DESERT

Simula e analizza le comunicazioni tra droni subacquei.
HoloOcean gestisce movimento, fisica e sensori; DESERT gestisce il canale
acustico e la rete. La dashboard permette di scegliere un esempio, creare
un proprio scenario e osservare messaggi e risultati.

## Apri il laboratorio

Con il progetto già installato, da questa directory:

```powershell
.venv\Scripts\holo-desert.exe dashboard
```

Apri **http://127.0.0.1:8000**. Su Linux il comando è
`.venv/bin/holo-desert dashboard`.

1. **Scegli uno scenario.** La scheda spiega cosa succede e cosa osservare.
2. **Avvia simulazione.** HoloOcean e DESERT si inizializzano automaticamente.
3. **Esplora la mappa.** Seleziona un drone; usa rotella e trascinamento per
   cambiare inquadratura. Le posizioni sono quelle misurate da HoloOcean.
4. **Segui i messaggi.** Seleziona una comunicazione per vedere il percorso e
   la timeline. Una trasmissione osservata non è ancora una consegna.
5. **Approfondisci in Analisi.** Le icone informative spiegano le metriche.
6. **Apri Impostazioni** per regolare MAC, bitrate, potenza e parametri avanzati
   prima della prossima corsa.
7. **Esporta risultati** per scaricare configurazione, eventi e pacchetti in ZIP.

I risultati delle corse ordinarie sono temporanei: esportali prima del reset
o della chiusura. Gli scenari personali, invece, vengono conservati.

## Crea il tuo scenario

In **I miei scenari**, premi **Nuovo scenario**, oppure **Duplica** su un esempio.
L'editor guida attraverso cinque passaggi: generale, droni e movimento,
comunicazioni, rete acustica, riepilogo e avvio.

Puoi aggiungere droni, trascinare le posizioni iniziali nella mappa, impostare
waypoint, flussi di messaggi e route statiche con relay. Dopo **Salva scenario**
lo ritrovi nella libreria e puoi avviarlo subito. Importazione ed esportazione
YAML restano disponibili. I sei esempi sono protetti da modifica e cancellazione.

Gli scenari vengono salvati nella directory dati dell'utente, separata dal
pacchetto. `HOLO_DESERT_SCENARIOS_DIR` permette di scegliere una directory
portabile. [Dettagli di utilizzo e salvataggio](docs/dashboard.md).

## Installazione

Servono Python 3.10–3.12, HoloOcean/Ocean **2.3.0**, GPU adatta al rendering e
Docker con container Linux. HoloOcean rimane sull'host, DESERT gira in Docker;
non serve gestire una distribuzione WSL personale.

Su Windows, con il client HoloOcean già scaricato:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup.ps1 -HoloOceanClient "<HoloOcean-2.3.0>\client"
.venv\Scripts\holo-desert.exe doctor
```

Installazione Ubuntu 24.04, Ocean e prerequisiti: [guida installazione](docs/installation.md).
Il primo avvio può scaricare l'immagine DESERT e compilare l'estensione.

## Gli esempi

| ID | Scenario | Cosa osservare |
|---|---|---|
| E01 | Scambio di messaggi | Richiesta e risposta tra due droni |
| E02 | Comunicazione tra più droni | Quattro droni sullo stesso canale |
| E03 | Droni in movimento | Allontanamento, ritorno, distanza e consegna |
| E04 | Congestione della rete | Code, interferenza e confronto MAC |
| E05 | Comunicazione tramite relay | Due tratte osservate A → B → C |
| E06 | Coordinamento tra droni | Heartbeat, attesa e ripresa del follower |

In **Analisi → Confronto MAC**, conserva due riepiloghi E04 cambiando soltanto
il protocollo tra ALOHA e CSMA-ALOHA. Il controllo segnala configurazioni non
equivalenti e mantiene anche i risultati negativi.

## CLI, test e sviluppo

La CLI continua ad accettare `holo-desert run e03_mobility` e file YAML
personali: `holo-desert run percorso/scenario.yaml`. `--no-dashboard` esegue
senza interfaccia; `--persist directory` salva esplicitamente i risultati.

```powershell
.venv\Scripts\holo-desert.exe test
.venv\Scripts\holo-desert.exe test --integration
.venv\Scripts\holo-desert.exe test --end-to-end
npm.cmd --prefix tests/frontend ci
npm.cmd --prefix tests/frontend test -- --config playwright.config.cjs
```

I test browser richiedono Node e usano Edge installato su Windows. Su Linux:
`cd tests/frontend && npx playwright install --with-deps chromium && npm test`.
I test di presentazione utilizzano fixture dichiarate, separate dai simulatori.

- [Dashboard, metriche e scenari personali](docs/dashboard.md)
- [Guida sviluppatori e applicazioni](docs/developer-guide.md)
- [Architettura](docs/architecture.md) · [API comunicazione](docs/communication-api.md)
- [Protocolli](docs/protocols.md) · [Installazione](docs/installation.md)
- [Revisione visiva e verifiche UI](docs/ui-review.md)
- [Validazione originale](docs/validation.md) · [Consolidamento](docs/consolidation-validation.md)

HoloOcean e DESERT mantengono le rispettive licenze. Binary Ocean, immagini,
venv e risultati delle simulazioni non sono inclusi nel repository.
