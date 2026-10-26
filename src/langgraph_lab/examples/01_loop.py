"""Пример 1 урока 4: цикл из ребра назад и условного выхода на END.

Граф обходит стенд mini_repo по одному файлу за проход. Узел pick_file берёт
следующее имя из очереди, узел scan_file считает в нём строки, ребро от
scan_file ведёт назад к pick_file. Выход на END стоит в функции маршрутизации
после pick_file, то есть проверяется до разбора.
"""

import operator
from pathlib import Path
from typing import Annotated, Any, Literal, NotRequired

from langgraph.graph import START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from typing_extensions import TypedDict

REPO: Path = Path(__file__).parent / "mini_repo"


class WalkState(TypedDict):
    root: str
    queue: list[str]
    current: str
    findings: Annotated[list[str], operator.add]


class QueueUpdate(TypedDict):
    queue: list[str]
    current: str


# На пустой очереди pick_file пишет только current.
class PickUpdate(TypedDict):
    current: str
    queue: NotRequired[list[str]]


class FindingsUpdate(TypedDict):
    findings: list[str]


def collect_files(state: WalkState) -> QueueUpdate:
    """Складывает имена файлов стенда в очередь обхода."""
    names: list[str] = sorted(path.name for path in Path(state["root"]).glob("*.py"))
    return {"queue": names, "current": ""}


def pick_file(state: WalkState) -> PickUpdate:
    """Берёт следующее имя из очереди и убирает его оттуда."""
    queue: list[str] = list(state["queue"])
    if not queue:
        return {"current": ""}
    return {"current": queue.pop(0), "queue": queue}


def scan_file(state: WalkState) -> FindingsUpdate:
    """Считает строки в выбранном файле."""
    path: Path = Path(state["root"]) / state["current"]
    lines: int = len(path.read_text(encoding="utf-8").splitlines())
    return {"findings": [f"{state['current']}: строк {lines}"]}


# END объявлен как str, под Literal mypy его не пускает, поэтому "__end__".
def route_next(state: WalkState) -> Literal["scan_file", "__end__"]:
    """Условие выхода: пустое имя означает, что очередь закончилась."""
    if not state["current"]:
        return "__end__"
    return "scan_file"


builder: StateGraph[WalkState] = StateGraph(WalkState)
builder.add_node(collect_files)
builder.add_node(pick_file)
builder.add_node(scan_file)
builder.add_edge(START, collect_files.__name__)
builder.add_edge(collect_files.__name__, pick_file.__name__)
builder.add_conditional_edges(pick_file.__name__, route_next)
builder.add_edge(scan_file.__name__, pick_file.__name__)
graph: CompiledStateGraph[WalkState] = builder.compile()

start: WalkState = {"root": str(REPO), "queue": [], "current": "", "findings": []}

# 1. Каждый шаг запуска отдельной строкой.
print("1. обход по шагам:")
event: dict[str, Any]
for event in graph.stream(start, stream_mode="updates"):
    print("  ", event)

# 2. Итог обхода.
result: dict[str, Any] = graph.invoke(start)
print("2. находок:", len(result["findings"]))
line: str
for line in result["findings"]:
    print("    ", line)

# 3. Ребро назад на схеме графа.
print("3. схема графа:")
print(graph.get_graph().draw_mermaid())

# Вывод:
# 1. обход по шагам:
#    {'collect_files': {'queue': ['app.py', 'config.py', 'db.py', 'utils.py'], 'current': ''}}
#    {'pick_file': {'current': 'app.py', 'queue': ['config.py', 'db.py', 'utils.py']}}
#    {'scan_file': {'findings': ['app.py: строк 13']}}
#    {'pick_file': {'current': 'config.py', 'queue': ['db.py', 'utils.py']}}
#    {'scan_file': {'findings': ['config.py: строк 6']}}
#    {'pick_file': {'current': 'db.py', 'queue': ['utils.py']}}
#    {'scan_file': {'findings': ['db.py: строк 15']}}
#    {'pick_file': {'current': 'utils.py', 'queue': []}}
#    {'scan_file': {'findings': ['utils.py: строк 10']}}
#    {'pick_file': {'current': ''}}
# 2. находок: 4
#     app.py: строк 13
#     config.py: строк 6
#     db.py: строк 15
#     utils.py: строк 10
# 3. схема графа:
# ---
# config:
#   flowchart:
#     curve: linear
# ---
# graph TD;
#   __start__([<p>__start__</p>]):::first
#   collect_files(collect_files)
#   pick_file(pick_file)
#   scan_file(scan_file)
#   __end__([<p>__end__</p>]):::last
#   __start__ --> collect_files;
#   collect_files --> pick_file;
#   pick_file -.-> __end__;
#   pick_file -.-> scan_file;
#   scan_file --> pick_file;
#   classDef default fill:#f2f0ff,line-height:1.2
#   classDef first fill-opacity:0
#   classDef last fill:#bfb6fc
