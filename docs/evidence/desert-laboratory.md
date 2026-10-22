# Laboratorio DESERT: implementazione e verifiche

20 ottobre 2026. Estensione del repository esistente, senza modificare i sei
YAML E01–E06. HoloOcean 2.3.0 mantiene fisica, controller e sensori; tutte le
decisioni di rete rimangono in DESERT/NS-MIRACLE. Nessun supporto completo di
DESERT 4.0 viene dichiarato: il catalogo distingue implementazione verificata,
PHY sperimentale e moduli installati non integrati.

## Risultato operativo

| Livello | Utilizzabile |
|---|---|
| MAC | ALOHA, CSMA-ALOHA, TDMA, TDMA Frame, CSMA/CA, DACAP |
| Routing | StaticRouting diretto/multi-hop; Flooding nativo |
| PHY | BPSK upstream; classe separata BPSK corretto sperimentale |
| Canale | Underwater analitico, Thorp, rumore ambientale, interferenza MIV |
| Interfacce | Una acustica per drone; override indipendenti di PHY e parametri |
| Applicazioni | Periodico, intervallo variabile, Poisson, burst, eventi, request/reply, heartbeat |
| Indirizzamento | Destinatari applicativi unicast; broadcast reale nel routing Flooding |

Flooding è ammesso con ALOHA, CSMA-ALOHA, TDMA e TDMA Frame. La matrice nativa
ha rivelato quattro combinazioni senza consegna: Flooding con CSMA/CA o DACAP,
per entrambe le classi PHY. CSMA/CA rifiuta gli RTS broadcast nel sorgente
`data_link/uw-csma-ca/uw-csma-ca.cpp`, ramo `stateRxRTS`, righe 406–408 della
versione installata. Queste combinazioni vengono rifiutate dallo schema e
dal server Docker; la UI filtra il routing. Il modello non viene modificato.

Non sono implementati multicast applicativo, API di gruppi, più interfacce per
drone, MAC differenti per nodo, priorità MAC, switching, ranging o energia.
I generatori Python non sono UW/CBR o UW/VBR nativi. Nessuna di queste funzioni
viene presentata come operativa.

## Identità del motore e audit

Base fissata: `uwsignet/desert:4.0.0@sha256:59c734d2980de64e4b36429c3fb4a60aceb1cb7efc5f9d605f9b7781fbc51ca6`.
Sorgente presente nel container: `12203f3cdba7d85bac78074d1f2ccfddbfb08021`.
Immagine del laboratorio: `holo-desert-engine:4.0.0-v2`; builder `desert-lab-v2`.
Immagine derivata verificata in questa installazione:
`sha256:07d51cacd55ad3bfcf2e1bcac15c1162d5b8e8190fa76fed798458797067312a`.
Gli hash dell'immagine derivata dipendono dalla build locale; non sostituiscono
il digest della base. La patch è compilata nell'estensione del progetto,
senza modificare i sorgenti ufficiali.

L'audit ha individuato 116 librerie installate, 102 moduli sorgente,
181 dichiarazioni TclClass, 100 file di default e 85 script ufficiali.
**181 dichiarazioni non significano 181 costruttori verificati.** Passano
100/109 caricamenti isolati di plugin e 67/68 sequenze di librerie dei campioni;
sette librerie di supporto sono escluse dal test di plugin Tcl. Non è stata
eseguita integralmente ogni simulazione ufficiale: per i moduli integrati
sono state eseguite prove equivalenti sul bridge effettivo.

L'[inventario completo](../../src/holo_desert/resources/docker/desert-inventory.json)
contiene tutti i nomi, percorsi, librerie, classi, default, campioni e risultati
dei probe. È una fotografia dell'immagine iniziale v1, identificata nel campo
`runtime`; il [catalogo corrente](../../src/holo_desert/resources/docker/communication-catalog.json)
aggiunge lo stato di integrazione v2. La [matrice delle capacità](../stack-configuration.md#protocol-catalogue)
spiega i moduli non abilitati. Le API sono `/api/network-inventory` e
`/api/network-catalog`.

## Stack Builder

Lo schema `scenarios/network.py` descrive le sole opzioni supportate.
`resources/docker/stack_builder.py`, condiviso fra host e container, valida
anche il JSON ricevuto direttamente via TCP e produce costanti Tcl numeriche,
classi e librerie in whitelist. Respinge valori non finiti, input Tcl, route
cicliche, riferimenti errati, interfacce sconosciute e combinazioni incompatibili.

Ogni adapter in `resources/desert/tcl/modules/` applica l'inizializzazione
del protocollo: variabili prima del costruttore quando necessario, indirizzi,
slot o matrice, modalità ACK e avvio dei timer. UDP/IP/MLL restano fissi.
L'orchestratore non deve conoscere gli stati interni dei MAC.

Propagazione e maschera spettrale sono istanze per drone. Gli override non
riscrivono una variabile Tcl di classe dopo aver costruito tutti i nodi.
La velocità del suono resta una proprietà del canale condiviso. In modalità
integrata vengono applicate le pose misurate da HoloOcean a ogni barriera.

I vecchi YAML utilizzano i default storici e `bpsk_upstream`. La modifica dello
schema è additiva; il client rifiuta un'immagine bridge precedente, così una
vecchia immagine non può ignorare silenziosamente nuove opzioni. Aggiornare con
`holo-desert engine up`, che comprende la build.

`engine_info` registra commit, builder, patch, configurazione effettiva e
override risolti. `run_started` registra versioni HoloOcean/progetto, substream
e mappa degli indirizzi. `run_selection` conserva l'identificativo dello scenario;
`network.profile_id` conserva l'eventuale profilo di origine. Il nome e tutti i
parametri finali sono nel `config.json` esportato. L'identificativo del profilo
è provenienza, non un riferimento modificabile che governa una corsa precedente,
ed è escluso dall'impronta del confronto.

## Correzione probabilistica BPSK

L'upstream continua a chiamare `UnderwaterMPhyBpsk::endRx()` senza cambiarne
le decisioni. La nuova classe `Module/MPhy/BPSK/Underwater/HOLO/Corrected`
ha ID `conditional-bpsk-v1`. La dashboard mostra la classe e la patch usate,
anche quando sono diverse fra nodi.

Sia `Pn` la probabilità di errore del pacchetto per solo rumore e `Pt` quella
totale per rumore e interferenza. Dopo il test di rumore il rischio residuo è
`q = (Pt - Pn) / (1 - Pn)`, quindi `Pn + (1-Pn)q = Pt`.
Si calcola il rapporto delle probabilità di successo in dominio logaritmico,
con `log1p`/`expm1`, evitando cancellazione numerica e divisione per zero.
Per interferenza variabile si sommano i contributi dei chunk MIV, pesati con
bit frazionari proporzionali alla loro durata. Dividere un chunk non cambia
il risultato. Le parti senza interferenza conservano il rischio del rumore.
Con interferenza nulla `q=0` e non si esegue un secondo sorteggio.

Restano inalterate acquisizione, bitrate, penalità SNR, propagazione,
interferenza MIV e gestione dei pacchetti. La patch cambia il numero di
estrazioni RNG: confrontare statistiche, non esigere gli stessi singoli esiti.
È una patch sperimentale del modello BPSK idealizzato, non una calibrazione
rispetto a un modem o a misure in mare.

Prova controllata: due nodi fissi a 40 m, 105 dB SPL, 25 kHz, 5 kHz,
4800 bit/s, substream 1, payload 16 byte, 24 frame per variante ogni 2 s.
Frame effettivi 1624–1632 bit; SNR grezzo 17,423024 dB; interferenza nulla.

| PHY | Decodificati | Rumore | Secondo ramo “interferenza” |
|---|---:|---:|---:|
| Upstream | 3/24 | 16 | 5, con Pi=0 |
| Corretto | 11/24 | 13 | 0 |

Queste sono frequenze empiriche, non stime precise del PER. Con penalità
−10 dB il BER ideale è circa 0,0004436: per 1624–1632 bit il successo teorico
è circa 0,485–0,486 con un solo test, circa 0,235–0,237 con due test analoghi
indipendenti. Il campione è intenzionalmente piccolo. La prova separata con
due trasmettitori sovrapposti produce interferenza positiva ed errori nel
PHY corretto: il secondo rischio non è stato semplicemente eliminato.

## Telemetria e confronto

Si separano byte payload, byte envelope, bit PHY, frame dati/controllo,
inizio/fine TX e RX, potenze lineari normalizzate, SNR grezzo, penalità,
esiti, consegna, TTL e arrivo tardivo. Il timestamp PHY assoluto non è la
latenza applicativa. I contatori MAC sono nativi; quelli non esposti valgono
`null`, mai zero inventato. TDMA/Frame usano `get_buffer_size`; CSMA/CA e
DACAP espongono anche contatori specifici di handshake/scarto/attesa.

Il tempo sul mezzo è la **somma** delle durate delle trasmissioni, comprese
ritrasmissioni e forwarding: con trasmissioni sovrapposte può superare il
tempo simulato. Non è l'unione temporale dell'occupazione di un singolo canale.
Il numero di errori PHY include ascolti non destinati al destinatario finale;
non coincide con il numero dei messaggi persi.

Un TTL scaduto resta a causa indeterminata se manca evidenza individuale.
Un `interference_error` upstream con Pi=0 è etichettato “secondo test PHY
fallito (interferenza nulla)”; metadati insufficienti non diventano collisioni.
Gli arrivi dopo TTL restano fuori dalle consegne valide, nella timeline.
I percorsi sono osservazioni di inoltro, non route dinamiche ricostruite da
posizioni globali. Le frecce PHY passate riappaiono solo selezionando il messaggio;
le consegne storiche riportano il tempo assoluto.

Il confronto conserva fino a sei riepiloghi in memoria. L'impronta include
PHY, potenza, bitrate, seed, traffico, geometria, tempi e opzioni MAC comuni;
le impostazioni specifiche dei diversi protocolli sono conservate nelle
configurazioni. Seed e traiettorie configurate uguali non garantiscono
traiettorie fisiche misurate identiche. Nessuna stima energetica viene inventata.

## Prove eseguite

Prove native: matrice di 20 combinazioni operative MAC/routing/PHY con invio
bidirezionale, più quattro combinazioni rifiutate; restart dei quattro nuovi
MAC; slot di entrambi i nodi con assegnazioni invertite; relay Flooding reale;
potenza/bitrate/PHY per istanza; ACK e frame DACAP identificati dal loro header;
test matematico compilato e interferenza controllata. Il test di morte NS
usa esclusivamente il container di verifica indicato con `DESERT_TEST_CONTAINER`.

Otto prove integrate HoloOcean passano: sei configurazioni rappresentative
con i nuovi MAC, Flooding e PHY corretto, più request/reply originale e
pausa/ripresa/arresto con congelamento di entrambi gli orologi. Tutte le sei
configurazioni nuove hanno consegnato 4/4 messaggi nelle condizioni brevi di
prova; questo non costituisce una garanzia di PDR in altre condizioni.

| MAC nella prova integrata | Frame dati | Frame controllo | Bit controllo | Airtime dati/controllo [s] |
|---|---:|---:|---:|---|
| TDMA | 4 | 0 | 0 | 1,415 / 0 |
| TDMA Frame | 4 | 0 | 0 | 1,415 / 0 |
| CSMA/CA | 4 | 8 | 64 | 1,415 / 0,013333 |
| DACAP | 4 | 8 | 256 | 1,428333 / 0,053333 |

Il conteggio dei bit è quello dichiarato dal modello nativo, che può usare
frame di controllo idealizzati molto piccoli; non equivale a una misura di
modem reale con preambolo, codifica e framing hardware.

Regressione completa, una corsa per ciascun YAML originale, con BPSK upstream:

| Scenario | Generati | Consegnati | Scaduti | Pendenti |
|---|---:|---:|---:|---:|
| E01 | 2 | 2 | 0 | 0 |
| E02 | 24 | 11 | 13 | 0 |
| E03 | 45 | 22 | 23 | 0 |
| E04 | 84 | 23 | 61 | 0 |
| E05 | 3 | 3 | 0 | 0 |
| E06 | 29 | 19 | 10 | 0 |

E03 mantiene 21 errori di rumore e due esiti del secondo ramo upstream;
E05 mantiene tre forwarding osservati nel relay; E06 mantiene HOLD/PROCEED
in risposta all'interruzione reale del collegamento. I file originali non
sono modificati. La [diagnosi E03](e03-loss-diagnosis.md) rimane valida.

La prova browser contro il backend reale seleziona TDMA, Flooding e BPSK
corretto, applica un override, avvia HoloOcean/DESERT e verifica 4 consegne,
patch effettiva e metriche renderizzate. Le prove UI di fixture sono distinte
da questa prova reale. Screenshot del Designer e dei risultati sono stati
ispezionati a desktop e finestra ridotta; pannelli avanzati restano richiudibili.
Cinque screenshot compatti sono conservati con la documentazione:
[1920×1080](../images/network-designer-1920.png),
[1440×900](../images/network-designer-1440.png),
[900×900](../images/network-designer-900.png),
[parametri avanzati](../images/network-designer-advanced-1440.png),
[confronto di sei corse reali](../images/network-comparison-1440.png).
Gli altri log e artefatti di lavoro sono in `.local/`, esclusi da Git.

Verifica conclusiva: **63 test unitari**, **47 test nativi DESERT**,
**8 test integrati HoloOcean** e **22 test browser** passati. Un test di symlink
è saltato perché Windows richiede privilegi non disponibili. Le prove native
includono controlli di rifiuto, non 47 esperimenti con ricezione riuscita.
Il wheel è stato costruito e controllato: catalogo, inventario, adapter Tcl,
header C++ e nuovi moduli frontend sono inclusi. Nessuna dipendenza runtime aggiunta.

La verifica guidata da Playwright ha inoltre completato **sei corse consecutive
dalla UI**, una per MAC, con 4/4 consegne ciascuna e parametri comuni equivalenti.
Questo campione breve verifica il percorso UI/bridge, non una classifica
statistica. Il confronto mostra overhead e latenze effettive con lo stesso traffico.

## Anomalie implementative incontrate

| Problema | Evidenza e trattamento |
|---|---|
| BPSK upstream riconta il rumore | Preservato nell'originale; classe sperimentale con rischio condizionato e test analitici/nativi |
| TDMA Frame: separatore della matrice | Il default nativo è virgola; importare righe con spazi causava SIGFPE. L'adapter imposta il separatore spazio |
| DACAP cambia il packet type | La telemetria riconosce DATA_PKT e orig_type nell'header nativo; dati separati dal controllo |
| Coda TDMA appariva N/D | Il comando corretto è get_buffer_size, non getQueueSize; verificato nel sorgente e nelle corse |
| Riesegui ignorava il MAC applicato | Test browser inizialmente fallente; dashboard/static/app.js conserva la configurazione applicata alla corsa da rieseguire |
| Dimensione serializzata negli slot | stack_builder.py include timestamp float lungo, envelope request/reply, header UDP/Flooding e interfaccia più lenta; include heartbeat. Nessuna modifica automatica del frame |
| Avvio HoloOcean Windows intermittente | OpenSemaphore falliva prima della generazione di pacchetti; attesa IPC nell'adapter, descritta sotto |

Nel sorgente locale HoloOcean 2.3,
`engine/Source/Holodeck/HolodeckCore/Private/HolodeckServer.cpp:35–37`, Windows
rilascia LOADING prima di creare SERVER e CLIENT. Il client installato apre
subito questi ultimi in `holooceanclient.py:45–53`, dopo l'avvio in
`environments.py:211`. L'ordine spiega l'errore Windows 2 osservato e il processo
rimasto ad attendere comandi. Questi avvii avevano zero messaggi: non erano
perdite DESERT.

`holoocean_adapter/adapter.py` usa una sottoclasse dell'ambiente ufficiale su
Windows, con gli stessi parametri/package/world della factory 2.3, e attende
al massimo due secondi entrambi i semafori della propria UUID. Non ritenta
errori di permesso. Conserva l'oggetto se il costruttore fallisce, per chiudere
il processo posseduto. Nessun file SDK è modificato; fisica e sincronizzazione
rimangono ufficiali. `windows-ipc-ready-v1` è registrato in run_started.versions.
Test unitari verificano handle, permessi e pulizia dopo inizializzazione parziale;
seguono sei avvii UI consecutivi e otto test integrati riusciti.

Prima dell'aggiornamento è stata esportata la corsa preesistente terminata in
`.local/pre-lab-dashboard-results.zip` (circa 60 kB). Nessuna corsa attiva
dell'utente è stata interrotta. La dashboard aggiornata resta sulla porta 8000;
i container e il server aggiuntivi di verifica sono temporanei.

## Commit locali

| Commit | Contenuto |
|---|---|
| f5978b3 | Inventario, catalogo, schema, builder e stack nativi, BPSK separato, test DESERT |
| 4a8200c | Designer, profili, traffico, diagnostica e confronto; fix Riesegui |
| a41296d | Attesa IPC Windows e pulizia dell'inizializzazione HoloOcean |
| Commit contenente questo report | README, guide, evidenze e screenshot |

Ramo `feat/desert-laboratory`; nessun push e nessun merge. `git log -4 --oneline`
mostra anche l'identificativo dell'ultimo commit di documentazione.

## Avvio e limiti

```powershell
.venv\Scripts\holo-desert.exe engine up
.venv\Scripts\holo-desert.exe dashboard
# Oppure una prova con MAC diverso, preservando gli altri parametri:
.venv\Scripts\holo-desert.exe run e01_chat --mac tdma --headless
```

Aprire http://127.0.0.1:8000 e seguire la [guida al Designer](../dashboard.md#network-designer).
Docker continua a ospitare DESERT; HoloOcean rimane sull'host. Nessuna nuova
distribuzione WSL, middleware o dipendenza Python/JS runtime è richiesta.

WOSS, ottico/EM, multi-PHY, discovery dinamico e ranging restano lavoro
successivo esplicitamente censito. Non sono stati eseguiti test hardware,
calibrazione in mare, campagne multi-seed o tutti gli script ufficiali.
