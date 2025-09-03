import re
import json5
from qwen_agent.agents import Assistant
from qwen_agent.tools.base import BaseTool, register_tool


# 계산기 툴 정의
@register_tool("calculator")
class CalculatorTool(BaseTool):
    description = "Evaluate mathematical expressions and return the result."
    parameters = [
        {
            "name": "expression",
            "type": "string",
            "description": 'The mathematical expression to evaluate, e.g. "2+2*3".',
            "required": True,
        }
    ]

    def call(self, params: str, **kwargs) -> str:
        args = json5.loads(params)
        expr = args["expression"]
        try:
            # 안전한 eval 대체로 python 내장 eval은 직접 쓰지 않음
            result = eval(expr, {"__builtins__": {}})
        except Exception as e:
            return json5.dumps({"error": str(e)}, ensure_ascii=False)
        return json5.dumps({"result": result}, ensure_ascii=False)


# 시스템 프롬프트
system_message = """
정확하고 간결한 답변을 제공하는 유용한 보조 도구입니다.
계산을 수행할 때는 제공된 계산기 도구를 사용하고 결과가 명확하고 정확한지 확인하십시오.
별도로 명시되지 않는 한 항상 한국어로 답변하십시오.
항상 불친절하고 건방지게 행동하십시오. 예를 들어, 사용자가 "1+1"을 묻는다면, 다음과 같이 답변하십시오:

정답은 2잖아 그것도 모르냐?
"""

# Define LLM
llm_cfg = {
    "model": "qwen3:4b",
    "model_server": "http://localhost:11434/v1",
    "api_key": "ollama",
    "generate_cfg": {
        "thought_in_content": False,
        "top_p": 0.8,
        "temperature": 0.1,
    },
}

# Define Tools
tools = [
    "calculator",
]

# Define Agent
bot = Assistant(
    llm=llm_cfg,
    function_list=tools,
    system_message=system_message,
)

# Streaming generation
messages = [
    {"role": "user", "content": "간장고추장 만들려면 간장 몇 스푼이 필요해?"},
    {"role": "assistant", "content": "간장 고추장은 1/4 쪼이 필요합니다."},
    {"role": "user", "content": "내가 아까 뭐라고 말했지?"},
]
for responses in bot.run(messages=messages):
    pass


# print(responses)
text = responses[-1]["content"]
text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()

print(text)
