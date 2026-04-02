import time
import requests
from prometheus_client import start_http_server, Gauge

# ==========================================
# 1. DEFINE PROMETHEUS METRICS
# ==========================================

# Block A: App-Route Metrics
LATENCY = Gauge('sdwan_latency_ms', 'Link latency in ms', ['vdevice', 'color'])
LOSS = Gauge('sdwan_loss_percent', 'Link packet loss percentage', ['vdevice', 'color'])
JITTER = Gauge('sdwan_jitter_ms', 'Link jitter in ms', ['vdevice', 'color'])
VQOE = Gauge('sdwan_vqoe_score', 'Video Quality of Experience score', ['vdevice', 'color'])

# Block B: QoS Aggregation Metrics
QOS_DROPS = Gauge('sdwan_qos_drop_kbps', 'Drops in kbps per queue', ['vdevice', 'interface', 'queue_name'])
QOS_QUEUED = Gauge('sdwan_qos_queued_pkts', 'Number of packets queued', ['vdevice', 'interface', 'queue_name'])

# Block C: Interface Aggregation Metrics
RX_KBPS = Gauge('sdwan_interface_rx_kbps', 'Receive bandwidth in kbps', ['vdevice', 'interface'])
TX_KBPS = Gauge('sdwan_interface_tx_kbps', 'Transmit bandwidth in kbps', ['vdevice', 'interface'])
RX_DROPS = Gauge('sdwan_interface_rx_drops', 'Hardware receive drops', ['vdevice', 'interface'])
TX_DROPS = Gauge('sdwan_interface_tx_drops', 'Hardware transmit drops', ['vdevice', 'interface'])

# Block D: NEW TLOC State Metrics
TLOC_STATE = Gauge('sdwan_tloc_state', 'TLOC operational state (1=up, 0=down)', ['vdevice', 'color'])


# ==========================================
# 2. DEFINE API URLS
# ==========================================
APPROUTE_API_URL = "http://127.0.0.1:8000/dataservice/statistics/approute" 
QOS_API_URL = "http://127.0.0.1:8000/dataservice/statistics/qos/aggregation"
INTERFACE_API_URL = "http://127.0.0.1:8000/dataservice/statistics/interface/aggregation"
DEVICE_API_URL = "http://127.0.0.1:8000/dataservice/device"
TLOC_API_URL = "http://127.0.0.1:8000/dataservice/device/tloc"


# ==========================================
# 3. FETCH AND TRANSLATE LOGIC
# ==========================================
def fetch_and_update_metrics():
    # --- Block A: App-Route (Layer 3) Telemetry ---
    try:
        response = requests.post(APPROUTE_API_URL, timeout=5)
        data = response.json().get("data", [])
        
        for item in data:
            device = item["vdevice-name"]
            color = item["local-color"]
            
            LATENCY.labels(vdevice=device, color=color).set(item["latency"])
            LOSS.labels(vdevice=device, color=color).set(item["loss_percentage"])
            JITTER.labels(vdevice=device, color=color).set(item["jitter"])
            VQOE.labels(vdevice=device, color=color).set(item["vqoe_score"])
            
    except Exception as e:
        print(f"Failed to fetch App-Route metrics: {e}")

    # --- Block B: QoS Aggregation Telemetry ---
    try:
        qos_response = requests.post(QOS_API_URL, timeout=5)
        qos_data = qos_response.json().get("data", [])
        
        for item in qos_data:
            device = item["vdevice-name"]
            interface = item["interface"]
            queue = item["queue_name"]
            
            QOS_DROPS.labels(vdevice=device, interface=interface, queue_name=queue).set(item["drop_in_kbps"])
            QOS_QUEUED.labels(vdevice=device, interface=interface, queue_name=queue).set(item["queued_pkts"])
            
    except Exception as e:
        print(f"Failed to fetch QoS metrics: {e}")

    # --- Block C: Interface Aggregation Telemetry ---
    try:
        int_response = requests.post(INTERFACE_API_URL, timeout=5)
        int_data = int_response.json().get("data", [])
        
        for item in int_data:
            device = item["vdevice-name"]
            interface = item["interface"]
            
            RX_KBPS.labels(vdevice=device, interface=interface).set(item["rx_kbps"])
            TX_KBPS.labels(vdevice=device, interface=interface).set(item["tx_kbps"])
            RX_DROPS.labels(vdevice=device, interface=interface).set(item["rx_drops"])
            TX_DROPS.labels(vdevice=device, interface=interface).set(item["tx_drops"])
            
    except Exception as e:
        print(f"Failed to fetch Interface metrics: {e}")

    # --- Block D: NEW TLOC State Telemetry ---
    try:
        # First, dynamically get the device inventory
        device_resp = requests.get(DEVICE_API_URL, timeout=5)
        devices = device_resp.json().get("data", [])
        
        for dev in devices:
            # FIX: Grab BOTH the system_ip (for the API) and device_id (for Prometheus)
            sys_ip = dev.get("system_ip") 
            dev_id = dev.get("device_id")
            
            if not sys_ip:
                continue
            
            # FIX: Ask the API for the TLOCs using the system_ip!
            tloc_resp = requests.get(f"{TLOC_API_URL}?deviceId={sys_ip}", timeout=5)
            tloc_data = tloc_resp.json().get("data", [])
            
            for item in tloc_data:
                color = item.get("color")
                state_str = item.get("state", "down").lower()
                
                # Convert string to binary: 1 for up, 0 for down
                state_num = 1 if state_str == "up" else 0
                
                # Use dev_id here so it matches your App-Route and QoS metrics
                TLOC_STATE.labels(vdevice=dev_id, color=color).set(state_num)
                
    except Exception as e:
        print(f"Failed to fetch TLOC metrics: {e}")


# ==========================================
# 4. MAIN RUNNER
# ==========================================
if __name__ == '__main__':
    start_http_server(8002)
    print("Prometheus Exporter running on http://127.0.0.1:8002/metrics ...")
    
    while True:
        fetch_and_update_metrics()
        time.sleep(5)