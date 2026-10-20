# Usare il laboratorio

Avviare `holo-desert dashboard`, aprire http://127.0.0.1:8000 e scegliere uno
scenario. I sei esempi presentano una descrizione in italiano, cosa osservare,
numero di droni e durata. Nessuna simulazione parte aprendo la pagina.
**Come funziona** e le icone `?` spiegano le operazioni e i termini meno comuni.

## Simulazione, messaggi e analisi

La vista **Simulazione** unisce mappa, comunicazioni, dettagli contestuali e
ultimi messaggi. La mappa XY mantiene la stessa scala sui due assi. Posizioni,
orientamento, profondità e distanze 3D provengono dai sensori HoloOcean.
Rotella per zoom, trascinamento per pan, **Adatta mappa** per ripristinare
l'inquadratura. Le traiettorie percorse sono distinte dai waypoint desiderati
dell'editor. Il browser non sostituisce il mondo 3D HoloOcean.

Selezionare un drone per le sue informazioni, oppure un messaggio per isolare
il percorso e leggere la timeline. Le frecce blu seguono TX/RX PHY osservate;
la consegna applicativa finale è verde e tratteggiata, con il relativo tempo.
Una consegna passata non certifica che il collegamento sia ancora disponibile.
**Livelli** permette di mostrare le route configurate, grigie e tratteggiate.
Queste route non garantiscono raggiungibilità. Gli ascolti PHY di pacchetti
destinati ad altri droni restano nei dettagli, senza creare consegne grafiche.

**Messaggi** filtra per drone, destinatario, tipo, stato e, facoltativamente,
evento tecnico. I dettagli mostrano solo le fasi effettivamente osservate,
distinguendo applicazione, inoltro di rete e PHY. Il JSON originale, payload
ed envelope, contatori e dettagli completi rimangono espandibili.

Un messaggio generato non è necessariamente trasmesso. “Trasmissione osservata”
descrive la storia, non una radio tuttora in trasmissione. La coda MAC e gli
scarti sono aggregati per nodo: non sono disponibili per singolo UUID.
Un errore PHY non prova la perdita applicativa finale; una scadenza TTL indica
mancata consegna entro il tempo di validità, causa ignota. Il TTL applicativo
non annulla un frame già accodato nel MAC.

Nella vista principale:

- **Generati:** messaggi creati dalle applicazioni.
- **Ricevuti:** consegne applicative entro TTL.
- **Consegna riuscita:** ricevuti / (ricevuti + scaduti), in percentuale;
  i messaggi pendenti sono esclusi.
- **Latenza:** media cumulativa dalla generazione alla consegna, usando il
  tempo simulato NS; ultimo campione disponibile.

**Analisi** divide consegna, canale acustico, movimento/tempo e confronto MAC.
Goodput: bit di payload consegnato al secondo nell'intervallo campionato.
Throughput: bit dell'envelope JSON/base64 consegnato, senza header PHY/MAC,
ACK o ritrasmissioni. La coda MAC è campionata a 1 Hz: picchi intermedi non
osservati. N/D e vuoti nei grafici non vengono trasformati in zeri fittizi.
Le metriche di consegna sono globali; si seleziona il drone per PHY/code e
la coppia per la distanza. La deriva è tempo reale meno simulato, esclusa pausa.

Nelle statistiche avanzate restano contatori per nodo, route effettive, eventi
del canale, transizioni HOLD/PROCEED e cambi di potenza E06. `app_received`
DESERT precede il controllo TTL Python e può includere ricezioni tardive.

## Impostazioni e controlli

**Impostazioni** mostra MAC, bitrate e potenza. Dettagli avanzati: frequenza,
banda, buffer, tentativi, ACK, route statiche, flussi e modalità solo DESERT.
L'editor JSON rimane un'opzione avanzata: **Campi → JSON**, modifica, **JSON →
Campi**. Il backend valida prima dell'applicazione e nuovamente all'avvio.
Le modifiche valgono per una nuova corsa, senza cambiare quella corrente.

La modalità completa avvia HoloOcean nativo e DESERT Docker. Solo DESERT usa
posizioni fisse dichiarate, senza fisica: non è disponibile per movimento o
coordinamento. Non esistono fallback di rete Python.

Pausa ferma entrambi i motori alla barriera; ripresa prosegue dagli stessi
orologi. Durante l'avvio sono mostrati stato e inizializzazione dei servizi.
`stopping` include il teardown: reset e nuovo avvio attendono il suo termine.
Gli errori hanno spiegazione breve, dettagli espandibili e comando diagnostico.

Per confrontare E04, completare una corsa, **Conserva riepilogo corrente**,
cambiare soltanto MAC e ripetere. L'intera configurazione escluso il protocollo
deve coincidere. Due riepiloghi in memoria, conservati anche dopo reset fino
alla chiusura del server; esportazione JSON manuale, nessuna campagna automatica.

## I miei scenari

**Nuovo scenario** parte da impostazioni predefinite; **Duplica** conserva la
configurazione dell'esempio o dello scenario personale, senza alterare l'originale.
Cinque passaggi:

1. Nome, descrizione, durata, ambiente; frequenza fisica nelle opzioni avanzate.
2. Da 2 a 32 droni, ID univoci `auv_NN`, X/Y/Z in metri, yaw in gradi e waypoint
   ordinati per tempo. Profondità = −Z. La mappa di anteprima permette di
   trascinare le posizioni iniziali; non rappresenta osservazioni di una corsa.
3. Mittente/destinatario, intervallo e payload; tempi, TTL e risposta nei dettagli.
4. MAC, acustica e route statiche; senza override il next hop è la destinazione.
5. Riepilogo, validazione e salvataggio; possibilità di avviare subito dopo.

OpenWater e HoveringAUV sono le scelte verificate dell'editor. Gli YAML
importati conservano eventuali altri ambienti: richiedono un'installazione
HoloOcean compatibile. Non sono stati aggiunti modelli di veicolo o algoritmi.
Gli scenari heartbeat duplicati mantengono l'applicazione esistente a due nodi;
non accettano flussi ordinari aggiuntivi. Eventi di potenza importati sono
conservati nel formato completo, senza un nuovo editor di autonomia.

Rinominare un ID aggiorna i riferimenti; rimuovere un drone rimuove, dopo
conferma, flussi, route e power event che lo usano. Un salvataggio inconsistente
è rifiutato. Durante una corsa le modifiche sono disabilitate. L'eliminazione
di uno scenario personale richiede conferma; esempi protetti anche negli endpoint.

**Importa YAML** apre una bozza da controllare e salvare. **Esporta YAML**
scarica lo stesso schema Pydantic `Scenario` usato dalla CLI. Nessun secondo
formato di configurazione è stato introdotto.

Directory predefinite:

- Windows: `%LOCALAPPDATA%/HoloOceanDESERT/scenarios`.
- Linux: `$XDG_DATA_HOME/holo-desert/scenarios`, oppure
  `~/.local/share/holo-desert/scenarios`.
- Override: variabile `HOLO_DESERT_SCENARIOS_DIR`, anche verso un disco portabile.

Per tenere anche la libreria sul disco del progetto, prima dell'avvio:

```powershell
$env:HOLO_DESERT_SCENARIOS_DIR = Join-Path (Get-Location) 'user_scenarios'
.venv\Scripts\holo-desert.exe dashboard
```

Usare la stessa directory negli avvii successivi; le configurazioni sono
normali file YAML e possono essere copiate insieme al progetto.

Gli scenari sopravvivono a riavvii e aggiornamenti. I file usano ID generati
dal server, senza percorsi forniti dal browser. Nomi personali univoci, limite
256 KiB, YAML sicuro, lock tra processi, salvataggio temporaneo + `fsync` +
`os.replace`, revisioni SHA256: una modifica concorrente produce HTTP 409 e
richiede ricaricamento. Il file `.library.lock` resta nella directory, ma il
lock OS viene rilasciato anche se il processo termina. La CLI continua ad
accettare YAML arbitrari; accetta anche gli ID personali `user_…` della libreria.

## Esportazione e memoria

I risultati ordinari sono temporanei. **Esporta risultati** salva manualmente
configurazione, eventi JSONL e pacchetti CSV. Esportare prima del reset o della
chiusura; `--persist` rimane l'opzione CLI per la persistenza esplicita.
I salvataggi personali riguardano configurazioni, non risultati automatici.

Limiti conservati: 500 pacchetti esposti, 5.000 conservati, 256 eventi per
pacchetto con troncamento dichiarato, 300 osservazioni topologiche, 200 punti
di traiettoria per nodo, 1.000 campioni, 100 transizioni e due confronti.
Il JSONL temporaneo mantiene la storia completa fino al reset.

Verifiche visive e limiti: [revisione UI](ui-review.md).
