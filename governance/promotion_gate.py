# SPDX-License-Identifier: Apache-2.0
"""Governance adapter: re-exports PromotionGate from canonical runtime module.

Implementation lives in runtime.governance.promotion_gate.
This file is a pure re-export shim; no implementation code is permitted here.
"""

from runtime.governance.promotion_gate import (
    PromotionDecision,
    PromotionPolicy,
    evaluate_promotion,
)

__all__ = ["PromotionDecision", "PromotionPolicy", "evaluate_promotion"]
