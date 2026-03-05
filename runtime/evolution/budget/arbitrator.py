# SPDX-License-Identifier: Apache-2.0
"""BudgetArbitrator — Darwinian Softmax fitness-weighted reallocation. ADAAD-11 Track B."""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from runtime.evolution.budget.pool import AgentBudgetPool

@dataclass(frozen=True)
class ArbitrationResult:
    epoch_id: str; new_shares: Dict[str,float]; evicted_agents: List[str]
    starved_agents: List[str]; market_scalar: float; temperature: float
    fitness_inputs: Dict[str,float]; total_share_sum: float

class BudgetArbitrator:
    """Fitness-weighted Softmax budget arbitrator with starvation + eviction.
    
    Authority invariant: writes to AgentBudgetPool only; never approves mutations.
    """
    def __init__(self,*,pool:AgentBudgetPool,temperature:float=1.0,
                 starvation_threshold:float=0.02,eviction_starvation_count:int=3):
        self._pool=pool; self._temperature=max(0.01,temperature)
        self._starvation_threshold=starvation_threshold
        self._eviction_count=eviction_starvation_count
        self._starvation_counts:Dict[str,int]={}

    def arbitrate(self,*,fitness_scores:Dict[str,float],epoch_id:str,
                  market_pressure:float=1.0)->ArbitrationResult:
        market_scalar=max(0.1,min(3.0,float(market_pressure)))
        # Softmax over fitness scores
        agents=sorted(fitness_scores.keys())
        scores=[fitness_scores[a] for a in agents]
        tau=self._temperature
        max_s=max(scores) if scores else 0.0
        exps=[math.exp((s-max_s)/tau) for s in scores]
        total_exp=sum(exps) or 1.0
        softmax={a:exps[i]/total_exp for i,a in enumerate(agents)}
        # Apply market scalar (clamp total to 1.0)
        scaled={a:min(1.0,v*market_scalar) for a,v in softmax.items()}
        total=sum(scaled.values()) or 1.0
        normalised={a:v/total for a,v in scaled.items()}
        # Starvation detection
        starved=[a for a,s in normalised.items() if s<self._starvation_threshold]
        for a in starved: self._starvation_counts[a]=self._starvation_counts.get(a,0)+1
        for a in list(self._starvation_counts):
            if a not in starved: self._starvation_counts[a]=0
        evicted=[a for a in starved if self._starvation_counts.get(a,0)>=self._eviction_count]
        # Zero out evicted
        final={a:(0.0 if a in evicted else v) for a,v in normalised.items()}
        # Renormalise
        total2=sum(final.values()) or 1.0
        final={a:v/total2 for a,v in final.items() if v>0}
        total_sum=sum(final.values())
        self._pool.apply_reallocation(
            {**final,**{a:0.0 for a in evicted}},epoch_id=epoch_id,reason="darwinian_reallocation"
        )
        return ArbitrationResult(
            epoch_id=epoch_id,new_shares=final,evicted_agents=evicted,
            starved_agents=starved,market_scalar=market_scalar,temperature=tau,
            fitness_inputs=dict(fitness_scores),total_share_sum=total_sum,
        )
__all__=["BudgetArbitrator","ArbitrationResult"]
