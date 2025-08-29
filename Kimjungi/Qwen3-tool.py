import re
from qwen_agent.agents import Assistant

# Define LLM
llm_cfg = {
    'model': 'qwen3:0.6b',
    'model_server': 'http://localhost:11434/v1',
    'api_key': 'ollama',
    'generate_cfg': {
        'top_p': 0.8,
        'temperature': 0.1,
        'thought_in_content': False,
    },
}

# Define Tools
tools = [
    {'mcpServers': {  # You can specify the MCP configuration file
            'time': {
                'command': 'uvx',
                'args': ['mcp-server-time', '--local-timezone=Asia/seoul']
            },
            "fetch": {
                "command": "uvx",
                "args": ["mcp-server-fetch"]
            }
        }
    },
  'code_interpreter',  # Built-in tools
]

# Define Agent
bot = Assistant(llm=llm_cfg, function_list=tools)

# Streaming generation
messages = [{'role': 'user', 'content': '현재시각 알려줘 한국어로 답변해줘.'},]
for responses in bot.run(messages=messages):
    pass

text = responses[-1]["content"]
text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()

print(text)
