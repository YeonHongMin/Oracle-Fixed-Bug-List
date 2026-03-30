import xml.etree.ElementTree as ET
import glob
import subprocess
import tempfile
import zipfile
import io
import os
import re
import sys
from datetime import datetime


# 7-Zip 경로 (Windows 기본 설치 경로)
SEVENZIP_PATH = r"C:\Program Files\7-Zip\7z.exe"


def _version_key(path):
    """
    파일 경로에서 버전 정보를 추출하여 자연 정렬용 키를 반환.
    예: GOLDIMG_DB_23.4.0.24.05.zip → (23, 4, 0, 24, 5)
    """
    name = os.path.splitext(os.path.basename(path))[0]

    # "GOLDIMG_DB_" 또는 "GOLDIMG_GI_" 이후의 버전 문자열 추출
    match = re.search(r'GOLDIMG_(?:DB|GI)_(.+)', name)
    version = match.group(1) if match else name

    # 버전 문자열에서 숫자만 추출하여 정수 튜플로 변환
    numbers = [int(part) for part in re.split(r"[^\d]+", version) if part.isdigit()]
    return tuple(numbers), version


def _list_inventory_files_7z(zip_path):
    """
    7z를 사용하여 ZIP 내 inventory.xml 파일 목록과 크기를 빠르게 조회.
    .patch_storage 경로는 제외.
    Returns: list of (filename, size) tuples
    """
    result = subprocess.run(
        [SEVENZIP_PATH, "l", "-slt", zip_path],
        capture_output=True, text=True, encoding='utf-8'
    )

    candidates = []
    current_path = None
    current_size = 0

    for line in result.stdout.splitlines():
        if line.startswith("Path = "):
            current_path = line[7:]
        elif line.startswith("Size = "):
            try:
                current_size = int(line[7:])
            except ValueError:
                current_size = 0

        # 한 엔트리의 정보가 모이면 inventory.xml 여부 확인
        if current_path and current_path.endswith('inventory.xml'):
            if '.patch_storage' not in current_path:
                candidates.append((current_path, current_size))
            current_path = None

    return candidates


def _extract_file_7z(zip_path, internal_path, output_dir):
    """
    7z를 사용하여 ZIP 내 특정 파일을 추출.
    Returns: 추출된 파일의 전체 경로
    """
    subprocess.run(
        [SEVENZIP_PATH, "e", zip_path, internal_path, f"-o{output_dir}", "-y"],
        capture_output=True, text=True
    )
    # 7z -e는 플랫하게 추출하므로 파일명만 사용
    filename = os.path.basename(internal_path)
    return os.path.join(output_dir, filename)


def parse_bugs_from_goldimg(zip_path, patch_type, output_file=None):
    """
    지정된 경로의 GOLDIMG ZIP 파일에서 inventory.xml을 파싱하여
    Fixed Bug 정보를 추출하고 결과 파일에 저장.

    Args:
        zip_path (str): ZIP 파일이 있는 디렉터리 경로
        patch_type (str): "DB" 또는 "GI"
        output_file (str): 출력 파일명 (None이면 자동 생성)
    """
    pattern = f"GOLDIMG_{patch_type}_*.zip"
    zip_files = sorted(glob.glob(os.path.join(zip_path, pattern)), key=_version_key)

    if not zip_files:
        print(f"  {pattern} 파일이 없습니다.")
        return None

    # 7z 사용 가능 여부 확인
    use_7z = os.path.exists(SEVENZIP_PATH)
    if use_7z:
        print(f"  7-Zip 사용: {SEVENZIP_PATH}")
    else:
        print(f"  7-Zip 미설치. Python zipfile 사용 (대용량 파일은 느릴 수 있음)")

    output_lines = []           # 출력할 라인들을 저장
    bug_positions = {}          # 이미 출력된 BUG 번호 추적 (중복 방지용)
    last_version = None         # 마지막 버전 추적
    type_label = "Database" if patch_type == "DB" else "Grid Infrastructure"

    # 각 ZIP 파일 순회
    for zip_file in zip_files:
        zip_basename = os.path.basename(zip_file)
        print(f"  처리 중: {zip_basename}")

        try:
            if use_7z:
                root = _parse_with_7z(zip_file)
            else:
                root = _parse_with_zipfile(zip_file)

            if root is None:
                print(f"    ⚠ inventory.xml을 찾을 수 없습니다.")
                continue

            # patch_description 요소에서 패치 설명 텍스트 추출
            patch_desc = root.find('patch_description')
            patch_text = patch_desc.text if patch_desc is not None else ""

            if not patch_text:
                continue

            # ZIP 파일명에서 표시용 버전 이름 생성
            _, display_name = _version_key(zip_file)

            # 버전 헤더와 패치 설명 추가
            output_lines.append(f"### {type_label} RU {display_name}\n")
            output_lines.append(f" *** {patch_text}\n")

            # "Database/Grid Infrastructure Release Update :" 뒤의 버전 정보 추출
            ver_match = re.search(
                r'(?:Database|Grid Infrastructure) Release Update\s*:\s*([\d.]+)',
                patch_text
            )
            if ver_match:
                last_version = ver_match.group(1)

            # XML 내 모든 bug 요소 순회
            bug_count = 0
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
                bug_count += 1

            print(f"    → 새로운 BUG {bug_count}개 추가 (누적 {len(bug_positions)}개)")

        except Exception as e:
            print(f"    ⚠ 오류 발생: {e}")
            continue

    if not output_lines:
        print(f"  추출된 패치 정보가 없습니다.")
        return None

    # 출력 파일명: 사용자 지정 또는 자동 생성
    if output_file is None:
        today = datetime.now().strftime("%Y%m%d")
        if last_version:
            output_file = f"Fixed_Bug_{patch_type}_For_{last_version}_{today}.txt"
        else:
            output_file = f"Fixed_Bug_{patch_type}_{today}.txt"

    # 결과를 파일에 저장
    with open(output_file, 'w', encoding='utf-8') as f:
        for line in output_lines:
            if line is not None:
                f.write(line)

    return output_file


def _parse_with_7z(zip_file):
    """
    7z를 사용하여 ZIP에서 메인 inventory.xml을 추출 후 파싱.
    가장 큰 inventory.xml = 메인 RU 패치.
    """
    candidates = _list_inventory_files_7z(zip_file)

    if not candidates:
        return None

    # 가장 큰 inventory.xml 선택
    main_inv_path, main_inv_size = max(candidates, key=lambda x: x[1])
    print(f"    → {main_inv_path} ({main_inv_size:,} bytes)")

    # 임시 디렉터리에 추출
    temp_dir = os.path.join(os.path.dirname(zip_file) or ".", "_temp_extract")
    os.makedirs(temp_dir, exist_ok=True)

    try:
        extracted = _extract_file_7z(zip_file, main_inv_path, temp_dir)
        root = ET.parse(extracted).getroot()
        return root
    finally:
        # 임시 파일 정리
        inv_file = os.path.join(temp_dir, "inventory.xml")
        if os.path.exists(inv_file):
            os.remove(inv_file)
        try:
            os.rmdir(temp_dir)
        except OSError:
            pass


def _parse_with_zipfile(zip_file):
    """
    Python zipfile을 사용하여 ZIP에서 메인 inventory.xml을 파싱.
    대용량 파일에서는 느릴 수 있음.
    """
    with zipfile.ZipFile(zip_file, 'r') as z:
        candidates = []
        for info in z.infolist():
            if info.filename.endswith('inventory.xml') and '.patch_storage' not in info.filename:
                candidates.append(info)

        if not candidates:
            return None

        main_inv = max(candidates, key=lambda x: x.file_size)
        print(f"    → {main_inv.filename} ({main_inv.file_size:,} bytes)")

        xml_content = z.read(main_inv.filename)
        root = ET.parse(io.BytesIO(xml_content)).getroot()
        return root


if __name__ == "__main__":
    # 명령줄 인자 처리
    # 사용법: python parse_bugs_26ai.py [DB|GI|ALL] [output_file]
    patch_type = sys.argv[1].upper() if len(sys.argv) > 1 else "ALL"
    user_output_file = sys.argv[2] if len(sys.argv) > 2 else None

    print("=" * 60)
    print("Oracle 23ai/26ai GOLDIMG 패치 정보 추출기")
    print("=" * 60)

    if patch_type in ("DB", "ALL"):
        print(f"\n[Database 패치 처리]")
        db_output = parse_bugs_from_goldimg(".", "DB", user_output_file if patch_type == "DB" else None)
        if db_output:
            print(f"  ✓ {db_output} 파일이 생성되었습니다.\n")

    if patch_type in ("GI", "ALL"):
        print(f"\n[Grid Infrastructure 패치 처리]")
        gi_output = parse_bugs_from_goldimg(".", "GI", user_output_file if patch_type == "GI" else None)
        if gi_output:
            print(f"  ✓ {gi_output} 파일이 생성되었습니다.\n")

    print("=" * 60)
    print("완료!")
