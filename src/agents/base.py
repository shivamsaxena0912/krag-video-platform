"""Base agent class and utilities."""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from src.common.logging import get_logger

TInput = TypeVar("TInput", bound=BaseModel)
TOutput = TypeVar("TOutput", bound=BaseModel)


@dataclass
class AgentMetrics:
    """Metrics collected during agent execution."""

    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_duration_seconds: float = 0.0
    total_cost: float = 0.0

    def record_success(self, duration: float, cost: float = 0.0) -> None:
        """Record a successful execution."""
        self.total_calls += 1
        self.successful_calls += 1
        self.total_duration_seconds += duration
        self.total_cost += cost

    def record_failure(self, duration: float) -> None:
        """Record a failed execution."""
        self.total_calls += 1
        self.failed_calls += 1
        self.total_duration_seconds += duration

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_calls == 0:
            return 0.0
        return self.successful_calls / self.total_calls

    @property
    def average_duration(self) -> float:
        """Calculate average duration."""
        if self.successful_calls == 0:
            return 0.0
        return self.total_duration_seconds / self.successful_calls


@dataclass
class AgentConfig:
    """Configuration for an agent."""

    name: str
    max_retries: int = 3
    timeout_seconds: int = 60
    retry_delay_seconds: float = 1.0
    cost_tracking: bool = True
    extra: dict[str, Any] = field(default_factory=dict)


class AgentError(Exception):
    """Base exception for agent errors."""

    def __init__(self, message: str, recoverable: bool = True):
        super().__init__(message)
        self.recoverable = recoverable


class AgentTimeoutError(AgentError):
    """Raised when agent execution times out."""

    def __init__(self, message: str = "Agent execution timed out"):
        super().__init__(message, recoverable=True)


class AgentValidationError(AgentError):
    """Raised when input/output validation fails."""

    def __init__(self, message: str):
        super().__init__(message, recoverable=False)


class BaseAgent(ABC, Generic[TInput, TOutput]):
    """
    Base class for all agents in the pipeline.

    Agents are stateless components that transform inputs to outputs.
    They handle logging, metrics, retries, and error handling.
    """

    def __init__(self, config: AgentConfig | None = None):
        """Initialize the agent."""
        self.config = config or AgentConfig(name=self.__class__.__name__)
        self.logger = get_logger(self.config.name)
        self.metrics = AgentMetrics()

    @property
    def name(self) -> str:
        """Get the agent name."""
        return self.config.name

    @abstractmethod
    async def execute(self, input: TInput) -> TOutput:
        """
        Execute the agent's primary function.

        This method must be implemented by subclasses.

        Args:
            input: The typed input for this agent

        Returns:
            The typed output from this agent

        Raises:
            AgentError: If execution fails
        """
        pass

    async def __call__(self, input: TInput) -> TOutput:
        """
        Execute the agent with logging, metrics, and error handling.

        Args:
            input: The typed input for this agent

        Returns:
            The typed output from this agent
        """
        start_time = time.time()
        input_summary = input.model_dump() if hasattr(input, "model_dump") else str(input)

        self.logger.info(
            "agent_execution_start",
            agent=self.name,
            input_type=type(input).__name__,
        )

        try:
            output = await self.execute(input)
            duration = time.time() - start_time

            self.metrics.record_success(duration)
            self.logger.info(
                "agent_execution_success",
                agent=self.name,
                duration_seconds=round(duration, 3),
                output_type=type(output).__name__,
            )

            return output

        except Exception as e:
            duration = time.time() - start_time
            self.metrics.record_failure(duration)

            self.logger.error(
                "agent_execution_failed",
                agent=self.name,
                duration_seconds=round(duration, 3),
                error_type=type(e).__name__,
                error_message=str(e),
            )
            raise

    def get_metrics(self) -> dict[str, Any]:
        """Get current metrics as a dictionary."""
        return {
            "name": self.name,
            "total_calls": self.metrics.total_calls,
            "successful_calls": self.metrics.successful_calls,
            "failed_calls": self.metrics.failed_calls,
            "success_rate": self.metrics.success_rate,
            "average_duration_seconds": self.metrics.average_duration,
            "total_cost": self.metrics.total_cost,
        }


class AgentRegistry:
    """Registry for agent instances."""

    _agents: dict[str, BaseAgent] = {}

    @classmethod
    def register(cls, name: str, agent: BaseAgent) -> None:
        """Register an agent by name."""
        cls._agents[name] = agent

    @classmethod
    def get(cls, name: str) -> BaseAgent:
        """Get an agent by name."""
        if name not in cls._agents:
            raise KeyError(f"Agent '{name}' not registered")
        return cls._agents[name]

    @classmethod
    def list(cls) -> list[str]:
        """List all registered agent names."""
        return list(cls._agents.keys())

    @classmethod
    def clear(cls) -> None:
        """Clear all registered agents."""
        cls._agents.clear()
