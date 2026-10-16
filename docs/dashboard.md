# Laboratorio dalla dashboard

Avviare `holo-desert dashboard`, aprire http://127.0.0.1:8000 e scegliere uno
dei sei scenari. La modalità integrata avvia HoloOcean nativo e DESERT Docker;
la modalità standalone usa esclusivamente posizioni fisse dichiarate ed è
rifiutata per E03/E06. Nessuna simulazione parte aprendo la pagina.

Il selettore MAC cambia soltanto `network.mac.protocol`. **Configura rete**
permette di modificare bitrate, frequenza, banda, potenza SPL, buffer, tentativi,
ACK, override delle route e flussi. Le unità sono accanto ai campi. Il modulo
viene validato dal server prima dell'applicazione e nuovamente prima dell'avvio.
Route non specificate: destinazione diretta, come nel backend esistente.
Nodi sconosciuti, loop, self hop, banda sotto zero, protocolli o campi non
supportati sono rifiutati. I waypoint restano comandi fisici HoloOcean.

L'editor JSON avanzato rimane disponibile. **Campi → JSON** trasferisce le
modifiche del modulo; **JSON → Campi** importa e valida il JSON. Il salvataggio
normale legge il modulo. E06 impiega heartbeat, quindi non accetta flussi
aggiuntivi che l'applicazione di coordinamento non eseguirebbe.

## Flotta e movimento

La mappa XY usa solo `DynamicsSensor`, con stessa scala sui due assi, griglia
in metri, orientamento, traiettorie, zoom con rotella e pan trascinando.
**Adatta mappa** ripristina l'inquadratura automatica. Selezionare un nodo
sulla mappa o dal menu per coordinate, profondità, yaw e statistiche DESERT.
Le distanze sono euclidee 3D tra posizioni misurate, non tra waypoint.

Il grafico sotto la mappa sovrappone distanza (asse sinistro, m) e PDR risolti
(asse destro, 0–1), utile per l'allontanamento e ritorno di E03. Il PDR è
cumulativo: può reagire con ritardo rispetto al movimento e non è una stima
istantanea di qualità del canale. In E06 il pannello mostra ruolo, stato,
ultimo heartbeat arrivato ed età, insieme alle transizioni HOLD/PROCEED e ai
cambi di potenza effettivamente applicati da DESERT.

## Topologia e pacchetti

- Tratteggio grigio: route esplicite e percorsi dei flussi, configurazione
  dichiarativa senza presunzione di raggiungibilità.
- Viola: `forward`, passaggio sotto IP osservato. Include l'invio della
  sorgente; un evento sul nodo intermedio prova l'inoltro del relay.
- Ambra: `phy_tx_start`, tratta destinata al next hop MAC effettivo.
- Blu: `phy_rx_end` con esito `decoded`. Può essere un ascolto di un pacchetto
  diretto a un altro nodo, quindi non prova né accettazione MAC né consegna.
- Verde: ricezione applicativa finale entro TTL; freccia end-to-end, anche
  quando la trasmissione richiede un relay.

Le identità MAC provengono da `node_info` all'avvio e dagli header reali dei
pacchetti al PHY. Non sono ricavate da indici o distanza. Le frecce osservate
sono storia recente, non uno stato binario del collegamento. L'evidenziazione
di un secondo simulato segue soltanto eventi effettivi. Un bordo rosso sul
nodo segnala un esito PHY negativo osservato. Usare il selettore del messaggio
per isolare le tratte A→B→C di E05 e la relativa timeline.

Packet Inspector filtra per nodo (inclusi relay), stato ed evento. Selezionando
una riga si vedono payload ed envelope separati, tempi originali NS, prima
TX fisica, consegna, deadline, latenza, relay e timeline. I metadati originali
rimangono espandibili. `phy_tx_observed` indica una TX nella storia del
messaggio; non significa che la radio stia ancora trasmettendo.

“Inserito nello stack” non certifica la presenza nella coda MAC. La coda e i
contatori di scarto sono disponibili per nodo, non per singolo UUID. Non
vengono inventati eventi individuali di scarto. **TTL scaduto** significa
mancata consegna applicativa entro la deadline, causa ignota: non collisione.
DESERT può ancora trasmettere un messaggio scaduto, ma Python non lo consegna
all'algoritmo. Gli errori PHY sono osservazioni (anche di ascolti), non il
numero di messaggi applicativi persi.

## Metriche e confronto

Le schede dividono consegna, PHY/code e geometria/clock. Scegliere intervallo,
nodo per PHY/code e coppia per distanza; le metriche di consegna sono globali.
Assi in secondi simulati con unità nel titolo.
La coda è campionata da DESERT a 1 Hz; i grafici mantengono l'ultimo campione
con una linea a gradini. Picchi intermedi non osservati. N/D e interruzioni
della linea indicano valori indisponibili, non zeri inventati.

Il PDR risolti è `ricevuti / (ricevuti + scaduti)`: i pending sono esclusi.
Goodput: bit di payload applicativo consegnati per intervallo campionato.
Throughput envelope: bit dell'envelope JSON/base64 consegnato, esclusi header
MAC/PHY, ACK e ritrasmissioni. La latenza è media cumulativa end-to-end, usando
tempo NS. La deriva è tempo reale trascorso meno tempo simulato, esclusa pausa;
in modalità fast può essere negativa.
I contatori `app_received` ufficiali DESERT precedono la validazione del TTL
Python e possono includere ricezioni tardive, escluse dalle consegne dashboard.

Per confrontare E04, completare una corsa, premere **Conserva riepilogo
corrente**, cambiare solo MAC e ripetere. La scheda verifica l'equivalenza
dell'intera configurazione escluso il protocollo. Seed/substream, geometria
configurata, durata e flussi devono coincidere; le traiettorie reali non sono
garantite identiche. I due riepiloghi includono i risultati negativi, goodput
medio sull'intera corsa, latenze, osservazioni PHY e picco della coda campionata.
È ammesso solo E04 integrato concluso; corse interrotte o fallite non sono
comparabili. Nessuna campagna viene avviata automaticamente.

## Controlli, memoria e risultati

Pausa ferma entrambi i motori alla barriera; ripresa prosegue dagli stessi
orologi. **stopping** include la pulizia di HoloOcean e DESERT: avvio e reset
sono abilitati solo dopo il completamento. Chiudere il server arresta la
sessione posseduta. Il primo build Docker può richiedere diversi minuti.

Snapshot separati dalle strutture del simulatore evitano modifiche durante la
serializzazione HTTP. Limiti: 500 pacchetti recenti esposti, 5.000 conservati,
256 eventi per pacchetto (troncamento dichiarato), 300 osservazioni topologiche,
200 punti di traiettoria per nodo, 1.000 campioni metrici, 100 transizioni e
due riepiloghi di confronto. I riepiloghi sopravvivono al reset fino alla
chiusura del server. Nessun localStorage o salvataggio automatico.

Il JSONL temporaneo conserva la storia completa fino al reset/chiusura.
**Esporta ZIP** salva manualmente configurazione, JSONL e CSV; **Esporta
confronto JSON** salva i due riepiloghi. Per conservarli esportare prima del
reset. `--persist` rimane un'opzione esplicita della CLI.

Stato delle prove e verifica visiva mancante: [consolidamento](consolidation-validation.md).
