"""Pytest configuration and fixtures."""

import pytest
import asyncio
from pathlib import Path


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_story_path():
    """Path to sample story file."""
    return Path(__file__).parent.parent / "examples" / "story_001.txt"


@pytest.fixture
def sample_story_text(sample_story_path):
    """Sample story text content."""
    return sample_story_path.read_text()
