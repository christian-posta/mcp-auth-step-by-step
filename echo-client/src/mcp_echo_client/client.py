import asyncio
import json
from typing import Any, Dict, List, Optional
from uuid import uuid4

import httpx
from pydantic import BaseModel, Field


class MCPRequest(BaseModel):
    """MCP request wrapper for HTTP transport."""
    jsonrpc: str = "2.0"
    id: str
    method: str
    params: Optional[Dict[str, Any]] = None


class MCPResponse(BaseModel):
    """MCP response wrapper for HTTP transport."""
    jsonrpc: str = "2.0"
    id: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None


class EchoToolRequest(BaseModel):
    """Parameters for the echo tool."""
    message: str = Field(description="The message to echo back")
    repeat_count: int = Field(default=1, description="Number of times to repeat the message", ge=1, le=10)


class MCPEchoClient:
    """MCP client for communicating with the echo server over HTTP."""
    
    def __init__(self, server_url: str = "http://localhost:9000"):
        self.server_url = server_url.rstrip('/')
        self.mcp_endpoint = f"{self.server_url}/mcp"
        self.client = httpx.AsyncClient()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
    
    async def _make_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make an MCP request to the server."""
        request_id = str(uuid4())
        request = MCPRequest(
            id=request_id,
            method=method,
            params=params
        )
        
        try:
            response = await self.client.post(
                self.mcp_endpoint,
                json=request.model_dump(),
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            
            mcp_response = MCPResponse(**response.json())
            
            if mcp_response.error:
                raise Exception(f"MCP Error: {mcp_response.error}")
            
            return mcp_response.result or {}
            
        except httpx.HTTPError as e:
            raise Exception(f"HTTP error: {e}")
        except Exception as e:
            raise Exception(f"Request failed: {e}")
    
    async def initialize(self) -> Dict[str, Any]:
        """Initialize the MCP connection."""
        return await self._make_request("initialize")
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools."""
        result = await self._make_request("tools/list")
        return result.get("tools", [])
    
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool by name with arguments."""
        params = {
            "name": name,
            "arguments": arguments
        }
        return await self._make_request("tools/call", params)
    
    async def list_prompts(self) -> List[Dict[str, Any]]:
        """List available prompts."""
        result = await self._make_request("prompts/list")
        return result.get("prompts", [])
    
    async def get_prompt(self, name: str, arguments: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Get a prompt by name with optional arguments."""
        params = {
            "name": name,
            "arguments": arguments or {}
        }
        return await self._make_request("prompts/get", params)
    
    async def ping(self) -> Dict[str, Any]:
        """Send a ping to the server."""
        return await self._make_request("ping")
    
    async def echo(self, message: str, repeat_count: int = 1) -> str:
        """Convenience method to call the echo tool."""
        echo_args = EchoToolRequest(message=message, repeat_count=repeat_count)
        result = await self.call_tool("echo", echo_args.model_dump())
        
        # Extract the text content from the result
        content = result.get("content", [])
        if content and len(content) > 0:
            return content[0].get("text", "")
        return ""
    
    async def health_check(self) -> Dict[str, Any]:
        """Check server health."""
        try:
            response = await self.client.get(f"{self.server_url}/health")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            raise Exception(f"Health check failed: {e}")


async def demo():
    """Demo function showing how to use the client."""
    async with MCPEchoClient() as client:
        print("🔍 Checking server health...")
        try:
            health = await client.health_check()
            print(f"✅ Server health: {health}")
        except Exception as e:
            print(f"❌ Health check failed: {e}")
            return
        
        print("\n🔧 Initializing MCP connection...")
        try:
            init_result = await client.initialize()
            print(f"✅ Initialized: {init_result}")
        except Exception as e:
            print(f"❌ Initialization failed: {e}")
            return
        
        print("\n📋 Listing available tools...")
        try:
            tools = await client.list_tools()
            print(f"✅ Available tools: {len(tools)}")
            for tool in tools:
                print(f"  - {tool['name']}: {tool['description']}")
        except Exception as e:
            print(f"❌ Failed to list tools: {e}")
            return
        
        print("\n📝 Listing available prompts...")
        try:
            prompts = await client.list_prompts()
            print(f"✅ Available prompts: {len(prompts)}")
            for prompt in prompts:
                print(f"  - {prompt['name']}: {prompt['description']}")
        except Exception as e:
            print(f"❌ Failed to list prompts: {e}")
            return
        
        print("\n🔄 Testing echo tool...")
        try:
            echo_result = await client.echo("Hello, MCP World!", 3)
            print(f"✅ Echo result: {echo_result}")
        except Exception as e:
            print(f"❌ Echo failed: {e}")
            return
        
        print("\n📄 Testing prompt...")
        try:
            prompt_result = await client.get_prompt("echo_prompt", {"message": "Test message"})
            print(f"✅ Prompt result: {prompt_result}")
        except Exception as e:
            print(f"❌ Prompt failed: {e}")
            return
        
        print("\n🏓 Testing ping...")
        try:
            ping_result = await client.ping()
            print(f"✅ Ping successful: {ping_result}")
        except Exception as e:
            print(f"❌ Ping failed: {e}")
            return
        
        print("\n🎉 All tests completed successfully!")


if __name__ == "__main__":
    asyncio.run(demo()) 