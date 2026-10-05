"""The error a command raises when acting would break the experiment's protocol."""


class RefusedError(RuntimeError):
    """A precondition of the resolver or truth protocol does not hold, so nothing is written."""
