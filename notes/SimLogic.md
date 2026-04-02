This is the definitive blueprint for the **Aegis-WAN** engine’s simulation and logic flow, strictly mapped to your provided Cisco vManage Swagger specification.

### Required Endpoints for Simulation

**Data Plane / Observability (The "Eyes"):**
* **/dataservice/device**: To discover the `system-ip` (deviceId) of the router.
* **/dataservice/device/tloc**: To identify which "Colors" (e.g., `mpls`, `public-internet`) are active on the device.
* **/dataservice/device/interface**: To map those colors to physical hardware (e.g., `Cellular0` for 5G vs `GigabitEthernet1` for Satellite).
* **/dataservice/statistics/approute**: To pull real-time BFD metrics (Latency, Jitter, Loss) for each color.
* **/dataservice/statistics/interface/aggregation**: To monitor physical packet drops and bandwidth trends over time.
* **/dataservice/statistics/qos/aggregation**: To identify which specific traffic queues (VoIP vs. Bulk) are suffering from congestion.

**Control Plane / Policy (The "Hands"):**
* **/dataservice/template/policy/definition/approute/{id}**: To GET the current logic definition of the traffic-steering rules.
* **/dataservice/template/policy/definition/approute**: To PUT (update) the policy definition with a new "Preferred Color."
* **/dataservice/template/policy/vsmart/activate/{id}**: To push the updated policy to the vSmart controllers, making the switch live.
* **/dataservice/device/action/status/{taskId}**: To monitor the success or failure of the configuration push.

---

### Example Workflow: The "Strait of Hormuz" Scenario

**1. Data Collection (Aegis "Pulls")**
Aegis calls `/statistics/approute` and `/statistics/qos/aggregation`. It retrieves a JSON showing that the `public-internet` (5G) link has a latency of 45ms, but `tx_drops` on `Queue0` (VoIP) have jumped from 0% to 8% in the last 60 seconds.

**2. The Calculation (The "Brain")**
Aegis calculates a **Degradation Trend**. It doesn't just see a single drop; it calculates that the *rate of change* in packet loss is increasing exponentially (a sign of active signal jamming). It compares this against the `tloc` data, noting that the only alternative is `mpls` (Satellite).
* **Aegis Logic:** If (Predicted Loss in 30s > 15%) AND (Current Latency < Satellite Baseline), initiate **Make-Before-Break**.

**3. Preparing the Switch**
Aegis calls `GET /template/policy/definition/approute`. It parses the JSON to find the sequence matching "Voice Traffic." It modifies the `preferred-color` from `public-internet` to `mpls`. 

**4. Executing the Switch**
Aegis sends a `PUT` request to update the policy definition, followed by a `POST` to `/vsmart/activate`. The vManage API returns a `taskId`. 

**5. Verification**
Aegis polls `/device/action/status` until the task is "Success." It then checks `/statistics/approute` again to confirm that the `vDevice-dataKey` for the Voice flow has moved to the `mpls` color.



---

### Critical Gotchas and Failure Cases

**1. The "Policy Lock" Failure**
* **The Case:** If another administrator (or another script) is currently pushing a change to vManage, your `POST /vsmart/activate` will return a `400 Bad Request` or `409 Conflict` because the "Configuration Database" is locked.
* **Aegis Solution:** Your simulator must handle **Task Serialization**. You must check for an active `taskId` before attempting a switch.

**2. The "MTU Black Hole" (Post-Switch)**
* **The Case:** You successfully switch to Satellite. The BFD status says "Up." However, because you didn't lower the MTU/MSS during the switch, your encrypted 1500-byte packets are being dropped by the satellite provider. 
* **Aegis Solution:** The engine must monitor `/statistics/interface/aggregation` *after* the switch. If `tx_drops` remain high despite a "Green" BFD status, it must trigger an emergency MTU reduction via an Interface Template update.

**3. The "Ping-Pong" Effect (Flapping)**
* **The Case:** 5G gets jammed, Aegis switches to Satellite. 5G clears up for 2 seconds, Aegis switches back. 5G gets jammed again. This creates a "flapping" state that destroys VoIP calls.
* **Aegis Solution:** Implement a **Hysteresis Timer**. Once a switch to Satellite occurs, forbid a switch-back for a minimum of 300 seconds (5 minutes) regardless of 5G recovery.

**4. The "Asynchronous Gap"**
* **The Case:** Your script assumes the switch is instant. It starts sending high-bandwidth data before the vSmart has actually pushed the new routes to the router.
* **Aegis Solution:** Use the `taskId` status. Aegis must not consider the switch "Complete" until the API returns a status of `Success` for the activation task.
