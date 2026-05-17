import os, json, httpx
from mcp.server.fastmcp import FastMCP

GHL_API_KEY = os.environ.get("GHL_API_KEY", "")
GHL_LOCATION_ID = os.environ.get("GHL_LOCATION_ID", "")
BASE_URL = "https://services.leadconnectorhq.com"
HEADERS = {"Authorization": f"Bearer {GHL_API_KEY}", "Version": "2021-07-28", "Content-Type": "application/json"}
PORT = int(os.environ.get("PORT", 8080))

mcp = FastMCP("GHL Ecometri", host="0.0.0.0", port=PORT)

async def ghl_get(path, params={}):
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}{path}", headers=HEADERS, params=params)
        r.raise_for_status()
        return r.json()

@mcp.tool()
async def get_contacts_by_tag(tag: str, max_pages: int = 10) -> str:
    """Get ALL contacts with a specific tag from GHL, auto-paginated"""
    all_contacts, skip = [], 0
    for _ in range(max_pages):
        data = await ghl_get("/contacts/", {"locationId": GHL_LOCATION_ID, "tags": tag, "limit": 100, "skip": skip})
        batch = data.get("contacts", [])
        all_contacts.extend(batch)
        if len(batch) < 100: break
        skip += 100
    return json.dumps({"total": len(all_contacts), "contacts": all_contacts}, ensure_ascii=False)

@mcp.tool()
async def get_contact(contact_id: str) -> str:
    """Get full details of a single GHL contact including all custom fields"""
    return json.dumps(await ghl_get(f"/contacts/{contact_id}"), ensure_ascii=False)

@mcp.tool()
async def get_pipelines() -> str:
    """Get all GHL pipelines and their stages"""
    return json.dumps(await ghl_get("/opportunities/pipelines", {"locationId": GHL_LOCATION_ID}), ensure_ascii=False)

@mcp.tool()
async def get_opportunities(pipeline_id: str = "", stage_id: str = "", limit: int = 100) -> str:
    """Get deals/opportunities from GHL pipeline"""
    params = {"location_id": GHL_LOCATION_ID, "limit": limit}
    if pipeline_id: params["pipeline_id"] = pipeline_id
    if stage_id: params["pipeline_stage_id"] = stage_id
    return json.dumps(await ghl_get("/opportunities/search", params), ensure_ascii=False)

@mcp.tool()
async def get_custom_fields() -> str:
    """Get all custom field definitions for this GHL location"""
    return json.dumps(await ghl_get("/custom-fields/", {"locationId": GHL_LOCATION_ID}), ensure_ascii=False)

@mcp.tool()
async def get_workflows() -> str:
    """Get all GHL workflows and their enrollment stats"""
    return json.dumps(await ghl_get("/workflows/", {"locationId": GHL_LOCATION_ID}), ensure_ascii=False)

@mcp.tool()
async def get_location_stats() -> str:
    """Get total contacts, pipelines and workflows count"""
    c = await ghl_get("/contacts/", {"locationId": GHL_LOCATION_ID, "limit": 1})
    p = await ghl_get("/opportunities/pipelines", {"locationId": GHL_LOCATION_ID})
    w = await ghl_get("/workflows/", {"locationId": GHL_LOCATION_ID})
    return json.dumps({"total_contacts": c.get("meta",{}).get("total","?"), "pipelines": len(p.get("pipelines",[])), "workflows": len(w.get("workflows",[]))})

if __name__ == "__main__":
    import uvicorn
    from mcp.server.fastmcp import FastMCP
    app = mcp.get_asgi_app()
    uvicorn.run(app, host="0.0.0.0", port=PORT)
