"""Практика урока 1: отчёт по стенду mini_repo.

Граф собирает файлы стенда, параллельно ищет самый длинный файл и файлы без
импортов, затем собирает текстовый отчёт.
"""

from functools import cache
from pathlib import Path
from typing import Final, NotRequired

from langgraph.errors import InvalidUpdateError
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import StreamPart
from typing_extensions import TypedDict

REPO: Path = Path(__file__).parent / "examples" / "mini_repo"

# Ключи состояния. Bare Final, а не Final[str]: так mypy держит тип как
# Literal["root"] и принимает константу в state[ROOT]; с Final[str] тип
# расширяется до str и mypy отвечает literal-required. Константы нужны потому,
# что LangGraph молча выбрасывает из правки узла ключ, которого нет в схеме,
# так что опечатка в литерале теряет данные без ошибки.
ROOT: Final = "root"
FILES: Final = "files"
LARGEST_FILE: Final = "largest_file"
FILES_WITHOUT_IMPORTS: Final = "files_without_imports"
REPORT: Final = "report"


# На входе есть только root; остальные ключи дописывают узлы по ходу запуска.
class RepoState(TypedDict):
    root: Path
    files: NotRequired[list[Path]]
    largest_file: NotRequired[Path]
    files_without_imports: NotRequired[list[Path]]
    report: NotRequired[str]


def get_files(state: RepoState) -> dict[str, list[Path]]:
    # Сортировка даёт одинаковый порядок от запуска к запуску: без неё он
    # зависит от файловой системы.
    files: list[Path] = sorted(state[ROOT].glob("*.py"))
    return {FILES: files}


# Кеш по пути: get_largest_file считает строки всех файлов, а build_report
# берёт число строк победителя уже из кеша, без второго чтения файла.
@cache
def count_lines(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def get_largest_file(state: RepoState) -> dict[str, Path]:
    files: list[Path] = state[FILES]
    if not files:
        raise ValueError(f"в папке {state[ROOT]} нет .py файлов")
    # max отдаёт первый из равных, а список отсортирован: при равенстве строк
    # побеждает первый по алфавиту.
    largest: Path = max(files, key=count_lines)
    return {LARGEST_FILE: largest}


def has_imports(path: Path) -> bool:
    # lstrip ловит и импорты с отступом, например внутри функции. Ложно
    # сработает только строка многострочного текста, начатая с import или from.
    line: str
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith(("import ", "from ")):
            return True
    return False


def get_files_without_imports(state: RepoState) -> dict[str, list[Path]]:
    without_imports: list[Path] = []
    path: Path
    for path in state[FILES]:
        if not has_imports(path):
            without_imports.append(path)
    return {FILES_WITHOUT_IMPORTS: without_imports}


def build_report(state: RepoState) -> dict[str, str]:
    largest: Path = state[LARGEST_FILE]
    names: list[str] = []
    path: Path
    for path in state[FILES_WITHOUT_IMPORTS]:
        names.append(path.name)
    without_imports: str = ", ".join(names) if names else "нет"
    report: str = (
        f"файлов: {len(state[FILES])}\n"
        f"самый длинный: {largest.name} ({count_lines(largest)} строк)\n"
        f"без импортов: {without_imports}"
    )
    return {REPORT: report}


def parallel() -> StateGraph[RepoState]:
    """Средние узлы стоят рядом: оба выходят из get_files, build_report ждёт обоих."""
    builder: StateGraph[RepoState] = StateGraph(RepoState)
    builder.add_node(get_files)
    builder.add_node(get_largest_file)
    builder.add_node(get_files_without_imports)
    builder.add_node(build_report)
    builder.add_edge(START, get_files.__name__)
    builder.add_edge(get_files.__name__, get_largest_file.__name__)
    builder.add_edge(get_files.__name__, get_files_without_imports.__name__)
    builder.add_edge(
        [get_largest_file.__name__, get_files_without_imports.__name__],
        build_report.__name__,
    )
    builder.add_edge(build_report.__name__, END)
    return builder


def sequential() -> StateGraph[RepoState]:
    """Те же узлы цепочкой: средние идут друг за другом, шагов на один больше."""
    builder: StateGraph[RepoState] = StateGraph(RepoState)
    builder.add_node(get_files)
    builder.add_node(get_largest_file)
    builder.add_node(get_files_without_imports)
    builder.add_node(build_report)
    builder.add_edge(START, get_files.__name__)
    builder.add_edge(get_files.__name__, get_largest_file.__name__)
    builder.add_edge(get_largest_file.__name__, get_files_without_imports.__name__)
    builder.add_edge(get_files_without_imports.__name__, build_report.__name__)
    builder.add_edge(build_report.__name__, END)
    return builder


# Сломанные версии средних узлов: оба пишут в files. В одном шаге у ключа без
# редьюсера может быть только одна правка, поэтому запуск падает.
def get_largest_file_into_files(state: RepoState) -> dict[str, list[Path]]:
    return {FILES: [get_largest_file(state)[LARGEST_FILE]]}


def get_files_without_imports_into_files(state: RepoState) -> dict[str, list[Path]]:
    return {FILES: get_files_without_imports(state)[FILES_WITHOUT_IMPORTS]}


def conflicting() -> StateGraph[RepoState]:
    """Параллельная пара, где оба средних узла пишут в один ключ files."""
    builder: StateGraph[RepoState] = StateGraph(RepoState)
    builder.add_node(get_files)
    builder.add_node(get_largest_file_into_files)
    builder.add_node(get_files_without_imports_into_files)
    builder.add_node(build_report)
    builder.add_edge(START, get_files.__name__)
    builder.add_edge(get_files.__name__, get_largest_file_into_files.__name__)
    builder.add_edge(get_files.__name__, get_files_without_imports_into_files.__name__)
    builder.add_edge(
        [
            get_largest_file_into_files.__name__,
            get_files_without_imports_into_files.__name__,
        ],
        build_report.__name__,
    )
    builder.add_edge(build_report.__name__, END)
    return builder


def show_conflict() -> None:
    graph: CompiledStateGraph[RepoState] = conflicting().compile()
    try:
        graph.invoke({ROOT: REPO})
    except InvalidUpdateError as error:
        # Первая строка сообщения; дальше LangGraph дописывает ссылку на доку.
        print(f"InvalidUpdateError: {str(error).splitlines()[0]}")


def format_value(value: object, root: Path) -> str:
    """Файлы относительно root, список через запятую, многострочный текст с отступом.

    Сам root печатается полным путём: относительно себя он был бы просто ".".
    """
    if isinstance(value, list):
        parts: list[str] = []
        item: object
        for item in value:
            parts.append(format_value(item, root))
        return ", ".join(parts)
    if isinstance(value, Path) and value != root and value.is_relative_to(root):
        return str(value.relative_to(root))
    return str(value).replace("\n", "\n      ")


def run(title: str, builder: StateGraph[RepoState]) -> None:
    graph: CompiledStateGraph[RepoState] = builder.compile()
    print(title)
    number: int = 0
    chunk: StreamPart[RepoState, RepoState]
    for chunk in graph.stream({ROOT: REPO}, stream_mode="values", version="v2"):
        # Режим один, values; проверка сужает тип снимка для проверки типов.
        if chunk["type"] != "values":
            continue
        number += 1
        print(f"  снимок {number}:")
        key: str
        value: object
        for key, value in chunk["data"].items():
            print(f"    {key}: {format_value(value, REPO)}")
    print(f"  снимков всего: {number}")


def run_all() -> None:
    run("ПАРАЛЛЕЛЬНАЯ СХЕМА", parallel())
    print()
    run("ЦЕПОЧКА", sequential())
    print()
    print("КОНФЛИКТ: оба средних узла пишут в files")
    show_conflict()
    print()
    print("СХЕМА ПАРАЛЛЕЛЬНОГО ГРАФА")
    print(parallel().compile().get_graph().draw_mermaid())
