---
name: Cloud fallback is OFF by default; turning it on means data leaves your laptop
description: Local-first is the privacy default; --i-understand-egress is deliberate friction
type: reference
---

`student ai` calls local Ollama by default. If Ollama isn't running or the
local model fails, the call fails — it does NOT silently fall back to cloud.

To enable cloud fallback (Gemini, GitHub Copilot for Students) you must run:

    student ai enable-cloud --i-understand-egress

The `--i-understand-egress` flag is deliberate friction: enabling cloud means
your paper draft, data, and prompts leave your laptop and travel to a third-
party server, subject to that server's retention policy. For many Uganda-
based students, this may violate ethics-board constraints on patient data.

**Why:** The E156 student flow is designed for a clinical/research context
where a loose "let me just ask GPT" can be an IRB violation. Local-first isn't
just a privacy nicety — it's what makes the bundle compliant with the data-
handling rules most medical schools require.

**How to apply:** Turn cloud ON only when:
- You're writing about PUBLISHED data (no patient identifiers, no unpublished
  numbers).
- You've checked your ethics approval letter for whether cloud LLM use is
  permitted.
- You've noted in your acknowledgments that "AI cloud assistance from
  provider X was used for language editing on sentences Y, Z."

Turn it OFF immediately after: `student ai disable-cloud`.
