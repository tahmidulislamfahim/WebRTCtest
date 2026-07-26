import os
import uuid
import logging
from typing import List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, status, Depends
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from connection_manager import ConnectionManager
import database
import auth
from models import RegisterRequest, LoginRequest, AuthResponse, UserResponse, UsersListResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("webrtc_signaling")

app = FastAPI(
    title="WebRTC Signaling & JWT Auth Server",
    description="FastAPI WebRTC Signaling Server with JWT Auth, User Directory & Direct Calling",
    version="2.1.0",
    docs_url="/docs",
    openapi_url="/openapi.json"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

manager = ConnectionManager()
security = HTTPBearer()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

# --- REST Endpoints ---

@app.get("/")
async def root():
    return {
        "status": "online",
        "service": "WebRTC JWT Auth & Signaling API",
        "endpoints": {
            "register": "POST /api/register",
            "login": "POST /api/login",
            "users": "GET /api/users (Protected with Bearer JWT Token)",
            "user_websocket": "WS /ws/user/{user_id}",
            "room_websocket": "WS /ws/{room_id}/{peer_id}",
            "test_client": "GET /test"
        }
    }

@app.post("/api/register", response_model=AuthResponse)
async def register(req: RegisterRequest):
    """Registers a new user account and returns a JWT access token."""
    user = database.register_user(req.username, req.password, req.display_name)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username is already taken."
        )
    
    token = auth.create_access_token({"sub": user["id"], "username": user["username"]})

    return AuthResponse(
        success=True,
        message="Registration successful!",
        access_token=token,
        token_type="bearer",
        user=UserResponse(
            id=user["id"],
            username=user["username"],
            display_name=user["display_name"],
            is_online=manager.is_user_online(user["id"])
        )
    )

@app.post("/api/login", response_model=AuthResponse)
async def login(req: LoginRequest):
    """Authenticates user and returns a signed JWT access token."""
    user = database.authenticate_user(req.username, req.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password."
        )

    token = auth.create_access_token({"sub": user["id"], "username": user["username"]})

    return AuthResponse(
        success=True,
        message="Login successful!",
        access_token=token,
        token_type="bearer",
        user=UserResponse(
            id=user["id"],
            username=user["username"],
            display_name=user["display_name"],
            is_online=manager.is_user_online(user["id"])
        )
    )

@app.get("/api/users", response_model=UsersListResponse)
async def list_users(auth_header: HTTPAuthorizationCredentials = Depends(security)):
    """
    Returns list of all registered users EXCEPT the currently authenticated user.
    PROTECTED: Requires Bearer JWT Token in Authorization header.
    """
    token = auth_header.credentials
    payload = auth.decode_access_token(token)
    current_user_id = payload.get("sub")

    all_users = database.get_all_users()
    user_list = [
        UserResponse(
            id=u["id"],
            username=u["username"],
            display_name=u["display_name"],
            is_online=manager.is_user_online(u["id"])
        )
        for u in all_users
        if u["id"] != current_user_id
    ]
    return UsersListResponse(users=user_list)

@app.get("/rooms")
async def get_rooms():
    """Returns active rooms summary."""
    return {
        "active_rooms": manager.get_rooms_summary(),
        "online_users": manager.get_online_user_ids()
    }

@app.get("/test", response_class=HTMLResponse)
async def get_test_client():
    """Serves WebRTC test page."""
    test_page_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(test_page_path):
        return FileResponse(test_page_path)
    raise HTTPException(status_code=404, detail="Test client page not found.")

# --- WebSocket Endpoints ---

@app.websocket("/ws/user/{user_id}")
async def user_websocket_endpoint(websocket: WebSocket, user_id: str):
    """
    WebSocket connection for registered users.
    Handles online status, incoming call alerts, and direct WebRTC signaling.
    """
    await manager.connect_user(websocket, user_id)
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            target_user_id = data.get("targetUserId")

            data["senderId"] = user_id

            logger.info(f"User WebSocket message '{msg_type}' from user '{user_id}' to target '{target_user_id}'")

            if msg_type == "call_user":
                room_id = f"call_{uuid.uuid4().hex[:8]}"
                data["roomId"] = room_id

                sent = await manager.send_to_user(target_user_id, {
                    "type": "incoming_call",
                    "callerId": user_id,
                    "callerName": data.get("callerName", "Unknown"),
                    "roomId": room_id,
                    "isVideo": data.get("isVideo", True)
                })
                if not sent:
                    await websocket.send_json({
                        "type": "call_failed",
                        "reason": "User is offline or unavailable."
                    })

            elif msg_type == "accept_call":
                caller_id = data.get("callerId")
                room_id = data.get("roomId")
                await manager.send_to_user(caller_id, {
                    "type": "call_accepted",
                    "acceptorId": user_id,
                    "roomId": room_id
                })

            elif msg_type == "decline_call":
                caller_id = data.get("callerId")
                await manager.send_to_user(caller_id, {
                    "type": "call_declined",
                    "declinerId": user_id
                })

            elif msg_type in ["offer", "answer", "ice_candidate"]:
                if target_user_id:
                    await manager.send_to_user(target_user_id, data)
                elif data.get("roomId"):
                    await manager.broadcast_to_room(data.get("roomId"), data, exclude_peer_id=user_id)

    except WebSocketDisconnect:
        logger.info(f"User '{user_id}' WebSocket disconnected.")
    except Exception as e:
        logger.error(f"User WebSocket error for '{user_id}': {e}")
    finally:
        manager.disconnect_user(user_id)

@app.websocket("/ws/{room_id}/{peer_id}")
async def room_websocket_endpoint(websocket: WebSocket, room_id: str, peer_id: str):
    """Room-based WebRTC signaling endpoint for general room testing."""
    await manager.connect_room(websocket, room_id, peer_id)
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            target_id = data.get("targetId")

            data["senderId"] = peer_id
            data["roomId"] = room_id

            if msg_type in ["offer", "answer", "ice_candidate"]:
                if target_id:
                    await manager.send_to_peer(room_id, target_id, data)
                else:
                    await manager.broadcast_to_room(room_id, data, exclude_peer_id=peer_id)
            elif msg_type == "leave":
                break
            else:
                await manager.broadcast_to_room(room_id, data, exclude_peer_id=peer_id)
    except WebSocketDisconnect:
        logger.info(f"Room WebSocket disconnect for '{peer_id}' in '{room_id}'")
    finally:
        manager.disconnect_room(room_id, peer_id)
        await manager.broadcast_to_room(
            room_id=room_id,
            message={
                "type": "peer_left",
                "roomId": room_id,
                "peerId": peer_id
            }
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
