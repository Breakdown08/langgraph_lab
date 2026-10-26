"""Пример 5 урока 4: кеш узла и его ключ.

Узел разбора помечен CachePolicy, граф скомпилирован с InMemoryCache. Первый
вариант узла принимает узкую схему входа (корень и текущий файл), второй читает
всё состояние целиком. Три запуска подряд показывают, когда кеш срабатывает, а
когда ключ расходится и узел выполняется заново.
"""

import operator
from pathlib import Path
from typing import Annotated, Any, Literal, NotRequired, Protocol

from langgraph.cache.memory import InMemoryCache
from langgraph.graph import START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import CachePolicy
from typing_extensions import TypedDict

REPO: Path = Path(__file__).parent / "mini_repo"
CALLS: list[str] = []


class WalkState(TypedDict):
    root: str
    queue: list[str]
    current: str
    findings: Annotated[list[str], operator.add]


class ScanIn(TypedDict):
    root: str
    current: str


class QueueUpdate(TypedDict):
    queue: list[str]
    current: str


class PickUpdate(TypedDict):
    current: str
    queue: NotRequired[list[str]]


class FindingsUpdate(TypedDict):
    findings: list[str]


# Узел разбора приходит в build аргументом. Схема входа у вариантов разная,
# но WalkState содержит все поля ScanIn, поэтому scan_narrow тоже принимает
# WalkState и подходит под протокол.
class Scanner(Protocol):
    def __call__(self, state: WalkState) -> FindingsUpdate: ...


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


def scan_narrow(state: ScanIn) -> FindingsUpdate:
    """Считает строки. Из состояния получает только корень и текущий файл."""
    CALLS.append(state["current"])
    path: Path = Path(state["root"]) / state["current"]
    lines: int = len(path.read_text(encoding="utf-8").splitlines())
    return {"findings": [f"{state['current']}: строк {lines}"]}


def scan_wide(state: WalkState) -> FindingsUpdate:
    """Тот же разбор, но на входе всё состояние, включая накопленные находки."""
    CALLS.append(state["current"])
    path: Path = Path(state["root"]) / state["current"]
    lines: int = len(path.read_text(encoding="utf-8").splitlines())
    return {"findings": [f"{state['current']}: строк {lines}"]}


def route_next(state: WalkState) -> Literal["scan_file", "__end__"]:
    """Выход по пустой очереди."""
    if not state["current"]:
        return "__end__"
    return "scan_file"


# Оба варианта разбора встают в граф под одним именем scan_file.
def build(scanner: Scanner) -> CompiledStateGraph[WalkState]:
    """Собирает обход с кешируемым узлом разбора и своим кешем в памяти."""
    builder: StateGraph[WalkState] = StateGraph(WalkState)
    builder.add_node(collect_files)
    builder.add_node(pick_file)
    builder.add_node("scan_file", scanner, cache_policy=CachePolicy(ttl=60))
    builder.add_edge(START, collect_files.__name__)
    builder.add_edge(collect_files.__name__, pick_file.__name__)
    builder.add_conditional_edges(pick_file.__name__, route_next)
    builder.add_edge("scan_file", pick_file.__name__)
    return builder.compile(cache=InMemoryCache())


def run(graph: CompiledStateGraph[WalkState], note: str) -> None:
    """Запускает обход и считает, сколько разборов пришло из кеша."""
    CALLS.clear()
    cached: int = 0
    start: WalkState = {"root": str(REPO), "queue": [], "current": "", "findings": []}
    if note:
        start["findings"] = [note]
    event: dict[str, Any]
    for event in graph.stream(start, stream_mode="updates"):
        if event.get("__metadata__", {}).get("cached"):
            cached += 1
    print(f"   из кеша {cached}, выполнений тела узла {len(CALLS)}")


PASSES: tuple[tuple[str, str], ...] = (
    ("первый запуск", ""),
    ("тот же вход", ""),
    ("лишняя строка на входе", "начато вручную"),
)

narrow: CompiledStateGraph[WalkState] = build(scan_narrow)
wide: CompiledStateGraph[WalkState] = build(scan_wide)

label: str
note: str
print("1. узкая схема входа:")
for label, note in PASSES:
    print(f"   {label}:")
    run(narrow, note)
print("2. на входе всё состояние:")
for label, note in PASSES:
    print(f"   {label}:")
    run(wide, note)

# 3. Пометка о кеше приходит только в режиме updates.
print("3. где видна пометка:")
clean: WalkState = {"root": str(REPO), "queue": [], "current": "", "findings": []}
events: list[dict[str, Any]] = list(narrow.stream(clean, stream_mode="updates"))
print("   updates, третье событие:", events[2])
print("   invoke, ключи итога:", sorted(narrow.invoke(clean)))

# Вывод:
# 1. узкая схема входа:
#    первый запуск:
#    из кеша 0, выполнений тела узла 4
#    тот же вход:
#    из кеша 4, выполнений тела узла 0
#    лишняя строка на входе:
#    из кеша 4, выполнений тела узла 0
# 2. на входе всё состояние:
#    первый запуск:
#    из кеша 0, выполнений тела узла 4
#    тот же вход:
#    из кеша 4, выполнений тела узла 0
#    лишняя строка на входе:
#    из кеша 0, выполнений тела узла 4
# 3. где видна пометка:
#    updates, третье событие: {'scan_file': {'findings': ['app.py: строк 13']}, '__metadata__': {'cached': True}}
#    invoke, ключи итога: ['current', 'findings', 'queue', 'root']
