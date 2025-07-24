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
        
        # persistent HTTP client for faster local connections. part of the speed optimizations
        self._client = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        # get or create persistent HTTP client
        if self._client is None or self._client.is_closed:
            is_https = self.base_url.startswith("https://")
            
            # optimize timeouts based on protocol
            if is_https:
                # HTTPS typically means remote, use generous timeouts
                timeout = httpx.Timeout(connect=10.0, read=30.0, write=30.0, pool=30.0)
                use_http2 = True  # HTTP/2 is better for HTTPS
            else:
                # HTTP typically means local, use fast timeouts
                timeout = httpx.Timeout(connect=2.0, read=5.0, write=5.0, pool=5.0)
                use_http2 = False  # HTTP/1.1 is just a bit quicker for local HTTP

            limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
            
            self._client = httpx.AsyncClient(
                timeout=timeout,
                limits=limits,
                http2=use_http2,
                follow_redirects=False
            )
        return self._client
    
    async def close(self):
        # clean up HTTP client
        if self._client and not self._client.is_closed:
            await self._client.aclose()
    
    async def get_state(self, entity_id: str) -> Optional[Dict[str, Any]]:
        # Get state entity
        url = f"{self.base_url}/api/states/{entity_id}"
        
        client = await self._get_client()
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
        
        client = await self._get_client()
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
        
        client = await self._get_client()
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
        
        client = await self._get_client()
        try:
            response = await client.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            print(f"Error getting all entities: {e}")
            return []
