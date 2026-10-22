# Revisione dashboard e scenari personali

Verifica locale del 20 ottobre 2026, Windows, Python 3.10.20, Node 24,
Playwright 1.64.1 con Edge headless. HoloOcean/Ocean 2.3 e DESERT in Docker
sono quelli già installati. Nessuna distribuzione WSL personale aggiunta.

## Revisione visiva

Prima delle modifiche sono state eseguite vere corse E03, E04, E05 ed E06,
con gli YAML originali e solo l'attesa in tempo reale disabilitata per la
verifica. Ogni corsa è stata messa in pausa per acquisire dati e schermate,
poi ripresa fino al termine e resettata. Sono state aperte e ispezionate
anche pagina iniziale, dettaglio messaggi e metriche.

Problemi osservati e corretti:

- Pagina iniziale dominata da pannelli tecnici vuoti: ora presenta sei esempi
  descritti, obiettivo dell'esperimento, numero di droni, durata e avvio.
- Mappa e comunicazioni separate: ora condividono la vista principale,
  con selezione del drone o messaggio e approfondimenti contestuali.
- Metriche e controlli troppo lontani: quattro indicatori principali,
  mappa più compatta e ultimi messaggi prima degli approfondimenti.
- Dettaglio pacchetto denso: filtri leggibili, timeline delle fasi osservate,
  dati originali e parametri tecnici espandibili.
- Etichette TX/RX/inoltro sovrapposte: tempi sulle TX del messaggio selezionato,
  frecce distinte e consegna finale curva con il proprio timestamp.
- Collegamenti storici potenzialmente ambigui: spiegazione esplicita della
  storia osservata; route configurate separatamente e disattivate di default.
- Grafico compatto della distanza con troppe etichette: numero di tacche
  adattato allo spazio verticale disponibile.
- Libreria personale vuota che mostrava un esempio: ora propone creazione
  e duplicazione, senza una scheda o impostazioni non pertinenti.
- Azioni dell'editor con identificativi invalidi: errore nel modulo,
  senza perdere la bozza; chiusura con modifiche richiede conferma.

Le immagini finali E03–E06 riutilizzano gli snapshot delle vere corse iniziali
per confrontare esattamente gli stessi dati. Una fascia visibile le identifica
come istantanee registrate, senza simulazione in corso. Non sono prove di una
nuova esecuzione. Le fixture sintetiche dei test browser sono dichiarate da
una fascia diversa e restano esclusivamente nei test.

Artefatti locali, ignorati da Git: `.local/ui-review/before/` e
`.local/ui-review/after/`. Sono stati aperti e controllati gli screenshot di
pagina iniziale, quattro esempi, messaggi, analisi, impostazioni ed editor.
Il confronto più diretto è `before/e05_multihop.png` rispetto a
`after/e05_multihop.png`; l'editor è in `after/editor-drones.png` e
`after/editor-half-width.png`.

Controlli browser alle dimensioni 1920×1080, 1440×900, 1366×768, 740×900 e
390×844: mappa e comandi utilizzabili, dialoghi accessibili e nessun overflow
orizzontale della pagina. Su finestre basse o strette serve scorrimento
verticale; le tabelle e i dettagli lunghi hanno il proprio scorrimento.
Non si dichiara che ogni dettaglio entri contemporaneamente nello schermo.

## Scenari personali

L'editor usa lo schema `Scenario`, senza un formato parallelo. Verificati:
tre droni, trascinamento delle posizioni con aggiornamento dei numeri,
waypoint, relay statico, salvataggio, modifica e ricaricamento, duplicazione
di E03, importazione/esportazione YAML, cancellazione annullata e confermata,
rimozione dei riferimenti di un drone e rifiuto delle configurazioni invalide.
I sei esempi distribuiti restano identici e protetti anche negli endpoint.

La libreria applica nomi univoci normalizzati, ID generati dal server,
validazione Pydantic, YAML sicuro, limiti di dimensione, protezione dei percorsi,
lock OS tra processi, sostituzione atomica e revisioni SHA256. Sono provati
conflitti tra gestori, salvataggio interrotto prima della sostituzione,
rilascio del lock dopo uscita del processo e persistenza tra istanze.
È stato anche riavviato realmente il server di verifica: scenario e revisione
sono rimasti identici; lo scenario di prova è stato poi eliminato.

Un caso personale è stato creato e avviato dalla UI con tre HoveringAUV,
posizioni iniziali X 0/30/60 m, Z −20 m, flusso Drone 01 → Drone 03 e route
via Drone 02. HoloOcean e DESERT erano reali. Inoltro sul relay osservato,
posizioni effettive dei tre sensori disponibili; pausa a 4,2 s con tempo
fermo, ripresa e arresto a 6,167 s. Risultato all'arresto: **2 generati,
2 ricevuti, 0 scaduti, 0 pendenti**; entrambi i simulatori arrestati.
Verificati esportazione ZIP, reset e cancellazione dello scenario di prova.
Nessun errore JavaScript durante la prova conclusiva.

`after/custom-real.png` e `custom-real-results.zip` sono acquisiti alla pausa
(2 generati, 1 ricevuto, 1 pendente). `custom-real-summary.json` contiene il
risultato successivo all'arresto: non va confuso con lo ZIP intermedio.
Tutti questi file sono sotto `.local/ui-review/` e non versionati.

## Test e distribuzione

| Verifica | Esito |
|---|---|
| Python Windows, `pytest -q -m 'desert or not desert'` | 53 passati, 1 saltato, 15 warning |
| Solo unitari Linux, Python 3.12 in Docker | 41 passati, 1 warning |
| Playwright, `npm.cmd --prefix tests/frontend test` | 13 passati |
| Wheel, `pip wheel . --no-deps` | compilato, risorse UI e libreria incluse |
| Persistenza con riavvio del processo HTTP | configurazione e revisione identiche |

La suite Windows comprende 11 test DESERT e 2 end-to-end HoloOcean.
Il test saltato richiede privilegi per creare un symlink su questo Windows;
la stessa protezione è verificata dal test Linux. I warning vengono da
Starlette/AnyIO e Matplotlib/Pyparsing esistenti. La CI comprende ora un job
browser Linux, ma non è stata eseguita su GitHub: nessun push effettuato.

## Limiti conservati

OpenWater e HoveringAUV sono le sole opzioni verificate dell'editor.
I waypoint rimangono target del controller HoloOcean, il routing è statico.
Nessun nuovo motore, protocollo, algoritmo applicativo o calcolo delle
metriche è stato introdotto. Orchestratore, sincronizzazione, collector,
adapter dei simulatori e YAML originali non sono stati modificati.
Generazione, TX, ricezione PHY, consegna applicativa e scadenza restano
distinte: non vengono inventate collisioni né cause di perdita.

Il servizio aggiornato viene lasciato inattivo su http://127.0.0.1:8000.
Prima di riavviare la precedente dashboard già conclusa, i suoi risultati
sono stati conservati in `.local/ui-review/pre-existing-results.zip`.
Le prove non producono salvataggi automatici delle corse ordinarie.
