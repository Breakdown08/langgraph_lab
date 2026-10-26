"""Пример 5 урока 3: ветки разной длины и итоговый узел.

Быстрая ветка из одного узла и подробная из двух расходятся после сбора файлов
и сходятся в карточке. Узел карточки подключён отдельными рёбрами, с
defer=True и ребром из списка узлов. Пункты 4 и 5 показывают, что меняется, когда
функция маршрутизации выбрала одну ветку.
"""

import operator
from pathlib import Path
from typing import Annotated, Any, NotRequired

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from typing_extensions import TypedDict

REPO: Path = Path(__file__).parent / "mini_repo"


# На входе root и which, остальное дописывают узлы.
class ScanState(TypedDict):
    root: str
    which: str
    files: NotRequired[list[str]]
    findings: NotRequired[Annotated[list[str], operator.add]]
    cards: NotRequired[Annotated[list[str], operator.add]]


class CollectUpdate(TypedDict):
    files: list[str]
    findings: list[str]


class FindingsUpdate(TypedDict):
    findings: list[str]


class CardsUpdate(TypedDict):
    cards: list[str]


def collect_files(state: ScanState) -> CollectUpdate:
    """Собирает имена файлов стенда."""
    names: list[str] = sorted(path.name for path in Path(state["root"]).glob("*.py"))
    return {"files": names, "findings": [f"файлов {len(names)}"]}


def count_lines(state: ScanState) -> FindingsUpdate:
    """Быстрая ветка: одна операция, один узел."""
    root: Path = Path(state["root"])
    total: int = sum(
        len((root / name).read_text(encoding="utf-8").splitlines())
        for name in state["files"]
    )
    return {"findings": [f"строк {total}"]}


def read_imports(state: ScanState) -> FindingsUpdate:
    """Подробная ветка, первый узел: собирает строки импорта."""
    root: Path = Path(state["root"])
    found: list[str] = []
    name: str
    line: str
    for name in state["files"]:
        for line in (root / name).read_text(encoding="utf-8").splitlines():
            if line.startswith("import ") or line.startswith("from "):
                found.append(line.split()[1])
    return {"findings": [f"импортов {len(found)}"]}


def rank_imports(state: ScanState) -> FindingsUpdate:
    """Подробная ветка, второй узел. Работы в нём нет, он удлиняет ветку."""
    return {"findings": ["связи разобраны"]}


def make_card(state: ScanState) -> CardsUpdate:
    """Итоговый узел: печатает полученные находки и дописывает карточку."""
    print("   make_card получил находки:", state["findings"])
    return {"cards": [f"находок {len(state['findings'])}"]}


def route(state: ScanState) -> list[str]:
    """Выбирает ветки по значению which."""
    if state["which"] == "обе":
        return [count_lines.__name__, read_imports.__name__]
    return [count_lines.__name__]


def build(
    *, defer: bool, list_edge: bool, conditional: bool
) -> CompiledStateGraph[ScanState]:
    """Собирает граф с двумя ветками.

    Флаги задают способ дождаться веток и то, выбирает ли ветки функция
    маршрутизации.
    """
    builder: StateGraph[ScanState] = StateGraph(ScanState)
    builder.add_node(collect_files)
    builder.add_node(count_lines)
    builder.add_node(read_imports)
    builder.add_node(rank_imports)
    builder.add_node(make_card, defer=defer)
    builder.add_edge(START, collect_files.__name__)
    if conditional:
        builder.add_conditional_edges(
            collect_files.__name__,
            route,
            [count_lines.__name__, read_imports.__name__],
        )
    else:
        builder.add_edge(collect_files.__name__, count_lines.__name__)
        builder.add_edge(collect_files.__name__, read_imports.__name__)
    builder.add_edge(read_imports.__name__, rank_imports.__name__)
    if list_edge:
        builder.add_edge(
            [count_lines.__name__, rank_imports.__name__], make_card.__name__
        )
    else:
        builder.add_edge(count_lines.__name__, make_card.__name__)
        builder.add_edge(rank_imports.__name__, make_card.__name__)
    builder.add_edge(make_card.__name__, END)
    return builder.compile()


start: ScanState = {"root": str(REPO), "which": "обе"}

# 1. Отдельные рёбра: карточка собирается дважды, ветки заканчиваются в разных шагах.
print("1. отдельные рёбра")
print(
    "   карточки:",
    build(defer=False, list_edge=False, conditional=False).invoke(start)["cards"],
)

# 2. defer=True: узел ждёт, пока в графе не останется незаконченных задач.
print("2. defer=True")
print(
    "   карточки:",
    build(defer=True, list_edge=False, conditional=False).invoke(start)["cards"],
)

# 3. Ребро из списка узлов: тот же итог, но без defer.
print("3. ребро из списка узлов")
print(
    "   карточки:",
    build(defer=False, list_edge=True, conditional=False).invoke(start)["cards"],
)

# 4. Функция маршрутизации выбрала одну ветку из двух.
# Ребро из списка узлов ждёт обе и не дожидается.
print("4. выбрана одна ветка, ребро из списка узлов")
one: ScanState = {"root": str(REPO), "which": "быстрая"}
result: dict[str, Any] = build(defer=False, list_edge=True, conditional=True).invoke(
    one
)
print("   карточки:", result["cards"], "| находки:", result["findings"])

# 5. То же самое, но с defer=True: карточка собирается один раз.
print("5. выбрана одна ветка, defer=True")
print(
    "   карточки:",
    build(defer=True, list_edge=False, conditional=True).invoke(one)["cards"],
)

# Вывод:
# 1. отдельные рёбра
#    make_card получил находки: ['файлов 4', 'строк 44', 'импортов 3']
#    make_card получил находки: ['файлов 4', 'строк 44', 'импортов 3', 'связи разобраны']
#    карточки: ['находок 3', 'находок 4']
# 2. defer=True
#    make_card получил находки: ['файлов 4', 'строк 44', 'импортов 3', 'связи разобраны']
#    карточки: ['находок 4']
# 3. ребро из списка узлов
#    make_card получил находки: ['файлов 4', 'строк 44', 'импортов 3', 'связи разобраны']
#    карточки: ['находок 4']
# 4. выбрана одна ветка, ребро из списка узлов
#    карточки: [] | находки: ['файлов 4', 'строк 44']
# 5. выбрана одна ветка, defer=True
#    make_card получил находки: ['файлов 4', 'строк 44']
#    карточки: ['находок 2']
