"""Пример 4 урока 4: узел при возврате выполняется с начала.

Цикл проверки гипотезы: узел write_note записывает заметку в отчёт, узел check
проверяет гипотезу, и сходится она только после третьей заметки. Первый вариант
узла write_note дописывает строку в конец файла, второй пишет её по ключу. Тело
узла выполняется три раза в обоих случаях, а вот отчёт получается разный.
"""

import operator
import tempfile
from pathlib import Path
from typing import Annotated, Any, Literal, Protocol, TextIO

from langgraph.graph import START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from typing_extensions import TypedDict

CALLS: list[int] = []


class CheckState(TypedDict):
    target: str
    report: str
    attempt: int
    passed: bool
    findings: Annotated[list[str], operator.add]


class AttemptUpdate(TypedDict):
    attempt: int


class CheckUpdate(TypedDict):
    passed: bool
    findings: list[str]


# Узел заметки приходит в build аргументом. Callable[[CheckState], ...] под
# типы LangGraph не подходит, нужен протокол с __call__.
class NoteWriter(Protocol):
    def __call__(self, state: CheckState) -> AttemptUpdate: ...


def write_note_append(state: CheckState) -> AttemptUpdate:
    """Дописывает заметку в конец отчёта."""
    CALLS.append(state["attempt"])
    line: str = f"- {state['target']}: гипотеза про импорты\n"
    report: TextIO
    with open(state["report"], "a", encoding="utf-8") as report:
        report.write(line)
    return {"attempt": state["attempt"] + 1}


def write_note_upsert(state: CheckState) -> AttemptUpdate:
    """Пишет ту же заметку по ключу: читает отчёт, убирает старую строку, ставит новую."""
    CALLS.append(state["attempt"])
    key: str = f"- {state['target']}:"
    path: Path = Path(state["report"])
    kept: list[str] = [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if not line.startswith(key)
    ]
    kept.append(f"{key} гипотеза про импорты, попытка {state['attempt'] + 1}")
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")
    return {"attempt": state["attempt"] + 1}


def check(state: CheckState) -> CheckUpdate:
    """Проверка гипотезы: сходится после третьей заметки."""
    passed: bool = state["attempt"] >= 4
    verdict: str = "сошлось" if passed else "не сошлось"
    return {"passed": passed, "findings": [f"попытка {state['attempt']}: {verdict}"]}


def route_check(state: CheckState) -> Literal["write_note", "__end__"]:
    """Проверка провалена, значит заметка пишется заново."""
    if state["passed"]:
        return "__end__"
    return "write_note"


# Оба варианта заметки встают в граф под одним именем write_note, поэтому
# имя узла задано строкой, а не через __name__.
def build(writer: NoteWriter) -> CompiledStateGraph[CheckState]:
    """Собирает цикл с одним из двух вариантов заметки."""
    builder: StateGraph[CheckState] = StateGraph(CheckState)
    builder.add_node("write_note", writer)
    builder.add_node(check)
    builder.add_edge(START, "write_note")
    builder.add_edge("write_note", check.__name__)
    builder.add_conditional_edges(check.__name__, route_check)
    return builder.compile()


def run(writer: NoteWriter, folder: Path, name: str) -> None:
    """Запускает цикл и печатает отчёт вместе с числом вызовов узла."""
    CALLS.clear()
    report: Path = folder / name
    report.write_text("# Отчёт обхода\n", encoding="utf-8")
    graph: CompiledStateGraph[CheckState] = build(writer)
    result: dict[str, Any] = graph.invoke(
        {
            "target": "db.py",
            "report": str(report),
            "attempt": 1,
            "passed": False,
            "findings": [],
        }
    )
    print("   тело узла выполнено раз:", len(CALLS), "с попытками", CALLS)
    print("   проверки по попыткам:", result["findings"])
    print("   отчёт:")
    line: str
    for line in report.read_text(encoding="utf-8").splitlines():
        print("     ", line)


tmp: str
with tempfile.TemporaryDirectory() as tmp:
    folder: Path = Path(tmp)
    print("1. заметка дописывается в конец:")
    run(write_note_append, folder, "append.md")
    print("2. заметка пишется по ключу:")
    run(write_note_upsert, folder, "upsert.md")

# Вывод:
# 1. заметка дописывается в конец:
#    тело узла выполнено раз: 3 с попытками [1, 2, 3]
#    проверки по попыткам: ['попытка 2: не сошлось', 'попытка 3: не сошлось', 'попытка 4: сошлось']
#    отчёт:
#       # Отчёт обхода
#       - db.py: гипотеза про импорты
#       - db.py: гипотеза про импорты
#       - db.py: гипотеза про импорты
# 2. заметка пишется по ключу:
#    тело узла выполнено раз: 3 с попытками [1, 2, 3]
#    проверки по попыткам: ['попытка 2: не сошлось', 'попытка 3: не сошлось', 'попытка 4: сошлось']
#    отчёт:
#       # Отчёт обхода
#       - db.py: гипотеза про импорты, попытка 4
