from langchain.chat_models import BaseChatModel

from langgraph_lab.course_model import build_model


def main() -> None:
    model: BaseChatModel = build_model()
    print(f"model {type(model).__name__} is ready for work...")


if __name__ == "__main__":
    main()
