from langchain.chat_models import BaseChatModel

from langgraph_lab.course_model import build_model
from langgraph_lab.repo_send import run_all


def main() -> None:
    model: BaseChatModel = build_model()
    print(f"model {type(model).__name__} is ready for work...")
    print()
    run_all()


if __name__ == "__main__":
    main()
