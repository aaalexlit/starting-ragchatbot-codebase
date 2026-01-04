"""Integration tests for RAG system query handling"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from rag_system import RAGSystem
from models import Source
from tests.fixtures.mock_data import mock_sources


@pytest.fixture
def rag_system(mock_config):
    """Create RAGSystem with mocked dependencies"""
    with patch('rag_system.VectorStore'), \
         patch('rag_system.AIGenerator'), \
         patch('rag_system.SessionManager'), \
         patch('rag_system.ToolManager'), \
         patch('rag_system.DocumentProcessor'):

        rag = RAGSystem(mock_config)

        # Configure mocks
        rag.ai_generator.generate_response = Mock(return_value="Test response")
        rag.tool_manager.get_tool_definitions = Mock(return_value=[])
        rag.tool_manager.get_last_sources = Mock(return_value=[])
        rag.tool_manager.reset_sources = Mock()
        rag.session_manager.get_conversation_history = Mock(return_value=None)
        rag.session_manager.add_exchange = Mock()

        return rag


class TestRAGSystemBasicQueries:
    """Tests for basic query handling"""

    def test_query_without_session_creates_new_session(self, rag_system):
        """
        Test 1: Query without session - creates new session
        - Call rag_system.query(query, session_id=None)
        - Assert: Response returned
        - Assert: Sources list returned
        - Assert: No session history used
        """
        # Act
        response, sources = rag_system.query(
            query="What is Python?",
            session_id=None
        )

        # Assert - response returned
        assert response == "Test response"
        assert isinstance(sources, list)

        # Assert - no history used (None passed to ai_generator)
        rag_system.session_manager.get_conversation_history.assert_not_called()

        # Assert - ai_generator called with correct params
        rag_system.ai_generator.generate_response.assert_called_once()
        call_kwargs = rag_system.ai_generator.generate_response.call_args[1]
        assert call_kwargs["conversation_history"] is None

    def test_query_with_existing_session_uses_history(self, rag_system):
        """
        Test 2: Query with existing session - uses history
        - Mock session_manager to return history string
        - Call rag_system.query(query, session_id="test_session")
        - Assert: History passed to ai_generator
        - Assert: Session updated with new exchange
        """
        # Arrange
        mock_history = "User: Hello\nAssistant: Hi there!"
        rag_system.session_manager.get_conversation_history.return_value = mock_history

        # Act
        response, sources = rag_system.query(
            query="Follow-up question",
            session_id="test_session_123"
        )

        # Assert - history retrieved
        rag_system.session_manager.get_conversation_history.assert_called_once_with("test_session_123")

        # Assert - history passed to ai_generator
        call_kwargs = rag_system.ai_generator.generate_response.call_args[1]
        assert call_kwargs["conversation_history"] == mock_history

        # Assert - session updated
        rag_system.session_manager.add_exchange.assert_called_once()
        exchange_call = rag_system.session_manager.add_exchange.call_args[0]
        assert exchange_call[0] == "test_session_123"
        assert "Follow-up question" in exchange_call[1]
        assert exchange_call[2] == "Test response"


class TestRAGSystemToolUsage:
    """Tests for tool usage in queries"""

    def test_content_query_triggers_tool_use(self, rag_system):
        """
        Test 3: Content query triggers tool use
        - Query: "Explain X concept in course Y"
        - Mock ai_generator to simulate tool use
        - Mock tool_manager to return search results
        - Assert: Sources retrieved from tool_manager
        - Assert: Sources reset after retrieval
        """
        # Arrange
        mock_sources_list = mock_sources()
        rag_system.tool_manager.get_last_sources.return_value = mock_sources_list

        # Act
        response, sources = rag_system.query(
            query="Explain decorators in Python course"
        )

        # Assert - sources retrieved
        rag_system.tool_manager.get_last_sources.assert_called_once()
        assert sources == mock_sources_list
        assert len(sources) == 2

        # Assert - sources reset
        rag_system.tool_manager.reset_sources.assert_called_once()

    def test_general_query_no_tool_use(self, rag_system):
        """
        Test 4: General query - no tool use
        - Query: "What is Python?"
        - Mock ai_generator to return direct response
        - Assert: No tools called (implicitly tested by empty sources)
        - Assert: Sources list empty
        """
        # Arrange
        rag_system.tool_manager.get_last_sources.return_value = []

        # Act
        response, sources = rag_system.query(
            query="What is Python in general?"
        )

        # Assert - response returned
        assert response == "Test response"

        # Assert - sources empty (no tool use)
        assert sources == []


class TestRAGSystemSourceTracking:
    """Tests for source tracking and management"""

    def test_tool_execution_populates_sources(self, rag_system):
        """
        Test 5: Tool execution populates sources
        - Mock CourseSearchTool to populate last_sources
        - Assert: tool_manager.get_last_sources() returns Source objects
        - Assert: Sources included in response
        """
        # Arrange
        expected_sources = [
            Source(text="Course A - Lesson 1", link="https://example.com/lesson1"),
            Source(text="Course A - Lesson 2", link="https://example.com/lesson2"),
            Source(text="Course B - Lesson 3", link="https://example.com/lesson3")
        ]
        rag_system.tool_manager.get_last_sources.return_value = expected_sources

        # Act
        response, sources = rag_system.query(query="Search query")

        # Assert - sources returned
        assert len(sources) == 3
        assert all(isinstance(src, Source) for src in sources)
        assert sources[0].text == "Course A - Lesson 1"
        assert sources[0].link == "https://example.com/lesson1"

    def test_source_reset_after_query(self, rag_system):
        """
        Test 6: Source reset after query
        - Execute query that uses tools
        - Assert: tool_manager.reset_sources() called
        - Assert: Next query starts with empty sources
        """
        # Arrange
        rag_system.tool_manager.get_last_sources.return_value = mock_sources()

        # Act - first query
        response1, sources1 = rag_system.query(query="First query")

        # Assert - sources returned and reset called
        assert len(sources1) > 0
        assert rag_system.tool_manager.reset_sources.call_count == 1

        # Arrange - second query with no sources
        rag_system.tool_manager.get_last_sources.return_value = []

        # Act - second query
        response2, sources2 = rag_system.query(query="Second query")

        # Assert - new query has empty sources
        assert sources2 == []
        assert rag_system.tool_manager.reset_sources.call_count == 2


class TestRAGSystemConversationHistory:
    """Tests for conversation history management"""

    def test_conversation_history_formatting(self, rag_system):
        """
        Test 7: Conversation history formatting
        - Add multiple exchanges to session
        - Assert: History formatted as string
        - Assert: MAX_HISTORY limit respected (default: 2)
        """
        # Arrange - set up history mock
        history_string = (
            "User: What is Python?\n"
            "Assistant: Python is a programming language.\n"
            "User: Is it easy to learn?\n"
            "Assistant: Yes, Python is known for being beginner-friendly."
        )
        rag_system.session_manager.get_conversation_history.return_value = history_string

        # Act
        response, sources = rag_system.query(
            query="Tell me more",
            session_id="session_with_history"
        )

        # Assert - history retrieved
        rag_system.session_manager.get_conversation_history.assert_called_once_with("session_with_history")

        # Assert - history passed to generator
        call_kwargs = rag_system.ai_generator.generate_response.call_args[1]
        assert call_kwargs["conversation_history"] == history_string

        # Assert - response includes context from history
        assert response is not None


class TestRAGSystemIntegration:
    """End-to-end integration tests"""

    def test_full_query_flow_with_tools(self, rag_system):
        """Test complete query flow: query → ai_generator → tool execution → sources → response"""
        # Arrange
        rag_system.ai_generator.generate_response.return_value = "Here's what I found in the course..."
        rag_system.tool_manager.get_last_sources.return_value = mock_sources()

        # Act
        response, sources = rag_system.query(
            query="What are decorators in Python course?",
            session_id="integration_test_session"
        )

        # Assert - complete flow
        # 1. AI generator called
        assert rag_system.ai_generator.generate_response.called

        # 2. Tool definitions passed
        call_kwargs = rag_system.ai_generator.generate_response.call_args[1]
        assert "tools" in call_kwargs
        assert "tool_manager" in call_kwargs

        # 3. Sources retrieved and reset
        assert rag_system.tool_manager.get_last_sources.called
        assert rag_system.tool_manager.reset_sources.called

        # 4. Session updated
        assert rag_system.session_manager.add_exchange.called

        # 5. Response and sources returned
        assert response == "Here's what I found in the course..."
        assert len(sources) == 2

    def test_query_prompt_formatting(self, rag_system):
        """Test that query is properly formatted as prompt"""
        # Act
        response, sources = rag_system.query(
            query="Test user query"
        )

        # Assert - prompt formatted correctly
        call_args = rag_system.ai_generator.generate_response.call_args
        query_arg = call_args[1]["query"]
        assert "Answer this question about course materials" in query_arg
        assert "Test user query" in query_arg
