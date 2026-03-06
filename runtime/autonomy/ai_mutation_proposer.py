# SPDX-License-Identifier: Apache-2.0
"""
AI Mutation Proposer — connects the Claude API to the ADAAD mutation pipeline.

Architecture:
- Three specialised agent personas (Architect, Dream, Beast) each produce a
  statistically distinct set of MutationCandidate proposals via Claude.
- All HTTP calls use pure urllib.request — zero third-party dependencies,
  Android/Pydroid3 safe.
- JSON schema is injected into every system prompt; markdown fence stripping
  handles Claude's occasional formatting non-compliance.
- propose_from_all_agents() is the primary entry point for the EvolutionLoop.

Design decisions:
- Model: claude-sonnet-4-20250514  (best instruction-following + JSON fidelity)
- max_tokens: 2048  (3-6 proposals × ~300 tokens + JSON overhead)
- temperature: default (1.0) for proposal diversity
- Error propagation: urllib.error.HTTPError and json.JSONDecodeError both
  propagate to the caller (EvolutionLoop handles retry/logging).
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Dict, List, Optional

from runtime.autonomy.mutation_scaffold import MutationCandidate

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"
CLAUDE_MODEL   = "claude-sonnet-4-20250514"
MAX_TOKENS     = 2048

VALID_AGENTS     = {"architect", "dream", "beast"}
VALID_MUT_TYPES  = {"structural", "behavioral", "performance", "coverage", "experimental"}

PROPOSAL_SCHEMA = """
Return ONLY a JSON array. No markdown, no preamble. Each element must have:
{
  "mutation_id"    : "<agent>-<slug>-<unix_ts>",
  "description"    : "<one sentence>",
  "expected_gain"  : <float 0.0-1.0>,
  "risk_score"     : <float 0.0-1.0>,
  "complexity"     : <float 0.0-1.0>,
  "coverage_delta" : <float 0.0-1.0>,
  "target_files"   : ["file.py"],
  "mutation_type"  : "structural|behavioral|performance|coverage|experimental"
}
Produce exactly 3-5 proposals.
"""

AGENT_SYSTEM_PROMPTS: Dict[str, str] = {
    "architect": (
        "You are the Architect agent in the ADAAD system. Your role is to propose "
        "structural mutations: module reorganisation, abstraction improvements, "
        "dependency refactoring, and interface contract tightening. "
        "You never propose implementation-level changes — only structural shapes. "
        "Expected gains are medium (0.3-0.6). Risk is low-medium (0.1-0.4). "
        "mutation_type must always be 'structural'.\n\n" + PROPOSAL_SCHEMA
    ),
    "dream": (
        "You are the Dream agent in the ADAAD system. Your role is to propose "
        "high-novelty, exploratory mutations. You favour breadth over safety. "
        "Cross-domain patterns, experimental approaches, and alternative "
        "architectures are your domain. Your proposals are high-gain (0.5-0.9), "
        "higher-risk (0.4-0.8). mutation_type should be 'experimental' or 'behavioral'.\n\n"
        + PROPOSAL_SCHEMA
    ),
    "beast": (
        "You are the Beast agent in the ADAAD system. Your role is to propose "
        "conservative, measurable, safe mutations: micro-optimisations, dead code "
        "removal, coverage additions, and performance improvements. "
        "You never propose speculative changes. "
        "Expected gain is low-medium (0.2-0.5). Risk is very low (0.05-0.2). "
        "mutation_type should be 'performance' or 'coverage'.\n\n" + PROPOSAL_SCHEMA
    ),
}


# ---------------------------------------------------------------------------
# CodebaseContext
# ---------------------------------------------------------------------------


@dataclass
class CodebaseContext:
    """
    Snapshot of the codebase state passed to proposal agents.

    file_summaries: {relative_path: docstring_or_summary}
    recent_failures: list of failing test names from last CI run
    current_epoch_id: epoch identifier string
    explore_ratio: 0.0 = pure exploit, 1.0 = pure explore
    """
    file_summaries:    Dict[str, str]
    recent_failures:   List[str]
    current_epoch_id:  str
    explore_ratio:     float = 0.5

    def context_hash(self) -> str:
        """Stable 8-hex-char hash of the codebase state for lineage tracing."""
        payload = json.dumps(
            {
                "files": sorted(self.file_summaries.keys()),
                "failures": sorted(self.recent_failures),
                "epoch": self.current_epoch_id,
            },
            sort_keys=True,
        )
        return hashlib.md5(payload.encode()).hexdigest()[:8]

    def as_prompt_block(self) -> str:
        """Format context as a human-readable block for injection into prompts."""
        lines = [
            f"Epoch: {self.current_epoch_id}",
            f"Explore ratio: {self.explore_ratio:.2f}",
            "",
            "Files under consideration:",
        ]
        for path, summary in sorted(self.file_summaries.items()):
            lines.append(f"  {path}: {summary[:120]}")
        if self.recent_failures:
            lines.append("")
            lines.append("Recent test failures:")
            for f in self.recent_failures[:10]:
                lines.append(f"  - {f}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Internal: Claude API call
# ---------------------------------------------------------------------------


def _call_claude(
    system_prompt: str,
    user_message:  str,
    api_key:       str,
    timeout:       int = 30,
) -> str:
    """
    Single Claude API call. Returns raw response text.

    Raises:
    - urllib.error.HTTPError on non-2xx status.
    - urllib.error.URLError on network failure.
    """
    payload = json.dumps({
        "model":      CLAUDE_MODEL,
        "max_tokens": MAX_TOKENS,
        "system":     system_prompt,
        "messages":   [{"role": "user", "content": user_message}],
    }).encode()

    req = urllib.request.Request(
        CLAUDE_API_URL,
        data=payload,
        headers={
            "Content-Type":      "application/json",
            "x-api-key":         api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode())

    return body["content"][0]["text"]


# ---------------------------------------------------------------------------
# Internal: Parse proposals
# ---------------------------------------------------------------------------


def _parse_proposals(
    raw_text:    str,
    agent:       str,
    context:     CodebaseContext,
    parent_id:   Optional[str] = None,
    epoch_id:    str            = "",
) -> List[MutationCandidate]:
    """
    Parse Claude's JSON response into MutationCandidate objects.

    Robustness:
    - Strips markdown code fences (```json ... ```) if present.
    - Propagates JSONDecodeError to caller — never silently swallows.
    - Validates mutation_type against VALID_MUT_TYPES; defaults to agent
      persona's canonical type on unknown values.
    """
    text = raw_text.strip()
    # Strip markdown fences defensively
    if text.startswith("```"):
        text = "\n".join(
            line for line in text.splitlines()
            if not line.strip().startswith("```")
        ).strip()

    proposals_raw = json.loads(text)  # JSONDecodeError propagates

    context_hash = context.context_hash()
    ts = int(time.time())
    candidates: List[MutationCandidate] = []

    for p in proposals_raw:
        mut_type = p.get("mutation_type", "structural")
        if mut_type not in VALID_MUT_TYPES:
            mut_type = "structural"

        # Ensure unique, agent-scoped mutation_id
        raw_id = str(p.get("mutation_id", f"{agent}-auto-{ts}"))
        if not raw_id.startswith(agent):
            raw_id = f"{agent}-{raw_id}-{ts}"

        candidates.append(MutationCandidate(
            mutation_id=raw_id,
            expected_gain=float(p.get("expected_gain", 0.3)),
            risk_score=float(p.get("risk_score", 0.3)),
            complexity=float(p.get("complexity", 0.3)),
            coverage_delta=float(p.get("coverage_delta", 0.1)),
            parent_id=parent_id,
            generation=0,
            agent_origin=agent,
            epoch_id=epoch_id,
            source_context_hash=context_hash,
        ))

    return candidates


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def propose_mutations(
    agent:     str,
    context:   CodebaseContext,
    api_key:   str,
    parent_id: Optional[str] = None,
    timeout:   int           = 30,
) -> List[MutationCandidate]:
    """
    Call Claude as the specified agent persona and return mutation proposals.

    Args:
        agent:     One of 'architect', 'dream', 'beast'.
        context:   Current codebase snapshot.
        api_key:   Anthropic API key.
        parent_id: Optional parent mutation_id for lineage chaining.
        timeout:   HTTP timeout in seconds.

    Returns:
        List of MutationCandidate objects (>= 1).

    Raises:
        ValueError: Unknown agent name.
        urllib.error.HTTPError: API call failed.
        json.JSONDecodeError: Claude returned non-JSON output.
    """
    if agent not in VALID_AGENTS:
        raise ValueError(f"Unknown agent '{agent}'. Must be one of {VALID_AGENTS}.")

    system_prompt = AGENT_SYSTEM_PROMPTS[agent]
    user_message = (
        f"Analyse this codebase context and propose {agent}-persona mutations:\n\n"
        f"{context.as_prompt_block()}"
    )

    raw = _call_claude(system_prompt, user_message, api_key, timeout=timeout)
    return _parse_proposals(
        raw,
        agent=agent,
        context=context,
        parent_id=parent_id,
        epoch_id=context.current_epoch_id,
    )


def propose_from_all_agents(
    context: CodebaseContext,
    api_key: str,
    timeout: int = 30,
) -> Dict[str, List[MutationCandidate]]:
    """
    Call all three agents and return proposals keyed by agent name.

    Returns:
        {"architect": [...], "dream": [...], "beast": [...]}

    Individual agent failures are re-raised — EvolutionLoop handles per-agent
    retry/fallback logic.
    """
    return {
        agent: propose_mutations(agent, context, api_key, timeout=timeout)
        for agent in ("architect", "dream", "beast")
    }
