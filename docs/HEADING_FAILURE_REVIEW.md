# Heading detection, query overlap, and the next controlled experiment

Review date: 2026-10-12 EDT. Starting checkpoint:
`10e91145bd6b9530c2f43f18c9e91512f2173093`.

**Recommend a narrow note-format coverage ablation next, with scoring and matching
unchanged.** It tests a demonstrated loss of useful acquisition/legal heading terms.
Keep expansion v1 as the development control and section v1 as a saved comparator.
No new detector, ranking rule, runtime configuration or experiment is implemented
by this review.

The five multi-page failures mostly involve correctly detected statement/risk/list
headings with weak lexical signal or insufficient score, not missing titles. A note
format repair therefore has a limited hypothesis; it is not a proposed solution to
every multi-page case. Keep these mechanisms separate when interpreting the next run.

## Evidence and review boundaries

The saved section run is `20261013T010312Z-967cd9567b9c`. Its ten artifact byte hashes/
sizes and the original native-cache identity were checked again. The current committed
Python package matches the executed source fingerprint with Windows CRLF newlines.
Expansion/section policy fingerprints and the previously verified metrics remain
unchanged. Section v1 Recall@5 is 40.97%, complete coverage 8/24, and all five
multi-page questions remain incomplete. No new ranking or metric is executed here.

Review uses the original native text, saved heading records/scopes, expanded minimal
queries, and saved body/heading scores. Page IDs are zero-based physical PDF indices;
ranks are one-based; offsets are raw Unicode characters [start,end), not PDF geometry.

The attached `heading-failure-casebook.json` records 13 selected development examples
and the saved heading/overlap/score audit for the five multi-page tasks. Source spans
and query-token intersections are reproducible facts. Semantic heading correctness
and usefulness are reviewer judgments based on surrounding native text. Examples are
purposively selected; their counts do not estimate corpus heading precision/recall.
The PDFs/fonts/bounding boxes are not available for visual validation. This report
and casebook are gold-exposed offline diagnostics: exclude them from retrieval,
extractor prompts and ledger/correction memory.

## Separate three questions for each case

1. **Detection and scope:** Is a genuine local heading present in source text? Did
   v1 identify it, distinguish it from table/prose text, and stop/start context at
   the appropriate boundary? A saved pointer can be byte-correct yet semantically wrong.
2. **Matching:** Does the correctly identified heading share literal content tokens
   with the frozen expanded question? If it does, are those terms about the requested
   topic or mainly a company name, role instruction, or broad financial context?
3. **Retrieval:** If a useful heading score exists, does the page enter the fixed
   top-five evidence set? Positive overlap/score does not guarantee multi-page coverage.

These are separate flags, not mutually exclusive page labels. A page can contain a
missed useful heading, correctly observed but irrelevant titles, and a stale inherited
scope. Zero heading score alone does not establish a detector failure. Conversely,
nonzero score does not establish that the heading provided the missing evidence.

## Detection failures, independently of matching

| Source example | V1 detection/scope result | Overlap with the relevant query | Diagnosis |
|---|---|---|---|
| Best Buy 2023 p50: `2. Acquisitions`, [1837,1854) | Missed bare-number note; Stock-Based Compensation scope continues through acquisition prose | acquisitions | A missed, directly useful topic heading; plausibly contributes to lost heading signal |
| Boeing 2022 p111: `Note 21 – Legal Proceedings`, [2122,2149) | En dash unsupported; Fair Value Disclosures remains active | legal | Missed useful topic and wrong context entering continuation p112 |
| Boeing 2022 p112: `Note 22 – Segment and Revenue Information`, [2429,2470) | Also missed; inherited Fair Value scope covers the entire page | none for the legal question | Missing boundary; repairing this title alone would not add a legal-token match |
| Best Buy 2023 p50: `3. Restructuring`, [3369,3387) | Missed bare-number boundary | none for the acquisitions question | Real detection failure without a direct acquisitions signal |
| AMD 2015 p55: Year Ended, [127,137) | Accepted generic title, then eligible for continuation | none for the D&A question | Time-column label affects heading state; not a statement/topic title |
| PepsiCo 2022 p77: division-name column row, [2255,2303) | Accepted generic title | none for the restructuring question | Table header mistaken for a local section title |
| Best Buy 2023 p46: `Consolidated Statements of Earnings from the fair value of the derivatives.`, [1587,1662) | Accepted statement heading | Not evaluated against a selected question | Wrapped prose matches the broad statement-prefix grammar |

For Boeing, the important new distinction is **Note 21**, not just Note 22. Native
page 111 starts with Fair Value Disclosures and changes to Legal Proceedings at
offset 2122. Legal prose continues at the opening of page 112 until the Segment
and Revenue note begins at offset 2429. V1 misses both note titles and carries
Fair Value Disclosures from p111 into p112 over [18,4088). Recovering Note 21 would
make legal available as a source heading token and make the continuation's scope
more appropriate. That is an untested retrieval hypothesis, not a claim that the
gold page would enter the top five. Note 22 is needed to close that legal span,
even though its own title has no useful overlap with the legal question.

For Best Buy acquisitions (01077), saved page 50 has no heading match and remains
at score 6.756721. Page 49's correctly observed Best Buy Gift Cards title matches
best/buy and adds a weighted 1.426465; its total 7.180274 overtakes page 50, moving
the first gold rank 3→4. This case combines a missed useful heading on p50 and a
company-word boost on a competing page. The regression cannot be attributed solely
to one mechanism without a controlled ablation.

## Correct detections with weak or absent query signal

| Case | Correctly observed heading/context | Actual literal overlap | What the existing run shows |
|---|---|---|---|
| Boeing customers 01290, p7/9/13 | Airline risk, defense-spending risk, government-contract risk | Empty on all three gold heading fields | No gold heading boost; ranks 39→46, 3→3, 161→162 as competitors gain |
| PepsiCo geographies 01009, p3 | Our Operations | Empty | Page 3 remains rank 228; heading is present, not missing |
| Same task, opening of p4 | Our Operations inherited only over [18,374) | Empty | Continuation boundary is correct; operations and operates are distinct tokens |
| Same task, p4 local division titles | Includes PepsiCo Beverages North America | pepsico only | Adds 0.473297 weighted score; rank 20→13, still outside five; no geography-specific token match |
| AMD D&A 03069, p55 | Consolidated Statements of Operations | Empty for that exact title | P&L statement wording does not literally match; page's separate Item 8 heading matches financial only |
| PepsiCo calculations 03620/04481, p61 | Consolidated Statement of Income | income, statement | Correct and relevant positive match; +2.345978 weighted score, ranks 23→19 and 24→20, still missing at k=5 |

The Boeing headings describe the customer categories in source language, but the
question asks primary customers of Boeing/FY2022. Detecting those headings again
or increasing a weight cannot turn an empty token intersection into a match. A
semantic/customer-category relationship would be a separate matching experiment;
copying airline/government answer categories into a question rule from these labels
would not be an acceptable runtime repair.

For PepsiCo geographies, generic stemming/lemmatization is not a guaranteed remedy:
operates is a verb and operations is a noun, and the question's geographies term
still does not name regions in the source titles. Any normalization or semantic
matching policy would need its own definition and comparison; it is not a detector fix.

AMD p59's cash-flow title matches cash/flows, while an inherited stockholders' equity
title matches equity from the question's analyst-role wording. That inherited label
ends at the real cash-flow title, but its incidental match still enters the page-level
field. This illustrates that a bounded raw scope can generate an unhelpful page-wide
bonus. The p55 operations title is correctly detected; calling that miss a heading
extraction failure would be misleading.

For the PepsiCo calculations, the missing income-statement title is neither absent
nor unmatched. It receives useful signal that is too small to pass competing pages.
Scalar lexical scoring does not enforce coverage of both question-named statements.
Changing heading detection alone is not expected to resolve that dependency; any
statement-family coverage selector is a separate retrieval experiment.

## Recommended next experiment: note-format coverage only

Use a separately versioned detector condition to test whether missed **query-relevant
note headings** materially contribute to current coverage/ranking failures. This is
a narrow, source-grounded intervention before changing scoring, semantic matching
or memory. Best Buy acquisitions and Boeing legal proceedings supply concrete
diagnostic targets; all 24 pilot questions stay in the evaluation denominator.

| Condition | Role | What changes |
|---|---|---|
| E: frozen expansion v1 | Development control | Nothing |
| S1: saved section v1 | Existing structural comparator | Nothing; reproduce its outputs |
| S2: proposed note-format coverage condition | New detector ablation | Recognize supported new note forms; downstream heading scopes/field update normally |

**S2 minus S1 isolates the detector-format change.** S2 minus E reports the overall
structural effect; that combined difference must not be attributed solely to note
recognition. Preserve all historical controls and their metrics.

The proposed intervention has two related syntax cases within note recognition:

- Add U+2013 en dash to the existing Note-number punctuation variants, preserving
  source text and raw offsets. Do not globally rewrite query/body punctuation.
- Admit complete bare-number note titles such as `2. Acquisitions` only within an
  eligible source-observed notes region. Require an exact standalone Notes to
  Consolidated Financial Statements parent title (including an explicit continued
  form if supported), rather than a prose mention. Best Buy's real title is on p43;
  the longer reference on p27 must not establish eligibility. Those page numbers
  are review examples, never implementation constants. Clear eligibility at source
  Item/contents/signature/exhibit/report boundaries. Use generic title/number syntax
  and log ambiguous rejected candidates; do not whitelist acquisitions/legal text.

That region flag controls recognition only. It does not carry heading text, values,
year or currency across many pages and is not a retained condition-C ledger. Keep
the existing one-page heading-text continuation limit and new-heading scope ends.
An exact generic rule and eligibility/reset behavior must be frozen before execution.
If bare-note syntax cannot be distinguished reliably from numbered lists in source
hard-negative checks, narrow/reject that case rather than admitting every numbered line.

Hold these components fixed: minimal original/expanded queries and financial rules,
stopwords/tokenizer/no stemming, original body BM25, k1=1.2/b=0.75, heading weight
0.25, 64 lexical heading tokens per page, duplicate/cap policies, one-page continuation,
full physical-page candidates including attachments/blanks, zero-based IDs and fixed
tie rule. Source input is doc/page/raw text only; no task labels, answers, justifications,
reviewed page roles or this casebook may guide recognition.

Newly recognized boundaries necessarily change active local scopes, admitted heading
tokens, cap competition and heading DF/average lengths. These are consequences of
the detector intervention, not reasons to pretend that the heading index is fixed.
The **body** index/scores stay fixed. Log source pointers, boundary changes and
context/query/index cost so the effect can be traced.

Do not bundle a generic-title cleanup or stricter consolidated-statement grammar
into this first run. Those false-positive cases remain known limitations with
separate hypotheses. Also defer weight searches, company-term suppression, role
cleanup, query synonyms/stemming, adjacency, family selection and ledger retention.
This controlled step tests note coverage, not total detector perfection.

## Evaluation and decision rules

Before a run, inspect source-only examples across companies and non-evidence pages:
explicit notes with varied dashes, bare-number notes, contents references, numeric
tables, numbered non-note lists, wrapped prose and attachment boundaries. Verify
raw spans, proper eligibility and preservation of resets. Label this as development
source validation, not held-out heading performance or PDF geometry ground truth.

For the actual run, require all original/stopword/expansion and section-v1 outputs
to reproduce before accepting S2. Save source context and full predictions before
loading gold annotations. Use the same 24 questions, k=1/3/5 and page budget.
Measure macro Recall@5, hit and complete coverage, paired gains/regressions, deeper
gold-page ranks, MRR and the five multi-page subgroup. Record whether acquisitions
and legal titles are detected and whether their source scopes/continuations improve;
assess token/cap changes and unexpected new candidates separately from task scores.

Recovering valid headings without a retrieval gain would still separate detector
coverage from matching/ranking as the bottleneck. Do not then infer a memory benefit
or simply increase the weight. Correct-but-unmatched Boeing/PepsiCo cases need a
future matching hypothesis; the two-statement financial gaps need a separate coverage
or selection hypothesis. Those later choices should follow this ablation's real
outputs, not be combined into it or reported as already evaluated.

No expected rank, recall or answer-accuracy gain is claimed. No proposed policy has
been implemented or run. Expansion v1 and the completed section-v1 result remain
fixed; this recommendation is development-only and makes no generalization claim.
