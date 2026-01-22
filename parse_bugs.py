import xml.etree.ElementTree as ET
import glob
import zipfile
import io
import os
import re
from collections import OrderedDict


def _version_key(path):
    """
    파일 경로에서 버전 정보를 추출하여 자연 정렬용 키를 반환.
    예: 19.4 < 19.10 순서로 정렬되도록 숫자 튜플 생성.
    """
    # 파일명에서 확장자 제거
    name = os.path.splitext(os.path.basename(path))[0]

    # "RU_" 이후의 버전 문자열 추출 (없으면 전체 파일명 사용)
    version = name.split("RU_", 1)[1] if "RU_" in name else name

    # 버전 문자열에서 숫자만 추출하여 정수 튜플로 변환
    numbers = [int(part) for part in re.split(r"[^\d]+", version) if part.isdigit()]
    return tuple(numbers), version


def parse_bugs_from_zip(zip_path, output_file):
    """
    지정된 경로의 모든 ZIP 파일에서 inventory.xml을 파싱하여
    Fixed Bug 정보를 추출하고 결과 파일에 저장.
    """
    # 디렉터리 내 모든 ZIP 파일을 버전 순서대로 정렬
    zip_files = sorted(glob.glob(f"{zip_path}/*.zip"), key=_version_key)

    output_lines = []           # 출력할 라인들을 저장
    bug_positions = {}          # 이미 출력된 BUG 번호 추적 (중복 방지용)

    # 각 ZIP 파일 순회
    for zip_file in zip_files:
        with zipfile.ZipFile(zip_file, 'r') as z:
            # ZIP 내에서 inventory.xml 파일 목록 검색
            inventory_files = [name for name in z.namelist() if name.endswith('inventory.xml')]

            # 각 inventory.xml 파일 처리
            for inv_file in inventory_files:
                # XML 파일 읽기 및 파싱
                xml_content = z.read(inv_file)
                root = ET.parse(io.BytesIO(xml_content)).getroot()

                # patch_description 요소에서 패치 설명 텍스트 추출
                patch_desc = root.find('patch_description')
                patch_text = patch_desc.text if patch_desc is not None else ""

                # patch_description이 있는 경우에만 처리
                if patch_text:
                    # ZIP 파일명에서 표시용 버전 이름 생성
                    zip_name = os.path.splitext(os.path.basename(zip_file))[0]
                    display_name = zip_name.split("RU_", 1)[1] if "RU_" in zip_name else zip_name

                    # 버전 헤더와 패치 설명 추가
                    output_lines.append(f"### RU {display_name}\n")
                    output_lines.append(f" *** {patch_text}\n")

                    # XML 내 모든 bug 요소 순회
                    for bug in root.findall('.//bug'):
                        number = bug.get('number')
                        description = bug.get('description') or ""
                        line = f"     BUG {number} - {description}\n"

                        # 이미 출력된 BUG 번호는 건너뜀 (중복 제거)
                        if number in bug_positions:
                            continue

                        # 새로운 BUG 번호 기록 및 출력 라인 추가
                        bug_positions[number] = len(output_lines)
                        output_lines.append(line)

    # 결과를 파일에 저장
    with open(output_file, 'w', encoding='utf-8') as f:
        for line in output_lines:
            if line is not None:
                f.write(line)


if __name__ == "__main__":
    parse_bugs_from_zip(".", "result.txt")
    print("result.txt 파일이 생성되었습니다.")
