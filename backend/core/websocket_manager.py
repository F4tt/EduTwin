"""
WebSocket Manager for EduTwin
Handles real-time communication for chatbot, notifications, and study updates
"""
import socketio
from typing import Dict, Set, Optional
import asyncio
from datetime import datetime
from core.logging_config import get_logger

logger = get_logger(__name__)

# Create Socket.IO server instance
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins='*',
    logger=False,
    engineio_logger=False
)

# Track active connections
user_sessions: Dict[int, Set[str]] = {}  # user_id -> set of session_ids
session_users: Dict[str, int] = {}  # session_id -> user_id


class WebSocketManager:
    """Manages WebSocket connections and events"""
    
    @staticmethod
    async def emit_to_user(user_id: int, event: str, data: dict):
        """Emit an event to all sessions of a specific user"""
        if user_id in user_sessions:
            for sid in user_sessions[user_id]:
                try:
                    await sio.emit(event, data, room=sid)
                    logger.debug(f"Emitted {event} to user {user_id} session {sid}")
                except Exception as e:
                    logger.error(f"Failed to emit to session {sid}: {e}")
    
    @staticmethod
    async def emit_to_session(session_id: str, event: str, data: dict):
        """Emit an event to a specific session"""
        try:
            await sio.emit(event, data, room=session_id)
            logger.debug(f"Emitted {event} to session {session_id}")
        except Exception as e:
            logger.error(f"Failed to emit to session {session_id}: {e}")
    
    @staticmethod
    async def broadcast(event: str, data: dict):
        """Broadcast an event to all connected clients"""
        try:
            await sio.emit(event, data)
            logger.debug(f"Broadcasted {event} to all clients")
        except Exception as e:
            logger.error(f"Failed to broadcast: {e}")
    
    @staticmethod
    def get_user_sessions(user_id: int) -> Set[str]:
        """Get all session IDs for a user"""
        return user_sessions.get(user_id, set())
    
    @staticmethod
    def get_session_user(session_id: str) -> Optional[int]:
        """Get user ID for a session"""
        return session_users.get(session_id)


# Socket.IO Event Handlers

@sio.event
async def connect(sid, environ, auth):
    """Handle client connection"""
    logger.info(f"Client connected: {sid}")
    
    # Extract user_id from auth data if available
    if auth and 'user_id' in auth:
        user_id = auth['user_id']
        
        # Track the connection
        if user_id not in user_sessions:
            user_sessions[user_id] = set()
        user_sessions[user_id].add(sid)
        session_users[sid] = user_id
        
        # Auto-join user room for receiving reasoning events
        user_room = f"user_{user_id}"
        await sio.enter_room(sid, user_room)
        logger.info(f"User {user_id} connected with session {sid}, joined room {user_room}")
        
        # Send connection confirmation
        await sio.emit('connected', {
            'message': 'Connected to EduTwin WebSocket',
            'user_id': user_id,
            'user_room': user_room,
            'timestamp': datetime.utcnow().isoformat()
        }, room=sid)


@sio.event
async def disconnect(sid):
    """Handle client disconnection"""
    logger.info(f"Client disconnected: {sid}")
    
    # Clean up tracking
    if sid in session_users:
        user_id = session_users[sid]
        if user_id in user_sessions:
            user_sessions[user_id].discard(sid)
            if not user_sessions[user_id]:
                del user_sessions[user_id]
        del session_users[sid]
        logger.info(f"User {user_id} disconnected session {sid}")


@sio.event
async def authenticate(sid, data):
    """Handle authentication after connection"""
    try:
        user_id = data.get('user_id')
        if not user_id:
            await sio.emit('error', {'message': 'Missing user_id'}, room=sid)
            return
        
        # Update tracking
        if user_id not in user_sessions:
            user_sessions[user_id] = set()
        user_sessions[user_id].add(sid)
        session_users[sid] = user_id
        
        logger.info(f"User {user_id} authenticated session {sid}")
        
        await sio.emit('authenticated', {
            'message': 'Authentication successful',
            'user_id': user_id
        }, room=sid)
        
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        await sio.emit('error', {'message': 'Authentication failed'}, room=sid)


@sio.event
async def ping(sid):
    """Handle ping for connection health check"""
    await sio.emit('pong', {'timestamp': datetime.utcnow().isoformat()}, room=sid)


@sio.event
async def join_chat_session(sid, data):
    """Join a specific chat session room"""
    try:
        chat_session_id = data.get('chat_session_id')
        if chat_session_id:
            room_name = f"chat_{chat_session_id}"
            await sio.enter_room(sid, room_name)
            logger.info(f"Session {sid} joined chat room {room_name}")
            await sio.emit('joined_chat', {'chat_session_id': chat_session_id}, room=sid)
    except Exception as e:
        logger.error(f"Error joining chat session: {e}")


@sio.event
async def leave_chat_session(sid, data):
    """Leave a specific chat session room"""
    try:
        chat_session_id = data.get('chat_session_id')
        if chat_session_id:
            room_name = f"chat_{chat_session_id}"
            await sio.leave_room(sid, room_name)
            logger.info(f"Session {sid} left chat room {room_name}")
    except Exception as e:
        logger.error(f"Error leaving chat session: {e}")


# Helper functions for emitting specific events

async def emit_chat_message(chat_session_id: str, message: dict):
    """Emit a new chat message to all clients in the chat session"""
    room_name = f"chat_{chat_session_id}"
    await sio.emit('chat_message', message, room=room_name)
    logger.debug(f"Emitted chat message to room {room_name}")


async def emit_chat_typing(chat_session_id: str, is_typing: bool):
    """Emit typing indicator to chat session"""
    room_name = f"chat_{chat_session_id}"
    await sio.emit('chat_typing', {'is_typing': is_typing}, room=room_name)


async def emit_study_update(user_id: int, update: dict):
    """Send a study update to a specific user"""
    await WebSocketManager.emit_to_user(user_id, 'study_update', update)
    logger.info(f"Sent study update to user {user_id}")


async def emit_prediction_update(user_id: int, predictions: dict):
    """Send updated predictions to a user"""
    await WebSocketManager.emit_to_user(user_id, 'prediction_update', predictions)
    logger.info(f"Sent prediction update to user {user_id}")


# Create ASGI application for Socket.IO
socket_app = socketio.ASGIApp(sio, socketio_path='/socket.io')
