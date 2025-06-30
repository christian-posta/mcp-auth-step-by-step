from .client import MCPEchoClient, demo


def main():
    """MCP Echo Client - Demo client for the echo server"""
    import asyncio

    asyncio.run(demo())


if __name__ == "__main__":
    main() 