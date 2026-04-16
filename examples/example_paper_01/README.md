# Example Paper #01 — Your First E156 Rewrite

This is the walkthrough paper. Everything you need to practice the full
workflow is in this folder. If this runs end-to-end on your laptop, your
bootstrap is working.

## What you're rewriting

An anonymised methods-paper abstract (156 words, 7 sentences, E156
format). Your job: rewrite it in your own words keeping the same
7-sentence structure (Question · Dataset · Method · Result · Robustness ·
Interpretation · Boundary) and stay at or under 156 words.

See `current_body.txt` for the AI-generated draft.

## Workflow

1. **Read the current body.** Understand what the paper is claiming.
2. **Rewrite it.** Open `your_rewrite.txt` and write your own version.
   You can use AI help at any point — see step 3.
3. **Use the AI to brainstorm or polish.** From this folder, run:
   ```
   python ../../ai/ai_call.py prose "Read this draft and suggest a clearer opening sentence: $(cat current_body.txt)"
   ```
   or for code help:
   ```
   python ../../ai/ai_call.py code "What's wrong with this Python snippet: ..."
   ```
4. **Validate format.** Run the checker:
   ```
   python ../../tools/validate_e156.py your_rewrite.txt
   ```
   It should report: `PASS (7 sentences, N words, N ≤ 156)`.
5. **Commit and push.** You're done with the practice paper.

## What if Ollama isn't running?

Start it: `ollama serve` in a separate terminal (Windows: Ollama tray
icon should be running — right-click → "Start").

Verify with:
```
ollama list
```
You should see `gemma2:9b` and `qwen2.5-coder:7b` (or the `:2b` /
`:1.5b` variants on low-RAM mode).

## What if I have no internet?

Everything in this example works offline once models are pulled. The
router (`ai_call.py`) will automatically use local Ollama models; it
won't try cloud fallbacks unless local is down.
