"""Pick pairs out of a pair set by id."""

from collections.abc import Sequence

from ladder.schemas import Pair, PairSet


class UnknownPairError(LookupError):
    """A pair id is not in pairs.json."""


def find_pair(pair_set: PairSet, pair_id: str) -> Pair:
    """Return the pair with this id; raise UnknownPairError when there is none."""
    for pair in pair_set.pairs:
        if pair.pair_id == pair_id:
            return pair
    raise UnknownPairError(f"no pair {pair_id} in pairs.json")


def select_pairs(pair_set: PairSet, pair_ids: Sequence[str]) -> list[Pair]:
    """Return the pairs with these ids, in pairs.json order, each once."""
    wanted = {find_pair(pair_set, pair_id).pair_id for pair_id in pair_ids}
    return [pair for pair in pair_set.pairs if pair.pair_id in wanted]
