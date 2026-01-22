import xml.etree.ElementTree as ET
import glob
import zipfile
import io
import os
import re
from collections import OrderedDict


def _version_key(path):
    """Return a tuple of ints for natural sorting (e.g., 19.4 < 19.10)."""
    name = os.path.splitext(os.path.basename(path))[0]
    version = name.split("RU_", 1)[1] if "RU_" in name else name
    numbers = [int(part) for part in re.split(r"[^\d]+", version) if part.isdigit()]
    return tuple(numbers), version

def parse_bugs_from_zip(zip_path, output_file):
    zip_files = sorted(glob.glob(f"{zip_path}/*.zip"), key=_version_key)

    output_lines = []
    bug_positions = {}  # BUG number -> index in output_lines

    for zip_file in zip_files:
        with zipfile.ZipFile(zip_file, 'r') as z:
            inventory_files = [name for name in z.namelist() if name.endswith('inventory.xml')]

            for inv_file in inventory_files:
                xml_content = z.read(inv_file)
                root = ET.parse(io.BytesIO(xml_content)).getroot()

                patch_desc = root.find('patch_description')
                patch_text = patch_desc.text if patch_desc is not None else ""

                if patch_text:
                    zip_name = os.path.splitext(os.path.basename(zip_file))[0]
                    display_name = zip_name.split("RU_", 1)[1] if "RU_" in zip_name else zip_name
                    output_lines.append(f"### RU {display_name}\n")
                    output_lines.append(f" *** {patch_text}\n")

                    for bug in root.findall('.//bug'):
                        number = bug.get('number')
                        description = bug.get('description') or ""
                        line = f"     BUG {number} - {description}\n"

                        if number in bug_positions:
                            # 이후 동일 BUG 라인은 제거
                            continue

                        bug_positions[number] = len(output_lines)
                        output_lines.append(line)

    with open(output_file, 'w', encoding='utf-8') as f:
        for line in output_lines:
            if line is not None:
                f.write(line)

if __name__ == "__main__":
    parse_bugs_from_zip(".", "result.txt")
    print("result.txt 파일이 생성되었습니다.")
