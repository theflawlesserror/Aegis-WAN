## **BFD (Bidirectional Forwarding Detection)**

## Endpoints under investigation

Target: Figure out physical link type (Cellular or Satellite)

1. `http://10.10.20.90/dataservice/device/interface?deviceId=10.10.1.13`
    - `.data[i].ifname`:
        1. If it's `GigabitEthernet.*`, it's satellite or ethernet. Disambiguate using heuristics from latency and jitter (higher => satellite)
        2. `Cellular.*`, it's satellite or ethernet. Disambiguate using heuristics from latency and jitter (higher => satellite)
    - `.data[i].if_admin_status` determines if it' s up or down.






---

## TBD

- Measures latency, loss, and jitter

| **Action**         | **API Endpoint (GET)**                               | **Why you need it**                                                                       |
| ------------------ | ---------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| [[List Devices]]   | `/dataservice/device`                                | To get the `deviceId` (System-IP) of your router.                                         |
| **Link Status**    | `/dataservice/device/interface?deviceId={id}`        | Check if the physical interface (LTE/Sat) is `up` or `down`.                              |
| **Tunnel Quality** | `/dataservice/statistics/approute/aggregation`       | **Crucial.** Returns real-time latency, jitter, and packet loss for every tunnel (color). |
| **BFD Sessions**   | `/dataservice/device/bfd/sessions?deviceId={id}`<br> | Shows if the control plane is actually alive over that specific link.                     |

## QOS
### 1. The Critical API Endpoints

To get the "Health" of the link (Loss, Latency, Jitter) via BFD:

- **Endpoint:** `GET /dataservice/statistics/approute/fields` (To see available metrics)
    
- **Endpoint:** `POST /dataservice/statistics/approute`
    
    - **Payload:** You'll want to filter by `local-color` (e.g., `lte` or `satellite`) and `remote-color`.
        

To get the **QoS Queue** stats (to see if your satellite link is dropping packets because the buffer is full):

- **Endpoint:** `GET /dataservice/device/qos/statistics?deviceId={system_ip}`
    
    - **What it tells you:** This shows `dropped_packets` and `transmitted_packets` per forwarding class (Voice, Video, Best Effort).



## More
- Router health endpoint:
    - CPU and MEM usage etc
