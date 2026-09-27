# Authorship Record

**Work:** Resonance (resonance-journal-blind)
**Human author and copyright holder:** Samuel Jackson Grim
**Last updated:** 2026-09-27

This record documents the human creative control exercised over this work. It
exists because U.S. copyright protects human-authored expression, and an
accurate account of the author's contribution supports registration and
enforcement. (Under *Thaler v. Perlmutter*, an AI is not an author and holds no
rights.)

## How this work was created

1. **The method.** The author designed and wrote the
   [Architecture-Blueprints-Frameworks](https://github.com/SamuelJacksonGrim/Architecture-Blueprints-Frameworks)
   methodology over months of iterative, multi-model refinement (Claude, GPT, Grok, Gemini): its construction order,
   depth selection, intake rules, security floor, the definition of "done", and
   the templates every design document starts from. That methodology governed
   how this work was designed and built.
2. **The trials.** The work came out of consecutive, controlled trial and error
   that the author directed. Each round changed the framework the next round
   ran under, and the author decided what changed:
   - **Trial 1:** a first build of a journal application
     (`resonance-journal`). The author graded it and named what it missed.
   - **Intake trials:** two rounds of fresh AI agents ran the framework's
     intake on three different requests. Their failures became framework
     revisions (Architecture-Blueprints-Frameworks D-013 to D-022).
   - **Trial 2:** a re-run (`resonance-journal-rerun`). It exposed an answer
     key inside the framework, and the author ruled that answer keys stay
     outside the system under test (D-023).
   - **Trial 3:** a blind build (`resonance-journal-blind`) from a prompt the
     author wrote to be unseen by the framework. The author then judged it,
     overruled an AI's defect finding, and directed the accent-folding fix.
3. **This repository is Trial 3.** The author's prompt: *"Build me something that weighs semantic relationships between words for storage that makes accessing them easy for an AI to pull when relevant."*
4. **The final generation pass.** An AI tool (Claude) wrote this repository's
   design documents and code in one autonomous pass under the framework as it
   stood after the earlier rounds. That pass is the last step of the sequence
   above, not a standalone one-shot.
5. **Selection and direction.** The author reviewed the result, judged it, accepted it, and directed later changes. The first was the accent-folding fix (D-010 in architecture/DecisionLog.md).

The AI tools were instruments. None is an author.

## The author's position

The author's position is that this work is protected human authorship, on three
grounds.

1. **The framework is a human-authored control system, not a prompt.** The
   Architecture-Blueprints-Frameworks repository was built since 2026-06-15
   through a multi-model chain (Claude, GPT, Grok, Gemini) directed, selected, and
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

Keep the evidence: commits, prompts, and decision logs.

## Why this matters for the license

The author is the work's sole human author
and may license it under both the AGPL-3.0 and a separate commercial license
(see `LEGAL-BASIS.md`).

## Keeping this accurate

This record must stay truthful. Update it when the process changes.

---

## Related

[[LEGAL-BASIS]] · [[LICENSING]] · [[CONTRIBUTING]] · [[COMMERCIAL-LICENSE]]
