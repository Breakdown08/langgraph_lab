"""Практика урока 4: обход репозитория по кругу с мягкой остановкой.

Очередь файлов приходит на входе. Узел выбора берёт следующий файл, узел
разбора считает в нём строки и пишет строку в отчёт по ключу, ребро назад
возвращает граф к выбору. Выход на END по пустой очереди или когда до предела
шагов осталось меньше трёх. Разбор принимает узкую схему входа и кешируется.
"""

from collections.abc import Callable, Hashable, Sequence
from operator import or_
from pathlib import Path
from typing import Annotated, Any, Final, Literal, NotRequired

from langgraph.cache.memory import InMemoryCache
from langgraph.errors import GraphRecursionError
from langgraph.graph import START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.managed import RemainingSteps
from langgraph.types import CachePolicy
from typing_extensions import TypedDict

REPO: Path = Path(__file__).parent / "examples" / "mini_repo"
REPORT: Path = Path(__file__).parent / "report.md"

# Ключи состояния. Bare Final держит тип Literal["queue"], и mypy принимает
# константу в state[QUEUE].
QUEUE: Final = "queue"
CURRENT_FILE: Final = "current_file"
FINDINGS: Final = "findings"
STEPS_REMAINING: Final = "steps_remaining"
REPORT_PATH: Final = "report_path"


# На входе queue и report_path. current_file пишет pick_file, findings
# копит разбор, steps_remaining подставляет LangGraph. Редьюсер or_ сливает
# словари: повторный разбор того же файла перезапишет его ключ, а не добавит.
class WalkState(TypedDict):
    queue: list[Path]
    current_file: NotRequired[Path | None]
    findings: NotRequired[Annotated[dict[str, int], or_]]
    steps_remaining: NotRequired[RemainingSteps]
    report_path: Path


# Узкая схема входа разбора. От неё считается ключ кеша: в ней нет ничего,
# что меняется от прохода к проходу, кроме самого файла.
class ScanInput(TypedDict):
    current_file: Path | None
    report_path: Path


# На пустой очереди pick_file пишет только current_file.
class PickUpdate(TypedDict):
    current_file: Path | None
    queue: NotRequired[list[Path]]


class FindingsUpdate(TypedDict):
    findings: dict[str, int]


type Route = Callable[[WalkState], Hashable | Sequence[Hashable]]


def pick_file(state: WalkState) -> PickUpdate:
    """Берёт следующий файл из очереди и убирает его оттуда."""
    # Копия: правку состояния узел возвращает, а не делает на месте.
    queue: list[Path] = list(state[QUEUE])
    if not queue:
        return {CURRENT_FILE: None}
    return {CURRENT_FILE: queue.pop(0), QUEUE: queue}


def write_line(report: Path, key: str, line: str) -> None:
    """Пишет строку в отчёт по ключу: прежнюю строку с тем же ключом убирает."""
    kept: list[str] = []
    if report.exists():
        kept = [
            old
            for old in report.read_text(encoding="utf-8").splitlines()
            if not old.startswith(key)
        ]
    kept.append(line)
    report.write_text("\n".join(kept) + "\n", encoding="utf-8")


def scan_file(state: ScanInput) -> FindingsUpdate:
    """Считает строки в текущем файле и пишет их в отчёт по ключу."""
    path: Path | None = state[CURRENT_FILE]
    # Сюда граф приходит только с файлом: None отсекает route_next.
    if path is None:
        raise ValueError("scan_file вызван без текущего файла")
    lines: int = len(path.read_text(encoding="utf-8").splitlines())
    write_line(state[REPORT_PATH], f"- {path.name}:", f"- {path.name}: строк {lines}")
    return {FINDINGS: {path.name: lines}}


# Имена узлов в Literal — строки: константу внутри Literal mypy не пускает.
def route_next(state: WalkState) -> Literal["scan_file", "__end__"]:
    """Выход по пустой очереди или когда до предела меньше трёх шагов."""
    if state[CURRENT_FILE] is None:
        return "__end__"
    # Разбор, новый выбор и последний пустой шаг: решение идти дальше стоит
    # трёх шагов.
    if state[STEPS_REMAINING] < 3:
        return "__end__"
    return "scan_file"


def route_queue_only(state: WalkState) -> Literal["scan_file", "__end__"]:
    """Тот же выход, но без проверки остатка шагов."""
    if state[CURRENT_FILE] is None:
        return "__end__"
    return "scan_file"


def build(
    *, cached: bool = True, soft_stop: bool = True
) -> CompiledStateGraph[WalkState]:
    """Собирает обход. Флаги снимают кеш разбора и проверку остатка шагов."""
    router: Route = route_next if soft_stop else route_queue_only
    builder: StateGraph[WalkState] = StateGraph(WalkState)
    builder.add_node(pick_file)
    builder.add_node(
        scan_file,
        input_schema=ScanInput,
        cache_policy=CachePolicy(ttl=60) if cached else None,
    )
    builder.add_edge(START, pick_file.__name__)
    builder.add_conditional_edges(pick_file.__name__, router)
    builder.add_edge(scan_file.__name__, pick_file.__name__)
    return builder.compile(cache=InMemoryCache() if cached else None)


def start(queue: list[Path]) -> WalkState:
    """Входное состояние обхода: очередь с полными путями и общий отчёт."""
    return {QUEUE: queue, REPORT_PATH: REPORT}


def report_lines() -> list[str]:
    """Строки отчёта с находками, без пустых."""
    return [line for line in REPORT.read_text(encoding="utf-8").splitlines() if line]


def run_all() -> None:
    """Прогоняет пять проверок практики по порядку."""
    files: list[Path] = sorted(REPO.glob("*.py"))
    graph: CompiledStateGraph[WalkState] = build()

    print("1. стенд, предел по умолчанию:")
    full: WalkState = graph.invoke(start(files), version="v2").value
    print("   находки:", full.get(FINDINGS))
    print("   строк в отчёте:", len(report_lines()))
    print()

    print("2. recursion_limit=6:")
    short: WalkState = graph.invoke(
        start(files), {"recursion_limit": 6}, version="v2"
    ).value
    print("   находки:", short.get(FINDINGS))
    print("   осталось в очереди:", [path.name for path in short[QUEUE]])
    print()

    print("3. второй запуск того же графа, режим updates:")
    event: dict[str, Any]
    for event in graph.stream(start(files), stream_mode="updates"):
        if scan_file.__name__ in event:
            print("   ", event[scan_file.__name__], event.get("__metadata__"))
    print()

    print("4. без CachePolicy, app.py в очереди дважды:")
    twice: list[Path] = [*files, REPO / "app.py"]
    print("   очередь:", [path.name for path in twice])
    build(cached=False).invoke(start(twice))
    line: str
    for line in report_lines():
        print("   ", line)
    print()

    print("5. без проверки остатка шагов, recursion_limit=6:")
    error: GraphRecursionError
    try:
        build(soft_stop=False).invoke(start(files), {"recursion_limit": 6})
    except GraphRecursionError as error:
        print("   ", type(error).__name__)


if __name__ == "__main__":
    run_all()
