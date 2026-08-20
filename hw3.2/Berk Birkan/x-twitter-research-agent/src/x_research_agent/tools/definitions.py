from typing import Any


def function_tool(name: str, description: str, parameters: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": parameters,
        },
    }


TOOL_DEFINITIONS = [
    function_tool(
        "search_x_posts",
        "Search public X posts through the read-only Xquik API. Use focused X search syntax. "
        "The application enforces language, date, retweet and total post-budget constraints.",
        {
            "type": "object",
            "properties": {
                "query": {"type": "string", "minLength": 1},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                "cursor": {"type": ["string", "null"]},
                "purpose": {
                    "type": "string",
                    "description": (
                        "Short user-visible reason for this search; no hidden reasoning."
                    ),
                },
            },
            "required": ["query", "limit", "purpose"],
            "additionalProperties": False,
        },
    ),
    function_tool(
        "get_x_post",
        "Fetch one public X post by numeric ID or x.com status URL through the read-only API.",
        {
            "type": "object",
            "properties": {"post_id_or_url": {"type": "string"}},
            "required": ["post_id_or_url"],
            "additionalProperties": False,
        },
    ),
    function_tool(
        "save_search_results",
        "Persist the exact, unmodified Xquik results from a previous search_call_id to PostgreSQL. "
        "Call this for every search whose posts may be used in the report.",
        {
            "type": "object",
            "properties": {"search_call_id": {"type": "string"}},
            "required": ["search_call_id"],
            "additionalProperties": False,
        },
    ),
    function_tool(
        "finalize_research",
        "Validate citations and save the final structured research report to PostgreSQL. "
        "A successful research turn must end with this tool.",
        {
            "type": "object",
            "properties": {
                "report": {
                    "type": "object",
                    "properties": {
                        "short_answer": {"type": "string"},
                        "sentiment_overview": {"type": "string"},
                        "positive_themes": {
                            "type": "array",
                            "items": {"$ref": "#/properties/report/$defs/theme"},
                        },
                        "negative_themes": {
                            "type": "array",
                            "items": {"$ref": "#/properties/report/$defs/theme"},
                        },
                        "answer_to_user_question": {"type": "string"},
                        "evidence": {
                            "type": "array",
                            "minItems": 1,
                            "items": {
                                "type": "object",
                                "properties": {
                                    "post_id": {"type": "string"},
                                    "claim": {"type": "string"},
                                },
                                "required": ["post_id", "claim"],
                                "additionalProperties": False,
                            },
                        },
                        "limitations": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": [
                        "short_answer",
                        "sentiment_overview",
                        "positive_themes",
                        "negative_themes",
                        "answer_to_user_question",
                        "evidence",
                        "limitations",
                    ],
                    "$defs": {
                        "theme": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "summary": {"type": "string"},
                                "post_ids": {
                                    "type": "array",
                                    "minItems": 1,
                                    "items": {"type": "string"},
                                },
                            },
                            "required": ["title", "summary", "post_ids"],
                            "additionalProperties": False,
                        }
                    },
                    "additionalProperties": False,
                }
            },
            "required": ["report"],
            "additionalProperties": False,
        },
    ),
    function_tool(
        "get_saved_research",
        "Read a saved research thread from PostgreSQL using its thread ID and access code.",
        {
            "type": "object",
            "properties": {
                "thread_id": {"type": "string"},
                "access_code": {"type": "string"},
            },
            "required": ["thread_id", "access_code"],
            "additionalProperties": False,
        },
    ),
    function_tool(
        "list_session_research",
        "List research threads belonging to the current anonymous browser session.",
        {"type": "object", "properties": {}, "additionalProperties": False},
    ),
    function_tool(
        "delete_research",
        "Permanently delete a research thread owned by the current session. "
        "Only call after the user explicitly confirms deletion.",
        {
            "type": "object",
            "properties": {
                "thread_id": {"type": "string"},
                "confirmed": {"type": "boolean", "const": True},
            },
            "required": ["thread_id", "confirmed"],
            "additionalProperties": False,
        },
    ),
]
