from flask import Flask, request, jsonify
from flask_cors import CORS
import random
import time
import uuid
import json
import os

app = Flask(__name__)
CORS(app)

# ==========================================
# DIGITAL TWIN DATABASE (STATEFUL MOCK DATA)
# ==========================================

VESSEL_DB = {}
POLICY_LIST = []

def load_data():
    """Loads the initial fleet state and policies from the local JSON file."""
    global VESSEL_DB, POLICY_LIST
    file_path = 'vessels.json'
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            data = json.load(f)
            VESSEL_DB = data.get("vessels", {})
            POLICY_LIST = data.get("policies", [])
        print(f"Loaded {len(VESSEL_DB)} vessels and {len(POLICY_LIST)} policies into the simulation.")
    else:
        print(f"ERROR: {file_path} not found. Please create it.")
        VESSEL_DB = {}
        POLICY_LIST = []

# Load on startup
load_data()

# Global Control Plane DB
POLICY_DB = {}
TASKS = {}
AUDIT_LOGS = []

# ==========================================
# REALISTIC TELEMETRY GENERATOR
# ==========================================

def _read_live_metrics(transport):
    """
    Pure read: computes and returns current metrics from transport baselines
    without mutating any state. Safe to call multiple times per polling cycle
    without inflating accumulated drop counters.
    Returns: (lat, loss, jit, rx, tx, new_drops, vqoe)
    """
    health = transport["health_percentage"]
    bases = transport["baselines"]

    deg = (100 - health) / 100.0

    lat = int(bases["base_latency_ms"] + (bases["base_latency_ms"] * 5 * deg) + random.randint(-2, 2))
    jit = int(bases["base_jitter_ms"] + (deg * 100) + random.randint(-1, 1))
    loss = round(min(100.0, bases["base_loss_percent"] + (deg * 40.0) + (random.random() if deg > 0 else 0)), 1)

    rx = int(bases["max_rx_kbps"] * (health / 100.0) * random.uniform(0.95, 1.0))
    tx = int(bases["max_tx_kbps"] * (health / 100.0) * random.uniform(0.95, 1.0))

    new_drops = int(deg * random.randint(50, 200))

    vqoe = max(1, int(10 - (deg * 9)))

    return max(1, lat), max(0, loss), max(1, jit), rx, tx, new_drops, vqoe


def get_live_metrics(transport):
    """
    Accumulating wrapper: calls _read_live_metrics() then applies the drop
    accumulation side-effect. Must be called exactly ONCE per polling cycle
    (only from post_approute) so that accumulated_stats reflects one tick
    of real elapsed time, not one tick per endpoint polled.
    All other endpoints call _read_live_metrics() directly.
    """
    lat, loss, jit, rx, tx, new_drops, vqoe = _read_live_metrics(transport)

    transport["accumulated_stats"]["total_tx_drops"] += new_drops
    transport["accumulated_stats"]["total_rx_drops"] += int(new_drops * 0.3)

    return lat, loss, jit, rx, tx, new_drops, vqoe

# ==========================================
# CISCO vMANAGE SIMULATION ENDPOINTS
# ==========================================

@app.route('/dataservice/device', methods=['GET'])
def get_device():
    # Include preferred_color from control_plane alongside identity fields so
    # consumers can bootstrap their active-link state without a separate call.
    # Real vManage includes reachability/policy color in the device list response.
    data = []
    for v in VESSEL_DB.values():
        entry = dict(v["identity"])
        entry["preferred_color"] = v["control_plane"].get("preferred_color", "")
        data.append(entry)
    return jsonify({"data": data})

@app.route('/dataservice/device/tloc', methods=['GET'])
def get_tloc():
    device_id = request.args.get('deviceId')
    if not device_id: return jsonify({"error": {"message": "Missing deviceId"}}), 400
    if device_id not in VESSEL_DB: return jsonify({"data": []}), 200

    vessel = VESSEL_DB[device_id]
    data = []
    for link_name, t in vessel["transports"].items():
        data.append({
            "color": t["sdwan_color"],
            "system-ip": vessel["identity"]["system_ip"],
            "bfdSessionsUp": 6 if t["oper_status"] == "up" else 0,
            "state": t["oper_status"]
        })
    return jsonify({"header": {"generatedOn": int(time.time() * 1000)}, "data": data})

@app.route('/dataservice/device/interface', methods=['GET'])
def get_interface():
    device_id = request.args.get('deviceId')
    if not device_id: return jsonify({"error": {"message": "Missing deviceId"}}), 400
    if device_id not in VESSEL_DB: return jsonify({"data": []}), 200

    vessel = VESSEL_DB[device_id]
    data = []
    for link_name, t in vessel["transports"].items():
        _, _, _, rx, tx, _, _ = _read_live_metrics(t)  # read-only, no drop accumulation
        data.append({
            "if-name": t["physical_interface"],
            "oper-status": t["oper_status"],
            "admin-status": "up",
            "rx-kbps": str(rx),
            "tx-kbps": str(tx),
            "mtu": str(t["mtu"]),
            "ip-address": t["public_ip"]
        })
    return jsonify({"data": data})

@app.route('/dataservice/statistics/approute', methods=['POST'])
def post_approute():
    # BUG-2 FIX: Accept optional deviceId in the request body to scope telemetry
    # to a single vessel. Without this, a multi-vessel VESSEL_DB returns 2×N rows
    # and StateBuilder's [:2] slice silently discards all but the first vessel —
    # correct only by coincidence of dict insertion order. Filtering here makes
    # the contract explicit and safe regardless of fleet size.
    body = request.get_json(silent=True) or {}
    device_filter = body.get("deviceId")

    data = []
    for sys_ip, vessel in VESSEL_DB.items():
        if device_filter and sys_ip != device_filter:
            continue
        for link_name, t in vessel["transports"].items():
            if t["oper_status"] == "down":
                # Dead link — emit zeroed telemetry so the model learns that a
                # down link produces no signal, matching real deployment behaviour.
                # Accumulation is skipped — a down link generates no drops.
                data.append({
                    "vdevice-name": vessel["identity"]["device_id"],
                    "local-color": t["sdwan_color"],
                    "latency": 0,
                    "loss_percentage": 0.0,
                    "jitter": 0,
                    "vqoe_score": 0
                })
            else:
                lat, loss, jit, _, _, _, vqoe = get_live_metrics(t)
                data.append({
                    "vdevice-name": vessel["identity"]["device_id"],
                    "local-color": t["sdwan_color"],
                    "latency": lat,
                    "loss_percentage": loss,
                    "jitter": jit,
                    "vqoe_score": vqoe
                })
    return jsonify({"data": data})

@app.route('/dataservice/statistics/interface/aggregation', methods=['POST'])
def post_interface_aggregation():
    data = []
    for sys_ip, vessel in VESSEL_DB.items():
        for link_name, t in vessel["transports"].items():
            _, _, _, rx, tx, _, _ = _read_live_metrics(t)  # read-only, no drop accumulation
            data.append({
                "vdevice-name": vessel["identity"]["device_id"],
                "interface": t["physical_interface"],
                "rx_drops": t["accumulated_stats"]["total_rx_drops"],
                "tx_drops": t["accumulated_stats"]["total_tx_drops"],
                "rx_kbps": rx,
                "tx_kbps": tx
            })
    return jsonify({"data": data})

@app.route('/dataservice/statistics/qos/aggregation', methods=['POST'])
def post_qos_aggregation():
    """
    Emits exactly ONE QoS row per transport — the shape StateBuilder expects.

    ROOT CAUSE OF TWO BUGS FIXED HERE:

    BUG-C (QoS row count — structural cross-contamination):
      The previous implementation emitted 2 rows per transport (Queue0 +
      Queue3 = 4 rows total for 2 transports). StateBuilder slices the
      response with qos_data[:2], which took rows [0] and [1] — both from
      Satellite. The 5G rows at [2] and [3] were silently dropped, so
      features f11-f12 (5G QoS base) and f17-f20 (5G queue OHE) were
      populated with Satellite Queue3 data in every training row.

    BUG-D (queue_name vocabulary — constant dead one-hot):
      StateBuilder._encode_queue() recognises "Voice", "Video", "Data",
      "Default". The previous values "Queue0" and "Queue3" both fell
      through to the Default else-branch, encoding as [0,0,0,1] for every
      single row regardless of health or transport. Features f13-f20 were
      a constant — zero discriminative signal — across all 3,000 samples.

    FIX — row count: emit exactly 1 row per transport (2 total).
      We represent each transport with its highest-priority active queue
      (Video/Queue3), which carries the strongest health-correlated signal:
      drops escalate at health<100 (all degradation) and queued_pkts grow
      linearly with deg_factor. The Queue0 contribution is absorbed into
      the base noise floor of the single emitted row.

    FIX — queue_name vocabulary: "Video" maps to [0,1,0,0] in
      StateBuilder._encode_queue(). This makes f13-f20 a live discriminator:
      when the active transport is carrying Video-class traffic (the primary
      DSCP 46 flow per §4), the MLP can observe its queue behaviour and
      distinguish STABLE (low drops) from DEGRADING/FAILING (high drops).

    BUG-2 FIX: Accept optional deviceId in the request body to scope rows
      to a single vessel, matching the fix applied to post_approute.
    """
    # BUG-2 FIX: filter to the requesting vessel only
    body = request.get_json(silent=True) or {}
    device_filter = body.get("deviceId")

    data = []
    for sys_ip, vessel in VESSEL_DB.items():
        if device_filter and sys_ip != device_filter:
            continue
        for link_name, t in vessel["transports"].items():
            if t["oper_status"] == "down":
                # Dead link — one zeroed row per transport.
                # queue_name="Default" is the correct sentinel: a down link has
                # no active queue, mapping to [0,0,0,1] in _encode_queue().
                data.append({
                    "vdevice-name": vessel["identity"]["device_id"],
                    "interface": t["physical_interface"],
                    "queue_name": "Default",
                    "drop_in_kbps": 0,
                    "tx_pkts": 0,
                    "queued_pkts": 0
                })
                continue

            # Note: _read_live_metrics() is intentionally NOT called here.
            # The previous dead call was removed to eliminate 10-12 wasted RNG
            # draws per sample that caused a train/inference Mersenne Twister
            # state mismatch on features 9-20.

            health = t["health_percentage"]
            deg_factor = (100 - health) / 100.0

            # Single representative row using Video (Queue3) signal.
            base_noise = random.randint(1, 5)
            drop_in_kbps = base_noise

            if health < 100:
                drop_in_kbps += int(deg_factor * 800) + random.randint(10, 50)

            # BUG-A FIX (carried forward): was `health < 40` — excluded health=40.
            # The harvester's FAILING zone is randint(0, 40) inclusive of 40.
            # Corrected to `<= 40` so escalation fires for the full FAILING zone.
            if health <= 40:
                drop_in_kbps += int(deg_factor * 150) + random.randint(5, 20)

            tx_pkts = int((15000 if health > 20 else 2000) * random.uniform(0.9, 1.1))
            queued_pkts = int(deg_factor * 1200) + random.randint(20, 100)

            data.append({
                "vdevice-name": vessel["identity"]["device_id"],
                "interface": t["physical_interface"],
                "queue_name": "Video",   # BUG-D FIX: was "Queue3" → [0,0,0,1]; now "Video" → [0,1,0,0]
                "drop_in_kbps": drop_in_kbps,
                "tx_pkts": tx_pkts,
                "queued_pkts": queued_pkts
            })

    return jsonify({"data": data})

# ----------------------------------------------------
# ENDPOINT: Get list of vSmart (Centralized) Policies
# ----------------------------------------------------
@app.route('/dataservice/template/policy/vsmart', methods=['GET'])
def get_vsmart_policies():
    """Returns all available policies and their activation status."""
    return jsonify({"data": POLICY_LIST})

@app.route('/dataservice/template/policy/definition/approute/<policy_id>', methods=['GET', 'PUT'])
def policy_definition(policy_id):
    if policy_id not in POLICY_DB:
        POLICY_DB[policy_id] = {
            "name": policy_id,
            "sequences": [{
                "sequenceType": "app-route",
                "sequenceId": 1,
                "match": {"dscp": 46},
                "action": {"preferredColor": "public-internet", "strict": False}
            }]
        }

    if request.method == 'GET':
        return jsonify({"policyDefinition": POLICY_DB[policy_id]})

    elif request.method == 'PUT':
        new_def = request.json.get("policyDefinition", {})
        POLICY_DB[policy_id] = new_def

        new_color = new_def.get("sequences", [{}])[0].get("action", {}).get("preferredColor", "unknown")
        AUDIT_LOGS.append({
            "entry_time": int(time.time() * 1000),
            "user": "aegis-agent",
            "action": "Edit Policy Definition",
            "details": f"Policy {policy_id} updated. Preferred color set to {new_color}.",
            "status": "Success"
        })

        return jsonify({"masterTemplatesAffected": ["vessel-master-template-1"]})

@app.route('/dataservice/template/policy/vsmart/activate/<policy_id>', methods=['POST'])
def activate_policy(policy_id):
    target_policy = next((p for p in POLICY_LIST if p["policyId"] == policy_id), None)

    if not target_policy:
        return jsonify({"error": {"message": "Policy not found"}}), 404

    new_color = target_policy.get("preferredColor", "default")

    # Accept an optional deviceId in the request body to scope the policy push
    # to a single vessel.  Without this, every activation was fleet-wide: when
    # vessel A switched to 5G it overwrote all other vessels' control planes,
    # and when vessel B then switched to Satellite it flipped everyone back —
    # including vessel A, which now had split-brain (engine says 5G, vManage
    # says Satellite).  Scoped pushes mean each vessel\s engine and vManage
    # stay in sync independently.
    body = request.get_json(silent=True) or {}
    device_id = body.get("deviceId")

    if device_id:
        # Per-vessel push — only touch the one vessel that requested the switch.
        if device_id not in VESSEL_DB:
            return jsonify({"error": {"message": f"Device {device_id} not found"}}), 404
        vessels_to_update = [VESSEL_DB[device_id]]
    else:
        # Fleet-wide push (legacy / manual operator use).
        vessels_to_update = list(VESSEL_DB.values())
        # Only mark the global policy as active for fleet-wide pushes.
        for p in POLICY_LIST:
            p["isPolicyActivated"] = (p["policyId"] == policy_id)

    for vessel in vessels_to_update:
        vessel["control_plane"]["preferred_color"] = new_color
        vessel["control_plane"]["active_policy_name"] = target_policy["policyName"]

    task_id = f"push_action_{uuid.uuid4().hex[:8]}"
    TASKS[task_id] = "Success"

    scope = f"device:{device_id}" if device_id else "fleet-wide"
    AUDIT_LOGS.append({
        "entry_time": int(time.time() * 1000),
        "user": "aegis-agent",
        "action": "Activate Centralized Policy",
        "details": f"Policy {policy_id} applied ({scope}). Preferred color switched to {new_color}",
        "status": "Success"
    })

    return jsonify({"id": task_id})

@app.route('/dataservice/device/action/status/<task_id>', methods=['GET'])
def get_task_status(task_id):
    status = TASKS.get(task_id, "Failure")
    return jsonify({
        "data": [{
            "statusId": task_id,
            "status": status,
            "activity": ["Validating Policy", "Pushing to vSmart Controllers", "Completed"]
        }]
    })

@app.route('/dataservice/auditlog', methods=['GET'])
def get_audit_log():
    return jsonify({"data": AUDIT_LOGS})

# ==========================================
# AEGIS-WAN CONTROL & INJECTION ENDPOINTS
# ==========================================

@app.route('/sim/control/health/<system_ip>/<link_type>', methods=['POST'])
def set_link_health(system_ip, link_type):
    if system_ip not in VESSEL_DB:
        return jsonify({"error": "Vessel not found"}), 404

    vessel = VESSEL_DB[system_ip]
    if link_type not in vessel["transports"]:
        return jsonify({"error": "Link type not found on this vessel"}), 404

    new_health = max(0, min(100, int(request.json.get('health', 100))))
    vessel["transports"][link_type]["health_percentage"] = new_health
    vessel["transports"][link_type]["oper_status"] = "up" if new_health > 0 else "down"

    return jsonify({"message": f"{link_type} health on {system_ip} updated to {new_health}%"})

@app.route('/sim/overview', methods=['GET'])
def get_sim_overview():
    """Diagnostic dashboard — retained for manual inspection during Chaos Engineering only.
    Not part of the CMAB reward loop or the 24-D state vector pipeline (§7)."""
    dashboard = {}
    for sys_ip, vessel in VESSEL_DB.items():
        dashboard[vessel["identity"]["host_name"]] = {
            "active_color": vessel["control_plane"]["preferred_color"],
            "active_policy": vessel["control_plane"]["active_policy_name"],
            "links": {}
        }
        for link_name, t in vessel["transports"].items():
            lat, loss, jit, _, _, _, _ = _read_live_metrics(t)  # read-only, no drop accumulation
            dashboard[vessel["identity"]["host_name"]]["links"][link_name] = {
                "health": f"{t['health_percentage']}%",
                "accumulated_tx_drops": t["accumulated_stats"]["total_tx_drops"],
                "live_metrics": f"Lat: {lat}ms | Loss: {loss}% | Jit: {jit}ms"
            }
    return jsonify(dashboard)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
