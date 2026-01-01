from typing import Dict, Any, Optional, Protocol
from abc import ABC, abstractmethod
import json
from vector_store import VectorStore, SearchResults
from models import Source


class Tool(ABC):
    """Abstract base class for all tools"""
    
    @abstractmethod
    def get_tool_definition(self) -> Dict[str, Any]:
        """Return Anthropic tool definition for this tool"""
        pass
    
    @abstractmethod
    def execute(self, **kwargs) -> str:
        """Execute the tool with given parameters"""
        pass


class CourseSearchTool(Tool):
    """Tool for searching course content with semantic course name matching"""
    
    def __init__(self, vector_store: VectorStore):
        self.store = vector_store
        self.last_sources = []  # Track sources from last search
    
    def get_tool_definition(self) -> Dict[str, Any]:
        """Return Anthropic tool definition for this tool"""
        return {
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
        }
    
    def execute(self, query: str, course_name: Optional[str] = None, lesson_number: Optional[int] = None) -> str:
        """
        Execute the search tool with given parameters.
        
        Args:
            query: What to search for
            course_name: Optional course filter
            lesson_number: Optional lesson filter
            
        Returns:
            Formatted search results or error message
        """
        
        # Use the vector store's unified search interface
        results = self.store.search(
            query=query,
            course_name=course_name,
            lesson_number=lesson_number
        )
        
        # Handle errors
        if results.error:
            return results.error
        
        # Handle empty results
        if results.is_empty():
            filter_info = ""
            if course_name:
                filter_info += f" in course '{course_name}'"
            if lesson_number:
                filter_info += f" in lesson {lesson_number}"
            return f"No relevant content found{filter_info}."
        
        # Format and return results
        return self._format_results(results)
    
    def _format_results(self, results: SearchResults) -> str:
        """Format search results with course and lesson context"""
        formatted = []
        sources = []  # Track sources for the UI (now as Source objects)

        for doc, meta in zip(results.documents, results.metadata):
            course_title = meta.get('course_title', 'unknown')
            lesson_num = meta.get('lesson_number')

            # Build context header
            header = f"[{course_title}"
            if lesson_num is not None:
                header += f" - Lesson {lesson_num}"
            header += "]"

            # Build source text for display
            source_text = course_title
            if lesson_num is not None:
                source_text += f" - Lesson {lesson_num}"

            # Fetch lesson link if lesson number exists
            lesson_link = None
            if lesson_num is not None:
                lesson_link = self.store.get_lesson_link(course_title, lesson_num)

            # Create Source object with text and link
            source_obj = Source(text=source_text, link=lesson_link)
            sources.append(source_obj)

            formatted.append(f"{header}\n{doc}")

        # Store sources for retrieval (now as Source objects)
        self.last_sources = sources

        return "\n\n".join(formatted)


class CourseOutlineTool(Tool):
    """Tool for retrieving complete course outline with lesson structure"""

    def __init__(self, vector_store: VectorStore):
        self.store = vector_store
        self.last_sources = []  # Track lesson links as Source objects

    def get_tool_definition(self) -> Dict[str, Any]:
        """Return Anthropic tool definition for this tool"""
        return {
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

    def execute(self, course_name: str) -> str:
        """
        Execute the outline tool with given course name.

        Args:
            course_name: Course title (supports partial/fuzzy matching)

        Returns:
            Formatted course outline or error message
        """

        # 1. Resolve course name using fuzzy matching
        resolved_title = self.store._resolve_course_name(course_name)

        # 2. Handle course not found
        if not resolved_title:
            existing_courses = self.store.get_existing_course_titles()
            if existing_courses:
                course_list = ", ".join(existing_courses)
                return f"No course found matching '{course_name}'. Available courses: {course_list}"
            return "No courses available in the system."

        # 3. Get course metadata
        result = self.store.course_catalog.get(ids=[resolved_title])
        if not result['metadatas'] or len(result['metadatas']) == 0:
            return f"Error: Unable to retrieve metadata for '{resolved_title}'"

        metadata = result['metadatas'][0]

        # 4. Extract course info
        course_title = metadata.get('title', 'Unknown')
        course_link = metadata.get('course_link')
        instructor = metadata.get('instructor', 'Unknown')
        lessons_json = metadata.get('lessons_json', '[]')

        # 5. Parse lessons
        try:
            lessons = json.loads(lessons_json)
        except json.JSONDecodeError:
            lessons = []

        # 6. Format output and create sources
        return self._format_outline(course_title, course_link, instructor, lessons)

    def _format_outline(self, course_title: str, course_link: str, instructor: str, lessons: list) -> str:
        """Format course outline and populate last_sources with lesson links"""
        formatted = []
        sources = []

        # Course header
        formatted.append(f"Course: {course_title}")
        if course_link:
            formatted.append(f"Link: {course_link}")
        formatted.append(f"Instructor: {instructor}")
        formatted.append("")  # Blank line
        formatted.append("Lessons:")

        # Format each lesson and create Source objects
        if lessons:
            for lesson in lessons:
                lesson_num = lesson.get('lesson_number')
                lesson_title = lesson.get('lesson_title', 'Untitled')
                lesson_link = lesson.get('lesson_link')

                # Format text without visible URL
                formatted.append(f"- Lesson {lesson_num}: {lesson_title}")

                # Create Source object for clickable link
                if lesson_link:
                    source_text = f"{course_title} - Lesson {lesson_num}"
                    source_obj = Source(text=source_text, link=lesson_link)
                    sources.append(source_obj)
        else:
            formatted.append("- No lessons available")

        # Store sources for UI
        self.last_sources = sources

        return "\n".join(formatted)


class ToolManager:
    """Manages available tools for the AI"""
    
    def __init__(self):
        self.tools = {}
    
    def register_tool(self, tool: Tool):
        """Register any tool that implements the Tool interface"""
        tool_def = tool.get_tool_definition()
        tool_name = tool_def.get("name")
        if not tool_name:
            raise ValueError("Tool must have a 'name' in its definition")
        self.tools[tool_name] = tool

    
    def get_tool_definitions(self) -> list:
        """Get all tool definitions for Anthropic tool calling"""
        return [tool.get_tool_definition() for tool in self.tools.values()]
    
    def execute_tool(self, tool_name: str, **kwargs) -> str:
        """Execute a tool by name with given parameters"""
        if tool_name not in self.tools:
            return f"Tool '{tool_name}' not found"
        
        return self.tools[tool_name].execute(**kwargs)
    
    def get_last_sources(self) -> list:
        """Get sources from the last search operation"""
        # Check all tools for last_sources attribute
        for tool in self.tools.values():
            if hasattr(tool, 'last_sources') and tool.last_sources:
                return tool.last_sources
        return []

    def reset_sources(self):
        """Reset sources from all tools that track sources"""
        for tool in self.tools.values():
            if hasattr(tool, 'last_sources'):
                tool.last_sources = []