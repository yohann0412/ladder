"""Apply the pre-registered decision rules of PLAN.md section 1 to the headline rates."""

from dataclasses import dataclass

from ladder.ratefmt import phrase
from ladder.schemas import Rate, RungRow

CLAIM_A_THRESHOLD = 90.0
CLAIM_A_MIN_PAIRS = 10
INTENT_DROPPED_THRESHOLD = 15.0
TESTS_PASS_DROPPED_THRESHOLD = 10.0
HUMAN_BASE_RATE = 1.0
A_BEST_CASE = "A best case"
CLAIMS = ("A", A_BEST_CASE, "B", "C")


@dataclass(frozen=True)
class _Part:
    label: str
    rate: Rate
    threshold: float

    @property
    def met(self) -> bool:
        return self.rate.pct is not None and self.rate.pct >= self.threshold

    def describe(self) -> str:
        side = "at or above" if self.met else "below"
        return f"{self.label} in {phrase(self.rate)}, {side} {self.threshold:g}%"


def claim_a(practical: Rate) -> str:
    """Return the Claim A verdict from the practical ladder's human-equivalent rate."""
    return _claim_a(
        "Claim A", practical, "the practical ladder's accepted output was human-equivalent for"
    )


def claim_a_best_case(bound: Rate) -> str:
    """Return the Claim A verdict under the best-case bound of D20 and D21."""
    return _claim_a(
        "Claim A at its best-case bound (D20, D21)",
        bound,
        "counting every pair with an LLM run that failed only for reading its own output or for "
        "a cut-off transcript as human-equivalent, the practical ladder is human-equivalent on "
        "at most",
    )


def _claim_a(subject: str, rate: Rate, measured: str) -> str:
    if rate.pct is None:
        return f"{subject} is not measured: no conflicting pair has a located human resolution."
    found = f"{measured} {phrase(rate)} conflicting pairs with a located human resolution"
    side = "at or above" if rate.pct >= CLAIM_A_THRESHOLD else "below"
    reasons: list[str] = []
    if rate.denominator < CLAIM_A_MIN_PAIRS:
        reasons.append(f"there are fewer than {CLAIM_A_MIN_PAIRS} pairs")
    low, high = rate.ci_low or 0.0, rate.ci_high or 0.0
    if low < CLAIM_A_THRESHOLD / 100 < high:
        reasons.append("the interval straddles 90%")
    if reasons:
        return (
            f"{subject} is inconclusive: {found}; the point estimate is {side} the 90% threshold "
            f"but {' and '.join(reasons)}."
        )
    if side == "below":
        return f"{subject} is falsified: {found}, below the 90% threshold."
    return f"{subject} holds: {found}, at or above the 90% threshold."


def claim_b(llm_raw: RungRow | None) -> str:
    """Return the Claim B verdict from the llm-raw row's intent rates."""
    if llm_raw is None:
        return "Claim B is not measured: no pair has an llm-raw score."
    parts = [
        _Part("intent dropped", llm_raw.intent_dropped, INTENT_DROPPED_THRESHOLD),
        _Part(
            "tests pass but intent dropped",
            llm_raw.tests_pass_intent_dropped,
            TESTS_PASS_DROPPED_THRESHOLD,
        ),
    ]
    measured = [part for part in parts if part.rate.denominator > 0]
    unmeasured = [
        f"{part.label} not measured (0 outputs)" for part in parts if part not in measured
    ]
    if not measured:
        return (
            "Claim B is not measured: llm-raw produced an output for "
            f"{phrase(llm_raw.available)} conflicting pairs it was planned for."
        )
    details = "; ".join([*(part.describe() for part in measured), *unmeasured])
    if any(part.met for part in measured):
        held = " and ".join(part.label for part in measured if part.met)
        return f"Claim B holds on {held}: llm-raw outputs had {details}."
    if unmeasured:
        return f"Claim B is not supported by what was measured: llm-raw outputs had {details}."
    return f"Claim B is falsified: llm-raw outputs had {details}."


def claim_c(fails_together: Rate) -> str:
    """Return the Claim C statement: the rate against the human small-team base rate."""
    if fails_together.pct is None:
        return "Claim C is not measured: no clean pair has a decided Claim C record."
    side = "at or above" if fails_together.pct >= HUMAN_BASE_RATE else "below"
    text = (
        f"Claim C: {phrase(fails_together)} clean pairs pass alone and fail together, "
        f"{side} the 1% human small-team base rate."
    )
    if side == "at or above":
        text += " A merge queue already catches these; only automatic repair remains open."
    elif fails_together.numerator == 0 and (fails_together.ci_high or 0.0) < 0.01:
        text += " Zero positives with an upper bound below 1%: not a problem worth solving."
    return text


def verdicts(
    practical: Rate, best_case: Rate | None, llm_raw: RungRow | None, fails_together: Rate
) -> dict[str, str]:
    """Return the verdict sentences keyed A, B and C, with `A best case` when a bound is given."""
    claims = {"A": claim_a(practical)}
    if best_case is not None:
        claims[A_BEST_CASE] = claim_a_best_case(best_case)
    return {**claims, "B": claim_b(llm_raw), "C": claim_c(fails_together)}
