import time
import random
from predictor import StreamPredictor

class HysteresisEngine:
    """Prevents route flapping by enforcing delta and time thresholds."""
    def __init__(self, initial_active_link, delta_threshold=1.5, sustained_ticks=3):
        self.active_link = initial_active_link
        self.delta_threshold = delta_threshold 
        self.sustained_ticks = sustained_ticks 
        
        self.candidate_link = None
        self.consecutive_ticks = 0

    def evaluate(self, current_predictions):
        # Find the link with the highest predicted score
        best_link = max(current_predictions, key=current_predictions.get)
        best_score = current_predictions[best_link]
        active_score = current_predictions[self.active_link]

        # Scenario 1: Active link is still the best
        if best_link == self.active_link:
            self.consecutive_ticks = 0
            self.candidate_link = None
            return None 

        # Scenario 2: Another link is better. Check the Delta threshold.
        if (best_score - active_score) >= self.delta_threshold:
            if self.candidate_link == best_link:
                self.consecutive_ticks += 1
            else:
                self.candidate_link = best_link
                self.consecutive_ticks = 1

            # Check if it has been better for long enough (Time Rule)
            if self.consecutive_ticks >= self.sustained_ticks:
                self.active_link = best_link
                self.consecutive_ticks = 0
                self.candidate_link = None
                return best_link 
        else:
            # Better, but not enough to justify a switch
            self.consecutive_ticks = 0
            self.candidate_link = None

        return None


def generate_synthetic_telemetry(link_type, is_degraded=False):
    """Generates correlated SD-WAN telemetry."""
    if link_type == "5G":
        if is_degraded:
            latency, jitter, loss = random.uniform(100.0, 150.0), random.uniform(20.0, 40.0), random.uniform(2.0, 5.0)
        else:
            latency, jitter, loss = random.uniform(30.0, 45.0), random.uniform(2.0, 6.0), random.uniform(0.0, 0.1)
    elif link_type == "Satellite":
        latency, jitter, loss = random.uniform(550.0, 650.0), random.uniform(5.0, 15.0), random.uniform(0.1, 0.5)

    base_score = 10.0
    raw_vqoe = base_score - (latency * 0.005) - (jitter * 0.1) - (loss * 1.5)
    noise = random.uniform(-0.2, 0.2) 
    final_vqoe = max(1.0, min(10.0, raw_vqoe + noise))
        
    return {
        "interface": link_type,
        "latency": round(latency, 2),
        "jitter": round(jitter, 2),
        "loss": round(loss, 2),
        "vqoe_score": round(final_vqoe, 2)
    }


def run_simulation():
    print("Initializing SD-WAN Predictive Routing Engine...")
    
    link_models = {
        "5G": StreamPredictor(learning_rate=0.05), 
        "Satellite": StreamPredictor(learning_rate=0.05)
    }
    
    routing_engine = HysteresisEngine(initial_active_link="5G", delta_threshold=1.5, sustained_ticks=3)
    
    # --- THE FIX: BURN-IN PHASE ---
    print("Running invisible burn-in phase to train model weights...")
    for _ in range(15):
        # Force the model to see extreme variance so it learns negative weights
        for link in ["5G", "Satellite"]:
            is_chaotic = random.choice([True, False]) 
            payload = generate_synthetic_telemetry(link, is_degraded=is_chaotic)
            features = {"latency": payload["latency"], "jitter": payload["jitter"], "loss": payload["loss"]}
            link_models[link].process_telemetry(features, payload["vqoe_score"])
    # ------------------------------

    total_iterations = 40
    degradation_start = 10
    degradation_end = 25
    
    print("-" * 85)
    print(f"{'STEP':<5} | {'5G (Act/Pred)':<15} | {'SAT (Act/Pred)':<15} | {'ACTIVE LINK':<15} | {'NETWORK STATE'}")
    print("-" * 85)
    
    for step in range(1, total_iterations + 1):
        is_5g_degraded = degradation_start <= step <= degradation_end
        state_flag = "5G BROWNOUT" if is_5g_degraded else "NORMAL"
        
        current_predictions = {}
        display_data = {}

        for link in ["5G", "Satellite"]:
            payload = generate_synthetic_telemetry(link, is_degraded=(link=="5G" and is_5g_degraded))
            features = {"latency": payload["latency"], "jitter": payload["jitter"], "loss": payload["loss"]}
            actual_vqoe = payload["vqoe_score"]
            
            predicted_vqoe = link_models[link].process_telemetry(features, actual_vqoe)
            current_predictions[link] = predicted_vqoe
            
            display_data[link] = f"{actual_vqoe:.1f} / {predicted_vqoe:.1f}"

        switch_decision = routing_engine.evaluate(current_predictions)
        
        if switch_decision:
            print("-" * 85)
            print(f"!!! ROUTING UPDATE: Executing API call to switch active path to {switch_decision} !!!")
            print("-" * 85)

        active_str = f"[{routing_engine.active_link}]"
        print(f"{step:<5} | {display_data['5G']:<15} | {display_data['Satellite']:<15} | {active_str:<15} | {state_flag}")
        
        time.sleep(0.5)

if __name__ == "__main__":
    run_simulation()
