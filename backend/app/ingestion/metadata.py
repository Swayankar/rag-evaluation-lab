import re
from typing import Optional

_YEAR_RE = re.compile(r"(19|20)\d{2}")


def extract_year(document_id: str) -> Optional[int]:
    match = _YEAR_RE.search(document_id)
    return int(match.group()) if match else None
