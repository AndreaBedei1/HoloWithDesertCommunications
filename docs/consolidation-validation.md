# Consolidamento: prove del 16 ottobre 2026

Questo documento aggiunge nuove verifiche. [La validazione precedente](validation.md)
e i sei YAML originali non sono stati modificati. Nessun nuovo scenario,
algoritmo di rete Python o protocollo non verificato è stato introdotto.

## Riferimento iniziale

Repository pulito al commit `cfa553c`; letti architettura, documentazione,
scenari, eventi C++/Tcl e frontend. Comando iniziale:

```powershell
.venv\Scripts\python.exe -m pytest -q -m 'desert or not desert'
```

31 test superati in 53,46 s: 20 unitari, 9 DESERT, 2 end-to-end HoloOcean.
E03, E04 CSMA, E05 ed E06 rieseguiti tramite `validate_examples.py` prima del
cambio dell'estensione; conteggi uguali alle evidenze precedenti. E02 mantiene
le evidenze precedenti (24 generati, 11 ricevuti), senza ripetere la campagna.

## Verifica del percorso dashboard

DESERT ricompilato dal digest ufficiale con estensione aggiornata; build C++
riuscito. HoloOcean 2.3.0/Ocean su Windows nativo, Python 3.10.20, GPU NVIDIA
RTX 6000 Ada, Docker Desktop Linux containers (Engine 29.8.2, Compose 5.6.0).
Nessuna distribuzione WSL personale, modifica a driver o daemon.

Server locale FastAPI e `scripts/validate_dashboard.py`, cinque corse sequenziali
sullo stesso servizio DESERT: E03, E04 CSMA, E04 ALOHA, E05, E06. Rimosso solo il
pacing reale per la prova (`realtime=false`), senza cambiare durata logica,
potenza, flussi o buffer. Viewport HoloOcean abilitato dal percorso standard
dashboard; non è stato possibile ispezionarne visivamente il contenuto.

| Scenario | Generati | Consegnati | TTL scaduti | Evidenza |
|---|---:|---:|---:|---|
| E01 Chat | 2 | 2 | 0 | Test E2E reale mantenuto |
| E02 Multi-node | 24 | 11 | 13 | Evidenza precedente riutilizzata |
| E03 Mobility | 45 | 22 | 23 | Distanza circa 20→77→20 m; pausa/ripresa HTTP |
| E04 CSMA-ALOHA | 84 | 23 | 61 | Buffer campionato fino a 20 |
| E04 ALOHA | 84 | 0 | 84 | Risultato negativo conservato |
| E05 Multi-hop | 3 | 3 | 0 | PHY TX A→B e B→C; inoltro sotto IP su B |
| E06 Coordination | 29 | 19 | 10 | HOLD/PROCEED guidati da heartbeat reali |

Tutte le cinque corse HTTP: stato finale `finished`, servizi `stopped`, nessun
`cleanup_error`/`run_error`, posizioni per tutti i nodi, next hop risolti da MAC
reali, consegne nel JSONL uguali ai contatori dashboard, ZIP leggibile, reset
a idle e nuovo avvio successivo. Pausa E03: tempo dashboard fermo per 150 ms
reali; il test E2E verifica anche il contatore tick fisico e il clock DESERT.

Massimo tempo di risposta HTTP `/api/state` misurato dal client: E03 0,250 s,
E04 CSMA 0,110 s, E04 ALOHA 0,141 s, E05 0,078 s, E06 0,062 s. Non è una misura
del frame rate browser. Serie finali: rispettivamente 200, 90, 90, 60, 60
campioni. Le due configurazioni E04 hanno lo stesso fingerprint escludendo
solo il protocollo MAC; il confronto sopravvive ai reset e resta limitato a
due riepiloghi in memoria.

| Metrica E04 | CSMA-ALOHA | ALOHA |
|---|---:|---:|
| PDR risolti | 0,27381 | 0 |
| Goodput medio su 45 s [bit/s] | 1046,756 | 0 |
| Throughput envelope medio [bit/s] | 2126,222 | 0 |
| Latenza media consegnati [s] | 5,49942 | N/D |
| Errori PHY interferenza [osservazioni] | 8 | 28 |
| PHY non sincronizzati [osservazioni] | 16 | 224 |
| Picco coda MAC campionato [pacchetti] | 20 | 7 |

E06: potenza leader portata a 0 dB SPL a 8 s e ripristinata a 135 dB SPL a
18 s da DESERT. Follower HOLD iniziale, PROCEED a 1,8667 s, HOLD a 10,4667 s,
PROCEED a 18,6 s; distanza finale 46,43 m. La freschezza usa l'arrivo del
messaggio, non la sua generazione o il polling HTTP.

## Confini della verifica visiva

Browser integrato: nessuna istanza disponibile (`listBrowsers → []`). Skill
Computer Use inizializzata e finestre inventariate; tentativo di aprire Edge
installato fallito con `GetCursorPos failed: Accesso negato (0x80070005)`.
Nuovo inventario: nessuna finestra browser. Non sono stati aggirati permessi
o modificati profili browser.

Il controllo dei file statici ha scoperto che il registro MIME Windows
restituiva `text/plain` per `.js`, incompatibile con i moduli ES. Corretto con
Content-Type esplicito nell'applicazione, senza toccare il registro; tutti i
sei moduli sono ora verificati via HTTP come `text/javascript` e il CSS come
`text/css`. Un test forza una mappatura MIME errata per coprire la regressione.
Verificati via HTTP i file statici e le API; tutti i moduli JavaScript passano
`node --check`. **Layout, canvas nel browser, zoom/pan, interazioni del modulo,
ridimensionamento e rendering 3D sullo schermo non sono verificati visivamente**.
Il loro codice è implementato, ma l'audit HTTP non sostituisce una prova UI.
Prima di una consegna didattica verificare in browser Fleet/Topology/Inspector/
Metrics con E03–E06, configurazione route/flussi e larghezze 1440/1024/390 px.

## Test e installazione

Le nuove prove coprono route cicliche/self hop, compatibilità dei sei YAML,
serie distanze/code con N/D, snapshot indipendenti, identità dei next hop,
assenza di consegne premature, limiti di memoria, età heartbeat, stato finale
solo dopo cleanup, applicazioni senza proprietà DESERT, confronto equivalente
e non equivalente, reset e conflitto porta prima dell'avvio. I test DESERT
aggiunti verificano entrambi i MAC con ACK e indirizzi effettivi negli header.
Rimane il controllo multi-hop 500+500 m contro diretto 1.000 m senza consegna.

`pip check` host superato; `doctor` interamente OK, comprese porte possedute,
versioni e health TCP. I log e i riepiloghi della prova sono temporanei o
esplicitamente salvati sotto `.local/` ignorata da Git, non risultati versionati.

La prima verifica su un nuovo `ubuntu:24.04` ha rilevato l'assenza di gcc per
compilare `posix_ipc`. Corretto `check_linux_package.sh` aggiungendo
`build-essential` ai soli prerequisiti del container usa e getta. Lo script
mantiene il vincolo `/.dockerenv` e il mount del progetto in sola lettura.
La seconda verifica ha completato installazione e `pip check`, ma identificato
una dipendenza accidentale del nuovo test di teardown dai metadati HoloOcean:
il test usa fisica iniettata, quindi deve dichiararsi standalone. Corretto il
test senza aggiungere HoloOcean alla CI unitaria; avviata una nuova verifica
pulita dopo la correzione.

Suite Windows definitiva: **41 test superati in 60,30 s**, suddivisi in 28
unitari, 11 DESERT e 2 E2E HoloOcean. I 15 warning riguardano deprecazioni delle
dipendenze già presenti, non errori della co-simulazione. Wheel costruito e
contenuto verificato: 8 risorse frontend, profili veicolo e 6 scenari originali.
Nessuna nuova dipendenza runtime. Prova Ubuntu 24.04 pulita finale conclusa
con exit code 0: compilazione `posix_ipc` riuscita, installazione del lock e
del progetto riuscita, `pip check` senza errori, **28 test unitari superati
in 1,54 s** con Python 3.12; 13 test dei motori esclusi esplicitamente.
Container di prova rimosso automaticamente dopo la conclusione. Il progetto
host era montato in sola lettura; venv e compilazioni erano in `/tmp` interno.

Wheel finale `holoocean_desert-0.1.0-py3-none-any.whl`, SHA256
`be5b98bbf98a50823d4b81f98a786b06b3d11481330c6e02d6d20b96fbc5638f`.
Controllati anche ID HTML univoci e riferimenti letterali dei moduli ai campi.
Server usato per QA chiuso in stato idle; porta 8000 libera per il normale
comando `holo-desert dashboard`. Il servizio DESERT preesistente resta sano
e inattivo, riutilizzabile dal prossimo esperimento.

Non è disponibile un host Ubuntu con GPU: rendering e co-simulazione HoloOcean
nativa su Linux non sono certificati. La CI GitHub resta basata su Ubuntu
24.04/Python 3.10 e 3.12, test unitari senza motori; non è stata eseguita su
GitHub durante questa sessione. Non sono stati effettuati push o merge.
