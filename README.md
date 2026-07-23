# Oracle Patch Fixed Bug Extractor

Oracle 패치 ZIP의 `inventory.xml`에서 Fixed Bug 목록을 추출하고, Oracle Support KB로 Section 태그를 붙이는 Python 스크립트 모음입니다.

지원 체계: **11g** · **19c** · **23ai/26ai**

## 개요

| 단계 | 산출물 | 설명 |
|------|--------|------|
| 1. 추출 | `Fixed_Bug_*.txt` | 패치 ZIP → 버전별 신규 Fixed Bug |
| 2. 태깅 | `Info_Fixed_Bug_*.txt` | KB Section을 `[카테고리] BUG …` 형태로 부착 |

상위 RU는 하위 픽스를 포함하므로, 스크립트는 **BUG 번호 중복을 제거하고 처음 등장한 버전에만** 남깁니다.  
정확한 버전별 목록을 얻으려면 **해당 버전까지 끊김 없는 패치 ZIP 세트**가 필요합니다.

## 공통 기능

- 디렉터리 내 패치 ZIP 자동 탐색 · 버전 자연 정렬
- `inventory.xml` 파싱 · `patch_description` 포함
- 중복 BUG 번호 제거 (첫 등장 버전만 출력)

---

## 19c — `parse_bugs_19c.py`

### 지원 ZIP

- `COMBO_GI_RU_19.x.x.x.xxxxxx_pxxxxxxxx_190000_Linux-x86-64.zip`
- `GI_RU_19.x.x.x.x_pxxxxxxxx_190000_Linux-x86-64.zip`

파일명에 `19.`가 있으면 대상입니다. `OLD_` 접두 ZIP도 매칭되므로 **구버전 패치는 작업 폴더에서 제거**하세요.

### ZIP 내부 구조

```
<patch_id>/<sub_patch_id>/<sub_sub_patch_id>/etc/config/inventory.xml
```

COMBO는 Database + GI가 한 ZIP에 들어 있으며, 서브 패치별 `inventory.xml`이 여러 개입니다.

### 사용법

```bash
python parse_bugs_19c.py
python parse_bugs_19c.py Fixed_Bug_For_19.32.0.0.260721_20260723.txt
```

| 조건 | 출력 |
|------|------|
| 자동 | `Fixed_Bug_For_<DB RU 버전>_<날짜>.txt` |
| 지정 | 인자로 준 파일명 |

### 출력 예

```
### RU 19.32.0.0.260721_p39618711_190000_Linux-x86-64
 *** Database Release Update : 19.32.0.0.260721 (...)
     BUG ........ - ...
```

---

## 23ai/26ai — `parse_bugs_26ai.py`

Database와 Grid Infrastructure ZIP이 **분리**되어 있습니다.

| 유형 | 패턴 |
|------|------|
| DB | `GOLDIMG_DB_23.*.zip` |
| GI | `GOLDIMG_GI_23.*.zip` |

### ZIP 내부 구조

```
inventory/oneoffs/<patch_id>/etc/config/inventory.xml
```

가장 큰 `inventory.xml`을 메인 RU로 사용합니다. (7-Zip 권장, 없으면 `zipfile` 폴백)

### 사용법

```bash
python parse_bugs_26ai.py          # DB + GI
python parse_bugs_26ai.py DB
python parse_bugs_26ai.py GI
python parse_bugs_26ai.py DB Fixed_Bug_DB_For_23.26.3.0.0_20260723.txt
```

| 조건 | 출력 |
|------|------|
| DB 자동 | `Fixed_Bug_DB_For_<버전>_<날짜>.txt` |
| GI 자동 | `Fixed_Bug_GI_For_<버전>_<날짜>.txt` |

### 필요한 패치 예

```
├── GOLDIMG_DB_23.4.0.24.05.zip
├── ...
├── GOLDIMG_DB_23.26.3.0.0_p39581612_230000_Linux-x86-64.zip
├── GOLDIMG_GI_23.4.0.24.05.zip
├── ...
└── GOLDIMG_GI_23.26.3.0.0_p39581618_230000_Linux-x86-64.zip
```

---

## 19c vs 23ai/26ai 비교

| 항목 | 19c | 23ai/26ai |
|------|-----|-----------|
| 추출 스크립트 | `parse_bugs_19c.py` | `parse_bugs_26ai.py` |
| ZIP | `COMBO_GI_RU_*.zip` (통합) | `GOLDIMG_DB_*` + `GOLDIMG_GI_*` (분리) |
| inventory 경로 | `<id>/.../etc/config/` | `inventory/oneoffs/<id>/etc/config/` |
| Fixed 출력 | 단일 `Fixed_Bug_For_*` | `Fixed_Bug_DB_*` / `Fixed_Bug_GI_*` |
| Info 스크립트 | `make_info_fixed_bug_19c.py` | `make_info_fixed_bug_26ai.py` |
| Bugs Fixed KB | KB850150 + **KB718940(GI)** | **KB781900 통합** (GI 전용 Bugs Fixed KB 없음) |

> ZIP 파일 크기와 Fixed Bug 개수는 비례하지 않습니다. (패키징·ACFS 바이너리 등)  
> 누적 픽스 여부는 `inventory.xml` / Fixed 문서의 BUG 수로 확인하세요.

---

## Info 생성 (KB Section 태그)

`Fixed_Bug_*.txt`에 KB 카테고리를 `[Section] BUG …`로 붙입니다.  
**19c와 26ai는 KB 체계가 다르므로 스크립트가 분리**되어 있습니다.

| | 19c | 23ai / 26ai |
|--|-----|-------------|
| Bugs Fixed KB | KB850150 (DB) + KB718940 (GI) | KB781900 (DB/GI Bugs Fixed 통합) |
| Known Issues (참고) | — | KB915346 등 (형식·목적이 Bugs Fixed와 다름) |
| 입력 | `Fixed_Bug_For_19.xx.txt` | `Fixed_Bug_DB_*.txt` / `Fixed_Bug_GI_*.txt` |
| 스크립트 | `make_info_fixed_bug_19c.py` | `make_info_fixed_bug_26ai.py` |

KB는 **important bugs만** 수록합니다. inventory Fixed Bug의 대부분에 태그가 없는 것은 정상입니다.

### 19c

```bash
python make_info_fixed_bug_19c.py ^
  "KB850150 Database 19 Release Updates and Revisions Bugs Fixed Lists (2026-07-21).md,KB718940 Grid Infrastructure 19 Release Updates and Revisions Bugs Fixed Lists (2026-07-21).md" ^
  "Fixed_Bug_For_19.32.0.0.260721_20260723.txt" ^
  "Info_Fixed_Bug_For_19.32.0.0.260721_20260723.txt"
```

### 26ai (DB / GI 각각)

```bash
python make_info_fixed_bug_26ai.py ^
  "KB781900 Database 26ai Release Updates Bugs Fixed Lists (2026-07-23).md" ^
  "Fixed_Bug_DB_For_23.26.3.0.0_20260723.txt" ^
  "Info_Fixed_Bug_DB_For_23.26.3.0.0_20260723.txt"

python make_info_fixed_bug_26ai.py ^
  "KB781900 Database 26ai Release Updates Bugs Fixed Lists (2026-07-23).md" ^
  "Fixed_Bug_GI_For_23.26.3.0.0_20260723.txt" ^
  "Info_Fixed_Bug_GI_For_23.26.3.0.0_20260723.txt"
```

출력 예:

```text
     [Advance Queuing] BUG 30309807 - ORA-00600 ...
```

---

## 11g

| 스크립트 | 용도 |
|----------|------|
| `parse_bugs_11g.py` | 11.2.0.4 PSU 등 Fixed Bug 추출 |
| `make_info_fixed_bug_11g.py` | KB866924(DB) / KB513423(GI) + 설명 fuzzy 매칭 |

---

## 파일 목록

| 파일 | 설명 |
|------|------|
| `parse_bugs_19c.py` | 19c Fixed Bug 추출 |
| `parse_bugs_26ai.py` | 23ai/26ai Fixed Bug 추출 (DB/GI) |
| `parse_bugs_11g.py` | 11g Fixed Bug 추출 |
| `make_info_fixed_bug_19c.py` | 19c Info (KB850150 + KB718940) |
| `make_info_fixed_bug_26ai.py` | 26ai Info (KB781900) |
| `make_info_fixed_bug_11g.py` | 11g Info |
| `parse_bugs_19c_old.py` | 19c 레거시 |
| `parse_aggr_bugs.py` / `parse_dp_bugs.py` / `parse_move_bugs.py` | 키워드별 Fixed Bug 요약 추출 |

---

## 주의사항

1. **누적 패치 세트**: 중간 RU ZIP이 빠지면 신규 BUG가 잘못된 버전에 잡힐 수 있습니다.
2. **OLD_ ZIP**: 19c 스크립트는 `OLD_COMBO_…`도 `19.` 때문에 포함합니다. 구 패치는 폴더에서 빼세요.
3. **Info 태그율**: KB important 목록 ≪ inventory 전체이므로 미매칭이 많습니다.
4. **ZIP 크기**: 상위 RU ZIP이 하위보다 작을 수 있습니다. 픽스 누적과 무관합니다.

## 요구사항

- Python 3.6+
- 표준 라이브러리만 사용
- `parse_bugs_26ai.py`: [7-Zip](https://www.7-zip.org/) 권장

## 라이선스

MIT License
