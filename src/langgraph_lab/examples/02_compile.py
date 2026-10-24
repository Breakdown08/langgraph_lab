"""Пример 2 урока 1: что compile проверяет и чего не проверяет.

Четыре сборки одного графа: запуск без компиляции, граф без входа, ребро в
несуществующий узел и узел, к которому не ведёт ни одного ребра. Первые три
падают на месте, четвёртая компилируется и запускается.
"""

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from typing_extensions import TypedDict


class State(TypedDict):
    steps: list[str]


def step_a(state: State) -> dict[str, list[str]]:
    return {"steps": state["steps"] + ["a"]}


def step_b(state: State) -> dict[str, list[str]]:
    return {"steps": state["steps"] + ["b"]}


def fresh() -> StateGraph[State]:
    """Возвращает сборщик с двумя узлами и без единого ребра."""
    builder: StateGraph[State] = StateGraph(State)
    builder.add_node("step_a", step_a)
    builder.add_node("step_b", step_b)
    return builder


# 1. Запуск без компиляции.
builder: StateGraph[State] = fresh()
builder.add_edge(START, "step_a")
builder.add_edge("step_a", END)
try:
    # Ошибка здесь и есть урок: у сборщика нет invoke, проверка типов это видит.
    builder.invoke({"steps": []})  # type: ignore[attr-defined]
except AttributeError as error:
    print("1. без компиляции:", error)

# 2. Ни одного ребра из START.
builder = fresh()
builder.add_edge("step_a", END)
try:
    builder.compile()
except ValueError as error:
    print("2. без входа:", error)

# 3. Ребро ведёт в узел, которого в графе нет.
builder = fresh()
builder.add_edge(START, "step_a")
builder.add_edge("step_a", "step_c")
try:
    builder.compile()
except ValueError as error:
    print("3. чужое имя:", error)

# 4. Узел step_b добавлен, рёбер к нему нет.
builder = fresh()
builder.add_edge(START, "step_a")
builder.add_edge("step_a", END)
graph: CompiledStateGraph[State] = builder.compile()
print("4. узел без рёбер, результат:", graph.invoke({"steps": []}))
print("   узлы собранного графа:", sorted(graph.get_graph().nodes))

# Вывод:
# 1. без компиляции: 'StateGraph' object has no attribute 'invoke'
# 2. без входа: Graph must have an entrypoint: add at least one edge from START to another node
# 3. чужое имя: Found edge ending at unknown node `step_c`
# 4. узел без рёбер, результат: {'steps': ['a']}
#    узлы собранного графа: ['__end__', '__start__', 'step_a', 'step_b']
