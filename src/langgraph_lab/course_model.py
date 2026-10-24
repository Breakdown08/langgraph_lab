"""Сборка модели для примеров курса по LangGraph.

build_model() собирает модель по переменным MODEL_NAME, MODEL_BASE_URL и
OPENAI_API_KEY из файла .env. Без MODEL_BASE_URL модель идёт напрямую к
провайдеру: для claude-* это Anthropic с ключом ANTHROPIC_API_KEY.

load_dotenv() ищет файл .env, начиная с текущей папки, и поднимается вверх.
"""

import os
from typing import Any, TypedDict

from dotenv import load_dotenv
from langchain.chat_models import BaseChatModel, init_chat_model

load_dotenv()


class GatewayKwargs(TypedDict, total=False):
    """Аргументы init_chat_model для шлюза, совместимого с OpenAI."""

    model_provider: str
    base_url: str
    api_key: str


def gateway_kwargs() -> GatewayKwargs:
    """Возвращает аргументы доступа к шлюзу, совместимому с OpenAI.

    Нужны примерам, которые вызывают init_chat_model сами.
    """
    base_url: str | None = os.getenv("MODEL_BASE_URL")

    if base_url:
        return {
            "model_provider": "openai",
            "base_url": base_url,
            "api_key": os.environ["OPENAI_API_KEY"],
        }

    return {}


def build_model(model_name: str | None = None, **kwargs: Any) -> BaseChatModel:
    """Собирает модель курса.

    model_name без значения означает модель из MODEL_NAME. Остальные именованные
    аргументы уходят в init_chat_model как есть: temperature, max_tokens и прочее.
    """
    name: str = model_name or os.environ["MODEL_NAME"]
    access: GatewayKwargs = gateway_kwargs()
    model: BaseChatModel

    if access:
        model = init_chat_model(model=name, **access, **kwargs)
    else:
        model = init_chat_model(name, **kwargs)

    return model
