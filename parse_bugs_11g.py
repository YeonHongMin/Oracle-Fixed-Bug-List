import xml.etree.ElementTree as ET
import glob
import zipfile
import io
import os
import re
import sys
from datetime import datetime


ZIP_NAME_PATTERN = re.compile(r"^(COMBO|GI_PSU)_11\.2\.0\.4\.([^_]+)_p(\d+)_")
PSU_VERSION_PATTERN = re.compile(
    r"(?:Database|OCW|Grid Infrastructure|OJVM|ACFS)\s+"
    r"(?:PATCH SET UPDATE|Patch Set Update)\s*:?\s*"
    r"(11\.2\.0\.4\.[^\s(]+)",
    re.IGNORECASE,
)


def _parse_zip_identity(path):
    """ZIP 파일명에서 패치 유형(COMBO/GI_PSU)과 날짜 키를 추출."""
    name = os.path.basename(path)
    match = ZIP_NAME_PATTERN.match(name)
    if not match:
        return None, None, None
    return match.group(1), match.group(2), match.group(3)


def _version_key(path):
    """
    파일 경로에서 버전 정보를 추출하여 자연 정렬용 키를 반환.
    같은 날짜면 COMBO가 GI_PSU보다 먼저 오도록 우선순위를 부여.
    """
    patch_type, date_key, _ = _parse_zip_identity(path)
    if date_key is None:
        name = os.path.splitext(os.path.basename(path))[0]
        return (999999,), 1, name

    if date_key == "4":
        numbers = (4,)
    else:
        numbers = tuple(int(part) for part in re.split(r"[^\d]+", date_key) if part.isdigit())

    type_priority = 0 if patch_type == "COMBO" else 1
    return numbers, type_priority, date_key


def _select_zip_files(zip_path):
    """
    COMBO/GI_PSU 11.2.0.4 ZIP 목록을 선택.
    같은 날짜에 COMBO와 GI_PSU가 모두 있으면 COMBO만 사용.
    """
    candidates = []
    for pattern in ("COMBO_11.2.0.4*.zip", "GI_PSU_11.2.0.4*.zip"):
        candidates.extend(glob.glob(os.path.join(zip_path, pattern)))

    selected_by_date = {}
    for zip_file in candidates:
        patch_type, date_key, _ = _parse_zip_identity(zip_file)
        if date_key is None:
            continue

        current = selected_by_date.get(date_key)
        if current is None:
            selected_by_date[date_key] = (patch_type, zip_file)
            continue

        current_type, _ = current
        if patch_type == "COMBO" and current_type != "COMBO":
            selected_by_date[date_key] = (patch_type, zip_file)

    return sorted((item[1] for item in selected_by_date.values()), key=_version_key)


def _psu_label(patch_type, date_key):
    prefix = "COMBO" if patch_type == "COMBO" else "GI PSU"
    return f"{prefix} 11.2.0.4.{date_key}"


def _expected_psu_version(date_key):
    return f"11.2.0.4.{date_key}"


def _extract_psu_version(patch_text):
    match = PSU_VERSION_PATTERN.search(patch_text)
    return match.group(1) if match else None


def _inventory_matches_release(patch_text, date_key):
    """inventory.xml이 현재 ZIP의 PSU 버전에 해당하는지 확인."""
    version = _extract_psu_version(patch_text)
    return version == _expected_psu_version(date_key)


def _prefer_inventory_path(path):
    """
    동일 patch_description의 중복 inventory 중 우선할 경로를 결정.
    custom/server 경로보다 일반 etc/config 경로를 우선한다.
    """
    return ("/custom/server/" in path.lower(), path.lower())


def parse_bugs_from_zip(zip_path, output_file=None):
    """
    지정된 경로의 COMBO/GI_PSU 11.2.0.4 ZIP 파일에서 inventory.xml을 파싱하여
    Fixed Bug 정보를 추출하고 결과 파일에 저장.

    각 ZIP은 하나의 PSU 릴리스를 나타낸다. ZIP 내부의 과거 PSU inventory는
    무시하고, patch_description 버전이 ZIP 파일명 날짜와 일치하는
    inventory.xml만 처리한다.
    """
    zip_files = _select_zip_files(zip_path)

    output_lines = []
    bug_positions = {}
    last_psu_version = None

    for zip_file in zip_files:
        patch_type, date_key, _ = _parse_zip_identity(zip_file)
        label = _psu_label(patch_type, date_key)

        inventories_by_patch = {}

        with zipfile.ZipFile(zip_file, "r") as z:
            for inv_file in z.namelist():
                if not inv_file.endswith("inventory.xml"):
                    continue

                xml_content = z.read(inv_file)
                root = ET.parse(io.BytesIO(xml_content)).getroot()

                patch_desc = root.find("patch_description")
                patch_text = patch_desc.text if patch_desc is not None else ""
                if not patch_text or not _inventory_matches_release(patch_text, date_key):
                    continue

                bugs = []
                for bug in root.findall(".//bug"):
                    number = bug.get("number")
                    if not number:
                        continue
                    description = bug.get("description") or ""
                    bugs.append((number, description))

                current = inventories_by_patch.get(patch_text)
                candidate = (inv_file, bugs)
                if current is None or _prefer_inventory_path(inv_file) < _prefer_inventory_path(current[0]):
                    inventories_by_patch[patch_text] = candidate

        for patch_text, (_, bugs) in sorted(inventories_by_patch.items()):
            new_bug_lines = []
            for number, description in bugs:
                if number in bug_positions:
                    continue
                line = f"     BUG {number} - {description}\n"
                bug_positions[number] = len(output_lines) + len(new_bug_lines) + 2
                new_bug_lines.append(line)

            if not new_bug_lines:
                continue

            output_lines.append(f"### {label}\n")
            output_lines.append(f" *** {patch_text}\n")
            output_lines.extend(new_bug_lines)

            version = _extract_psu_version(patch_text)
            if version:
                last_psu_version = version

    if output_file is None:
        today = datetime.now().strftime("%Y%m%d")
        if last_psu_version:
            output_file = f"Fixed_Bug_For_{last_psu_version}_{today}.txt"
        else:
            output_file = f"Fixed_Bug_11.2.0.4_{today}.txt"

    with open(output_file, "w", encoding="utf-8") as f:
        for line in output_lines:
            if line is not None:
                f.write(line)

    return output_file


if __name__ == "__main__":
    user_output_file = sys.argv[1] if len(sys.argv) > 1 else None
    output_file = parse_bugs_from_zip(".", user_output_file)
    print(f"{output_file} 파일이 생성되었습니다.")