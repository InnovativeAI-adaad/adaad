# SPDX-License-Identifier: Apache-2.0
"""I/O helpers for bounded streaming reads."""

from runtime.io.jsonl_tail import JSONLTailReadResult, read_jsonl_tail

__all__ = ["JSONLTailReadResult", "read_jsonl_tail"]
