import os, json, httpx
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import Response
import uvicorn
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent

GHL_API_KEY = os.environ.get("GHL_API_KEY", "")
GHL_LOCATION_ID = os.environ.get("GHL_LOCATION_ID", "")
BASE_URL = "https://services.leadconnectorhq.com"
HEADERS = {"Authorization": f"Bearer {GHL_API_KEY}", "Version": "2021-07-28", "Content-Type": "application/json"}
PORT = int(os.environ.get("PORT", 8000))

mcp = Server("ghl-ecometri")

async def ghl_get(path, params={}):
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}{path}", headers=HEADERS, params=params)
        r.raise_for_status()
        return r.json()

@mcp.list_tools()
async def list_tools():
    return [
        Tool(name="get_contacts_by_tag", description="Get all contacts with a specific tag",
             inputSchema={"type":"object","required":["tag"],"properties":{"tag":{"type":"string"},"max_pages":{"type":"integer"}}}),
        Tool(name="get_contact", description="Get full contact details",
             inputSchema={"type":"object","required":["contact_id"],"properties":{"contact_id":{"type":"string"}}}),
        Tool(name="get_pipelines", description="Get all pipelines and stages",
             inputSchema={"type":"object","properties":{}}),
        Tool(name="get_opportunities", description="Get deals/opportunities",
             inputSchema={"type":"object","properties":{"pipeline_id":{"type":"string"},"stage_id":{"type":"string"},"limit":{"type":"integer"}}}),
        Tool(name="get_custom_fields", description="Get all custom field definitions",
             inputSchema={"type":"object","properties":{}}),
        Tool(name="get_workflows", description="Get all workflows",
             inputSchema={"type":"object","properties":{}}),
        Tool(name="get_location_stats", description="Get total contacts, pipelines, workflows",
             inputSchema={"type":"object","properties":{}}),
    ]

@mcp.call_tool()
async def call_tool(name, arguments):
    try:
        if name == "get_contacts_by_tag":
            tag = arguments["tag"]
            max_pages = arguments.get("max_pages", 10)
            all_contacts, skip = [], 0
            for _ in range(max_pages):
                data = await ghl_get("/contacts/", {"locationId": GHL_LOCATION_ID, "tags": tag, "limit": 100, "skip": skip})
                batch = data.get("contacts", [])
                all_contacts.extend(batch)
                if len(batch) < 100: break
                skip += 100
            result = {"total": len(all_contacts), "contacts": all_contacts}
        elif name == "get_contact":
            result = await ghl_get(f"/contacts/{arguments['contact_id']}")
        elif name == "get_pipelines":
            result = await ghl_get("/opportunities/pipelines", {"locationId": GHL_LOCATION_ID})
        elif name == "get_opportunities":
            params = {"location_id": GHL_LOCATION_ID, "limit": arguments.get("limit", 100)}
            if arguments.get("pipeline_id"): params["pipeline_id"] = arguments["pipeline_id"]
            if arguments.get("stage_id"): params["pipeline_stage_id"] = arguments["stage_id"]
            result = await ghl_get("/opportunities/search", params)
        elif name == "get_custom_fields":
            result = await ghl_get("/custom-fields/", {"locationId": GHL_LOCATION_ID})
        elif name == "get_workflows":
            result = await ghl_get("/workflows/", {"locationId": GHL_LOCATION_ID})
        elif name == "get_location_stats":
            c = await ghl_get("/contacts/", {"locationId": GHL_LOCATION_ID, "limit": 1})
            p = await ghl_get("/opportunities/pipelines", {"locationId": GHL_LOCATION_ID})
            w = await ghl_get("/workflows/", {"locationId": GHL_LOCATION_ID})
            result = {"total_contacts": c.get("meta",{}).get("total","?"), "pipelines": len(p.get("pipelines",[])), "workflows": len(w.get("workflows",[]))}
        else:
            result = {"error": f"Unknown tool: {name}"}
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

sse = SseServerTransport("/messages/")

async def handle_sse(request):
    async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
        await mcp.run(streams[0], streams[1], mcp.create_initialization_options())

async def handle_messages(request):
    await sse.handle_post_message(request.scope, request.receive, request._send)

async def health(request):
    return Response("GHL MCP OK", status_code=200)

app = Starlette(routes=[
    Route("/", health),
    Route("/health", health),
    Route("/sse", handle_sse),
    Mount("/messages/", app=handle_messages),
])

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
