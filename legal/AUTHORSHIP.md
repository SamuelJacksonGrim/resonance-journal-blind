# Authorship Record

**Work:** Resonance (resonance-journal-blind)
**Human author and copyright holder:** Samuel Jackson Grim
**Last updated:** 2026-09-27

This record documents the human creative control exercised over this work. It
exists because U.S. copyright protects human-authored expression, and an
accurate account of the author's contribution supports registration and
enforcement. (Under *Thaler v. Perlmutter*, an AI is not an author and holds no
rights.)

## How this work was created. Stated plainly, because it differs from the author's multi-model projects.

1. **The method.** The author designed and wrote the
   [Architecture-Blueprints-Frameworks](https://github.com/SamuelJacksonGrim/Architecture-Blueprints-Frameworks)
   methodology over months of iterative, multi-model refinement (Claude, GPT, Grok): its construction order,
   depth selection, intake rules, security floor, the definition of "done", and
   the templates every design document starts from. That methodology governed
   how this work was designed and built.
2. **The prompt.** The author wrote a one-shot request: *"Build me something that weighs semantic relationships between words for storage that makes accessing them easy for an AI to pull when relevant."*
3. **Generation.** An AI tool (Claude) produced the design documents and code in a single autonomous pass under that methodology, with no further human input during the pass.
4. **Selection and direction.** The author reviewed the result, judged it, accepted it, and directed later changes. The first was the accent-folding fix (D-010 in architecture/DecisionLog.md).

The AI tools were instruments. None is an author.

## The author's position

The author's position is that this work is protected human authorship, on three
grounds.

1. **The framework is a human-authored control system, not a prompt.** The
   Architecture-Blueprints-Frameworks repository was built since 2026-06-15
   through a multi-model chain (Claude, GPT, Grok) directed, selected, and
   edited by the author, and refined further through controlled test
   iterations the author designed and judged (see that repository's
   `legal/AUTHORSHIP.md`). It does not merely describe a wanted result. It sets
   the construction order, what must be decided and recorded, how, and in what
   form.
2. **Human-authored expression appears in this work.** The design documents in
   `architecture/` and the `INTENT.md` card were instantiated from the author's
   templates. They carry the templates' structure, headings, frontmatter, and
   wording, and they apply the author's documented rules. Those parts are
   derivative of the author's protected expression.
3. **The author, through the framework, controlled the structure, sequence,
   and organization** of the design record. For software, that is the
   expression copyright law protects. The evidence is consistency: independent
   builds with different prompts, one of them blind (`resonance-journal`,
   `resonance-journal-rerun`, `resonance-journal-blind`), produced the same
   ten-document structure, the same Intent Card sections, the same DecisionLog
   form, and the same kind of handover. The framework determined that
   arrangement. The model did not.

**The honest limits.**
- A method *as a method* is excluded from copyright (17 U.S.C. §102(b)).
- Prompts alone were held generally insufficient in the Copyright Office's
  January 2025 report on copyrightability.
- The individual lines of code varied between runs, so the control argument is
  strongest for the design record's structure and weaker line by line.
- Functional code is thinly protected for everyone (the *Altai* filtration
  test; the merger doctrine).
- No court has ruled on AI-built software yet.

The claim strengthens with every change the author makes or directs from here
on. Keep the evidence: commits, prompts, and decision logs.

## Why this matters for the license

To the extent the work is copyrightable, the author is its sole human author
and may license it under both the AGPL-3.0 and a separate commercial license
(see `LEGAL-BASIS.md`).

## Keeping this accurate

This record must stay truthful. Update it when the process changes.

---

## Related

[[LEGAL-BASIS]] · [[LICENSING]] · [[CONTRIBUTING]] · [[COMMERCIAL-LICENSE]]
