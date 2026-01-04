"""Integration tests for AIGenerator tool-calling behavior"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from ai_generator import AIGenerator
from tests.fixtures.mock_data import (
    mock_anthropic_direct_response,
    mock_anthropic_tool_use_response,
    mock_anthropic_final_response,
    mock_anthropic_multiple_tool_use,
    mock_tool_definitions
)


@pytest.fixture
def ai_generator():
    """Create AIGenerator instance with test API key"""
    return AIGenerator(api_key="test-key-12345", model="claude-sonnet-4-20250514")


class TestAIGeneratorDirectResponse:
    """Tests for direct responses without tool use"""

    def test_direct_response_without_tool_use(self, ai_generator, mock_tool_manager):
        """
        Test 1: Direct response without tool use
        - Mock Anthropic API to return stop_reason="end_turn"
        - Assert: Returns response.content[0].text directly
        - Assert: No tool execution attempted
        - Assert: Single API call made
        """
        # Arrange
        mock_response = mock_anthropic_direct_response("Python is a programming language.")

        with patch.object(ai_generator.client.messages, 'create', return_value=mock_response) as mock_create:
            # Act
            result = ai_generator.generate_response(
                query="What is Python?",
                tools=mock_tool_definitions(),
                tool_manager=mock_tool_manager
            )

            # Assert - direct text returned
            assert result == "Python is a programming language."

            # Assert - single API call
            assert mock_create.call_count == 1

            # Assert - tools passed in call
            call_args = mock_create.call_args[1]
            assert "tools" in call_args
            assert call_args["tool_choice"] == {"type": "auto"}

            # Assert - tool_manager not used
            mock_tool_manager.execute_tool.assert_not_called()


class TestAIGeneratorToolCalling:
    """Tests for tool-calling flow (two-API-call pattern)"""

    def test_tool_use_flow_search_course_content(self, ai_generator, mock_tool_manager):
        """
        Test 2: Tool use flow - search_course_content
        - Mock first API call: return stop_reason="tool_use"
        - Mock tool_manager.execute_tool() to return formatted results
        - Mock second API call: return final synthesized response
        - Assert: Two API calls made
        - Assert: First call includes tools parameter
        - Assert: Second call does NOT include tools parameter
        - Assert: Message chain preserved
        - Assert: tool_use_id correctly links results
        """
        # Arrange
        first_response = mock_anthropic_tool_use_response(
            tool_name="search_course_content",
            tool_input={"query": "decorators", "course_name": "Python"}
        )
        second_response = mock_anthropic_final_response(
            "Decorators are a powerful feature in Python..."
        )

        mock_tool_manager.execute_tool.return_value = "[Python - Lesson 5]\nDecorators explained..."

        with patch.object(ai_generator.client.messages, 'create') as mock_create:
            mock_create.side_effect = [first_response, second_response]

            # Act
            result = ai_generator.generate_response(
                query="Explain decorators in Python course",
                tools=mock_tool_definitions(),
                tool_manager=mock_tool_manager
            )

            # Assert - two API calls made
            assert mock_create.call_count == 2

            # Assert - first call has tools
            first_call_kwargs = mock_create.call_args_list[0][1]
            assert "tools" in first_call_kwargs
            assert first_call_kwargs["tool_choice"] == {"type": "auto"}
            assert len(first_call_kwargs["messages"]) == 1
            assert first_call_kwargs["messages"][0]["role"] == "user"

            # Assert - tool executed
            mock_tool_manager.execute_tool.assert_called_once_with(
                "search_course_content",
                query="decorators",
                course_name="Python"
            )

            # Assert - second call does NOT have tools
            second_call_kwargs = mock_create.call_args_list[1][1]
            assert "tools" not in second_call_kwargs

            # Assert - second call has complete message chain
            messages = second_call_kwargs["messages"]
            assert len(messages) == 3  # user → assistant (tool_use) → user (tool_results)
            assert messages[0]["role"] == "user"
            assert messages[1]["role"] == "assistant"
            assert messages[2]["role"] == "user"

            # Assert - tool_results structure
            tool_results = messages[2]["content"]
            assert isinstance(tool_results, list)
            assert tool_results[0]["type"] == "tool_result"
            assert tool_results[0]["tool_use_id"] == "toolu_abc123"
            assert "[Python - Lesson 5]" in tool_results[0]["content"]

            # Assert - final result
            assert result == "Decorators are a powerful feature in Python..."

    def test_tool_use_flow_get_course_outline(self, ai_generator, mock_tool_manager):
        """
        Test 3: Tool use flow - get_course_outline
        - Mock tool use for outline tool
        - Assert: Correct tool name and parameters extracted
        - Assert: Tool execution called with course_name
        """
        # Arrange
        first_response = mock_anthropic_tool_use_response(
            tool_name="get_course_outline",
            tool_input={"course_name": "MCP"},
            tool_id="toolu_outline_1"
        )
        second_response = mock_anthropic_final_response(
            "Here's the course outline..."
        )

        mock_tool_manager.execute_tool.return_value = "Course: MCP\nLessons:\n- Lesson 0: Intro"

        with patch.object(ai_generator.client.messages, 'create') as mock_create:
            mock_create.side_effect = [first_response, second_response]

            # Act
            result = ai_generator.generate_response(
                query="Show me the MCP course outline",
                tools=mock_tool_definitions(),
                tool_manager=mock_tool_manager
            )

            # Assert - tool executed with correct params
            mock_tool_manager.execute_tool.assert_called_once_with(
                "get_course_outline",
                course_name="MCP"
            )

            # Assert - result returned
            assert "course outline" in result.lower()

    def test_multiple_tool_uses_in_single_response(self, ai_generator, mock_tool_manager):
        """
        Test 4: Multiple tool uses in single response
        - Mock response with multiple tool_use blocks
        - Assert: All tools executed
        - Assert: All results included in second API call
        """
        # Arrange
        first_response = mock_anthropic_multiple_tool_use()
        second_response = mock_anthropic_final_response(
            "Based on the outline and search results..."
        )

        mock_tool_manager.execute_tool.side_effect = [
            "Course: Python Basics\nLessons: ...",
            "[Python Basics - Lesson 3]\nDecorators are..."
        ]

        with patch.object(ai_generator.client.messages, 'create') as mock_create:
            mock_create.side_effect = [first_response, second_response]

            # Act
            result = ai_generator.generate_response(
                query="Show me Python Basics outline and explain decorators",
                tools=mock_tool_definitions(),
                tool_manager=mock_tool_manager
            )

            # Assert - both tools executed
            assert mock_tool_manager.execute_tool.call_count == 2

            # Check first tool call
            first_tool_call = mock_tool_manager.execute_tool.call_args_list[0]
            assert first_tool_call[0][0] == "get_course_outline"
            assert first_tool_call[1] == {"course_name": "Python Basics"}

            # Check second tool call
            second_tool_call = mock_tool_manager.execute_tool.call_args_list[1]
            assert second_tool_call[0][0] == "search_course_content"
            assert second_tool_call[1] == {"query": "decorators", "course_name": "Python Basics"}

            # Assert - both results in second API call
            second_call_kwargs = mock_create.call_args_list[1][1]
            tool_results = second_call_kwargs["messages"][2]["content"]
            assert len(tool_results) == 2
            assert tool_results[0]["tool_use_id"] == "toolu_outline_1"
            assert tool_results[1]["tool_use_id"] == "toolu_search_2"


class TestAIGeneratorConversationHistory:
    """Tests for conversation history integration"""

    def test_conversation_history_integration(self, ai_generator, mock_tool_manager):
        """
        Test 5: Conversation history integration
        - Provide conversation_history string
        - Assert: System prompt includes history
        - Assert: Format: "Previous conversation:\\n{history}"
        """
        # Arrange
        mock_response = mock_anthropic_direct_response("Based on our previous discussion...")
        history = "User: What is Python?\nAssistant: Python is a programming language."

        with patch.object(ai_generator.client.messages, 'create', return_value=mock_response) as mock_create:
            # Act
            result = ai_generator.generate_response(
                query="Can you elaborate?",
                conversation_history=history,
                tools=mock_tool_definitions(),
                tool_manager=mock_tool_manager
            )

            # Assert - system prompt includes history
            call_kwargs = mock_create.call_args[1]
            system_content = call_kwargs["system"]
            assert "Previous conversation:" in system_content
            assert "What is Python?" in system_content
            assert "Python is a programming language" in system_content


class TestAIGeneratorToolDefinitions:
    """Tests for tool definition handling"""

    def test_tool_definition_passing(self, ai_generator, mock_tool_manager):
        """
        Test 6: Tool definition passing
        - Provide tools list from tool_manager
        - Assert: tools parameter passed to first API call
        - Assert: tool_choice = {"type": "auto"}
        """
        # Arrange
        mock_response = mock_anthropic_direct_response()
        tools = mock_tool_definitions()

        with patch.object(ai_generator.client.messages, 'create', return_value=mock_response) as mock_create:
            # Act
            ai_generator.generate_response(
                query="Test query",
                tools=tools,
                tool_manager=mock_tool_manager
            )

            # Assert - tools passed
            call_kwargs = mock_create.call_args[1]
            assert "tools" in call_kwargs
            assert call_kwargs["tools"] == tools

            # Assert - tool_choice set to auto
            assert call_kwargs["tool_choice"] == {"type": "auto"}


class TestAIGeneratorErrorHandling:
    """Tests for error handling"""

    def test_error_handling_tool_not_found(self, ai_generator, mock_tool_manager):
        """
        Test 7: Error handling - tool not found
        - Mock tool_manager.execute_tool() to return error message
        - Assert: Error passed to second API call
        - Assert: Final response handles error gracefully
        """
        # Arrange
        first_response = mock_anthropic_tool_use_response()
        second_response = mock_anthropic_final_response(
            "I couldn't find that information in the course materials."
        )

        mock_tool_manager.execute_tool.return_value = "Tool 'unknown_tool' not found"

        with patch.object(ai_generator.client.messages, 'create') as mock_create:
            mock_create.side_effect = [first_response, second_response]

            # Act
            result = ai_generator.generate_response(
                query="Test query",
                tools=mock_tool_definitions(),
                tool_manager=mock_tool_manager
            )

            # Assert - error passed to second API call
            second_call_kwargs = mock_create.call_args_list[1][1]
            tool_results = second_call_kwargs["messages"][2]["content"]
            assert "Tool" in tool_results[0]["content"] or "not found" in tool_results[0]["content"]

            # Assert - graceful response
            assert result is not None
