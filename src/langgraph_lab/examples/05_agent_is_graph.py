"""Пример 5 урока 1: тот же разбор стенда, но агентом.

Агент собран функцией create_agent с двумя инструментами для того же стенда
mini_repo. Печатаются класс агента, имена узлов его графа и правки узлов при
запуске в режиме updates. Порядок вызовов инструментов выбирает модель.

В уроке модели передаётся temperature=0. Модели Claude семейства 5 отвечают
на него ошибкой 400, поэтому параметр убран и порядок может меняться.
"""

from pathlib import Path
from typing import Any

from langchain.agents import AgentState, create_agent
from langchain.agents.middleware.types import InputAgentState, OutputAgentState
from langchain_core.messages import AnyMessage, ToolCall
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import StreamPart

from langgraph_lab.course_model import build_model

REPO: Path = Path(__file__).parent / "mini_repo"


def list_files() -> str:
    """Возвращает имена файлов Python в репозитории."""
    names: list[str] = sorted(path.name for path in REPO.glob("*.py"))
    return ", ".join(names)


def file_lines(name: str) -> str:
    """Возвращает число строк в файле репозитория по его имени."""
    path: Path = REPO / name
    if not path.exists():
        return f"Файла {name} в репозитории нет."
    return f"{name}: {len(path.read_text(encoding='utf-8').splitlines())} строк"


agent: CompiledStateGraph[
    AgentState[Any], None, InputAgentState, OutputAgentState[Any]
] = create_agent(
    model=build_model(max_tokens=512),
    tools=[list_files, file_lines],
    system_prompt=(
        "Вы разбираете чужой репозиторий. Отвечайте по-русски, коротко. "
        "Числа берите только из инструментов, своих догадок не добавляйте."
    ),
)

print("КЛАСС АГЕНТА:", type(agent).__name__)
print("УЗЛЫ ГРАФА АГЕНТА:", sorted(agent.get_graph().nodes))
print()

update_no: int = 0
chunk: StreamPart[AgentState[Any], OutputAgentState[Any]]
node: str
# Правка узла приходит как есть: у model и tools это словарь, но тип не задан.
update: Any
messages: list[AnyMessage]
message: AnyMessage
calls: list[ToolCall] | None
text: str
for chunk in agent.stream(
    {
        "messages": [
            {
                "role": "user",
                "content": "Сколько строк в файле db.py и какие ещё файлы есть?",
            }
        ]
    },
    stream_mode="updates",
    version="v2",
):
    if chunk["type"] != "updates":
        continue
    for node, update in chunk["data"].items():
        update_no += 1
        messages = update.get("messages", []) if isinstance(update, dict) else []
        for message in messages:
            calls = getattr(message, "tool_calls", None)
            if calls:
                print(
                    f"правка {update_no}: узел {node}, запрошены {[call['name'] for call in calls]}"
                )
            else:
                text = message.text.replace("\n", " ")
                print(
                    f"правка {update_no}: узел {node}, {type(message).__name__}: {text[:70]}"
                )

print()
print("ПРАВОК ОТ УЗЛОВ:", update_no)

# Вывод:
# КЛАСС АГЕНТА: CompiledStateGraph
# УЗЛЫ ГРАФА АГЕНТА: ['__end__', '__start__', 'model', 'tools']
#
# правка 1: узел model, запрошены ['file_lines', 'list_files']
# правка 2: узел tools, ToolMessage: db.py: 15 строк
# правка 3: узел tools, ToolMessage: app.py, config.py, db.py, utils.py
# правка 4: узел model, AIMessage: Файл **db.py** содержит **15 строк**.  В репозитории также есть файлы:
#
# ПРАВОК ОТ УЗЛОВ: 4
