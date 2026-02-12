"""
WebSocket connection manager for real-time timer broadcasts.
Manages active connections per round and broadcasts window status updates.
"""

from typing import Dict, List
from uuid import UUID
import asyncio
import logging

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages WebSocket connections for countdown timer broadcasts.

    Each round can have multiple connected clients receiving real-time
    countdown updates.
    """

    def __init__(self):
        # round_id -> list of active websocket connections
        self.active_connections: Dict[UUID, List[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, round_id: UUID) -> None:
        """
        Accept and register a new WebSocket connection for a round.

        Args:
            websocket: WebSocket connection to register
            round_id: UUID of the round to subscribe to
        """
        await websocket.accept()

        async with self._lock:
            if round_id not in self.active_connections:
                self.active_connections[round_id] = []
            self.active_connections[round_id].append(websocket)

        logger.info(f"WebSocket connected for round {round_id}. Total connections: {len(self.active_connections[round_id])}")

    async def disconnect(self, websocket: WebSocket, round_id: UUID) -> None:
        """
        Unregister a WebSocket connection.

        Args:
            websocket: WebSocket connection to remove
            round_id: UUID of the round
        """
        async with self._lock:
            if round_id in self.active_connections:
                try:
                    self.active_connections[round_id].remove(websocket)
                    if not self.active_connections[round_id]:
                        # Remove empty list to save memory
                        del self.active_connections[round_id]
                    logger.info(f"WebSocket disconnected for round {round_id}")
                except ValueError:
                    # Connection not in list (already removed)
                    pass

    async def broadcast_to_round(self, round_id: UUID, message: dict) -> None:
        """
        Broadcast a message to all connected clients for a specific round.

        Automatically handles and removes dead connections.

        Args:
            round_id: UUID of the round
            message: JSON-serializable message to broadcast
        """
        if round_id not in self.active_connections:
            return

        # Make a copy to avoid modification during iteration
        connections = self.active_connections[round_id].copy()
        dead_connections = []

        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send message to connection: {e}")
                dead_connections.append(connection)

        # Remove dead connections
        if dead_connections:
            async with self._lock:
                for dead_conn in dead_connections:
                    try:
                        self.active_connections[round_id].remove(dead_conn)
                    except (ValueError, KeyError):
                        pass

                # Clean up empty list
                if round_id in self.active_connections and not self.active_connections[round_id]:
                    del self.active_connections[round_id]

    def get_connection_count(self, round_id: UUID) -> int:
        """
        Get the number of active connections for a round.

        Args:
            round_id: UUID of the round

        Returns:
            Number of active connections
        """
        return len(self.active_connections.get(round_id, []))

    def get_total_connections(self) -> int:
        """
        Get the total number of active connections across all rounds.

        Returns:
            Total connection count
        """
        return sum(len(conns) for conns in self.active_connections.values())


# Global singleton instance
connection_manager = ConnectionManager()
