# Quest Journal: PDF Formatting Preservation

- Quest ID: `pdf-formatting_2026-04-06__1833`
- Slug: pdf-formatting
- Completed: 2026-04-06
- Mode: workflow
- Quality: Silver
- Celebration: [`celebrations/pdf-formatting_2026-04-06.md`](celebrations/pdf-formatting_2026-04-06.md)
- Outcome: Improve doc2md's PDF converter to better preserve formatting from structured PDFs, using only existing pdfjs-dist positional data (no new dependencies). ### Phase 1 (safe, additive heuristics): 1. ...

## What Shipped

**Problem:** doc2md's PDF converter extracts text via pdfjs-dist but ignores x-position data and font-size mixing within lines. This causes superscript symbols to fragment headings, tables to flatten into prose, nested lists to lose indentation, headers/footers to pollute every page, kerning gaps...

## Files Changed

- `.quest/pdf-formatting_2026-04-06__1833/phase_01_plan/plan.md`
- `.quest/pdf-formatting_2026-04-06__1833/phase_01_plan/arbiter_verdict.md`
- `.quest/pdf-formatting_2026-04-06__1833/phase_01_plan/review_plan-reviewer-a.md`
- `.quest/pdf-formatting_2026-04-06__1833/phase_01_plan/review_plan-reviewer-b.md`
- `src/converters/pdf.ts`
- `src/converters/pdf.test.ts`
- `.quest/pdf-formatting_2026-04-06__1833/phase_03_review/review_code-reviewer-a.md`
- `.quest/pdf-formatting_2026-04-06__1833/phase_03_review/review_code-reviewer-b.md`
- `.quest/pdf-formatting_2026-04-06__1833/phase_03_review/review_fix_feedback_discussion.md`

## Iterations

- Plan iterations: 1
- Fix iterations: 2

## Agents

- **The Judge** (arbiter): 
- **The Implementer** (builder): 

## Quest Brief

Improve doc2md's PDF converter to better preserve formatting from structured PDFs, using only existing pdfjs-dist positional data (no new dependencies).

### Phase 1 (safe, additive heuristics):
1. **Superscript folding** — Detect registered/trademark/copyright symbols at smaller font sizes on the same y-row and merge into surrounding text instead of classifying as separate headings
2. **Header/footer stripping** — Detect repeating text at extreme y-positions across 3+ pages (with page numbers wildcarded) and remove before rendering
3. **Kerning-aware spacing** — Use item width + gap distance to suppress false spaces (fixes "202 6" to "2026")
4. **TOC dot leader cleanup** — Strip runs of 3+ dots optionally followed by page numbers

### Phase 2 (core rendering changes):
5. **Table detection via x-position clustering** — Group items by y-row, detect 3+ consecutive rows sharing the same 2+ x-column clusters, emit markdown tables
6. **Nested list indentation** — Use x-position depth to determine nesting level; detect "o" in non-body fonts as bullet characters
7. **Inline bold spans** — Track font changes within a line and emit `**...**` around bold spans rather than classifying whole lines

### Constraints:
- All changes in `src/converters/pdf.ts` (and new test files)
- No new npm dependencies
- Must work in both browser and Node
- Must not break existing tests
- Use infliximab PDF as test fixture
- Reference: `docs/implementation/pdf-formatting-analysis.md` has full evidence
- Test document in `.ws/complicated-pdf` for local testing only, do NOT commit or reference concrete content

### Key Technical Insights:
- pdfjs-dist provides transform[4] (x), transform[5] (y), width, fontName, fontSize per text item
- Table signal is clean: consistent 2-item rows snapping to same x-positions vs variable prose rows
- Conservative safeguards: 3+ consecutive rows, 2+ x-clusters, matching column counts
- No new dependencies needed for any of the 7 improvements

## Carry-Over Findings

- No carry-over findings this round; nothing was inherited from earlier quests and nothing needs to be saved for the next one.

## Celebration

This journal embeds the celebration payload used by `/celebrate`.

- Full celebration: [`celebrations/pdf-formatting_2026-04-06.md`](celebrations/pdf-formatting_2026-04-06.md)
- [Jump to Celebration Data](#celebration-data)
- Replay locally: `/celebrate docs/quest-journal/pdf-formatting_2026-04-06.md`

## Celebration Data

<!-- celebration-data-start -->
```json
{
  "quest_mode": "workflow",
  "agents": [
    {
      "name": "arbiter",
      "model": "",
      "role": "The Judge"
    },
    {
      "name": "builder",
      "model": "",
      "role": "The Implementer"
    }
  ],
  "achievements": [
    {
      "icon": "[BUG]",
      "title": "Gremlin Slayer",
      "desc": "Tackled 12 review findings"
    },
    {
      "icon": "[TEST]",
      "title": "Battle Tested",
      "desc": "Survived 5 reviews"
    },
    {
      "icon": "[WIN]",
      "title": "Quest Complete",
      "desc": "All phases finished successfully"
    }
  ],
  "metrics": [
    {
      "icon": "📊",
      "label": "Plan iterations: 1"
    },
    {
      "icon": "🔧",
      "label": "Fix iterations: 2"
    },
    {
      "icon": "📝",
      "label": "Review findings: 5"
    }
  ],
  "quality": {
    "tier": "Silver",
    "grade": "S"
  },
  "inherited_findings_used": {
    "count": 0,
    "summaries": []
  },
  "findings_left_for_future_quests": {
    "count": 0,
    "summaries": []
  },
  "test_count": null,
  "tests_added": null,
  "files_changed": 9
}
```
<!-- celebration-data-end -->
