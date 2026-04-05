# LLM Provider Integration Specification

**Invariants:** `DORK-FREE-0`, `BRIDGE-FREE-0`, `DORK-STREAM-0`  
**Applies to:** All LLM-dependent ADAAD subsystems  
**Priority:** Free tier first. Paid APIs require explicit HUMAN-0 authorization.

---

## Provider Hierarchy

```
PRIMARY:   Groq Free Tier
           ├── Model: llama-3.3-70b-versatile
           ├── Rate: 14,400 req/day (600/hour)
           ├── Context: 128k tokens
           ├── Streaming: SSE
           └── Cost: $0

SECONDARY: Ollama Local
           ├── Endpoint: http://localhost:11434
           ├── Model: configurable (llama3.2, mistral, etc.)
           ├── Streaming: SSE via /api/chat
           └── Cost: $0 (local compute)

FALLBACK:  DorkEngine Deterministic
           ├── Constitutional rule engine
           ├── No network dependency
           ├── Deterministic outputs from rule application
           └── Cost: $0

FORBIDDEN: Any paid API without HUMAN-0 authorization
           ├── OpenAI API
           ├── Anthropic API (direct usage)
           └── Any API requiring payment per request
```

---

## Groq Integration

### Authentication
```python
import os
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_MODEL = "llama-3.3-70b-versatile"
```

### Streaming Request
```python
import httpx

async def groq_stream(prompt: str, system: str = "") -> AsyncGenerator[str, None]:
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system} if system else None,
            {"role": "user", "content": prompt}
        ],
        "stream": True,
        "temperature": 0.7,
        "max_tokens": 2048
    }
    payload["messages"] = [m for m in payload["messages"] if m]
    
    async with httpx.AsyncClient(timeout=60) as client:
        async with client.stream("POST", f"{GROQ_BASE_URL}/chat/completions",
                                  headers=headers, json=payload) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: ") and not line.endswith("[DONE]"):
                    chunk = json.loads(line[6:])
                    delta = chunk["choices"][0]["delta"].get("content", "")
                    if delta:
                        yield delta
```

### Rate Limit Handling
```python
GROQ_RATE_LIMIT_PER_HOUR = 600
GROQ_RATE_LIMIT_PER_DAY = 14400
GROQ_RETRY_AFTER_SECONDS = 60

async def groq_with_retry(prompt, system="", max_retries=3):
    for attempt in range(max_retries):
        try:
            return await groq_complete(prompt, system)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                wait = int(e.response.headers.get("retry-after", GROQ_RETRY_AFTER_SECONDS))
                await asyncio.sleep(wait)
                continue
            raise
    # Fall through to Ollama
    return await ollama_complete(prompt, system)
```

---

## Ollama Integration

### Health Check
```python
async def ollama_available() -> bool:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get("http://localhost:11434/api/tags")
            return r.status_code == 200
    except Exception:
        return False
```

### Chat Request
```python
async def ollama_stream(prompt: str, model: str = "llama3.2") -> AsyncGenerator[str, None]:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True
    }
    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream("POST", "http://localhost:11434/api/chat",
                                  json=payload) as response:
            async for line in response.aiter_lines():
                if line:
                    chunk = json.loads(line)
                    content = chunk.get("message", {}).get("content", "")
                    if content:
                        yield content
                    if chunk.get("done"):
                        break
```

---

## DorkEngine Deterministic Fallback

The DorkEngine is the always-available fallback. It produces deterministic outputs from ADAAD's constitutional rule engine — no LLM required.

```python
class DorkEngine:
    """Deterministic fallback — constitutional rule application."""
    
    def __init__(self, constitution_path: Path = Path("constitution.yaml")):
        self.rules = self._load_rules(constitution_path)
    
    def respond(self, prompt: str, context: dict = None) -> str:
        """Apply constitutional rules deterministically to produce a response."""
        # Match prompt against known query patterns
        for pattern, handler in self.HANDLERS.items():
            if re.search(pattern, prompt, re.IGNORECASE):
                return handler(prompt, context or {})
        return self._default_response(prompt, context or {})
    
    def _default_response(self, prompt: str, context: dict) -> str:
        """Constitutional rule-based default response."""
        active_rules = [r for r in self.rules if r.get("status") == "active"]
        return (
            f"[DorkEngine Fallback] Constitutional analysis: "
            f"{len(active_rules)} active rules. "
            f"Query requires Groq/Ollama connectivity for full analysis."
        )
```

---

## Provider Selector (Unified Interface)

```python
class LLMProvider:
    """Unified LLM provider with automatic fallback chain."""
    
    async def complete(self, prompt: str, system: str = "") -> str:
        # Try Groq
        if GROQ_API_KEY:
            try:
                return await groq_complete(prompt, system)
            except Exception as e:
                logger.warning(f"Groq failed: {e}, falling back to Ollama")
        
        # Try Ollama
        if await ollama_available():
            try:
                return await ollama_complete(prompt)
            except Exception as e:
                logger.warning(f"Ollama failed: {e}, falling back to DorkEngine")
        
        # DorkEngine (always succeeds)
        return self.dork_engine.respond(prompt)
    
    async def stream(self, prompt: str, system: str = "") -> AsyncGenerator[str, None]:
        # Same fallback logic for streaming
        ...
```

---

## ADAAD_STATE_BUS Integration

The state bus (`window.ADAAD_STATE_BUS` in UI) is the L1 shared state layer. LLM providers update the bus after every successful completion:

```javascript
// In Dork/Oracle UI:
window.ADAAD_STATE_BUS = {
  provider: 'groq',           // 'groq' | 'ollama' | 'dork_engine'
  model: 'llama-3.3-70b-versatile',
  last_response_ms: 450,
  groq_requests_today: 127,
  groq_requests_remaining: 14273,
  ollama_available: true,
  dork_engine_active: false,
  updated_at: Date.now()
};
```

Oracle chip in Aponi reads this bus to display provider status in the governance panel.

---

## Invariants

| Invariant | Description |
|---|---|
| `DORK-FREE-0` | No paid API in primary or secondary path |
| `DORK-STREAM-0` | SSE streaming required for Groq and Ollama |
| `DORK-AUDIT-0` | All LLM calls logged with provider, model, latency |
| `BRIDGE-STATE-0` | State bus updated after every provider call |
| `BRIDGE-FREE-0` | State bus relay requires no external auth |

---

*Free tier first. Zero paid dependencies. Always-available fallback.*
