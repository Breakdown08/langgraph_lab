from langchain.chat_models import BaseChatModel

from langgraph_lab.course_model import build_model


def main():
    model: BaseChatModel = build_model()
    print("model is ready for work...")


if __name__ == "__main__":
    main()
