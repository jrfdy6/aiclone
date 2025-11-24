"""
WebSocket Connection Manager
Manages WebSocket connections for real-time updates
"""
import logging
import json
from typing import Dict, Set, List
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections per user"""
    
    def __init__(self):
        # Map user_id -> Set of WebSocket connections
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # Map WebSocket -> user_id
        self.connection_users: Dict[WebSocket, str] = {}
    
    async def connect(self, websocket: WebSocket, user_id: str):
        """Accept a new WebSocket connection"""
        await websocket.accept()
        
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        
        self.active_connections[user_id].add(websocket)
        self.connection_users[websocket] = user_id
        
        logger.info(f"WebSocket connected for user {user_id}. Total connections: {len(self.active_connections[user_id])}")
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection"""
        if websocket in self.connection_users:
            user_id = self.connection_users[websocket]
            
            if user_id in self.active_connections:
                self.active_connections[user_id].discard(websocket)
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]
            
            del self.connection_users[websocket]
            logger.info(f"WebSocket disconnected for user {user_id}")
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """Send a message to a specific connection"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            self.disconnect(websocket)
    
    async def broadcast_to_user(self, user_id: str, message: dict):
        """Broadcast a message to all connections for a user"""
        if user_id not in self.active_connections:
            return
        
        disconnected = []
        for websocket in self.active_connections[user_id]:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to user {user_id}: {e}")
                disconnected.append(websocket)
        
        # Clean up disconnected connections
        for ws in disconnected:
            self.disconnect(ws)
    
    async def broadcast_to_all(self, message: dict):
        """Broadcast a message to all connected users"""
        disconnected = []
        for websocket, user_id in list(self.connection_users.items()):
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to all: {e}")
                disconnected.append(websocket)
        
        # Clean up disconnected connections
        for ws in disconnected:
            self.disconnect(ws)
    
    def get_user_connection_count(self, user_id: str) -> int:
        """Get the number of active connections for a user"""
        return len(self.active_connections.get(user_id, set()))
    
    def get_total_connections(self) -> int:
        """Get total number of active connections"""
        return len(self.connection_users)


# Global connection manager instance
manager = ConnectionManager()


async def broadcast_activity(user_id: str, activity_type: str, title: str, message: str, metadata: dict = None):
    """Broadcast an activity event to a user"""
    event = {
        "type": "activity",
        "activity_type": activity_type,
        "title": title,
        "message": message,
        "metadata": metadata or {},
        "timestamp": datetime.now().isoformat(),
    }
    await manager.broadcast_to_user(user_id, event)


async def broadcast_notification(user_id: str, notification_type: str, title: str, message: str, link: str = None):
    """Broadcast a notification to a user"""
    event = {
        "type": "notification",
        "notification_type": notification_type,
        "title": title,
        "message": message,
        "link": link,
        "timestamp": datetime.now().isoformat(),
    }
    await manager.broadcast_to_user(user_id, event)


async def broadcast_task_update(user_id: str, task_id: str, status: str, progress: int = None, message: str = None):
    """Broadcast a task status update"""
    event = {
        "type": "task_update",
        "task_id": task_id,
        "status": status,
        "progress": progress,
        "message": message,
        "timestamp": datetime.now().isoformat(),
    }
    await manager.broadcast_to_user(user_id, event)

