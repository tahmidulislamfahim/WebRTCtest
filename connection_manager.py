import json
import logging
from typing import Dict, List, Optional
from fastapi import WebSocket

logger = logging.getLogger("webrtc_signaling")

class ConnectionManager:
    """
    Manages WebSocket connections for:
    1. Active Users (user_id -> WebSocket) for receiving call notifications.
    2. Active Rooms (room_id -> { peer_id/user_id: WebSocket }) for WebRTC media signaling.
    """
    def __init__(self):
        # user_id -> WebSocket
        self.active_users: Dict[str, WebSocket] = {}
        # room_id -> { peer_id: WebSocket }
        self.active_rooms: Dict[str, Dict[str, WebSocket]] = {}

    # --- User Connection Management ---
    async def connect_user(self, websocket: WebSocket, user_id: str):
        """Registers an authenticated user's WebSocket connection."""
        await websocket.accept()
        self.active_users[user_id] = websocket
        logger.info(f"User '{user_id}' connected to WebSocket signaling. Total online users: {len(self.active_users)}")

    def disconnect_user(self, user_id: str):
        """Unregisters a user when disconnected."""
        if user_id in self.active_users:
            del self.active_users[user_id]
            logger.info(f"User '{user_id}' disconnected. Total online users: {len(self.active_users)}")

    def is_user_online(self, user_id: str) -> bool:
        """Returns True if user has an active WebSocket connection."""
        return user_id in self.active_users

    def get_online_user_ids(self) -> List[str]:
        """Returns list of all online user IDs."""
        return list(self.active_users.keys())

    async def send_to_user(self, user_id: str, message: dict) -> bool:
        """Sends a WebSocket message directly to a specific user by user_id."""
        if user_id in self.active_users:
            websocket = self.active_users[user_id]
            try:
                await websocket.send_json(message)
                return True
            except Exception as e:
                logger.error(f"Error sending message to user '{user_id}': {e}")
                return False
        return False

    # --- Room & WebRTC Signaling Management ---
    async def connect_room(self, websocket: WebSocket, room_id: str, peer_id: str):
        """Joins a peer into a specific WebRTC call room."""
        await websocket.accept()
        if room_id not in self.active_rooms:
            self.active_rooms[room_id] = {}

        existing_peers = list(self.active_rooms[room_id].keys())
        self.active_rooms[room_id][peer_id] = websocket
        logger.info(f"Peer '{peer_id}' joined room '{room_id}'. Total peers in room: {len(self.active_rooms[room_id])}")

        await websocket.send_json({
            "type": "room_joined",
            "roomId": room_id,
            "peerId": peer_id,
            "existingPeers": existing_peers
        })

        await self.broadcast_to_room(
            room_id=room_id,
            message={
                "type": "peer_joined",
                "roomId": room_id,
                "peerId": peer_id
            },
            exclude_peer_id=peer_id
        )

    def disconnect_room(self, room_id: str, peer_id: str):
        """Removes peer from a room."""
        if room_id in self.active_rooms:
            if peer_id in self.active_rooms[room_id]:
                del self.active_rooms[room_id][peer_id]
            if not self.active_rooms[room_id]:
                del self.active_rooms[room_id]

    async def send_to_peer(self, room_id: str, target_peer_id: str, message: dict) -> bool:
        """Sends a message to a specific peer in a room."""
        if room_id in self.active_rooms and target_peer_id in self.active_rooms[room_id]:
            websocket = self.active_rooms[room_id][target_peer_id]
            try:
                await websocket.send_json(message)
                return True
            except Exception as e:
                logger.error(f"Error sending to peer '{target_peer_id}' in room '{room_id}': {e}")
                return False
        return False

    async def broadcast_to_room(self, room_id: str, message: dict, exclude_peer_id: Optional[str] = None):
        """Broadcasts a message to all peers in a room except the excluded peer."""
        if room_id in self.active_rooms:
            for peer_id, websocket in list(self.active_rooms[room_id].items()):
                if exclude_peer_id is None or peer_id != exclude_peer_id:
                    try:
                        await websocket.send_json(message)
                    except Exception as e:
                        logger.error(f"Failed to broadcast to peer '{peer_id}': {e}")

    def get_rooms_summary(self) -> dict:
        """Returns snapshot of active rooms."""
        summary = {}
        for room_id, peers in self.active_rooms.items():
            summary[room_id] = {
                "peer_count": len(peers),
                "peers": list(peers.keys())
            }
        return summary
