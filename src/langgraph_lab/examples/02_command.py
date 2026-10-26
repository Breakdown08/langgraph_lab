"""Пример 2 урока 3: Command вместо пары "обновить состояние и перейти".

Та же развилка, что в примере 1, но узел сам объявляет переход. Условных рёбер
в графе нет вовсе. Ещё в примере: статическое ребро рядом с Command
выполняется вместе с ним, а goto на END заканчивает запуск в первом узле.
"""

import operator
from pathlib import Path
from typing import Annotated, Literal, NotRequired

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command
from typing_extensions import TypedDict

REPO: Path = Path(__file__).parent / "mini_repo"


# На входе только root и limit, files и report дописывают узлы.
class ScanState(TypedDict):
    root: str
    limit: int
    files: NotRequired[list[str]]
    report: NotRequired[Annotated[list[str], operator.add]]


class ReportUpdate(TypedDict):
    report: list[str]


def quick_scan(state: ScanState) -> ReportUpdate:
    """Короткий разбор: только число файлов."""
    return {"report": [f"быстрый разбор: файлов {len(state['files'])}"]}


def deep_scan(state: ScanState) -> ReportUpdate:
    """Подробный разбор: считает строки в каждом файле."""
    root: Path = Path(state["root"])
    total: int = sum(
        len((root / name).read_text(encoding="utf-8").splitlines())
        for name in state["files"]
    )
    return {"report": [f"подробный разбор: строк {total}"]}


def collect_files(state: ScanState) -> Command[Literal["quick_scan", "deep_scan"]]:
    """Собирает файлы и тут же говорит, каким разбором идти дальше."""
    names: list[str] = sorted(path.name for path in Path(state["root"]).glob("*.py"))
    goto: Literal["quick_scan", "deep_scan"] = (
        "quick_scan" if len(names) > state["limit"] else "deep_scan"
    )
    return Command(update={"files": names}, goto=goto)


builder: StateGraph[ScanState] = StateGraph(ScanState)
builder.add_node(collect_files)
builder.add_node(quick_scan)
builder.add_node(deep_scan)
builder.add_edge(START, collect_files.__name__)
builder.add_edge(quick_scan.__name__, END)
builder.add_edge(deep_scan.__name__, END)
graph: CompiledStateGraph[ScanState] = builder.compile()

# 1. Переход задан внутри узла, рёбер между тремя узлами нет.
print("1. предел 2:", graph.invoke({"root": str(REPO), "limit": 2})["report"])
print("   предел 10:", graph.invoke({"root": str(REPO), "limit": 10})["report"])

# 2. Статическое ребро рядом с Command: выполняются оба перехода.
mixed: StateGraph[ScanState] = StateGraph(ScanState)
mixed.add_node(collect_files)
mixed.add_node(quick_scan)
mixed.add_node(deep_scan)
mixed.add_edge(START, collect_files.__name__)
mixed.add_edge(collect_files.__name__, quick_scan.__name__)
mixed.add_edge(quick_scan.__name__, END)
mixed.add_edge(deep_scan.__name__, END)
print(
    "2. Command и ребро вместе:",
    mixed.compile().invoke({"root": str(REPO), "limit": 10})["report"],
)


# 3. Command на END: разбирать нечего, запуск заканчивается в первом узле.
def collect_or_stop(state: ScanState) -> Command[Literal["quick_scan", "__end__"]]:
    """Файлов не нашлось, значит дальше идти незачем."""
    names: list[str] = sorted(path.name for path in Path(state["root"]).glob("*.py"))
    if not names:
        # END равен "__end__", но объявлен как str, а goto ждёт Literal из
        # аннотации. Поэтому здесь сама строка, а не константа.
        return Command(
            update={"report": ["файлов нет, разбор не нужен"]}, goto="__end__"
        )
    return Command(update={"files": names}, goto="quick_scan")


stop: StateGraph[ScanState] = StateGraph(ScanState)
stop.add_node(collect_or_stop)
stop.add_node(quick_scan)
stop.add_edge(START, collect_or_stop.__name__)
stop.add_edge(quick_scan.__name__, END)
stop_graph: CompiledStateGraph[ScanState] = stop.compile()

# Папки docs в стенде нет, поэтому glob по ней вернёт пустой список.
print(
    "3. папки нет:",
    stop_graph.invoke({"root": str(REPO / "docs"), "limit": 2})["report"],
)
print(
    "   стенд на месте:", stop_graph.invoke({"root": str(REPO), "limit": 2})["report"]
)

# Вывод:
# 1. предел 2: ['быстрый разбор: файлов 4']
#    предел 10: ['подробный разбор: строк 44']
# 2. Command и ребро вместе: ['подробный разбор: строк 44', 'быстрый разбор: файлов 4']
# 3. папки нет: ['файлов нет, разбор не нужен']
#    стенд на месте: ['быстрый разбор: файлов 4']
