"""Shared pytest fixtures for all tests"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock

# Add backend to path so tests can import modules
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))


@pytest.fixture
def mock_config():
    """Mock config object with test values"""
    class MockConfig:
        ANTHROPIC_API_KEY = "test-key-12345"
        ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
        CHROMA_PATH = "./test_chroma_db"
        EMBEDDING_MODEL = "all-MiniLM-L6-v2"
        MAX_RESULTS = 5
        MAX_HISTORY = 2
        CHUNK_SIZE = 800
        CHUNK_OVERLAP = 100

    return MockConfig()


@pytest.fixture
def mock_vector_store():
    """Mock VectorStore with search and get_lesson_link methods"""
    mock_store = Mock()
    mock_store.search = Mock()
    mock_store.get_lesson_link = Mock()
    mock_store._resolve_course_name = Mock()
    mock_store.get_existing_course_titles = Mock(return_value=[])
    mock_store.course_catalog = Mock()
    return mock_store


@pytest.fixture
def mock_tool_manager():
    """Mock ToolManager with execute_tool and get_tool_definitions"""
    mock_manager = Mock()
    mock_manager.get_tool_definitions = Mock(return_value=[])
    mock_manager.execute_tool = Mock(return_value="Mock tool result")
    mock_manager.get_last_sources = Mock(return_value=[])
    mock_manager.reset_sources = Mock()
    return mock_manager


@pytest.fixture
def mock_session_manager():
    """Mock SessionManager"""
    mock_manager = Mock()
    mock_manager.get_conversation_history = Mock(return_value=None)
    mock_manager.add_exchange = Mock()
    return mock_manager


@pytest.fixture(autouse=True)
def reset_mocks():
    """Auto-reset all mocks between tests"""
    yield
    # Additional cleanup can go here if needed
