"""
Generation with Claude Haiku: answer ONLY from the sources, cite them, and say
NOT_FOUND when they don't contain the answer.

Needs ANTHROPIC_API_KEY in .env. Without it, generation is skipped and the
trace says so, so the rest of the pipeline still runs. Any API failure
(rate limit, outage, timeout) is also reported in the trace instead of
crashing the request: the visitor still sees the retrieval.
"""

import os

from ..config import ANTHROPIC_MODEL
from .assemble import Source, render

NOT_FOUND = "NOT_FOUND"
MAX_TOKENS = 1024  # room for low-effort thinking plus a 120-word answer

RULES = f"""Use only the numbered sources in the user's message. Do not use outside knowledge, even if you know the answer.
After every sentence that states a fact, cite the source(s) it came from in square brackets, like [S2] or [S1][S3].
If the sources do not contain the answer, reply with exactly {NOT_FOUND} and nothing else.
Keep answers under 120 words. Plain English."""

# What each library's sources are, and any house style for its answers.
SUBJECTS = {
    "ev": "You answer questions about 2026 electric cars, from the US EPA's test figures. Each source is a short "
          "card describing one car's range, efficiency, yearly running cost or home-charging time.\n"
          "When the question asks which cars are best, longest, cheapest, fastest or similar, answer with a short "
          "numbered list, one car per line with the number that matters and its citation, like "
          "\"1. Lucid Air G Touring XR AWD: 512 miles of range [S1]\". Keep the sources' order when the user's message "
          "says they are already sorted. Only list cars that fit the question.\n"
          "The sources give running costs, not purchase prices: if asked what a car costs to buy, say the sources "
          "don't include prices.",
}
DEFAULT_SUBJECT = "You answer questions from a library of documents."


def system_prompt(library: str) -> str:
    return f"{SUBJECTS.get(library, DEFAULT_SUBJECT)}\n\n{RULES}"


_client = None


def _get_client():
    """One client for the whole process: it reuses connections between requests."""
    global _client
    if _client is None:
        import anthropic

        # 30 s per attempt, 2 retries on 429/5xx/network errors (the SDK backs off between them).
        _client = anthropic.Anthropic(timeout=30.0, max_retries=2)
    return _client


def user_message(question: str, sources: list[Source], sorted_by: str | None = None) -> str:
    """sorted_by: what the rank stage sorted the sources by, e.g. "SUV · range · longest"."""
    note = f"\n\nThe sources are already sorted for this question ({sorted_by}), best first." if sorted_by else ""
    return f"Sources:\n\n{render(sources)}{note}\n\nQuestion: {question}"


def generate(question: str, sources: list[Source], library: str = "ev", sorted_by: str | None = None) -> dict:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return {"answer": None, "skipped": "ANTHROPIC_API_KEY is not set", "model": ANTHROPIC_MODEL}
    if not sources:
        return {"answer": NOT_FOUND, "model": ANTHROPIC_MODEL, "skipped": "no sources retrieved"}

    import anthropic

    try:
        response = _get_client().messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=MAX_TOKENS,
            output_config={"effort": "low"},  # a short grounded answer; low effort keeps it fast and cheap
            system=system_prompt(library),
            messages=[{"role": "user", "content": user_message(question, sources, sorted_by)}],
        )
    except anthropic.RateLimitError:
        return _failed("the AI is busy right now (rate limited); try again in a minute")
    except anthropic.APITimeoutError:
        return _failed("the AI took too long to reply")
    except anthropic.APIConnectionError:
        return _failed("could not reach the AI service")
    except anthropic.APIStatusError as e:
        return _failed(f"the AI service returned an error ({e.status_code})")

    if response.stop_reason == "refusal":
        return {"answer": None, "model": response.model, "skipped": "the model declined to answer"}
    if response.stop_reason == "max_tokens":
        return {"answer": None, "model": response.model, "skipped": "the answer was cut off before it finished"}
    text = "".join(b.text for b in response.content if b.type == "text").strip()
    return {
        "answer": text,
        "model": response.model,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }


def _failed(reason: str) -> dict:
    print(f"generation failed: {reason}")
    return {"answer": None, "model": ANTHROPIC_MODEL, "skipped": reason, "error": True}
