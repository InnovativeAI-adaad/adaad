# ADR: Whale.Dic dork LLM direct browser integration

- Status: Accepted
- Date: 2026-03-18
- Decision owner: Whale.Dic integration squad

## Context
Whale.Dic integrates the dork assistant for governed developer intelligence workflows. The current approved architecture requires dork to call Anthropic directly from the browser runtime instead of creating a new ADAAD backend proxy endpoint.

## Decision
Whale.Dic uses browser `fetch('https://api.anthropic.com/v1/messages')` for dork interactions.

## Rationale
- Keeps parity with ADAADchat runtime key-injection behavior.
- Avoids new backend endpoint surface area in this integration epoch.
- Reduces additional backend latency and implementation complexity.

## Tradeoffs
### Benefits
- Lower latency path from UI to provider.
- Faster integration with no proxy deployment requirements.
- Smaller change set in governed backend code.

### Costs / risks
- Browser context carries key-availability assumptions from ADAADchat runtime.
- Backend-native centralized metering/rate controls are limited in this phase.
- Audit telemetry for LLM calls depends on optional ledger logging route (`/api/ledger/log`).

## Revisit conditions
Revisit this ADR and consider a backend proxy if any of the following becomes mandatory:
- Governance requires server-side rate limiting, request signing, or token accounting enforcement.
- Governance requires centrally auditable logging of full LLM request metadata.
- Runtime key-injection model changes or browser key exposure posture is no longer acceptable.
