import os
import json
from datetime import datetime
import gradio as gr
from agent import GemmaCalendarAgent

try:
    import spaces
    has_spaces = True
except ImportError:
    has_spaces = False

agent = GemmaCalendarAgent()

def predict(message, history):
    # In Gradio 5 with type="messages", history is a list of dicts: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
    formatted_history = []
    if isinstance(history, list):
        for msg in history:
            if isinstance(msg, dict) and "role" in msg and "content" in msg:
                clean_content = msg["content"].split("<div style='background: rgba(15, 23, 42")[0].strip()
                formatted_history.append({"role": msg["role"], "content": clean_content})
            elif isinstance(msg, (tuple, list)) and len(msg) == 2:
                u, a = msg
                if u:
                    formatted_history.append({"role": "user", "content": str(u)})
                if a:
                    formatted_history.append({"role": "assistant", "content": str(a).split("<div style='background: rgba(15, 23, 42")[0].strip()})

    try:
        result = agent.process_request(formatted_history, message)
        reply_content = result["content"]
        executed_tools = result.get("executed_tools", [])

        # Format tool badges if tools were executed
        if executed_tools:
            tool_badges_html = "<br/><br/>"
            for tool in executed_tools:
                t_name = tool["tool_name"]
                t_args = json.dumps(tool["arguments"], ensure_ascii=False)
                t_out = json.dumps(tool["output"], ensure_ascii=False)
                tool_badges_html += f"""
                <div style='background: rgba(15, 23, 42, 0.95); border: 1px solid rgba(6, 182, 212, 0.4); border-radius: 10px; padding: 10px 14px; margin-top: 8px; font-size: 0.85rem;'>
                    <div style='color: #38bdf8; font-weight: 600; display: flex; justify-content: space-between;'>
                        <span>⚙️ Python Tool Executed: <b>{t_name}</b></span>
                        <span style='color: #34d399;'>✓ Executed against SQLite</span>
                    </div>
                    <div style='font-family: monospace; background: rgba(0,0,0,0.5); padding: 8px; border-radius: 6px; color: #a7f3d0; margin-top: 6px; word-break: break-all;'>
                        <b>Args:</b> {t_args}<br/>
                        <b>SQLite Output:</b> {t_out}
                    </div>
                </div>
                """
            reply_content += tool_badges_html

        return reply_content
    except Exception as e:
        return f"⚠️ Error: {str(e)}"

# Apply spaces.GPU decorator if ZeroGPU is active on Hugging Face Space
if has_spaces:
    try:
        predict = spaces.GPU(predict)
    except Exception:
        pass

demo = gr.ChatInterface(
    fn=predict,
    type="messages",
    title="✨ Gemma 2 Calendar AI Agent",
    description="Python • Gradio 5 • Hugging Face Serverless Inference • SQLite Tools | Powered by Google Gemma 2 LLM",
    examples=[
        "Check my schedule tomorrow",
        "Find 2 hours free time tomorrow",
        "Book dentist visit for tomorrow 10am",
        "Cancel my schedule on Friday",
        "Create a 3-day workout plan"
    ]
)

if __name__ == "__main__":
    demo.queue().launch()
