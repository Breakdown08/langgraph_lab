"""Пример 5 урока 2: раздельные схемы входа и выхода, приватный ключ и контекст.

Граф строит карточку стенда mini_repo. На входе принимается один ключ, наружу
отдаётся тоже один, а промежуточные размеры файлов идут приватным ключом от
первого узла ко второму. Настройки запуска передаются контекстом.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import NotRequired

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime
from langgraph.types import StreamPart
from typing_extensions import TypedDict

REPO: Path = Path(__file__).parent / "mini_repo"


class InputState(TypedDict):
    root: str


class OutputState(TypedDict):
    card: str


# Вход графа проверяет InputState, а OverallState здесь описывает правку
# make_card: в ней только card и files, поэтому root тоже не обязателен.
class OverallState(TypedDict):
    root: NotRequired[str]
    card: NotRequired[str]
    files: NotRequired[list[str]]


class PrivateState(TypedDict):
    sizes: dict[str, int]


@dataclass
class RunContext:
    label: str = "обзор"
    max_files: int = 2


def scan(state: InputState, runtime: Runtime[RunContext]) -> PrivateState:
    """Считает строки в первых файлах стенда, число файлов задаёт контекст запуска."""
    print("   узел scan получил runtime.context =", runtime.context)
    # Типы обещают RunContext, но без context при вызове приходит None.
    context: RunContext = runtime.context or RunContext()
    paths: list[Path] = sorted(Path(state["root"]).glob("*.py"))[: context.max_files]
    sizes: dict[str, int] = {
        path.name: len(path.read_text(encoding="utf-8").splitlines()) for path in paths
    }
    return {"sizes": sizes}


def make_card(state: PrivateState, runtime: Runtime[RunContext]) -> OverallState:
    """Собирает карточку из приватных размеров и подписи из контекста."""
    context: RunContext = runtime.context or RunContext()
    parts: list[str] = [f"{name}: {lines}" for name, lines in state["sizes"].items()]
    return {
        "card": f"{context.label}, " + "; ".join(parts),
        "files": list(state["sizes"]),
    }


builder: StateGraph[OverallState, RunContext, InputState, OutputState] = StateGraph(
    OverallState,
    context_schema=RunContext,
    input_schema=InputState,
    output_schema=OutputState,
)
builder.add_node("scan", scan)
builder.add_node("make_card", make_card)
builder.add_edge(START, "scan")
builder.add_edge("scan", "make_card")
builder.add_edge("make_card", END)

graph: CompiledStateGraph[OverallState, RunContext, InputState, OutputState] = (
    builder.compile()
)

# Пункты 2 и 3: типы LangGraph ждут в context объект RunContext, а при запуске
# принимают и словарь. Пример показывает словарь: пустой {} подставляет
# значения по умолчанию, а отсутствие context даёт None. Поэтому там стоит
# игнор call-overload.
print("1. без контекста вовсе:", graph.invoke({"root": str(REPO)}))
print("2. пустой контекст:", graph.invoke({"root": str(REPO)}, context={}))  # type: ignore[call-overload]
print(
    "3. свой контекст:",
    graph.invoke(  # type: ignore[call-overload]
        {"root": str(REPO)}, context={"label": "полный обход", "max_files": 4}
    ),
)

print("4. снимки состояния потоком:")
chunk: StreamPart[OverallState, OutputState]
for chunk in graph.stream({"root": str(REPO)}, stream_mode="values", version="v2"):
    # Режим один, values; проверка сужает тип снимка для проверки типов.
    if chunk["type"] != "values":
        continue
    print("   ключи снимка:", sorted(chunk["data"]))

# Вывод:
#    узел scan получил runtime.context = None
# 1. без контекста вовсе: {'card': 'обзор, app.py: 13; config.py: 6'}
#    узел scan получил runtime.context = RunContext(label='обзор', max_files=2)
# 2. пустой контекст: {'card': 'обзор, app.py: 13; config.py: 6'}
#    узел scan получил runtime.context = RunContext(label='полный обход', max_files=4)
# 3. свой контекст: {'card': 'полный обход, app.py: 13; config.py: 6; db.py: 15; utils.py: 10'}
# 4. снимки состояния потоком:
#    ключи снимка: ['root']
#    узел scan получил runtime.context = None
#    ключи снимка: ['root', 'sizes']
#    ключи снимка: ['card', 'files', 'root', 'sizes']
