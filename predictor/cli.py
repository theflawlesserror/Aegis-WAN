import requests
import sys

VMANAGE_BASE_URL = "http://localhost:8000"

def get_available_devices():
    """Fetches the list of active system IPs from the mock vManage."""
    try:
        response = requests.get(f"{VMANAGE_BASE_URL}/dataservice/device", timeout=3)
        response.raise_for_status()
        devices = response.json().get("data", [])
        return {d.get("system_ip"): d.get("host_name") for d in devices if d.get("system_ip")}
    except requests.exceptions.RequestException:
        print("[!] Could not reach the simulation server at localhost:8000.")
        return {}

def set_link_health(system_ip: str, link_type: str, health: int):
    """Sends the POST request to the Aegis simulation endpoint."""
    url = f"{VMANAGE_BASE_URL}/sim/control/health/{system_ip}/{link_type}"
    payload = {"health": health}
    
    try:
        response = requests.post(url, json=payload, timeout=3)
        response.raise_for_status()
        print(f"\n[+] SUCCESS: {link_type} on {system_ip} degraded to {health}% health.")
    except requests.exceptions.HTTPError as e:
        print(f"\n[!] API ERROR: {response.json().get('error', 'Unknown error')}")
    except requests.exceptions.RequestException as e:
        print(f"\n[!] CONNECTION ERROR: Failed to reach {url}\n{e}")

def main():
    print("========================================")
    print("  Aegis-WAN Simulation Controller CLI   ")
    print("========================================")
    
    devices = get_available_devices()
    if not devices:
        print("Exiting. Please ensure your simulation server is running.")
        sys.exit(1)

    print("\nAvailable Devices:")
    device_list = list(devices.keys())
    for idx, ip in enumerate(device_list):
        print(f"  {idx + 1}. {ip} ({devices[ip]})")
    
    # 1. Select Target Device
    while True:
        try:
            choice = int(input("\nSelect target device (number): ")) - 1
            if 0 <= choice < len(device_list):
                target_ip = device_list[choice]
                break
            print("Invalid choice.")
        except ValueError:
            print("Please enter a number.")

    # 2. Control Loop
    while True:
        print(f"\n--- Managing: {target_ip} ---")
        print("1. Set 5G Health")
        print("2. Set Satellite Health")
        print("3. Reset Both to 100% (Instant Recovery)")
        print("4. Exit")
        
        cmd = input("Action: ").strip()
        
        if cmd == '4':
            print("Exiting controller...")
            break
            
        elif cmd == '3':
            set_link_health(target_ip, "5G", 100)
            set_link_health(target_ip, "Satellite", 100)
            continue
            
        elif cmd in ['1', '2']:
            link = "5G" if cmd == '1' else "Satellite"
            while True:
                try:
                    health = int(input(f"Enter target health for {link} (0-100): "))
                    if 0 <= health <= 100:
                        set_link_health(target_ip, link, health)
                        break
                    else:
                        print("Health must be an integer between 0 and 100.")
                except ValueError:
                    print("Please enter a valid integer.")
        else:
            print("Invalid command. Please select 1, 2, 3, or 4.")

if __name__ == "__main__":
    # Graceful exit on Ctrl+C
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting controller...")
        sys.exit(0)
