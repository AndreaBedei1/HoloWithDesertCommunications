# Usare il Network Designer

Aprire la dashboard e scegliere uno scenario. **Impostazioni** apre il
Designer; le stesse sezioni sono disponibili nell'editor degli scenari personali.
MAC, PHY e routing mostrano soltanto moduli operativi. Il **Catalogo dei moduli**
spiega anche quelli presenti in DESERT ma non integrati.

1. Scegliere MAC, PHY e routing. I due BPSK sono esplicitamente distinti;
   quello corretto è sperimentale. La scelta non cambia movimento e applicazioni.
2. Regolare bitrate e potenza. La potenza è SPL acustico, non dBm.
3. Aprire **Impostazioni avanzate** per parametri del canale e del protocollo,
   slot, route, override dei droni e flussi. I campi cambiano con il modulo.
4. Usare le icone `?` con puntatore, clic o tastiera. Spiegano significato,
   unità, default e vincoli; un intervallo ammesso non è un valore raccomandato.
5. Applicare alla prossima corsa. Lo schema viene validato sul server e di nuovo
   nel container; errori e combinazioni incompatibili bloccano l'avvio.

Con TDMA assegnare uno slot diverso a ogni drone, da zero a N−1; il campo
vuoto iniziale usa l'ordine dei nodi. Frame e guard devono lasciare spazio
all'envelope serializzato. Con Flooding non inserire route statiche: gli
inoltri sono broadcast nativi. CSMA/CA e DACAP richiedono routing statico
nello stack verificato. Il catalogo documenta questa incompatibilità.

Gli override acustici vuoti ereditano il profilo globale. Potenza, bitrate,
frequenza, banda, PHY e ricevitore sono indipendenti per drone. La velocità
del suono resta condivisa; MAC/routing differenti per drone e più interfacce
non sono attualmente disponibili. Un flusso usa l'unica interfaccia acustica.

## Profili e scenari

Uno **scenario** contiene droni, movimento, traffico e rete. Un **profilo di
comunicazione** contiene la rete da riusare con scenari differenti.

Da **Profili di comunicazione**, scegliere un esempio oppure **Nuovo dalla rete
corrente**, assegnare nome/descrizione e salvare. Gli esempi si possono duplicare;
i personali si possono modificare, duplicare, eliminare, importare ed esportare
in YAML. Le scritture sono atomiche e revisionate: una versione modificata
altrove produce un conflitto, senza sovrascrivere il file più recente.

**Applica rete al progetto** mantiene droni, waypoint e flussi. Route e slot
devono riferirsi ai droni dello scenario corrente; l'applicazione verifica
questa compatibilità. Il profilo viene risolto nella configurazione della
corsa, così successive modifiche al profilo non cambiano risultati precedenti.

I profili sono conservati nella sottocartella `profiles` della libreria dati
scenari. `HOLO_DESERT_SCENARIOS_DIR` sceglie una directory portabile. Le corse
ordinarie rimangono temporanee e si salvano solo con l'esportazione ZIP.

## Traffico e lettura dei risultati

Periodico e intervallo finale producono traffico a frequenza costante o
variabile. Poisson usa un RNG applicativo indipendente e riproducibile dal seed;
burst specifica numero/intervallo/periodo, eventi specifica tempi assoluti.
I tempi sono quantizzati dai tick HoloOcean: al massimo una generazione per
flusso in un aggiornamento, senza recuperi simultanei artificiali dei tick passati.
Poisson parte al tempo iniziale indicato, poi campiona intervalli esponenziali.
Sono injector Python; le trasmissioni rimangono nel DESERT reale. Non sono
i generatori nativi UW/CBR o UW/VBR, censiti separatamente nel catalogo.

Il payload è distinto dall'envelope e dai bit PHY. La risposta applicativa
è distinta dall'ACK MAC. Il TTL parte dalla generazione; non cancella un frame
già nella coda DESERT. Arrivi tardivi non diventano consegne valide.

Selezionare un messaggio per timeline, relay osservati, TX/RX, SNR e dati
originali. Una scadenza non dimostra un errore PHY. Il secondo ramo upstream
con interferenza nulla viene etichettato esplicitamente. N/D significa dato
non osservabile, non zero. I tempi sulla mappa sono assoluti; la latenza è
ricezione meno generazione.

In **Analisi → Confronto MAC** conservare il riepilogo di una corsa integrata
finita e ripetere con un MAC diverso. Si conservano al massimo sei riepiloghi,
con PDR, latenza, goodput, envelope throughput, code, errori, scarti e dati/
controllo PHY. Esportare il confronto per controllare le configurazioni complete.
Differenze nei parametri comuni o MAC uguali rendono il confronto non controllato.
Il confronto non avvia campagne automatiche né riscrive applicazioni/traffico.

Il tempo trasmesso è la somma degli airtime, non l'occupazione temporale unita
del canale: sovrapposizioni e inoltri possono aumentarne il totale oltre la
durata della corsa. Non è un consumo energetico.

Per limiti fisici, inizializzazione e default dei protocolli consultare le
[schede tecniche](desert-capabilities.md); per evidenze e regressioni il
[report di verifica](desert-laboratory.md).
