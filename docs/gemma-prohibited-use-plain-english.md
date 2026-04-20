# About the AI you're installing

This installer will download Google's **Gemma 2** language model to your
laptop. Gemma is powerful and free to use for research, but it has rules
about what you can use it for. You MUST agree to these rules to continue.

## You MAY use Gemma for

- Rewriting a 156-word research paper abstract
- Suggesting citations
- Proofreading your methods section
- Asking "what does this statistics term mean?"

## You MUST NOT use Gemma for

- Deciding what medication a patient should take
- Deciding whether a patient needs an investigation
- Giving clinical advice to real patients
- Anything that would be a clinical decision in a hospital

## Why this rule exists

Gemma is trained on general text. It does not know your patient, it was
not reviewed by any medical regulator, and its answers can be confidently
wrong. Using it to decide patient care would be unsafe.

## What happens when you type AGREE

Your laptop records the date and time you agreed, in a file only you can
read (`~/e156/.consent.json`). The installer continues. If you ever change
your mind, delete that file to reset.

## What happens if you don't type AGREE

The installer exits. Nothing is installed. No laptop settings are changed.
You can close this window and restart later.
