from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import json
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import uuid
from datetime import datetime
import asyncio

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Dict[str, Any]] = {}
        self.game_rooms: Dict[str, Dict[str, Any]] = {}

    async def connect(self, websocket: WebSocket, room_id: str, player_name: str):
        await websocket.accept()
        
        if room_id not in self.game_rooms:
            self.game_rooms[room_id] = {
                "players": {},
                "grid": [[None for _ in range(10)] for _ in range(10)],
                "score": 0,
                "next_piece": self.generate_random_piece()
            }
        
        # Generate player color
        colors = ["#3B82F6", "#EF4444", "#10B981", "#F59E0B", "#8B5CF6", "#EC4899"]
        player_color = colors[len(self.game_rooms[room_id]["players"]) % len(colors)]
        
        self.game_rooms[room_id]["players"][player_name] = {
            "websocket": websocket,
            "color": player_color,
            "connected": True
        }
        
        self.active_connections[f"{room_id}_{player_name}"] = {
            "websocket": websocket,
            "room_id": room_id,
            "player_name": player_name
        }
        
        # Send initial game state to new player
        await websocket.send_text(json.dumps({
            "type": "game_state",
            "data": {
                "grid": self.game_rooms[room_id]["grid"],
                "players": {name: {"color": data["color"], "connected": data["connected"]} 
                          for name, data in self.game_rooms[room_id]["players"].items()},
                "score": self.game_rooms[room_id]["score"],
                "next_piece": self.game_rooms[room_id]["next_piece"],
                "player_name": player_name,
                "player_color": player_color
            }
        }))
        
        # Notify other players
        await self.broadcast_to_room(room_id, {
            "type": "player_joined",
            "data": {
                "player_name": player_name,
                "players": {name: {"color": data["color"], "connected": data["connected"]} 
                          for name, data in self.game_rooms[room_id]["players"].items()}
            }
        }, exclude=player_name)

    def disconnect(self, room_id: str, player_name: str):
        connection_key = f"{room_id}_{player_name}"
        if connection_key in self.active_connections:
            del self.active_connections[connection_key]
        
        if room_id in self.game_rooms and player_name in self.game_rooms[room_id]["players"]:
            self.game_rooms[room_id]["players"][player_name]["connected"] = False

    async def broadcast_to_room(self, room_id: str, message: dict, exclude: str = None):
        if room_id not in self.game_rooms:
            return
        
        for player_name, player_data in self.game_rooms[room_id]["players"].items():
            if exclude and player_name == exclude:
                continue
            
            websocket = player_data["websocket"]
            if websocket.client_state == WebSocketState.CONNECTED:
                try:
                    await websocket.send_text(json.dumps(message))
                except:
                    pass

    def generate_random_piece(self):
        import random
        pieces = [
            {"type": "I", "shape": [[1, 1, 1, 1]], "color": "#00FFFF"},
            {"type": "O", "shape": [[1, 1], [1, 1]], "color": "#FFFF00"},
            {"type": "T", "shape": [[0, 1, 0], [1, 1, 1]], "color": "#800080"},
            {"type": "L", "shape": [[1, 0, 0], [1, 1, 1]], "color": "#FFA500"},
            {"type": "J", "shape": [[0, 0, 1], [1, 1, 1]], "color": "#0000FF"},
            {"type": "S", "shape": [[0, 1, 1], [1, 1, 0]], "color": "#00FF00"},
            {"type": "Z", "shape": [[1, 1, 0], [0, 1, 1]], "color": "#FF0000"}
        ]
        return random.choice(pieces)

    async def place_piece(self, room_id: str, player_name: str, piece_data: dict):
        if room_id not in self.game_rooms:
            return False
        
        grid = self.game_rooms[room_id]["grid"]
        shape = piece_data["shape"]
        x, y = piece_data["position"]["x"], piece_data["position"]["y"]
        color = piece_data["color"]
        
        # Check if placement is valid
        if not self.is_valid_placement(grid, shape, x, y):
            return False
        
        # Place the piece
        for row_idx, row in enumerate(shape):
            for col_idx, cell in enumerate(row):
                if cell == 1:
                    grid_y = y + row_idx
                    grid_x = x + col_idx
                    if 0 <= grid_y < 10 and 0 <= grid_x < 10:
                        grid[grid_y][grid_x] = {
                            "color": color,
                            "player": player_name
                        }
        
        # Update score
        score_gained = len([cell for row in shape for cell in row if cell == 1]) * 10
        self.game_rooms[room_id]["score"] += score_gained
        
        # Generate next piece
        self.game_rooms[room_id]["next_piece"] = self.generate_random_piece()
        
        # Broadcast updated game state
        await self.broadcast_to_room(room_id, {
            "type": "piece_placed",
            "data": {
                "grid": grid,
                "score": self.game_rooms[room_id]["score"],
                "next_piece": self.game_rooms[room_id]["next_piece"],
                "placed_by": player_name
            }
        })
        
        return True

    def is_valid_placement(self, grid, shape, x, y):
        for row_idx, row in enumerate(shape):
            for col_idx, cell in enumerate(row):
                if cell == 1:
                    grid_y = y + row_idx
                    grid_x = x + col_idx
                    
                    # Check bounds
                    if grid_y < 0 or grid_y >= 10 or grid_x < 0 or grid_x >= 10:
                        return False
                    
                    # Check collision
                    if grid[grid_y][grid_x] is not None:
                        return False
        
        return True

    def rotate_piece(self, shape):
        # Rotate 90 degrees clockwise
        return [[shape[j][i] for j in range(len(shape)-1, -1, -1)] for i in range(len(shape[0]))]

manager = ConnectionManager()

# Define Models
class StatusCheck(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class StatusCheckCreate(BaseModel):
    client_name: str

# Add your routes to the router instead of directly to app
@api_router.get("/")
async def root():
    return {"message": "BoxFit Game API"}

@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_dict = input.dict()
    status_obj = StatusCheck(**status_dict)
    _ = await db.status_checks.insert_one(status_obj.dict())
    return status_obj

@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    status_checks = await db.status_checks.find().to_list(1000)
    return [StatusCheck(**status_check) for status_check in status_checks]

@api_router.websocket("/ws/{room_id}/{player_name}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, player_name: str):
    await manager.connect(websocket, room_id, player_name)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message["type"] == "place_piece":
                await manager.place_piece(room_id, player_name, message["data"])
            elif message["type"] == "rotate_piece":
                # Handle piece rotation
                rotated_shape = manager.rotate_piece(message["data"]["shape"])
                await websocket.send_text(json.dumps({
                    "type": "piece_rotated",
                    "data": {"shape": rotated_shape}
                }))
            
    except WebSocketDisconnect:
        manager.disconnect(room_id, player_name)
        await manager.broadcast_to_room(room_id, {
            "type": "player_left",
            "data": {
                "player_name": player_name,
                "players": {name: {"color": data["color"], "connected": data["connected"]} 
                          for name, data in manager.game_rooms.get(room_id, {}).get("players", {}).items()}
            }
        })

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()