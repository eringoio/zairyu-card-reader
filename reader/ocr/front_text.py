"""Front-side OCR text normalisation and field parsing.

Pure text processing: these helpers take text a local OCR engine already produced and
derive reviewed field candidates from it. Nothing here touches an image, the filesystem,
a subprocess, or the network.
"""

from __future__ import annotations

import re

from reader.parsing.address_splitter import PREFECTURES

JAPANESE_CHARS = r"\u3040-\u30ff\u3400-\u9fff"
KATAKANA_CHARS = r"\u30a0-\u30ff"


class OcrError(Exception):
    """A local OCR or image-decoding step could not complete."""


def normalize_ocr_text(text: str) -> str:
    text = repair_mojibake(text)
    replacements = {
        "\u3000": " ",
        "｜": "|",
        "：": ":",
        "．": ".",
        "，": ",",
    }
    normalized = text
    for source, target in replacements.items():
        normalized = normalized.replace(source, target)
    normalized = re.sub(r"[ \t]+", " ", normalized)
    return normalized.strip()


def _japanese_character_count(text: str) -> int:
    return len(re.findall(f"[{JAPANESE_CHARS}]", text))


def repair_mojibake(text: str) -> str:
    markers = ("ã", "æ", "ç", "å", "ï")
    if not any(marker in text for marker in markers):
        return text
    best = text
    best_count = _japanese_character_count(text)
    for encoding in ("cp1252", "latin1"):
        try:
            candidate = text.encode(encoding).decode("utf-8")
        except UnicodeError:
            continue
        candidate_count = _japanese_character_count(candidate)
        if candidate_count > best_count:
            best = candidate
            best_count = candidate_count
    return best


def compact_japanese_spacing(text: str) -> str:
    compacted = text
    for _ in range(3):
        compacted = re.sub(f"(?<=[{JAPANESE_CHARS}])\\s+(?=[{JAPANESE_CHARS}])", "", compacted)
        compacted = re.sub(f"(?<=[{JAPANESE_CHARS}])\\s+(?=\\d)", "", compacted)
        compacted = re.sub(f"(?<=\\d)\\s+(?=[{JAPANESE_CHARS}])", "", compacted)
        compacted = re.sub(r"(?<=\d)\s+(?=\d)", "", compacted)
    return compacted


def _format_date(year: str, month: str, day: str) -> str:
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"


def _extract_dates(text: str) -> list[str]:
    dates: list[str] = []
    text = compact_japanese_spacing(text)
    for match in re.finditer(r"(19\d{2}|20\d{2})\s*[年/\-.]?\s*(\d{1,2})\s*[月/\-.]?\s*(\d{1,2})\s*日?", text):
        try:
            dates.append(_format_date(match.group(1), match.group(2), match.group(3)))
        except ValueError:
            continue
    return dates


def _date_from_split_validity_lines(lines: list[str]) -> str:
    for index, line in enumerate(lines):
        current = compact_japanese_spacing(line)
        if not re.search(r"有効|VALIDITY|VALID", current, re.IGNORECASE):
            continue
        window = [compact_japanese_spacing(item) for item in lines[index + 1 : index + 5]]
        for offset, candidate in enumerate(window):
            partial = re.search(r"(20\d{2}|19\d{2})年(\d{1,2})月0?$", candidate)
            if partial is None:
                continue
            trailing = "".join(window[offset + 1 : offset + 3])
            day = re.search(r"(\d{1,2})日まで有効", trailing)
            if day is None:
                continue
            try:
                return _format_date(partial.group(1), partial.group(2), day.group(1))
            except ValueError:
                continue
    return ""


def _line_looks_like_heading(line: str) -> bool:
    upper = line.upper()
    blocked = [
        "RESIDENCE CARD",
        "STATUS",
        "PERIOD",
        "PERMISSION",
        "VALID",
        "CARD",
        "MINISTER",
        "在留カード",
        "日本国",
    ]
    return any(token in upper for token in blocked)


def _line_looks_like_address_start(line: str) -> bool:
    return bool(
        re.search(
            r"住居地|住所|Address|都|道|府|県|市|区|町|村|"
            r"郡|通|丁目|番地",
            line,
            re.IGNORECASE,
        )
    )


def _line_looks_like_other_front_field(line: str) -> bool:
    """Return true for a printed field label that cannot continue an address."""
    return bool(
        re.search(
            r"国籍|地域|生年月日|性別|在留資格|在留期間|在留期限|カード有効|"
            r"就労|資格外活動|許可日|番号|氏名|Nationality|Date.?Birth|Sex|"
            r"Status.?Residence|Period.?Stay|Card.?Expiry|Work.?Restriction|Name",
            line,
            re.IGNORECASE,
        )
    )


_NEXT_FRONT_FIELD_LABEL = re.compile(
    r"国籍(?:[・･ ]?地域)?|生年月日|性別|在留資格|在留期間|在留期限|カード有効|"
    r"就労|資格外活動|許可日|番号|氏名|Nationality(?:[ /]?Region)?|Date.?Birth|Sex|"
    r"Status.?Residence|Period.?Stay|Card.?Expiry|Work.?Restriction|Name",
    re.IGNORECASE,
)


def _without_trailing_front_field(text: str) -> str:
    """Keep only a field value when OCR joined the following label to its row."""
    match = _NEXT_FRONT_FIELD_LABEL.search(text)
    return text[: match.start()].strip(" :：/|　") if match else text.strip(" :：/|　")


def _line_looks_like_address_stop(line: str, status_candidates: list[str]) -> bool:
    if _line_looks_like_heading(line):
        return True
    if any(status in line for status in status_candidates):
        return True
    if _extract_dates(line):
        return True
    if _line_looks_like_other_front_field(line):
        return True
    return bool(
        re.search(
            r"就労|制限|許可|在留|期間|"
            r"有効|永住|定住|留学|PERIOD|STATUS|VALID",
            line,
            re.IGNORECASE,
        )
    )


def _clean_detached_address_prefix(line: str) -> str:
    if len(re.findall(f"[{KATAKANA_CHARS}]", line)) < 4:
        return ""
    if re.search(r"\u30aa\u30e9\u30f3\u30c0|\u30a2\u30e1\u30ea\u30ab|\u30a4\u30ae\u30ea\u30b9", line):
        return ""
    cleaned = re.sub(f"[^{KATAKANA_CHARS}\\u3400-\\u9fffA-Za-z0-9\\-]", "", line)
    return cleaned.strip("-")


def _restore_street_prefix(first_line: str, continuation: str) -> str:
    for match in reversed(list(re.finditer(r"([\u3400-\u9fff\u3040-\u30ff]+通)", first_line))):
        street = match.group(1)
        for start in range(max(0, len(street) - 8), len(street) - 1):
            suffix = street[start:]
            if len(suffix) > 1 and continuation.startswith(suffix[1:]):
                return suffix[0] + continuation
    return continuation


def _find_detached_address_prefix(
    compact_lines: list[str],
    address_start_index: int,
    current_parts: list[str],
    status_candidates: list[str],
) -> str:
    current_address = "\n".join(current_parts)
    for line in compact_lines[address_start_index + len(current_parts) :]:
        if line in current_parts or _line_looks_like_address_stop(line, status_candidates):
            continue
        if any(part and part in line for part in current_parts):
            continue
        prefix = _clean_detached_address_prefix(line)
        if prefix and prefix not in current_address:
            return prefix
    return ""


def _guess_address(compact_lines: list[str], status_candidates: list[str]) -> str:
    for index, line in enumerate(compact_lines):
        if not _line_looks_like_address_start(line):
            continue
        # A recognizer can join an address and the next printed label into one row.  The
        # explicit address label still makes this a valid starting point; its value is
        # trimmed below before the following label can be added.
        if _line_looks_like_address_stop(line, status_candidates) and not re.search(r"住居地|住所|Address", line, re.IGNORECASE):
            continue

        first = _without_trailing_front_field(_clean_labeled_value(line, [r"住居地|住所|Address"]))
        parts = [first] if first else []
        for continuation in compact_lines[index + 1 :]:
            if _line_looks_like_address_stop(continuation, status_candidates):
                break
            if _japanese_character_count(continuation) == 0 and not re.search(r"\d", continuation):
                break
            if continuation:
                value = _without_trailing_front_field(continuation)
                if value:
                    parts.append(value)
                if value != continuation:
                    break
            # The address may be one line; continuing into an unrelated unlabelled
            # Japanese field is less safe than returning the already complete address.
            if re.search(r"(?:丁目|番地|号|\d[-−]\d)", "".join(parts)):
                break
        if len(parts) >= 2:
            prefix = _find_detached_address_prefix(compact_lines, index, parts, status_candidates)
            if prefix:
                parts[-1] = prefix + _restore_street_prefix(parts[0], parts[-1])
        return "\n".join(parts)
    return ""


def _guess_name(lines: list[str], birth_line_index: int | None) -> str:
    labeled = _guess_labeled_value(lines, r"氏名|Name")
    if labeled:
        cleaned = re.sub(r"[^A-Za-z ,.'-]", "", labeled).strip(" ,")
        if len(cleaned) >= 4:
            return cleaned
    candidates = lines[: birth_line_index if birth_line_index is not None else min(len(lines), 5)]
    for line in candidates:
        cleaned = re.sub(r"[^A-Za-z ,.'-]", "", line).strip(" ,")
        if len(cleaned) >= 5 and not _line_looks_like_heading(line):
            return cleaned
    return ""


def _clean_labeled_value(line: str, labels: list[str]) -> str:
    value = compact_japanese_spacing(line)
    for label in labels:
        value = re.sub(label, "", value, flags=re.IGNORECASE)
    value = value.strip(" :：/|　")
    return value


def _line_after_label(lines: list[str], index: int) -> str:
    for candidate in lines[index + 1 : index + 3]:
        cleaned = compact_japanese_spacing(candidate).strip(" :：/|　")
        if cleaned and not _line_looks_like_heading(cleaned):
            return cleaned
    return ""


def _guess_labeled_value(lines: list[str], label_pattern: str) -> str:
    for index, line in enumerate(lines):
        compact_line = compact_japanese_spacing(line)
        if not re.search(label_pattern, compact_line, re.IGNORECASE):
            continue
        value = _clean_labeled_value(compact_line, [label_pattern])
        if value:
            return value
        return _line_after_label(lines, index)
    return ""


def _guess_nationality(lines: list[str], compact: str, birth_line_index: int | None) -> str:
    nationality_map = {
        "米国": "USA",
        "アメリカ": "USA",
        "中国": "CHINA",
        "韓国": "KOREA",
        "英国": "UNITED KINGDOM",
        "イギリス": "UNITED KINGDOM",
        "フランス": "FRANCE",
        "ドイツ": "GERMANY",
        "オランダ": "オランダ",
        "ネパール": "ネパール",
        "ベトナム": "ベトナム",
        "フィリピン": "フィリピン",
        "ブラジル": "ブラジル",
        "インドネシア": "インドネシア",
        "ミャンマー": "ミャンマー",
    }
    label_pattern = r"国籍(?:[・･ ]?地域)?|Nationality(?:[ /]?Region)?"
    labeled = ""
    for index, line in enumerate(lines):
        match = re.search(label_pattern, compact_japanese_spacing(line), re.IGNORECASE)
        if match:
            # Extract after the matched label, rather than removing the label globally:
            # an OCR row may contain the preceding address as well as the country value.
            labeled = compact_japanese_spacing(line)[match.end() :]
            if not labeled:
                labeled = _line_after_label(lines, index)
            break
    if labeled:
        labeled = _without_trailing_front_field(labeled)
        candidate = _normalize_nationality_candidate(labeled, nationality_map)
        if candidate:
            return candidate

    for label, value in nationality_map.items():
        if label in compact:
            return value

    if birth_line_index is not None:
        birth_line = lines[birth_line_index]
        tail = re.split(r"男|女|\bM\.?\b|\bF\.?\b|Male|Female", birth_line, flags=re.IGNORECASE)[-1]
        # A sex marker is never a country. Values after the marker can be English or
        # Japanese (for example, Katakana) but arbitrary Han-only OCR noise is rejected.
        return _normalize_nationality_candidate(tail, nationality_map)
    return ""


def _normalize_nationality_candidate(value: str, nationality_map: dict[str, str]) -> str:
    """Accept only an English or Japanese country candidate; never emit sex/Chinese noise."""
    compact_value = compact_japanese_spacing(value).strip(" :：/|　")
    for source, normalized in nationality_map.items():
        if source in compact_value:
            return normalized
    english = re.sub(r"[^A-Za-z .'-]", "", compact_value).strip(" .'-")
    if len(re.sub(r"\s+", "", english)) >= 3:
        return english
    # Katakana country names are Japanese. Do not pass through unrecognized Han-only text:
    # Japanese and Chinese share Han code points, so a bare sequence cannot be classified
    # safely without a country mapping.
    katakana = re.sub(r"[^\u30a0-\u30ffー ]", "", compact_value).strip()
    return katakana if len(katakana.replace(" ", "")) >= 2 else ""


def parse_front_ocr_text(text: str) -> dict[str, str]:
    normalized = normalize_ocr_text(text)
    lines = [line.strip() for line in normalized.splitlines() if line.strip()]
    compact_lines = [compact_japanese_spacing(line) for line in lines]
    compact = compact_japanese_spacing(" ".join(lines))
    dates = _extract_dates(compact)
    split_validity_date = _date_from_split_validity_lines(lines)

    birth_line_index: int | None = None
    for index, line in enumerate(lines):
        if _extract_dates(line) and re.search(r"男|女|\bM\.?\b|\bF\.?\b|Male|Female", line, re.IGNORECASE):
            birth_line_index = index
            break

    sex = ""
    if re.search(r"男|\bM\.?\b|Male", compact, re.IGNORECASE):
        sex = "M"
    if re.search(r"女|\bF\.?\b|Female", compact, re.IGNORECASE):
        sex = "F"

    status_candidates = [
        "永住者",
        "定住者",
        "留学",
        "家族滞在",
        "日本人の配偶者等",
        "永住者の配偶者等",
        "技術・人文知識・国際業務",
        "経営・管理",
        "高度専門職",
        "技能",
        "特定技能",
        "介護",
    ]
    residence_status = next((status for status in status_candidates if status in compact), "")

    work_restriction = ""
    for line in compact_lines:
        if re.search(r"就労|活動|不可|制限|指定書|許可", line):
            work_restriction = line
            break

    address = _guess_address(compact_lines, status_candidates)
    # A real Japanese address can be safely anchored at a prefecture. The full-card
    # recognizer otherwise occasionally joins a neighbouring field and creates a
    # convincing-looking but invalid fragment. Keep an anchored suffix only; do not pass
    # unclassified Han-only noise into the reviewed/copy fields.
    address_prefecture_match = next(
        (re.search(re.escape(prefecture), address) for prefecture in PREFECTURES if prefecture in address),
        None,
    )
    if address_prefecture_match:
        address = address[address_prefecture_match.start() :]
    elif address and not any(re.search(r"住居地|住所|Address", line, re.IGNORECASE) for line in compact_lines):
        address = ""
    address_strategy = (
        "explicit_label"
        if any(re.search(r"住居地|住所|Address", line, re.IGNORECASE) for line in compact_lines)
        else "address_pattern" if address else "unanchored_pattern_rejected"
    )

    nationality = _guess_nationality(lines, compact, birth_line_index)
    nationality_strategy = (
        "explicit_label"
        if any(re.search(r"国籍(?:[・･ ]?地域)?|Nationality(?:[ /]?Region)?", line, re.IGNORECASE) for line in compact_lines)
        else "fallback" if nationality else "not_found"
    )

    period_of_stay = ""
    residence_expiry_date = ""
    if residence_status == "永住者":
        period_of_stay = "無期限"
        residence_expiry_date = "該当なし"

    parsed = {
        "name": _guess_name(lines, birth_line_index),
        "birth_date": dates[0] if dates else "",
        "sex": sex,
        "nationality": nationality,
        "address": address,
        "residence_status": residence_status,
        "period_of_stay": period_of_stay,
        "residence_expiry_date": residence_expiry_date,
        "card_expiry_date": split_validity_date or (dates[-1] if len(dates) >= 2 else ""),
        "work_restriction": work_restriction,
        "front_ocr_address_strategy": address_strategy,
        "front_ocr_nationality_strategy": nationality_strategy,
        "front_ocr_text": normalized,
        "front_ocr_parse_note": "OCR candidates are machine-read from the protected front image; verify before export.",
    }
    return {key: value for key, value in parsed.items() if value}
