# Future actions

Open items that need a decision or a hands-on intervention outside what
the agent can do via `gh` and `git` on its own. Companion to
[`PLAN.md`](PLAN.md) (the build specification) and
[`PROMPT.md`](PROMPT.md) (the chronological log of what shipped).

---

## 1. PR #16 — frozen "Files changed" diff still carries the original content

### The problem

[PR #16](https://github.com/chaeyoonyunakim/pwr-workforce-elasticity-modelling/pull/16)
introduced the first version of `plan/PROMPT.md`, which quoted the
repository owner's prompts verbatim. The file has since been rewritten
on `main` (commit `92167c6`) into an action-only narrative without
verbatim quoting, and the original merge commit `ee39093` is no longer
reachable from any branch on this repository.

Surfaces I have already neutralised on PR #16:

- **Title** changed to "Add plan/PROMPT.md — session activity log
  (superseded)".
- **Body** rewritten as a redirect note pointing readers at the current
  `plan/PROMPT.md` on `main`.
- **Comment** added explaining the supersession and that the merge
  commit is unreachable.
- The head branch (`chore/prompt-log`) has been deleted from `origin`.

What I cannot change via the CLI: the **"Files changed"** tab on a
merged PR is frozen at merge time. GitHub stores the merge-base ↔
merge-head diff as part of the merge record, and force-pushing the head
branch does not cause it to recompute. The 311-line diff that adds the
original `plan/PROMPT.md` still renders if anyone navigates directly to
that tab.

### Options (pick one — none is automatic)

| # | Option | Effort | Side-effects |
|---|---|---|---|
| 1 | **Open a GitHub Support ticket** asking them to remove PR #16 and / or the orphan commit `ee39093` from public view. Quote the PR URL and a short rationale ("contains content that should not be public"). | Low (~5 minutes of writing + a few business days to resolve) | None for the working repo; the PR record becomes invisible. |
| 2 | **Rewrite repository history with `git filter-repo`** to scrub `ee39093` and the unreachable head commit `e0feff8`. Force-push every ref, re-tag `v0.0.0` against the rewritten commit graph. | Medium (~30 minutes to script and validate) | Invalidates every existing clone of this repository; anyone who already pulled has to re-clone. Existing PR numbers stay the same on GitHub but their merge SHAs change. |
| 3 | **Delete and recreate the repository.** Push the current `main` tree to a fresh repository under the same name. | High in terms of broken links; low in terms of effort. | Loses every existing PR (#1–#17), issue, watcher, star, release, and the v0.0.0 tag. Forks and external links all break. |
| 4 | **Do nothing.** Rely on PR #16's edited title and body to communicate that the diff is obsolete; let the PR sink down the list as subsequent activity buries it. | Zero | The frozen diff remains technically reachable to anyone who navigates directly to it. |

### Recommendation

**Option 1 (GitHub Support).** It is the only path that leaves the rest
of the repository's history intact, requires no force-pushes, preserves
every PR number and the v0.0.0 release, and removes the offending diff
from public view. The typical ticket turnaround is two to five business
days. If urgency is higher, escalate to Option 2 — but accept the cost
that every clone of this repository needs to be re-fetched.

Owner action: file the ticket through
[https://support.github.com/contact/private-information](https://support.github.com/contact/private-information).
A two-line description plus the PR URL is sufficient. I (the agent)
cannot file the ticket on the owner's behalf.

---

## Closed actions

*(none yet)*
