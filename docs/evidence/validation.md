# Verifiche eseguite — 16 ottobre 2026

Ambiente reale: Windows nativo, Python 3.10.20, HoloOcean/Ocean 2.3.0,
NVIDIA RTX 6000 Ada Generation, Docker Engine 29.8.2 e Compose 5.6.0.
DESERT gira nel container ufficiale Ubuntu 24.04 amd64, fissato al digest
registrato in `dependencies.lock.json`; il processo NS usa le librerie originali.
Nessuna distribuzione WSL personale è usata dal progetto.

**Suite finale: 31 test superati in 82,96 s**: 20 unitari, 9 di integrazione
DESERT e 2 end-to-end con HoloOcean. Comando effettivo:
`python -m pytest -q -m 'desert or not desert'`.
I 15 warning sono deprecazioni delle dipendenze upstream.

## Campione e interfacce ufficiali

- `holo-desert official-sample`: 166 inviati, 166 ricevuti, PDR 100%.
- `holo-desert official-sockets`: TCP esterno bidirezionale verificato, un
  payload per direzione e contatori DESERT TX/RX entrambi `1,1`.
- UDP ufficiale: ingresso e passaggio acustico verificati (`TX=1,1`, `RX=1,1`),
  nessun ritorno dei payload sui client UDP. Il backend integrato usa quindi
  il trasporto framed e l'estensione isolata.
- `holo-desert probe-holo`: due AUV, sensori COM e 30 tick fisici verificati.
- `holo-desert doctor`: tutti i controlli passati dopo l'installazione.

## Dimostrazioni con HoloOcean e DESERT insieme

Tutte le sei configurazioni sono state eseguite con veicoli HoloOcean reali.
Le cifre sono osservazioni del modello con substream 1; non sono misure di un
modem reale. Le esecuzioni di validazione usano `--fast`: cambia il pacing,
non lo scheduler né la timeline logica.

| Demo | Durata logica | Generati | Ricevuti | Timeout TTL | Evidenza |
|---|---:|---:|---:|---:|---|
| E01 chat | 16 s | 2 | 2 | 0 | Richiesta e risposta, stessi ID nel motore e nella dashboard |
| E02 concorrente | 25 s | 24 | 11 | 13 | 11 osservazioni PHY di errore da interferenza, coda massima 3 |
| E03 movimento | 100 s | 45 | 22 | 23 | Distanza 19,7→76,9→20,0 m, perdita e ripresa osservate |
| E04 CSMA-ALOHA | 45 s | 84 | 23 | 61 | Coda MAC raggiunge il limite configurato di 20 |
| E05 multi-hop | 30 s | 3 | 3 | 0 | 3 inoltri osservati su B e ricezione su C |
| E06 coordinazione | 30 s | 29 | 19 | 10 | HOLD/PROCEED reagiscono all'interruzione e al ripristino PHY |

E03, coorti definite dal tempo di generazione: nei primi 12 s arrivano 5/6;
tra 25 e 55 s arrivano 0/15; tra 70 e 100 s arrivano 10/10. Il drone ritorna
realmente alla distanza iniziale, misurata dai sensori. La prima traiettoria,
più lunga, non lasciava al controller PD abbastanza tempo per il rientro:
è stata sostituita con target fisicamente raggiungibili e tempo di assestamento.
Il profilo acustico è rimasto invariato a 105 dB SPL.

E06: follower HOLD iniziale, PROCEED a 1,867 s, HOLD a 10,467 s,
PROCEED a 18,6 s. La potenza del leader viene abbassata nel motore a 8 s e
ripristinata a 18 s. Nessun heartbeat viene eliminato arbitrariamente in Python.

Confronto E04 cambiando **solo** MAC tramite `--mac aloha`: 84 generati,
0 ricevuti, 84 timeout, 28 osservazioni PHY di errore da interferenza e
224 ricezioni non sincronizzate, coda massima 7. I tre flussi sono simultanei:
questo esito negativo è conservato. Il corretto funzionamento ALOHA a basso
carico è verificato separatamente dai test di trasporto binario.

## Esperimenti controllati sul canale DESERT

Fixture spaziali fisse, nessuna fisica sostitutiva Python. Stesso payload,
stesso substream e parametri identici salvo quelli esplicitati:

| Esperimento | Risultato |
|---|---|
| 30 m, 4800 bit/s, 135 dB SPL | RX, ritardo applicativo 0,8866 s |
| 500 m, 4800 bit/s, 135 dB SPL | RX, ritardo applicativo 1,1999 s |
| 30 m, 1200 bit/s, 135 dB SPL | RX, ritardo applicativo 1,9616 s |
| 30 m, potenza 0 dB SPL | Nessuna ricezione applicativa |
| 30 m, trasmissione contemporanea inversa | RX, ritardo 1,4046 s |
| A-B-C, 500 m per tratta, 132 dB SPL | RX a 2,1824 s; nodi di inoltro osservati 1,2 |
| A-C diretto, 1000 m, 132 dB SPL | Nessuna ricezione applicativa; errore osservato al PHY |

Nella variazione 30→500→30 m entro **la stessa sessione**, il test misura
la propagazione fra inizio TX PHY e inizio RX PHY, separandola dal backoff MAC.
La differenza della propagazione cresce di oltre 0,2 s e ritorna al valore
iniziale. Nessuna modifica o ricreazione dei nodi DESERT è necessaria.

L'esplorazione dichiarata della potenza ha trovato che 100–126 dB non consegnano
sulle tratte da 500 m in queste condizioni; 128–135 dB consegnano via relay ma
non direttamente a 1000 m; a 136 dB funziona anche il diretto. E05 usa 132 dB,
all'interno della regione verificata. Non si chiama multi-hop una consegna diretta.

## Installazione Linux e pacchetto

In un container Ubuntu 24.04 pulito con Python 3.12.3 è stato eseguito
`scripts/check_linux_package.sh`: venv, installazione completa del lock,
build `posix_ipc`, installazione del progetto, `pip check` e 18 test unitari
superati. La verifica precede i due test aggiunti per il caso di teardown Windows.
Non include il rendering GPU HoloOcean nativo Linux.

`pip wheel . --no-deps` è riuscito; il wheel contiene tutti i sei YAML,
dashboard, profili, Dockerfile, script server, Tcl, C++ e header di compilazione.
Sintassi JavaScript controllata con `node --check`. HTTP, controlli e ZIP
sono verificati con TestClient; nessun browser automatizzabile era disponibile
per una QA visiva.
È stata inoltre verificata la dashboard HTTP live su `127.0.0.1:8000`:
avvio di E01 standalone attraverso i controlli API, 2 pacchetti reali DESERT
ricevuti, eventi correlati nel Packet Inspector, download ZIP valido e reset
allo stato idle. Il servizio rimane pronto per l'avvio degli scenari dal browser.

## Ripetere le verifiche

```bash
holo-desert engine up
holo-desert official-sample
holo-desert official-sockets
holo-desert test
holo-desert test --integration
holo-desert test --end-to-end
python scripts/validate_channel.py --sweep
python scripts/validate_examples.py
python scripts/validate_examples.py e04_congestion --mac aloha
```

I test includono payload binari, due MAC, più nodi, tempo, variazione della
geometria, potenza/interruzione/ripresa, inoltro reale e controllo diretto,
riavvio NS dopo kill, pausa di entrambi i clock, arresto e API della dashboard.
Gli eventi completi delle prove sono temporanei; solo i riepiloghi espliciti
sono stati usati per questa tabella. I warning upstream sono riportati, non
nascosti come successi né classificati come perdite di pacchetti.
