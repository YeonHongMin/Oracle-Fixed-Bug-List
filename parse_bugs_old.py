#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Oracle 패치 ZIP 파일에서 Fixed Bug 정보를 추출하는 프로그램

ZIP 파일 내의 inventory.xml을 파싱하여 버전별로 정리된
Fixed Bug 목록을 생성합니다.
"""

import xml.etree.ElementTree as ET
import sys
import os
import glob
import zipfile
import io
import re
from datetime import datetime


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


def parse_bugs_from_xml_content(xml_content, source_name=''):
    """
    XML 내용에서 bug 요소를 파싱하여 반환

    Args:
        xml_content (str or bytes): XML 내용 (문자열 또는 바이트)
        source_name (str): 소스 이름 (에러 메시지용)

    Returns:
        tuple: (patch_description, bug_list) - 패치 설명과 BUG 정보 리스트
    """
    try:
        # 입력 타입에 따라 XML 파싱 방식 결정
        if isinstance(xml_content, bytes):
            # 바이트인 경우 BytesIO로 감싸서 파싱
            root = ET.parse(io.BytesIO(xml_content)).getroot()
        else:
            # 문자열인 경우 직접 파싱
            root = ET.fromstring(xml_content)

        # patch_description 요소에서 패치 설명 텍스트 추출
        patch_desc = root.find('patch_description')
        patch_text = patch_desc.text if patch_desc is not None else ""

        # XML 내 모든 bug 요소 검색 (경로 무관)
        bugs = root.findall('.//bug')

        # bug 요소가 없으면 경고 출력 후 빈 리스트 반환
        if not bugs:
            source = source_name if source_name else 'XML'
            print(f"Warning: No bug elements found in {source}.", file=sys.stderr)
            return patch_text, []

        # BUG 정보를 저장할 리스트
        bug_list = []

        # 각 bug 요소에서 number와 description 속성 추출
        for bug in bugs:
            number = bug.get('number')
            description = bug.get('description') or ""

            # number 속성이 있는 경우에만 리스트에 추가
            if number:
                bug_list.append((number, description))

        return patch_text, bug_list

    except ET.ParseError as e:
        # XML 파싱 오류 처리
        source = source_name if source_name else 'XML'
        print(f"Error: XML parsing failed for {source} - {e}", file=sys.stderr)
        return "", []
    except Exception as e:
        # 기타 예외 처리
        source = source_name if source_name else 'XML'
        print(f"Error processing {source}: {e}", file=sys.stderr)
        return "", []


def process_zip_files(directory='.'):
    """
    디렉터리 내 모든 ZIP 파일에서 inventory.xml을 찾아 반환

    Args:
        directory (str): 검색할 디렉토리 경로

    Returns:
        list: (zip_file_path, xml_content, file_basename) 튜플 리스트
    """
    # 디렉터리 내 모든 ZIP 파일을 버전 순서대로 정렬
    zip_files = sorted(glob.glob(os.path.join(directory, '*.zip')), key=_version_key)

    # 찾은 inventory.xml 정보를 저장할 리스트
    found_xmls = []

    # 각 ZIP 파일 순회
    for zip_file in zip_files:
        try:
            with zipfile.ZipFile(zip_file, 'r') as zf:
                # ZIP 파일 내에서 inventory.xml로 끝나는 파일 목록 검색
                inventory_files = [name for name in zf.namelist() if name.endswith('inventory.xml')]

                # 각 inventory.xml 파일 처리
                for inv_file in inventory_files:
                    # XML 파일 내용 읽기
                    xml_content = zf.read(inv_file)
                    # ZIP 파일명에서 확장자 제거하여 기본 이름 추출
                    file_basename = os.path.splitext(os.path.basename(zip_file))[0]
                    # 결과 리스트에 추가
                    found_xmls.append((zip_file, xml_content, file_basename))
                    print(f"Found inventory.xml in {zip_file} (as {inv_file})", file=sys.stderr)

        except zipfile.BadZipFile:
            # 손상된 ZIP 파일 처리
            print(f"Warning: {zip_file} is not a valid ZIP file.", file=sys.stderr)
        except Exception as e:
            # 기타 예외 처리
            print(f"Error processing ZIP file {zip_file}: {e}", file=sys.stderr)

    return found_xmls


def process_all_xml_files(directory='.', output_file=None):
    """
    디렉터리 내 모든 ZIP 파일의 inventory.xml을 처리하여 결과 파일에 저장

    Args:
        directory (str): 검색할 디렉터리 경로
        output_file (str): 출력 파일 경로 (None이면 자동 생성)

    Returns:
        str: 생성된 출력 파일명
    """
    # ZIP 파일에서 inventory.xml 목록 가져오기
    zip_xmls = process_zip_files(directory)

    # inventory.xml이 없으면 경고 출력 후 종료
    if not zip_xmls:
        print(f"Warning: No ZIP files with inventory.xml found in {directory}.", file=sys.stderr)
        return None

    output_lines = []           # 출력할 라인들을 저장
    bug_positions = {}          # 이미 출력된 BUG 번호 추적 (중복 방지용)
    total_bugs = 0              # 총 유니크 BUG 수
    processed_count = 0         # 처리된 파일 수
    last_db_version = None      # 마지막 DB RU 버전 추적

    # 각 inventory.xml 파일 처리
    for zip_file, xml_content, file_basename in zip_xmls:
        # XML에서 패치 설명과 BUG 목록 추출
        patch_text, bug_list = parse_bugs_from_xml_content(xml_content, f"{zip_file}/inventory.xml")

        # 패치 설명과 BUG 목록이 모두 있는 경우에만 처리
        if patch_text and bug_list:
            # ZIP 파일명에서 표시용 버전 이름 생성
            display_name = file_basename.split("RU_", 1)[1] if "RU_" in file_basename else file_basename

            # 버전 헤더와 패치 설명 추가
            output_lines.append(f"### RU {display_name}\n")
            output_lines.append(f" *** {patch_text}\n")

            # "Database Release Update :" 뒤의 버전 정보 추출
            match = re.search(r'Database Release Update\s*:\s*([\d.]+)', patch_text)
            if match:
                last_db_version = match.group(1)

            # 각 BUG 항목 처리 (중복 제거)
            for number, description in bug_list:
                # 이미 출력된 BUG 번호는 건너뜀
                if number in bug_positions:
                    continue

                # 새로운 BUG 번호 기록 및 출력 라인 추가
                bug_positions[number] = True
                line = f"     BUG {number} - {description}\n"
                output_lines.append(line)
                total_bugs += 1

            processed_count += 1
            print(f"Processed {zip_file}/inventory.xml: {len(bug_list)} bugs found.", file=sys.stderr)

    # 출력 파일명: 사용자 지정 또는 자동 생성 (Fixed_Bug_For_<버전>_<날짜>.txt)
    if output_file is None:
        today = datetime.now().strftime("%Y%m%d")
        if last_db_version:
            output_file = f"Fixed_Bug_For_{last_db_version}_{today}.txt"
        else:
            output_file = f"Fixed_Bug_{today}.txt"

    # 결과를 파일에 저장
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            for line in output_lines:
                if line is not None:
                    f.write(line)

        print(f"\nResults saved to {output_file} file.", file=sys.stderr)
        print(f"Processed {processed_count} file(s) with total {total_bugs} unique bug items.", file=sys.stderr)
    except IOError as e:
        # 파일 저장 실패 시 에러 출력 후 종료
        print(f"Warning: Failed to save file - {e}", file=sys.stderr)
        sys.exit(1)

    return output_file


if __name__ == '__main__':
    # 스크립트 파일이 있는 디렉터리로 작업 디렉터리 변경
    try:
        # 일반적인 실행: __file__ 변수 사용 가능
        script_dir = os.path.dirname(os.path.abspath(__file__))
        os.chdir(script_dir)
    except NameError:
        # exec() 등으로 실행 시 __file__ 없음: 현재 디렉터리 사용
        pass

    # 명령줄 인자로 출력 파일명 지정 가능 (없으면 자동 생성)
    user_output_file = sys.argv[1] if len(sys.argv) > 1 else None
    output_file = process_all_xml_files('.', user_output_file)
    if output_file:
        print(f"{output_file} 파일이 생성되었습니다.")
