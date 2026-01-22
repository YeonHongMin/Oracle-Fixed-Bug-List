# Oracle Patch Fixed Bug Extractor

Oracle COMBO 패치 또는 Grid Infrastructure(GI) 패치의 ZIP 파일에서 Fixed Bug 정보를 추출하는 Python 스크립트입니다.

## 개요

Oracle 패치 ZIP 파일 내부의 `inventory.xml`에는 해당 패치에서 수정된 버그(Fixed Bug) 목록이 포함되어 있습니다. 이 스크립트는 여러 패치 파일을 한 번에 처리하여 버전별로 정리된 버그 목록을 생성합니다.

## 기능

- 디렉터리 내 모든 Oracle 패치 ZIP 파일 자동 탐색
- ZIP 파일 내 `inventory.xml` 파싱
- 버전 순서대로 자연 정렬 (19.4 → 19.5 → ... → 19.10 → 19.11)
- 중복 BUG 번호 자동 제거 (첫 등장 버전에만 표시)
- 패치 설명(patch_description) 포함

## 지원 패치 형식

- `COMBO_GI_RU_19.x.x.x.xxxxxx_pxxxxxxxx_190000_Linux-x86-64.zip`
- `GI_RU_19.x.x.x.x_pxxxxxxxx_190000_Linux-x86-64.zip`

## 사용법

### 기본 실행 (자동 파일명 생성)

```bash
python parse_bugs.py
```

마지막 Database Release Update 버전과 현재 날짜를 기반으로 파일명이 자동 생성됩니다.

```
Fixed_Bug_For_<DB RU 버전>_<날짜>.txt
```

예시: `Fixed_Bug_For_19.30.0.0.260120_20260122.txt`

### 출력 파일명 직접 지정

```bash
python parse_bugs.py my_output.txt
```

사용자가 원하는 파일명을 직접 지정할 수 있습니다.

## 출력 형식

```
### RU 19.4.0.0.190716_p29699097_190000_Linux-x86-64
 *** OCW RELEASE UPDATE 19.4.0.0.0 (29850993)
     BUG 25736599 - GI 12.2.0.1 CVU POST-GI-UPGRADE CHECK OF OCR AND OCR BACKUP
     BUG 26675491 - MAIN HAS SRGRSC2 ASM CONFIGURATION FAILS CLSGPNP_NOT_FOUND
     ...

### RU 19.5.0.0.191015_p30133178_190000_Linux-x86-64
 *** Database Release Update : 19.5.0.0.191015 (30125133)
     BUG 24687075 - SPACE ADVISOR TASKS/JOBS HITTING DEADLOCKS WITH GATHER DB STATS JOBS
     ...
```

## 파일 설명

| 파일 | 설명 |
|------|------|
| `parse_bugs.py` | 메인 스크립트 (간결한 버전) |
| `parse_bugs_old.py` | 동일 기능의 대체 스크립트 (상세 로깅 포함) |

### 출력 파일명 형식

| 조건 | 파일명 형식 |
|------|------------|
| 자동 생성 | `Fixed_Bug_For_<DB RU 버전>_<날짜>.txt` |
| 사용자 지정 | 명령줄 인자로 전달한 파일명 |

예시:
- 자동: `Fixed_Bug_For_19.30.0.0.260120_20260122.txt`
- 사용자 지정: `python parse_bugs.py my_bugs.txt` → `my_bugs.txt`

## 주의사항

> **중요:** 상위 버전 패치는 하위 버전의 모든 Fixed Bug을 포함하고 있습니다.

이 스크립트는 각 버전에서 **새로 추가된 Fixed Bug만** 출력합니다 (중복 제거). 따라서 정확한 버전별 Fixed Bug 목록을 얻으려면 **해당 버전까지의 모든 패치 파일이 필요**합니다.

예를 들어, 19.30 버전의 Fixed Bug 목록을 확인하려면:
- 19.4 ~ 19.30까지의 모든 GI RU 또는 COMBO GI RU 패치 파일 필요
- 중간 버전이 누락되면 해당 버전의 Fixed Bug이 다른 버전에 잘못 표시될 수 있음

```
필요한 패치 예시:
├── COMBO_GI_RU_19.4.0.0.xxxxxx_pxxxxxxxx_190000_Linux-x86-64.zip
├── COMBO_GI_RU_19.5.0.0.xxxxxx_pxxxxxxxx_190000_Linux-x86-64.zip
├── ...
├── COMBO_GI_RU_19.29.0.0.xxxxxx_pxxxxxxxx_190000_Linux-x86-64.zip
└── COMBO_GI_RU_19.30.0.0.xxxxxx_pxxxxxxxx_190000_Linux-x86-64.zip
```

## 요구사항

- Python 3.6+
- 표준 라이브러리만 사용 (추가 설치 불필요)

## 동작 원리

1. 현재 디렉터리에서 `*.zip` 파일 검색
2. 파일명에서 버전 정보 추출 후 자연 정렬
3. 각 ZIP 파일 내 `inventory.xml` 파일 탐색
4. XML에서 `patch_description`과 `bug` 요소 파싱
5. 이미 출력된 BUG 번호는 중복 제거
6. 결과를 텍스트 파일로 저장

## 라이선스

MIT License
