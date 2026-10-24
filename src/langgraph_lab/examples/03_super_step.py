"""Пример 3 урока 1: один шаг графа против двух.

Четыре узла и две схемы связи. В последовательной схеме счёт строк и разбор
импортов стоят друг за другом, в параллельной, рядом. В режиме values поток
отдаёт снимок состояния на входе и после каждого шага, поэтому снимков на один
больше, чем шагов.
"""

from pathlib import Path
from typing import NotRequired

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import StreamPart
from typing_extensions import TypedDict

REPO: Path = Path(__file__).parent / "mini_repo"


# На входе есть только root; остальные ключи дописывают узлы по ходу запуска.
class RepoState(TypedDict):
    root: str
    files: NotRequired[list[str]]
    total_lines: NotRequired[int]
    imports: NotRequired[list[str]]
    card: NotRequired[str]


def collect_files(state: RepoState) -> dict[str, list[str]]:
    names: list[str] = sorted(path.name for path in Path(state["root"]).glob("*.py"))
    return {"files": names}


def count_lines(state: RepoState) -> dict[str, int]:
    root: Path = Path(state["root"])
    total: int = 0
    name: str
    for name in state["files"]:
        total += len((root / name).read_text(encoding="utf-8").splitlines())
    return {"total_lines": total}


def collect_imports(state: RepoState) -> dict[str, list[str]]:
    root: Path = Path(state["root"])
    found: set[str] = set()
    name: str
    line: str
    for name in state["files"]:
        for line in (root / name).read_text(encoding="utf-8").splitlines():
            if line.startswith("from ") or line.startswith("import "):
                found.add(line.split()[1])
    return {"imports": sorted(found)}


def make_card(state: RepoState) -> dict[str, str]:
    card: str = (
        f"файлов {len(state['files'])}, "
        f"строк {state['total_lines']}, "
        f"импортов {len(state['imports'])}"
    )
    return {"card": card}


def sequential() -> StateGraph[RepoState]:
    """Четыре узла цепочкой: каждый ждёт предыдущего."""
    builder: StateGraph[RepoState] = StateGraph(RepoState)
    builder.add_node("collect_files", collect_files)
    builder.add_node("count_lines", count_lines)
    builder.add_node("collect_imports", collect_imports)
    builder.add_node("make_card", make_card)
    builder.add_edge(START, "collect_files")
    builder.add_edge("collect_files", "count_lines")
    builder.add_edge("count_lines", "collect_imports")
    builder.add_edge("collect_imports", "make_card")
    builder.add_edge("make_card", END)
    return builder


def parallel() -> StateGraph[RepoState]:
    """Те же узлы, но счёт строк и разбор импортов стоят рядом."""
    builder: StateGraph[RepoState] = StateGraph(RepoState)
    builder.add_node("collect_files", collect_files)
    builder.add_node("count_lines", count_lines)
    builder.add_node("collect_imports", collect_imports)
    builder.add_node("make_card", make_card)
    builder.add_edge(START, "collect_files")
    builder.add_edge("collect_files", "count_lines")
    builder.add_edge("collect_files", "collect_imports")
    builder.add_edge("count_lines", "make_card")
    builder.add_edge("collect_imports", "make_card")
    builder.add_edge("make_card", END)
    return builder


def run(title: str, builder: StateGraph[RepoState]) -> None:
    graph: CompiledStateGraph[RepoState] = builder.compile()
    print(title)
    number: int = 0
    chunk: StreamPart[RepoState, RepoState]
    for chunk in graph.stream({"root": str(REPO)}, stream_mode="values", version="v2"):
        # Режим один, values; проверка сужает тип снимка для проверки типов.
        if chunk["type"] != "values":
            continue
        number += 1
        filled: list[str] = sorted(key for key in chunk["data"] if key != "root")
        print(f"  снимок {number}: заполнены {filled}")
    print(f"  снимков всего: {number}")


run("ПОСЛЕДОВАТЕЛЬНАЯ СХЕМА", sequential())
print()
run("ПАРАЛЛЕЛЬНАЯ СХЕМА", parallel())

# Вывод:
# ПОСЛЕДОВАТЕЛЬНАЯ СХЕМА
#   снимок 1: заполнены []
#   снимок 2: заполнены ['files']
#   снимок 3: заполнены ['files', 'total_lines']
#   снимок 4: заполнены ['files', 'imports', 'total_lines']
#   снимок 5: заполнены ['card', 'files', 'imports', 'total_lines']
#   снимков всего: 5
#
# ПАРАЛЛЕЛЬНАЯ СХЕМА
#   снимок 1: заполнены []
#   снимок 2: заполнены ['files']
#   снимок 3: заполнены ['files', 'imports', 'total_lines']
#   снимок 4: заполнены ['card', 'files', 'imports', 'total_lines']
#   снимков всего: 4
