# API applicativa

```python
comm = communication_manager.drone("auv_01")
packet_id = comm.send(destination="auv_02", payload={"message": "hello"})
packet_id = comm.send("auv_02", b"\x00\xffbinary", ttl=10, priority=0)
for delivery in comm.receive():
    print(delivery.message.source, delivery.message.payload, delivery.network_time)
```

`send` accetta bytes o un dict JSON. `send_json` serializza altri valori JSON.
`receive` restituisce immediatamente una lista, svuotando la coda del proprio nodo.
Nessuna funzione Tcl è accessibile tramite questa API.

Il messaggio v1 contiene `id`, `version`, `source`, `destination`,
`message_type`, `creation_time`, `payload`, `priority`, `ttl`.
Il payload binario viene codificato base64 nell'envelope JSON; il limite DESERT
di 4096 byte si applica all'**intero envelope serializzato**. Le dimensioni
user payload e wire envelope sono mostrate separatamente.

`creation_time` usa il tempo logico corrente. `Delivery.network_time` è il
tempo della ricezione riportato dall'applicazione DESERT. I metadati conservano
tempo d'inserimento nello stack e UID NS, quando presenti.
`transport_observed_wall_time` è un clock diverso e non entra nella latenza.

La priorità è solo metadato applicativo: non modifica il MAC. Il TTL limita la
validità **applicativa**; non annulla un pacchetto già accodato nel MAC.
Un messaggio oltre TTL genera `late_receive` e non viene consegnato all'algoritmo.
Un timeout non prova una perdita fisica né ne identifica la causa.

Le code applicative sono limitate a 1000 elementi. Overflow TX solleva
`BufferError`; overflow RX produce `bridge_receive_overflow` distinto dalle
perdite di rete. I duplicati sono filtrati per ID nel periodo di validità.
Un nodo o destinatario inesistente causa un errore prima dell'inserimento.
Broadcast e stato teorico del link non sono esposti da questo backend iniziale.

Per creare una propria applicazione implementare `update(now, own_pose, received)`
come negli esempi di `core/applications.py`. Un'azione opzionale contiene il
target del controller ufficiale HoloOcean, non una posizione imposta.
