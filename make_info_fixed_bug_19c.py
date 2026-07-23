"""
make_info_fixed_bug_19c.py
--------------------------
19c 용 Info 생성기.

KB 체계:
  - DB: KB850150 Database 19 Release Updates and Revisions Bugs Fixed Lists
  - GI: KB718940 Grid Infrastructure 19 Release Updates and Revisions Bugs Fixed Lists
  - 보통 두 KB를 콤마로 함께 넘겨 COMBO Fixed_Bug 한 파일에 태깅한다.

파일명 규칙:
  Fixed: Fixed_Bug_For_<버전>_<날짜>.txt
  Info:   Info_Fixed_Bug_For_<버전>_<날짜>.txt

사용법:
  python make_info_fixed_bug_19c.py "KB850150....md,KB718940....md" \\
    Fixed_Bug_For_19.32.0.0.260721_20260723.txt \\
    Info_Fixed_Bug_For_19.32.0.0.260721_20260723.txt
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
            '사용법: python make_info_fixed_bug_19c.py '
            '"KB850150....md,KB718940....md" <Fixed_Bug파일> <Info출력파일>'
        )
        sys.exit(1)

    kb_files = [p.strip() for p in sys.argv[1].split(',') if p.strip()]
    source_file = sys.argv[2]
    output_file = sys.argv[3]

    print("1) [19c] KB 파일에서 Bug-Section 매핑 추출 중...")
    for kb_path in kb_files:
        print(f"   - {kb_path}")
    bug_to_section = extract_bug_section_map(kb_files)
    print(f"   추출된 Bug-Section 매핑: {len(bug_to_section)}건")

    print("2) [19c] Info 파일 생성 중...")
    matched, unmatched = make_info_file(source_file, output_file, bug_to_section)
    print(f"   Section 태그 추가 완료: {matched}건 매칭, {unmatched}건 미매칭")
    print(f"3) 완료: {output_file}")
