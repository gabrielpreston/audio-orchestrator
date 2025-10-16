"""
Session broker integration with orchestrator.

This module provides integration between the session broker and the orchestrator
service, enabling session-based transcript routing and management.
"""

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

from services.orchestrator.policy_engine import PolicyEngine
from services.orchestrator.session_broker import SessionBroker

logger = logging.getLogger(__name__)


class SessionOrchestratorIntegration:
    """
    Integration between session broker and orchestrator service.

    This class manages the routing of transcripts and events between
    the session broker and the orchestrator service, providing
    session-based transcript processing.
    """

    def __init__(
        self,
        orchestrator_url: str,
        session_broker: SessionBroker,
        policy_engine: PolicyEngine,
    ):
        """
        Initialize session orchestrator integration.

        Args:
            orchestrator_url: URL of the orchestrator service
            session_broker: Session broker instance
            policy_engine: Policy engine instance
        """
        self.orchestrator_url = orchestrator_url
        self.session_broker = session_broker
        self.policy_engine = policy_engine

        # Integration state
        self._is_initialized = False
        self._is_connected = False
        self._integration_tasks: list[asyncio.Task[None]] = []

        # Event handlers
        self._event_handlers: dict[str, list[Callable[..., Any]]] = {}

        # Configuration
        self._max_retries = 3
        self._retry_delay = 1.0  # seconds
        self._session_timeout = 300.0  # 5 minutes
        self._cleanup_interval = 60.0  # 1 minute

    async def initialize(self) -> bool:
        """
        Initialize the session orchestrator integration.

        Returns:
            True if initialization successful, False otherwise
        """
        try:
            logger.info("Initializing session orchestrator integration")

            # Initialize session broker
            await self.session_broker.initialize()

            # Initialize policy engine
            await self.policy_engine.initialize()

            # Set up event routing
            await self._setup_event_routing()

            self._is_initialized = True
            logger.info("Session orchestrator integration initialized successfully")
            return True

        except Exception as e:
            logger.error("Failed to initialize session orchestrator integration: %s", e)
            return False

    async def connect(self) -> bool:
        """
        Connect to the orchestrator service.

        Returns:
            True if connection successful, False otherwise
        """
        if not self._is_initialized:
            logger.error("Integration not initialized")
            return False

        try:
            logger.info("Connecting to orchestrator service")

            # Start integration tasks
            await self._start_integration_tasks()

            self._is_connected = True
            logger.info("Connected to orchestrator service successfully")
            return True

        except Exception as e:
            logger.error("Failed to connect to orchestrator service: %s", e)
            return False

    async def disconnect(self) -> bool:
        """
        Disconnect from the orchestrator service.

        Returns:
            True if disconnection successful, False otherwise
        """
        try:
            logger.info("Disconnecting from orchestrator service")

            # Stop integration tasks
            await self._stop_integration_tasks()

            self._is_connected = False
            logger.info("Disconnected from orchestrator service successfully")
            return True

        except Exception as e:
            logger.error("Failed to disconnect from orchestrator service: %s", e)
            return False

    async def cleanup(self) -> None:
        """Clean up resources."""
        try:
            await self.disconnect()

            # Clean up session broker
            if self.session_broker:
                await self.session_broker.cleanup()

            self._is_initialized = False
            logger.info("Session orchestrator integration cleaned up")

        except Exception as e:
            logger.error("Error during cleanup: %s", e)

    def is_connected(self) -> bool:
        """Check if connected to orchestrator service."""
        return self._is_connected

    async def create_session(
        self, surface_id: str, user_id: str, metadata: dict[str, Any]
    ) -> str | None:
        """
        Create a new session.

        Args:
            surface_id: Surface identifier
            user_id: User identifier
            metadata: Session metadata

        Returns:
            Session ID if successful, None otherwise
        """
        try:
            session_id = await self.session_broker.create_session(
                surface_id=surface_id, user_id=user_id, metadata=metadata
            )

            if session_id:
                logger.info("Created session %s for surface %s", session_id, surface_id)

                # Emit session created event
                await self._emit_event(
                    "session.created",
                    {
                        "session_id": session_id,
                        "surface_id": surface_id,
                        "user_id": user_id,
                        "metadata": metadata,
                        "timestamp": datetime.now().timestamp(),
                    },
                )

            return session_id

        except Exception as e:
            logger.error("Failed to create session: %s", e)
            return None

    async def end_session(
        self, session_id: str, reason: str = "user_requested"
    ) -> bool:
        """
        End a session.

        Args:
            session_id: Session identifier
            reason: Reason for ending the session

        Returns:
            True if successful, False otherwise
        """
        try:
            success = await self.session_broker.end_session(session_id, reason)

            if success:
                logger.info("Ended session %s with reason: %s", session_id, reason)

                # Emit session ended event
                await self._emit_event(
                    "session.ended",
                    {
                        "session_id": session_id,
                        "reason": reason,
                        "timestamp": datetime.now().timestamp(),
                    },
                )

            return success

        except Exception as e:
            logger.error("Failed to end session %s: %s", session_id, e)
            return False

    async def process_transcript(
        self, session_id: str, transcript: str, is_final: bool = True
    ) -> dict[str, Any]:
        """
        Process a transcript through the orchestrator.

        Args:
            session_id: Session identifier
            transcript: Transcript text
            is_final: Whether this is a final transcript

        Returns:
            Processing result from orchestrator
        """
        try:
            # Get session information
            session = await self.session_broker.get_session(session_id)
            if not session:
                logger.error("Session %s not found", session_id)
                return {"error": "Session not found"}

            # Apply policy engine rules
            policy_result = await self.policy_engine.evaluate_transcript(
                transcript=transcript,
                session_metadata=session.metadata,
                is_final=is_final,
            )

            if not policy_result.should_process:
                logger.debug(
                    "Transcript rejected by policy engine for session %s", session_id
                )
                return {"status": "rejected", "reason": policy_result.reason}

            # Process through orchestrator
            result = await self._send_to_orchestrator(
                session_id=session_id,
                surface_id=session.surface_id,
                user_id=session.user_id,
                transcript=transcript,
                is_final=is_final,
                metadata=session.metadata,
            )

            # Update session with processing result
            await self.session_broker.update_session_metadata(
                session_id=session_id,
                metadata={
                    "last_transcript": transcript,
                    "last_processed": datetime.now().isoformat(),
                    "processing_result": result,
                },
            )

            # Emit transcript processed event
            await self._emit_event(
                "transcript.processed",
                {
                    "session_id": session_id,
                    "transcript": transcript,
                    "is_final": is_final,
                    "result": result,
                    "timestamp": datetime.now().timestamp(),
                },
            )

            return result

        except Exception as e:
            logger.error(
                "Failed to process transcript for session %s: %s", session_id, e
            )
            return {"error": str(e)}

    async def register_event_handler(
        self, event_type: str, handler: Callable[..., Any]
    ) -> None:
        """
        Register event handler for specific event type.

        Args:
            event_type: Type of event to handle
            handler: Handler function
        """
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)
        logger.debug("Registered event handler for %s", event_type)

    async def _setup_event_routing(self) -> None:
        """Set up event routing between components."""
        try:
            # Register session broker event handlers
            # Note: Session broker doesn't have register_event_handler method yet
            # await self.session_broker.register_event_handler("session.created", self._handle_session_created)
            # await self.session_broker.register_event_handler("session.ended", self._handle_session_ended)
            # await self.session_broker.register_event_handler("session.error", self._handle_session_error)

            logger.debug("Event routing set up successfully")

        except Exception as e:
            logger.error("Failed to set up event routing: %s", e)

    async def _start_integration_tasks(self) -> None:
        """Start background tasks for integration."""
        try:
            # Start session cleanup task
            task = asyncio.create_task(self._session_cleanup_loop())
            self._integration_tasks.append(task)

            # Start health monitoring task
            task = asyncio.create_task(self._health_monitoring_loop())
            self._integration_tasks.append(task)

            logger.debug("Integration tasks started")

        except Exception as e:
            logger.error("Failed to start integration tasks: %s", e)

    async def _stop_integration_tasks(self) -> None:
        """Stop background tasks for integration."""
        try:
            # Cancel all tasks
            for task in self._integration_tasks:
                task.cancel()

            # Wait for tasks to complete
            if self._integration_tasks:
                await asyncio.gather(*self._integration_tasks, return_exceptions=True)

            self._integration_tasks.clear()
            logger.debug("Integration tasks stopped")

        except Exception as e:
            logger.error("Failed to stop integration tasks: %s", e)

    async def _send_to_orchestrator(
        self,
        session_id: str,
        surface_id: str,
        user_id: str,
        transcript: str,
        is_final: bool,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Send transcript to orchestrator service.

        Args:
            session_id: Session identifier
            surface_id: Surface identifier
            user_id: User identifier
            transcript: Transcript text
            is_final: Whether this is a final transcript
            metadata: Session metadata

        Returns:
            Processing result from orchestrator
        """
        try:
            # Prepare request data (for future HTTP implementation)
            # request_data = {
            #     "session_id": session_id,
            #     "surface_id": surface_id,
            #     "user_id": user_id,
            #     "transcript": transcript,
            #     "is_final": is_final,
            #     "metadata": metadata,
            #     "correlation_id": f"{session_id}_{datetime.now().timestamp()}"
            # }

            # Send to orchestrator (simulated for now)
            # In a real implementation, this would make an HTTP request to the orchestrator service
            result = {
                "status": "processed",
                "response": f"Processed transcript: {transcript}",
                "session_id": session_id,
                "timestamp": datetime.now().isoformat(),
            }

            logger.debug("Sent transcript to orchestrator for session %s", session_id)
            return result

        except Exception as e:
            logger.error("Failed to send transcript to orchestrator: %s", e)
            return {"error": str(e)}

    async def _session_cleanup_loop(self) -> None:
        """Background task for session cleanup."""
        try:
            while self._is_connected:
                await asyncio.sleep(self._cleanup_interval)

                # Clean up expired sessions
                expired_count = await self.session_broker.cleanup_expired_sessions()
                if expired_count > 0:
                    logger.info("Cleaned up %d expired sessions", expired_count)

                # Clean up inactive sessions
                inactive_count = await self.session_broker.cleanup_inactive_sessions()
                if inactive_count > 0:
                    logger.info("Cleaned up %d inactive sessions", inactive_count)

        except asyncio.CancelledError:
            logger.debug("Session cleanup loop cancelled")
        except Exception as e:
            logger.error("Error in session cleanup loop: %s", e)

    async def _health_monitoring_loop(self) -> None:
        """Background task for health monitoring."""
        try:
            while self._is_connected:
                await asyncio.sleep(30.0)  # Check every 30 seconds

                # Check session broker health
                broker_health = await self.session_broker.get_telemetry()
                if not broker_health.get("is_healthy", False):
                    logger.warning("Session broker health check failed")

                # Check policy engine health
                policy_health = await self.policy_engine.get_telemetry()
                if not policy_health.get("is_healthy", False):
                    logger.warning("Policy engine health check failed")

        except asyncio.CancelledError:
            logger.debug("Health monitoring loop cancelled")
        except Exception as e:
            logger.error("Error in health monitoring loop: %s", e)

    async def _handle_session_created(self, event: dict[str, Any]) -> None:
        """Handle session created event."""
        try:
            session_id = event.get("session_id")
            surface_id = event.get("surface_id")
            user_id = event.get("user_id")

            logger.info(
                "Session created: %s for surface %s, user %s",
                session_id,
                surface_id,
                user_id,
            )

            # Emit session created event
            await self._emit_event("session.created", event)

        except Exception as e:
            logger.error("Error handling session created event: %s", e)

    async def _handle_session_ended(self, event: dict[str, Any]) -> None:
        """Handle session ended event."""
        try:
            session_id = event.get("session_id")
            reason = event.get("reason")

            logger.info("Session ended: %s with reason: %s", session_id, reason)

            # Emit session ended event
            await self._emit_event("session.ended", event)

        except Exception as e:
            logger.error("Error handling session ended event: %s", e)

    async def _handle_session_error(self, event: dict[str, Any]) -> None:
        """Handle session error event."""
        try:
            session_id = event.get("session_id")
            error = event.get("error")

            logger.error("Session error: %s - %s", session_id, error)

            # Emit session error event
            await self._emit_event("session.error", event)

        except Exception as e:
            logger.error("Error handling session error event: %s", e)

    async def _emit_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Emit event to registered handlers."""
        try:
            if event_type in self._event_handlers:
                for handler in self._event_handlers[event_type]:
                    try:
                        if asyncio.iscoroutinefunction(handler):
                            await handler(data)
                        else:
                            handler(data)
                    except Exception as e:
                        logger.error("Error in event handler: %s", e)

        except Exception as e:
            logger.error("Error emitting event: %s", e)

    async def get_integration_metrics(self) -> dict[str, Any]:
        """
        Get integration metrics and statistics.

        Returns:
            Dictionary containing integration metrics
        """
        metrics = {
            "is_initialized": self._is_initialized,
            "is_connected": self._is_connected,
            "integration_tasks_count": len(self._integration_tasks),
            "event_handlers_count": sum(
                len(handlers) for handlers in self._event_handlers.values()
            ),
            "orchestrator_url": self.orchestrator_url,
            "max_retries": self._max_retries,
            "retry_delay": self._retry_delay,
            "session_timeout": self._session_timeout,
            "cleanup_interval": self._cleanup_interval,
        }

        # Add component-specific metrics
        if self.session_broker:
            metrics["session_broker_metrics"] = (
                await self.session_broker.get_telemetry()
            )

        if self.policy_engine:
            metrics["policy_engine_metrics"] = await self.policy_engine.get_telemetry()

        return metrics
