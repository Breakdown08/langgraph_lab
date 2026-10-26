"""Практика урока 3: узел сбора сам раскладывает работу через Command.

Узел сбора файлов возвращает Command. Файлов нет — переход сразу в карточку.
Файлы есть — по Send в узел разбора на каждый файл и в том же goto переход в
сводку. Сводка идёт двумя узлами подряд, разбор файла одним, поэтому ветки
разной длины. Карточка ждёт их всех через defer=True и собирается один раз.
"""

from operator import add
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated, Final, Literal, NotRequired, Protocol

from langchain_core.runnables.graph import Edge
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command, Send
from typing_extensions import TypedDict

REPO: Path = Path(__file__).parent / "examples" / "mini_repo"

# Ключи состояния. Bare Final держит тип Literal["root"], и mypy принимает
# константу в state[ROOT]. ROOT общий для обеих схем, NAME только у FileState.
ROOT: Final = "root"
FILES: Final = "files"
FINDINGS: Final = "findings"
CARDS: Final = "cards"
NAME: Final = "name"


# На входе только root, остальное дописывают узлы. Редьюсер add нужен обоим
# спискам: в findings пишут копии разбора и сводка, в cards — карточка, и
# без defer=True она пишет дважды.
class ScanState(TypedDict):
    root: str
    files: NotRequired[list[str]]
    findings: NotRequired[Annotated[list[str], add]]
    cards: NotRequired[Annotated[list[str], add]]


class FileState(TypedDict):
    """Вход одной копии узла разбора: корень стенда и имя своего файла."""

    root: str
    name: str


class FindingsUpdate(TypedDict):
    findings: list[str]


class CardsUpdate(TypedDict):
    cards: list[str]


# Узел сбора приходит в build аргументом. Callable[[ScanState], ...] под типы
# LangGraph не подходит, нужен протокол с __call__.
class CollectNode(Protocol):
    __name__: str

    def __call__(self, state: ScanState) -> object: ...


def list_files(root: str) -> list[str]:
    """Отдаёт имена файлов Python в папке по алфавиту."""
    return sorted(path.name for path in Path(root).glob("*.py"))


def read_lines(root: str, name: str) -> int:
    """Считает строки в одном файле."""
    return len((Path(root) / name).read_text(encoding="utf-8").splitlines())


def scan_file(state: FileState) -> FindingsUpdate:
    """Разбирает один файл. Состояние своё: корень и имя, общего здесь нет."""
    return {FINDINGS: [f"{state[NAME]}: строк {read_lines(state[ROOT], state[NAME])}"]}


def count_files(state: ScanState) -> FindingsUpdate:
    """Сводка, первый узел: число файлов."""
    return {FINDINGS: [f"файлов {len(state[FILES])}"]}


def count_lines(state: ScanState) -> FindingsUpdate:
    """Сводка, второй узел: строки во всех файлах разом."""
    total: int = 0
    name: str
    for name in state[FILES]:
        total += read_lines(state[ROOT], name)
    return {FINDINGS: [f"строк {total}"]}


def make_card(state: ScanState) -> CardsUpdate:
    """Печатает полученные находки и дописывает карточку."""
    findings: list[str] = state.get(FINDINGS, [])
    print("   make_card получил находки:", findings)
    return {CARDS: [f"находок {len(findings)}"]}


def file_jobs(root: str, names: list[str]) -> list[Send]:
    """По одному Send в узел разбора на файл, у каждого своё состояние."""
    sends: list[Send] = []
    name: str
    for name in names:
        job: FileState = {ROOT: root, NAME: name}
        sends.append(Send(scan_file.__name__, job))
    return sends


# Имена узлов в Literal и goto — строки: константу внутри Literal mypy не
# пускает, а __name__ имеет тип str. Опечатку всё равно не пропустят: goto
# mypy сверяет с Literal, а Literal LangGraph сверяет с узлами при compile().
def collect_files(
    state: ScanState,
) -> Command[Literal["scan_file", "count_files", "make_card"]]:
    """Собирает файлы и сам раскладывает работу: разбор, сводка или карточка."""
    names: list[str] = list_files(state[ROOT])
    if not names:
        return Command(update={FILES: names}, goto="make_card")
    sends: list[Send] = file_jobs(state[ROOT], names)
    return Command(update={FILES: names}, goto=[*sends, "count_files"])


def collect_files_bare(state: ScanState) -> Command[str]:
    """Тот же сбор, но в аннотации нет Literal: схеме не из чего взять переходы.

    Вызвать collect_files нельзя: Command инвариантен, и Command[Literal[...]]
    mypy не принимает как Command[str].
    """
    names: list[str] = list_files(state[ROOT])
    if not names:
        return Command(update={FILES: names}, goto=make_card.__name__)
    sends: list[Send] = file_jobs(state[ROOT], names)
    return Command(update={FILES: names}, goto=[*sends, count_files.__name__])


def build(collect: CollectNode, *, defer: bool = True) -> CompiledStateGraph[ScanState]:
    """Собирает граф. Узел сбора и defer у карточки задаёт вызов."""
    builder: StateGraph[ScanState] = StateGraph(ScanState)
    builder.add_node(collect_files.__name__, collect)
    builder.add_node(scan_file, input_schema=FileState)
    builder.add_node(count_files)
    builder.add_node(count_lines)
    builder.add_node(make_card, defer=defer)
    builder.add_edge(START, collect_files.__name__)
    builder.add_edge(count_files.__name__, count_lines.__name__)
    # Рёбра в карточку отдельные, не списком: при пустой папке ни scan_file,
    # ни count_lines не выполнятся, и ребро из списка карточку не запустит.
    builder.add_edge(scan_file.__name__, make_card.__name__)
    builder.add_edge(count_lines.__name__, make_card.__name__)
    builder.add_edge(make_card.__name__, END)
    return builder.compile()


def collect_edges(graph: CompiledStateGraph[ScanState]) -> list[str]:
    """Отдаёт рёбра схемы, которые выходят из узла сбора."""
    lines: list[str] = []
    edge: Edge
    for edge in graph.get_graph().edges:
        if edge.source == collect_files.__name__:
            lines.append(f"{edge.source} -> {edge.target}")
    return lines


def run_all() -> None:
    """Прогоняет пять проверок практики по порядку."""
    graph: CompiledStateGraph[ScanState] = build(collect_files)

    print("1. схема графа:")
    print(graph.get_graph().draw_mermaid())

    print("2. стенд mini_repo:")
    full: ScanState = graph.invoke({ROOT: str(REPO)}, version="v2").value
    print("   находки:", full[FINDINGS])
    print("   карточки:", full[CARDS])
    print()

    print("3. папка без файлов Python:")
    empty_dir: str
    with TemporaryDirectory() as empty_dir:
        empty: ScanState = graph.invoke({ROOT: empty_dir}, version="v2").value
    print("   карточки:", empty[CARDS])
    print()

    print("4. рёбра из узла сбора:")
    print("   с аннотацией:", collect_edges(graph))
    print("   без аннотации:", collect_edges(build(collect_files_bare)))
    print()

    print("5. карточка без defer=True:")
    twice: ScanState = (
        build(collect_files, defer=False).invoke({ROOT: str(REPO)}, version="v2").value
    )
    print("   карточки:", twice[CARDS])


if __name__ == "__main__":
    run_all()
