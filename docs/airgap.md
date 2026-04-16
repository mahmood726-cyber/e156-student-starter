# Air-gapped / low-connectivity workflows

This starter is designed to work fully offline **after the one-time
model download**. This doc covers:

1. Running day-to-day without internet
2. Installing on a machine that's never online (sneaker-net)
3. What needs internet and what doesn't

## What needs internet

| Task | Internet? | Why |
|---|---|---|
| Install Ollama + pull models (one time) | Yes | ~350 MB Ollama + ~10 GB models |
| Running Gemma for prose | **No** | All local |
| Running Qwen Coder for code | **No** | All local |
| `validate_e156.py` checker | **No** | Pure Python |
| Reading `rules/*.md` | **No** | Local markdown |
| Multi-persona review via cloud | Yes | GitHub Models / Gemini API |
| Pushing finished paper to GitHub | Yes (briefly) | For the one git push |
| Submitting to Synthēsis OJS | Yes (briefly) | Uploading the .docx |

**Bottom line:** you need internet twice — once at setup, once at submit.
Everything between is local.

## Sneaker-net install (never-online machine)

If your laptop has no internet at all, install from a USB stick:

### On an internet-connected machine (friend's, cyber café, etc.)

1. Download the Ollama portable zip: https://github.com/ollama/ollama/releases/latest/download/ollama-windows-amd64.zip (or the matching Linux binary).
2. On that internet-connected machine, install Ollama + pull the models:
   ```
   ollama pull gemma2:9b
   ollama pull qwen2.5-coder:7b
   ollama pull qwen2.5-coder:1.5b
   ```
3. Find the Ollama models directory (typically `C:\Users\<you>\.ollama\models`
   or `~/.ollama/models`). Copy the entire `models` folder to your USB stick.
4. Also copy:
   - The Ollama binary / installer
   - This whole `e156-student-starter/` folder

### On the offline machine

1. Copy the `e156-student-starter/` folder somewhere writable.
2. Run:
   ```
   .\install\install.ps1 -NoModelPull          # Windows
   bash install/install.sh --no-pull           # Linux
   ```
3. Copy the `models/` folder from your USB stick into `D:\ollama\models\`
   (the path your installer chose, shown at the end of setup).
4. Start Ollama: `ollama serve` (or the installer auto-starts it).
5. Verify: `ollama list` should show gemma2:9b + qwen2.5-coder:7b.
6. Smoke-test: `python D:\e156-student-starter\ai\ai_call.py quick "say OK"`

If `ollama list` is empty after copying, check that `OLLAMA_MODELS` env
points at the right folder. On Windows:
```
echo %OLLAMA_MODELS%
```

## Intermittent internet — how the router copes

The AI router (`ai/ai_call.py`) is explicitly **local-first**. It will:

1. Try Ollama first. If Ollama responds, use it. No cloud call ever happens.
2. Only fall back to cloud (GitHub Models, then Gemini) if Ollama is down.

You can force local-only by setting in `.env`:
```
E156_AI_PREFER=gemma
```

This guarantees zero cloud calls, even if `GITHUB_TOKEN` is set.

## Running when the power goes

If your machine is on battery:

- Gemma 2 9B uses ~4-6 W during inference on a modern laptop (CPU-only).
- A 60 Wh battery → ~10 hours of continuous AI-assisted work.
- Qwen 2.5 Coder 7B is similar.

If you're doing a lot of bulk work (e.g. rewriting 5 papers in one session),
consider:

```
# Force low-power quick model for brief tasks
E156_AI_PREFER=quick
```

`quick` maps to `qwen2.5-coder:1.5b`, which uses about 1/4 the electricity
of 9B while remaining useful for short edits.

## Verifying your offline setup

A full offline smoke test:

```
# 1. Disconnect from Wi-Fi.
# 2. Restart ollama if needed:
ollama serve &

# 3. Run the full pipeline:
cd examples/example_paper_01
python ../../ai/ai_call.py prose "Suggest 3 sharper opening sentences for this abstract: $(cat current_body.txt)"

# 4. Validate format:
python ../../tools/validate_e156.py current_body.txt
```

If all four steps work while disconnected, you are fully offline-ready.
