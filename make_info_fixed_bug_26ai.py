"""
make_info_fixed_bug_26ai.py
---------------------------
23ai / 26ai 용 Info 생성기.

KB 체계 (19c와 다름):
  - Bugs Fixed: KB781900 Database 26ai Release Updates Bugs Fixed Lists
    → 26ai부터 DB/GI Bugs Fixed 목록이 이 문서로 통합됨 (별도 GI KB 없음)
  - Known Issues: KB915346 등은 이슈 문서이며 Section 표 형식이 다를 수 있음
  - Fixed_Bug 입력은 DB/GI 분리:
      Fixed_Bug_For_<버전>_DB_<날짜>.txt
      Fixed_Bug_For_<버전>_GI_<날짜>.txt
  - Info 출력도 동일 규칙:
      Info_Fixed_Bug_For_<버전>_DB_<날짜>.txt
      Info_Fixed_Bug_For_<버전>_GI_<날짜>.txt

사용법:
  python make_info_fixed_bug_26ai.py "KB781900....md" \\
    Fixed_Bug_For_23.26.3.0.0_DB_20260723.txt Info_Fixed_Bug_For_23.26.3.0.0_DB_20260723.txt
  python make_info_fixed_bug_26ai.py "KB781900....md" \\
    Fixed_Bug_For_23.26.3.0.0_GI_20260723.txt Info_Fixed_Bug_For_23.26.3.0.0_GI_20260723.txt
"""

import re
import sys


def extract_bug_section_map(kb_paths):
    """
    KB 파일들을 파싱하여 {bug_number: section_name} 딕셔너리를 반환한다.
    """
    bug_to_section = {}

    section_pat = re.compile(r'>\s+\*\*(.+?)\*\*\s*$')
    bug_pat = re.compile(
        r'<td[^>]*>\s*(?:<a[^>]*>)?\s*(\d{5,9})\s*(?:</a>)?\s*(?:<strong>[A-Z]</strong>)?\s*</td>'
    )

    for kb_path in kb_paths:
        current_section = None
        with open(kb_path, encoding='utf-8') as f:
            for line in f:
                m = section_pat.search(line)
                if m:
                    current_section = m.group(1).strip()
                    continue
                if current_section:
                    for bm in bug_pat.finditer(line):
                        bug_num = bm.group(1)
                        if bug_num not in bug_to_section:
                            bug_to_section[bug_num] = current_section

    return bug_to_section


def make_info_file(source_path, output_path, bug_to_section):
    """
    source 파일을 읽어 BUG 라인마다 [Section] 태그를 앞에 붙여 output 파일에 저장.
    """
    bug_line_pat = re.compile(r'^(\s+BUG\s+)(\d+)(\s+-\s*.*)$')

    matched = 0
    unmatched = 0

    with open(source_path, encoding='utf-8') as fin, \
         open(output_path, 'w', encoding='utf-8') as fout:
        for line in fin:
            m = bug_line_pat.match(line.rstrip('\n'))
            if m:
                prefix, bug_num, rest = m.group(1), m.group(2), m.group(3)
                section = bug_to_section.get(bug_num)
                if section:
                    new_prefix = prefix.replace("BUG", f"[{section}] BUG")
                    new_line = f"{new_prefix}{bug_num}{rest}\n"
                    matched += 1
                else:
                    new_line = line
                    unmatched += 1
                fout.write(new_line)
            else:
                fout.write(line)

    return matched, unmatched


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(
            '사용법: python make_info_fixed_bug_26ai.py '
            '"KB781900....md" <Fixed_Bug_For_..._DB|GI_....txt> '
            '<Info_Fixed_Bug_For_..._DB|GI_....txt>'
        )
        sys.exit(1)

    kb_files = [p.strip() for p in sys.argv[1].split(',') if p.strip()]
    source_file = sys.argv[2]
    output_file = sys.argv[3]

    print("1) [26ai] KB 파일에서 Bug-Section 매핑 추출 중...")
    for kb_path in kb_files:
        print(f"   - {kb_path}")
    bug_to_section = extract_bug_section_map(kb_files)
    print(f"   추출된 Bug-Section 매핑: {len(bug_to_section)}건")

    print("2) [26ai] Info 파일 생성 중...")
    matched, unmatched = make_info_file(source_file, output_file, bug_to_section)
    print(f"   Section 태그 추가 완료: {matched}건 매칭, {unmatched}건 미매칭")
    print(f"3) 완료: {output_file}")
    print(
        "참고: KB는 important bugs만 수록. inventory Fixed Bug 전부가 "
        "태깅되지 않는 것은 정상이다."
    )
