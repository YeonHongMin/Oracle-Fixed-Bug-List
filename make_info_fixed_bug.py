"""
make_info_fixed_bug.py
----------------------
Fixed_Bug_For_19.31.0.0.260421_20260503.txt 을 복사하여
Info_Fixed_Bug_For_19.31.0.0.260421_20260503.txt 를 생성하고,
KB850150 파일에서 추출한 Section 정보를 각 BUG 라인 앞에 [Section] 형태로 삽입한다.
"""

import re
import os

import sys


def extract_bug_section_map(kb_paths):
    """
    KB 파일들을 파싱하여 {bug_number: section_name} 딕셔너리를 반환한다.
    KB 파일 구조:
      > **Section Name**
      > <table ...>...<td>BUG_NUMBER</td>...
    """
    bug_to_section = {}

    # 굵은 섹션 헤더: > **Advance Queuing** 형태
    section_pat = re.compile(r'>\s+\*\*(.+?)\*\*\s*$')
    # <td> 안의 BUG 번호 (href 포함 또는 plain)
    bug_pat = re.compile(r'<td[^>]*>\s*(?:<a[^>]*>)?\s*(\d{5,9})\s*(?:</a>)?\s*(?:<strong>[A-Z]</strong>)?\s*</td>')

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
                        # 이미 등록된 것은 첫 번째 섹션 우선
                        if bug_num not in bug_to_section:
                            bug_to_section[bug_num] = current_section

    return bug_to_section


def make_info_file(source_path, output_path, bug_to_section):
    """
    source 파일을 읽어 BUG 라인마다 [Section] 태그를 앞에 붙여 output 파일에 저장.
    """
    # BUG 라인 패턴: "     BUG 30309807 - ..."
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
                    # "[Section] BUG 30309807 - DESCRIPTION..." 형태
                    new_prefix = prefix.replace("BUG", f"[{section}] BUG")
                    new_line = f"{new_prefix}{bug_num}{rest}\n"
                    matched += 1
                else:
                    new_line = line  # 섹션 정보 없는 BUG 는 그대로
                    unmatched += 1
                fout.write(new_line)
            else:
                fout.write(line)

    return matched, unmatched


if __name__ == "__main__":
    kb_files = sys.argv[1].split(',')
    source_file = sys.argv[2]
    output_file = sys.argv[3]
    
    print("1) KB 파일에서 Bug-Section 매핑 추출 중...")
    bug_to_section = extract_bug_section_map(kb_files)
    print(f"   추출된 Bug-Section 매핑: {len(bug_to_section)}건")

    print("2) Info 파일 생성 중...")
    matched, unmatched = make_info_file(source_file, output_file, bug_to_section)
    print(f"   Section 태그 추가 완료: {matched}건 매칭, {unmatched}건 미매칭")
    print(f"3) 완료: {output_file}")
