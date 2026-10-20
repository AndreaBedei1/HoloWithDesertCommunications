# Catalogo DESERT installato

La base, il commit effettivo e il metodo di prova sono descritti nel
[report del laboratorio](desert-laboratory.md). L'elenco completo di **tutti
i 102 moduli sorgente** e delle 116 librerie è nel file
[desert-inventory.json](../src/holo_desert/resources/docker/desert-inventory.json).
Il catalogo operativo centralizzato è
[communication-catalog.json](../src/holo_desert/resources/docker/communication-catalog.json),
consultabile anche nel Network Designer. L'inventario fotografa v1; il
catalogo registra la successiva integrazione v2. Non confondere le due date.

## Matrice di disponibilità

“Carica” significa plugin/sequenza di librerie caricabile, non costruttore
senza configurazione né intera simulazione ufficiale eseguibile. “E2E” include
una prova equivalente sul bridge reale; i risultati dei singoli probe sono
conservati nell'inventario. I moduli non integrati sono visibili nel catalogo,
esclusi dai selettori operativi.

| Famiglia | Sorgente / compilato | Carica | Bridge / E2E | Limite |
|---|---|---|---|---|
| ALOHA, CSMA-ALOHA | Sì / sì | Sì | Sì / sì | Mantengono la configurazione storica |
| TDMA, TDMA Frame | Sì / sì | Sì | Sì / sì | Slot, guard e frame devono essere validi |
| CSMA/CA, DACAP | Sì / sì | Sì | Sì / sì | Nessun Flooding broadcast verificato |
| StaticRouting, Flooding | Sì / sì | Sì | Sì / sì | Flooding solo con i quattro MAC compatibili |
| BPSK originale | Sì / sì | Sì | Sì / sì | Doppio test upstream conservato |
| BPSK corretto | Estensione progetto / sì | Sì | Sì / sì | Sperimentale, classe e patch distinte |
| Polling | Sì / sì | Sì | No / no | Ruoli AUV/sink/nodi e ciclo di polling non adattati |
| T-LOHI | Sì / sì | Sì | No / no | Richiede wake-up PHY/MIV e procedure dedicate |
| TokenBus | Sì / sì | Sì | No / no | Inizializzazione token/anello e recovery non adattati |
| CS-Burst | Sì / sì | Sì | No / no | Framing e ciclo burst nativi non adattati |
| ALOHA-Q / Sync | Sì / sì | Sì | No / no | Ruoli, apprendimento e sincronizzazione non integrati |
| UFetch | Sì / sì | Fallisce nel probe | No / no | Simboli/dipendenze native e ruoli da risolvere |
| SUN | Sì / sì | Libreria sì | No / no | Sink costruibile; node senza setup causa SIGSEGV |
| ICRP | Sì / sì | Fallisce | No / no | `UWIP_CLMSG_SEND_ADDR` non risolto nel caricamento provato |
| Position-Based | Sì / sì | Sì | No / no | Politica della conoscenza delle posizioni e discovery non integrate |
| WOSS/Bellhop | Sì / sì | Sequenza sì | No / no | Ambiente acustico e manager/PHY non integrati |
| Ottico | Sì / sì | Sì | No / no | PHY/canale dedicati, orientamento e LUT da collegare |
| EM | Sì / sì | Sì | No / no | Mezzo, antenna, unità, LUT e canale dedicati |
| OFDM / HMM | Sì / sì | Sì | No / no | Framing, interferenza o stati/tabelle dedicati |
| Multi-PHY | Sì / sì | Librerie sì | No / no | Controller e più catene/interfacce non costruiti |
| Ranging TDMA/TDOA/tokenbus | Sì / sì | Librerie sì | No / no | Header e risultati di misura non integrati |
| UW/CBR, UW/VBR nativi | Sì / sì | Sì | No / no | Header/identità diversi dai messaggi applicativi del bridge |
| Driver modem reali | Sì / sì | Dipende dal driver | No / no | Nessun hardware mappato/rilevato o configurazione verificata |

Le famiglie non operative richiedono adapter e validazioni specifici: non
sono dichiarate impossibili né tutte prive di dipendenze. Gli errori di load
non provano che il sorgente o la libreria manchino: il Tcl installato usa
RTLD_LOCAL e alcuni plugin non dichiarano i sibling necessari in DT_NEEDED.
Nessuna modifica ABI o ricompilazione di queste librerie è stata introdotta.

## Schede dei protocolli operativi

| Protocollo | Funzionamento e impiego | Modulo / inizializzazione | Parametri e limiti |
|---|---|---|---|
| ALOHA | Trasmette senza ascolto preventivo; riferimento per accesso casuale | `Module/UW/ALOHA`, `libuwaloha.so`; indirizzo, ACK/noACK, initialize | ACK, tentativi, limite buffer storico; possibili collisioni |
| CSMA-ALOHA | Ascolta il canale e usa attesa casuale; confronto con ALOHA | `Module/UW/CSMA_ALOHA`, `libuwcsmaaloha.so`; stessa famiglia di inizializzazione | ACK/tentativi; nessuna garanzia di consegna o assenza di collisioni |
| TDMA | Accesso pianificato per slot; utile per studiare attese e guard | `Module/UW/TDMA`, `libuwtdma.so`; default prima di new, setSlotNumber, start a t=0 | Frame 3 s, guard 0,1 s, un pacchetto/slot, N slot per N droni; indici 0..N-1 |
| TDMA Frame | Pianificazione da matrice di topologia | `Module/UW/TDMA_FRAME`, `libuwtdma_frame.so`; default ereditati espliciti, separatore spazio, matrice e indice 1-based, start | Profilo one-hot generato in cartella temporanea; niente matrice Tcl arbitraria; fase nativa spostata di uno slot |
| CSMA/CA | Handshake RTS/CTS prima dei dati; overhead osservabile | `Module/UW/CSMA_CA`, **`libuwcsmaca.so`**; binding interi prima di new, bitrate per istanza, ACK/noACK, initialize | Coda 10, backoff delta 1 s/max 20, timeout CTS/dati/ACK 10 s; bitrate intero; niente Flooding |
| DACAP | Handshake con attese legate ai ritardi acustici | `Module/UW/DACAP`, `libuwdacap.so`; binding senza underscore, indirizzo e ACK/noACK; niente initialize ALOHA | max_prop_delay 2 s, wait_costant 0,2, delta_D 1500, t_min 2, T_W_min 0; niente Flooding |
| StaticRouting | Prossimo hop esplicito o destinazione diretta | `Module/UW/StaticRouting`, `libuwstaticrouting.so`; addRoute nativo | Riferimenti e cicli validati; una route non garantisce ricezione |
| Flooding | Diffusione e forwarding broadcast nativi, cache contro duplicati | `Module/UW/FLOODING`, `libuwflooding.so`; addr e parametri nativi, nessun addRoute | TTL di rete 10 hop, cache 60 s, optimize true; distinto dal TTL applicativo in secondi |

I default riportati sono il **profilo di inizializzazione del bridge**,
verificato sulle binding native. Non sono raccomandazioni di impiego né tutti
i default grezzi upstream. Per esempio, TDMA deve ricevere un numero di slot
valido prima del costruttore, mentre alcuni default grezzi sono zero.
CSMA/CA ha semantica propria per i timeout e non eredita artificiosamente il
numero di retry ALOHA. Il parametro DACAP `delta_D` mantiene la binding nativa:
non viene alimentato con distanze globali HoloOcean come se fossero misure.

Entrambi i TDMA richiedono frame abbastanza lunghi per l'envelope fisico e
guard inferiore allo slot. La validazione usa un limite conservativo del
messaggio serializzato; non è una garanzia di assenza di sovrapposizione in
qualsiasi geometria. Propagazione e sincronizzazione rimangono nel modello.
Con due nodi e frame di 3 s, TDMA usa fasi 0 e 1,5 s; TDMA Frame, con la stessa
matrice one-hot, usa 1,5 e 0 s nel frame periodico. Questa fase è osservata
e testata, non riscritta per far coincidere i due protocolli.

La famiglia ALOHA storica imposta il limite buffer dopo la costruzione:
`has_buffer_queue` deriva dal default del costruttore e il limite non diventa
una coda finita attiva. Il comportamento è documentato nell'aiuto del parametro
e preservato per riprodurre E01–E06. Per studiare una coda realmente limitata
usare un MAC con coda nativa verificata; nessuna correzione silenziosa di ALOHA.

Per una prova dalla CLI: `holo-desert run e01_chat --mac tdma --headless`.
Sostituire `tdma` con uno dei sei identificativi. Dalla dashboard duplicare E01,
scegliere il modulo e applicare le impostazioni; per Flooding eliminare route
statiche residue e usare uno dei MAC compatibili. Consultare sempre i campi
specifici nel Designer prima di usare topologie o traffico differenti.

## PHY e unità

Entrambe le classi acustiche usano lo stesso modello Underwater/Thorp e MIV.
Il default storico è spreading 1,75, shipping 0,5, vento 0 m/s, velocità
1500 m/s, penalità ricevitore −10 dB e acquisizione 0 dB. Frequenza 25 kHz,
banda 5 kHz, bitrate 4800 bit/s e potenza 135 dB SPL sono il profilo base;
E03 mantiene il suo valore di 105 dB SPL.

Il livello SPL produce nel modello `Pt = 10^(SPL/10)` in unità acustiche
normalizzate: non watt elettrici, dBm o dBW. Il ritardo del canale analitico
è distanza/velocità del suono. Frequenza/banda sono Hz; spreading è adimensionale;
shipping è compreso fra 0 e 1. La banda deve restare sopra zero Hz.
Ottimizzazioni automatiche SPL/frequenza/banda restano disattivate per non
alterare la configurazione sperimentale. Il BER non è un parametro fittizio
indipendente: deriva dal PHY e dai suoi parametri effettivi.

## Dipendenze dei moduli ambientali e specialistici

WOSS e `bellhop.exe` sono installati; esistono SSP e un esempio senza database
globali. Non è quindi corretto sostenere che servano sempre database globali
per eseguire Bellhop. L'esempio con database richiede invece GEBCO2025,
WOA2023 e DECK41, assenti nei percorsi campione esaminati. Mancano nel bridge
la configurazione del creator/DB manager/controller, coordinate geografiche,
ambiente SSP/batimetria/sedimenti/superficie, directory dei risultati e hook
PHY. Nessuna geometria Unreal viene convertita automaticamente in batimetria.

Per l'ottico sono presenti `optical_noise/LUT.txt` e una LUT di attenuazione
a 532 nm. Per EM è presente una LUT PER SF7/CR4-5. Non basta averle sul disco:
servono le catene PHY/canale/propagazione corrispondenti, convenzioni di
orientamento, antenna, mezzo e unità, poi prove geometriche reali. Il
multi-PHY richiede più catene e i controller DESERT con ID e soglie espliciti.

I moduli di ranging richiedono messaggi/clock e output di misura propri.
Il costruttore RANGING_TDMA senza slot configurati causa SIGFPE nel probe;
questo non significa che il protocollo sia inutilizzabile con setup valido.
La distanza HoloOcean rimane ground truth e non viene spacciata per ranging.

Ahoi, EvoLogics e altri driver/packer upstream sono installati. L'audit non
rileva modem verificati o device mappati nel container. Hardware, indirizzi,
packing e scheduler realtime sono prerequisiti distinti dalla simulazione.
