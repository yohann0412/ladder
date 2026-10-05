"""The git rung without a workspace: git merge-tree on the pair's original commits in its cache.

The repository cache is blob-less, so merge-tree lazily fetches only the blobs the merge reads.
merge-tree names each side after its argument, so the original commits' ids are relabeled
`a` and `b` in messages and paths: the record then equals the workspace rung's apart from
its detail.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from ladder.categories import categorize
from ladder.conflicts import conflict_messages, types_for_path
from ladder.gitio import GitError, run_git
from ladder.gitrung import git_record_name, git_result
from ladder.jsonio import write_record
from ladder.layout import Layout
from ladder.markers import conflict_regions
from ladder.mergework import RungError
from ladder.schemas import ConflictedFile, GitRungResult, HeadsKind, Pair
from ladder.workspace import Sources, UnusablePairError, source_commits

MERGE_TREE = (
    "-c",
    "merge.conflictStyle=diff3",
    "merge-tree",
    "--write-tree",
    "--messages",
    "--name-only",
    "-z",
)
METHOD = "git merge-tree on the original commits in the repository cache"


@dataclass(frozen=True)
class MergeTreeOutput:
    """What `git merge-tree --write-tree --messages --name-only -z` printed."""

    tree: str
    conflicted: list[str]
    messages: str


def run_git_rung_in_cache(layout: Layout, pair: Pair, heads: HeadsKind) -> GitRungResult:
    """Merge the pair's original b head into its a head in the cache; record and return it."""
    try:
        sources = source_commits(pair, heads)
    except UnusablePairError as error:
        raise RungError(str(error)) from error
    cache = layout.cache_dir(pair.repo)
    if not cache.is_dir():
        raise RungError(f"no repository cache at {cache}; run `ladder pairs resolve`")
    try:
        result = _merge(cache, pair.pair_id, heads, sources)
    except GitError as error:
        result = git_result(pair.pair_id, heads, "error", str(error))
    write_record(layout.result_file(pair.pair_id, git_record_name(heads)), result)
    return result


def merge_tree_args(heads: HeadsKind, sources: Sources) -> list[str]:
    """Return the merge-tree arguments; replay heads name the one recorded merge base."""
    base = [f"--merge-base={sources.base}"] if heads == "replay" else []
    return [*MERGE_TREE, *base, sources.a, sources.b]


def parse_merge_tree(stdout: bytes) -> MergeTreeOutput:
    """Split merge-tree's NUL-separated output; messages are joined as it prints them without -z."""
    fields = stdout.split(b"\0")
    names_end = fields.index(b"", 1)
    conflicted = [name.decode("utf-8", "replace") for name in fields[1:names_end]]
    messages: list[bytes] = []
    index = names_end + 1
    while index < len(fields) - 1:
        index += int(fields[index]) + 2
        messages.append(fields[index])
        index += 1
    text = b"".join(messages).decode("utf-8", "replace")
    return MergeTreeOutput(tree=fields[0].decode(), conflicted=conflicted, messages=text)


def relabel(text: str, labels: Mapping[str, str]) -> str:
    """Replace every commit id in the text with its label."""
    for commit, label in labels.items():
        text = text.replace(commit, label)
    return text


def _merge(cache: Path, pair_id: str, heads: HeadsKind, sources: Sources) -> GitRungResult:
    proc = run_git(merge_tree_args(heads, sources), cache, ok_codes=(0, 1))
    output = parse_merge_tree(proc.stdout)
    if proc.returncode == 0:
        detail = f"b merges into a cleanly ({METHOD})"
        return git_result(pair_id, heads, "clean", detail, merged_tree=output.tree)
    labels = {sources.a: "a", sources.b: "b"}
    messages = conflict_messages(relabel(output.messages, labels))
    regions = _regions(cache, output.tree, output.conflicted)
    paths = {relabel(path, labels): regions.get(path, 0) for path in output.conflicted}
    files = [
        ConflictedFile(
            path=path,
            types=types_for_path(path, messages),
            regions=paths[path],
            category=categorize(path),
        )
        for path in sorted(paths)
    ]
    detail = f"conflict messages: {len(messages)}, conflicted files: {len(files)} ({METHOD})"
    return git_result(pair_id, heads, "conflicted", detail, messages=messages, files=files)


def _regions(cache: Path, tree: str, paths: Sequence[str]) -> dict[str, int]:
    wanted = set(paths)
    blobs: dict[str, str] = {}
    for entry in run_git(["ls-tree", "-r", "-z", tree], cache).stdout.split(b"\0"):
        meta, _, name = entry.partition(b"\t")
        path = name.decode("utf-8", "replace")
        if path in wanted:
            _, kind, blob = meta.decode().split(" ")
            if kind == "blob":
                blobs[path] = blob
    contents = _read_blobs(cache, sorted(set(blobs.values())))
    return {path: conflict_regions(contents[blob]) for path, blob in blobs.items()}


def _read_blobs(cache: Path, blobs: Sequence[str]) -> dict[str, bytes]:
    if not blobs:
        return {}
    request = "".join(f"{blob}\n" for blob in blobs).encode()
    out = run_git(["cat-file", "--batch"], cache, stdin=request).stdout
    contents: dict[str, bytes] = {}
    start = 0
    for blob in blobs:
        header_end = out.index(b"\n", start)
        header = out[start:header_end].split(b" ")
        if len(header) != 3:
            raise GitError(f"git cat-file cannot read blob {blob}: {b' '.join(header).decode()}")
        size = int(header[2])
        contents[blob] = out[header_end + 1 : header_end + 1 + size]
        start = header_end + 2 + size
    return contents
