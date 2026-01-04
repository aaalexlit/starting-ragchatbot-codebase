"""Mock data for testing: SearchResults, Anthropic responses, tool definitions"""

from unittest.mock import Mock
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from vector_store import SearchResults
from models import Source


# ==== Mock SearchResults ====

def mock_search_results_success():
    """SearchResults with 2 documents from different lessons"""
    return SearchResults(
        documents=[
            "This is content from lesson 1 about basic concepts.",
            "This is content from lesson 2 about advanced topics."
        ],
        metadata=[
            {'course_title': 'Test Course', 'lesson_number': 1, 'chunk_index': 0},
            {'course_title': 'Test Course', 'lesson_number': 2, 'chunk_index': 1}
        ],
        distances=[0.1, 0.15],
        error=None
    )


def mock_search_results_single():
    """SearchResults with single document"""
    return SearchResults(
        documents=["Single result from lesson 5"],
        metadata=[{'course_title': 'Python Course', 'lesson_number': 5, 'chunk_index': 0}],
        distances=[0.08],
        error=None
    )


def mock_search_results_empty():
    """Empty SearchResults (no matches found)"""
    return SearchResults(
        documents=[],
        metadata=[],
        distances=[],
        error=None
    )


def mock_search_results_error():
    """SearchResults with error message"""
    return SearchResults(
        documents=[],
        metadata=[],
        distances=[],
        error="No course found matching 'NonExistentCourse'"
    )


# ==== Mock Anthropic API Responses ====

def mock_anthropic_direct_response(text="This is a direct answer without using tools."):
    """Mock Anthropic response without tool use (direct answer)"""
    response = Mock()
    response.stop_reason = "end_turn"

    text_block = Mock()
    text_block.text = text
    text_block.type = "text"

    response.content = [text_block]
    return response


def mock_anthropic_tool_use_response(
    tool_name="search_course_content",
    tool_input=None,
    tool_id="toolu_abc123"
):
    """Mock Anthropic response with tool_use (first API call)"""
    if tool_input is None:
        tool_input = {"query": "test query", "course_name": "Test Course"}

    response = Mock()
    response.stop_reason = "tool_use"

    # Text block before tool use (Claude's thinking)
    text_block = Mock()
    text_block.type = "text"
    text_block.text = "I'll search the course content for that information."

    # Tool use block
    tool_use_block = Mock()
    tool_use_block.type = "tool_use"
    tool_use_block.name = tool_name
    tool_use_block.id = tool_id
    tool_use_block.input = tool_input

    response.content = [text_block, tool_use_block]
    return response


def mock_anthropic_final_response(text="Here's the answer based on the search results."):
    """Mock Anthropic response after tool execution (second API call)"""
    response = Mock()
    response.stop_reason = "end_turn"

    text_block = Mock()
    text_block.text = text
    text_block.type = "text"

    response.content = [text_block]
    return response


def mock_anthropic_multiple_tool_use():
    """Mock Anthropic response with multiple tool uses"""
    response = Mock()
    response.stop_reason = "tool_use"

    # First tool use
    tool_use_1 = Mock()
    tool_use_1.type = "tool_use"
    tool_use_1.name = "get_course_outline"
    tool_use_1.id = "toolu_outline_1"
    tool_use_1.input = {"course_name": "Python Basics"}

    # Second tool use
    tool_use_2 = Mock()
    tool_use_2.type = "tool_use"
    tool_use_2.name = "search_course_content"
    tool_use_2.id = "toolu_search_2"
    tool_use_2.input = {"query": "decorators", "course_name": "Python Basics"}

    response.content = [tool_use_1, tool_use_2]
    return response


# ==== Mock Tool Definitions ====

def mock_tool_definitions():
    """Mock tool definitions matching CourseSearchTool and CourseOutlineTool"""
    return [
        {
            "name": "search_course_content",
            "description": "Search course materials with smart course name matching and lesson filtering",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "What to search for in the course content"
                    },
                    "course_name": {
                        "type": "string",
                        "description": "Course title (partial matches work, e.g. 'MCP', 'Introduction')"
                    },
                    "lesson_number": {
                        "type": "integer",
                        "description": "Specific lesson number to search within (e.g. 1, 2, 3)"
                    }
                },
                "required": ["query"]
            }
        },
        {
            "name": "get_course_outline",
            "description": "Get complete course outline including course title, link, instructor, and all lessons with numbers and titles. Use when users ask about course structure or lesson list.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "course_name": {
                        "type": "string",
                        "description": "Course title (partial matches work, e.g. 'MCP', 'Introduction')"
                    }
                },
                "required": ["course_name"]
            }
        }
    ]


# ==== Mock Source Objects ====

def mock_sources():
    """Mock list of Source objects"""
    return [
        Source(text="Test Course - Lesson 1", link="https://example.com/lesson1"),
        Source(text="Test Course - Lesson 2", link="https://example.com/lesson2")
    ]


def mock_sources_no_links():
    """Mock Source objects without links"""
    return [
        Source(text="Test Course - Lesson 1", link=None),
        Source(text="Test Course - Lesson 2", link=None)
    ]
