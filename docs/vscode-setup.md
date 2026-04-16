# VS Code + Continue.dev setup

If you want inline AI in your editor (like Copilot but free and local),
install Continue.dev and point it at your local Ollama.

## Why Continue.dev

- Free, open-source VS Code / JetBrains extension.
- Talks to any model: local Ollama, GitHub Models, Gemini, OpenAI, etc.
- Unlike Copilot, works offline with local models.
- Ships with chat, inline edit, and autocomplete.

## Install

1. Install the Continue extension:
   https://marketplace.visualstudio.com/items?itemName=Continue.continue
2. Make sure Ollama is running and the models are pulled (if you ran
   `install.ps1` / `install.sh` this is already done).
3. Copy the config:
   ```
   # Windows (PowerShell)
   mkdir -Force $HOME\.continue
   Copy-Item install\continue-config.yaml $HOME\.continue\config.yaml

   # Linux / macOS
   mkdir -p ~/.continue
   cp install/continue-config.yaml ~/.continue/config.yaml
   ```
4. Restart VS Code.
5. Click the Continue icon in the sidebar. You should see:
   - **Gemma 2 9B (prose)** — for chat and explanation
   - **Qwen 2.5 Coder 7B** — for code editing
   - **Qwen 2.5 Coder 1.5B** — for fast autocomplete

## How it routes

Continue uses "roles" to pick which model runs each task:

| Task | Model | Why |
|---|---|---|
| Chat in the sidebar | Gemma 2 9B (first) or Qwen Coder (manual pick) | Prose/research → Gemma; code Q&A → Qwen |
| Inline edit (Ctrl+I) | Qwen 2.5 Coder 7B | Code edits need the coder |
| Tab autocomplete | Qwen 2.5 Coder 1.5B | Must be <300ms; 1.5B is the largest that stays fast |
| Apply edit | Qwen 2.5 Coder 7B | Writing diffs |

If you want to pin a single model, click the model dropdown at the top
of the Continue panel.

## Slash commands

The config ships three E156-specific slash commands:

- `/e156` — validate the currently open buffer as an E156 body. Reports
  sentence count, word count, and any citation markers in the prose.
- `/rewrite156` — suggest a 7-sentence, 156-word rewrite of the selected
  text in the E156 S1-S7 order.
- `/explain-stats` — explain the selected statistical phrase in plain
  English for a clinician.

Type `/` in the Continue chat box to see them.

## Turning off autocomplete on weak hardware

If your laptop struggles with the 1.5B autocomplete model, edit
`~/.continue/config.yaml` and set:

```yaml
tabAutocompleteOptions:
  enable: false
```

You still get chat + inline edit, just not inline suggestions.

## What if I have a GitHub Copilot subscription?

If you're accepted into the GitHub Copilot Student Pack, you can add a
fourth model to Continue that uses GPT-4o via GitHub Models. Add this
block to `config.yaml`:

```yaml
  - name: GPT-4o (via GitHub Models)
    provider: openai
    model: gpt-4o-mini
    apiKey: ${GITHUB_TOKEN}
    apiBase: https://models.inference.ai.azure.com/
    roles:
      - chat
      - edit
```

Then set `GITHUB_TOKEN` in your environment. Continue will now offer
GPT-4o alongside your local models. Use it for multi-persona reviews
where 9B isn't sharp enough.

## What about Copilot itself?

If you have Copilot and want to use its built-in features too, you can
run Copilot and Continue side-by-side — Continue handles chat + custom
slash commands, Copilot handles inline autocomplete. That's the setup
most students with Copilot actually prefer.

Set `tabAutocompleteOptions.enable: false` in Continue so Copilot owns
autocomplete, keeping Continue for chat + slash commands against local
models. Best of both worlds.
