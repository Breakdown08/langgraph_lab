"""Пример 3 урока 4: счётчик шага и RemainingSteps.

Тот же обход стенда. Узел разбора печатает номер текущего шага из
config["metadata"]["langgraph_step"] и остаток шагов из состояния. Второй граф
использует остаток как условие мягкого выхода: обход сворачивается сам и
возвращает то, что успел собрать, вместо GraphRecursionError.

В уроке remaining_steps в схеме обязательный, а вход его не передаёт. Здесь
поле помечено NotRequired: значение всё равно подставляет LangGraph, а mypy
перестаёт требовать его на входе (проверено запуском).
"""

import operator
from collections.abc import Callable, Hashable, Sequence
from pathlib import Path
from typing import Annotated, Any, Literal, NotRequired

from langchain_core.runnables import RunnableConfig
from langgraph.errors import GraphRecursionError
from langgraph.graph import START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.managed import RemainingSteps
from typing_extensions import TypedDict

REPO: Path = Path(__file__).parent / "mini_repo"


class WalkState(TypedDict):
    root: str
    queue: list[str]
    current: str
    findings: Annotated[list[str], operator.add]
    remaining_steps: NotRequired[RemainingSteps]


class QueueUpdate(TypedDict):
    queue: list[str]
    current: str


class PickUpdate(TypedDict):
    current: str
    queue: NotRequired[list[str]]


class FindingsUpdate(TypedDict):
    findings: list[str]


type Route = Callable[[WalkState], Hashable | Sequence[Hashable]]


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


# LangGraph подставляет config по имени параметра: с другим именем узел падает
# с TypeError о пропущенном аргументе.
def scan_file(state: WalkState, config: RunnableConfig) -> FindingsUpdate:
    """Считает строки и печатает номер шага и остаток шагов."""
    step: int = config["metadata"]["langgraph_step"]
    remaining: int = state["remaining_steps"]
    print(f"   шаг {step}, остаток {remaining}, сумма {step + remaining}")
    path: Path = Path(state["root"]) / state["current"]
    lines: int = len(path.read_text(encoding="utf-8").splitlines())
    return {"findings": [f"{state['current']}: строк {lines}"]}


def route_next(state: WalkState) -> Literal["scan_file", "__end__"]:
    """Выход только по пустой очереди."""
    if not state["current"]:
        return "__end__"
    return "scan_file"


def route_soft(state: WalkState) -> Literal["scan_file", "__end__"]:
    """Тот же выход плюс мягкая остановка за два шага до предела."""
    if state["remaining_steps"] <= 2:
        return "__end__"
    if not state["current"]:
        return "__end__"
    return "scan_file"


def build(router: Route) -> CompiledStateGraph[WalkState]:
    """Собирает один и тот же цикл с разной функцией маршрутизации."""
    builder: StateGraph[WalkState] = StateGraph(WalkState)
    builder.add_node(collect_files)
    builder.add_node(pick_file)
    builder.add_node(scan_file)
    builder.add_edge(START, collect_files.__name__)
    builder.add_edge(collect_files.__name__, pick_file.__name__)
    builder.add_conditional_edges(pick_file.__name__, router)
    builder.add_edge(scan_file.__name__, pick_file.__name__)
    return builder.compile()


def start() -> WalkState:
    """Входное состояние обхода."""
    return {"root": str(REPO), "queue": [], "current": "", "findings": []}


graph: CompiledStateGraph[WalkState] = build(route_next)
soft: CompiledStateGraph[WalkState] = build(route_soft)

# 1. Предел задан, и остаток считается от него.
print("1. предел 11:")
result: dict[str, Any] = graph.invoke(start(), {"recursion_limit": 11})
print("   ключи итога:", sorted(result))

# 2. Предел не задан, работает значение по умолчанию.
print("2. без предела:")
graph.invoke(start())

# 3. Жёсткая остановка: работа не доделана, ошибка вместо результата.
print("3. предел 7, жёсткое условие:")
error: GraphRecursionError
try:
    graph.invoke(start(), {"recursion_limit": 7})
except GraphRecursionError as error:
    print("   ", type(error).__name__)

# 4. Мягкая остановка на том же пределе: результат неполный, но он есть.
print("4. предел 7, мягкое условие:")
partial: dict[str, Any] = soft.invoke(start(), {"recursion_limit": 7})
print("   находок:", len(partial["findings"]), "осталось в очереди:", partial["queue"])

# Вывод:
# 1. предел 11:
#    шаг 3, остаток 8, сумма 11
#    шаг 5, остаток 6, сумма 11
#    шаг 7, остаток 4, сумма 11
#    шаг 9, остаток 2, сумма 11
#    ключи итога: ['current', 'findings', 'queue', 'root']
# 2. без предела:
#    шаг 3, остаток 10004, сумма 10007
#    шаг 5, остаток 10002, сумма 10007
#    шаг 7, остаток 10000, сумма 10007
#    шаг 9, остаток 9998, сумма 10007
# 3. предел 7, жёсткое условие:
#    шаг 3, остаток 4, сумма 7
#    шаг 5, остаток 2, сумма 7
#    шаг 7, остаток 0, сумма 7
#     GraphRecursionError
# 4. предел 7, мягкое условие:
#    шаг 3, остаток 4, сумма 7
#    шаг 5, остаток 2, сумма 7
#    находок: 2 осталось в очереди: ['utils.py']
