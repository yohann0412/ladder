"""Score every rung output of a conflicting pair and write one RungScore record per output."""

from dataclasses import dataclass

from ladder.entitymap import FileEntities, file_entities
from ladder.equivalence import Truth, against_truth, every, load_truth
from ladder.intent import intent_drops
from ladder.jsonio import read_optional, write_record
from ladder.layout import Layout
from ladder.markers import has_markers
from ladder.mergeable import is_mergeable, new_duplicates
from ladder.pairsides import PairSides, PathSides, load_sides
from ladder.rungoutputs import ResolvedState, RungOutput, ScoreError, materialise, rung_outputs
from ladder.runtime import RuntimeDir, remove_tree, runtime_for
from ladder.schemas import FileScore, GitRungResult, IntentDrop, RungScore, Runnability, Side
from ladder.scoretests import PairTests
from ladder.syntax import Parsed, parse, parses
from ladder.trees import find_workspace, workspace_repo


@dataclass(frozen=True)
class PairContext:
    """What every output of one pair is scored against: its sides, its truth, its suite."""

    pair_id: str
    sides: PairSides
    truth: Truth | None
    tests: PairTests

    def score(self, output: RungOutput, state: ResolvedState) -> RungScore:
        """Return every metric of one materialised output."""
        resolved: dict[str, FileEntities] = {}
        files: list[FileScore] = []
        for item in self.sides.paths:
            data = state.read(item.path)
            parsed = None if data is None else parse(data, item.language)
            resolved[item.path] = file_entities(parsed)
            files.append(_file_score(item, data, parsed, resolved[item.path], self.truth))
        mergeable = is_mergeable(files, state.unresolved)
        drops = intent_drops(self.sides, resolved, state)
        outcomes = self.tests.outcomes(output.name, state.tree, mergeable)
        return RungScore(
            pair_id=self.pair_id,
            rung=output.rung,
            run=output.run,
            available=True,
            unavailable_reason=None,
            mergeable=mergeable,
            human_equivalent=every(file.human_equivalent for file in files),
            human_equivalent_unordered=every(file.human_equivalent_unordered for file in files),
            intent_preserved_a=_preserved(drops, "a"),
            intent_preserved_b=_preserved(drops, "b"),
            intent_drops=drops,
            files=files,
            tests_full=outcomes.full,
            tests_a=outcomes.a,
            tests_b=outcomes.b,
        )


def score_pair(layout: Layout, pair_id: str) -> list[RungScore]:
    """Score every output of a conflicting pair, write each record, and return the scores."""
    git_rung = _conflicted(layout, pair_id)
    workspace = find_workspace(layout, pair_id, "replay")
    sides = load_sides(workspace_repo(workspace), git_rung)
    runnability = read_optional(layout.result_file(pair_id, "runnability"), Runnability)
    tests = PairTests(layout, runnability, workspace, sides)
    context = PairContext(pair_id, sides, load_truth(layout, pair_id), tests)
    runtime = runtime_for(layout, pair_id)
    scores: list[RungScore] = []
    for output in rung_outputs(layout, pair_id, git_rung):
        score = _score_output(context, runtime, output)
        write_record(layout.result_file(pair_id, output.name), score)
        scores.append(score)
    return scores


def _score_output(context: PairContext, runtime: RuntimeDir, output: RungOutput) -> RungScore:
    """Score one output in a fresh scratch tree; the tree and any env are deleted afterwards."""
    if output.source is None:
        return _unavailable(context.pair_id, output)
    label = output.name
    runtime.clear(label)
    try:
        return context.score(output, materialise(output.source, runtime.tree(label)))
    finally:
        remove_tree(runtime.tree(label))
        remove_tree(runtime.env(label))


def _conflicted(layout: Layout, pair_id: str) -> GitRungResult:
    record = read_optional(layout.result_file(pair_id, "rung-git"), GitRungResult)
    if record is None:
        raise ScoreError(f"{pair_id} has no git rung record; run ladder rung git {pair_id}")
    if record.status == "clean":
        raise ScoreError(f"{pair_id}: clean pair: nothing to score")
    if record.status != "conflicted":
        raise ScoreError(f"{pair_id}: git rung status {record.status}: nothing to score")
    return record


def _file_score(
    item: PathSides,
    data: bytes | None,
    parsed: Parsed | None,
    entities: FileEntities,
    truth: Truth | None,
) -> FileScore:
    equivalence = against_truth(item.path, data, item.language, truth)
    return FileScore(
        path=item.path,
        mode="token" if item.language is None else "ast",
        language=item.language,
        present=data is not None,
        has_markers=data is not None and has_markers(data),
        parses=None if parsed is None else parses(parsed),
        new_duplicates=new_duplicates(item, entities),
        human_equivalent=equivalence.equivalent,
        human_equivalent_unordered=equivalence.unordered,
        similarity=equivalence.similarity,
    )


def _preserved(drops: list[IntentDrop], side: Side) -> bool:
    return not any(drop.loser == side for drop in drops)


def _unavailable(pair_id: str, output: RungOutput) -> RungScore:
    return RungScore(
        pair_id=pair_id,
        rung=output.rung,
        run=output.run,
        available=False,
        unavailable_reason=output.unavailable_reason,
        mergeable=False,
        human_equivalent=None,
        human_equivalent_unordered=None,
        intent_preserved_a=None,
        intent_preserved_b=None,
        intent_drops=[],
        files=[],
        tests_full=None,
        tests_a=None,
        tests_b=None,
    )
