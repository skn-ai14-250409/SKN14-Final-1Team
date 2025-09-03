from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
import ast
from langchain_core.tools import tool

llm = ChatOpenAI(
    model="qwen3:0.6b",
    base_url="http://localhost:11434/v1",
    api_key="ollama",
    temperature=0.1,
)

system_message = """
정확하고 간결한 답변을 제공하는 유용한 보조 도구입니다.
계산을 수행할 때는 제공된 계산기 도구를 사용하고 결과가 명확하고 정확한지 확인하십시오.
별도로 명시되지 않는 한 항상 한국어로 답변하십시오.
""".strip()

history = [
    HumanMessage(content="간장고추장 만들려면 간장 몇 스푼이 필요해?"),
    AIMessage(content="간장 고추장은 1/4 쪼이 필요합니다."),
    HumanMessage(content="내가 아까 뭐라고 말했지?"),
]

ALLOWED_NODES = (
    ast.Expression, ast.BinOp, ast.UnaryOp,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod, ast.FloorDiv,
    ast.UAdd, ast.USub, ast.Constant,
    ast.Load, ast.Call, ast.Name  # (원치 않으면 Call/Name 제거)
)

def safe_eval(expr: str):
    node = ast.parse(expr, mode="eval")
    for n in ast.walk(node):
        if not isinstance(n, ALLOWED_NODES):
            raise ValueError(f"허용되지 않는 토큰: {type(n).__name__}")
        if isinstance(n, ast.Call):
            raise ValueError("함수 호출은 허용되지 않습니다.")
        if isinstance(n, ast.Name):
            raise ValueError("식별자는 허용되지 않습니다.")
    return eval(compile(node, "<expr>", "eval"), {"__builtins__": {}}, {})

@tool(parse_docstring=True)
def calculator(expression: str) -> str:
    """Evaluate mathematical expressions and return the result.
    
    Args:
        expression: e.g. "2+2*3"
    """
    try:
        return str(safe_eval(expression))
    except Exception as e:
        return f"error: {e}"



llm_tools = llm.bind_tools([calculator])

state = [SystemMessage(content=system_message), *history]

while True:
    ai = llm_tools.invoke(state)   # 한 턴 생성
    state.append(ai)

    # 툴 호출이 없으면 종료
    tool_calls = getattr(ai, "tool_calls", None) or []
    if not tool_calls:
        break

    # 호출된 툴들 실행 → ToolMessage 추가
    for call in tool_calls:
        if call["name"] == "calculator":
            expr = call["args"]["expression"]
            result = calculator.invoke({"expression": expr})
            state.append(ToolMessage(tool_call_id=call["id"], content=result))

# 최종 답변
print(state[-1].content)