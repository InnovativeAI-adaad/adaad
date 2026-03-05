# SPDX-License-Identifier: Apache-2.0
"""Governance adapter: re-exports MutationLedger from canonical runtime module.

Implementation lives in runtime.governance.mutation_ledger.
This file is a pure re-export shim; no implementation code is permitted here.
"""

from runtime.governance.mutation_ledger import LedgerEntry, MutationLedger

__all__ = ["LedgerEntry", "MutationLedger"]
