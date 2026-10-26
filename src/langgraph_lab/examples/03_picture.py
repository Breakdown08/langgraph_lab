"""Пример 3 урока 3: что попадает на схему графа.

Одна и та же развилка собрана на условном ребре, на Command и с параметром
destinations, с подсказкой о переходах и без неё. Для каждой сборки печатаются
рёбра схемы графа. В конце показан переход на узел, которого в графе нет.

В уроке варианты «без подсказки» написаны вовсе без аннотаций. Здесь у них
`-> str` и `-> Command[str]`: LangGraph ищет в аннотации Literal, и без него
схема та же, что без аннотации (проверено запуском). Так ruff и mypy не
приходится глушить.
"""

from typing import Literal, NotRequired, Protocol

from langchain_core.runnables.graph import Edge
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command
from typing_extensions import TypedDict


class ScanState(TypedDict):
    files: list[str]
    report: NotRequired[str]


class FilesUpdate(TypedDict):
    files: list[str]


class ReportUpdate(TypedDict):
    report: str


# Узел сбора приходит в base аргументом. Callable[[ScanState], ...] под типы
# LangGraph не подходит, нужен протокол с __call__.
class CollectNode(Protocol):
    __name__: str

    def __call__(self, state: ScanState) -> object: ...


def quick_scan(state: ScanState) -> ReportUpdate:
    """Короткий разбор."""
    return {"report": "быстрый разбор"}


def deep_scan(state: ScanState) -> ReportUpdate:
    """Подробный разбор."""
    return {"report": "подробный разбор"}


def edges(builder: StateGraph[ScanState]) -> list[str]:
    """Возвращает рёбра собранного графа в том виде, в каком их строит схема."""
    graph: CompiledStateGraph[ScanState] = builder.compile()
    lines: list[str] = []
    edge: Edge
    for edge in graph.get_graph().edges:
        lines.append(
            f"{edge.source} -> {edge.target}"
            + (" (условное)" if edge.conditional else "")
        )
    return lines


def base(collect: CollectNode) -> StateGraph[ScanState]:
    """Каркас из трёх узлов, общий для всех вариантов. Узел сбора — collect_files."""
    builder: StateGraph[ScanState] = StateGraph(ScanState)
    builder.add_node("collect_files", collect)
    builder.add_node(quick_scan)
    builder.add_node(deep_scan)
    builder.add_edge(START, "collect_files")
    builder.add_edge(quick_scan.__name__, END)
    builder.add_edge(deep_scan.__name__, END)
    return builder


def collect_plain(state: ScanState) -> FilesUpdate:
    """Обычный узел без Command, переход задаёт условное ребро."""
    return {"files": ["app.py"]}


def route_typed(state: ScanState) -> Literal["quick_scan", "deep_scan"]:
    """Маршрут с аннотацией возврата."""
    return "quick_scan"


def route_bare(state: ScanState) -> str:
    """Тот же маршрут, но в аннотации нет Literal с именами узлов."""
    return "quick_scan"


def collect_cmd_typed(state: ScanState) -> Command[Literal["quick_scan", "deep_scan"]]:
    """Command с аннотацией возврата."""
    return Command(update={"files": ["app.py"]}, goto="quick_scan")


def collect_cmd_bare(state: ScanState) -> Command[str]:
    """Тот же Command, но в аннотации нет Literal с именами узлов."""
    return Command(update={"files": ["app.py"]}, goto="quick_scan")


# 1. Условное ребро, у функции маршрутизации есть аннотация.
typed: StateGraph[ScanState] = base(collect_plain)
typed.add_conditional_edges("collect_files", route_typed)
print("1. условное ребро с аннотацией:", edges(typed))

# 2. То же самое без аннотации и без словаря соответствия.
bare: StateGraph[ScanState] = base(collect_plain)
bare.add_conditional_edges("collect_files", route_bare)
print("2. условное ребро без аннотации:", edges(bare))

# 3. Словарь соответствия возвращает переходы на схему.
mapped: StateGraph[ScanState] = base(collect_plain)
mapped.add_conditional_edges(
    "collect_files",
    route_bare,
    {"quick_scan": "quick_scan", "deep_scan": "deep_scan"},
)
print("3. условное ребро со словарём:", edges(mapped))

# 4. Command с аннотацией и без неё.
cmd_typed: StateGraph[ScanState] = base(collect_cmd_typed)
print("4. Command с аннотацией:", edges(cmd_typed))

cmd_bare: StateGraph[ScanState] = base(collect_cmd_bare)
print("   Command без аннотации:", edges(cmd_bare))

# 5. Тот же Command без аннотации, но с destinations при регистрации узла.
named: StateGraph[ScanState] = StateGraph(ScanState)
named.add_node(
    "collect_files",
    collect_cmd_bare,
    destinations={"quick_scan": "файлов много", "deep_scan": "файлов мало"},
)
named.add_node(quick_scan)
named.add_node(deep_scan)
named.add_edge(START, "collect_files")
named.add_edge(quick_scan.__name__, END)
named.add_edge(deep_scan.__name__, END)
print("5. Command с destinations:", edges(named))
print()
print(named.compile().get_graph().draw_mermaid())


# 6. Переход на узел, которого в графе нет.
def goto_nowhere_typed(state: ScanState) -> Command[Literal["nowhere"]]:
    """Аннотация называет узел, которого в графе нет."""
    return Command(goto="nowhere")


def goto_nowhere_bare(state: ScanState) -> Command[str]:
    """То же самое, но в аннотации нет Literal."""
    return Command(goto="nowhere")


broken: StateGraph[ScanState] = StateGraph(ScanState)
broken.add_node("collect_files", goto_nowhere_typed)
broken.add_edge(START, "collect_files")
error: ValueError
try:
    broken.compile()
except ValueError as error:
    print("6. переход в никуда с аннотацией:", type(error).__name__, error)

silent: StateGraph[ScanState] = StateGraph(ScanState)
silent.add_node("collect_files", goto_nowhere_bare)
silent.add_node(quick_scan)
silent.add_edge(START, "collect_files")
silent.add_edge(quick_scan.__name__, END)
print("   переход в никуда без аннотации:", silent.compile().invoke({"files": []}))

# Вывод:
# 1. условное ребро с аннотацией: ['__start__ -> collect_files', 'collect_files -> deep_scan (условное)', 'collect_files -> quick_scan (условное)', 'deep_scan -> __end__', 'quick_scan -> __end__']
# 2. условное ребро без аннотации: ['__start__ -> collect_files', 'collect_files -> __end__']
# 3. условное ребро со словарём: ['__start__ -> collect_files', 'collect_files -> deep_scan (условное)', 'collect_files -> quick_scan (условное)', 'deep_scan -> __end__', 'quick_scan -> __end__']
# 4. Command с аннотацией: ['__start__ -> collect_files', 'collect_files -> deep_scan (условное)', 'collect_files -> quick_scan (условное)', 'deep_scan -> __end__', 'quick_scan -> __end__']
#    Command без аннотации: ['__start__ -> collect_files', 'collect_files -> __end__']
# 5. Command с destinations: ['__start__ -> collect_files', 'collect_files -> deep_scan (условное)', 'collect_files -> quick_scan (условное)', 'deep_scan -> __end__', 'quick_scan -> __end__']
#
# ---
# config:
#   flowchart:
#     curve: linear
# ---
# graph TD;
#   __start__([<p>__start__</p>]):::first
#   collect_files(collect_files)
#   quick_scan(quick_scan)
#   deep_scan(deep_scan)
#   __end__([<p>__end__</p>]):::last
#   __start__ --> collect_files;
#   collect_files -. &nbsp;файлов мало&nbsp; .-> deep_scan;
#   collect_files -. &nbsp;файлов много&nbsp; .-> quick_scan;
#   deep_scan --> __end__;
#   quick_scan --> __end__;
#   classDef default fill:#f2f0ff,line-height:1.2
#   classDef first fill-opacity:0
#   classDef last fill:#bfb6fc
#
# 6. переход в никуда с аннотацией: ValueError Found edge ending at unknown node `nowhere`
#    переход в никуда без аннотации: {'files': []}
#
# В пункте 6 без аннотации LangGraph пишет в журнал (stderr, модуль logging):
# Task collect_files with path ('__pregel_pull', 'collect_files') wrote to
# unknown channel branch:to:nowhere, ignoring it.
