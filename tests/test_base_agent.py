import pytest

from adaad.agents.base_agent import BaseAgent


class CompleteAgent(BaseAgent):
    def info(self) -> dict:
        return {"name": "complete"}

    def run(self, input=None) -> dict:
        return {"input": input}

    def mutate(self, src: str) -> str:
        return src

    def score(self, output: dict) -> float:
        return 1.0


def test_base_agent_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        BaseAgent()


def test_concrete_subclass_with_complete_contract_instantiates() -> None:
    agent = CompleteAgent()
    assert agent.info() == {"name": "complete"}
