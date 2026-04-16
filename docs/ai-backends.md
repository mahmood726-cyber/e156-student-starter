# AI backends

The router (`ai/ai_call.py`) can talk to four backends. You pick by
setting environment variables; the router handles the rest.

## Local (default)

- **Ollama** running on `127.0.0.1:11434` with `gemma2:9b` and
  `qwen2.5-coder:7b` pulled.
- Setup: run `install.ps1` or `install.sh`. That's it.
- Cost: free.
- Speed: ~20-60 tokens/second on a modern laptop CPU; 100+ on GPU.
- Quality: great for prose and code; limited for long-context reviews
  (8K context window on Gemma 2).

## GitHub Models (recommended cloud fallback)

Free tier for GitHub Copilot subscribers — including the free
**Copilot for Students** program.

### Get the token

1. Apply for Copilot for Students: https://education.github.com/pack
2. Approval takes 1-14 days. You need a `.edu` email OR a student ID
   / enrollment verification letter.
3. Once approved, visit https://github.com/settings/tokens and create
   a new **fine-grained** personal access token with **"Models" scope**.
4. Add to `.env`:
   ```
   GITHUB_TOKEN=github_pat_your_token
   ```

### Quotas

GitHub Models free tier as of 2025 (subject to change — check
https://github.com/marketplace/models):

- `gpt-4o-mini`: ~150 requests/day
- `gpt-4o`: ~50/day
- `Meta-Llama-3.3-70B`: ~150/day
- `Phi-3.5-mini`: ~300/day
- `o1-mini`: ~50/day

For a student doing 5 multi-persona reviews + 20 short queries per day,
this is comfortably inside free tier.

### Which model gets used

The router uses `gpt-4o-mini` for cloud reviews — cheapest quota, good
enough for most tasks. You can override in `.env`:

```
E156_AI_PREFER=github
# ai_call.py uses GITHUB_MODEL_FOR_REVIEW in the code,
# which defaults to gpt-4o-mini. Edit the constant to switch to
# Llama 3.3 70B if you prefer open-weights.
```

## Gemini (backup cloud)

Free tier from https://aistudio.google.com/.

- Quota: ~15 requests per minute, 1M tokens per day, 1M-token context.
- Good for long-context tasks (reviewing a whole paper) where even
  GitHub Models hits context limits.
- Downside: **heavily throttled in many regions**. Expect 429 errors
  at peak times. Not reliable as a primary backend.

Set up:

1. Visit https://aistudio.google.com/ and click "Get API key".
2. Copy the key.
3. Add to `.env`:
   ```
   GEMINI_API_KEY=your_key_here
   ```

## Router priority

By default:

- **prose / stats** → Ollama Gemma
- **code** → Ollama Qwen Coder
- **review** (or prompts > 8000 chars) → GitHub Models (if `GITHUB_TOKEN`
  set), else Gemini (if `GEMINI_API_KEY` set), else Gemma (degraded).
- **quick** → Ollama Qwen 1.5B (fastest)

You can override:

```
export E156_AI_PREFER=gemma     # always use Gemma 9B
export E156_AI_PREFER=qwen      # always use Qwen Coder 7B
export E156_AI_PREFER=github    # always use GitHub Models
export E156_AI_PREFER=gemini    # always use Gemini
```

## Debug which backend ran

```
export E156_AI_DEBUG=1
python ai/ai_call.py prose "test"
# prints: [ai_call] backend=ollama model=gemma2:9b took=3240ms
```
