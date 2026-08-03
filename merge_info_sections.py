"""
merge_info_sections.py
----------------------
Info_Fixed_Bug 파일의 [Section] 태그를 병합한다.

인라인 형식:
    [Generic] BUG 123 - ...
    [Generic] BUG 456 - ...

병합 형식:
    [Generic]
    BUG 123 - ...
    BUG 456 - ...

사용법:
  python merge_info_sections.py Info_Fixed_Bug_For_19.32....txt
  python merge_info_sections.py input.txt output.txt
"""

import re
import sys

TAGGED_BUG_PAT = re.compile(r'^(\s+)\[([^\]]+)\]\s+BUG\s+(\d+)(\s+-\s*.*)$')
SECTION_HEADER_PAT = re.compile(r'^(\s+)\[([^\]]+)\]\s*$')
PLAIN_BUG_PAT = re.compile(r'^(\s+)BUG\s+(\d+)(\s+-\s*.*)$')


def merge_section_lines(lines):
    """
    연속된 동일 [Section] BUG 라인을 Section 헤더 1줄 + BUG 라인들로 병합한다.
  이미 병합된 파일에 재실행해도 동일한 결과를 유지한다.
    """
    merged = []
    current_section = None
    section_bugs = []
    indent = "     "
    in_header_group = False

    def flush():
        nonlocal current_section, section_bugs, in_header_group
        if current_section and section_bugs:
            merged.append(f"{indent}[{current_section}]\n")
            for bug_num, rest in section_bugs:
                merged.append(f"{indent}BUG {bug_num}{rest}\n")
        current_section = None
        section_bugs = []
        in_header_group = False

    for line in lines:
        stripped = line.rstrip('\n')

        tagged = TAGGED_BUG_PAT.match(stripped)
        if tagged:
            in_header_group = False
            indent, section, bug_num, rest = (
                tagged.group(1), tagged.group(2), tagged.group(3), tagged.group(4),
            )
            if section != current_section:
                flush()
                current_section = section
                section_bugs = [(bug_num, rest)]
            else:
                section_bugs.append((bug_num, rest))
            continue

        header = SECTION_HEADER_PAT.match(stripped)
        if header:
            flush()
            indent, current_section = header.group(1), header.group(2)
            section_bugs = []
            in_header_group = True
            continue

        plain = PLAIN_BUG_PAT.match(stripped)
        if plain:
            indent, bug_num, rest = plain.group(1), plain.group(2), plain.group(3)
            if in_header_group and current_section is not None:
                section_bugs.append((bug_num, rest))
            else:
                flush()
                merged.append(line)
            continue

        flush()
        merged.append(line)

    flush()
    return merged


def merge_info_file(info_path, output_path=None):
    """Info 파일의 [Section] BUG 라인을 Section 헤더 병합 형식으로 변환."""
    if output_path is None:
        output_path = info_path
    with open(info_path, encoding='utf-8') as fin:
        merged = merge_section_lines(fin)
    with open(output_path, 'w', encoding='utf-8') as fout:
        fout.writelines(merged)
    return len(merged)


def count_section_groups(lines):
    """병합 결과 통계: Section 헤더 수, 인라인 태그 잔존 수."""
    headers = 0
    inline = 0
    for line in lines:
        s = line.rstrip('\n')
        if SECTION_HEADER_PAT.match(s):
            headers += 1
        elif TAGGED_BUG_PAT.match(s):
            inline += 1
    return headers, inline


if __name__ == '__main__':
    if len(sys.argv) not in (2, 3):
        print(
            '사용법:\n'
            '  python merge_info_sections.py <Info파일>\n'
            '  python merge_info_sections.py <입력Info파일> <출력Info파일>'
        )
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) == 3 else input_file

    print(f'Section 병합 중: {input_file}')
    with open(input_file, encoding='utf-8') as fin:
        before = list(fin)
    inline_before = sum(1 for line in before if TAGGED_BUG_PAT.match(line.rstrip('\n')))

    line_count = merge_info_file(input_file, output_file)

    with open(output_file, encoding='utf-8') as fin:
        after = list(fin)
    headers, inline_after = count_section_groups(after)

    print(f'  인라인 [Section] BUG: {inline_before} -> {inline_after}')
    print(f'  Section 헤더: {headers}개')
    print(f'  출력: {output_file} ({line_count}줄)')
