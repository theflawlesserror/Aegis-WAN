import random
from predictor import StreamPredictor

def generate_synthetic_telemetry(link_type: str, is_degraded: bool):
    """Generates realistic metrics matching the simulation's feature structure."""
    if not is_degraded:
        # Healthy Network State
        lat = random.uniform(20, 50) if link_type == "5G" else random.uniform(500, 600)
        jit = random.uniform(1, 5)
        loss = 0.0
        rx = random.uniform(12000, 15000)
        tx = random.uniform(12000, 15000)
        vqoe = random.uniform(9.0, 10.0)
    else:
        # Brownout / Degraded Network State
        lat = random.uniform(100, 300) if link_type == "5G" else random.uniform(800, 1200)
        jit = random.uniform(30, 100)
        loss = random.uniform(2.0, 15.0)
        rx = random.uniform(1000, 4000)
        tx = random.uniform(1000, 4000)
        vqoe = random.uniform(1.0, 4.0)

    return {
        "features": {
            "latency": lat,
            "jitter": jit,
            "loss": loss,
            "rx_kbps": rx,
            "tx_kbps": tx
        },
        "actual_vqoe": vqoe
    }

def build_pretrained_models(num_samples: int = 3000):
    """Initializes models and trains them on thousands of varied samples."""
    print(f"[*] Pretraining ML models on {num_samples} synthetic samples...")
    
    models = {
        "5G": StreamPredictor(learning_rate=0.05),
        "Satellite": StreamPredictor(learning_rate=0.05)
    }

    for link in ["5G", "Satellite"]:
        for _ in range(num_samples):
            # 80% healthy data, 20% brownout data to establish a strong baseline 
            # while ensuring the model learns the penalties for bad metrics.
            is_degraded = random.random() < 0.2
            
            data = generate_synthetic_telemetry(link, is_degraded)
            
            # Feed the data into the River model to adjust its weights
            models[link].process_telemetry(data["features"], data["actual_vqoe"])

    print("[*] Pretraining complete. Model weights are locked and ready.")
    return models

if __name__ == "__main__":
    # Allows you to run this script directly to verify it doesn't crash
    build_pretrained_models()
