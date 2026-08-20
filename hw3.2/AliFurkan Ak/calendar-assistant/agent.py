import os
import json
from datetime import datetime
from huggingface_hub import InferenceClient, get_token
import tools

class GemmaCalendarAgent:
    def __init__(self):
        tools.init_db()

    def process_request(self, history: list, user_query: str) -> dict:
        token = (
            os.environ.get("HF_TOKEN", "").strip() or 
            os.environ.get("HUGGINGFACEHUB_API_TOKEN", "").strip() or 
            os.environ.get("HF_API_KEY", "").strip() or 
            (get_token() or "").strip()
        )

        if not token:
            return {
                "content": (
                    "⚠️ **HF_TOKEN (Access Token) Bulunamadı!**\n\n"
                    "Hugging Face Serverless Inference API'yi ücretsiz kullanabilmek için:\n"
                    "1. [https://huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) adresinden ücretsiz bir **User Access Token** alın.\n"
                    "2. Space sayfanızda **Settings ➔ Variables and secrets** sekmesinde New Secret oluşturun:\n"
                    "   - **Name:** `HF_TOKEN`\n"
                    "   - **Value:** `hf_...` (Token anahtarınız)\n\n"
                    "Secret eklendikten sonra uygulamanız sorunsuz yanıt verecektir!"
                ),
                "executed_tools": [],
                "timestamp": datetime.now().strftime("%H:%M")
            }
        
        today_str = datetime.today().strftime("%Y-%m-%d")
        system_instruction = (
            f"You are an intelligent, empathetic Personal Calendar AI Assistant powered by Google Gemma. "
            f"Current Local Date: {today_str}. "
            f"You operate the user's SQLite calendar database via tools. "
            f"Always use tools to view, book, update, cancel, find free slots, or generate plans. "
            f"After a tool returns data, carefully interpret and explain the result to the user in a helpful, conversational manner."
        )

        executed_tools = []
        available_tools = {
            "get_calendar_events": tools.get_calendar_events,
            "find_free_slots": tools.find_free_slots,
            "book_event": tools.book_event,
            "update_event": tools.update_event,
            "cancel_event": tools.cancel_event,
            "create_multistep_plan": tools.create_multistep_plan
        }

        def run_tool(name: str, args: dict):
            if name in available_tools:
                out = available_tools[name](**args)
            else:
                out = {"error": f"Tool '{name}' not found."}
            executed_tools.append({
                "tool_name": name,
                "arguments": args,
                "output": out
            })
            return out

        tool_declarations = [
            {
                "type": "function",
                "function": {
                    "name": "get_calendar_events",
                    "description": "Query calendar events between start_date and end_date.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "start_date": {"type": "string", "description": "YYYY-MM-DD start date"},
                            "end_date": {"type": "string", "description": "YYYY-MM-DD end date"},
                            "keyword": {"type": "string", "description": "Optional search keyword"}
                        },
                        "required": ["start_date", "end_date"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "find_free_slots",
                    "description": "Find available free time slots in calendar.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "date": {"type": "string", "description": "Target date YYYY-MM-DD"},
                            "duration_minutes": {"type": "integer", "description": "Required minutes"}
                        },
                        "required": ["date", "duration_minutes"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "book_event",
                    "description": "Book a calendar appointment or event.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "description": "Event title"},
                            "start_time": {"type": "string", "description": "Start YYYY-MM-DD HH:mm"},
                            "end_time": {"type": "string", "description": "End YYYY-MM-DD HH:mm"},
                            "description": {"type": "string", "description": "Optional description"},
                            "category": {"type": "string", "description": "Category name"}
                        },
                        "required": ["title", "start_time", "end_time"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "update_event",
                    "description": "Update an existing calendar event title, time, description, or category.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "event_id": {"type": "string", "description": "ID of the event to update"},
                            "new_title": {"type": "string", "description": "New event title"},
                            "new_start_time": {"type": "string", "description": "New start time YYYY-MM-DD HH:mm"},
                            "new_end_time": {"type": "string", "description": "New end time YYYY-MM-DD HH:mm"},
                            "new_description": {"type": "string", "description": "New description"},
                            "new_category": {"type": "string", "description": "New category name"}
                        },
                        "required": ["event_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "cancel_event",
                    "description": "Cancel an event or day schedule.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "event_id_or_date": {"type": "string", "description": "Event ID or YYYY-MM-DD date"},
                            "reason": {"type": "string", "description": "Cancellation reason"}
                        },
                        "required": ["event_id_or_date"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "create_multistep_plan",
                    "description": "Create a multi-day schedule plan.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "goal": {"type": "string", "description": "Goal description"},
                            "start_date": {"type": "string", "description": "Start date YYYY-MM-DD"},
                            "duration_days": {"type": "integer", "description": "Number of days"},
                            "daily_minutes": {"type": "integer", "description": "Daily minutes"}
                        },
                        "required": ["goal", "start_date"]
                    }
                }
            }
        ]

        models_to_try = [
            "google/gemma-2-9b-it",
            "google/gemma-2-2b-it",
            "meta-llama/Meta-Llama-3.1-8B-Instruct",
            "Qwen/Qwen2.5-72B-Instruct"
        ]

        messages = [{"role": "system", "content": system_instruction}]
        for msg in history:
            role = "user" if msg.get("role") == "user" else "assistant"
            messages.append({"role": role, "content": msg["content"]})
        messages.append({"role": "user", "content": user_query})

        last_error = None
        for model_id in models_to_try:
            try:
                client = InferenceClient(model=model_id, api_key=token)

                response = client.chat_completion(
                    messages=messages,
                    tools=tool_declarations,
                    max_tokens=1024
                )
                
                choice = response.choices[0]
                assistant_msg = choice.message

                # Check if model requested tool execution
                if hasattr(assistant_msg, "tool_calls") and assistant_msg.tool_calls:
                    # Append assistant tool_call message to context
                    tool_calls_data = []
                    for tc in assistant_msg.tool_calls:
                        tool_calls_data.append({
                            "id": getattr(tc, "id", None) or f"call_{tc.function.name}",
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments if isinstance(tc.function.arguments, str) else json.dumps(tc.function.arguments)
                            }
                        })
                    
                    messages.append({
                        "role": "assistant",
                        "content": assistant_msg.content or "",
                        "tool_calls": tool_calls_data
                    })

                    # Execute each tool and feed results back as tool role messages
                    for tc in assistant_msg.tool_calls:
                        fn_name = tc.function.name
                        fn_args = tc.function.arguments
                        if isinstance(fn_args, str):
                            try:
                                fn_args = json.loads(fn_args)
                            except Exception:
                                fn_args = {}
                        
                        out = run_tool(fn_name, fn_args)
                        call_id = getattr(tc, "id", None) or f"call_{fn_name}"
                        
                        messages.append({
                            "role": "tool",
                            "tool_call_id": call_id,
                            "content": json.dumps(out, ensure_ascii=False)
                        })

                    # Turn 2: Ask LLM to interpret tool outputs and respond to user
                    second_response = client.chat_completion(
                        messages=messages,
                        max_tokens=1024
                    )
                    final_text = second_response.choices[0].message.content or "Tool execution completed."
                    return {
                        "content": final_text,
                        "executed_tools": executed_tools,
                        "timestamp": datetime.now().strftime("%H:%M")
                    }

                text_content = assistant_msg.content or "Task processed successfully."
                return {
                    "content": text_content,
                    "executed_tools": executed_tools,
                    "timestamp": datetime.now().strftime("%H:%M")
                }
            except Exception as e:
                last_error = str(e)

        raise RuntimeError(f"Hugging Face Serverless Inference API Error: {last_error}")
