from .server import serve


def main():
    """MCP Echo Server - HTTP-based echo functionality for MCP"""
    import argparse

    parser = argparse.ArgumentParser(
        description="MCP Echo Server with HTTP transport"
    )
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=9000, help="Port to bind to")

    args = parser.parse_args()
    serve(args.host, args.port)


if __name__ == "__main__":
    main() 