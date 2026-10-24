"""Пример 1 урока 2: три способа задать схему состояния.

Граф из одного узла над стендом mini_repo собран трижды: на TypedDict, на
dataclass со значением по умолчанию и на модели Pydantic с проверкой входа.
Печатается, чем три схемы отличаются при запуске.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, NotRequired, Protocol

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel, ValidationError
from typing_extensions import TypedDict

REPO: Path = Path(__file__).parent / "mini_repo"


# files дописывает узел, поэтому на входе он не обязателен. suffix оставлен
# обязательным: пункт 1 показывает, что бывает без него.
class DictState(TypedDict):
    root: str
    suffix: str
    files: NotRequired[list[str]]


def collect_dict(state: DictState) -> dict[str, list[str]]:
    """Собирает имена файлов и приписывает к ним пометку из состояния."""
    names: list[str] = sorted(path.name for path in Path(state["root"]).glob("*.py"))
    return {"files": [name + state["suffix"] for name in names]}


@dataclass
class DataState:
    root: str
    suffix: str = " [py]"
    files: list[str] = field(default_factory=list)


def collect_data(state: DataState) -> dict[str, list[str]]:
    """То же самое, но состояние приходит объектом dataclass."""
    names: list[str] = sorted(path.name for path in Path(state.root).glob("*.py"))
    return {"files": [name + state.suffix for name in names]}


class ModelState(BaseModel):
    root: str
    suffix: str = " [py]"
    files: list[str] = []


def collect_model(state: ModelState) -> dict[str, list[str]]:
    """То же самое, но состояние приходит моделью Pydantic."""
    names: list[str] = sorted(path.name for path in Path(state.root).glob("*.py"))
    return {"files": [name + state.suffix for name in names]}


class Node[S](Protocol):
    """Узел с параметром state: так его описывают типы LangGraph.

    Callable[[S], ...] сюда не подходит: его аргумент позиционный, а LangGraph
    ждёт функцию, которую можно вызвать и как node(state=...).
    """

    def __call__(self, state: S) -> dict[str, list[str]]: ...


def build[S: (DictState, DataState, ModelState)](
    schema: type[S], node: Node[S]
) -> CompiledStateGraph[S]:
    """Собирает граф из одного узла на переданной схеме состояния."""
    builder: StateGraph[S] = StateGraph(schema)
    builder.add_node("collect", node)
    builder.add_edge(START, "collect")
    builder.add_edge("collect", END)
    return builder.compile()


result: dict[str, Any]

# Пункты 3-5: типы LangGraph требуют на входе invoke объект схемы (DataState,
# ModelState), а при запуске принимают и словарь. Пример показывает именно
# словарный вход: значение по умолчанию и проверку Pydantic делает граф, а не
# конструктор схемы. Поэтому там стоит type: ignore[call-overload].

# 1. TypedDict: ключа suffix на входе нет, значения по умолчанию тоже нет.
try:
    # Намеренно неполный вход: пример показывает, что TypedDict не подставляет
    # значение и узел падает с KeyError.
    build(DictState, collect_dict).invoke({"root": str(REPO)})  # type: ignore[call-overload]
except KeyError as error:
    print("1. TypedDict без suffix:", type(error).__name__, error)

# 2. TypedDict: ключ передан явно.
result = build(DictState, collect_dict).invoke({"root": str(REPO), "suffix": " [py]"})
print("2. TypedDict с suffix:", result["files"][:2])

# 3. dataclass: тот же вход без suffix, значение берётся из схемы.
result = build(DataState, collect_data).invoke({"root": str(REPO)})  # type: ignore[call-overload]
print("3. dataclass без suffix:", result["files"][:2])
print("   тип результата:", type(result).__name__)

# 4. Pydantic: неверный тип на входе.
try:
    build(ModelState, collect_model).invoke({"root": 42})  # type: ignore[call-overload]
except ValidationError as error:
    print("4. Pydantic, неверный тип:", str(error).splitlines()[0])

# 5. Pydantic: верный вход и тип результата.
result = build(ModelState, collect_model).invoke({"root": str(REPO)})  # type: ignore[call-overload]
print("5. Pydantic, верный вход:", result["files"][:2])
print("   тип результата:", type(result).__name__)

# Вывод:
# 1. TypedDict без suffix: KeyError 'suffix'
# 2. TypedDict с suffix: ['app.py [py]', 'config.py [py]']
# 3. dataclass без suffix: ['app.py [py]', 'config.py [py]']
#    тип результата: dict
# 4. Pydantic, неверный тип: 1 validation error for ModelState
# 5. Pydantic, верный вход: ['app.py [py]', 'config.py [py]']
#    тип результата: dict
