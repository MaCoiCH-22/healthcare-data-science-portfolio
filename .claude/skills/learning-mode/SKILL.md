---
name: learning-mode
description: Optional coding-lesson add-on. Use only when Macoi says "learning mode on" (or asks to learn from a change); stays off for ordinary production work.
---

# Learning mode

Off by default. When on, add a short lesson after a meaningful change (new function, bug fix, test), never after trivial edits. Keep it to one screen, in plain prose, after the production summary, so the real work is never delayed.

Each lesson has, in this order:

1. What the important function does, in plain English, three or four sentences.
2. Why this approach was chosen over one obvious alternative.
3. A code-reading exercise: show five to ten real lines from the change and ask one question about what they do.
4. Every third lesson or so, a fill-in-the-blank recall line from the same code, with the answer hidden below a line of dashes.
5. One sentence connecting it to a data science idea she knows (data validation, reproducibility, joins, distributions, model evaluation) when the link is real. Skip it rather than force it.

Never use real patient data in examples; use the fake plant names. Turn off when she says "learning mode off".
