To perform a traffic switch in Cisco SD-WAN via API, you aren't just "flipping a toggle." You are modifying the **Control Plane** instructions that tell the router how to map specific applications to specific transport "Colors" (like 5G or Satellite).

For the **Aegis-WAN** project, you should use the **Application-Aware Routing (AAR)** workflow. This allows you to define a "Preferred Color" and then use the API to update that preference programmatically.

### The "Aegis-WAN" Switching Workflow



#### Step 1: Retrieve the Current Policy Definition
Before you can change the link, you need the current JSON structure of your AAR policy. 
* **Endpoint:** `GET /dataservice/template/policy/definition/approute/{aar-policy-id}`
* **Action:** Find the `sequences` array in the response. Look for the `action` block that contains the `preferredColor`.

#### Step 2: Modify the "Preferred Color" in JSON
Your Python logic will identify that the 5G link is degrading and decide to switch to Satellite. You must update the JSON object retrieved in Step 1.
* **Logic:** Change `"preferredColor": "biz-internet"` (5G) to `"preferredColor": "custom1"` (Satellite).
* **Crucial Note:** If you are worried about an **MTU Black Hole**, this is the moment your script should also inject an MSS Clamping value or a lower MTU into the policy if the schema allows, or trigger a secondary interface template update.

#### Step 3: Push the Update (PUT Request)
Now, send the modified JSON back to vManage.
* **Endpoint:** `PUT /dataservice/template/policy/definition/approute/{aar-policy-id}`
* **Effect:** This updates the *definition* in the vManage database, but it hasn't hit the routers yet.

#### Step 4: The "Switch" (Policy Re-Activation)
To make the change live across the fabric, you must re-push the Centralized Policy to the **vSmart Controllers**.
* **Endpoint:** `POST /dataservice/template/policy/vsmart/activate/{policyId}?confirm=true`
* **Response:** You will receive a `taskId`. 

---

### Implementation Details for your Simulator

When your Flask server receives the `POST` to activate a policy, it should simulate the "Sync" delay. In the real world, this takes **10–30 seconds** (the "Switching Gap" your PDF mentions).

**Simulator Logic Example:**
```python
@app.route('/dataservice/template/policy/vsmart/activate/<policy_id>', methods=['POST'])
def activate_policy(policy_id):
    # 1. Start a background thread to simulate the NETCONF push to vSmart
    # 2. After 5 seconds, update the 'internal_routing_table'
    # 3. Subsequent calls to /approute stats should now show traffic on the new color
    return jsonify({"parentTaskId": "active-task-12345"})
```

### CCNA Lord's "Golden Rule" for Switching
In high-tension zones, **never switch the whole pipe at once**. 
1. Use a **Data Policy** to move only mission-critical traffic (VoIP/Telemetry) to the Satellite link first.
2. Keep the "Bulk" traffic (Emails/Updates) on the degrading 5G link until it fully dies. 
3. This preserves the expensive Satellite bandwidth and prevents "Bill Shock."

**Would you like the specific JSON payload structure for the `PUT` request to modify the preferred color?**
