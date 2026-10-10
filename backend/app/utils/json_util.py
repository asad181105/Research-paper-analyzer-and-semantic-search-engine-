import json
import re
from typing import Any


def parse_json_loose(text: str) -> Any:
    """Parse JSON from an LLM response, repairing common issues."""
    if not text:
        raise ValueError("empty response")
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        candidate = text[start : end + 1]
        candidate = re.sub(r",\s*}", "}", candidate)
        candidate = re.sub(r",\s*]", "]", candidate)
        return json.loads(candidate)
    raise ValueError("could not parse JSON from model output")
