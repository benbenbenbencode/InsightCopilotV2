from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.engine import Engine

from .agent import AskResult, ask
from .config import Settings
from .db import make_engine
from .llm import LLMClient
from .schema import SchemaInfo, load_schema


@dataclass
class Service:
    settings: Settings
    engine: Engine
    schema: SchemaInfo
    llm: LLMClient

    @classmethod
    def build(cls, settings: Settings | None = None) -> "Service":
        s = settings or Settings.from_env()
        engine = make_engine(s)
        return cls(s, engine, load_schema(engine, s), LLMClient(s))

    def ask(self, question: str) -> AskResult:
        return ask(question, self.settings, self.engine, self.schema, self.llm)
