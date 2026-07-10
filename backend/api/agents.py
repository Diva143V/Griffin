from fastapi import APIRouter, WebSocket
import asyncio

router = APIRouter()

@router.websocket("/agent-stream")
async def agent_stream(websocket: WebSocket):
    await websocket.accept()
    steps = [
        "Planner started",
        "Searching papers",
        "Ranking evidence",
        "Generating synthesis"
    ]
    for step in steps:
        await websocket.send_json({
            "agent": step
        })
        await asyncio.sleep(0.5)
