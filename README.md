# Vigil

A personal Discord AI agent powered by Claude. It reasons in a ReAct loop, uses tools to interact with your filesystem and shell, and builds long-term memory through semantic search.

Inspired by [OpenClaw](https://github.com/OpenClaw) — a Python reimplementation built to understand the core architecture from the ground up.

## Features

- **ReAct reasoning loop** — Claude thinks step-by-step, calling tools as needed before responding
- **Semantic memory** — important events are stored in ChromaDB; each message retrieves the most relevant memories via vector search
- **Persistent identity** — `SOUL.md` defines the agent's personality and rules; `USER.md` stores what it knows about you; both are updated by the agent over time
- **Extensible skill system** — builtin tools (file ops, shell, memory) plus user-defined skills in `workspace/skills/` that are loaded dynamically at startup
- **Dangerous command approval** — shell commands matching risky patterns (e.g. `rm -rf`, `sudo`, `dd`) require explicit user confirmation via Discord before executing
- **History compression** — when conversation history grows too long, older messages are summarized automatically to stay within context limits
- **Heartbeat** — runs an autonomous check every 30 minutes based on `HEARTBEAT.md`; only notifies you if something is wrong
- **Discord interface** — listens and replies in a single configured channel

## Architecture

```
main.py              — starts Discord, Gateway, and Heartbeat concurrently
brain.py             — ReAct loop: builds system prompt, calls Claude API, dispatches tools
gateway.py           — async queue between Discord and Brain
heartbeat.py         — periodic autonomous task runner
approval_manager.py  — middleware for dangerous shell commands (request → Discord → resolve)
channels/            — Discord bot (receive/send messages, handle approvals)
skills/
  loader.py          — dynamic skill loader (builtin + workspace/skills/)
  builtin/           — core tools: file_ops, shell, memory_ops
memory/              — ChromaDB vector store wrapper
workspace/
  SOUL.md            — agent personality and rules
  USER.md            — user profile (updated by the agent over time)
  HEARTBEAT.md       — autonomous task prompt
  memory/            — daily memory logs (.md) + ChromaDB vector index
  skills/            — user-defined skills (override builtins if same name)
```

### Memory system

Every call to `brain.think()` constructs the system prompt fresh:

```
SOUL.md  (full text, always)
USER.md  (full text, always)
Relevant Memories  (top-8 semantic search results from ChromaDB)
```

When the agent calls `memory_append`, the content is written to both a plain-text daily log (`workspace/memory/YYYY-MM-DD.md`) and the ChromaDB vector store. The `.md` files are the human-readable source of truth; ChromaDB is the retrieval index.

### Skill system

Skills are Python modules that expose either a single `TOOL_DEFINITION` or a list `TOOL_DEFINITIONS`. At startup, `skills/loader.py` loads all builtin skills first, then all modules in `workspace/skills/`. Workspace skills override builtins if they share the same tool name, letting you customize or replace any tool without touching core code.

### Dangerous command approval

When the shell tool detects a risky pattern in a command, it pauses and sends an approval request to Discord. The agent waits up to 60 seconds for you to reply `yes` or `no`. If no reply arrives, the command is automatically rejected.

### History compression

When the conversation history exceeds `HISTORY_COMPRESS_THRESHOLD` messages, `brain.py` summarizes the older portion using `claude-haiku` and replaces it with a compact summary, keeping the most recent `HISTORY_KEEP_RECENT` messages intact.

## Setup

**1. Clone and install dependencies**

```bash
git clone <repo-url>
cd pyagent
uv sync          # or: pip install -r requirements.txt
```

**2. Configure environment**

```bash
cp .env.example .env
```

Edit `.env` and fill in your keys:

```
ANTHROPIC_API_KEY=sk-ant-...
DISCORD_BOT_TOKEN=...
DISCORD_CHANNEL_ID=...

# Optional — defaults shown
HEARTBEAT_INTERVAL=1800          # seconds between heartbeat runs
HISTORY_COMPRESS_THRESHOLD=40    # messages before compression triggers
HISTORY_KEEP_RECENT=20           # messages to keep after compression
TAVILY_API_KEY=...               # required only if using the web_search skill
```

**3. Set up workspace files**

```bash
cp workspace/SOUL.md.example workspace/SOUL.md
cp workspace/USER.md.example workspace/USER.md
```

Edit `workspace/SOUL.md` to give your agent a name and personality.
Edit `workspace/USER.md` to tell it about yourself (or leave it blank and let the agent fill it in over time).
Edit `workspace/HEARTBEAT.md` to define what the agent should check periodically.

**4. Run**

```bash
uv run python main.py
```

## Requirements

- Python 3.12+
- An [Anthropic API key](https://console.anthropic.com)
- A Discord bot token with message content intent enabled ([guide](https://discord.com/developers/docs/intro))

## Managing memory

```bash
# List all stored memories
uv run python manage_memory.py list

# Search memories semantically
uv run python manage_memory.py search "your query"

# Delete a specific memory by index (use list to find the index)
uv run python manage_memory.py delete <index>

# Clear all memories from the vector store
uv run python manage_memory.py clear
```

The raw `.md` memory logs live in `workspace/memory/` and are not tracked by git.

## Adding custom skills

Create a Python file in `workspace/skills/`. It must expose either:

```python
# Single tool
TOOL_DEFINITION = {"name": "my_tool", "description": "...", "input_schema": {...}}

async def my_tool(param: str) -> str:
    ...
```

```python
# Multiple tools
TOOL_DEFINITIONS = [
    {"name": "tool_a", ...},
    {"name": "tool_b", ...},
]

async def tool_a(...): ...
async def tool_b(...): ...
```

The skill is loaded automatically on next startup. If the tool name matches a builtin, your workspace skill takes precedence.
