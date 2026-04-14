# Kaia — AI Personal Assistant

A personal AI companion built with Python, LangChain, LangGraph, and Gemini API.
Kaia is not just a chatbot — she has a persistent personality, remembers you across sessions,
and can take real actions through a extensible tool system.

---

## Features

- **Persona** — warm, friendly character defined via system prompt
- **Short-term memory** — remembers context within a session via chat history
- **Long-term memory** — persists important facts across sessions using extraction-based memory (`[REMEMBER]` pattern)
- **Function calling** — executes real actions via LangGraph's ReAct agent loop
- **Tool registry** — extensible tool system, add new tools without touching core logic
- **LangSmith monitoring** — full tracing and observability of every run

---

## Project Structure

```
kaia/
├── src/
│   ├── agent/
│   │   ├── persona.py          # System prompt and [REMEMBER] instructions
│   │   ├── memory.py           # Long-term memory read/write
│   │   └── graph.py            # LangGraph agent (nodes, edges, state)
│   ├── tools/
│   │   ├── __init__.py         # Central tool registry (ALL_TOOLS)
│   │   ├── datetime_tool.py    # get_current_datetime tool
│   │   └── notes_tool.py       # save_note / get_notes / delete_note tools
│   └── __init__.py
├── data/
│   ├── memory.json             # Persisted long-term memory
│   └── notes.json              # Persisted notes
├── main.py                     # Entry point — chat loop
├── .env.example                # Environment variable template
└── requirements.txt
```

---

## Architecture

```
User input
    ↓
main.py (chat loop + memory extraction)
    ↓
LangGraph Agent ─────────────────────────────────
│                                                │
│   [llm_node] ──→ should_use_tools?             │
│        ↑               │           │           │
│        │          [tool_node]    [END]          │
│        └── loop back (ReAct) ──┘               │
│                                                │
──────────────────────────────────────────────────
    ↓
Response to user

Supporting components:
- persona.py      → injected into every llm_node call
- memory.json     → loaded at session start, updated during chat
- Tools registry  → bound to LLM via bind_tools()
- LangSmith       → traces every run automatically
```

### How the ReAct loop works

1. User sends a message
2. `llm_node` calls Gemini with persona + memory + chat history
3. If Gemini requests a tool → `tool_node` executes it → result injected back to LLM
4. Loop continues until Gemini produces a final text response
5. Response displayed to user, `[REMEMBER]` tags extracted and saved

## Available Tools

| Tool | Description |
|---|---|
| `get_current_datetime` | Returns current date and time |
| `save_note` | Saves a note or reminder to `data/notes.json` |
| `get_notes` | Retrieves all saved notes |
| `delete_note` | Deletes a note by ID |

## How Memory Works

**Short-term memory** — `chat_history` list maintained in-session. Cleared when the program exits. Sent with every LLM request so Kaia remembers context within a conversation.

**Long-term memory** — facts extracted from conversation and persisted to `data/memory.json`. Kaia is instructed to append `[REMEMBER: fact]` tags when the user mentions something significant. These are parsed, saved, and injected into every future session's system prompt.

```json
{
  "user_name": "Faiz",
  "facts": [
    "Faiz has 4 years of experience as a software developer",
    "Faiz is currently learning AI engineering"
  ],
  "last_seen": "2026-04-13 23:00"
}
```

---

## Roadmap

- [ ] Google Calendar integration
- [ ] GitHub MCP integration
- [ ] Web search tool
- [ ] RAG — answer from personal documents
- [ ] Streamlit web interface
- [ ] LangGraph multi-agent support