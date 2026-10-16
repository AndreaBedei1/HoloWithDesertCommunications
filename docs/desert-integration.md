# Analisi delle interfacce DESERT 4.0.0

Fonte analizzata: tag `4.0.0`, commit
`8991214a1379747a2450f0dc4dd69f9173128f90` del [repository ufficiale](https://github.com/signetlabdei/DESERT_Underwater/tree/4.0.0).
L'esecuzione delle prove e l'identità effettiva dell'immagine sono registrate
separatamente in [validation.md](validation.md); leggere quel documento prima
di considerare una capacità verificata a runtime.

## Interfaccia applicativa ufficiale

File: `DESERT_Framework/DESERT/application/uwApplication/`.

1. **Ingresso payload**: `SetSocketProtocol TCP|UDP`, `Socket_Port_`, `start`.
   Il thread di socket alloca un `Packet`, copia bytes in
   `hdr_DATA_APPLICATION::payload_msg`, imposta dimensione e lo accoda.
   Il timer `transmit()` preleva un elemento, inserisce destinazione IP/UDP,
   timestamp `NOW`, tipo `PT_DATA_APPLICATION` e passa a `sendDown`.
2. **Ricezione**: `recv(Packet*)` valida il tipo, aggiorna statistiche e scrive
   il payload sul descrittore `clnSockDescr`, poi libera il pacchetto.
3. **TCP**: bidirezionale per la connessione accettata. Un'istanza applicativa
   serve un client alla volta; il ciclo di accept attende la disconnessione.
   Il nodo si distingue con la porta dell'istanza, non con un header socket.
4. **Framing**: TCP crea un pacchetto per `read`, che non equivale a un messaggio.
   `MAX_READ_LEN` default è 64, il limite header 4096. Non basta aumentare il
   read limit: frammentazione e coalescenza TCP restano possibili.
5. **UDP host**: `recvfrom` preserva i datagrammi in ingresso, ma l'uscita del
   modulo chiama `write(clnSockDescr,...)` mentre il ramo UDP non assegna una
   connessione client TCP. Non si considera verificato un ritorno UDP
   bidirezionale da questa sola implementazione.
6. **Destinatario**: `destAddr_` e `destPort_` sono proprietà dell'applicazione,
   non una destinazione per frame nel protocollo socket. Cambiarle mentre il
   timer ha payload in coda può associare la destinazione sbagliata.

Questi limiti motivano un'estensione isolata invece di usare TCP grezzo come
trasporto finale. Non sono implementati protocolli acustici Python.

## Posizioni e tempo

Il campione ufficiale [test_uwApplication.tcl](https://github.com/signetlabdei/DESERT_Underwater/blob/4.0.0/DESERT_Framework/DESERT/samples/desert_samples/Application/test_uwApplication.tcl)
collega `Position/BM` al nodo e a `PlugIn/PositionDB`, poi usa `setX_`, `setY_`,
`setZ_`. Le posizioni non sono payload; questi oggetti sono quelli consultati
dal modello del canale. L'estensione mantiene la stessa istanza e la aggiorna
sul thread scheduler, evitando modifiche concorrenti.

Il socket applicativo non espone queste operazioni. Non espone nemmeno lo
scheduler NS-MIRACLE. L'esempio può scegliere `RealTime` ma non offre un
protocollo esterno di pausa/step. Il nostro `bridge.tcl` aggiunge una callback
barriera che attende comandi, poi ritorna allo scheduler originale fino alla
successiva barriera programmata con `$ns at`. Non viene invocato ripetutamente
`$ns run`, non si azzera la coda e non si impone un ritardo di propagazione Python.

Le geometrie sono campionate ogni tick HoloOcean. Il modello mantiene la normale
semantica DESERT per segnali già in volo: nessuna pretesa di ray tracing mobile
continuo, Doppler o ricalcolo retroattivo della propagazione.

## Estensione del progetto

`resources/desert/extensions/bridge.cc` registra:

- `Module/UW/APPLICATION/HOLO`, sottoclasse dell'applicazione ufficiale.
  `sendhex destination bytes` inserisce un pacchetto v1 sul thread scheduler
  con header ufficiali IP/UDP/APPLICATION. `recv` riporta il tempo NS e bytes
  prima di delegare all'accounting e alla liberazione ufficiale.
- `Module/HoloProbe`, osservatore trasparente sotto IP. Registra passaggi
  verso il basso per provare l'inoltro di un relay; non cambia le route.

Il timer previsto dal distruttore upstream viene inizializzato senza avviare
traffico automatico. La sequenza è limitata al range sicuro dell'array di
lookup upstream; l'ID applicativo UUID è indipendente dalla sequenza DESERT.
La priorità header è zero; la priorità utente resta nell'envelope.

Il trasporto esterno è TCP locale con righe delimitate: una configurazione
JSON, poi `POSITION`, `SEND`, `POWER`, `STATS`, `STEP`, `STOP` con argomenti
validati. `hex` preserva payload binari e confini dei pacchetti. Non vengono
eseguiti comandi Tcl arbitrari dal client. Una sessione possiede un processo NS.
Più nodi appartengono allo **stesso** processo e canale condiviso; non si
collegano direttamente le applicazioni Python tra loro.

Non è necessaria alcuna patch ai sorgenti DESERT. Le librerie upstream vengono
caricate e l'estensione viene compilata nell'immagine Docker derivata.
L'estensione collega esplicitamente le librerie originali con `DT_NEEDED`:
il caricamento Tcl non rende automaticamente globali tutti i simboli tra plugin.

## Prove delle interfacce ufficiali

`holo-desert official-sample` ha eseguito il campione senza modificarlo:
166 pacchetti inviati, 166 ricevuti. `holo-desert official-sockets`, dopo
`engine up`, crea soltanto una copia temporanea del campione e abilita due
istanze socket. TCP: payload scambiati in entrambe le direzioni, contatori
ufficiali `PROBE_SENT=1,1`, `PROBE_RX=1,1`. UDP: gli stessi contatori nello
stack, ma nessun payload restituito ai due client esterni. Questa differenza
è osservata a runtime, non solo dedotta dai sorgenti.

## Statistiche, errori e disponibilità

Accounting ufficiale: `getsentpkts`, `getrecvpkts`, `getftt`, `getrtt`, `getthr`.
Si riportano soltanto contatori con significato pertinente: le statistiche
di perdita basate sulla sequenza non sono affidabili per tutti i flussi multi-sorgente.
MAC CSMA_ALOHA e ALOHA espongono `getQueueSize`; i contatori comuni MAC vengono
interrogati se disponibili e restituiti come `null` se non osservabili.

Una chiusura NS o TCP inattesa genera `BackendError` e porta la simulazione in
`failed`. Un errore di protocollo ferma la sessione e compare nel log motore.
Overflow del bridge e timeout applicativi sono eventi separati. Nessuna
collisione viene inventata in assenza di prove PHY. Il PHY BPSK iniziale non
offre la stessa classificazione avanzata del diverso `UW/PHYSICAL`.

Le librerie ALOHA, CSMA_ALOHA, UDP, IP, StaticRouting e MLL sono richieste
esplicitamente all'avvio: un modulo assente causa errore. Non esistono nomi
di protocollo tradotti silenziosamente in altri. Il catalogo completo della
release non equivale ai protocolli certificati dal nostro configuratore:
le sole combinazioni iniziali ammesse sono in [protocols.md](protocols.md).

## Identità immagine e header di compilazione

Il digest fissato contiene il commit DESERT `12203f3cdba7d85bac78074d1f2ccfddbfb08021`, che dentro l'immagine è etichettato 4.0.0. Il tag attualmente remoto risolve invece a `8991214a1379747a2450f0dc4dd69f9173128f90`. Sono registrati entrambi nel manifesto; il motore eseguito è quello dell'immagine e il commit effettivo è riportato nel log di ogni sessione.

L'immagine conserva gli header NS ma elimina `autoconf.h` generato. Il progetto fornisce un header di sola compilazione in `resources/desert/extensions/autoconf.h`, con feature Linux LP64 e impostazioni `RANDOM_RETURN_TYPE long`, `HAVE_STL`, namespace std riprese dall'installer ufficiale. Un `static_assert` rifiuta ABI diverse. Non modifica file o implementazioni NS. È valido soltanto per il digest Linux amd64 fissato; altri build richiedono verifica ABI.

Il backend usa `BPSK/Underwater` per rumore acustico e potenza SPL in dB. Il BPSK generico del campione usa invece potenza lineare e rumore costante: la sua proprietà `TxPower_` non viene etichettata come dB nel nostro configuratore. `HoloPhy` eredita il PHY subacqueo, aggiunge eventi osservativi e delega a esso TX/RX, sincronizzazione e decisioni di errore.
