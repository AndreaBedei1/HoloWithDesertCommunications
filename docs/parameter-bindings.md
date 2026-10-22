# Parametri del laboratorio: verifica dei binding

Verifica sul codice compilato dell'immagine fissata, DESERT commit
`12203f3cdba7d85bac78074d1f2ccfddbfb08021`. I default sotto indicati sono
del profilo del bridge; non sono raccomandazioni per modem reali.

| Controlli esposti | Binding e momento | Semantica verificata |
|---|---|---|
| Bitrate 4800 bit/s | `BitRate_`, istanza PHY | Durata nativa = bit frame / bitrate; override indipendente per nodo |
| Source level 135 dB | `MinTxSPL_dB_`, `MaxTxSPL_dB_`, istanza; ottimizzazioni disabilitate | Potenza normalizzata `10^(SPL/10)`, non watt o dBm |
| Frequenza 25000 Hz, banda 5000 Hz | `MSpectralMask/Rect setFreq/setBandwidth`, istanza | Banda positiva, influenza attenuazione, rumore integrato e sovrapposizione |
| Spreading 1.75, shipping 0.5, vento 0 m/s | `MPropagation/Underwater practicalSpreading_`, `shipping_`, `windspeed_`, istanza | Modello nativo di attenuazione e rumore; override per ricevitore |
| Velocità 1500 m/s | `Module/UnderwaterChannel propSpeed_`, canale condiviso | Ritardo di propagazione; non un override per nodo |
| Penalità −10 dB, acquisizione 0 dB | `RxSnrPenalty_dB_`, `AcquisitionThreshold_dB_`, istanza PHY | BER e acquisizione sono due controlli diversi; mantenuto il ramo BPSK upstream |
| ACK false | `setAckMode/setNoAckMode`, dopo costruttore MAC | ALOHA, CSMA-ALOHA, CSMA/CA e DACAP; rifiutato per TDMA |
| Massimo tentativi 3 | ALOHA `max_tx_tries_` dopo costruttore; DACAP `max_tx_tries` prima | Opera nel protocollo nativo con ACK; nessun tentativo automatico legato al TTL applicativo; non esposto per CSMA/CA |
| Buffer 100 | ALOHA `buffer_pkts_` dopo costruttore | **ALOHA abilita già la coda nel costruttore**; il limite funziona. Il precedente testo che lo dichiarava inefficace era troppo generale |
| Modalità CSMA-ALOHA legacy / bounded | `buffer_pkts_` di classe prima del costruttore, poi limite di istanza | Legacy conserva `has_buffer_queue=false` derivato dal default −1; bounded lo abilita prima di `new`. In legacy il campo limite non viene mostrato |
| Buffer TDMA/Frame 100 | `queue_size_` prima del costruttore | Limite nativo, controllato con `<`; non usa la logica ALOHA |
| Frame TDMA 3 s, guardia 0.1 s, 1 pacchetto/slot | `frame_duration`, `guard_time`, `max_packet_per_slot` prima del costruttore, `fair_mode=1`, `tot_slots=N` | Slot `frame/N`, guardia sottratta alla porzione attiva. Validazione preventiva dell'envelope e della risposta |
| Assegnazione slot | `setSlotNumber`, TDMA; matrice nativa, Frame | Indici 0..N−1; mantenuta la fase nativa differente di TDMA Frame |
| Coda CSMA/CA 10 | `queue_size_`, prima del costruttore | **Soglia nativa inclusiva**: `getQueueSize() <= max_queue_size`, può accodare soglia+1 oltre al frame in servizio. Documentato, non corretto upstream |
| Backoff CSMA/CA delta 1 s, max 20; attese CTS/dati/ACK 10 s | `backoff_delta_`, `backoff_max`, `cts_wait_val_`, `data_wait_val_`, `ack_wait_val_`, prima | Binding interi. `bitrate_` della singola istanza MAC segue il PHY ed è validato intero |
| DACAP attesa 0.2 s, massimo ritardo 2 s, delta D 1500, t_min 2, T_W_min 0 | `wait_costant`, `max_prop_delay`, `delta_D`, `t_min`, `T_W_min`, prima | Nomi e semantica upstream conservati; buffer e tentativi impostati prima di `new` |
| Flooding TTL 10, cache 60 s, optimize true | `ttl_`, `maximum_cache_time_`, `optimize_`, istanza | TTL in hop, distinto dal TTL applicativo in secondi. Broadcast nativo; incompatibilità handshake esplicite |

I parametri attraversano catalogo centralizzato, modello Pydantic, validazione
del builder condiviso e adapter Tcl. Gli override acustici non possono cambiare
silenziosamente il tipo di canale. Le route sono riferimenti numerici validati,
mai Tcl fornito dall'utente. I generatori Python restano applicazioni che
iniettano nel DESERT reale; non decidono la consegna.

Prove mirate: burst di cinque frame con buffer 1, eseguito sul PHY/MAC reale:
CSMA-ALOHA legacy nessuno scarto, bounded scarti osservati, ALOHA limite già
operativo. La modalità legacy è il default per riprodurre E01–E06 senza cambiare
i loro YAML. I test del builder verificano anche il rifiuto di modalità arbitrarie.
