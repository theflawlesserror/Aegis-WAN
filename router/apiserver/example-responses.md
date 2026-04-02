Here is the fully merged and structured markdown file. It includes the complete, up-to-date OpenAPI specification (incorporating the new centralized policy and simulation endpoints) and the comprehensive list of example responses (including the realistic QoS queue behavior and internal Aegis-WAN commands). 

You can save this directly as `aegis-api-documentation.md` for your project reference.

```markdown
# Aegis-WAN Simulation API Documentation

This document contains the complete OpenAPI 3.0.1 specification for the Aegis-WAN Simulation API, followed by a comprehensive set of example responses for testing, development, and AI agent training.

---

## Part 1: OpenAPI Specification (`router.spec.yml`)

```yaml
openapi: 3.0.1
info:
  title: Aegis-WAN Simulation API
  description: Combined API spec for Cisco vManage SD-WAN simulation and internal Aegis state control.
  version: 1.0.0
servers:
  - url: /

components:
  schemas:
    GenericDataArrayResponse:
      type: object
      properties:
        data:
          type: array
          items:
            type: object
            additionalProperties: true

    PolicyListResponse:
      type: object
      properties:
        data:
          type: array
          items:
            type: object
            properties:
              policyId:
                type: string
              policyName:
                type: string
              policyDescription:
                type: string
              policyType:
                type: string
              isPolicyActivated:
                type: boolean
              preferredColor:
                type: string

    PolicyDefinitionResponse:
      type: object
      properties:
        policyDefinition:
          type: object
          properties:
            name:
              type: string
            description:
              type: string
            sequences:
              type: array
              items:
                type: object
                properties:
                  sequenceType:
                    type: string
                  sequenceId:
                    type: integer
                  match:
                    type: object
                  action:
                    type: object
                    properties:
                      preferredColor:
                        type: string
                      strict:
                        type: boolean

    PolicyUpdateResponse:
      type: object
      properties:
        masterTemplatesAffected:
          type: array
          items:
            type: string

    ActivationResponse:
      type: object
      properties:
        id:
          type: string

    SimHealthRequest:
      type: object
      required:
        - health
      properties:
        health:
          type: integer
          description: Link health percentage (0-100)
          minimum: 0
          maximum: 100

    SimHealthResponse:
      type: object
      properties:
        message:
          type: string
        current_state:
          type: object
          properties:
            color:
              type: string
            interface:
              type: string
            mtu:
              type: integer
            base_latency:
              type: integer
            health:
              type: integer

    SimStateResponse:
      type: object
      properties:
        active_preferred_color:
          type: string
        links:
          type: object
          additionalProperties:
            type: object

    SimOverviewResponse:
      type: object
      properties:
        system_status:
          type: string
        active_routing:
          type: object
          properties:
            preferred_color:
              type: string
            link_name:
              type: string
        link_diagnostics:
          type: object
          additionalProperties:
            type: object
            properties:
              health_percentage:
                type: string
              status:
                type: string
              sdwan_color:
                type: string
              real_time_snapshot:
                type: object
                properties:
                  latency_ms:
                    type: integer
                  packet_loss_percent:
                    type: number
                  video_qoe_score:
                    type: string

paths:
  # ==========================================
  # CISCO vMANAGE MOCK ENDPOINTS
  # ==========================================
  /dataservice/device:
    get:
      summary: Get device inventory
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/GenericDataArrayResponse'

  /dataservice/device/tloc:
    get:
      summary: Get TLOC status list
      parameters:
        - name: deviceId
          in: query
          required: true
          description: The system-ip of the device
          schema:
            type: string
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/GenericDataArrayResponse'

  /dataservice/device/interface:
    get:
      summary: Get real-time interface statistics
      parameters:
        - name: deviceId
          in: query
          required: true
          description: The system-ip of the device
          schema:
            type: string
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/GenericDataArrayResponse'

  /dataservice/statistics/approute:
    post:
      summary: Get aggregated App-Route data
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/GenericDataArrayResponse'

  /dataservice/statistics/interface/aggregation:
    post:
      summary: Get aggregated interface statistics
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/GenericDataArrayResponse'

  /dataservice/statistics/qos/aggregation:
    post:
      summary: Get aggregated QoS statistics
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/GenericDataArrayResponse'

  /dataservice/template/policy/vsmart:
    get:
      summary: Get list of centralized vSmart policies
      description: Returns all available policies and their activation status.
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/PolicyListResponse'

  /dataservice/template/policy/definition/approute/{policy_id}:
    get:
      summary: Get App-Route policy definition
      parameters:
        - name: policy_id
          in: path
          required: true
          schema:
            type: string
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/PolicyDefinitionResponse'
    put:
      summary: Update App-Route policy definition
      parameters:
        - name: policy_id
          in: path
          required: true
          schema:
            type: string
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/PolicyDefinitionResponse'
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/PolicyUpdateResponse'

  /dataservice/template/policy/vsmart/activate/{policy_id}:
    post:
      summary: Activate Centralized Policy on vSmart
      parameters:
        - name: policy_id
          in: path
          required: true
          schema:
            type: string
      responses:
        '200':
          description: Task ID
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ActivationResponse'

  /dataservice/device/action/status/{task_id}:
    get:
      summary: Monitor status of async task
      parameters:
        - name: task_id
          in: path
          required: true
          schema:
            type: string
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/GenericDataArrayResponse'

  /dataservice/auditlog:
    get:
      summary: Retrieve administrative audit logs
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/GenericDataArrayResponse'

  # ==========================================
  # AEGIS-WAN CONTROL & INJECTION ENDPOINTS
  # ==========================================
  /sim/control/health/{system_id}/{link_type}:
    post:
      summary: Degrade or improve a specific link's health for a specific router
      parameters:
        - name: system_id
          in: path
          required: true
          description: The System-IP of the target vessel router (e.g., 10.10.1.13)
          schema:
            type: string
        - name: link_type
          in: path
          required: true
          description: Valid values are '5G', 'Satellite', or 'Ethernet'
          schema:
            type: string
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/SimHealthRequest'
      responses:
        '200':
          description: Health successfully updated
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SimHealthResponse'
        '400':
          description: Invalid link type or missing payload
        '404':
          description: Vessel or link type not found

  /sim/control/state:
    get:
      summary: Get raw internal simulation state
      responses:
        '200':
          description: Internal JSON dictionary of active parameters
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SimStateResponse'

  /sim/overview:
    get:
      summary: Get human-friendly diagnostics dashboard data
      responses:
        '200':
          description: Real-time calculated diagnostics view
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SimOverviewResponse'
```

---

## Part 2: Example Responses

These JSON payloads demonstrate the expected behavior of the Aegis-WAN simulation server.

### 1. Device & Inventory Monitoring

#### `GET /dataservice/device`
Returns the inventory of devices. Use this to discover the `system-ip` (deviceId) of your Vessel routers.
```json
{
  "data": [
    {
      "deviceId": "172.16.255.11",
      "system-ip": "10.10.1.13",
      "host-name": "Aegis-Vessel-Alpha",
      "reachability": "reachable",
      "status": "normal"
    },
    {
      "deviceId": "172.16.255.12",
      "system-ip": "10.10.2.14",
      "host-name": "Aegis-Vessel-Beta",
      "reachability": "reachable",
      "status": "normal"
    }
  ]
}
```

#### `GET /dataservice/device/tloc?deviceId=10.10.1.13`
Returns the Transport Locators (Colors) available on the target device.
```json
{
  "header": {
    "generatedOn": 1774619645268,
    "title": "tlocStatus"
  },
  "data": [
    {
      "color": "mpls",
      "system-ip": "10.10.1.13",
      "bfdSessionsDown": 0,
      "controlConnectionsUp": 1,
      "bfdSessionsUp": 6,
      "state": "up"
    },
    {
      "color": "public-internet",
      "system-ip": "10.10.1.13",
      "bfdSessionsDown": 0,
      "controlConnectionsUp": 2,
      "bfdSessionsUp": 6,
      "state": "up"
    }
  ]
}
```

#### `GET /dataservice/device/interface?deviceId=10.10.1.13`
Returns the real-time operational status and MTU values for the physical interfaces.
```json
{
  "data": [
    {
      "if-name": "Cellular0/1/0",
      "oper-status": "up",
      "admin-status": "up",
      "rx-kbps": "4500",
      "tx-kbps": "120",
      "mtu": "1500",
      "ip-address": "100.64.1.5"
    },
    {
      "if-name": "GigabitEthernet0/1",
      "oper-status": "up",
      "admin-status": "up",
      "rx-kbps": "800",
      "tx-kbps": "50",
      "mtu": "1420",
      "ip-address": "203.0.113.10"
    }
  ]
}
```

---

### 2. High-Frequency Observability (The "Eyes")

#### `POST /dataservice/statistics/approute`
Returns the real-time BFD statistics used by Aegis-WAN to predict outages before they happen.
```json
{
  "data": [
    {
      "vdevice-name": "172.16.255.11",
      "local-color": "public-internet",
      "latency": 45,
      "loss_percentage": 0.0,
      "jitter": 4,
      "vqoe_score": 9
    },
    {
      "vdevice-name": "172.16.255.11",
      "local-color": "mpls",
      "latency": 650,
      "loss_percentage": 0.0,
      "jitter": 25,
      "vqoe_score": 6
    }
  ]
}
```

#### `POST /dataservice/statistics/interface/aggregation`
Used to monitor historical drops and throughput to avoid the "MTU Black Hole." These counters persistently accumulate over time.
```json
{
  "data": [
    {
      "vdevice-name": "172.16.255.11",
      "interface": "Cellular0/1/0",
      "rx_drops": 1204,
      "tx_drops": 340, 
      "rx_kbps": 48500,
      "tx_kbps": 24000
    }
  ]
}
```

#### `POST /dataservice/statistics/qos/aggregation`
Identifies specific traffic types suffering from congestion. Shows realistic behavior where Queue3 (Bulk) buffers and drops heavily during degradation to protect Queue0 (Voice).
```json
{
  "data": [
    {
      "vdevice-name": "172.16.255.11",
      "interface": "Cellular0/1/0",
      "queue_name": "Queue0",
      "drop_in_kbps": 1,
      "tx_pkts": 5120,
      "queued_pkts": 2
    },
    {
      "vdevice-name": "172.16.255.11",
      "interface": "Cellular0/1/0",
      "queue_name": "Queue3",
      "drop_in_kbps": 245,
      "tx_pkts": 14500,
      "queued_pkts": 850
    }
  ]
}
```

---

### 3. Control & Policy Execution (The "Hands")

#### `GET /dataservice/template/policy/vsmart`
Returns the centralized list of available policies and indicates which one is currently running on the fleet.
```json
{
  "data": [
    {
      "policyId": "policy-001",
      "policyName": "Aegis-Vessel-Routing",
      "policyDescription": "Default policy: Prefers 5G (public-internet) for all traffic",
      "policyType": "app-route",
      "isPolicyActivated": true,
      "preferredColor": "public-internet"
    },
    {
      "policyId": "policy-002",
      "policyName": "Aegis-Failover-Routing",
      "policyDescription": "Emergency policy: Forces traffic to Satellite (mpls)",
      "policyType": "app-route",
      "isPolicyActivated": false,
      "preferredColor": "mpls"
    }
  ]
}
```

#### `GET /dataservice/template/policy/definition/approute/{id}`
Returns the specific routing logic within an App-Route policy template.
```json
{
  "policyDefinition": {
    "name": "Aegis-Vessel-Routing",
    "description": "Dynamic Voice and Telemetry Steering",
    "sequences": [
      {
        "sequenceType": "app-route",
        "sequenceId": 1,
        "match": {
          "dscp": 46
        },
        "action": {
          "preferredColor": "public-internet",
          "strict": false
        }
      }
    ]
  }
}
```

#### `PUT /dataservice/template/policy/definition/approute/{id}`
*(Request Body Example for updating the preferred color to Satellite/mpls)*
```json
{
  "policyDefinition": {
    "name": "Aegis-Vessel-Routing",
    "sequences": [
      {
        "sequenceType": "app-route",
        "sequenceId": 1,
        "match": {
          "dscp": 46
        },
        "action": {
          "preferredColor": "mpls",
          "strict": true
        }
      }
    ]
  }
}
```
**Response:**
```json
{
  "masterTemplatesAffected": ["vessel-master-template-1"]
}
```

#### `POST /dataservice/template/policy/vsmart/activate/{policyId}`
Executes the network-wide switch to the target policy. Returns the async `taskId`.
```json
{
  "id": "push_action_987654321"
}
```

---

### 4. Verification & Logging

#### `GET /dataservice/device/action/status/{taskId}`
Monitors the async task to verify the policy push was successful.
```json
{
  "data": [
    {
      "statusId": "push_action_987654321",
      "status": "Success",
      "activity": [
        "Validating Policy",
        "Pushing to vSmart Controllers",
        "Completed"
      ]
    }
  ]
}
```

#### `GET /dataservice/auditlog`
Returns the permanent administrative record of the policy change.
```json
{
  "data": [
    {
      "entry_time": 1774619900000,
      "user": "aegis-agent",
      "action": "Activate Centralized Policy",
      "details": "Policy policy-002 applied. Preferred color switched to mpls",
      "status": "Success"
    }
  ]
}
```

---

### 5. Aegis-WAN Internal Simulation Endpoints

#### `GET /sim/overview`
Provides a human-readable dashboard of the entire fleet's routing state, active policies, and live metrics.
```json
{
  "Aegis-Vessel-Alpha": {
    "active_color": "mpls",
    "active_policy": "Aegis-Failover-Routing",
    "links": {
      "5G": {
        "accumulated_tx_drops": 450,
        "health": "50%",
        "live_metrics": "Lat: 156ms | Loss: 20.4% | Jit: 55ms"
      },
      "Satellite": {
        "accumulated_tx_drops": 110,
        "health": "100%",
        "live_metrics": "Lat: 649ms | Loss: 0.0% | Jit: 26ms"
      }
    }
  }
}
```

#### `POST /sim/control/health/{system_id}/{link_type}`
*(Request Body to degrade Alpha's 5G link to 30%)*
```json
{
  "health": 30
}
```
**Response:**
```json
{
  "message": "5G health on 10.10.1.13 updated to 30%"
}
```




#### `POST /sim/control/health/{system_id}/{link_type}`
*(Request Body Example to degrade Alpha's 5G link to 30%)*
```json
{
  "health": 30
}
```
**Response:**
```json
{
  "message": "5G health on 10.10.1.13 updated to 30%"
}
```

#### `GET /sim/control/state`
Returns the raw internal JSON dictionary of the simulation's active parameters, bypassing the human-readable dashboard formatting. 
**Response:**
```json
{
  "active_preferred_color": "mpls",
  "links": {
    "5G": {
      "sdwan_color": "public-internet",
      "physical_interface": "Cellular0/1/0",
      "public_ip": "100.64.1.5",
      "mtu": 1500,
      "oper_status": "up",
      "health_percentage": 30
    },
    "Satellite": {
      "sdwan_color": "mpls",
      "physical_interface": "GigabitEthernet0/1",
      "public_ip": "203.0.113.10",
      "mtu": 1420,
      "oper_status": "up",
      "health_percentage": 100
    }
  }
}
```
