# SPDX-License-Identifier: Apache-2.0
"""Deterministic entropy budget forecasting for pre-mutation governance."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Literal


AdvisoryLevel = Literal["clear", "warn", "block"]


@dataclass(frozen=True)
class EntropyBudgetForecaster:
    """Forecast near-term entropy pressure and return deterministic advisories."""

    warn_utilization: float = 0.85
    block_utilization: float = 1.0
    warning_horizon_mutations: int = 2

    def forecast(
        self,
        *,
        epoch_id: str,
        mutation_count: int,
        epoch_entropy_bits: int,
        per_mutation_ceiling_bits: int,
        per_epoch_ceiling_bits: int,
    ) -> Dict[str, Any]:
        normalized_epoch_id = str(epoch_id or "")
        safe_mutation_count = max(0, int(mutation_count))
        safe_epoch_entropy_bits = max(0, int(epoch_entropy_bits))
        mutation_ceiling = max(0, int(per_mutation_ceiling_bits))
        epoch_ceiling = max(0, int(per_epoch_ceiling_bits))

        if mutation_ceiling <= 0 or epoch_ceiling <= 0:
            return {
                "epoch_id": normalized_epoch_id,
                "advisory": "clear",
                "reason": "entropy_forecast_disabled",
                "mutation_count": safe_mutation_count,
                "epoch_entropy_bits": safe_epoch_entropy_bits,
                "per_mutation_ceiling_bits": mutation_ceiling,
                "per_epoch_ceiling_bits": epoch_ceiling,
                "forecast_next_mutation_bits": 0,
                "projected_epoch_entropy_bits": safe_epoch_entropy_bits,
                "remaining_epoch_entropy_bits": 0,
                "recommended_per_mutation_ceiling_bits": mutation_ceiling,
            }

        average_bits = 0
        if safe_mutation_count > 0:
            average_bits = safe_epoch_entropy_bits // safe_mutation_count
        forecast_next_mutation_bits = max(1, min(mutation_ceiling, average_bits or mutation_ceiling))
        projected_epoch_entropy_bits = safe_epoch_entropy_bits + forecast_next_mutation_bits
        remaining_epoch_entropy_bits = max(0, epoch_ceiling - safe_epoch_entropy_bits)
        utilization = safe_epoch_entropy_bits / float(epoch_ceiling)

        advisory: AdvisoryLevel = "clear"
        reason = "ok"
        if safe_epoch_entropy_bits >= epoch_ceiling or utilization >= self.block_utilization:
            advisory = "block"
            reason = "epoch_entropy_budget_exhausted"
        else:
            horizon_projection = safe_epoch_entropy_bits + (forecast_next_mutation_bits * self.warning_horizon_mutations)
            if utilization >= self.warn_utilization or horizon_projection > epoch_ceiling:
                advisory = "warn"
                reason = "epoch_entropy_pressure"

        recommended_per_mutation_ceiling_bits = max(1, min(mutation_ceiling, remaining_epoch_entropy_bits))

        return {
            "epoch_id": normalized_epoch_id,
            "advisory": advisory,
            "reason": reason,
            "mutation_count": safe_mutation_count,
            "epoch_entropy_bits": safe_epoch_entropy_bits,
            "per_mutation_ceiling_bits": mutation_ceiling,
            "per_epoch_ceiling_bits": epoch_ceiling,
            "forecast_next_mutation_bits": forecast_next_mutation_bits,
            "projected_epoch_entropy_bits": projected_epoch_entropy_bits,
            "remaining_epoch_entropy_bits": remaining_epoch_entropy_bits,
            "recommended_per_mutation_ceiling_bits": recommended_per_mutation_ceiling_bits,
        }


__all__ = ["EntropyBudgetForecaster", "AdvisoryLevel"]

