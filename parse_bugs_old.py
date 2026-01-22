#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
디렉터리 내 모든 XML 파일에서 bug 정보를 추출하여 출력하는 프로그램
"""

import xml.etree.ElementTree as ET
import sys
import os
import glob
import zipfile
import io
import re


def _version_key(path):
    """Return a tuple of ints for natural sorting (e.g., 19.4 < 19.10)."""
    name = os.path.splitext(os.path.basename(path))[0]
    version = name.split("RU_", 1)[1] if "RU_" in name else name
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
        # 바이트면 BytesIO로 파싱
        if isinstance(xml_content, bytes):
            root = ET.parse(io.BytesIO(xml_content)).getroot()
        else:
            root = ET.fromstring(xml_content)

        # patch_description 찾기
        patch_desc = root.find('patch_description')
        patch_text = patch_desc.text if patch_desc is not None else ""

        # 모든 bug 요소 찾기 (어디에 있든)
        bugs = root.findall('.//bug')

        if not bugs:
            source = source_name if source_name else 'XML'
            print(f"Warning: No bug elements found in {source}.", file=sys.stderr)
            return patch_text, []

        # 결과를 저장할 리스트
        bug_list = []

        # 각 bug 정보 추출
        for bug in bugs:
            number = bug.get('number')
            description = bug.get('description') or ""

            if number:
                bug_list.append((number, description))

        return patch_text, bug_list

    except ET.ParseError as e:
        source = source_name if source_name else 'XML'
        print(f"Error: XML parsing failed for {source} - {e}", file=sys.stderr)
        return "", []
    except Exception as e:
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
    zip_files = sorted(glob.glob(os.path.join(directory, '*.zip')), key=_version_key)

    found_xmls = []

    for zip_file in zip_files:
        try:
            with zipfile.ZipFile(zip_file, 'r') as zf:
                # ZIP 파일 내에서 inventory.xml 찾기
                inventory_files = [name for name in zf.namelist() if name.endswith('inventory.xml')]

                for inv_file in inventory_files:
                    xml_content = zf.read(inv_file)
                    file_basename = os.path.splitext(os.path.basename(zip_file))[0]
                    found_xmls.append((zip_file, xml_content, file_basename))
                    print(f"Found inventory.xml in {zip_file} (as {inv_file})", file=sys.stderr)

        except zipfile.BadZipFile:
            print(f"Warning: {zip_file} is not a valid ZIP file.", file=sys.stderr)
        except Exception as e:
            print(f"Error processing ZIP file {zip_file}: {e}", file=sys.stderr)

    return found_xmls


def process_all_xml_files(directory='.', output_file='inventory.txt'):
    """
    디렉터리 내 모든 XML 파일과 ZIP 파일 내의 inventory.xml을 처리하여 하나의 출력 파일에 저장

    Args:
        directory (str): 검색할 디렉터리 경로
        output_file (str): 출력 파일 경로
    """
    # ZIP 파일에서 inventory.xml 찾기
    zip_xmls = process_zip_files(directory)

    if not zip_xmls:
        print(f"Warning: No ZIP files with inventory.xml found in {directory}.", file=sys.stderr)
        return

    # 결과를 저장할 리스트
    output_lines = []
    bug_positions = {}  # BUG number -> 이미 출력됨 여부
    total_bugs = 0
    processed_count = 0

    # ZIP 파일 내의 inventory.xml 처리
    for zip_file, xml_content, file_basename in zip_xmls:
        # BUG 정보 추출
        patch_text, bug_list = parse_bugs_from_xml_content(xml_content, f"{zip_file}/inventory.xml")

        if patch_text and bug_list:
            # 헤더 추가
            display_name = file_basename.split("RU_", 1)[1] if "RU_" in file_basename else file_basename
            output_lines.append(f"### RU {display_name}\n")
            output_lines.append(f" *** {patch_text}\n")

            # BUG 항목들 추가 (중복 제거)
            for number, description in bug_list:
                if number in bug_positions:
                    # 이미 출력된 BUG는 건너뜀
                    continue

                bug_positions[number] = True
                line = f"     BUG {number} - {description}\n"
                output_lines.append(line)
                total_bugs += 1

            processed_count += 1
            print(f"Processed {zip_file}/inventory.xml: {len(bug_list)} bugs found.", file=sys.stderr)

    # 파일에 저장
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            for line in output_lines:
                if line is not None:
                    f.write(line)

        print(f"\nResults saved to {output_file} file.", file=sys.stderr)
        print(f"Processed {processed_count} file(s) with total {total_bugs} unique bug items.", file=sys.stderr)
    except IOError as e:
        print(f"Warning: Failed to save file - {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    # 스크립트 파일이 있는 디렉토리로 작업 디렉토리 변경
    try:
        # __file__이 있는 경우 (일반적인 실행)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        os.chdir(script_dir)
    except NameError:
        # __file__이 없는 경우 (예: exec()로 실행), 현재 작업 디렉토리 사용
        # 현재 디렉토리에서 XML 파일을 찾음
        pass

    # 명령줄 인자로 출력 파일 경로를 받을 수 있음
    output_file = sys.argv[1] if len(sys.argv) > 1 else 'result.txt'
    process_all_xml_files('.', output_file)
    print("result.txt 파일이 생성되었습니다.")
