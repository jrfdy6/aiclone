"""
WebSocket Routes for Real-Time Updates
"""
import logging
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.services.websocket_manager import manager

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, user_id: str = Query(...)):
    """
    WebSocket endpoint for real-time updates.
    
    Query params:
    - user_id: User identifier for filtering events
    """
    await manager.connect(websocket, user_id)
    
    try:
        # Send initial connection confirmation
        await manager.send_personal_message({
            "type": "connection",
            "status": "connected",
            "user_id": user_id,
            "message": "WebSocket connection established"
        }, websocket)
        
        # Keep connection alive and listen for messages
        while True:
            try:
                # Wait for client messages (ping/pong or commands)
                data = await websocket.receive_text()
                
                try:
                    message = json.loads(data)
                    message_type = message.get("type")
                    
                    if message_type == "ping":
                        # Respond to ping with pong
                        await manager.send_personal_message({
                            "type": "pong",
                            "timestamp": message.get("timestamp")
                        }, websocket)
                    elif message_type == "subscribe":
                        # Handle subscription to specific event types
                        event_types = message.get("event_types", [])
                        await manager.send_personal_message({
                            "type": "subscription",
                            "status": "subscribed",
                            "event_types": event_types
                        }, websocket)
                    else:
                        await manager.send_personal_message({
                            "type": "error",
                            "message": f"Unknown message type: {message_type}"
                        }, websocket)
                except json.JSONDecodeError:
                    await manager.send_personal_message({
                        "type": "error",
                        "message": "Invalid JSON format"
                    }, websocket)
                    
            except WebSocketDisconnect:
                break
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for user {user_id}")
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {e}")
    finally:
        manager.disconnect(websocket)


@router.get("/ws/status")
async def websocket_status():
    """Get WebSocket connection status"""
    return {
        "active_users": len(manager.active_connections),
        "total_connections": manager.get_total_connections(),
        "connections_per_user": {
            user_id: manager.get_user_connection_count(user_id)
            for user_id in manager.active_connections.keys()
        }
    }

