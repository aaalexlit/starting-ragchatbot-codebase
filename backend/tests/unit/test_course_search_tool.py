"""Unit tests for CourseSearchTool.execute() method"""

import pytest
from unittest.mock import Mock
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from search_tools import CourseSearchTool
from models import Source
from tests.fixtures.mock_data import (
    mock_search_results_success,
    mock_search_results_empty,
    mock_search_results_error,
    mock_sources
)


@pytest.fixture
def search_tool(mock_vector_store):
    """Create CourseSearchTool with mocked VectorStore"""
    return CourseSearchTool(mock_vector_store)


class TestCourseSearchToolExecute:
    """Test suite for CourseSearchTool.execute() method"""

    def test_successful_search_query_only(self, search_tool, mock_vector_store):
        """
        Test 1: Successful search with query only
        - Mock VectorStore.search() to return SearchResults with 2 documents
        - Assert: Formatted output contains [Course - Lesson N] headers
        - Assert: last_sources populated with 2 Source objects
        - Assert: Source objects have correct text and links
        """
        # Arrange
        mock_results = mock_search_results_success()
        mock_vector_store.search.return_value = mock_results
        mock_vector_store.get_lesson_link.side_effect = [
            "https://example.com/lesson1",
            "https://example.com/lesson2"
        ]

        # Act
        result = search_tool.execute(query="test query")

        # Assert - search called correctly
        mock_vector_store.search.assert_called_once_with(
            query="test query",
            course_name=None,
            lesson_number=None
        )

        # Assert - output format
        assert "[Test Course - Lesson 1]" in result
        assert "[Test Course - Lesson 2]" in result
        assert "basic concepts" in result
        assert "advanced topics" in result

        # Assert - sources populated
        assert len(search_tool.last_sources) == 2
        assert all(isinstance(src, Source) for src in search_tool.last_sources)
        assert search_tool.last_sources[0].text == "Test Course - Lesson 1"
        assert search_tool.last_sources[0].link == "https://example.com/lesson1"
        assert search_tool.last_sources[1].text == "Test Course - Lesson 2"
        assert search_tool.last_sources[1].link == "https://example.com/lesson2"

    def test_successful_search_with_course_filter(self, search_tool, mock_vector_store):
        """
        Test 2: Successful search with course filter
        - Mock VectorStore.search() with course_name parameter
        - Assert: Filter passed correctly to vector store
        - Assert: Sources include lesson links
        """
        # Arrange
        mock_results = mock_search_results_success()
        mock_vector_store.search.return_value = mock_results
        mock_vector_store.get_lesson_link.return_value = "https://example.com/lesson"

        # Act
        result = search_tool.execute(
            query="decorators",
            course_name="Python Basics"
        )

        # Assert - search called with course filter
        mock_vector_store.search.assert_called_once_with(
            query="decorators",
            course_name="Python Basics",
            lesson_number=None
        )

        # Assert - results formatted
        assert "Test Course" in result
        assert len(search_tool.last_sources) == 2

    def test_successful_search_with_lesson_filter(self, search_tool, mock_vector_store):
        """
        Test 3: Successful search with lesson filter
        - Mock VectorStore.search() with lesson_number parameter
        - Assert: Lesson-specific results returned
        """
        # Arrange
        mock_results = mock_search_results_success()
        mock_vector_store.search.return_value = mock_results
        mock_vector_store.get_lesson_link.return_value = None

        # Act
        result = search_tool.execute(
            query="functions",
            lesson_number=3
        )

        # Assert - search called with lesson filter
        mock_vector_store.search.assert_called_once_with(
            query="functions",
            course_name=None,
            lesson_number=3
        )

        # Assert - results returned
        assert "Test Course" in result

    def test_empty_results_no_matches(self, search_tool, mock_vector_store):
        """
        Test 4: Empty results - no matches
        - Mock VectorStore.search() to return empty SearchResults
        - Assert: Returns "No relevant content found" message
        - Assert: Message includes filter info if filters applied
        - Assert: last_sources is empty list
        """
        # Arrange
        mock_vector_store.search.return_value = mock_search_results_empty()

        # Act - no filters
        result = search_tool.execute(query="nonexistent topic")

        # Assert
        assert "No relevant content found" in result
        assert len(search_tool.last_sources) == 0

        # Act - with course filter
        result_with_course = search_tool.execute(
            query="test",
            course_name="MCP"
        )

        # Assert - includes filter info
        assert "No relevant content found" in result_with_course
        assert "MCP" in result_with_course

    def test_error_from_vector_store(self, search_tool, mock_vector_store):
        """
        Test 5: Error from vector store
        - Mock VectorStore.search() to return SearchResults with error
        - Assert: Returns error message
        - Assert: No exception raised
        """
        # Arrange
        mock_vector_store.search.return_value = mock_search_results_error()

        # Act
        result = search_tool.execute(query="test")

        # Assert
        assert "No course found matching 'NonExistentCourse'" in result
        # Should not raise exception

    def test_missing_lesson_links(self, search_tool, mock_vector_store):
        """
        Test 6: Missing lesson links
        - Mock get_lesson_link() to return None
        - Assert: Sources created with link=None
        - Assert: No exceptions raised
        """
        # Arrange
        mock_results = mock_search_results_success()
        mock_vector_store.search.return_value = mock_results
        mock_vector_store.get_lesson_link.return_value = None

        # Act
        result = search_tool.execute(query="test")

        # Assert - no exceptions
        assert "Test Course" in result

        # Assert - sources created but with None links
        assert len(search_tool.last_sources) == 2
        assert search_tool.last_sources[0].link is None
        assert search_tool.last_sources[1].link is None

    def test_tool_definition_validation(self, search_tool):
        """
        Test 7: Tool definition validation
        - Call get_tool_definition()
        - Assert: Returns correct schema with name="search_course_content"
        - Assert: Required parameters: ["query"]
        - Assert: Optional parameters: course_name, lesson_number
        """
        # Act
        tool_def = search_tool.get_tool_definition()

        # Assert - basic structure
        assert tool_def["name"] == "search_course_content"
        assert "description" in tool_def
        assert "input_schema" in tool_def

        # Assert - schema structure
        schema = tool_def["input_schema"]
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "required" in schema

        # Assert - required parameters
        assert schema["required"] == ["query"]

        # Assert - all parameters present
        properties = schema["properties"]
        assert "query" in properties
        assert "course_name" in properties
        assert "lesson_number" in properties

        # Assert - parameter types
        assert properties["query"]["type"] == "string"
        assert properties["course_name"]["type"] == "string"
        assert properties["lesson_number"]["type"] == "integer"


class TestCourseSearchToolFormatResults:
    """Test suite for CourseSearchTool._format_results() helper method"""

    def test_format_results_creates_headers(self, search_tool, mock_vector_store):
        """Test that _format_results creates proper [Course - Lesson N] headers"""
        # Arrange
        mock_results = mock_search_results_success()
        mock_vector_store.search.return_value = mock_results
        mock_vector_store.get_lesson_link.return_value = None

        # Act
        result = search_tool.execute(query="test")

        # Assert - headers present
        assert "[Test Course - Lesson 1]" in result
        assert "[Test Course - Lesson 2]" in result

        # Assert - content after headers
        lines = result.split("\n\n")
        assert len(lines) == 2  # Two formatted results
