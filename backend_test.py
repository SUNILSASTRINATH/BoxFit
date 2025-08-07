import requests
import sys
import json
import asyncio
import websockets
from datetime import datetime

class BoxFitAPITester:
    def __init__(self, base_url="https://0ade0fab-e355-4693-923b-cba18b53ef12.preview.emergentagent.com"):
        self.base_url = base_url
        self.ws_url = base_url.replace('https://', 'wss://').replace('http://', 'ws://')
        self.tests_run = 0
        self.tests_passed = 0

    def run_test(self, name, test_func):
        """Run a single test"""
        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        
        try:
            result = test_func()
            if result:
                self.tests_passed += 1
                print(f"✅ Passed - {name}")
            else:
                print(f"❌ Failed - {name}")
            return result
        except Exception as e:
            print(f"❌ Failed - {name}: {str(e)}")
            return False

    def test_api_root(self):
        """Test the root API endpoint"""
        try:
            response = requests.get(f"{self.base_url}/api/", timeout=10)
            if response.status_code == 200:
                data = response.json()
                return data.get("message") == "BoxFit Game API"
            return False
        except Exception as e:
            print(f"Error: {e}")
            return False

    def test_status_endpoints(self):
        """Test status check endpoints"""
        try:
            # Test POST status
            test_data = {"client_name": f"test_client_{datetime.now().strftime('%H%M%S')}"}
            response = requests.post(f"{self.base_url}/api/status", json=test_data, timeout=10)
            
            if response.status_code != 200:
                print(f"POST status failed with status code: {response.status_code}")
                return False
            
            # Test GET status
            response = requests.get(f"{self.base_url}/api/status", timeout=10)
            if response.status_code == 200:
                data = response.json()
                return isinstance(data, list)
            return False
        except Exception as e:
            print(f"Error: {e}")
            return False

    async def test_websocket_connection(self):
        """Test WebSocket connection"""
        try:
            room_id = "test-room"
            player_name = "test-player"
            ws_endpoint = f"{self.ws_url}/api/ws/{room_id}/{player_name}"
            
            print(f"Connecting to: {ws_endpoint}")
            
            async with websockets.connect(ws_endpoint) as websocket:
                # Wait for initial game state message
                message = await asyncio.wait_for(websocket.recv(), timeout=5)
                data = json.loads(message)
                
                if data.get("type") == "game_state":
                    game_data = data.get("data", {})
                    # Check if we have the expected game state structure
                    required_fields = ["grid", "players", "score", "next_piece", "player_name", "player_color"]
                    return all(field in game_data for field in required_fields)
                
                return False
        except Exception as e:
            print(f"WebSocket error: {e}")
            return False

    async def test_piece_rotation(self):
        """Test piece rotation via WebSocket"""
        try:
            room_id = "test-room-rotate"
            player_name = "test-player-rotate"
            ws_endpoint = f"{self.ws_url}/api/ws/{room_id}/{player_name}"
            
            async with websockets.connect(ws_endpoint, timeout=10) as websocket:
                # Wait for initial game state
                await asyncio.wait_for(websocket.recv(), timeout=5)
                
                # Send rotation request
                rotation_message = {
                    "type": "rotate_piece",
                    "data": {"shape": [[1, 1, 1, 1]]}  # I-piece
                }
                await websocket.send(json.dumps(rotation_message))
                
                # Wait for rotation response
                response = await asyncio.wait_for(websocket.recv(), timeout=5)
                data = json.loads(response)
                
                return data.get("type") == "piece_rotated" and "shape" in data.get("data", {})
        except Exception as e:
            print(f"Piece rotation error: {e}")
            return False

    async def test_piece_placement(self):
        """Test piece placement via WebSocket"""
        try:
            room_id = "test-room-place"
            player_name = "test-player-place"
            ws_endpoint = f"{self.ws_url}/api/ws/{room_id}/{player_name}"
            
            async with websockets.connect(ws_endpoint, timeout=10) as websocket:
                # Wait for initial game state
                await asyncio.wait_for(websocket.recv(), timeout=5)
                
                # Send piece placement request
                placement_message = {
                    "type": "place_piece",
                    "data": {
                        "shape": [[1, 1], [1, 1]],  # O-piece
                        "position": {"x": 0, "y": 0},
                        "color": "#FFFF00"
                    }
                }
                await websocket.send(json.dumps(placement_message))
                
                # Wait for placement response
                response = await asyncio.wait_for(websocket.recv(), timeout=5)
                data = json.loads(response)
                
                if data.get("type") == "piece_placed":
                    placement_data = data.get("data", {})
                    # Check if score increased (should be 40 for 4-cell piece)
                    return placement_data.get("score", 0) >= 40
                
                return False
        except Exception as e:
            print(f"Piece placement error: {e}")
            return False

    def run_sync_tests(self):
        """Run synchronous tests"""
        print("🚀 Starting BoxFit API Tests...")
        
        # Test basic API endpoints
        self.run_test("API Root Endpoint", self.test_api_root)
        self.run_test("Status Endpoints", self.test_status_endpoints)

    async def run_async_tests(self):
        """Run asynchronous WebSocket tests"""
        print("\n🔌 Starting WebSocket Tests...")
        
        # Test WebSocket functionality
        ws_connection_result = await self.test_websocket_connection()
        if ws_connection_result:
            self.tests_passed += 1
            print("✅ Passed - WebSocket Connection")
        else:
            print("❌ Failed - WebSocket Connection")
        self.tests_run += 1
        
        # Test piece rotation
        rotation_result = await self.test_piece_rotation()
        if rotation_result:
            self.tests_passed += 1
            print("✅ Passed - Piece Rotation")
        else:
            print("❌ Failed - Piece Rotation")
        self.tests_run += 1
        
        # Test piece placement
        placement_result = await self.test_piece_placement()
        if placement_result:
            self.tests_passed += 1
            print("✅ Passed - Piece Placement")
        else:
            print("❌ Failed - Piece Placement")
        self.tests_run += 1

def main():
    tester = BoxFitAPITester()
    
    # Run synchronous tests
    tester.run_sync_tests()
    
    # Run asynchronous tests
    try:
        asyncio.run(tester.run_async_tests())
    except Exception as e:
        print(f"Error running async tests: {e}")
    
    # Print results
    print(f"\n📊 Backend Tests Summary:")
    print(f"Tests passed: {tester.tests_passed}/{tester.tests_run}")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All backend tests passed!")
        return 0
    else:
        print("⚠️  Some backend tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())