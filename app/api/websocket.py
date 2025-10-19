"""WebSocket API endpoints for real-time data streaming."""
import asyncio
import json
from typing import Dict, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

from app.brokers import get_broker
from app.services.data_ingestion import data_ingestion_service
from app.database.connection import get_db_pool
from app.database.models import SubscriptionQueries


router = APIRouter()


class ConnectionManager:
    """Manage WebSocket connections."""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.broker_connected = False
        self.broker_task = None
    
    async def connect(self, websocket: WebSocket):
        """Accept and register a WebSocket connection."""
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"Client connected. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        self.active_connections.discard(websocket)
        logger.info(f"Client disconnected. Total connections: {len(self.active_connections)}")
    
    async def broadcast(self, message: Dict):
        """Broadcast message to all connected clients."""
        if not self.active_connections:
            return
        
        message_json = json.dumps(message, default=str)
        disconnected = set()
        
        for connection in self.active_connections:
            try:
                await connection.send_text(message_json)
            except Exception as e:
                logger.error(f"Failed to send to client: {e}")
                disconnected.add(connection)
        
        # Remove disconnected clients
        for conn in disconnected:
            self.disconnect(conn)
    
    async def start_broker_connection(self):
        """Start broker WebSocket connection."""
        if self.broker_connected:
            logger.warning("Broker already connected")
            return
        
        try:
            # Get subscribed instruments
            pool = await get_db_pool()
            tokens = await SubscriptionQueries.get_subscribed_instruments(pool)
            
            if not tokens:
                logger.warning("No instruments subscribed. Start broker connection skipped.")
                return
            
            # Connect to broker
            broker = get_broker()
            
            async def tick_callback(tick_data: Dict):
                """Handle incoming ticks from broker."""
                # Store in database
                await data_ingestion_service.handle_tick(tick_data)
                
                # Broadcast to connected clients
                await self.broadcast({
                    "type": "tick",
                    "data": tick_data
                })
            
            await broker.connect_websocket(tokens, tick_callback)
            self.broker_connected = True
            logger.info(f"Broker WebSocket connected with {len(tokens)} instruments")
            
        except Exception as e:
            logger.error(f"Failed to connect to broker WebSocket: {e}")
            self.broker_connected = False
            raise
    
    async def stop_broker_connection(self):
        """Stop broker WebSocket connection."""
        if not self.broker_connected:
            return
        
        try:
            broker = get_broker()
            await broker.disconnect_websocket()
            self.broker_connected = False
            logger.info("Broker WebSocket disconnected")
        except Exception as e:
            logger.error(f"Failed to disconnect broker WebSocket: {e}")


# Global connection manager
connection_manager = ConnectionManager()


@router.websocket("/ticks")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time tick streaming.
    
    Clients connect to this endpoint to receive real-time market data
    for subscribed instruments.
    """
    await connection_manager.connect(websocket)
    
    # Start broker connection if not already connected
    if not connection_manager.broker_connected:
        try:
            await connection_manager.start_broker_connection()
        except Exception as e:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": f"Failed to connect to broker: {str(e)}"
            }))
    
    try:
        # Keep connection alive and listen for client messages
        while True:
            data = await websocket.receive_text()
            
            # Handle client commands
            try:
                message = json.loads(data)
                command = message.get("command")
                
                if command == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
                elif command == "status":
                    await websocket.send_text(json.dumps({
                        "type": "status",
                        "broker_connected": connection_manager.broker_connected,
                        "active_connections": len(connection_manager.active_connections)
                    }))
                else:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": f"Unknown command: {command}"
                    }))
                    
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Invalid JSON"
                }))
                
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)
        logger.info("Client disconnected normally")
        
        # Stop broker connection if no clients connected
        if not connection_manager.active_connections:
            await connection_manager.stop_broker_connection()
            
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        connection_manager.disconnect(websocket)


@router.post("/start")
async def start_streaming():
    """Manually start the broker WebSocket connection."""
    try:
        await connection_manager.start_broker_connection()
        return {
            "success": True,
            "message": "Broker WebSocket connection started"
        }
    except Exception as e:
        logger.error(f"Failed to start streaming: {e}")
        return {
            "success": False,
            "message": str(e)
        }


@router.post("/stop")
async def stop_streaming():
    """Manually stop the broker WebSocket connection."""
    try:
        await connection_manager.stop_broker_connection()
        return {
            "success": True,
            "message": "Broker WebSocket connection stopped"
        }
    except Exception as e:
        logger.error(f"Failed to stop streaming: {e}")
        return {
            "success": False,
            "message": str(e)
        }


@router.get("/status")
async def get_streaming_status():
    """Get current streaming status."""
    return {
        "broker_connected": connection_manager.broker_connected,
        "active_clients": len(connection_manager.active_connections),
        "status": "streaming" if connection_manager.broker_connected else "idle"
    }

