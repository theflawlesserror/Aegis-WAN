# Aegis-WAN: Intelligent Edge-AI Routing Architecture
**System Context & Technical Blueprint (v2.2)**

## 1. Project Overview
* **Objective:** Develop an autonomous networking solution for remote edge sites (vessels, trucks, field hospitals) to dynamically steer traffic across a Dual-WAN setup (Satellite/Starlink and 5G Cellular).
* **Control Architecture:** "Sidecar" control model. The Data Plane is managed by an enterprise SD-WAN router (Cisco vManage simulated). The Control Plane (the AI brain) runs on an adjacent edge compute device.
* **Hardware Target:** Raspberry Pi 4B (2GB RAM). 

## 2. Mathematical Framework: Contextual Multi-Armed Bandit (CMAB)
The system eschews static routing rules in favor of a Reinforcement Learning (RL) agent operating as a Contextual Multi-Armed Bandit.
* **Goal:** Maximize the Reward ($R$) for every routing decision.
* **Reward Function:** $R = (W_{perf} \cdot P) - (W_{cost} \cdot C) - \eta$
  * $P$: Application Performance (measured via App-Route Video QoE).
  * $C$: Operational Cost (statically mapped; e.g., Satellite = High, 5G = Medium).
  * $\eta$: Switching Penalty (prevents route flapping).

## 3. Edge-Optimized Feature Engineering (The 24-Feature Tensor)
To respect the strict 2GB RAM limit while avoiding feature leakage, the State Vector ($S_t$) relies on a 24-dimensional tensor heavily optimized with categorical One-Hot Encoding and defensive input validation. Ethernet/MPLS has been deprecated in favor of a strictly Dual-WAN approach. ThousandEyes geopolitical scores have been deprecated and removed pending a future integration decision.

**The State Vector ($S_t$) - Input Features:**
* **1-6: App-Route Telemetry** (Latency, Loss %, Jitter for Sat & 5G). Source: `POST /dataservice/statistics/approute`
* **7-8: Physical Hardware Status** (TLOC Binary 1/0 for Sat & 5G). Source: `GET /dataservice/device/tloc`
* **9-12: QoS Base Telemetry** (Drop in kbps, Queued Pkts for Sat & 5G). Source: `POST /dataservice/statistics/qos/aggregation`
* **13-20: QoS Queue ID (One-Hot Encoded)** (Voice, Video, Data, Default arrays for Sat & 5G). Source: `POST /dataservice/statistics/qos/aggregation`
* **21: Active Policy Status** (Boolean mapped to 1.0/0.0). Source: `GET /dataservice/template/policy/vsmart`
* **22-24: Active Link Color (One-Hot Encoded)** (biz-internet, cellular, default array). Source: `GET /dataservice/template/policy/vsmart`

## 4. API & Action Mapping (Cisco vManage Simulation)
The CMAB interacts with the physical network via RESTful Northbound APIs.

* **The Action ($A_t$):** * `PUT /dataservice/template/policy/definition/approute/{policy_id}` (Update preferred link).
  * `POST /dataservice/template/policy/vsmart/activate/{policy_id}` (Push policy to hardware).
* **The Reward Feedback ($R_t$):**
  * `POST /dataservice/statistics/approute` (Extract `vqoe_score` for Performance $P$).
  * `GET /dataservice/device/action/status/{task_id}` (Closed-Loop Verification. Hardware failure results in a severe mathematical penalty).

## 5. Perception Layer Architecture (PyTorch)
A Multi-Layer Perceptron (MLP) acts as the early-warning radar, classifying the current 24-D tensor state into 0 (Stable), 1 (Degrading), or 2 (Failing).
* **Structure:** `Linear(24, 64)` $\to$ `ReLU` $\to$ `Dropout(0.3)` $\to$ `Linear(64, 16)` $\to$ `ReLU` $\to$ `Dropout(0.3)` $\to$ `Linear(16, 3)`.
* **Data Handling:** Implements `WeightedRandomSampler` to correct class imbalances and ensure rare failure events are heavily weighted during training.
* **Safety:** Deep defensive programming ensures missing/malformed JSON payloads fall back to safe default matrices instead of crashing the edge agent.

## 6. Deployment Strategy & Chaos Engineering
1. **Perception Training (Phase 1 & 2):** Python-based pipeline.
2. **Data Generation (Phase 2.5):** A "Chaos Engineering Sandbox" will poll the API while a secondary script randomly attacks the network via `POST /sim/control/health/{system_ip}/{link_type}` to generate high-fidelity, correlated training data. Valid `link_type` values are `'Satellite'` and `'5G'` only — `'Ethernet'` is fully deprecated from this project and must not be used as a chaos target.
3. **Edge Inference (Phase 3 & 4):** Export the trained mathematical weights. Write the CMAB UCB logic and inference engine natively in C/C++ to execute the matrix multiplications on the Raspberry Pi in microseconds.

## 7. Supporting & Diagnostic Endpoints
The following endpoints are defined in the simulation API but serve infrastructure and diagnostic roles rather than direct feature engineering. They are not part of the 24-D state vector pipeline.

* `GET /dataservice/device` — Device inventory. Returns `system_ip` for each router. This value is a **required query parameter** (`deviceId`) for both `GET /dataservice/device/tloc` and `POST /sim/control/health/{system_ip}/{link_type}`. Must be called first during agent initialisation to resolve the target device's system IP.
* `GET /dataservice/device/interface` — Real-time interface statistics (rx/tx kbps, MTU, operational status). Not currently ingested by the state vector but available for future feature expansion.
* `POST /dataservice/statistics/interface/aggregation` — Aggregated interface-level drop and throughput counters. Not currently ingested; available as a supplementary signal.
* `GET /dataservice/auditlog` — Administrative audit log. Diagnostic use only.
* `GET /sim/overview` — Human-readable diagnostics dashboard. Was used as a reward feedback source in earlier architecture versions. It is **no longer part of the CMAB reward loop** — reward feedback is sourced exclusively from `POST /dataservice/statistics/approute` (`vqoe_score`). Retain for manual inspection during Chaos Engineering only.

## 8. Current Development Stage
* **Phase 1 (Data Ingestion Pipeline):** Complete (`state_builder.py`).
* **Phase 2 (Perception Model):** Complete (`perception_model.py`).
* **Next Immediate Step:** Once the mock API is live, build the `main.py` asynchronous polling engine and execute Phase 2.5 (Chaos Engineering) to harvest the dataset and train the neural network.
