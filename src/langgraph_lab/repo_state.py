"""Практика урока 2: карточка стенда mini_repo из параллельных находок.

Два узла параллельно собирают находки в один ключ с редьюсером: число строк и
импорты по файлам. Третий узел строит из находок карточку, а список файлов
получает приватным ключом от узла счёта строк. Наибольшее число файлов задаёт
контекст запуска.
"""

from dataclasses import dataclass
from operator import add
from pathlib import Path
from typing import Annotated, Final, NotRequired

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime
from langgraph.types import StreamPart
from typing_extensions import TypedDict

REPO: Path = Path(__file__).parent / "examples" / "mini_repo"

# Ключи состояния. Bare Final держит тип Literal["root"], и mypy принимает
# константу в state[ROOT]; опечатка в литерале теряла бы правку молча.
ROOT: Final = "root"
FINDINGS: Final = "findings"
FILES: Final = "files"
CARD: Final = "card"


class InputState(TypedDict):
    root: str


class OutputState(TypedDict):
    card: str


# Узлы дописывают findings и card по ходу запуска, на входе есть только root.
# Редьюсер add складывает списки, поэтому оба параллельных узла пишут в
# findings за один шаг.
class OverallState(TypedDict):
    root: str
    findings: NotRequired[Annotated[list[str], add]]
    card: NotRequired[str]


# Схема узла make_card. Ключа files нет в общей схеме: каналом его делает эта
# аннотация, так он и остаётся приватным между count_lines и make_card.
class CardState(TypedDict):
    findings: list[str]
    files: list[str]


class LinesUpdate(TypedDict):
    findings: list[str]
    files: list[str]


class ImportsUpdate(TypedDict):
    findings: list[str]


@dataclass
class RunContext:
    # None не ограничивает обход: срез [:None] отдаёт весь список.
    max_files: int | None = None


def list_files(root: str, runtime: Runtime[RunContext]) -> list[Path]:
    """Отдаёт первые файлы стенда по алфавиту, число задаёт контекст запуска."""
    # Типы обещают RunContext, но без context при вызове приходит None.
    context: RunContext = runtime.context or RunContext()
    return sorted(Path(root).glob("*.py"))[: context.max_files]


def count_lines(state: OverallState, runtime: Runtime[RunContext]) -> LinesUpdate:
    """Считает строки в каждом файле и передаёт список файлов сборке карточки."""
    paths: list[Path] = list_files(state[ROOT], runtime)
    rows: list[str] = []
    names: list[str] = []
    path: Path
    for path in paths:
        lines: int = len(path.read_text(encoding="utf-8").splitlines())
        rows.append(f"{path.name}: {lines}")
        names.append(path.name)
    return {FINDINGS: ["\n".join(rows)], FILES: names}


def imported_modules(path: Path) -> list[str]:
    """Отдаёт имена модулей из строк import и from в порядке появления."""
    modules: list[str] = []
    line: str
    for line in path.read_text(encoding="utf-8").splitlines():
        words: list[str] = line.split()
        if len(words) >= 2 and words[0] in ("import", "from"):
            modules.append(words[1].rstrip(","))
    return modules


def parse_imports(state: OverallState, runtime: Runtime[RunContext]) -> ImportsUpdate:
    """Перечисляет импортированные модули в каждом файле."""
    rows: list[str] = []
    path: Path
    for path in list_files(state[ROOT], runtime):
        modules: list[str] = imported_modules(path)
        rows.append(f"{path.name}: {', '.join(modules) or 'нет'}")
    return {FINDINGS: ["\n".join(rows)]}


def make_card(state: CardState) -> OutputState:
    """Собирает карточку из списка файлов и находок обоих узлов."""
    header: str = f"файлов: {len(state[FILES])} ({', '.join(state[FILES])})"
    return {CARD: "\n\n".join([header, *state[FINDINGS]])}


builder: StateGraph[OverallState, RunContext, InputState, OutputState] = StateGraph(
    OverallState,
    context_schema=RunContext,
    input_schema=InputState,
    output_schema=OutputState,
)
builder.add_node(count_lines)
builder.add_node(parse_imports)
builder.add_node(make_card)
builder.add_edge(START, count_lines.__name__)
builder.add_edge(START, parse_imports.__name__)
# Оба узла идут в одном шаге, поэтому make_card ждёт их обоих и запускается
# один раз, со сведёнными находками.
builder.add_edge(count_lines.__name__, make_card.__name__)
builder.add_edge(parse_imports.__name__, make_card.__name__)
builder.add_edge(make_card.__name__, END)

graph: CompiledStateGraph[OverallState, RunContext, InputState, OutputState] = (
    builder.compile()
)


def run_all() -> None:
    """Запускает граф без ограничения, с max_files=2 и потоком values."""
    # Без version invoke типизирован как dict[str, Any] | Any. С version="v2"
    # он отдаёт GraphOutput, и в value лежит выход с типом OutputState.
    full: OutputState = graph.invoke({ROOT: str(REPO)}, version="v2").value
    print("1. без контекста:", full)
    print(full[CARD])
    print()

    # Типы LangGraph ждут в context объект RunContext, при запуске принимают и
    # словарь; держим словарь, как в уроке.
    short: OutputState = graph.invoke(  # type: ignore[call-overload]
        {ROOT: str(REPO)}, context={"max_files": 2}, version="v2"
    ).value
    print("2. context max_files=2:", short)
    print(short[CARD])
    print("   карточка короче:", len(short[CARD]) < len(full[CARD]))
    print()

    print("3. findings в потоке values:")
    chunk: StreamPart[OverallState, OutputState]
    for chunk in graph.stream({ROOT: str(REPO)}, stream_mode="values", version="v2"):
        # Режим один, values; проверка сужает тип снимка для проверки типов.
        if chunk["type"] != "values":
            continue
        print("  ", chunk["data"].get(FINDINGS))


if __name__ == "__main__":
    run_all()
