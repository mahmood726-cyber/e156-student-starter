# Your E156 paper

Your first paper. This is the blank T0 template — you have a workbook
folder with the three files you need.

## Files

- `README.md`      — this file (rename it / overwrite with your paper title)
- `e156_body.md`   — the 7-sentence, ≤156-word body. **It already passes
                     `student validate`** — you just replace the `{{...}}`
                     placeholders with real content. `student validate --strict`
                     will BLOCK until every `{{...}}` is replaced.
- `preanalysis.md` — write your plan here and **commit it BEFORE you
                     start pulling data**. A later validator enforces that
                     preanalysis is committed before any data-touching commit.

## Suggested workflow

1. Edit `preanalysis.md` first. Commit with message `preanalysis: <topic>`.
2. Pull your data / run your analysis.
3. Edit `e156_body.md` sentence by sentence, replacing each `{{placeholder}}`.
4. Run `student validate --strict` — this should go green when you're ready.
5. Run `student baseline record <slug> --value pooled_estimate=X --value ci_lower=Y ...`
   to lock your numbers.
6. Run `student verify-citations --path e156_body.md` to check every
   author-year against PubMed (needs one online pass; then works offline).
7. Run `student enroll-authors --slug <slug>` to fill the authorship contract.
8. Run `student publish --slug <slug>` to produce the reproducibility zip.
