"""Draft a check-in message in the coach's voice.

The coach always reviews and sends. Nothing here contacts a member.

If ``ANTHROPIC_API_KEY`` is set and the ``anthropic`` package is installed, drafts are
written by Claude from the member's top signals. Otherwise, or if the call fails, a
deterministic template is used so the pipeline never blocks on the model.

The message never mentions scores, monitoring or "the system". It reads like a coach
who noticed, because that is what it is standing in for.
"""

from __future__ import annotations

import os
import re

from retention_radar.models import RiskAssessment, SignalHit

DEFAULT_MODEL = os.getenv("RADAR_MODEL", "claude-sonnet-5-5")

_SYSTEM = (
    "You write short check-in messages from a health coach at a longevity clinic to a "
    "member who has drifted. Warm, specific, human. Under 70 words. Plain sentences. "
    "No em dashes. No medical advice. Never mention scores, tracking, monitoring, data "
    "flags or any system. Offer one small concrete next step and make replying easy."
)


def _span(days: int) -> str:
    if days < 10:
        return "about a week"
    if days < 18:
        return "a couple of weeks"
    if days < 25:
        return "about three weeks"
    return "about a month"


def _days_in(hit: SignalHit) -> int:
    m = re.search(r"(\d+) days", hit.detail)
    return int(m.group(1)) if m else 14


_LINES = {
    "wearable_gap": lambda h: f"Your tracker has been quiet for {_span(_days_in(h))}.",
    "unanswered_messages": lambda h: "I know my last few notes may have gotten buried.",
    "habit_slip": lambda h: (
        "The last couple of weeks looked different from your usual. That's completely normal."
    ),
    "missed_lab": lambda h: (
        "Looks like the lab draw slipped. I can book an at-home draw at a time that suits you."
    ),
    "coach_gap": lambda h: "It's been too long since we properly caught up. That's on me.",
}


def template_draft(a: RiskAssessment) -> str:
    first = a.name.split()[0]
    lines = [f"Hi {first}, {a.coach} here."]
    lines += [_LINES[h.signal](h) for h in a.hits[:2] if h.signal in _LINES]
    lines.append("Want 15 minutes this week to reset the plan? I'll keep it simple.")
    return " ".join(lines)


def _clean(text: str) -> str:
    text = text.strip().strip('"')
    text = re.sub(r"\s*[—–]\s*", ". ", text)
    return re.sub(r"\s+", " ", text)


def llm_draft(a: RiskAssessment, model: str = DEFAULT_MODEL) -> str:
    import anthropic  # optional dependency

    client = anthropic.Anthropic()
    reasons = "\n".join(f"- {h.detail}" for h in a.hits) or "- No specific signals"
    prompt = (
        f"Member first name: {a.name.split()[0]}\n"
        f"Coach name: {a.coach}\n"
        f"Days until renewal: {a.days_to_renewal}\n"
        f"What the coach noticed:\n{reasons}\n\n"
        "Write the message the coach will send. Return only the message."
    )
    resp = client.messages.create(
        model=model,
        max_tokens=300,
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    return _clean(text)


def draft_checkin(a: RiskAssessment, use_llm: bool | None = None) -> str:
    """Best available draft. ``use_llm=None`` means use the model when a key is set."""
    if use_llm is None:
        use_llm = bool(os.getenv("ANTHROPIC_API_KEY"))
    if use_llm:
        try:
            return llm_draft(a)
        except Exception:  # network, auth, missing package: fall back, never block
            pass
    return template_draft(a)
