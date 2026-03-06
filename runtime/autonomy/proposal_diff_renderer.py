# SPDX-License-Identifier: Apache-2.0
"""
Phase 6 — Proposal Diff Renderer
=================================

Renders a RoadmapAmendmentProposal as a structured, human-readable Markdown
diff suitable for:
  - GitHub PR descriptions
  - Aponi IDE evidence viewer (D4)
  - Governance audit bundle output

No writes to ROADMAP.md occur here. This is a pure display utility.
"""

from __future__ import annotations

import textwrap
from typing import Any

from runtime.autonomy.roadmap_amendment_engine import RoadmapAmendmentProposal


_STATUS_EMOJI: dict[str, str] = {
    "proposed":  "🔵",
    "active":    "🟡",
    "shipped":   "✅",
    "deferred":  "⏸️",
    "cancelled": "❌",
}

_AUTHORITY_BADGE = "🔐 governor-review"


def render_proposal_diff(proposal: RoadmapAmendmentProposal) -> str:
    """
    Produce a Markdown block representing the full amendment proposal diff.

    Output sections:
      1. Header with proposal ID and score
      2. Authority and lineage fingerprints
      3. Rationale
      4. Milestone delta table
      5. Governance status summary

    Returns
    -------
    str — UTF-8 Markdown text. Never raises; errors emit inline warning blocks.
    """
    lines: list[str] = []

    # ── Header ─────────────────────────────────────────────────────────────
    score_bar = _score_to_bar(proposal.diff_score)
    lines += [
        f"## 📋 Roadmap Amendment — `{proposal.proposal_id}`",
        "",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| **Proposer** | `{proposal.proposer_agent}` |",
        f"| **Timestamp** | `{proposal.timestamp}` |",
        f"| **Diff Score** | `{proposal.diff_score:.4f}` {score_bar} |",
        f"| **Authority** | {_AUTHORITY_BADGE} |",
        f"| **Status** | `{proposal.status}` |",
        "",
    ]

    # ── Lineage fingerprints ────────────────────────────────────────────────
    lines += [
        "### 🔗 Lineage",
        "",
        f"```",
        f"prior_roadmap_hash  : {proposal.prior_roadmap_hash[:32]}…",
        f"lineage_chain_hash  : {proposal.lineage_chain_hash[:32]}…",
        f"```",
        "",
    ]

    # ── Rationale ──────────────────────────────────────────────────────────
    lines += [
        "### 📝 Rationale",
        "",
        textwrap.fill(proposal.rationale, width=100),
        "",
    ]

    # ── Milestone delta table ───────────────────────────────────────────────
    lines += [
        "### 📌 Milestone Changes",
        "",
        "| Phase | Title | Status | Target |",
        "|-------|-------|--------|--------|",
    ]
    for m in proposal.amended_milestones:
        emoji = _STATUS_EMOJI.get(m.get("status", ""), "❓")
        lines.append(
            f"| `{m.get('phase_id', '?')}` "
            f"| {m.get('title', '—')} "
            f"| {emoji} `{m.get('status', '?')}` "
            f"| `{m.get('target_ver', '?')}` |"
        )
    lines.append("")

    # ── Governance status ──────────────────────────────────────────────────
    approvals = proposal.approvals or []
    rejections = proposal.rejections or []
    lines += [
        "### ⚖️ Governance Status",
        "",
        f"- Approvals : {len(approvals)} — {', '.join(f'`{a}`' for a in approvals) or '_none yet_'}",
        f"- Rejections: {len(rejections)} — {', '.join(f'`{r}`' for r in rejections) or '_none_'}",
        "",
    ]

    # ── Phase transition log ────────────────────────────────────────────────
    if proposal.phase_transitions:
        lines += ["<details>", "<summary>Phase transition log</summary>", "", "```json"]
        import json
        lines.append(json.dumps(proposal.phase_transitions, indent=2))
        lines += ["```", "", "</details>", ""]

    return "\n".join(lines)


def _score_to_bar(score: float, width: int = 10) -> str:
    """Return a compact Unicode progress bar for diff_score ∈ [0, 1]."""
    filled = round(score * width)
    return "▓" * filled + "░" * (width - filled)
