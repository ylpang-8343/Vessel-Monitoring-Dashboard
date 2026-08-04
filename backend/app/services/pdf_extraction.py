"""AI-assisted extraction of vessel rows from a PDF vessel list (Section 3.2).

Extracted rows are always returned for editable-preview review before import -
this module never writes to the database itself.
"""

import io

from anthropic import Anthropic
from pypdf import PdfReader

from app.config import settings

# Defines the exact shape we force the model to return via tool-use, rather than parsing free
# text - `tool_choice` below makes the model always call this tool instead of replying in prose.
EXTRACTION_TOOL = {
    "name": "record_vessel_rows",
    "description": "Record the vessel rows found in the document.",
    "input_schema": {
        "type": "object",
        "properties": {
            "rows": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": ["string", "null"], "description": "Vessel name, e.g. MV ABC"},
                        "imo_number": {
                            "type": ["string", "null"],
                            "description": "7-digit IMO number if present, digits only",
                        },
                        "destination_port": {
                            "type": ["string", "null"],
                            "description": "Destination port if mentioned, else null",
                        },
                    },
                    "required": ["name", "imo_number", "destination_port"],
                },
            }
        },
        "required": ["rows"],
    },
}


def extract_text(pdf_bytes: bytes) -> str:
    """Pull all plain text out of a PDF, page by page. Works best on text-based PDFs; scanned
    (image-only) PDFs will yield little or no text (see README/proposal Section 10's note about
    scanned PDFs needing more manual correction)."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def extract_vessel_rows(pdf_bytes: bytes) -> list[dict]:
    """Extract vessel rows (name/IMO/destination) from a PDF using Claude's tool-use, for the
    bulk-upload PDF path (Section 3.2).

    Raises RuntimeError if no Anthropic API key is configured - callers (routers/bulk_upload.py)
    turn that into a clear 503 "unavailable" response rather than a raw upload failure, since
    Excel/CSV upload should keep working regardless of whether this is configured.
    """
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not configured; PDF extraction is unavailable")

    text = extract_text(pdf_bytes)
    if not text.strip():
        # Nothing readable in the PDF (e.g. a scanned image) - return no rows rather than
        # calling the model on empty input.
        return []

    client = Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=4096,
        tools=[EXTRACTION_TOOL],
        tool_choice={"type": "tool", "name": "record_vessel_rows"},
        messages=[
            {
                "role": "user",
                "content": (
                    "Extract every vessel entry from this vessel list. For each vessel capture "
                    "its name, IMO number (7 digits, if present), and destination port (if "
                    "mentioned). If a field isn't present for a row, use null rather than "
                    "guessing.\n\n" + text
                ),
            }
        ],
    )

    # tool_choice forces exactly one tool_use block in the response, but content is still a
    # list - scan it defensively rather than assuming block index 0.
    for block in response.content:
        if block.type == "tool_use" and block.name == "record_vessel_rows":
            return block.input.get("rows", [])
    return []
