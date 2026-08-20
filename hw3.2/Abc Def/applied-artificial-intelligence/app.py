import json
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
import re
import sqlite3

def get_chat_template():
    return "{{ bos_token }} \
{%- if tools is defined and tools is not none -%} \
    {{ '<|system|>You have access to the following tools:\n' }} \
    {%- for tool in tools -%} \
        {{ '<|tool_definition|>\n' }} \
        {{ tool | tojson }} \
        {{ '\n<|tool_definition|>\n' }} \
    {%- endfor -%} \
    {{ 'Use them when necessary.<|system|>\n' }} \
{%- endif -%} \
\
{%- for message in messages -%} \
    {%- if message['role'] == 'system' -%} \
        {{ '<|system|>' + message['content'] + '<|system|>\n' }} \
    {%- elif message['role'] == 'user' -%} \
        {{ '<|user|>' + message['content'] + '<|user|>\n' }} \
    {%- elif message['role'] == 'assistant' -%} \
        {{ '<|assistant|>' }} \
        {%- if message.reasoning_content is defined and message.reasoning_content is not none -%} \
            {{ '<|channel>thought\n' + message.reasoning_content + '\n<channel|>' }} \
        {%- elif message.reasoning is defined and message.reasoning is not none -%} \
            {{ '<|channel>thought\n' + message.reasoning + '\n<channel|>' }} \
        {%- endif -%} \
        {%- if message['content'] -%} \
            {{ message['content'] }} \
        {%- endif -%} \
        {%- if message.tool_calls is defined and message.tool_calls is not none -%} \
            {%- for tool_call in message.tool_calls -%} \
                {{ '<|tool_call>' }} \
                {{ { \"name\": tool_call.function.name, \"arguments\": tool_call.function.arguments } | tojson }} \
                {{ '<tool_call|>\n' }} \
            {%- endfor -%} \
        {%- endif -%}} \
        {{ '<|assistant|>\n' }} \
    {%- elif message['role'] == 'tool' or message['role'] == 'tool_response' -%} \
        {{ '<|tool_response|>' + message['content'] + '<|tool_response|>\n' }} \
    {%- endif -%} \
{%- endfor -%} \
\
{%- if add_generation_prompt -%} \
    {{ '<|assistant|>' }} \
    {%- if enable_thinking | default(false) -%} \
        {{ '<|channel>thought\n' }} \
    {%- endif -%} \
{%- endif -%}"

def get_book_list():
    """
    Returns a list of available books in following format:

    [
      {
        "id": 1,
        "name": "The Alchemist",
        "writer": "Paulo Coelho",
        "genre": "allegory"
      },
      {
        "id": 2,
        "name": "Dune",
        "writer": "Frank Herbert",
        "genre": "science fiction"
      },
      ...
    ]
    """
    with sqlite3.connect("hw.db") as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM books")

        rows = cursor.fetchall()

    return rows

def buy_book(book_name: str) -> str:
  """
  Purchases book with name if exists. Result format is:

  "Book \"{book_name}\" not found"

  for success and

  ""Successfully bought book \"{book_name}\""

  if book is not found.

  Args:
    book_name: The name of the book to be bought. For example, "The Alchemist".
  """
  with sqlite3.connect("hw.db") as conn:
      cursor = conn.cursor()

      search_query = "SELECT * FROM books WHERE name = ?"
      cursor.execute(search_query, (book_name,))
      record = cursor.fetchone()
      if record is None:
        return f"Book \"{book_name}\" not found"

      delete_query = "DELETE FROM books WHERE name = ?"
      cursor.execute(delete_query, (book_name,))
      conn.commit()
      return f"Successfully bought book \"{book_name}\""

TOOLS = [get_book_list, buy_book]

TOOL_MAPPING = {
    "get_book_list": get_book_list,
    "buy_book": buy_book
}

SYSTEM_PROMPT = """You are a helpful AI assistant equipped with tools.
When user asks to buy a book, just buy the book do not take any other action.
When user asks to list books, just list books do not take any other action.

When use asks to list books, you MUST use the following tool syntax to call the API:
<tool_call>{"tool": "get_book_list", "parameters": {}}</tool_call>

When user asks to buy a book, you MUST use the following tool syntax to call the API:
<tool_call>{"tool": "buy_book", "parameters": {"book_name": <string>}}</tool_call>

Do NOT put json.dumps or any related function in the JSON.

Do not say anything else except the exact JSON block if a tool call is needed.
"""

model_id = "unsloth/gemma-4-12B-it"

tokenizer = AutoTokenizer.from_pretrained(model_id)

tokenizer.chat_template = get_chat_template()

model = AutoModelForCausalLM.from_pretrained(
    model_id,
    quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16),
    device_map="auto"
)

def run_agent_workflow(user_query: str):
    print(f"\n🚀 User Query: {user_query}")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_query}
    ]

    max_tool_steps = 5
    step = 0

    while step < max_tool_steps:
        step += 1

        inputs = tokenizer.apply_chat_template(
          messages,
          tools=TOOLS,
          tokenize=True,
          return_dict=True,
          return_tensors="pt",
          add_generation_prompt=False,
          enable_thinking=False
        ).to(model.device)
        input_len = inputs["input_ids"].shape[-1]

        outputs = model.generate(**inputs, max_new_tokens=1024)
        response = tokenizer.decode(outputs[0][input_len:], skip_special_tokens=False)

        # Parse output
        output = tokenizer.parse_response(response)
        content = output['content'].strip()

        if "<tool_call>" in content:
          pattern = "<tool_call>(.*?)</tool_call>"
          res_match = re.search(pattern, content, flags=re.DOTALL | re.MULTILINE)
          tool_call = res_match.group(1)

          tool_call = json.loads(tool_call.strip())

          tool_name, tool_args = tool_call['tool'], tool_call['parameters']
          tool_name = tool_name.strip()

          if tool_name in TOOL_MAPPING:
                tool = TOOL_MAPPING[tool_name]
                print(f"  [Step {step}] Calling: '{tool_name}'")
                tool_response = tool(**tool_args)
                print(f"  [Step {step}] 🔌 Tool Result: {tool_response}")
                messages.append({"role": "assistant", "content": content})
                messages.append({"role": "user",
                                    "content": f"Tool '{tool_name}' returned: {tool_response}. Process this and continue."})
        else:
          print(content)
          break


def main():
    while True:
        query = input("Enter query (enter 'exit' to exit): ")
        if query == 'exit':
            break
        run_agent_workflow(query)

    #run_agent_workflow("List me books of AI Book Cafe")
    #run_agent_workflow("Buy 'Dune' from AI Book Cafe")

if __name__ == "__main__":
    main()