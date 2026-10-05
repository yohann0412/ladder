# ladder

When two AI coding agents open pull requests against the same repository at the same
time, their changes can conflict. `ladder` measures how far up a ladder of increasingly
capable merge tools those conflicts have to climb before they are resolved:

1. **git**: the default three-way merge (`git merge-tree`, diff3);
2. **structural**: the free structural merge drivers [weave](https://www.npmjs.com/package/@ataraxy-labs/weave)
   and [mergiraf](https://mergiraf.org), run as git merge drivers;
3. **LLM**: a fresh-context resolver agent that sees both PRs' descriptions and the
   conflicted files, either from git's markers (llm-raw) or from what weave left
   (llm-post-weave).

Every rung's output is compared with the resolution the maintainers actually merged:
mergeable, equivalent under a normalized syntax tree, and whether it drops a change one of
the PRs made (intent). Where a test suite runs, it is also run on each side and on the
merge. The pairs come from the replication package of the agent-PR merge-conflict replay
study (Zenodo 10.5281/zenodo.21186464), plus a supplementary sample drawn from AIDev by a
fixed rule.

**Results are in [RESULTS.md](RESULTS.md); what could be wrong with them is in
[reviews/results.md](reviews/results.md).** In short (Claims A and B over 224 conflicting
agent-PR pairs, Claim C over 918 pairs that merge cleanly):

- **Claim A (the ladder resolves >= 90% the way maintainers did): falsified.** The
  practical ladder's accepted output matched the maintainers' merge in 22 of 78 pairs that
  have one (28%, 95% CI 19-39%). The oracle ladder reaches 36% and the best-case bound 40%.
  Human-equivalence was confirmed in 20 of 20 sampled verdicts.
- **Claim B (the LLM silently drops a PR's intent in >= 15% of pairs): holds by the
  pre-registered rule (36%), but calibration does not support it.** A reviewer agreed with
  0 of 6 sampled intent-dropped verdicts on LLM outputs. The line-based intent check misreads
  merges that combine or re-implement both sides.
- **Claim C (pairs that pass alone and fail together): not decided.** 120 of 918 clean pairs
  were attempted before the pre-registered time cut; only 6 could be decided (0 fail
  together, 95% CI 0-39%), too few to compare with the 1-12.5% human base rates. Only about
  one repository in sixteen has a test suite this harness can run green.

## 30-second quickstart

```sh
just setup                      # Python environment (uv)
just tools                      # pinned weave and mergiraf into .tools/
just fixture                    # a small synthetic repository with 10 scenarios
just ladder --fixture --no-llm  # git and structural rungs on every scenario
```

The last command prints one row per scenario and checks it against
`fixtures/expected.json`. Running the LLM rung needs an agent harness. See
[HOW_TO_RUN_LOCALLY.md](HOW_TO_RUN_LOCALLY.md), which also covers the full experiment.

## What it does not do

- It is not a merge tool. It measures merge tools, and it never resolves a conflict itself.
- It calls no LLM API and needs no API key. LLM resolutions come from subagents of a
  harness, and each one is audited from its transcript.
- It does not edit resolver outputs, re-run resolvers whose output looked wrong, or pick
  the best rung after the fact. The practical ladder (first mergeable rung, in a fixed
  order) decides the claims; the oracle ladder is reported only as an upper bound.
- It does not judge whether a merge is good in general. "Human-equivalent" means
  equivalent to what the maintainers merged, and "intent" means the changed lines and
  definitions of each PR survive.
- It does not sandbox the repositories whose tests it runs. Run Claim C and the
  tests-based scores only in a disposable machine.

## Repository map

| Path | What it holds |
|------|---------------|
| `src/ladder/` | the harness: one small module per job |
| `e2e/` | one end-to-end acceptance test per feature, against real git repositories |
| `fixtures/` | the deterministic fixture generator, expected outcomes, a recorded resolver run |
| `resolver/` | the fixed resolver prompt template and agent definition |
| `data/` | vendored pair sources, `pairs.json`, and every result record |
| `PLAN.md`, `PLAN_REVIEW.md`, `DECISIONS.md`, `RISKS.md` | the pre-registered plan, its review, decisions made on the way, risks |
| `LOG.md` | what happened, in order, including what went wrong |
| `reviews/` | a review of each feature and of each phase's protocol |

## License

MIT, see [LICENSE](LICENSE).
