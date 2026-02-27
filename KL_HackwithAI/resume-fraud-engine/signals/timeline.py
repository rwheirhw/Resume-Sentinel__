import re
from datetime import datetime

import dateparser


DATE_TOKEN = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)[\s,.-]*\d{4}|\b\d{1,2}/\d{4}\b|\b\d{4}\b"
)
RANGE_PATTERN = re.compile(
    rf"(?P<start>{DATE_TOKEN})\s*(?:-|–|—|to)\s*(?P<end>{DATE_TOKEN}|present|current|now)",
    flags=re.IGNORECASE,
)


def _parse_date(value: str):
    value = (value or "").strip()
    if value.lower() in {"present", "current", "now"}:
        return datetime.utcnow()
    return dateparser.parse(value)


def _extract_ranges(raw_text: str):
    ranges = []
    for match in RANGE_PATTERN.finditer(raw_text or ""):
        start_raw = match.group("start")
        end_raw = match.group("end")
        start_date = _parse_date(start_raw)
        end_date = _parse_date(end_raw)
        if start_date and end_date and start_date <= end_date:
            ranges.append((start_date, end_date, start_raw, end_raw, match.group(0)))
    return ranges


def _overlap(a_start, a_end, b_start, b_end):
    return a_start <= b_end and b_start <= a_end


def timeline_signals(raw_text: str) -> dict:
    text = raw_text or ""
    intervals = _extract_ranges(text)

    overlap_count = 0
    overlapping_pairs = []

    for i in range(len(intervals)):
        for j in range(i + 1, len(intervals)):
            a_start, a_end, a_s_raw, a_e_raw, _ = intervals[i]
            b_start, b_end, b_s_raw, b_e_raw, _ = intervals[j]
            if _overlap(a_start, a_end, b_start, b_end):
                overlap_count += 1
                overlapping_pairs.append(
                    {
                        "first": f"{a_s_raw} - {a_e_raw}",
                        "second": f"{b_s_raw} - {b_e_raw}",
                    }
                )

    overlap_score = min(overlap_count * 20, 40)

    intern_lines = []
    senior_lines = []
    for line in text.splitlines():
        lower_line = line.lower()
        line_ranges = _extract_ranges(line)
        if not line_ranges:
            continue
        if "intern" in lower_line or "internship" in lower_line:
            intern_lines.extend(line_ranges)
        if "full time" in lower_line or "engineer" in lower_line or "developer" in lower_line:
            senior_lines.extend(line_ranges)

    intern_flag = False
    for intern_entry in intern_lines:
        for senior_entry in senior_lines:
            if _overlap(intern_entry[0], intern_entry[1], senior_entry[0], senior_entry[1]):
                intern_flag = True
                break
        if intern_flag:
            break

    return {
        "overlap_count": int(overlap_count),
        "overlapping_pairs": overlapping_pairs,
        "intern_flag": bool(intern_flag),
        "timeline_score": int(overlap_score),
    }
