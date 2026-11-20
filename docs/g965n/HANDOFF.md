# SM-G965N 작업 재개

2026-11-20 KST. 현재 작업 브랜치는 `codex/g965n-lte-audio`입니다.
먼저 [STATUS](STATUS.md)의 최신 요약을 읽고, 필요한 항목만
[VALIDATION](VALIDATION.md)과 [CHANGELOG](CHANGELOG.md)에서 확인하세요.
이전 행의 pending을 후속 성공 이력보다 우선하지 마세요.

## 현재 요청과 경계

카메라·지문을 제외한 드라이버/시스템 기능을 진행합니다. 문서 포털의
별도 WIP 작업을 합치지 않습니다. 개인 요청인 Tailscale·ChatGPT 설치는
공용 이미지/Git 구성에 넣지 않습니다. GPS 시험은 Wi-Fi로 진행합니다.
카메라·지문을 다시 시작하려면 사용자의 새로운 범위 지시를 확인하세요.

부팅/펌웨어/보정/신원 백업, 자격 증명과 실제 위치는 비공개입니다.
소스·패치·개인 정보 없는 요약만 커밋합니다. 빌드와 기기 쓰기를 분리합니다.
실기기 쓰기는 모델·현재 BOOT·검증 백업·승인 범위를 확인한 뒤 별도로 수행합니다.
RECOVERY/EFS/CPEFS/RADIO 및 부트로더를 복구 편의상 덮어쓰지 않습니다.

## 다시 접속할 때

1. Wi-Fi 주소와 개인 SSH 키는 로컬 연결 설정에서 찾습니다. Git에 저장하지 않습니다.
   USB 연결을 전제하지 마세요. 불명확하면 실제 라우팅과 Wi-Fi 연결을 확인합니다.
2. 현재 모델·BOOT·커널·백업은 읽기 전용으로 다시 검증합니다. 이 기록의 #48을
   다음 세션에서도 실행 중이라고 가정하지 마세요.
3. 실패한 unit과 전체 초기 `dmesg`를 확인합니다. journal에는 초기 경고가 누락됐습니다.
4. 현재 guard/profile을 읽고 그 경로/해시를 따라갑니다. 옛 실행 파일의 고정 경로를
   재사용하거나 검증을 끄지 않습니다.
5. 작업 하나가 검증될 때마다 CHANGELOG/VALIDATION/STATUS/이 문서를 갱신합니다.

현재 기기의 주요 상태 위치(내용은 비공개):

- `/var/lib/g965n-sensors/profile.json` 및 `profile.sha256`: 센서 supervisor·정확한 BOOT/백업 참조.
  최근 NFC용 receipt 루트는 `kernel48-nfc`였으나 프로필을 기준으로 조회합니다.
- `/var/lib/g965n-lte/desktop/config.json`: 모뎀 프로그램 핀. 파일 해시를 바꾸면
  해당 unit의 config-sha256도 갱신해야 합니다. APN/신원 정보는 출력·커밋하지 않습니다.
- `/usr/local/lib/g965n-native-nfc/pins.json`: Bluetooth/NFC 모듈 핀.
- `/usr/local/lib/g965n-gnss`: own-vendor HAL helper, supervisor, 개인 pin.
- `/run/g965n-gnss/nmea.sock`: GeoClue 전용 실제 GNSS 소켓. 단일 연결이며
  읽는 동안 GNSS 세션을 사용합니다. 원문을 터미널/파일/Git에 남기지 않습니다.

## 다음 작업 순서와 합격 조건

| 순서 | 작업·관련 소스 | 관찰된 문제 / 다음 조사 | 완료 판단 |
|---|---|---|---|
| 1 | GPS: `experiments/gnss/` | Wi-Fi 300초 시험에서 초기 NMEA 14개 뒤 갱신 없음, 사용 위성 0. HAL/daemon 지속 동작·LHD IPC·수신기/RF 경로 먼저 확인 | 지속 GNSS 샘플과 유효 GGA/RMC fix, 실제 GeoClue 위치 전달. 지도 위치만으로 통과시키지 않음 |
| 2 | GPS 보조 데이터 | NTP UTC 주입만 구현. standalone + 격리 network namespace라 SUPL/PSDS/LTO 다운로드·이전 위치 주입은 구현하지 않음. 원래 Broadcom HAL extension/지원 형식부터 조사 | 공식/허용된 출처의 올바른 형식, 만료·캐시·오류 처리, 전달 성공 및 실제 첫 fix 시간 비교. 타사 칩 파일을 임의 주입하지 않음 |
| 3 | RTC: `experiments/rtc/` | alarm IRQ63이 edge로 동작하지만 DT는 IRQ_TYPE_NONE. 먼저 GIC/드라이버 근거에 맞는 명시적 trigger 후보 검토 | BOOT-only 가드 적용 후 경고 없음, 시계 진행·깨어 있을 때 알람·재부팅 회귀 통과 |
| 4 | GPT | `/dev/sda` 논리 섹터 4096. primary header/array CRC 정상, 마지막 backup header 없음. 512바이트 가정의 첫 진단은 잘못된 가정이었음 | 먼저 원본 메타데이터/기하 보존 백업·쓰기 영향 검토. 수리 시 파티션 시작/끝·GUID·보호 파티션 보존 및 재부팅 검증. 검사 없이 자동 `sgdisk -e` 실행 금지 |
| 5 | 진동·LED: `experiments/pmic/`, `docs/g965n/PMIC_REVIEW.md` | 소스 수정 후보 있음. PWM 실클럭/핀·모터 전원·색상 전류 한계가 빠짐 | 보수적 실제 출력·정지·재부팅·오류 시 복원 확인 후 표준 input/LED 인터페이스·알림 연동 |
| 6 | 나침반/센서 | IIO/Qt/표준 앱 데이터 전달은 됨. 방향 정확도 미달 | USB/자석 분리한 기준 방향·기울기 비교 및 보정, 재부팅 후 유지 |
| 7 | GPU | 기본 가속/클럭 회귀는 통과한 이력. GNOME 실제 화면 애니메이션 버벅임 남음 | 실제 출력의 프레임 시간·장시간 부하 개선. 가상 모니터 성능만으로 통과하지 않음 |
| 8 | 통신·전원·주변 기능 | 데이터 SIM 망 등록, 복구/이동/IPv6, BT 프로파일, OTG·충전·절전·대기 전력 등 | 항목별 실제 시험. 과거 LTE/WFD 성공을 지우지 않고 최신 빌드의 회귀 증거를 추가 |

## NFC 회귀를 피하기 위한 기록

소스는 `experiments/nfc/`입니다. VEN active-low와 정상 전원 후 FIRM/wake 지연이
필요합니다. `.init`에서 순정 클럭 값 0x12를 vendor command 0x28로 보낸 뒤
CORE_RESET을 진행합니다. 이를 빼면 명령 응답은 성공해도 태그를 읽지 못했습니다.
neard는 패치로 active-tag socket을 먼저 닫아야 power-off EBUSY를 피합니다.
단순 Bluetooth unit의 After만으로는 NFC 준비가 보장되지 않아 `wait-ready.py`가
필요합니다. 3회 실제 읽기·꺼짐과 수정 후 warm boot 재읽기는 확인했습니다.
펌웨어/RF-register 파일 업로드는 이 성공 경로에 포함되지 않습니다.

## 재현 범위

모든 수동 설정을 포함한 새 이미지 설치는 아직 검증하지 않았습니다. root README의
기본 이미지 빌드와 실험 모듈/서비스 설치를 구분하세요. 다음 큰 작업은 현재 기기와
소스의 차이를 설치 manifest/패키지로 통합하고, 복구 가능한 별도 실험에서 새 설치를
검증하는 것입니다. 기존 기기를 지워서 재현성을 추정하지 않습니다.
