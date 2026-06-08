# LLM providers (Hong Kong and regional access)

TradeSentinel uses LangChain for facts-grounded ticker summaries. Direct calls to `api.openai.com` and `api.anthropic.com` are often unavailable in Hong Kong. Configure **one** provider profile in `.env`.

See [`.env.example`](../.env.example) for copy-paste templates.

---

## Recommended: OpenRouter

OpenRouter exposes many models (OpenAI, Anthropic, Google, etc.) through a single OpenAI-compatible API.

```env
LLM_PROVIDER=openrouter
LLM_API_KEY=sk-or-v1-...
LLM_MODEL=openai/gpt-4o-mini
```

**Cost tip:** `openai/gpt-4o-mini` or `anthropic/claude-3.5-haiku` typically stay within ~$5–15/month for personal usage.

**Verify connectivity:**

```bash
curl -s https://openrouter.ai/api/v1/models -H "Authorization: Bearer $LLM_API_KEY" | head
```

After changing `.env`:

```bash
docker compose restart api
```

---

## Ollama (local, no API key)

Run [Ollama](https://ollama.com) on your host, pull a model, then point the API container at it.

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434
LLM_MODEL=llama3.2
```

```bash
ollama pull llama3.2
ollama list
```

On Linux Docker, if `host.docker.internal` does not resolve, add to `docker-compose.yml` under `api`:

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

---

## Alibaba DashScope (Qwen)

Uses DashScope’s OpenAI-compatible endpoint (no extra LangChain package).

```env
LLM_PROVIDER=dashscope
DASHSCOPE_API_KEY=sk-...
LLM_MODEL=qwen-plus
```

Lower cost alternative: `LLM_MODEL=qwen-turbo`.

---

## Other OpenAI-compatible APIs

DeepSeek, SiliconFlow, or a self-hosted proxy:

```env
LLM_PROVIDER=openai_compatible
LLM_API_KEY=your-key
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
```

---

## Legacy: direct OpenAI / Anthropic

Only if your network can reach the official APIs:

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini
```

```env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
LLM_MODEL=claude-3-5-haiku-20241022
```

For OpenRouter, `LLM_API_KEY` is preferred; `OPENAI_API_KEY` is accepted as a fallback when `LLM_PROVIDER=openrouter`.

---

## Troubleshooting

| Symptom | Check |
|--------|--------|
| Placeholder bullets mentioning “LLM not configured” | Provider-specific keys in `.env`; `docker compose restart api` |
| OpenRouter 401 | Valid `LLM_API_KEY` at [openrouter.ai/keys](https://openrouter.ai/keys) |
| Ollama connection refused | Ollama running on host; correct `OLLAMA_BASE_URL`; model pulled |
| DashScope quota / 403 | API key and billing on Alibaba Cloud Model Studio |
| Parse errors in summary | Model ignoring JSON format; try a stronger model on OpenRouter |

Summaries are cached in Postgres (`context_cache`) for 15 minutes (`CACHE_TTL_SECONDS`).
