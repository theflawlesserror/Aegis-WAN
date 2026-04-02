import asyncio
import random
import uvicorn
from fastapi import FastAPI
from typing import List
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

# Global simulation speed modifier
SPEED = 100

# --- LIFESPAN CONTEXT MANAGER (Replaces the deprecated startup event) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start the background simulation loop when the server boots
    task = asyncio.create_task(update_positions())
    yield
    # Clean up the task when the server shuts down
    task.cancel()

# Initialize FastAPI with the lifespan manager
app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# 1. THE DATA MODEL & SIMULATION ENGINE
# ==========================================
class VesselState:
    def __init__(self, name: str, path: List[List[float]]):
        self.name = name
        # Generate kebab-case ID from name (e.g., "Ever Given" -> "ever-given")
        self.id = name.lower().replace(" ", "-")
        self.route_plan = path  
        self.current_leg = 0
        self.progress = 0.0 
        self.direction = 1  # 1 for forward, -1 for backward
        self.current_pos = [path[0][0], path[0][1]]

    def update(self):
        # Stop or loop if we reach the end of the route plan
        if self.current_leg >= len(self.route_plan) - 1 and self.direction == 1:
            self.direction = -1
        elif self.current_leg <= 0 and self.direction == -1:
            self.direction = 1

        # Select p1 and p2 based on current direction
        p1 = self.route_plan[self.current_leg]
        p2 = self.route_plan[self.current_leg + self.direction]

        # Advance progress
        self.progress += 0.01 * (SPEED / 100.0)
        
        # Handle leg transitions
        if self.progress >= 1.0:
            self.progress = 0.0
            self.current_leg += self.direction
            
            # Prevent out of bounds
            if self.current_leg >= len(self.route_plan) - 1 and self.direction == 1:
                self.current_leg = len(self.route_plan) - 2
            elif self.current_leg <= 0 and self.direction == -1:
                self.current_leg = 0
                
            p1 = self.route_plan[self.current_leg]
            p2 = self.route_plan[self.current_leg + self.direction]

        lat1, lon1 = p1[0], p1[1]
        lat2, lon2 = p2[0], p2[1]

        # Date Line Fix
        d_lon = lon2 - lon1
        if d_lon > 180: d_lon -= 360
        elif d_lon < -180: d_lon += 360

        new_lat = lat1 + (lat2 - lat1) * self.progress
        new_lon = lon1 + (d_lon * self.progress)

        # Normalize Lon
        if new_lon > 180: new_lon -= 360
        elif new_lon < -180: new_lon += 360

        # --- ADDING REALISTIC GPS NOISE ---
        # Simulate GNSS multipath errors and hardware drift
        noisy_lat = new_lat + random.uniform(-0.005, 0.005)
        noisy_lon = new_lon + random.uniform(-0.005, 0.005)

        self.current_pos = [round(noisy_lat, 4), round(noisy_lon, 4)]


# --- LOAD SAMPLE DATA ---
vessels = [
    VesselState("Ever Given", [[1.27, 103.54], [5.5, 98.5], [5.9, 80.0], [12.5, 43.3], [20.0, 39.0], [30.0, 32.5], [34.0, 20.0], [35.9, -5.5], [49.5, -4.0], [51.9, 4.1]]),
    VesselState("HMM Algeciras", [[35.1, 129.0], [41.4, 140.5], [45.0, 170.0], [34.0, -120.0], [33.7, -118.2]])
]

# Background loop to update coordinates every second
async def update_positions():
    while True:
        for v in vessels:
            v.update()
        await asyncio.sleep(1)


# ==========================================
# 2. API ENDPOINTS
# ==========================================

@app.get("/vessels")
async def get_vessels():
    """Returns the noisy, live GPS coordinates for the fleet map."""
    return [{"id": v.id, "name": v.name, "position": v.current_pos} for v in vessels]


# ==========================================
# 3. SERVER IGNITION
# ==========================================
if __name__ == "__main__":
    # This automatically starts the server if you run `python main.py` or `uv run main.py`
    uvicorn.run("main:app", host="127.0.0.1", port=8001, reload=True)