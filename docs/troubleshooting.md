# Troubleshooting

## "Ollama not reachable"

**Symptom:** `ai_call.py` returns "All available AI backends failed.
Tried: ollama/gemma2:9b. Last error: Ollama not reachable at
http://127.0.0.1:11434".

**Cause:** the Ollama server isn't running.

**Fix:**

```
# Start it (background)
ollama serve &           # Linux/macOS
```

Windows: either run `ollama.exe serve` in a PowerShell window and leave
it open, or re-run the installer — it starts the server as a background
process.

Verify with:
```
curl http://127.0.0.1:11434
```
You should see `Ollama is running`.

## "model 'gemma2:9b' not found"

**Cause:** the model wasn't pulled, or `OLLAMA_MODELS` points to the wrong folder.

**Fix 1:** pull it.
```
ollama pull gemma2:9b
```

**Fix 2:** check your models path.
```
echo $OLLAMA_MODELS        # Linux/macOS
echo %OLLAMA_MODELS%       # Windows cmd
echo $env:OLLAMA_MODELS    # Windows PowerShell
```
If it's empty or wrong, set it and restart Ollama:
```
# Windows PowerShell (user-level, persistent)
[Environment]::SetEnvironmentVariable("OLLAMA_MODELS","D:\ollama\models","User")

# Linux/macOS (add to ~/.bashrc)
export OLLAMA_MODELS=~/ollama/models
```

## "Model is very slow"

**Cause:** you're running on CPU without enough RAM, or the model is
too big for your laptop.

**Fix:** pass `--low-ram` to the installer and re-pull:
```
.\install\install.ps1 -LowRam      # Windows
bash install/install.sh --low-ram  # Linux/macOS
```

This pulls `gemma2:2b` (1.4 GB) and `qwen2.5-coder:1.5b` (1 GB)
instead of the 9B/7B variants. Quality drops, but they run at
usable speed on 8 GB RAM.

## "401 Unauthorized" from GitHub Models

**Cause:** `GITHUB_TOKEN` is missing, expired, or missing the `Models` scope.

**Fix:**

1. Go to https://github.com/settings/tokens
2. Delete the old token if it exists.
3. Create a **fine-grained personal access token**.
4. Under "Account permissions" find **Models** and set to "Read-only".
5. Copy the token (starts with `github_pat_`).
6. Update `.env`:
   ```
   GITHUB_TOKEN=github_pat_11XXX...
   ```
7. Reload your shell or re-open VS Code.

## "429 Too Many Requests"

**Cause:** you hit a cloud free-tier quota.

- GitHub Models: 150/day for most models. Resets at midnight UTC.
- Gemini: 15 req/min, resets per minute.

**Fix:** fall back to local:
```
export E156_AI_PREFER=gemma
```
or wait for the quota window.

## "Python not found" on Windows

**Cause:** Python isn't in your PATH.

**Fix:** install from https://python.org/downloads/ and check the
"Add Python to PATH" box during install. Then reopen PowerShell.

To verify:
```
python --version
```

## Gemma gives garbled output

**Cause:** some old Gemma 2 quantizations have tokenizer bugs.

**Fix:** re-pull with an explicit tag:
```
ollama pull gemma2:9b-instruct-q4_K_M
```

Then update `.env`:
```
E156_PROSE_MODEL=gemma2:9b-instruct-q4_K_M
```

## Disk full after pulling models

**Cause:** models landed on C: instead of D:.

**Fix:** set `OLLAMA_MODELS`, move existing models:
```powershell
# Windows
Move-Item "$env:USERPROFILE\.ollama\models\*" D:\ollama\models\
[Environment]::SetEnvironmentVariable("OLLAMA_MODELS","D:\ollama\models","User")
# Restart Ollama
```

```bash
# Linux/macOS
mv ~/.ollama/models/* ~/ollama/models/
export OLLAMA_MODELS=~/ollama/models
```

## "No senior author / no supervisor"

Not a technical error. **Do NOT type a placeholder** like "TBD", "FIXME",
or "request mentor" in the senior-author field — `student validate
--authorship` now blocks those on purpose, because a placeholder
author is how papers accidentally get submitted with no real senior
author attached (integrity issue).

Instead:

1. Leave the senior-author field blank for now.
2. Open an issue at
   <https://github.com/mahmood726-cyber/e156/issues/new?template=needs-mentor.md>
   (or label a plain issue `needs-mentor`) with a 2-3 sentence
   description of your paper topic.
3. One of the E156 advisory-pool mentors will be assigned before you
   submit, and they'll fill in the senior-author field with their
   real name, email, affiliation, and ORCID.

## Still stuck

Open an issue at https://github.com/mahmood726-cyber/e156/issues with
(a) what command you ran, (b) the exact error message, (c) the output
of `python ai_call.py quick "say OK"` with `E156_AI_DEBUG=1`, and
(d) your OS + RAM.
