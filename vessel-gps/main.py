import asyncio
from fastapi import FastAPI
from typing import List
from fastapi.middleware.cors import CORSMiddleware

# Global simulation speed modifier
SPEED = 100

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- THE DATA MODEL ---
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
        self.progress += 0.01 * SPEED

        if self.progress >= 1.0:
            self.current_leg += self.direction
            self.progress = 0.0
            new_lat, new_lon = self.route_plan[self.current_leg][0], self.route_plan[self.current_leg][1]
        else:
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

        self.current_pos = [round(new_lat, 4), round(new_lon, 4)]

# --- LOAD SAMPLE DATA ---
vessels = [
    VesselState("Ever Given", [[1.27, 103.54], [5.5, 98.5], [5.9, 80.0], [12.5, 43.3], [20.0, 39.0], [30.0, 32.5], [34.0, 20.0], [35.9, -5.5], [49.5, -4.0], [51.9, 4.1]]),
    VesselState("HMM Algeciras", [[35.1, 129.0], [41.4, 140.5], [45.0, 170.0], [34.0, -120.0], [33.7, -118.2]]),
    VesselState("Madrid Maersk", [[53.5, 8.5], [50.0, -2.0], [45.0, -30.0], [44.0, -60.0], [40.7, -74.1]]),
    VesselState("Mozah", [[25.9, 51.6], [26.5, 54.5], [26.6, 56.3], [24.5, 59.0], [15.0, 65.0], [9.9, 76.3]])
]

# --- BACKGROUND ENGINE ---
async def simulation_loop():
    while True:
        for v in vessels:
            v.update()
        await asyncio.sleep(2)

@app.on_event("startup")
async def startup():
    asyncio.create_task(simulation_loop())

# --- THE API ENDPOINT ---
@app.get("/vessels")
async def get_vessels():
    return [
        {
            "id": v.id,        # kebab-case ID
            "name": v.name,
            "pos": v.current_pos,
            "path": v.route_plan 
        } for v in vessels
    ]
