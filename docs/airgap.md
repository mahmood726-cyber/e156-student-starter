<!-- sentinel:skip-file — instructional doc showing example Windows paths -->
# Air-gapped / low-connectivity workflows

This starter is designed to work fully offline **after the one-time
model download**. This doc covers:

1. Running day-to-day without internet
2. Installing on a machine that's never online (sneaker-net)
3. What needs internet and what doesn't

## What needs internet

| Task | Internet? | Why |
|---|---|---|
| Install Ollama + pull models (one time) | Yes | ~380 MB Ollama + ~10 GB models |
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

If your laptop has no internet at all, install from a USB stick.

### On an internet-connected machine (friend's, cyber café, etc.)

1. Download the **content-stable mirror** of the Ollama portable zip. We mirror
   it because upstream Ollama Release assets are mutable (the same URL has
   served three different SHA256s on different days), so a strict pin against
   upstream is unreliable. The mirror serves a fixed snapshot:
   ```
   https://github.com/mahmood726-cyber/e156-binary-mirror/releases/download/mirror-2026-04-20/ollama-windows-amd64.zip
   ```
   Verify SHA256 = `eb565d16c8025e37d09fbb234c627c7c13f05c5f007bfa8f76fa6b6b8695ca31`.
   The starter installer also tries this URL first; if you'd rather use upstream
   directly, you can — `install.ps1` will WARN on SHA mismatch but proceed.

2. On that internet-connected machine, install Ollama + pull the models:
   ```
   ollama pull gemma2:9b
   ollama pull qwen2.5-coder:7b
   ollama pull qwen2.5-coder:1.5b
   ```
3. Find the Ollama models directory (typically `%USERPROFILE%\.ollama\models`
   on Windows or `~/.ollama/models` on Linux). Copy the entire `models` folder
   to your USB stick.
4. Also copy:
   - The Ollama portable zip (from step 1)
   - This whole `e156-student-starter/` folder

### On the offline machine

1. Copy the `e156-student-starter/` folder somewhere writable.
2. Run the installer in cloud-only mode so it skips the model pull (and use
   `-DryRun` first to check the bundle hash):
   ```powershell
   .\install\install.ps1 -DryRun       # verifies install.ps1 SHA, exits 0
   .\install\install.ps1 -CloudOnly    # full install, skips ollama pull
   ```
3. The installer creates `%LOCALAPPDATA%\e156\ollama\models\`. Copy the
   `models/` folder from your USB stick into that exact path.
4. Start Ollama: the installer launches it, but if you reboot:
   ```powershell
   & "$env:LOCALAPPDATA\e156\ollama\ollama.exe" serve
   ```
5. Verify: `ollama list` should show `gemma2:9b` + `qwen2.5-coder:7b`.
6. Smoke-test:
   ```powershell
   python ai\ai_call.py quick "say OK"
   ```

If `ollama list` is empty after copying, the `OLLAMA_MODELS` env var is wrong.
The installer sets it to `%LOCALAPPDATA%\e156\ollama\models` for the User
scope; check it with:
```powershell
$env:OLLAMA_MODELS
```

### Strict-SHA mode (paranoid users)

By default, the installer **warns** on Ollama SHA mismatch and continues —
because upstream is mutable and we don't want students stuck. To enforce a
byte-exact match (typical for reproducibility audits or supply-chain review):

```powershell
$env:E156_OLLAMA_REQUIRE_SHA_MATCH = '1'
.\install\install.ps1
```

The installer will roll back the install on any SHA mismatch (mirror or
upstream).

## Intermittent internet — how the router copes

The AI router (`ai/ai_call.py`) is explicitly **local-first**. It will:

1. Try Ollama first. If Ollama responds, use it. No cloud call ever happens.
2. Only fall back to cloud (GitHub Models, then Gemini) if Ollama is down.
3. The actual cloud HTTP call runs in a subprocess (`ai/cloud_subproc.py`)
   so the credential is never bound to a module constant in the main process.

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

```powershell
# 1. Disconnect from Wi-Fi.
# 2. Restart ollama if needed:
& "$env:LOCALAPPDATA\e156\ollama\ollama.exe" serve

# 3. Run the full pipeline (from the starter root):
python ai\ai_call.py prose "Suggest 3 sharper opening sentences for this abstract: ..."

# 4. Validate format on a paper:
python tools\validate_e156.py path\to\current_body.txt
```

If all three steps work while disconnected, you are fully offline-ready.
