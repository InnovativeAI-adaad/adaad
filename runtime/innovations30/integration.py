# SPDX-License-Identifier: Apache-2.0
"""Integration layer — wires all 30 innovations into a single pipeline.

Usage:
    from runtime.innovations30.integration import InnovationsPipeline
    pipeline = InnovationsPipeline()
    result = pipeline.evaluate_mutation(mutation_id, intent, diff, changed_files, ...)
"""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

@dataclass
class InnovationEvalResult:
    mutation_id: str
    # Constitutional
    invariant_discoveries: list[str] = field(default_factory=list)
    constitutional_tensions: list[str] = field(default_factory=list)
    rule_promotion_recommendations: list[dict] = field(default_factory=list)
    intent_realization_score: float = 1.0
    # Fitness
    temporal_regret_registered: bool = False
    counterfactual_adjusted_score: float = 0.0
    red_team_verdict: str = "PASS"
    aesthetic_score: float = 0.5
    # Safety
    self_aware_passed: bool = True
    regulatory_passed: bool = True
    semver_honored: bool = True
    blast_radius_tier: str = "low"
    # Governance
    jury_verdict: str | None = None
    curiosity_active: bool = False
    curiosity_inverted_fitness: float | None = None
    # Aggregated
    overall_innovations_score: float = 1.0
    blocking_violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class InnovationsPipeline:
    """Runs all applicable innovations for a given mutation proposal."""

    def __init__(self, data_dir: Path = Path("data"),
                 hardware_profile=None,
                 dry_run: bool = False):
        self.data_dir = Path(data_dir)
        self.dry_run = dry_run

        # Lazy-init all 30 components
        self._components: dict[str, Any] = {}
        self._hardware_profile = hardware_profile
        self._initialized = False

    def _init(self) -> None:
        if self._initialized:
            return
        d = self.data_dir

        from runtime.innovations30.invariant_discovery import InvariantDiscoveryEngine
        from runtime.innovations30.constitutional_tension import ConstitutionalTensionResolver
        from runtime.innovations30.graduated_invariants import GraduatedInvariantPromoter
        from runtime.innovations30.intent_preservation import IntentPreservationVerifier
        from runtime.innovations30.temporal_regret import TemporalRegretScorer
        from runtime.innovations30.counterfactual_fitness import CounterfactualFitnessSimulator
        from runtime.innovations30.epistemic_decay import EpistemicDecayEngine
        from runtime.innovations30.red_team_agent import RedTeamAgent
        from runtime.innovations30.aesthetic_fitness import AestheticFitnessScorer
        from runtime.innovations30.morphogenetic_memory import MorphogeneticMemory
        from runtime.innovations30.dream_state import DreamStateEngine
        from runtime.innovations30.mutation_genealogy import MutationGenealogyAnalyzer
        from runtime.innovations30.constitutional_jury import ConstitutionalJury, is_high_stakes
        from runtime.innovations30.reputation_staking import ReputationStakingLedger
        from runtime.innovations30.emergent_roles import EmergentRoleSpecializer
        from runtime.innovations30.agent_postmortem import AgentPostMortemSystem
        from runtime.innovations30.temporal_governance import TemporalGovernanceEngine
        from runtime.innovations30.governance_archaeology import GovernanceArchaeologist
        from runtime.innovations30.constitutional_stress_test import ConstitutionalStressTester
        from runtime.innovations30.governance_bankruptcy import GovernanceBankruptcyProtocol
        from runtime.innovations30.market_fitness import MarketConditionedFitness
        from runtime.innovations30.regulatory_compliance import RegulatoryComplianceEngine
        from runtime.innovations30.semantic_version_enforcer import SemanticVersionEnforcer
        from runtime.innovations30.hardware_adaptive_fitness import HardwareAdaptiveFitness
        from runtime.innovations30.constitutional_entropy_budget import ConstitutionalEntropyBudget
        from runtime.innovations30.blast_radius_model import BlastRadiusModeler
        from runtime.innovations30.self_awareness_invariant import SelfAwarenessInvariant
        from runtime.innovations30.curiosity_engine import CuriosityEngine
        from runtime.innovations30.mirror_test import MirrorTestEngine

        self._components = {
            "invariant_discovery":   InvariantDiscoveryEngine(d/"discovered_rules.jsonl"),
            "tension_resolver":      ConstitutionalTensionResolver(d/"tensions.jsonl"),
            "graduated_invariants":  GraduatedInvariantPromoter(d/"rule_calibrations.json"),
            "intent_verifier":       IntentPreservationVerifier(d/"intent_realization.jsonl"),
            "regret_scorer":         TemporalRegretScorer(d/"temporal_regret.jsonl"),
            "counterfactual":        CounterfactualFitnessSimulator(),
            "epistemic_decay":       EpistemicDecayEngine(d/"epistemic_decay_state.json"),
            "red_team":              RedTeamAgent(d/"red_team_verdicts.jsonl"),
            "aesthetic":             AestheticFitnessScorer(),
            "morpho_memory":         MorphogeneticMemory(d/"identity_ledger.jsonl"),
            "dream_state":           DreamStateEngine(d/"dream_candidates.jsonl"),
            "genealogy":             MutationGenealogyAnalyzer(d/"genealogy_vectors.jsonl"),
            "jury":                  ConstitutionalJury(d/"jury_decisions.jsonl"),
            "staking":               ReputationStakingLedger(d/"reputation_stakes.jsonl",
                                                               d/"agent_wallets.json"),
            "emergent_roles":        EmergentRoleSpecializer(d/"emergent_roles.json"),
            "postmortem":            AgentPostMortemSystem(d/"agent_postmortems.jsonl"),
            "temporal_gov":          TemporalGovernanceEngine(),
            "archaeologist":         GovernanceArchaeologist(),
            "stress_tester":         ConstitutionalStressTester(d/"stress_reports.jsonl"),
            "bankruptcy":            GovernanceBankruptcyProtocol(d/"bankruptcy_state.jsonl"),
            "market_fitness":        MarketConditionedFitness(d/"market_signals.jsonl"),
            "regulatory":            RegulatoryComplianceEngine(ledger_path=d/"compliance_violations.jsonl"),
            "semver":                SemanticVersionEnforcer(),
            "hw_fitness":            HardwareAdaptiveFitness(self._hardware_profile),
            "entropy_budget":        ConstitutionalEntropyBudget(state_path=d/"constitutional_entropy.json"),
            "blast_radius":          BlastRadiusModeler(),
            "self_aware":            SelfAwarenessInvariant(),
            "curiosity":             CuriosityEngine(d/"curiosity_state.json"),
            "mirror_test":           MirrorTestEngine(d/"mirror_test_state.jsonl"),
        }
        self._initialized = True

    def evaluate_mutation(
        self,
        mutation_id: str,
        agent_id: str,
        intent: str,
        diff_text: str,
        changed_files: list[str],
        before_source: str = "",
        after_source: str = "",
        epoch_id: str = "",
        epoch_seq: int = 0,
        declared_semver: str = "patch",
        base_fitness: float = 0.70,
        recent_fitness_deltas: list[float] | None = None,
        health_score: float = 0.75,
        blocking_rules: list[str] | None = None,
        overridden_rules: list[str] | None = None,
    ) -> InnovationEvalResult:
        self._init()
        c = self._components
        result = InnovationEvalResult(mutation_id=mutation_id)

        # ── 28: Self-Awareness Invariant (blocking) ────────────────────────
        sa = c["self_aware"].evaluate(mutation_id, diff_text, changed_files)
        result.self_aware_passed = sa.passed
        if not sa.passed:
            result.blocking_violations.extend(sa.violations)

        # ── 23: Regulatory Compliance (blocking) ──────────────────────────
        reg = c["regulatory"].evaluate(mutation_id, diff_text, intent)
        result.regulatory_passed = reg.passed
        if not reg.passed:
            for v in reg.violations:
                if v.rule_id.endswith("blocking"):
                    result.blocking_violations.append(v.violation_description)
                else:
                    result.warnings.append(v.violation_description)

        # ── 21: Governance Bankruptcy (blocking) ──────────────────────────
        allowed, reason = c["bankruptcy"].is_mutation_allowed(intent)
        if not allowed:
            result.blocking_violations.append(reason)

        # ── 8: Red Team (warning) ─────────────────────────────────────────
        red = c["red_team"].challenge(mutation_id, before_source,
                                        after_source, changed_files)
        result.red_team_verdict = red.verdict
        if red.verdict == "FAIL":
            result.warnings.extend(red.vulnerabilities[:2])

        # ── 4: Intent Preservation ────────────────────────────────────────
        if diff_text:
            intent_r = c["intent_verifier"].verify(
                mutation_id, agent_id, intent, diff_text, epoch_id)
            result.intent_realization_score = intent_r.realization_score

        # ── 24: Semantic Version Enforcer (warning) ───────────────────────
        semver_v = c["semver"].verify(mutation_id, declared_semver, diff_text)
        result.semver_honored = semver_v.contract_honored
        if not semver_v.contract_honored:
            result.warnings.extend(semver_v.violations)

        # ── 27: Blast Radius ─────────────────────────────────────────────
        blast = c["blast_radius"].model(mutation_id, changed_files)
        result.blast_radius_tier = blast.risk_tier
        if blast.risk_tier == "critical":
            result.warnings.append(f"CRITICAL blast radius: {blast.reversal_cost_estimate}")

        # ── 9: Aesthetic Fitness ──────────────────────────────────────────
        if before_source and after_source:
            aes = c["aesthetic"].score(mutation_id, before_source, after_source)
            result.aesthetic_score = aes.overall_aesthetic

        # ── 6: Counterfactual Fitness ─────────────────────────────────────
        cf = c["counterfactual"].evaluate(
            mutation_id, base_fitness, base_fitness,
            recent_fitness_deltas or [])
        result.counterfactual_adjusted_score = cf.adjusted_proposal_score

        # ── 29: Curiosity Engine ──────────────────────────────────────────
        result.curiosity_active = c["curiosity"].in_curiosity
        if result.curiosity_active:
            result.curiosity_inverted_fitness = c["curiosity"].invert_fitness(base_fitness)

        # ── 2: Constitutional Tensions ────────────────────────────────────
        if blocking_rules and overridden_rules:
            tensions = c["tension_resolver"].record_verdict(
                mutation_id, epoch_id, blocking_rules, overridden_rules)
            result.constitutional_tensions = [t.digest for t in tensions]

        # ── 10: Morphogenetic Memory ──────────────────────────────────────
        consistency = c["morpho_memory"].check_mutation_consistency(
            mutation_id, intent, diff_text)
        if not consistency.consistent:
            result.warnings.extend(consistency.violated_statements[:2])

        # ── Aggregate overall score ───────────────────────────────────────
        scores = [
            cf.adjusted_proposal_score,
            result.intent_realization_score,
            result.aesthetic_score,
            1.0 if result.self_aware_passed else 0.0,
            1.0 if result.regulatory_passed else 0.5,
        ]
        result.overall_innovations_score = round(
            sum(scores) / len(scores), 4)

        return result

    def get_component(self, name: str) -> Any:
        self._init()
        return self._components.get(name)

    def component_names(self) -> list[str]:
        return [
            "invariant_discovery", "tension_resolver", "graduated_invariants",
            "intent_verifier", "regret_scorer", "counterfactual", "epistemic_decay",
            "red_team", "aesthetic", "morpho_memory", "dream_state", "genealogy",
            "jury", "staking", "emergent_roles", "postmortem", "temporal_gov",
            "archaeologist", "stress_tester", "bankruptcy", "market_fitness",
            "regulatory", "semver", "hw_fitness", "entropy_budget", "blast_radius",
            "self_aware", "curiosity", "mirror_test",
        ]


__all__ = ["InnovationsPipeline", "InnovationEvalResult"]
