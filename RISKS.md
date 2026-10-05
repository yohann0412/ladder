# RISKS

Each risk: how it is detected, and the fallback.

| # | Risk | Detection | Fallback |
|---|------|-----------|----------|
| R1 | Dataset unreachable | `ladder pairs fetch-sources` exits non-zero and names the host | GitHub mirror, then Zenodo, then AIDev on Hugging Face; if all fail, `HANDOFF.md` with URLs and layout, finish the fixture, stop. Status: Zenodo and Hugging Face reachable, GitHub web/API 403. |
| R2 | Leakage of the human resolution to the resolver | F2 acceptance (3 commits, no remote, no hit for resolution content); transcript audit (D6); canary strings planted in the cache's future history for 3 real pairs and searched for in every resolver output | Any hit voids that pair's LLM results and is reported. |
| R3 | Leakage through the PR head itself (head already contains the resolution) | Contamination rule in `PLAN.md` 5.1; per-pair flag; count reported | Rewind; unrecoverable pairs leave the set with a reason. |
| R4 | Structural driver install fails | `just tools` exits non-zero; version check | npm wrapper then cargo for weave; cargo then release binary for mergiraf; else run without the rung and say so first in `RESULTS.md`. |
| R5 | Toolchains missing | adapter detection | Node, Python, Go only; others "unrunnable: missing toolchain". |
| R6 | Repos unrunnable at historical commits | two setup attempts per repo | Classify with a reason; AST metrics still use every pair; both denominators everywhere. |
| R7 | Human resolution is a rewrite | `truth_is_rewrite` rule in `PLAN.md` 5.1 | Report human-equivalence with and without those pairs. |
| R8 | Formatting noise | AST comparison strips it | Token mode where no pack exists, flagged per file. |
| R9 | Resolver variance | 30-pair double run | Below 80% agreement: say so, treat single-run numbers as noisy. |
| R10 | Selection bias of the runnable subset | side-by-side size, stars, language, test count | Shown in the report, not corrected. |
| R11 | Claim A denominator is tiny (23 both-merged conflicting pairs in the paper set before attrition) | count after F1b | Supplementary sample S with a pre-registered rule; report P and S separately and pooled. |
| R12 | Resolver breaks protocol (shell, web, paths) | transcript audit | Hard violation: "LLM: failed (protocol violation)", no re-run. |
| R13 | Resolver input too large (one paper pair has 905 conflicted files) | `prepare` computes file count and bytes | Above the cap (`DECISIONS.md`) the pair is "LLM: input exceeds cap", reported as a failure of the LLM rung, never silently dropped. |
| R14 | Subagent transcript format changes | `finalize` cannot parse it | Run recorded "audit impossible"; excluded from LLM metrics with the reason. |
| R15 | PR refs deleted or force-pushed since the paper | fetch failure; head differs from what the paper saw | Recorded as fetch failure; reconciliation explains the drift. |
| R16 | `merged_at` does not match any commit | truth locator finds nothing | "truth unlocated"; pair stays in intent metrics. |
| R17 | Criss-cross histories | more than one merge base | Flag `criss_cross`; first base used; reported. |
| R18 | Disk exhaustion from clones | `df` before each clone; clone size logged | Blob-less partial clones; delete caches of finished repos. |
| R19 | Orchestrator bias: the main model sees resolver outputs | process | Outputs are never edited; re-runs only as labeled whole-set runs; calibration verdicts are recorded before the totals are computed. |
| R20 | Implementation subagent reports success that did not happen | main model re-runs every acceptance test itself from the merged tree | Rejected until it passes in the main tree. |
