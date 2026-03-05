# SPDX-License-Identifier: Apache-2.0
"""CompetitionLedger — append-only Darwinian competition event log. ADAAD-11 Track B."""
from __future__ import annotations
import hashlib,json,time
from dataclasses import dataclass
from pathlib import Path
from typing import Any,Dict,List,Optional,Sequence

EVENT_ARBITRATION="budget_arbitration.v1"
EVENT_STARVATION="agent_starvation.v1"
EVENT_EVICTION="agent_eviction.v1"

@dataclass(frozen=True)
class AgentAllocationDelta:
    agent_id:str; previous_share:float; new_share:float; delta:float; outcome:str

@dataclass(frozen=True)
class CompetitionEvent:
    epoch_id:str; occurred_at:float; temperature:float; market_scalar:float
    total_share_sum:float; agent_deltas:List[AgentAllocationDelta]
    starved_agents:List[str]; evicted_agents:List[str]
    lineage_digest:str; fitness_inputs:Dict[str,float]
    @staticmethod
    def compute_digest(epoch_id:str,occurred_at:float,n:int)->str:
        p=json.dumps({"epoch_id":epoch_id,"occurred_at":occurred_at,"n":n},sort_keys=True)
        return "sha256:"+hashlib.sha256(p.encode()).hexdigest()

class CompetitionLedger:
    """Append-only journal; in-memory or JSONL file-backed."""
    def __init__(self,ledger_path:Optional[Path]=None):
        self._events:List[CompetitionEvent]=[]
        self._path=ledger_path
        if ledger_path: ledger_path.parent.mkdir(parents=True,exist_ok=True); ledger_path.touch() if not ledger_path.exists() else None
    def record(self,*,epoch_id:str,temperature:float,market_scalar:float,total_share_sum:float,
               agent_deltas:Sequence[AgentAllocationDelta],starved_agents:Sequence[str],
               evicted_agents:Sequence[str],fitness_inputs:Dict[str,float])->CompetitionEvent:
        now=time.time()
        ev=CompetitionEvent(
            epoch_id=epoch_id,occurred_at=now,temperature=temperature,market_scalar=market_scalar,
            total_share_sum=total_share_sum,agent_deltas=list(agent_deltas),
            starved_agents=list(starved_agents),evicted_agents=list(evicted_agents),
            lineage_digest=CompetitionEvent.compute_digest(epoch_id,now,len(agent_deltas)),
            fitness_inputs=dict(fitness_inputs),
        )
        self._events.append(ev)
        if self._path:
            with open(self._path,"a",encoding="utf-8") as f:
                f.write(json.dumps({"epoch_id":ev.epoch_id,"occurred_at":ev.occurred_at,"lineage_digest":ev.lineage_digest,"evicted":ev.evicted_agents})+"\n")
        return ev
    @property
    def events(self)->List[CompetitionEvent]: return list(self._events)
    def events_for_epoch(self,epoch_id:str)->List[CompetitionEvent]: return [e for e in self._events if e.epoch_id==epoch_id]
    def last_event(self)->Optional[CompetitionEvent]: return self._events[-1] if self._events else None
    def eviction_history(self)->List[Dict[str,Any]]:
        return [{"epoch_id":e.epoch_id,"agent_id":a,"occurred_at":e.occurred_at,"lineage_digest":e.lineage_digest}
                for e in self._events for a in e.evicted_agents]
    def export_audit(self)->List[Dict[str,Any]]:
        return [{"epoch_id":e.epoch_id,"occurred_at":e.occurred_at,"temperature":e.temperature,
                 "market_scalar":e.market_scalar,"total_share_sum":e.total_share_sum,
                 "starved_agents":e.starved_agents,"evicted_agents":e.evicted_agents,
                 "lineage_digest":e.lineage_digest,"fitness_inputs":e.fitness_inputs,
                 "agent_deltas":[{"agent_id":d.agent_id,"previous_share":d.previous_share,"new_share":d.new_share,"delta":d.delta,"outcome":d.outcome} for d in e.agent_deltas]}
                for e in self._events]
__all__=["CompetitionLedger","CompetitionEvent","AgentAllocationDelta"]
