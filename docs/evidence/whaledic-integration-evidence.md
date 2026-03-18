# Whale.Dic Integration Evidence

Date: 2026-03-18

## 1) Whale.Dic page reachable at canonical route

Command:

```bash
curl -si http://127.0.0.1:8092/ui/developer/ADAADdev/whaledic.html | sed -n '1,8p'
```

Observed output:

```http
HTTP/1.1 200 OK
content-type: text/html; charset=utf-8
content-length: 17822
```

## 2) Aponi nav link to Whale.Dic present

Recorded output verification:

- `pytest -v tests/test_aponi_ui.py` output:

```text
tests/test_aponi_ui.py::test_whaledic_nav_link PASSED
```

## 3) Whale.Dic page render evidence

Recorded output verification:

- `pytest -v tests/test_server_routes.py` output:

```text
tests/test_server_routes.py::test_whaledic_static_route PASSED
```

## 4) Mock routes flagged

The following routes were verified missing in current backend and are explicitly handled as `[MOCK]` in Whale.Dic:

- `/api/governance/status`
- `/api/mutations/recent`
- `/api/replay/score`
- `/api/epoch/current`
- `/api/agents/health`
- `/api/ledger/entries`
- `/api/webhooks/recent`
- `/api/webhooks/stream`
- `/api/release/readiness`
- `/api/ledger/log`

See debt tracking: `docs/debt/whaledic-api-debt.md`.
