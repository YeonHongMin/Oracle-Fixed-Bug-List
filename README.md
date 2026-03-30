# Oracle Patch Fixed Bug Extractor

Oracle 패치 ZIP 파일에서 Fixed Bug 정보를 추출하는 Python 스크립트 모음입니다.
**19c**와 **23ai/26ai** 두 가지 패치 체계를 지원합니다.

## 개요

Oracle 패치 ZIP 파일 내부의 `inventory.xml`에는 해당 패치에서 수정된 버그(Fixed Bug) 목록이 포함되어 있습니다. 이 스크립트는 여러 패치 파일을 한 번에 처리하여 버전별로 정리된 버그 목록을 생성합니다.

## 공통 기능

- 디렉터리 내 Oracle 패치 ZIP 파일 자동 탐색
- ZIP 파일 내 `inventory.xml` 파싱
- 버전 순서대로 자연 정렬
- 중복 BUG 번호 자동 제거 (첫 등장 버전에만 표시)
- 패치 설명(patch_description) 포함

---

## 19c — `parse_bugs_19c.py`

### 지원 패치 형식

- `COMBO_GI_RU_19.x.x.x.xxxxxx_pxxxxxxxx_190000_Linux-x86-64.zip`
- `GI_RU_19.x.x.x.x_pxxxxxxxx_190000_Linux-x86-64.zip`

### ZIP 내부 구조

```
<patch_id>/<sub_patch_id>/<sub_sub_patch_id>/etc/config/inventory.xml
```

19c COMBO 패치는 Database + GI가 하나의 ZIP에 합쳐져 있으며, 내부에 여러 서브 패치의 inventory.xml이 존재합니다.

### 사용법

```bash
# 기본 실행 (자동 파일명 생성)
python parse_bugs_19c.py

# 출력 파일명 직접 지정
python parse_bugs_19c.py my_output.txt
```

### 출력 파일명

| 조건 | 파일명 형식 |
|------|------------|
| 자동 생성 | `Fixed_Bug_For_<DB RU 버전>_<날짜>.txt` |
| 사용자 지정 | 명령줄 인자로 전달한 파일명 |

예시: `Fixed_Bug_For_19.30.0.0.260120_20260122.txt`

### 출력 형식

```
### RU 19.4.0.0.190716_p29699097_190000_Linux-x86-64
 *** OCW RELEASE UPDATE 19.4.0.0.0 (29850993)
     BUG 25736599 - GI 12.2.0.1 CVU POST-GI-UPGRADE CHECK OF OCR AND OCR BACKUP
     ...

### RU 19.5.0.0.191015_p30133178_190000_Linux-x86-64
 *** Database Release Update : 19.5.0.0.191015 (30125133)
     BUG 24687075 - SPACE ADVISOR TASKS/JOBS HITTING DEADLOCKS WITH GATHER DB STATS JOBS
     ...
```

### 필요한 패치 파일

```
├── COMBO_GI_RU_19.4.0.0.xxxxxx_pxxxxxxxx_190000_Linux-x86-64.zip
├── COMBO_GI_RU_19.5.0.0.xxxxxx_pxxxxxxxx_190000_Linux-x86-64.zip
├── ...
└── COMBO_GI_RU_19.30.0.0.x_pxxxxxxxx_190000_Linux-x86-64.zip
```

---

## 23ai/26ai — `parse_bugs_26ai.py`

### 지원 패치 형식

23ai/26ai는 Database와 Grid Infrastructure 패치가 **분리**되어 있습니다.

| 패치 유형 | ZIP 파일명 패턴 |
|-----------|----------------|
| Database (DB) | `GOLDIMG_DB_23.x.x.xx.xx.zip` |
| Grid Infrastructure (GI) | `GOLDIMG_GI_23.x.x.xx.xx.zip` |

### ZIP 내부 구조

```
inventory/oneoffs/<patch_id>/etc/config/inventory.xml
```

19c와 달리 `inventory/oneoffs/` 프리픽스가 추가되었으며, 가장 큰 inventory.xml이 메인 RU 패치에 해당합니다.

### 사용법

```bash
# DB + GI 모두 추출
python parse_bugs_26ai.py

# Database 패치만 추출
python parse_bugs_26ai.py DB

# Grid Infrastructure 패치만 추출
python parse_bugs_26ai.py GI

# 출력 파일명 직접 지정 (DB 또는 GI 단독 실행 시)
python parse_bugs_26ai.py DB my_db_bugs.txt
```

### 출력 파일명

| 조건 | 파일명 형식 |
|------|------------|
| DB 자동 | `Fixed_Bug_DB_For_<버전>_<날짜>.txt` |
| GI 자동 | `Fixed_Bug_GI_For_<버전>_<날짜>.txt` |

예시:
- `Fixed_Bug_DB_For_23.26.1.0.0_20260330.txt`
- `Fixed_Bug_GI_For_23.26.1.0.0_20260330.txt`

### 출력 형식

```
### Database RU 23.5.0.24.07
 *** Database Release Update : 23.5.0.24.07 (36741532) Gold Image
     BUG 36723967 - ORAOLEDB - INCREASE THE DEFAULT AND MAX VALUE OF INITIALLOBFETCHSIZE
     ...

### Database RU 23.26.0.26.01
 *** Database Release Update : 23.26.1.0.0 (38743669) Gold Image
     BUG 38123456 - ...
     ...
```

### 필요한 패치 파일

```
├── GOLDIMG_DB_23.4.0.24.05.zip
├── GOLDIMG_DB_23.5.0.24.07.zip
├── ...
├── GOLDIMG_DB_23.26.0.26.01.zip
├── GOLDIMG_GI_23.4.0.24.05.zip
├── GOLDIMG_GI_23.5.0.24.07.zip
├── ...
└── GOLDIMG_GI_23.26.0.26.01.zip
```

---

## 19c vs 23ai/26ai 패치 구조 비교

| 항목 | 19c | 23ai/26ai |
|------|-----|-----------|
| 스크립트 | `parse_bugs_19c.py` | `parse_bugs_26ai.py` |
| ZIP 파일 | `COMBO_GI_RU_*.zip` (DB+GI 통합) | `GOLDIMG_DB_*.zip` + `GOLDIMG_GI_*.zip` (분리) |
| inventory.xml 경로 | `<id>/<sub_id>/<id>/etc/config/` | `inventory/oneoffs/<id>/etc/config/` |
| 출력 | 단일 파일 | DB / GI 별도 파일 |
| ZIP 처리 엔진 | Python zipfile | 7-Zip 우선, zipfile 폴백 |

## 파일 설명

| 파일 | 설명 |
|------|------|
| `parse_bugs_19c.py` | 19c 패치 추출 스크립트 |
| `parse_bugs_26ai.py` | 23ai/26ai 패치 추출 스크립트 (DB/GI 분리) |
| `parse_bugs_19c_old.py` | 19c 이전 버전 스크립트 (레거시) |

## 주의사항

> **중요:** 상위 버전 패치는 하위 버전의 모든 Fixed Bug을 포함하고 있습니다.

각 스크립트는 버전에서 **새로 추가된 Fixed Bug만** 출력합니다 (중복 제거). 따라서 정확한 버전별 Fixed Bug 목록을 얻으려면 **해당 버전까지의 모든 패치 파일이 필요**합니다.

중간 버전이 누락되면 해당 버전의 Fixed Bug이 다른 버전에 잘못 표시될 수 있습니다.

## 요구사항

- Python 3.6+
- 표준 라이브러리만 사용 (추가 설치 불필요)
- **26ai 스크립트**: [7-Zip](https://www.7-zip.org/) 설치 권장 (대용량 ZIP 처리 성능 향상, 미설치 시 Python zipfile로 폴백)

## 라이선스

MIT License
