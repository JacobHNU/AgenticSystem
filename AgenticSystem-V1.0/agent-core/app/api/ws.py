from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

@router.websocket("/ws/{agent_id}/stream")
async def agent_stream(websocket: WebSocket, agent_id: str):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_json({"type": "ack", "agent_id": agent_id})
    except WebSocketDisconnect:
        pass
