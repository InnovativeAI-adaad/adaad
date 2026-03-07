# SPDX-License-Identifier: Apache-2.0
"""Compatibility shim; import from adaad.agents.test_subject instead."""

from adaad.agents.test_subject import *  # noqa: F401,F403
from adaad.agents.test_subject import TestSubjectAgent as TestSubjectAgent  # noqa: F401 — explicit re-export for AST validators


class _TestSubjectAgentShim(TestSubjectAgent):
    """Backward-compat bridge class visible to AST-based agent contract validators.

    Delegates all behaviour to ``adaad.agents.test_subject.TestSubjectAgent``.
    The star-import above is insufficient for static AST analysis; this class
    definition makes the contract validator's class-node scan succeed.
    """

    def info(self) -> dict:
        return super().info()

    def run(self, input=None) -> dict:
        return super().run(input)

    def mutate(self, src: str) -> str:
        return super().mutate(src)

    def score(self, output: dict) -> float:
        return super().score(output)
