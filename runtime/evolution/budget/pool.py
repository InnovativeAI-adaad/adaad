# SPDX-License-Identifier: Apache-2.0
"""AgentBudgetPool — finite shared budget with per-agent share tracking. ADAAD-11 Track B."""
from __future__ import annotations
import time
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional

@dataclass(frozen=True)
class AgentAllocation:
    agent_id: str; share: float; absolute: float; allocated_at: float; reason: str

@dataclass(frozen=True)
class AllocationEntry:
    epoch_id: str; agent_id: str; previous_share: float; new_share: float; reason: str; allocated_at: float

class AgentBudgetPool:
    """Finite shared pool — total immutable, reallocations only, append-only ledger."""
    def __init__(self,*,total_budget:float,initial_shares:Optional[Dict[str,float]]=None,starvation_threshold:float=0.02):
        if total_budget<=0: raise ValueError("pool_total_budget_must_be_positive")
        self._total=total_budget; self._starvation_threshold=starvation_threshold
        self._shares:Dict[str,float]={}; self._allocation_log:List[AllocationEntry]=[]
        if initial_shares:
            w=sum(initial_shares.values())
            if w>0: self._shares={k:v/w for k,v in initial_shares.items()}
    @property
    def total_budget(self)->float: return self._total
    @property
    def starvation_threshold(self)->float: return self._starvation_threshold
    @property
    def shares(self)->Mapping[str,float]: return dict(self._shares)
    @property
    def allocation_log(self)->List[AllocationEntry]: return list(self._allocation_log)
    def get_allocation(self,agent_id:str)->Optional[AgentAllocation]:
        s=self._shares.get(agent_id)
        return None if s is None else AgentAllocation(agent_id,s,s*self._total,time.time(),"query")
    def is_starving(self,agent_id:str)->bool: return self._shares.get(agent_id,0.0)<self._starvation_threshold
    def agent_ids(self)->List[str]: return sorted(self._shares.keys())
    def invariant_check(self)->bool: return sum(self._shares.values())<=1.0+1e-9
    def apply_reallocation(self,new_shares:Dict[str,float],*,epoch_id:str,reason:str="reallocation")->None:
        now=time.time()
        for agent_id,ns in new_shares.items():
            prev=self._shares.get(agent_id,0.0); clamped=max(0.0,min(1.0,ns))
            if clamped==0.0: self._shares.pop(agent_id,None); r="eviction"
            else: self._shares[agent_id]=clamped; r=reason
            self._allocation_log.append(AllocationEntry(epoch_id,agent_id,prev,clamped,r,now))
__all__=["AgentBudgetPool","AgentAllocation","AllocationEntry"]
