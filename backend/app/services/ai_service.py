"""AI Voyage Summary (Section 7): turns a vessel's recorded movement timeline into a
plain-language narrative, e.g. "Vessel arrived at China Port A on 20 Jul, departed on 23 Jul,
arrived at Pasir Gudang on 27 Jul, and sailed the same day at 2300 hrs." The proposal's Figure 3
sketches this as a panel on the vessel history page, which is where it's surfaced.

This is the one place in Phase 6 where a model is genuinely the right tool: turning a list of
timestamped events into readable prose is a language task. The *facts* still come entirely from
stored StatusEvents - the prompt below passes the timeline and instructs the model not to add
anything beyond it, so the summary stays a rendering of real data rather than a source of new
claims. Delay/exception detection deliberately stays rule-based; see exception_detector.py.

Unavailable rather than broken when ANTHROPIC_API_KEY isn't set - the same posture as PDF
extraction (services/pdf_extraction.py), which callers turn into a clear 503.
"""

import logging

from anthropic import Anthropic, APIError

from app.config import settings
from app.models import StatusEvent, Vessel

logger = logging.getLogger("ai_service")

# Kept modest on purpose: this is a short narrative paragraph, not a report. Well under the
# non-streaming threshold where request timeouts start to matter.
MAX_TOKENS = 1024

SYSTEM_PROMPT = (
    "You write short factual voyage summaries for a vessel monitoring dashboard used by port "
    "operations staff.\n\n"
    "Write one paragraph of plain language describing the vessel's movements, in chronological "
    "order. Refer to dates the way an operator would speak them (e.g. '20 Jul', '27 Jul at "
    "23:00').\n\n"
    "Use only the events given to you. Do not infer cargo, delays, reasons for a movement, or "
    "anything else the events do not state. If the timeline is very short, write a "
    "correspondingly short summary rather than padding it. No preamble, no bullet points, no "
    "heading - return only the paragraph itself."
)


def is_configured() -> bool:
    """Whether voyage summaries can actually be generated on this deployment. The frontend uses
    this (via the API) to decide whether to offer the button at all, rather than offering one
    that always fails."""
    return bool(settings.anthropic_api_key)


def _format_timeline(vessel: Vessel, events: list[StatusEvent]) -> str:
    """Render the vessel and its events as the plain-text block handed to the model. Kept
    deliberately simple and stable - one event per line, oldest first, so the model's input is
    an obvious transcription of what the history page shows."""
    header = f"Vessel: {vessel.name} (IMO {vessel.imo_number})\n"
    header += f"Destination: {vessel.destination_port or 'not set'}\n\nEvents (oldest first):\n"
    lines = [
        f"- {event.occurred_at.strftime('%d %b %Y, %H:%M')} UTC — {event.last_event_text} "
        f"(location: {event.current_location}, source: {event.source_name})"
        for event in events
    ]
    return header + "\n".join(lines)


def generate_voyage_summary(vessel: Vessel, events: list[StatusEvent]) -> str:
    """Generate the narrative for one vessel. Raises RuntimeError when unavailable (no API key,
    nothing to summarise, or the API call failed) so the router can turn each into a clear
    response instead of a half-rendered panel."""
    if not is_configured():
        raise RuntimeError("ANTHROPIC_API_KEY is not configured; AI voyage summaries are unavailable")
    if not events:
        raise RuntimeError("This vessel has no tracking events yet, so there is no voyage to summarise")

    client = Anthropic(api_key=settings.anthropic_api_key)
    try:
        response = client.messages.create(
            model=settings.ai_summary_model,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _format_timeline(vessel, events)}],
        )
    except APIError as exc:
        # Network/API failures surface as a clear "try again" rather than a 500 - the vessel
        # history page itself must keep working whether or not this panel does.
        logger.exception("voyage summary generation failed for vessel %s", vessel.imo_number)
        raise RuntimeError(f"Could not generate the summary: {exc}") from exc

    # Safety classifiers can decline a request (HTTP 200, stop_reason "refusal") - check before
    # reading content, which is empty or partial in that case.
    if response.stop_reason == "refusal":
        raise RuntimeError("The summary request was declined by the model's safety system")

    text = "".join(block.text for block in response.content if block.type == "text").strip()
    if not text:
        raise RuntimeError("The model returned an empty summary")
    return text
