# Protocolli e profili

Lo stack iniziale usa moduli realmente presenti nella release DESERT 4.0.0:

| Componente | Classe Tcl / implementazione |
|---|---|
| Applicazione | `Module/UW/APPLICATION/HOLO`, estensione di `Module/UW/APPLICATION` |
| Trasporto simulato | `Module/UW/UDP` |
| Routing | `Module/UW/StaticRouting` |
| Rete / risoluzione MAC | `Module/UW/IP`, `Module/UW/MLL` |
| MAC 1 | `Module/UW/CSMA_ALOHA`, libreria `libuwcsmaaloha.so` |
| MAC 2 | `Module/UW/ALOHA`, libreria `libuwaloha.so` |
| PHY | `Module/MPhy/BPSK/Underwater/HOLO`, sottoclasse osservatrice ufficiale |
| Propagazione | `MPropagation/Underwater` |
| Canale | `Module/UnderwaterChannel` |
| Interferenza | `MInterference/MIV` |

Non combinare MIV con il diverso `Module/UW/PHYSICAL`: il PHY subacqueo eredita BPSK e usa MIV. Il campione ufficiale usa invece BPSK generico. WOSS non fa parte del backend.

## Parametri supportati

| Campo YAML | Proprietà verificata nel codice/esempio DESERT |
|---|---|
| `acoustic.bitrate_bps` | `Module/MPhy/BPSK BitRate_` |
| `acoustic.tx_power_db` | `Module/MPhy/BPSK/Underwater MaxTxSPL_dB_` e `MinTxSPL_dB_` |
| `acoustic.frequency_hz` | `MSpectralMask/Rect setFreq` |
| `acoustic.bandwidth_hz` | `MSpectralMask/Rect setBandwidth` |
| `mac.ack` | `setAckMode` / `setNoAckMode` |
| `mac.max_tx_tries` | `max_tx_tries_` |
| `mac.buffer_packets` | `buffer_pkts_` |
| `network.routes` | `StaticRouting addRoute destination nextHop` |

La potenza è espressa nella convenzione acustica del modello DESERT, non in watt.
Frequenza, banda, bitrate e valore SPL default riprendono gli esempi ufficiali;
il PHY subacqueo applica la corretta conversione SPL, mentre il BPSK generico
del campione applicativo usa una diversa proprietà di potenza lineare.
La velocità del suono non
è esposta come parametro perché non è stata verificata una proprietà pubblica
corrispondente nel modello selezionato. Campi sconosciuti sono rifiutati.

`network.seed` seleziona il numero di substream del generatore NS, come il
parametro `rngstream` degli esempi ufficiali. Il log registra esplicitamente
`rng_substream`; non è un seed Python né una sorgente casuale basata sul wall clock.

Profili: `resources/profiles/acoustic_default.yaml` e `acoustic_aloha.yaml`.
Avvio alternativo: `holo-desert run e04_congestion --profile acoustic_aloha`.
Un profilo CLI sostituisce l'intera configurazione network dello scenario,
incluse eventuali route. Per modificare un solo valore conservando le route,
usare una copia dello YAML o l'editor configurazione della dashboard.
Per confrontare esclusivamente i due MAC, mantenendo potenza, bitrate e
buffer identici, usare `holo-desert run e04_congestion --mac aloha`.

Le metriche della coda MAC sono lette con `getQueueSize`. Retry e collisioni
non vengono dedotti da timeout o dal numero di messaggi ricevuti.
I contatori PHY `getErrorPktsNoise` e `getErrorPktsInterf` sono esposti. Le osservazioni per pacchetto registrano sincronizzazione, SNR e inizio/durata TX, delegando tutte le decisioni al modello originale.
Il campo `forward` indica il passaggio sotto IP di un pacchetto, anche su un
relay; la ricezione finale conferma il completamento end-to-end.

## Configurazione e valutazione di altri protocolli

Il modulo dashboard espone i parametri della tabella e gli override delle route
con validazione prima dell'avvio. ALOHA e CSMA-ALOHA sono stati provati anche
con ACK abilitati. Non è disponibile la correlazione di ogni ACK al UUID nella
dashboard: i trace per pacchetto descrivono i frame DATA applicativi. I contatori
MAC restano aggregati. Senza ACK, `max_tx_tries` non promette ritrasmissioni in
seguito a una mancata consegna applicativa.

L'immagine fissata contiene anche `libuwtdma.so`, `libuwtdma_frame.so`,
`libuwtokenbus.so`, `libuwcsmaca.so`, `libuwdacap.so`, `libuwflooding.so` e
`libuwposbasedrt.so`, riscontrate con `ls` nel container. Sono disponibilità di
librerie, non compatibilità certificata con questo bridge.

Valutati i campioni ufficiali locali `samples/desert_samples/MAC/test_uwtdma.tcl`
e `Network/test_uwflooding.tcl` del tag 4.0.0. TDMA richiede durata frame,
guard time, numero/assegnazione slot e avvio esplicito dei timer MAC: non è una
sostituzione della sola classe ALOHA. Il flooding introduce TTL e cache propri
e inoltri multipli, con semantica diversa dalle route statiche e dal TTL
applicativo. Una configurazione sicura richiederebbe schema e prove aggiuntive
su tempi, duplicati e telemetria. In questa fase si mantengono i due MAC
consolidati e il routing statico, senza aggiungere opzioni non verificate.

Per confronto E04 usare il selettore MAC e due riepiloghi della dashboard:
[procedura e significato delle metriche](dashboard.md). Il controllo include
ACK, tentativi, buffer, seed, flussi, geometria e ogni altro campo, escluso il
nome del MAC. Una differenza di bitrate o di durata rende il confronto non
controllato e viene segnalata.
