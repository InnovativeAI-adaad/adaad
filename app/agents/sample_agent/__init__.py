# SPDX-License-Identifier: Apache-2.0
"""Compatibility shim; import from adaad.agents.sample_agent instead."""

from adaad.agents.sample_agent import *  # noqa: F401,F403
from adaad.agents.sample_agent import SampleAgent as SampleAgent  # noqa: F401


class _SampleAgentShim(SampleAgent):
    """Backward-compat bridge class visible to AST-based agent contract validators.

    Delegates all behaviour to ``adaad.agents.sample_agent.SampleAgent``.
    """

    def info(self) -> dict:
        return super().info()

    def run(self, input=None) -> dict:
        return super().run(input)

    def mutate(self, src: str) -> str:
        return super().mutate(src)

    def score(self, output: dict) -> float:
        return super().score(output)
