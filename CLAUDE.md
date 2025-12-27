# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Retrieval-Augmented Generation (RAG) chatbot system** for answering questions about course materials. It combines semantic search (ChromaDB), AI generation (Anthropic Claude), and a web interface to provide intelligent, context-aware responses about educational content.

**Key Technical Pattern**: Claude uses **tool-calling** to autonomously decide when to search course content, making this an agentic RAG system rather than a simple retrieval-then-generate pipeline.

## Development Commands

### Running the Application

**Quick start:**
```bash
./run.sh
```

**Manual start:**
```bash
cd backend
uv run uvicorn app:app --reload --port 8000
```

Access at:
- Web UI: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Package Management

**Install all dependencies:**
```bash
uv sync
```

**Add a new dependency:**
```bash
uv add package-name
```

### Environment Setup

Create `.env` in project root:
```bash
ANTHROPIC_API_KEY=your-api-key-here
```

### ChromaDB Management

**Clear and rebuild vector database:**
```bash
rm -rf backend/chroma_db
# Then restart the app - it will rebuild on startup
```

## Architecture Overview

### Request Flow (User Query → Response)

1. **Frontend** (script.js) → POST `/api/query` with query and session_id
2. **FastAPI** (app.py) → Routes to RAG system
3. **RAG System** (rag_system.py) → Orchestrates the flow:
   - Retrieves conversation history from SessionManager
   - Calls AIGenerator with tools and history
4. **AI Generator** (ai_generator.py) → **First Claude API call** with tool definitions
5. **Claude decides to search** → Returns `tool_use` response
6. **Tool Manager** (search_tools.py) → Executes `search_course_content` tool
7. **Vector Store** (vector_store.py) → Semantic search in ChromaDB
8. **AI Generator** → **Second Claude API call** with tool results
9. **Claude synthesizes answer** → Returns final response
10. **RAG System** → Extracts sources, updates session history
11. **FastAPI** → Returns JSON response with answer + sources
12. **Frontend** → Displays formatted response with collapsible sources

**Critical: Two Claude API calls per query** - first to decide on tool use, second to generate final answer from retrieved context.

### Core Components

**Backend Architecture** (`backend/`):
- `app.py` - FastAPI server with two endpoints: `/api/query` and `/api/courses`
- `rag_system.py` - Main orchestrator that coordinates all components
- `ai_generator.py` - Claude API client with tool execution handling
- `vector_store.py` - ChromaDB wrapper with two collections: `course_catalog` (metadata) and `course_content` (chunks)
- `document_processor.py` - Parses course documents and creates sentence-based chunks
- `search_tools.py` - Tool definitions and manager for Claude's tool-calling capability
- `session_manager.py` - In-memory conversation history (max 2 exchanges by default)
- `models.py` - Pydantic models: Course, Lesson, CourseChunk
- `config.py` - Centralized configuration with defaults

**Frontend** (`frontend/`):
- Single-page application: `index.html`, `script.js`, `style.css`
- Uses Marked.js for markdown rendering
- Vanilla JavaScript (no framework)

### Vector Store Design

**Two ChromaDB collections strategy:**

1. **`course_catalog`** - Course metadata for name resolution
   - Document: Course title
   - Metadata: title, instructor, course_link, lessons_json, lesson_count
   - ID: Course title (unique identifier)
   - Purpose: Fast semantic search to resolve partial course names

2. **`course_content`** - Searchable course chunks
   - Document: Chunk text with context prepended
   - Metadata: course_title, lesson_number, chunk_index
   - ID: `{course_title}_{chunk_index}`
   - Purpose: Main semantic search for content retrieval

**Why two collections?** Separates metadata lookup from content search, enabling filtered searches without querying all content.

### Document Processing Pipeline

**Expected course document format** (`docs/*.txt`):
```
Course Title: [title]
Course Link: [url]
Course Instructor: [name]

Lesson 0: Introduction
Lesson Link: [url]
[content...]

Lesson 1: Getting Started
[content...]
```

**Processing steps:**
1. Parse metadata from first 3 lines
2. Split into lessons using regex: `Lesson \d+: Title`
3. Chunk each lesson using sentence-based splitting (respects abbreviations)
4. Add context to chunks: `"Course [title] Lesson [N] content: [chunk]"`
5. Store in both collections with metadata

**Chunking strategy:**
- Sentence-based (not fixed character boundaries)
- Default: 800 chars per chunk, 100 char overlap
- Maintains context continuity between chunks
- Configurable via `config.py`

### Tool-Based Search System

Claude is given a `search_course_content` tool with parameters:
- `query` (required) - What to search for
- `course_name` (optional) - Filter by course (partial matches work)
- `lesson_number` (optional) - Filter by specific lesson

**Tool execution flow:**
1. Vector search in `course_catalog` if course_name provided (resolves partial names)
2. Build ChromaDB filter combining course_title and/or lesson_number
3. Semantic search in `course_content` with filters
4. Format results with `[Course - Lesson N]` headers
5. Track sources separately for UI display

### Session Management

**In-memory storage** (resets on server restart):
- Session IDs: `session_1`, `session_2`, etc.
- History limit: Keeps last N exchanges (default: 2, configurable via `MAX_HISTORY`)
- Format: Injected into Claude's system prompt as context

## Configuration

All settings in `backend/config.py`:

**Model settings:**
- `ANTHROPIC_MODEL`: `claude-sonnet-4-20250514`
- `EMBEDDING_MODEL`: `all-MiniLM-L6-v2` (384-dimensional vectors)

**Processing settings:**
- `CHUNK_SIZE`: 800 chars
- `CHUNK_OVERLAP`: 100 chars
- `MAX_RESULTS`: 5 (top-k search results)
- `MAX_HISTORY`: 2 (conversation pairs to remember)

**Paths:**
- `CHROMA_PATH`: `./chroma_db` (relative to backend/)

## Adding New Course Documents

1. Place `.txt` files in `docs/` directory
2. Follow the expected format (see Document Processing Pipeline above)
3. Restart the server - documents are auto-processed on startup
4. System only adds new courses (incremental), skips existing ones

**To force rebuild:** Delete `backend/chroma_db/` and restart.

## Modifying the System

### Adding New Tools for Claude

1. Create tool class inheriting from `Tool` in `search_tools.py`
2. Implement `get_tool_definition()` - return Anthropic tool schema
3. Implement `execute(**kwargs)` - tool logic
4. Register in `rag_system.py`: `self.tool_manager.register_tool(your_tool)`

### Changing Search Behavior

**Vector store search logic:** `vector_store.py:61-100`
- Modify `search()` method to change filtering or ranking
- Change `MAX_RESULTS` in config for more/fewer results

**Search tool formatting:** `search_tools.py:88-114`
- Modify `_format_results()` to change how results are presented to Claude

### Adjusting Claude's Behavior

**System prompt:** `ai_generator.py:8-30`
- Modify `SYSTEM_PROMPT` to change how Claude responds
- Current instructions: search only for course-specific questions, brief responses

**API parameters:** `ai_generator.py:37-41`
- Temperature: 0 (deterministic)
- Max tokens: 800
- Modify for longer/more creative responses

## Important Implementation Details

**Startup behavior** (`app.py:88-98`):
- Automatically loads all documents from `../docs/` on server start
- Uses incremental loading (checks existing courses)
- Errors are logged but don't prevent startup

**Session creation:**
- First query without session_id creates new session
- Session ID returned in response, frontend stores it
- Subsequent queries use same session_id for context

**Source tracking:**
- Tools store sources in `last_sources` attribute
- RAG system extracts after AI generation
- Prevents sources from being mentioned in Claude's response text

**ChromaDB persistence:**
- Data persists in `backend/chroma_db/` directory
- First run processes all documents (~30s for 4 courses)
- Subsequent runs skip existing courses (fast startup)

## Known Limitations

- Sessions are in-memory only (lost on restart)
- No authentication or user management
- Single-instance only (no distributed setup)
- Course titles must be unique (used as IDs)
- Max conversation history is limited (prevent prompt bloat)
