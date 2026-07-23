"""
make_info_fixed_bug_11g.py
--------------------------
11.2.0.4 (11g) 전용 Info 생성기.

Fixed_Bug 텍스트에 KB(KB866924 DB PSU / KB513423 GI PSU) Section 태그를 붙인다.
설명 fuzzy 매칭(토큰 + SequenceMatcher)과 OCW/ACFS/OJVM 패치 컨텍스트를 사용한다.

19c 는 make_info_fixed_bug_19c.py, 23ai/26ai 는 make_info_fixed_bug_26ai.py 를 사용한다.
"""

import re
import sys
from difflib import SequenceMatcher


REFERENCED_BUG_PATTERN = re.compile(
    r"(?:fix(?:es)?\s+for\s+)?bug\s+(\d{5,9})",
    re.IGNORECASE,
)
FIX_FOR_BUG_PATTERN = re.compile(
    r"^\s*FIX\s+FOR\s+BUG\s+(\d{5,9})\s*$",
    re.IGNORECASE,
)
PATCH_LINE_PATTERN = re.compile(r"^\s+\*\*\*\s+(.+)$")
SEQUENCE_MATCH_THRESHOLD = 0.85
SEQUENCE_MATCH_THRESHOLD_BY_CONTEXT = {
    "DATABASE": 0.80,
}
SECTION_CONTEXT = {
    "Oracle Universal Storage Management": "ACFS",
    "Oracle Portable ClusterWare": "OCW",
    "Oracle Utilities": "OCW",
    "Miscellaneous Issues": "OCW",
}
PATCH_CONTEXT_FALLBACK = {
    "OJVM": "OJVM",
}
DEFAULT_KB_FILES_11G = (
    "KB866924 11.2.0.4 Patch Set Updates - List of Fixes in each PSU.md",
    "KB513423 11.2.0.4 Grid Infrastructure Patch Set Updates - List of Fixes in each GI PSU.md",
)
KB_FILE_ALIASES = {
    "KB866924": DEFAULT_KB_FILES_11G[0],
    "KB513423": DEFAULT_KB_FILES_11G[1],
    "DB": DEFAULT_KB_FILES_11G[0],
    "GI": DEFAULT_KB_FILES_11G[1],
}


def _strip_html(text):
    text = re.sub(r"&(?:gt|lt|amp|quot|nbsp);", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return text


def _normalize_text(text):
    text = _strip_html(text)
    text = text.upper()
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _tokenize(text):
    normalized = _normalize_text(text)
    return {token for token in normalized.split() if len(token) > 2}


def _is_section_header(name):
    lowered = name.lower()
    skip_prefixes = (
        "for details",
        "for known issues",
        "bugs fixed",
        "the table below",
        "please see",
        "copyright",
        "be the first",
        "11.2.0.4 patch set update fixes",
        "11.2.0.4 grid infrastructure patch set update fixes",
    )
    if any(lowered.startswith(prefix) for prefix in skip_prefixes):
        return False
    if "document:" in lowered:
        return False
    return True


def _extract_bug_ids(text):
    bug_ids = set()
    patterns = (
        re.compile(
            r"<(?:td|p)[^>]*>\s*(?:<a[^>]*>)?\s*(\d{5,9})\s*(?:</a>)?\s*(?:<strong>[^<]*</strong>)?\s*(?:</p>)?\s*</(?:td|p)>",
            re.I,
        ),
        re.compile(r"\|\s*[^|]+\|\s*(\d{5,9})\s*(?:\*\*[^|]*)?\s*\|"),
        re.compile(r">\s*(\d{5,9})\s*<"),
    )
    for pattern in patterns:
        bug_ids.update(pattern.findall(text))
    bug_ids.update(re.findall(r"(?:id|documentId)=(\d{5,9})", text, flags=re.I))
    bug_ids.update(REFERENCED_BUG_PATTERN.findall(text))
    return bug_ids


def _extract_description_from_row(row):
    cells = re.findall(r"<(?:td|p)[^>]*>(.*?)</(?:td|p)>", row, flags=re.I | re.S)
    if len(cells) >= 3:
        return _normalize_text(cells[-1])

    if len(cells) == 2:
        first_cell = _strip_html(cells[0]).strip()
        if re.fullmatch(r"(?:KI\d+|\d{5,9})", first_cell, flags=re.I):
            return _normalize_text(cells[1])

    if "|" in row and row.count("|") >= 3:
        parts = [part.strip() for part in row.split("|") if part.strip()]
        if len(parts) >= 3 and re.fullmatch(r"(?:KI\d+|\d{5,9})", parts[-2], flags=re.I):
            return _normalize_text(parts[-1])
        if len(parts) == 2 and re.fullmatch(r"(?:KI\d+|\d{5,9})", parts[0], flags=re.I):
            return _normalize_text(parts[1])
    return None


def _kb_component(kb_path, section_name):
    if "Grid Infrastructure" in kb_path or "GI PSU" in kb_path or "KB513423" in kb_path:
        return SECTION_CONTEXT.get(section_name, "OCW")
    return "DATABASE"


def _detect_patch_context(patch_line):
    upper = patch_line.upper()
    if "OJVM" in upper:
        return "OJVM"
    if "ACFS" in upper:
        return "ACFS"
    if "OCW" in upper or "GRID INFRASTRUCTURE" in upper or "CLUSTERWARE" in upper:
        return "OCW"
    if "DATABASE" in upper:
        return "DATABASE"
    return None


def _section_matches_context(section, component, patch_context):
    if not patch_context:
        return True
    if patch_context == "OJVM":
        return False
    entry_component = component or SECTION_CONTEXT.get(section, "DATABASE")
    return entry_component == patch_context


def _register_description_maps(
    description,
    section,
    component,
    desc_to_section,
    desc_token_entries,
    desc_sequence_entries,
):
    if not description:
        return

    if description not in desc_to_section:
        desc_to_section[description] = section

    tokens = _tokenize(description)
    if len(tokens) >= 3:
        # (tokens, description, section, component) — SequenceMatcher 후보 축소용
        desc_token_entries.append((tokens, description, section, component))
    desc_sequence_entries.append((description, section, component))


def _find_section_by_description(
    description,
    bug_to_section,
    desc_to_section,
    desc_token_entries,
    desc_sequence_entries,
    patch_context=None,
):
    normalized = _normalize_text(description)
    if not normalized:
        return None

    section = desc_to_section.get(normalized)
    if section and _section_matches_context(section, None, patch_context):
        return section

    fix_match = FIX_FOR_BUG_PATTERN.match(normalized)
    if fix_match:
        return bug_to_section.get(fix_match.group(1))

    for ref_bug in REFERENCED_BUG_PATTERN.findall(description):
        section = bug_to_section.get(ref_bug)
        if section and _section_matches_context(section, None, patch_context):
            return section

    desc_tokens = _tokenize(description)
    best_section = None
    best_score = 0.0
    # SequenceMatcher는 토큰 겹침 상위 후보만 (전체 KB×버그 O(N*M) 방지)
    sequence_candidates = []
    if len(desc_tokens) >= 3:
        for entry in desc_token_entries:
            kb_tokens, kb_desc, section, component = entry
            if not kb_tokens or not _section_matches_context(section, component, patch_context):
                continue
            overlap = len(desc_tokens & kb_tokens) / len(desc_tokens | kb_tokens)
            if overlap > best_score and overlap >= 0.55:
                best_score = overlap
                best_section = section
            if overlap >= 0.35:
                sequence_candidates.append((overlap, kb_desc, section))

    # 토큰 매칭이 충분하면 SequenceMatcher 생략
    if best_section:
        return best_section

    if not sequence_candidates:
        return None

    sequence_candidates.sort(key=lambda item: item[0], reverse=True)
    best_ratio = 0.0
    best_ratio_section = None
    for _, kb_desc, section in sequence_candidates[:30]:
        ratio = SequenceMatcher(None, normalized, kb_desc).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_ratio_section = section

    threshold = SEQUENCE_MATCH_THRESHOLD_BY_CONTEXT.get(
        patch_context, SEQUENCE_MATCH_THRESHOLD
    )
    if best_ratio >= threshold:
        return best_ratio_section

    return None


def _normalize_kb_path(path):
    path = path.strip()
    return KB_FILE_ALIASES.get(path.upper(), path)


def _is_11g_source(source_file):
    lowered = source_file.lower()
    return "11.2.0.4" in lowered or "11204" in lowered or "11g" in lowered


def resolve_kb_files(kb_arg, source_file):
    """
    11.2.0.4 입력은 DB(KB866924) + GI(KB513423) KB를 모두 사용한다.
    """
    kb_arg = (kb_arg or "").strip()
    if kb_arg.lower() in {"", "auto", "11g", "11.2.0.4", "default"}:
        return list(DEFAULT_KB_FILES_11G)

    resolved = []
    seen = set()
    for raw_path in kb_arg.split(","):
        path = _normalize_kb_path(raw_path)
        if not path or path in seen:
            continue
        seen.add(path)
        resolved.append(path)

    if _is_11g_source(source_file):
        for path in DEFAULT_KB_FILES_11G:
            if path not in seen:
                resolved.append(path)
                seen.add(path)

    return resolved


def extract_bug_section_map(kb_paths):
    """
    KB 파일들을 파싱하여 Bug/Section 매핑을 반환한다.

    Returns:
        tuple[dict, dict, list, list]: (
            {bug_number: section_name},
            {normalized_description: section_name},
            [(token_set, section_name, component), ...],
            [(normalized_description, section_name, component), ...],
        )
    """
    bug_to_section = {}
    desc_to_section = {}
    desc_token_entries = []
    desc_sequence_entries = []

    section_pat = re.compile(r"(?:^>\s*)?\*\*(.+?)\*\*\s*$")

    for kb_path in kb_paths:
        current_section = None
        current_component = None
        with open(kb_path, encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line[1:].lstrip() if raw_line.startswith(">") else raw_line
                section_match = section_pat.search(line.strip())
                if section_match and "<table" not in line.lower():
                    section_name = section_match.group(1).strip()
                    if _is_section_header(section_name):
                        current_section = section_name
                        current_component = _kb_component(kb_path, section_name)
                    continue

                if not current_section:
                    continue

                rows = re.split(r"<tr[^>]*>", line, flags=re.I)
                if len(rows) == 1 and "|" in line:
                    rows = [line]

                for row in rows:
                    if not row.strip():
                        continue

                    description = _extract_description_from_row(row)
                    _register_description_maps(
                        description,
                        current_section,
                        current_component,
                        desc_to_section,
                        desc_token_entries,
                        desc_sequence_entries,
                    )

                    for bug_num in _extract_bug_ids(row):
                        if bug_num not in bug_to_section:
                            bug_to_section[bug_num] = current_section

    return bug_to_section, desc_to_section, desc_token_entries, desc_sequence_entries


def make_info_file(
    source_path,
    output_path,
    bug_to_section,
    desc_to_section=None,
    desc_token_entries=None,
    desc_sequence_entries=None,
):
    """
    source 파일을 읽어 BUG 라인마다 [Section] 태그를 앞에 붙여 output 파일에 저장.
    """
    bug_line_pat = re.compile(r"^(\s+)(?:\[[^\]]+\]\s+)?BUG\s+(\d+)(\s+-\s*.*)$")

    matched = 0
    unmatched = 0
    desc_to_section = desc_to_section or {}
    desc_token_entries = desc_token_entries or []
    desc_sequence_entries = desc_sequence_entries or []
    current_patch_context = None

    with open(source_path, encoding="utf-8") as fin, open(output_path, "w", encoding="utf-8") as fout:
        for line in fin:
            stripped = line.rstrip("\n")
            patch_match = PATCH_LINE_PATTERN.match(stripped)
            if patch_match:
                current_patch_context = _detect_patch_context(patch_match.group(1))
                fout.write(line)
                continue

            match = bug_line_pat.match(stripped)
            if not match:
                fout.write(line)
                continue

            prefix, bug_num, rest = match.group(1), match.group(2), match.group(3)
            description = rest[3:] if rest.startswith(" - ") else rest

            section = bug_to_section.get(bug_num)
            if section and not _section_matches_context(
                section, SECTION_CONTEXT.get(section), current_patch_context
            ):
                section = None

            if not section:
                section = _find_section_by_description(
                    description,
                    bug_to_section,
                    desc_to_section,
                    desc_token_entries,
                    desc_sequence_entries,
                    current_patch_context,
                )

            if not section and current_patch_context:
                section = PATCH_CONTEXT_FALLBACK.get(current_patch_context)

            if section:
                new_line = f"{prefix}[{section}] BUG {bug_num}{rest}\n"
                matched += 1
            else:
                new_line = f"{prefix}BUG {bug_num}{rest}\n"
                unmatched += 1
            fout.write(new_line)

    return matched, unmatched


if __name__ == "__main__":
    # 사용법:
    #   python make_info_fixed_bug_11g.py [KB목록|auto] <Fixed_Bug파일> <Info출력파일>
    #   python make_info_fixed_bug_11g.py auto Fixed_Bug_For_11.2.0.4....txt Info_....txt
    if len(sys.argv) < 3:
        print(
            "사용법: python make_info_fixed_bug_11g.py [KB목록|auto] "
            "<Fixed_Bug파일> <Info출력파일>"
        )
        sys.exit(1)

    if len(sys.argv) == 3:
        kb_arg = "auto"
        source_file = sys.argv[1]
        output_file = sys.argv[2]
    else:
        kb_arg = sys.argv[1]
        source_file = sys.argv[2]
        output_file = sys.argv[3]

    kb_files = resolve_kb_files(kb_arg, source_file)

    print("1) [11g] KB 파일에서 Bug-Section 매핑 추출 중...")
    for kb_path in kb_files:
        print(f"   - {kb_path}")
    bug_to_section, desc_to_section, desc_token_entries, desc_sequence_entries = (
        extract_bug_section_map(kb_files)
    )
    print(f"   추출된 Bug-Section 매핑: {len(bug_to_section)}건")
    print(f"   추출된 Description-Section 매핑: {len(desc_to_section)}건")
    print(f"   토큰 기반 Description 후보: {len(desc_token_entries)}건")
    print(f"   SequenceMatcher Description 후보: {len(desc_sequence_entries)}건")

    print("2) [11g] Info 파일 생성 중...")
    matched, unmatched = make_info_file(
        source_file,
        output_file,
        bug_to_section,
        desc_to_section,
        desc_token_entries,
        desc_sequence_entries,
    )
    print(f"   Section 태그 추가 완료: {matched}건 매칭, {unmatched}건 미매칭")
    print(f"3) 완료: {output_file}")