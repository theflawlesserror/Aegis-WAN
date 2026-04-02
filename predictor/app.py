import asyncio
import httpx
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from typing import Dict
from pretrain import build_pretrained_models

from predictor import StreamPredictor

# -------------------------------------------------------------------
# Core Routing Logic
# -------------------------------------------------------------------
class HysteresisEngine:
    """
    Switches to whichever link has the highest predicted vQoE score.

    Anti-flap debounce: a candidate must be best for `sustained_ticks`
    consecutive ticks before a switch is committed. This prevents chasing
    transient spikes without adding the large latency of the old 3-tick
    + 1.5-delta design that was masking degraded-5G -> Satellite transitions.

    No primary/preferred-color logic — pure best-link wins.
    confirm_switch() must be called by the poller after the vManage
    activation API returns success so engine state stays in sync.
    """
    def __init__(self, delta_threshold=0.5, sustained_ticks=2):
        self.active_link = None
        self.delta_threshold = delta_threshold   # min margin to be considered "better"
        self.sustained_ticks = sustained_ticks   # consecutive ticks required before switch
        self.candidate_link = None
        self.consecutive_ticks = 0

    def evaluate(self, current_predictions: Dict[str, float]) -> str:
        if not current_predictions:
            return None

        if self.active_link is None or self.active_link not in current_predictions:
            # Bootstrap: latch onto best link, no policy push needed.
            self.active_link = max(current_predictions, key=current_predictions.get)
            return None

        best_link = max(current_predictions, key=current_predictions.get)
        best_score = current_predictions[best_link]
        active_score = current_predictions[self.active_link]

        # A switch is warranted when the best link beats the active one by
        # at least delta_threshold — rules out noise-level oscillations.
        if best_link != self.active_link and (best_score - active_score) >= self.delta_threshold:
            if self.candidate_link == best_link:
                self.consecutive_ticks += 1
            else:
                # New candidate — reset counter so we don't carry over ticks
                # from a previously flapping link.
                self.candidate_link = best_link
                self.consecutive_ticks = 1

            if self.consecutive_ticks >= self.sustained_ticks:
                self.consecutive_ticks = 0
                self.candidate_link = None
                return best_link  # caller must confirm_switch() on API success
        else:
            # Active link is best (or within noise margin) — reset debounce.
            self.consecutive_ticks = 0
            self.candidate_link = None

        return None

    def confirm_switch(self, link: str):
        """Commit active_link only after the upstream policy push has succeeded."""
        self.active_link = link

# -------------------------------------------------------------------
# State Management
# -------------------------------------------------------------------
VMANAGE_BASE_URL = "http://localhost:8000"
POLL_INTERVAL_SECONDS = 2.0
MAX_LOG_HISTORY = 100 

class DeviceState:
    def __init__(self, system_ip: str, initial_active_link: str = None):
        self.system_ip = system_ip
        # Instead of initializing empty models, we load the pre-warmed models
        self.models = build_pretrained_models(num_samples=3000)

        self.routing_engine = HysteresisEngine()
        # Seed the engine with the policy actually active in vManage right now.
        # Without this, the engine bootstraps from whichever link scores highest
        # on the first prediction tick — which can diverge from vManage reality
        # and cause the engine to think it's already on the better link, silently
        # suppressing switches that are genuinely needed.
        if initial_active_link:
            self.routing_engine.active_link = initial_active_link
        self.logs = []
        self.pending_task_id = None

    def add_log(self, entry: dict):
        self.logs.append(entry)
        if len(self.logs) > MAX_LOG_HISTORY:
            self.logs.pop(0)

managed_devices: Dict[str, DeviceState] = {}
policy_map: Dict[str, str] = {} 

# -------------------------------------------------------------------
# Background Polling Task
# -------------------------------------------------------------------
async def poll_vmanage():
    async with httpx.AsyncClient() as client:
        # --- PHASE 0: Fetch and map vSmart Policies on startup ---
        try:
            pol_res = await client.get(f"{VMANAGE_BASE_URL}/dataservice/template/policy/vsmart")
            pol_res.raise_for_status()
            policies = pol_res.json().get("data", [])
            
            print(f"[*] Found {len(policies)} policies on the vManage mock:")
            for p in policies:
                raw_name = str(p.get("policyName", ""))
                name = raw_name.lower()
                print(f"    - {raw_name} (ID: {p.get('policyId')})")
                
                # Map to the specific Aegis simulation policies
                if "vessel" in name:
                    policy_map["5G"] = p.get("policyId")
                elif "failover" in name:
                    policy_map["Satellite"] = p.get("policyId")
                    
            print(f"[*] Initialized vSmart Policy Map: {policy_map}")
            
            if not policy_map:
                print("[!] WARNING: Policy Map is completely empty! Route switching will NOT execute.")
                
        except Exception as e:
            print(f"[!] Warning: Failed to fetch vSmart policies. Route switching will fail. Error: {e}")

        step = 0
        while True:
            step += 1
            try:
                dev_res = await client.get(f"{VMANAGE_BASE_URL}/dataservice/device")
                dev_res.raise_for_status()
                
                device_id_to_ip = {}
                known_ips = set()
                ip_to_preferred_color = {}
                for d in dev_res.json().get("data", []):
                    d_id = str(d.get("device_id", "")).lower()
                    s_ip = d.get("system_ip")
                    if d_id and s_ip:
                        device_id_to_ip[d_id] = s_ip
                        known_ips.add(s_ip)
                        ip_to_preferred_color[s_ip] = d.get("preferred_color", "")

                app_res = await client.post(f"{VMANAGE_BASE_URL}/dataservice/statistics/approute")
                app_res.raise_for_status()
                telemetry_data = app_res.json().get("data", [])

                ip_payloads = {}
                for link_data in telemetry_data:
                    raw_device_id = str(link_data.get("vdevice-name", ""))
                    system_ip = device_id_to_ip.get(raw_device_id.lower())
                    
                    if not system_ip and raw_device_id in known_ips:
                        system_ip = raw_device_id

                    if not system_ip:
                        continue

                    if system_ip not in ip_payloads:
                        ip_payloads[system_ip] = []
                    ip_payloads[system_ip].append(link_data)

                for system_ip, links_data in ip_payloads.items():
                    if system_ip not in managed_devices:
                        # Seed the engine from the preferred_color already returned in
                        # the device list — no extra HTTP call needed.  This ensures the
                        # engine starts knowing which link vManage is currently enforcing
                        # rather than guessing from the first tick of ML predictions, which
                        # could be the wrong link and permanently suppress needed switches.
                        preferred_color = ip_to_preferred_color.get(system_ip, "")
                        if "cellular" in preferred_color or "5g" in preferred_color:
                            initial_link = "5G"
                        elif "biz-internet" in preferred_color or "satellite" in preferred_color:
                            initial_link = "Satellite"
                        else:
                            initial_link = None
                        print(f"[*] Discovered new device: {system_ip} (initial active link: {initial_link or 'unknown, will bootstrap from scores'})")
                        managed_devices[system_ip] = DeviceState(system_ip, initial_active_link=initial_link)

                    state = managed_devices[system_ip]
                    
                    if state.pending_task_id:
                        try:
                            status_res = await client.get(f"{VMANAGE_BASE_URL}/dataservice/device/action/status/{state.pending_task_id}")
                            status_res.raise_for_status()
                            task_data = status_res.json().get("data", [])
                            
                            if task_data and str(task_data[0].get("status", "")).lower() in ["in_progress", "processing"]:
                                continue 
                            else:
                                print(f"[*] {system_ip}: Policy activation {state.pending_task_id} resolved. Resuming ML loop.")
                                state.pending_task_id = None 
                        except Exception as e:
                            print(f"[!] Warning: Failed to check task status for {system_ip}: {e}. Releasing lock.")
                            state.pending_task_id = None

                    iface_res = await client.get(
                        f"{VMANAGE_BASE_URL}/dataservice/device/interface", 
                        params={"deviceId": system_ip}
                    )
                    
                    logical_iface_stats = {"5G": {"rx": 0.0, "tx": 0.0}, "Satellite": {"rx": 0.0, "tx": 0.0}}
                    
                    if iface_res.status_code == 200:
                        for i in iface_res.json().get("data", []):
                            if_name_safe = str(i.get("if-name", "")).lower()
                            rx = float(i.get("rx-kbps", 0) or 0)
                            tx = float(i.get("tx-kbps", 0) or 0)
                            
                            if "cellular" in if_name_safe or "lte" in if_name_safe:
                                logical_iface_stats["5G"] = {"rx": rx, "tx": tx}
                            elif "gigabitethernet" in if_name_safe or "ethernet" in if_name_safe:
                                logical_iface_stats["Satellite"] = {"rx": rx, "tx": tx}

                    current_predictions = {}
                    log_entry = {"step": step, "links": {}, "routing_update": None}

                    for link_data in links_data:
                        safe_color = str(link_data.get("local-color", "")).lower()

                        if safe_color.startswith("cellular") or "lte" in safe_color or "5g" in safe_color:
                            logical_link = "5G"
                        elif safe_color.startswith("gigabitethernet") or "ethernet" in safe_color or "biz-internet" in safe_color:
                            logical_link = "Satellite"
                        else:
                            continue

                        link_iface = logical_iface_stats[logical_link]

                        features = {
                            "latency": float(link_data.get("latency") or 0.0),
                            "jitter": float(link_data.get("jitter") or 0.0),
                            "loss": float(link_data.get("loss_percentage") or 0.0),
                            "rx_kbps": link_iface["rx"],
                            "tx_kbps": link_iface["tx"]
                        }
                        
                        actual_vqoe = float(link_data.get("vqoe_score") or 0.0)
                        
                        predicted_vqoe = 0.0
                        # If the simulator outputs 0 latency and 0 score, the link is physically dead.
                        # Do not train the model on this payload, or it will learn that 0 latency = bad!
                        if features["latency"] == 0 and actual_vqoe == 0:
                            predicted_vqoe = 0.0
                        else:
                            # Only train and predict on valid telemetry
                            predicted_vqoe = state.models[logical_link].process_telemetry(features, actual_vqoe)
                        # -----------------------------------------

                        current_predictions[logical_link] = predicted_vqoe

                        log_entry["links"][logical_link] = {
                            "actual_vqoe": actual_vqoe,
                            "predicted_vqoe": round(predicted_vqoe, 2),
                            "rx_kbps": features["rx_kbps"],
                            "tx_kbps": features["tx_kbps"]
                        }

                    if step > 1:
                        switch = state.routing_engine.evaluate(current_predictions)
                        if switch:
                            log_entry["routing_update"] = f"Triggered switch to {switch}"
                            print(f"[!] {system_ip}: Hysteresis triggered path switch to {switch}")

                            target_policy_id = policy_map.get(switch)
                            if not target_policy_id:
                                # policy_map was empty at startup (vManage unreachable).
                                # Log as a hard error — silent skip leaves active_link stale
                                # and blocks all future failbacks (including Satellite->5G).
                                err_msg = f"No policy ID for link '{switch}' — policy_map={policy_map}. Route switch ABORTED."
                                print(f"  -> [!] {system_ip}: {err_msg}")
                                log_entry["routing_update"] = f"ERROR: {err_msg}"
                            else:
                                try:
                                    act_res = await client.post(
                                        f"{VMANAGE_BASE_URL}/dataservice/template/policy/vsmart/activate/{target_policy_id}",
                                        # Pass deviceId so the activation is scoped to this
                                        # vessel only.  Without it, activate_policy was
                                        # fleet-wide: switching Maersk to 5G simultaneously
                                        # overwrote every other vessel's control plane, and
                                        # when any of them later switched to Satellite they
                                        # reverted Maersk too — causing split-brain where
                                        # the engine reported 5G but vManage enforced Satellite.
                                        json={"deviceId": system_ip}
                                    )
                                    act_res.raise_for_status()
                                    task_id = act_res.json().get("id")
                                    state.routing_engine.confirm_switch(switch)
                                    print(f"  -> Successfully activated {switch} policy for {system_ip} (Task ID: {task_id})")
                                    state.pending_task_id = task_id
                                except Exception as e:
                                    # Do NOT confirm: engine will re-evaluate and retry next tick.
                                    print(f"  -> [!] Failed to activate policy for {switch}: {e}")
                                    log_entry["routing_update"] = f"ERROR activating {switch}: {e}"

                    log_entry["active_link"] = state.routing_engine.active_link
                    state.add_log(log_entry)

            except Exception as e:
                print(f"[!] Polling error: {e}")

            await asyncio.sleep(POLL_INTERVAL_SECONDS)

# -------------------------------------------------------------------
# FastAPI Endpoints
# -------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(poll_vmanage())
    yield
    task.cancel()

app = FastAPI(lifespan=lifespan, title="Aegis ML Sidecar")

# Enable CORS for all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/logs")
def get_logs(
    system_ip: str = Query(..., description="Filter logs by system_ip"),
    limit: int = Query(10, description="Maximum number of logs to return (default 10)", ge=1)
):
    if system_ip not in managed_devices:
        raise HTTPException(status_code=404, detail="Device not tracked.")
    
    # Retrieve up to the requested limit, returning the most recent entries
    recent_logs = managed_devices[system_ip].logs[-limit:]
    
    return {
        "system_ip": system_ip,
        "active_link": managed_devices[system_ip].routing_engine.active_link,
        "logs": recent_logs
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8080)
