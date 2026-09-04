# Knowing the Answer Is Not Enough: A Vietnamese Medical Multiple-Answer MCQ Benchmark with Derived Ground Truth

---

## Abstract

Medical question answering is evaluated almost exclusively in the single-answer
multiple-choice format, which asks a model which option is correct but never how many
are. We introduce a Vietnamese medical benchmark in the multiple-answer format: 9,368
items whose correct-answer set contains two to four options, released together with an
11,368-item mixed set in which the answer count cannot be inferred from the task
description.

The design problem for such a resource is where the ground truth comes from. Prompting a
strong model to author items makes the benchmark a measure of agreement with the
generator, and any systematic error in the generator becomes ground truth; expert
authoring does not reach the tens of thousands of items needed for stable per-subgroup
estimates. We take neither route. We **derive** multiple-answer items from single-answer
exam questions whose keys are already known, using four rule-based transformations that
exploit recurring structures in Vietnamese exam writing: negated stems (*"all of the
following EXCEPT"*), *"all of the above"* keys, letter-referencing keys (*"both A and
B"*), and options that are themselves comma-separated lists. Each transformation turns an
existing answer key into a multi-answer key deterministically, so the source item's
correctness guarantee transfers. A language model screens candidates, rewrites stems and
writes distractor text, but is never permitted to decide which options are correct; a
second, independent audit round then re-examines every assembled item in both directions,
asking which labelled-correct options are false and which labelled-incorrect options are
true.

From 17 exam files (160,194 items; 122,017 after global deduplication) we release **Set
A**, the 9,368 multi-answer items, and **Set B**, those items with 2,000 single-answer
items interleaved. Each ships an index-aligned single-answer control containing the
verbatim source questions, so differences between a set and its control are attributable
to format rather than to difficulty.

Seven models — four open-weight (0.6B–4B) and three API — span 1.8% to 50.0% exact match
on Set B, and the benchmark is far from saturated: 33.3% of items are solved by none of
them. Difficulty labels inherited from the source exams, never consulted during
construction, predict accuracy monotonically for every sufficiently capable model, an
independent validity signal. The format also isolates a failure that single-answer
evaluation hides. On the 2,000 single-answer items, GPT-4o-mini's selected set contains
the correct option for **90.5%** of items — the highest of all seven models — yet it
answers only **13.2%** exactly, because it selects a single option in just 15.0% of
cases; stating the answer count restores it to 63.5%. Enabling reasoning on the strongest
model moves exact match by one point (50.0% → 51.0%) while making cardinality calibration
worse, indicating that the deficit is not one of inference-time compute.

Data, evaluation harness, and per-item predictions for all seven models are released.

---

## 1. Introduction

Medical question answering benchmarks are near-universally single-answer multiple
choice: MedQA, MedMCQA, PubMedQA and the medical subsets of MMLU all present a stem, a
handful of options, and exactly one key. This format is convenient — scoring is
unambiguous, and random-guess baselines are trivial to compute — but it embeds an
assumption that does not hold in clinical practice. Real diagnostic and management
questions frequently have several defensible answers, and part of competence is knowing
how many.

Standard MCQ evaluation gives that information away for free. When the prompt states
that exactly one option is correct, a model that has narrowed the field to two
candidates and guesses between them is scored identically to a model that is certain.
Worse, a model that has correctly identified all the true statements is *penalised* if
it reports more than one. The format measures option ranking, not answer-set selection.

We argue that answer-set selection is separately measurable, separately deficient in
current models, and cheap to evaluate if the benchmark is constructed carefully.

**The construction problem.** The obvious way to build a multiple-answer benchmark is to
prompt a strong language model to write the items. This is circular: the resulting
benchmark measures agreement with the generating model, and any systematic error in the
generator becomes ground truth. The alternative — expert authoring — does not scale to
the tens of thousands of items needed for stable per-subgroup estimates.

Our approach is neither. We observe that large Vietnamese medical exam banks already
contain multiple-answer items in disguise. A question of the form *"All of the following
are risk factors for X, EXCEPT: …"* with key D asserts that options A, B and C are all
true. A question whose key is *"All of the above"* asserts the same of every other
option. A question whose four options are each comma-separated lists of findings draws
from a shared pool of concepts, and the key identifies which pool members belong. In
each case the multi-answer ground truth is **derived** from the existing answer key by a
deterministic rule, not authored. The source item's correctness guarantee transfers.

This shifts the role of the language model from author to filter. In our pipeline the
model screens candidates for whether a transformation is semantically sound, rewrites
negated stems into affirmative form, and writes distractor text where a transformation
removes options. It never selects the correct answers. The distinction matters: a
generated distractor that turns out to be true is a detectable defect (an independent
audit round flags it), whereas a generated *key* that is wrong is indistinguishable from
ground truth.

**The mixed-format design.** To measure cardinality calibration we need items where the
model does not know the answer count a priori. We therefore release a second benchmark
in which 2,000 single-answer items — drawn from the same source bank, disjoint from the
multi-answer items by three independent criteria — are shuffled into the multi-answer
pool, and the prompt states only that a question "may have one or more correct answers."
Because the 2,000 items also appear verbatim in the paired single-answer control, the
same model can be scored on the same questions with and without the cardinality hint.
The difference is a direct measurement of calibration cost.

**Contributions.**

1. A construction method that derives multiple-answer items from single-answer exam
   banks, keeping ground truth traceable to a human-authored answer key, with four
   transformation families and a two-round LLM screening and audit protocol
   (Section 3).
2. Two paired benchmarks in Vietnamese medicine — 9,368 multi-answer items and 11,368
   mixed items — each with an index-aligned verbatim single-answer control, permitting
   per-item paired comparison of format effects (Section 3.4).
3. An evaluation of seven models isolating cardinality calibration from knowledge, and
   showing the two dissociate sharply: the model with the highest answer coverage has
   nearly the lowest exact-match accuracy (Section 5).
4. Two validity analyses: source difficulty labels predict accuracy monotonically for
   all capable models, and cumulative multi-model coverage bounds the fraction of the
   benchmark that is unsolvable-or-mislabelled at 33.3% (Sections 5.2, 5.4).

---

## 2. Related Work

> *Skeleton — needs a literature pass. The claims below are the positioning arguments;
> each needs citations and a check that the characterisation is fair.*

**Medical QA benchmarks.** MedQA, MedMCQA, PubMedQA, MMLU medical subsets, MedExpQA.
Position: all single-answer; several are English-only or English-translated. Note any
Vietnamese medical QA resources and how they differ.

**Multiple-answer and set-valued evaluation.** Prior work on multi-label QA and on
partial-credit scoring. Position: exact-set-match as the primary metric, with Jaccard
and micro-F1 reported as partial-credit secondaries, and why exact match is the right
primary here.

**Benchmark construction with language models.** Self-Instruct-style generation,
LLM-as-judge, and the contamination and circularity critiques. Position: our use of the
model is restricted to filtering and distractor authoring; ground truth is never
model-selected. Contrast with fully generated benchmarks.

**Calibration and abstention.** Confidence calibration, selective prediction, "I don't
know" behaviours. Position: answer-set cardinality is a distinct and under-measured form
of calibration — a model can be well calibrated on per-option probabilities yet unable
to pick a threshold.

**Contamination.** Note that the source bank is not public, that the benchmark was built
offline, and that we deliberately avoided provider free tiers whose terms permit
training on submitted prompts.

---

## 3. Benchmark Construction

### 3.1 Source corpus and deduplication

The source is 17 exported files from a Vietnamese medical exam bank, 160,194 items in
the schema `{question, answer_optionA..E, correctAnswer, medicalTopic, difficultLevel}`.

Deduplication must be global rather than per-file: the exports overlap heavily. We
remove exact duplicates by SHA-1 over the normalised stem and option set, and
order-invariant duplicates by comparing the stem against the sorted option multiset.
Together these remove **30,913 items (19.3%)** — 24,519 exact and 6,394 reordered. A
further 7,264 items are dropped for having fewer than four options or an unparseable
key, leaving **122,017**.

One artefact deserves note because it silently leaks the answer. In 5,889 items every
option text is prefixed with its own letter (`"A. A. Chronic obstructive pulmonary
disease"`). Left in place, options carried over from the source would bear the prefix
while LLM-written distractors would not, letting a model identify the correct options
without reading them. We strip the prefix when at least two options carry a
position-matching marker, before computing the deduplication hash — which also merges
export variants that differ only by this prefix, raising detected duplicates from 29,797
to 30,913.

### 3.2 Four transformation families

| Family | Source pattern | Derivation | Candidates |
|---|---|---|---:|
| `negation` | stem contains *"EXCEPT"*, *"which is FALSE"* | key is the single false option; the other three become the correct set | 4,729 |
| `pool` | every option is a comma-separated list | merge list items into a shared option pool; the key's items become the correct set | 3,048 |
| `meta-all` | key is *"All of the above"* | remove the meta option; remaining options are all correct; LLM writes 2 distractors | 1,102 |
| `meta-letters` | key is *"Both A and B"* | correct set read off the letters; remaining options are human-authored distractors; LLM tops up | 900 |
| | | **Total** | **9,779** |

Mechanical filters run before any model call: decimal commas are protected before list
splitting; option pools that are predominantly numeric are rejected; pools whose options
do not share a concept vocabulary are rejected by an overlap threshold; ordered-sequence
and ranking items are detected by repeated items within an option and by identical item
sets across options; blank-slot stems and junk options are removed; and near-duplicate
stems are removed by blocked `SequenceMatcher` comparison.

For the `pool` family we accept pools of up to 8 items and then randomly trim to 5
options, retaining every correct item and dropping only distractors. Hard-capping at 5
during filtering would have retained 1,280 candidates; trimming afterwards retains
3,048 with the same final shape.

### 3.3 Two-round LLM protocol

All model calls use `Qwen3-32B-FP8` under vLLM with structured outputs and thinking
disabled.

**Round 1 (9,779 calls)** is family-specific: verify that a negation item is genuinely
negated and rewrite its stem affirmatively; write two distractors for the two meta
families; and for `pool`, judge whether the items are independently meaningful and flag
any *distractor that is in fact also correct*. Only removal is permitted — the model may
delete a pool item, never add one to the key. 9,778 of 9,779 responses parsed; 9,368
items survived construction.

**Round 2 (9,368 calls)** is uniform across families: the assembled item is presented
with its current correct/incorrect labels, and the model is asked, in both directions,
which labelled-correct options are actually wrong and which labelled-incorrect options
are actually right. This is the only stage that can catch *semantic* defects — no
syntactic rule knows that a particular distractor is a true statement.

Two failure modes in the audit output required handling. First, the model conflates the
two index lists: 26.5% of indices in the "labelled-correct but actually wrong" array
point at options already labelled incorrect. Such self-contradictory verdicts are
discarded rather than treated as evidence; counting them rejects 1,229 items
unnecessarily. Second, the audit is not position-neutral — it accepts items whose single
incorrect option sits last more often, raising the share of incorrect options at
position D from 21.6% to 24.0% (≈5σ). We therefore re-shuffle option positions *after*
the audit gate, which is safe because surviving items have no flagged label errors.

### 3.4 The two released benchmarks

**Set A** is the 9,368 multi-answer items. **Set B** adds 2,000 single-answer items drawn
verbatim from the source bank, disjoint from Set A by item hash, by `(source file, index)`
pair, and by near-duplicate stem matching against both the multi-answer items and their
originals; they are spread evenly at 117–118 items per source file. Items whose key is a
meta option are excluded, since those are multi-answer items in disguise.

Each set ships an **index-aligned single-answer control**: record *i* of the control is
the verbatim source question for record *i* of the benchmark. Differences between the two
are therefore attributable to format, not to item difficulty.

Option positions are shuffled twice with seeds derived from the item hash, and item order
once with a fixed seed. In Set B the incorrect-option position distribution is
A 4,697 / B 4,712 / C 4,918 / D 4,908 (and E 1,858, which occurs only in five-option
items) — no positional leak.

> **A caveat we report rather than hide.** The single-answer controls inherit a strong
> position bias from the source: 41.5% of Set A control keys are option D, because the
> `meta-all` and `meta-letters` families select items whose key is a meta option, and meta
> options are almost always written last (89.7% and 84.3% D respectively). Always-D scores
> 41.5% on that control. Aggregate control scores are therefore inflated; the paired
> per-item comparison, which is what we use, is unaffected.

---

## 4. Experimental Setup

Seven models, four datasets each — 41,472 items per model, 290,304 evaluations total.

| | |
|---|---|
| Open-weight | Qwen3-0.6B, Qwen3-4B, Gemma3-1B, Gemma3-4B — vLLM on a single A10 24GB |
| API | Gemini-2.5-Flash, DeepSeek-v4-Flash-0731, GPT-4o-mini — via OpenRouter |
| Decoding | `temperature = 0`; output constrained to a JSON schema whose enum is exactly the option letters of that item |
| Reasoning | disabled for all seven; `reasoning_tokens` measured and confirmed zero for the API models |
| API cost | $4.93 |

Constraining the output is essential for comparability: the open models run under
grammar-constrained decoding, so an unconstrained API model would be scored on a
different task. The primary metric is **exact set match**; Jaccard and micro-F1 are
reported as partial-credit secondaries.

**Models we could not evaluate, and why.** `gpt-5-mini` and `gemini-2.5-pro` return
`HTTP 400: "Reasoning is mandatory for this endpoint and cannot be disabled"`. Since the
open models run with thinking disabled, including a mandatory-reasoning model would
confound capability with inference-time compute. `grok-4.3` runs correctly but was
excluded on cost: it tokenises accented Vietnamese at 1.09 characters per token — 2.9×
worse than Gemini's 3.11 — making a full sweep $20.89 rather than the $11.47 implied by
its per-token price. **Tokeniser efficiency on the target language is a first-order cost
factor for non-English benchmarks and is not visible in published pricing.**

---

## 5. Results

### 5.1 Overall accuracy

| Model | Set A | Set B | Control A | Control B |
|---|---:|---:|---:|---:|
| Gemma3-1B | 2.1 | 1.8 | 37.5 | 37.0 |
| Qwen3-0.6B | 3.6 | 3.3 | 40.6 | 39.5 |
| Gemma3-4B | 20.5 | 16.3 | 50.2 | 49.3 |
| Qwen3-4B | 24.7 | 21.2 | 55.7 | 55.5 |
| GPT-4o-mini | 37.5 | 33.9 | 67.0 | 66.2 |
| DeepSeek-v4-Flash | 45.1 | 43.3 | 72.8 | 72.2 |
| Gemini-2.5-Flash | **51.9** | **50.0** | **77.6** | **77.1** |

Exact match, percent. The ranking is identical across all four datasets, so conclusions
do not depend on which set is reported. The spread on Set B is 28× (50.0 vs 1.8).

The two sub-2B models score below their own single-answer controls by more than an order
of magnitude — they do not merely perform poorly in the multi-answer format, they fail
at it.

### 5.2 Cardinality calibration dissociates from knowledge

On the 2,000 single-answer items in Set B, each model is scored twice: once in Set B,
where the prompt does not reveal the answer count, and once in the control, where it
states there is exactly one.

| Model | Told count | Not told | Δ | Selects exactly 1 | Key ⊆ selection |
|---|---:|---:|---:|---:|---:|
| Qwen3-0.6B | 33.1 | 1.2 | −31.9 | 1.9 | 56.9 |
| Gemma3-1B | 34.8 | 0.1 | −34.8 | 0.1 | 54.0 |
| Gemma3-4B | 45.0 | 4.7 | −40.4 | 7.4 | 71.6 |
| Qwen3-4B | 54.1 | 12.5 | −41.6 | 16.6 | 71.7 |
| **GPT-4o-mini** | 63.5 | 13.2 | **−50.2** | 15.0 | **90.5** |
| DeepSeek-v4-Flash | 67.4 | 41.4 | −26.0 | 52.1 | 82.0 |
| Gemini-2.5-Flash | **74.4** | **50.9** | −23.5 | **63.2** | 83.2 |

GPT-4o-mini is the clearest case. Its selected set contains the correct answer for 90.5%
of items — the highest of all seven models, above Gemini-2.5-Flash — yet it answers only
13.2% exactly, because it selects a single option in just 15.0% of cases. It has more of
the required knowledge than Gemini and converts far less of it into answers. The
capability gap is not knowledge; it is knowing when to stop.

Averaged over all of Set B, where the mean key size is 2.51, selection sizes range from
2.01 (Gemma3-1B) to 3.06 (GPT-4o-mini). Gemma3-1B selects exactly two options for
11,315 of 11,368 items (99.5%) regardless of the item — it is effectively blind to
cardinality. Gemini-2.5-Flash is closest to the target at 2.48 and matches the key size
on 61.1% of items.

### 5.3 Source difficulty labels are valid

The source records a `difficultLevel` field, written by the exam authors in 15 surface
forms which we normalise to four levels. The field is never consulted during
construction.

| Level | n | Qwen3-0.6B | Gemma3-1B | Gemma3-4B | Qwen3-4B | GPT-4o-mini | DeepSeek | Gemini |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 Easy | 2,405 | 4.2 | 2.0 | 17.5 | 26.2 | 35.6 | 49.8 | **57.0** |
| 2 Moderate | 7,496 | 3.1 | 1.7 | 16.5 | 21.0 | 34.6 | 42.9 | 49.6 |
| 3 Hard | 1,428 | 2.9 | 1.9 | 13.0 | 14.4 | 27.7 | 34.7 | 41.0 |
| 4 Very hard | 39 | 2.6 | 2.6 | 7.7 | 12.8 | 12.8 | 25.6 | 23.1 |

All five sufficiently capable models decline monotonically across levels 1–3. The two
sub-2B models do not, which is consistent with their failure being formatting rather than
comprehension. Level 4 contains 39 items and should not be read as a trend.

That an independently-authored difficulty annotation predicts accuracy for every capable
model is evidence that the derived items retain the semantic content of their sources.

### 5.4 How much headroom remains

Accumulating models from weakest to strongest, the fraction of Set B solved by no model
falls as follows:

```
Gemma3-1B 98.2 → +Qwen3-0.6B 96.4 → +Gemma3-4B 81.7 → +Qwen3-4B 69.8
          → +GPT-4o-mini 54.7 → +DeepSeek 41.5 → +Gemini 33.3
```

The four open models leave 69.8% unsolved; all seven leave **33.3%**. More than half of
what looked unsolvable was merely beyond small models.

The residual 33.3% is an upper bound on the union of genuinely hard items and items whose
inherited key is wrong. The audit round rejected 1,570 constructed items for having a
labelled-correct option that is actually false, so wrong inherited keys are known to be
present at a non-trivial rate; separating the two components requires manual review of a
sample, which we have not done.

---

## 6. Limitations

**Distractors are model-written and not expert-verified.** 1,985 items in Set B contain
distractors authored by Qwen3-32B. They are filtered for length, meta-phrasing, and
near-duplication against the correct options, and pass the round-2 audit, but no
clinician has reviewed them. Items carry a `qualityFlag` allowing them to be excluded.

**Ground truth is inherited, and the source is imperfect.** Our derivations preserve the
source answer key, including its errors. A concrete example found during inspection: an
item on short-acting insulin lists "duration 24 hours" as correct, where the correct
value is 6–8 hours. The audit round removes some such items but cannot remove all.

**The single-answer controls have a position bias** (41.5% key-D on Control A), inherited
from the meta-answer families. Aggregate control accuracy is inflated; paired per-item
analysis is not affected.

**Mandatory-reasoning models are excluded.** We could not evaluate `gpt-5-mini` or
`gemini-2.5-pro` under matched conditions. As reasoning becomes non-optional in frontier
APIs, "thinking disabled" may cease to be an achievable control condition, and the
benchmark protocol will need a second, reasoning-enabled track.

**Single language and single source bank.** All items derive from one Vietnamese exam
bank. The four transformation families exploit conventions of Vietnamese exam writing;
their yield in other languages is untested, though the negation and "all of the above"
patterns are cross-linguistically common.

**The transformations assume the source is internally consistent.** The `negation` family
assumes that if a stem asks for the false option, the other three are true. Many exam
items in practice ask for the *most* false option. This assumption is what round 2 is
designed to test, and it is why `negation` has the largest audit rejection count.

---

## 7–9. To be written

- **Discussion** — implications for medical QA evaluation; whether cardinality
  calibration is trainable; whether the format is worth adopting for other domains.
- **Conclusion**.
- **Ethics and release** — the source bank is not ours to publish; what is released is
  the derived benchmark, the harness, and per-item predictions. Note that we avoided
  provider free tiers whose terms permit training on submitted prompts, to keep the
  benchmark uncontaminated.

**Appendices** — full prompts for both LLM rounds and their JSON schemas; per-family
accuracy for all seven models; the difficulty × family cross-tabulation; reproduction
commands.

---

## Figures

| | |
|---|---|
| Fig. 1 | Accuracy of seven models across four datasets — `figures/01_bang_diem.png` |
| Fig. 2 | Cumulative coverage: fraction unsolved as models are added — `figures/05_tran_bo_de.png` |
| Fig. 3 | Accuracy by source difficulty label — `figures/02_do_kho.png` |
| Fig. 4 | Told vs not-told answer count, same 2,000 items — `figures/04_bao_truoc.png` |
| Fig. 5 | Knowledge (key ⊆ selection) vs exact match — `figures/06_kien_thuc_vs_hieu_chinh.png` |
| Fig. 6 | Selection-size distributions against the key — `figures/03_so_o_chon.png` |

Figure captions need writing; axis labels in the current renders are Vietnamese and must
be regenerated in English for submission — `make_figures.py` holds the labels in one place.
