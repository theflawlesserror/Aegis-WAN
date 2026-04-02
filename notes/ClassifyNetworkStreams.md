
In a Cisco SD-WAN environment, traffic is mapped to specific queues (0–7) based on its priority. Based on the standard Cisco QoS model and the API schemas you provided, here is how you classify your data stream:

### 1\. Traffic Classification Logic

| Traffic Type | Queue Index | Latency/Jitter Fingerprint | Drop Tolerance |
| :--- | :--- | :--- | :--- |
| **VoIP (Voice)** | **Queue 0** (Low Latency) | **Latency:** \< 150ms<br>**Jitter:** \< 30ms | **ZERO.** Even 1% loss causes "robotic" voices. |
| **Surveillance (Video)** | **Queue 2** (Interactive) | **Latency:** \< 300ms<br>**Jitter:** High but buffered | **Low.** High throughput (rx\_kbps) with steady flow. |
| **Emails/Web (Bulk)** | **Queue 3** (Default) | **Latency:** Variable<br>**Jitter:** Not critical | **High.** TCP retransmits handle drops. |

**How to classify using your JSON:**

  * **Check the `interface` and `queue_name`:** If your `/statistics/qos/aggregation` response shows high `tx_pkts` on a queue labeled `Queue0` or `RealTime`, that is your **VoIP** traffic.
  * **Look for Throughput Consistency:** **Surveillance footage** will show a high, constant `rx_kbps` / `tx_kbps` on the interface aggregation, whereas **Emails** will appear as short, "bursty" spikes in data.

-----

### 2\. The Relevant Endpoints

To perform this classification programmatically in your Aegis-WAN engine, you need to pull from these three specific locations in the Swagger docs:

#### A. The Queue Monitor (The "What")

  * **Endpoint:** `POST /dataservice/statistics/qos/aggregation`
  * **Why:** This is the only place that breaks down traffic by **Queue**. You can see exactly which "bucket" the traffic is falling into. If you see drops in the `LowLatencyQueue`, your VoIP is dying.

#### B. The Application Health (The "Experience")

  * **Endpoint:** `POST /dataservice/statistics/approute`
  * **Why:** This gives you the `vqoe_score` (Video Quality of Experience) and `jitter`.
      * **VoIP/Video:** A low `vqoe_score` while `latency` is high tells you the "Surveillance" or "Voice" stream is failing.

#### C. The Policy Match (The "Rule")

  * **Endpoint:** `GET /dataservice/template/policy/vsmart/definition/data/{id}`
  * **Why:** This endpoint reveals the actual rules. It will show you that "Traffic with DSCP 46 (EF)" is being mapped to "Queue 0". This is the "dictionary" that tells your app that Queue 0 = Voice.

### Summary for your Python Logic:

1.  **Query** the QoS Aggregation endpoint to find out which **Queue Index** has the most active `tx_pkts`.
2.  **Cross-reference** that Index with your Policy Definition to see the **Application Name** or **DSCP Tag**.
3.  **Monitor** the App-Route stats for that specific color to see if the **Jitter** is too high for that traffic class.

**Would you like me to draft the specific Python `POST` payload for the QoS aggregation so you can filter it by Queue Index?**
