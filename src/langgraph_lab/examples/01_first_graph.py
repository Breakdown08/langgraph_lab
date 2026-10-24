"""Пример 1 урока 1: первый StateGraph из двух узлов.

Граф обходит стенд mini_repo, который лежит рядом с этим файлом: первый узел
собирает имена файлов, второй считает в них строки. Схема состояния задана TypedDict,
узел возвращает правку состояния словарём.
"""

from pathlib import Path
from typing import Any, NotRequired

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from typing_extensions import TypedDict

REPO: Path = Path(__file__).parent / "mini_repo"


# На входе есть только root; остальные ключи дописывают узлы по ходу запуска.
class RepoState(TypedDict):
    root: str
    files: NotRequired[list[str]]
    total_lines: NotRequired[int]


def collect_files(state: RepoState) -> dict[str, list[str]]:
    """Собирает имена файлов Python в папке стенда."""
    names: list[str] = sorted(path.name for path in Path(state["root"]).glob("*.py"))
    return {"files": names}


def count_lines(state: RepoState) -> dict[str, int]:
    """Считает строки во всех собранных файлах."""
    root: Path = Path(state["root"])
    total: int = 0
    name: str
    for name in state["files"]:
        total += len((root / name).read_text(encoding="utf-8").splitlines())
    return {"total_lines": total}


builder: StateGraph[RepoState] = StateGraph(RepoState)
builder.add_node("collect_files", collect_files)
builder.add_node("count_lines", count_lines)
builder.add_edge(START, "collect_files")
builder.add_edge("collect_files", "count_lines")
builder.add_edge("count_lines", END)

graph: CompiledStateGraph[RepoState] = builder.compile()

result: dict[str, Any] = graph.invoke({"root": str(REPO)})

print("ТИП СОБРАННОГО ГРАФА:", type(graph).__name__)
print("ФАЙЛЫ:", result["files"])
print("СТРОК ВСЕГО:", result["total_lines"])
print("КЛЮЧИ СОСТОЯНИЯ НА ВЫХОДЕ:", sorted(result))

# Вывод:
# ТИП СОБРАННОГО ГРАФА: CompiledStateGraph
# ФАЙЛЫ: ['app.py', 'config.py', 'db.py', 'utils.py']
# СТРОК ВСЕГО: 44
# КЛЮЧИ СОСТОЯНИЯ НА ВЫХОДЕ: ['files', 'root', 'total_lines']
