import os
import httpx
import asyncio
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

load_dotenv()

class HomeAssistantClient:
    
    def __init__(self):
        self.base_url = os.getenv("HA_URL", "http://127.0.0.1:8123")
        self.token = os.getenv("HA_TOKEN")
        
        if not self.token:
            raise ValueError("HA_TOKEN environment variable is required")
        
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        
        # Remove slash if present
        self.base_url = self.base_url.rstrip("/")
    
    async def get_state(self, entity_id: str) -> Optional[Dict[str, Any]]:
       # Get state entity
        url = f"{self.base_url}/api/states/{entity_id}"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                print(f"Error getting state for {entity_id}: {e}")
                return None
    
    async def call_service(self, domain: str, service: str, entity_id: str, 
                          service_data: Optional[Dict[str, Any]] = None) -> bool:
       # Call HA service
        url = f"{self.base_url}/api/services/{domain}/{service}"
        
        data = {"entity_id": entity_id}
        if service_data:
            data.update(service_data)
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, headers=self.headers, json=data)
                response.raise_for_status()
                return True
            except httpx.HTTPError as e:
                print(f"Error calling service {domain}.{service} for {entity_id}: {e}")
                return False
    
    async def toggle_light(self, entity_id: str) -> bool:
        return await self.call_service("light", "toggle", entity_id)
    
    async def turn_on_light(self, entity_id: str) -> bool:
        return await self.call_service("light", "turn_on", entity_id)
    
    async def turn_off_light(self, entity_id: str) -> bool:
        return await self.call_service("light", "turn_off", entity_id)
    
    async def test_connection(self) -> bool:
       # Test the connection to HA
        url = f"{self.base_url}/api/"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
                print("Successfully connected to HA!")
                return True
            except httpx.HTTPError as e:
                print(f"Failed to connect to HA: {e}")
                return False
    
    async def get_all_entities(self) -> List[Dict[str, Any]]:
       # Get all entities from Home Assistant
        url = f"{self.base_url}/api/states"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                print(f"Error getting all entities: {e}")
                return []
