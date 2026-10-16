# Limitazioni e confini verificati

- Target host Linux: Ubuntu 24.04. La verifica grafica effettuata su questa
  macchina riguarda Windows nativo, Ocean 2.3.0 e GPU NVIDIA. Non equivale a
  una certificazione di rendering su Ubuntu, WSLg, macOS o GPU diverse.
- DESERT è fissato al digest ufficiale Linux amd64. Il suo commit interno
  differisce dal tag Git oggi pubblicato; entrambi sono nel manifesto.
  Header SDK e ABI di compilazione sono specifici di questa immagine.
- Il backend iniziale usa BPSK/Underwater, propagazione analitica Underwater,
  interferenza MIV, MAC ALOHA/CSMA_ALOHA e route statiche. WOSS, ray tracing,
  routing dinamico e altri MAC non sono esposti dal configuratore.
- Ostacoli e fondale influenzano la fisica HoloOcean. Non vengono convertiti
  in occlusioni acustiche o bathymetry del modello analitico DESERT.
- Geometria mantenuta costante per un tick fisico. Nessun Doppler, movimento
  continuo durante il volo o ricalcolo retroattivo dei segnali. I waypoint
  sono target, mentre il canale usa esclusivamente le posizioni misurate.
- Ogni ricezione viene consegnata all'applicazione al tick fisico successivo
  o coincidente, conservando il timestamp preciso del motore NS.
- La pausa riguarda entrambi gli scheduler logici. Il tempo di rendering,
  caricamento dei mondi e costruzione iniziale dell'immagine non è tempo
  simulato. Lo stop durante un build Docker attende la conclusione o il
  timeout dell'operazione in corso; non interrompe globalmente Docker.
- Una sola esecuzione per servizio DESERT. Il protocollo applicativo iniziale
  offre unicast; broadcast non è implementato e viene rifiutato.
- Priorità applicativa e TTL sono metadati/validità dell'applicazione: non
  diventano priorità MAC o cancellazioni di pacchetti già in volo.
- I contatori PHY includono anche ricezioni overheard. `interference_error`
  è una prova di errore da interferenza del PHY, non un sinonimo di qualunque
  timeout. Le ricezioni non sincronizzate possono dipendere da SNR basso,
  sovrapposizione o trasmettitore occupato; il dettaglio conserva l'esito.
- Retry per messaggio non sono ricostruiti come conteggi certi. Gli eventi
  PHY permettono ispezione, ma il dashboard non inventa una statistica MAC.
- La topologia mostra ricezioni applicative end-to-end, non link fisici
  stimati dalla sola vicinanza. I relay vanno verificati nei dettagli.
- Le soglie di E03/E05 sono dimostrazioni qualitative del modello e del seed
  configurati, non una calibrazione di un modem o di un ambiente marino reale.
- Dashboard tramite polling HTTP ogni 500 ms. Visualizzazione recente:
  500 pacchetti, 1000 campioni metrici, 200 punti di traiettoria per nodo.
  Gli eventi completi restano nel JSONL temporaneo fino alla chiusura.
- Le verifiche HTTP e sintattiche della dashboard sono automatizzate.
  Nessun browser automatizzabile era disponibile per una verifica visiva
  dell'interfaccia durante questa sessione.
- Le dipendenze upstream emettono warning di deprecazione Matplotlib/pyparsing
  e alcuni warning Tcl di variabili default mancanti. Non vengono interpretati
  come perdite di comunicazione. Gli errori reali del processo fermano il run.
- Su Windows è stato osservato un processo Unreal già terminato secondo
  `GetExitCodeProcess`, ma il cui handle non risulta ancora segnalato alla wait
  di Python. L'adattatore controlla l'exit code del solo handle posseduto:
  `STILL_ACTIVE` non viene mai accettato come arresto riuscito. La liberazione
  finale degli oggetti kernel/driver resta responsabilità del sistema operativo.

Esiti numerici e comandi effettivamente eseguiti: [validation.md](validation.md).
