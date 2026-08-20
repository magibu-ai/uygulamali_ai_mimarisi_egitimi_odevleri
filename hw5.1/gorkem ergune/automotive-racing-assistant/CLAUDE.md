# CLAUDE.md

## Project

**Automotive Racing Assistant**

Repository:

`automotive-racing-assistant`

This project is an academic local-LLM assistant designed for an automotive/racing team scenario.

The project demonstrates:

- Local LLM usage
- System prompt design
- Tool calling
- Scenario-specific tools
- Multi-step tool usage
- Tool result handling
- Reliable local AI application design

---

## Core Objective

Build a local automotive racing assistant that can:

1. Answer general questions about the racing team scenario.
2. Search the internet when current or external information is required.
3. Retrieve weather information for race preparation.
4. Check the status of vehicle components.
5. Retrieve racing regulation information.
6. Decide when a tool is necessary.
7. Select the appropriate tool.
8. Execute the tool.
9. Return the tool result to the local LLM.
10. Generate a final natural-language response.

The primary objective is reliable tool calling rather than unnecessary application complexity.

---

# Technology

Use:

- Python
- Ollama
- `qwen2.5:7b-instruct`
- Existing `ollama_asistan` architecture
- Terminal interface

Do not introduce:

- LangChain
- LangGraph
- CrewAI
- AutoGen
- MCP
- Other agent frameworks

unless explicitly requested by the user.

The purpose of this assignment is to demonstrate direct local LLM + tool calling implementation.

---

# Repository Structure

Expected structure:

```text
automotive-racing-assistant/
│
├── ollama_asistan/
│   ├── chat.py
│   ├── tools.py
│   ├── ollama_client.py
│   └── race_data.py
│
├── tests/
├── docs/
│
├── CLAUDE.md
├── ROADMAP.md
├── TASKS.md
├── README.md
├── requirements.txt
└── .gitignore
```

Do not create unnecessary files or directories.

---

# Original Template

The project is based on the `ollama_asistan` directory from:

`malibayram/single_letter_transformers`

Before changing code, inspect the existing implementation.

Important files:

- `chat.py`
- `tools.py`
- `ollama_client.py`
- `medical_rag.py`

Reuse the existing architecture where practical.

Medical-specific functionality should be adapted or removed.

Do not blindly rewrite the entire template.

---

# Target Architecture

```text
User
  ↓
System Prompt
  ↓
Qwen2.5 7B
  ↓
Tool required?
  ├── No → Final Answer
  │
  └── Yes
       ↓
   Tool Call
       ↓
   Python Tool
       ↓
   Tool Result
       ↓
   Qwen2.5 7B
       ↓
   Final Answer
```

The assistant may perform multiple tool calls when required.

Use a bounded tool loop.

Recommended:

`MAX_TOOL_ROUNDS = 5`

Never allow an infinite tool-calling loop.

---

# Scenario

The assistant represents an automotive/racing team assistant.

It can help with:

- Race preparation
- Vehicle maintenance
- Vehicle component status
- Weather
- Racing regulations
- Current external information

The project uses demonstration/mock vehicle data.

It does NOT have access to:

- Real vehicle telemetry
- Real sensors
- Real team databases
- Confidential university information

The assistant must never pretend that mock data is real telemetry.

---

# Required Tools

## `internet_search`

Purpose:

Search the internet for current or external information.

Use when:

- Information is time-sensitive.
- Information is external.
- The user explicitly asks for a web search.
- Internal tools cannot provide the required information.

Do not use it unnecessarily.

---

## `get_weather`

Purpose:

Retrieve weather information for a race location.

Use when the user asks about:

- Current weather
- Forecast weather
- Race-day weather
- Weather-related race preparation

Never invent weather results.

---

## `check_part_status`

Purpose:

Retrieve vehicle component information from the demonstration dataset.

Possible components:

- brake pads
- tires
- engine oil
- battery
- brake discs

The tool should return information such as:

- component
- status
- last inspection
- remaining measurement when available
- warning information

---

## `get_race_regulations`

Purpose:

Retrieve racing regulation information from the internal demonstration dataset.

Possible topics:

- brakes
- tires
- safety
- electrical
- driver
- technical inspection

Never invent regulation information.

If the requested information is unavailable, explicitly say that it is unavailable.

---

# Tool Selection Rules

The system prompt must teach the model the following behavior.

### Weather

Use:

`get_weather`

for weather-related questions.

### Vehicle components

Use:

`check_part_status`

for:

- component condition
- maintenance status
- inspection status
- remaining component life
- component warnings

### Regulations

Use:

`get_race_regulations`

for racing or technical regulation questions.

### Current information

Use:

`internet_search`

for:

- current information
- external information
- explicit search requests

### No tool

Do not call a tool when the question can be answered directly.

---

# System Prompt

The system prompt must define:

1. Role
2. Scenario
3. Capabilities
4. Tool descriptions
5. Tool selection rules
6. When not to use tools
7. Tool result handling
8. Hallucination prevention
9. Mock-data limitations
10. Multi-tool behavior
11. Response style

The system prompt should be optimized for a 7B local model.

Prefer concise, explicit instructions.

Use few-shot examples only when they improve tool selection.

---

# Tool Result Rules

The assistant must:

- Never invent tool results.
- Never claim a tool was used if it was not.
- Never expose raw JSON unless requested.
- Base the final answer on actual tool results.
- Distinguish mock/demo data from real-world data.
- Avoid unsupported engineering claims.

---

# Multi-Tool Behavior

The assistant must be able to perform multiple tool calls when necessary.

Example:

User:

"Yarın yağmur varsa fren balatalarımızı kontrol etmeli miyiz?"

Possible flow:

```text
get_weather
      ↓
weather result
      ↓
check_part_status
      ↓
part status result
      ↓
final answer
```

Do not perform unnecessary tool calls.

---

# Reliability

Handle:

- Ollama connection errors
- malformed tool calls
- unknown tools
- missing arguments
- invalid arguments
- tool exceptions
- external API failures
- unknown components
- unknown regulation topics
- maximum tool rounds

The application must fail gracefully.

---

# Code Quality

Prefer:

- simple functions
- readable code
- type hints where useful
- clear naming
- minimal dependencies
- explicit error handling

Do not over-engineer.

Do not introduce large frameworks for simple functionality.

---

# Testing

The project must test:

1. Direct response
2. Weather tool
3. Part status tool
4. Regulation tool
5. Internet search
6. Multi-tool scenario
7. Unknown information
8. Invalid arguments
9. Tool failure
10. Maximum tool rounds

Do not claim a test passed unless it was actually executed.

---

# Documentation

README.md must contain:

- Project overview
- Assignment objective
- Architecture
- Technologies
- Installation
- Ollama setup
- Model setup
- Usage
- Available tools
- System prompt strategy
- Tool calling examples
- Real test conversations
- Tool call logs
- Limitations
- Future improvements
- Project structure

Never fabricate test outputs.

---

# Git Rules

Never perform destructive Git operations without explicit user approval.

Do not use:

```text
git reset --hard
git push --force
```

Do not rewrite history.

Use meaningful commits such as:

```text
feat: adapt assistant to automotive scenario
feat: add racing tools
feat: optimize system prompt
test: add tool calling scenarios
fix: handle tool execution errors
docs: add project documentation
```

Never commit:

- API keys
- `.env`
- secrets
- virtual environments
- model files
- caches
- logs containing secrets

---

# Development Workflow

Before changing code:

1. Read `CLAUDE.md`.
2. Read `ROADMAP.md`.
3. Read `TASKS.md`.
4. Inspect the existing implementation.
5. Understand the tool-calling flow.
6. Make the smallest necessary change.
7. Run relevant tests.
8. Fix failures.
9. Update `TASKS.md`.
10. Update `ROADMAP.md` when a phase changes.

Never mark work complete without verification.

---

# Priority

The project priorities are:

1. Local LLM
2. Reliable tool calling
3. System prompt optimization
4. Scenario-specific functionality
5. Error handling
6. Testing
7. Documentation

Keep the project simple, reliable, and demonstrable.
