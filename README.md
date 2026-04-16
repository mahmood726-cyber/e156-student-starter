# E156 Student Starter

A complete research-infrastructure bootstrap for medical and public-health
students. Runs entirely on your own laptop. No subscription required.

**What you get:**

- The same quality-assurance system used to manage 483 E156 micro-papers
  (Sentinel pre-push rules, Overmind verifier, E156 format checker).
- Two local AI models running offline via Ollama — **Gemma 2** for prose
  and research writing, **Qwen 2.5 Coder** for Python and debugging.
- Optional cloud fallback for multi-persona review (GitHub Models free
  tier for students, or Gemini free tier).
- One worked example paper you can rewrite end-to-end in 30 minutes.

**Hardware:**

| Your laptop | What you run |
|---|---|
| 16 GB RAM (recommended) | Gemma 2 9B + Qwen 2.5 Coder 7B |
| 8 GB RAM | Gemma 2 2B + Qwen 2.5 Coder 1.5B (pass `--low-ram`) |
| 4 GB RAM | Cloud-only mode (Gemini or GitHub Models) |

All models download once (~10 GB) then work fully offline.

**No internet? No problem.** After the one-time setup, the whole system
works on a flight, in a power outage with a UPS, or in a lab without
Wi-Fi. The only things that need internet are (a) the one-time model
download and (b) pushing your finished paper to GitHub.

---

## Install

### Windows (PowerShell, no admin required)

```powershell
cd D:\e156-student-starter
.\install\install.ps1
```

### Linux / macOS

```bash
cd ~/e156-student-starter
bash install/install.sh
```

Pass `--low-ram` if your laptop has less than 12 GB RAM.

The installer will:
1. Download the portable Ollama runtime (~350 MB).
2. Pull Gemma 2 and Qwen 2.5 Coder to a local folder (~10 GB one-time).
3. Set up environment variables.
4. Run a smoke test to confirm everything works.

Total time: **15-45 minutes** depending on your connection.

---

## First paper (30 minutes)

After install, open `examples/example_paper_01/` and follow the README.
You'll rewrite a 156-word abstract using the local AI, validate it
against the E156 format checker, and see the whole pipeline run
end-to-end. This is the simplest possible test of your setup.

---

## Claiming a real paper

Once the example works:

1. Browse the **E156 student board**: https://mahmood726-cyber.github.io/e156/students.html
2. Pick a paper and click **Claim this paper**.
3. Fill the form (name, affiliation, email, senior-author nomination).
   If you don't have a faculty supervisor yet, type exactly
   `TBD - request mentor` and one will be assigned.
4. You have **42 days** to rewrite the 156-word body and submit to
   Synthēsis (synthesis-medicine.org). The workflow is documented on
   the student board and in the SUBMISSION METADATA block of every
   workbook entry.

**Authorship rule:** You are first author. Mahmood Ahmad is middle
author. Your faculty supervisor (or a nominated mentor) is last/senior
author. Never more, never less.

---

## The whole folder explained

```
e156-student-starter/
├── README.md                  ← you are here
├── install/
│   ├── install.ps1            ← Windows bootstrap
│   └── install.sh             ← Linux / macOS bootstrap
├── ai/
│   └── ai_call.py             ← task-typed AI router (pure stdlib)
├── tools/
│   ├── validate_e156.py       ← format checker (7 sentences, 156 words)
│   └── (more as needed)
├── rules/                     ← the playbook — read these
│   ├── AGENTS.md              ← cross-agent rules
│   ├── CLAUDE.md              ← Claude-specific pointer
│   ├── rules.md               ← workflow + testing + html-apps
│   ├── lessons.md             ← past-incident bug prevention
│   ├── e156.md                ← E156 format spec
│   └── advanced-stats.md      ← statistics gotchas
├── examples/
│   └── example_paper_01/      ← first-paper walkthrough
├── workbook/                  ← (empty, for your own papers)
└── docs/
    ├── getting-started.md     ← longer onboarding guide
    ├── ai-backends.md         ← how to add cloud fallbacks
    ├── airgap.md              ← offline / low-connectivity workflows
    └── troubleshooting.md     ← common errors
```

---

## Upgrading to cloud AI (optional)

If you get a **free GitHub Copilot for Students** account
(https://education.github.com/pack), your `.edu` email or student ID
unlocks a free `GITHUB_TOKEN` that gives you access to GPT-4o, Llama 70B,
and other cloud models via GitHub Models. Add this line to your
`.env` file:

```
GITHUB_TOKEN=ghp_your_token_here
```

The router will automatically use cloud models for multi-persona reviews
(which benefit from higher quality) while keeping day-to-day prose
and code tasks on local Gemma/Qwen.

If you don't qualify for Copilot but want a cloud option,
[Google AI Studio](https://aistudio.google.com/) gives free Gemini
access — add `GEMINI_API_KEY=your_key` to `.env`.

---

## Credits

This starter is a distilled version of the infrastructure at
`github.com/mahmood726-cyber/e156`. Everything here is released under
MIT (code) and CC-BY-4.0 (docs and rules).
