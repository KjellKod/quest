# Quest Housekeeping Docs Should Be Current Before the Draft PR

Date: 2026-09-22
Status: `proposed`
Origin: surfaced while auditing documentation in a downstream repo that uses
Quest. Four separate stale-status incidents in one session, all the same
mechanism. Analysis only, no code changed.

## Problem

A Quest writes housekeeping documentation as it goes: plan artifacts, journal
entries, implementation records. Those documents carry a `status:` field, and
that field is written **at authoring time**, before the work has landed.

Nothing ever updates it.

So a document says `delivered as draft PR, not merged` and stays that way
forever, including long after the PR merged. The document is not wrong when it
is written. It rots the moment the PR merges, and nothing notices.

### Observed, not hypothetical

In one downstream repository, seven implementation records claimed the work was
unmerged. All seven had shipped:

| Document status | Reality |
|---|---|
| `delivered as draft PR, not merged` | PR merged 5 days earlier |
| `implemented on <branch>, not merged` | PR merged 1 day earlier |
| `complete, approved for commit and draft PR` | PR merged |
| `Delivered in draft PR 395, awaiting integration` | PR 395 merged |
| `Validated, draft PR pending publication approval` | PR merged |
| `Delivered in draft PR 402, not merged` | PR 402 merged |
| `implemented, live rollout pending` | shipped, workflow live on main |

The same mechanism had also left that repository's `README.md` telling every
visitor the product was not available for sale, months after it became
purchasable.

### Why it matters more than it looks

1. **It manufactures phantom work.** Seven shipped features looked like an
   outstanding backlog. An agent reading the repository to decide what to do
   next would have picked up work that was already done.
2. **It poisons agent context.** Agents read `status:` fields as fact. A stale
   one is worse than an absent one, because it is confidently wrong and the
   agent has no reason to doubt it. This produced a wrong review in that
   session until the human asked "what draft PR?" and the claim collapsed on
   the first check.
3. **It is invisible.** A link validator catches broken links. Nothing catches
   a status line that was true in the past.

## The rule worth adopting

**Any documentation a Quest touched as housekeeping must reflect the state the
Quest is actually delivering, before the draft PR is created.** Not after
merge, not "later", and not left describing an intermediate state that the PR
itself makes obsolete.

Explicitly opt out when the stale-looking state is deliberate, for example a
record that intentionally preserves what was believed at the time. The opt-out
should be a stated decision, not a default.

The reason to put the gate before the draft PR rather than after merge: at draft
time the agent still has full context on what the documents claim and why. After
merge that context is gone, and whoever returns to it is reconstructing.

## Where it should live

Three candidate homes, and they are not exclusive:

**A. A `quest_complete` / draft-PR-time check (preferred).** Before the draft
PR is created, enumerate documents the Quest created or modified, extract their
`status:` fields, and require each to describe the state being delivered. A
document still saying `pending` or `not merged` in the same PR that delivers it
is the signal. This catches the problem at the moment the agent can still fix
it cheaply.

**B. `pr-shepherd`, at merge.** Update a document's `status:` when the PR it
references merges. This is the narrower, more mechanical fix: it only helps
documents that name their PR, and only after the fact. Useful as a backstop,
weaker as the primary gate.

**C. A repo-shared lint.** Flag a `status:` value containing `pending`,
`not merged`, `awaiting`, or `draft PR` on a document whose referenced PR is
merged. Cheap, runs in CI, catches drift from any source including
human-authored docs. The weakness is that it only works for documents that cite
a PR number.

A reasonable combination is A as the gate and C as the safety net, with B only
if it falls out of the shepherd pipeline for free.

## Open questions

- Should the gate block draft PR creation, or warn? Blocking risks a false
  positive stopping delivery over a doc field. Warning risks being ignored.
  A warning that must be explicitly acknowledged is probably the right shape.
- Should `status:` become a closed vocabulary? Observed values in one repo
  included `complete`, `Complete`, `implemented`, `Validated, draft PR pending
  publication approval`, and `delivered as draft PR, not merged`. A closed set
  would make the check trivial, but Quest does not own downstream repos'
  documentation conventions and should not impose one.
- Does this extend to journal entries, or only to implementation records?
  Journals arguably *should* freeze at authoring time, since they record what
  happened. That is an argument for scoping the rule to documents that describe
  current state rather than history.
- What about documents describing work deliberately left unmerged? Those are
  the legitimate case for the opt-out, and they are also the ones most worth
  surfacing, since an unmerged branch is easy to lose.

## Non-goals

- Rewriting the body of a document. The `status:` field is the machine-read
  part and the one that misleads. Prose drift is a separate and much larger
  problem.
- Enforcing a documentation format on downstream repositories.
- Retroactively auditing existing documents. That is a one-off cleanup, not a
  Quest feature.
