# Evoluzione del laboratorio DESERT

## Intento e autorizzazione

Il brief utente del 20/10/2026 richiede esecuzione diretta in fasi A–H,
senza riscrivere dashboard, editor o fisica. HoloOcean misura le pose;
solo DESERT decide propagazione, errori, accesso al canale e routing.
Questa specifica applica quel mandato, senza una nuova richiesta di permesso.

## Scelta architetturale

Scartati un elenco di nomi Tcl sostituibili e plugin Tcl arbitrari: non
descrivono inizializzazioni, ruoli, unità e compatibilità. Si usa invece un
catalogo di adapter espliciti, con metadati condivisi e configurazione
Pydantic. Il catalogo distingue presenza sorgente, libreria, caricabilità,
esempio, compatibilità e verifica integrata. Installato non significa operativo.

Il builder genera solo costanti numeriche, nomi e comandi in whitelist.
Adapter MAC/routing/PHY dichiarano librerie e procedure di inizializzazione;
nessuna decisione di rete è implementata nel builder. Il server Docker valida
anche l'input JSON direttamente ricevuto. Il catalogo è incluso nell'immagine.

Gli YAML esistenti conservano default e comportamento upstream. Lo schema
ammette nuovi blocchi opzionali tipizzati; i default storici restano invariati.
Le risorse E01–E06 non cambiano. Gli override per nodo sono applicati alle
istanze, mai simulati cambiando l'ultima variabile di classe per tutti.
Combinazioni non supportate vengono rifiutate prima dell'avvio.

## Modello fisico

Un'estensione separata introduce BPSK condizionato: un unico rischio totale
rumore+interferenza, con classificazione probabilistica coerente. L'originale
resta identico e selezionabile; nessuna patch ai sorgenti ufficiali. La
versione corretta entra nel catalogo operativo solo dopo compilazione e prove
analitiche e native, sia isolate sia con interferenti. Il run registra la scelta.

Spreading, shipping, vento, velocità del suono, penalità e acquisizione sono
parametri reali verificati nel container. Le unità rimangono acustiche, non dBm.
Gli eventi distinguono SNR grezzo, potenze, interferenza, dimensione wire,
dimensione PHY e tempo di propagazione quando effettivamente osservati.

## Frontend e configurazioni

La UI esistente conserva pagina iniziale, mappa, editor scenari e stile.
Network Designer espandibile: moduli/parametri pertinenti con aiuti accessibili
da catalogo, canale, traffico, override, riepilogo. Catalogo informativo separato
dai selettori operativi; motivazioni per i moduli non integrati.
Profili di comunicazione persistenti e revisionati sono distinti dagli scenari,
applicabili senza cambiare droni e movimento. La gestione riusa le garanzie
di scrittura atomica/conflitti della libreria esistente.

Il confronto conserva configurazioni, substream e impronta dei parametri
comuni. Non dichiara equivalenti configurazioni con traffico, potenza, PHY o
traiettorie configurate differenti. Non deduce collisioni da timeout o archi
attivi da consegne storiche.

## Sequenza e condizioni di accettazione

A. Audit dell'immagine e piano adapter; matrice completa prima delle estensioni.
B. TDMA e altri MAC verificabili, generatori di traffico espliciti.
C. Flooding e ulteriori routing dove inizializzazione e osservabilità lo consentono.
D. Parametri fisici e BPSK corretto, con scelta storica conservata.
E–G. WOSS, ottico, EM, multi-PHY, ranging e hardware: integrazione solo se
dipendenze, semantica e prove sono disponibili; altrimenti motivazione concreta
nel catalogo, senza placeholder operativi. Non bloccare gli altri adapter.
H. UI, API, profili, telemetria, test reali e documentazione.

Ogni adapter operativo deve attraversare vero DESERT e HoloOcean, conservare
gli eventi, inizializzarsi e arrestarsi dalla dashboard. I test verificano slot,
hop o collisioni reali oltre alla semplice consegna. Nessuna campagna estesa,
nessun output ordinario persistente. Restano compatti rapporto e screenshot
ignorati da Git. Commit locali logici; nessun push o merge.
