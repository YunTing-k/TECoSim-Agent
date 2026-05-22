import asyncio
from fastmcp.client.transports import StdioTransport, StreamableHttpTransport
from fastmcp import Client


async def http_mcp():
    transport = StreamableHttpTransport(
        url="https://mcp.socket.dev"
    )

    client = Client(transport, name="ping!")

    async with client:
        print(client.initialize_result.model_dump())
        print("Connected to Socket MCP Server")
        print("name: " + client.name)
        tools = await client.list_tools()
        print(f"{len(tools)} tools found:")
        for t in tools:
            print(f"- {t.name}: {t.description}")
            print(f"  Input schema: {t.inputSchema}")
            print(f"  Output schema: {t.outputSchema}")

        result = await client.call_tool_mcp(
            "depscore",
            {
                "packages": [
                    {
                        "depname": "react",
                        "ecosystem": "npm",
                        "version": "18.2.0"
                    }
                ]
            }
        )

        print("📊 执行结果：")
        print(result.model_dump())


async def stdio_mcp():
    transport = StdioTransport(
        command=r"C:\Users\admin\Desktop\PythonFile\TECoSimAgent\Agent\mcps\sources\matlab-mcp-core-server-win64.exe",
        args=["--matlab-display-mode", "desktop", "--initialize-matlab-on-startup"]
    )

    client = Client(transport, name="hi!")

    async with client:
        print(client.initialize_result.model_dump())
        print("Connected to MATLAB MCP Core Server")
        print("name: " + client.name)
        tools = await client.list_tools()
        print(f"{len(tools)} tools found:")
        for t in tools:
            print(f"- {t.name}: {t.description}")
            print(f"  Input schema: {t.inputSchema}")
            print(f"  Output schema: {t.outputSchema}")

        result = await client.call_tool_mcp(
            "evaluate_matlab_code", {"code": "exp(1:10)"}
        )

        print("📊 执行结果：")
        print(result.model_dump())

if __name__ == "__main__":
    asyncio.run(http_mcp())
    asyncio.run(stdio_mcp())
