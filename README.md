# Reflective Coaching Agent

A FastAPI + LangGraph backend service that conducts multi-turn reflective coaching conversations, manages session state, and generates post-session reflections.

## Features

- **Multi-turn Coaching Conversations**: Guides learners through 4 phases (Framing → Exploration → Challenge → Synthesis)
- **Session Memory**: Full conversation history persisted in SQLite
- **Phase-Aware Responses**: Different coaching techniques for each phase
- **Turn Budget Management**: Configurable session length with intelligent phase pacing
- **Post-Session Reflections**: Free-form narrative observations with outcome classification

## Tech Stack

- **Framework**: FastAPI (async Python)
- **Agent**: LangGraph (stateful conversation management)
- **LLM**: Anthropic Claude
- **Database**: SQLite + SQLAlchemy (async)
- **Validation**: Pydantic v2

## Quick Start

### 1. Install Dependencies

**Option A: Using Conda (Recommended)**

```bash
cd reflective-coach
conda env create -f environment.yml
conda activate reflective-coach
```

**Option B: Using pip**

```bash
cd reflective-coach
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env and add your Anthropic API key
```

### 3. Run the Server

```bash
uvicorn app.main:app --reload
```

### 4. Open API Docs

Navigate to http://localhost:8000/docs

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/sessions` | Start a new coaching session |
| `POST` | `/sessions/{id}/messages` | Send message, get coach response |
| `POST` | `/sessions/{id}/end` | End session, generate reflection |
| `GET` | `/sessions/{id}` | Get session details + history |
| `GET` | `/sessions/{id}/reflection` | Get generated reflection |

## Usage Example

### Create a Session

```bash
curl -X POST http://localhost:8000/sessions \
  -H "Content-Type: application/json" \
  -d '{"topic": "I want to speak up more in meetings", "max_turns": 12}'
```

Response:
```json
{
  "session_id": "abc-123",
  "phase": "framing",
  "max_turns": 12,
  "turn_count": 0,
  "turns_remaining": 12,
  "content": "What's on your mind today? Tell me more about wanting to speak up in meetings."
}
```

### Send a Message

```bash
curl -X POST http://localhost:8000/sessions/abc-123/messages \
  -H "Content-Type: application/json" \
  -d '{"content": "I keep staying quiet even when I have something valuable to say"}'
```

### End Session

```bash
curl -X POST http://localhost:8000/sessions/abc-123/end
```

## Coaching Phases

| Phase | Purpose | % of Session |
|-------|---------|--------------|
| **Framing** | Establish context, understand the topic | 1-2 turns |
| **Exploration** | Surface resistance, identify beliefs | 30-40% |
| **Challenge** | Reality-test assumptions, secure commitment | 30-40% |
| **Synthesis** | Anchor insight, confirm commitment | 1-3 turns |

## Reflection Output

After ending a session, the system generates a structured reflection:

```json
{
  "key_observations": "Free-form narrative describing fears, beliefs, patterns, and strengths observed...",
  "outcome_classification": "breakthrough_achieved",
  "insights_summary": "Summary of the core shift that occurred...",
  "commitment": "Specific action the learner committed to...",
  "suggested_followup": "Recommendation for future coaching..."
}
```

### Outcome Classifications

- **breakthrough_achieved**: Genuine insight + specific commitment made
- **partial_progress**: Increased awareness but action unclear
- **root_cause_identified**: Deeper issue uncovered, needs follow-up

## Project Structure

```
reflective-coach/
├── app/
│   ├── main.py              # FastAPI entry point
│   ├── config.py            # Settings
│   ├── api/
│   │   ├── schemas.py       # Pydantic models
│   │   ├── routes/          # API endpoints
│   │   └── errors.py        # Exception handlers
│   ├── core/
│   │   ├── agent.py         # LangGraph state machine
│   │   ├── prompts.py       # Coaching prompts
│   │   ├── transitions.py   # Phase logic
│   │   └── llm.py           # LLM integration
│   ├── db/
│   │   ├── database.py      # SQLAlchemy setup
│   │   ├── models.py        # ORM models
│   │   └── repositories.py  # Data access
│   └── services/
│       ├── coaching.py      # Main orchestration
│       └── reflection.py    # Reflection generation
├── tests/
├── environment.yml          # Conda environment
├── requirements.txt         # Pip requirements
└── .env.example
```

## Running Tests

```bash
pytest tests/ -v
```

## Design Decisions

1. **max_turns parameter**: LLM needs to know the session budget to pace phases correctly (30-40% allocations)
2. **Unified `content` key**: Same response structure for all endpoints
3. **Free-form observations**: Richer narrative vs. forced JSON categories
4. **SQLite**: Simple persistence that scales to Postgres with same ORM code

## License

MIT
