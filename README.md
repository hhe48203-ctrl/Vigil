# Vigil

A personal Discord AI agent powered by Claude. It reasons in a ReAct loop, uses tools to interact with your filesystem and shell, and builds long-term memory through semantic search.

Inspired by [OpenClaw](https://github.com/OpenClaw) — a Python reimplementation built to understand the core architecture from the ground up.

## Features

- **ReAct reasoning loop** — Claude thinks step-by-step, calling tools as needed before responding
- **Semantic memory** — important events are stored in ChromaDB; each message retrieves the most relevant memories via vector search
- **Persistent identity** — `SOUL.md` defines the agent's personality and rules; `USER.md` stores what it knows about you; both are updated by the agent over time
- **Tool use** — file read/write, shell execution, memory append, user profile update, soul update
- **Heartbeat** — runs an autonomous check every 30 minutes based on `HEARTBEAT.md`
- **Discord interface** — listens and replies in a single configured channel

## Architecture

```
main.py          — starts Discord, Gateway, and Heartbeat concurrently
brain.py         — ReAct loop: builds system prompt, calls Claude API, dispatches tools
gateway.py       — async queue between Discord and Brain
heartbeat.py     — periodic autonomous task runner
channels/        — Discord bot (receive/send messages)
skills/builtin/  — tools: file_ops, shell, memory_ops
memory/          — ChromaDB vector store wrapper
workspace/       — agent's runtime files (SOUL.md, USER.md, memory logs)
```

### Memory system

Every call to `brain.think()` constructs the system prompt fresh:

```
SOUL.md  (full text, always)
USER.md  (full text, always)
Relevant Memories  (top-8 semantic search results from ChromaDB)
```

When the agent calls `memory_append`, the content is written to both a plain-text daily log (`workspace/memory/YYYY-MM-DD.md`) and the ChromaDB vector store. The `.md` files are the human-readable source of truth; ChromaDB is the retrieval index.

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
HEARTBEAT_INTERVAL=1800
```

**3. Set up workspace files**

```bash
cp workspace/SOUL.md.example workspace/SOUL.md
cp workspace/USER.md.example workspace/USER.md
cp workspace/HEARTBEAT.md.example workspace/HEARTBEAT.md  # if provided
```

Edit `workspace/SOUL.md` to give your agent a name and personality.  
Edit `workspace/USER.md` to tell it about yourself (or leave it blank and let the agent fill it in over time).

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

# Clear all memories from the vector store
uv run python manage_memory.py clear
```

The raw `.md` memory logs live in `workspace/memory/` and are not tracked by git.
