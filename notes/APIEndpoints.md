For the Aegis WAN application, your goal is to transition from reactive to predictive path selection to avoid the "Reactive Switching Gap" and "Satellite Bill Shock". To achieve this, your Python/Flask simulator and logic engine must fetch and simulate specific data points that reflect real-world link degradation, especially in high-tension or contested zones.

Based on the Aegis WAN vision and the vManage API surface, here is the relevant data you should focus on:

### 1. Interface Statistics (Link Identification & "Blindness" Prevention)
To prevent your system from being "geopolitically blind," you must first accurately identify the physical nature of each uplink.

* **Relevant Endpoint:** `GET /statistics/interface/aggregation` or `GET /device/interface`.
* **Data to Fetch/Simulate:**
    * **`if-name` & `vdevice-dataKey`**: Used to map a logical "Color" (e.g., `public-internet`) to a physical port (e.g., `Cellular0/1/0` for 5G or `GigabitEthernet0/1` for Starlink/Satellite).
    * **`oper-status` & `admin-status`**: Basic connectivity checks to see if the link is physically up or down.
    * **`rx_kbps` & `tx_kbps`**: Bandwidth throughput. Sudden drops in throughput while the `oper-status` remains "up" can indicate jamming or a "blackout" scenario.
    * **`mtu`**: Critical for preventing the "MTU Black Hole." Aegis-WAN needs to monitor this to ensure encrypted packets aren't being silently dropped by satellite providers.

### 2. QoS Statistics (Congestion & Cost Control)
QoS data is vital for managing "Satellite Bill Shock" by ensuring only high-priority traffic uses expensive links during a failover.

* **Relevant Endpoint:** `GET /statistics/qos/aggregation`.
* **Data to Fetch/Simulate:**
    * **`drop_in_kbps` / `drop_in_bytes`**: High drop rates in specific queues (like Voice or Video) suggest a link is congested even if BFD says it's "up".
    * **`queued_pkts`**: Indicates buffer bloat, which is common on satellite links and can severely impact real-time VoIP and telemetry.
    * **`tx_pkts` per Queue**: Use this to verify that your "make-before-break" transition actually moved the data to the correct backup link.

### 3. App-Route (BFD) Statistics (Predictive Health)
Aegis-WAN aims to solve the "Reactive Switching Gap" by not waiting for a total link failure. You need fine-grained performance metrics to feed into your Reinforcement Learning (RL) model.

* **Relevant Endpoint:** `POST /statistics/approute`.
* **Data to Fetch/Simulate:**
    * **`latency`**: For satellite links, you should simulate a baseline of 600ms+ (GEO) or 30-100ms (Starlink).
    * **`loss_percentage`**: Standard routers wait for total failure (DPD timers); your application should trigger a switch if this trends upward (e.g., from 0.1% to 2%) before the link fully dies.
    * **`vqoe_score` (Video Quality of Experience)**: A composite metric that provides a quick "health" score for the link, useful for fast decision-making in high-tension zones.

### Summary Table for Simulation

| Data Point | Application Purpose | Simulated "Bad" Condition |
| :--- | :--- | :--- |
| **MTU Value** | Avoid "MTU Black Hole" | Value < 1400 (Fragmentation begins) |
| **Drop in KBPS** | Congestion Detection | > 50 KBPS on critical queues |
| **Loss %** | Predictive Switching | Rising from 0% to 5% (Jammed signal) |
| **Latency** | Link Identification | Spiking from 40ms to 800ms (Failover to SAT) |

By monitoring these specific data points, your Aegis-WAN engine can proactively move traffic from a jammed 5G signal to a satellite link *before* the 30-second blackout occurs.
