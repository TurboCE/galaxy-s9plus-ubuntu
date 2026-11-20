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
  최근 RTC용 receipt 루트는 `kernel48-rtc-irq`이며 프로필을 기준으로 조회합니다.
- `/var/lib/g965n-lte/desktop/config.json`: 모뎀 프로그램 핀. 파일 해시를 바꾸면
  해당 unit의 config-sha256도 갱신해야 합니다. APN/신원 정보는 출력·커밋하지 않습니다.
- `/usr/local/lib/g965n-native-nfc/pins.json`: Bluetooth/NFC 모듈 핀.
- `/usr/local/lib/g965n-gnss`: own-vendor HAL helper, supervisor, 개인 pin.
- `/run/g965n-gnss/nmea.sock`: GeoClue 전용 실제 GNSS 소켓. 단일 연결이며
  읽는 동안 GNSS 세션을 사용합니다. 원문을 터미널/파일/Git에 남기지 않습니다.

## 다음 작업 순서와 합격 조건

| 순서 | 작업·관련 소스 | 관찰된 문제 / 다음 조사 | 완료 판단 |
|---|---|---|---|
| 1 | GPS 후속 회귀: `experiments/gnss/` | gpsd NdkSensorsInfo 충돌을 private config의 hal SensorsEnable=false로 수정. 창가 재시험 300초/4,448문장/오류0에서 3D fix, 사용 위성8. GeoClue가 1.2초 이내 위치·보고 정확도3m 전달. 기본 수신/연결 문제 수정 확인 | 기본 fix는 확인됨. 추가 야외 이동/냉간 부팅/절전 복귀·장기 정확도·캐시 만료/오프라인 실제 회귀가 남음 |
| 2 | GPS 보조 데이터 | 순정 gps_psds.conf의 4day/v5 LTO를 HTTPS로 수신. 24h 캐시·4day Last-Modified 제한·해시·원본 설정 일치 검사. XTRA init/inject 모두0, 124,383바이트가 수신기 저장 파일과 일치. hourly 갱신 timer 연결 | 보조 데이터를 사용한 실제 fix는 확인됨. 보조 유무의 첫 fix 시간 A/B 비교는 안 함. SUPL/이전 위치 주입 미구현 |
| 3 (확인) | RTC: `experiments/rtc/` | DT의 IRQ_TYPE_NONE 때문에 경고. generic IRQ sysfs는 edge라 표시했지만 실제 GICD_ICFGR의 IRQ63/64 필드 값은1이고 bit1=0(level). generic 표시만으로 EDGE_RISING을 적용하면 안 됨. LEVEL_HIGH 적용 후 초기 부팅·별도 재부팅에서 경고/호출 추적0, 시계 진행·실제 알람·시간 유지 통과. 서비스 receipt 이관 및 재시작 확인 | 기본 회귀 완료. 냉간 전원·절전 깨우기·자동 시각 동기화는 미검증 |
| 4 (확인) | GPT: `experiments/storage/` | 실제 섹터4096, Samsung 헤더512. 원본 메타데이터를 기기·호스트에 보존하고 비어 있던 보조 영역20KiB만 복원 | 재부팅 경고0, 주 메타데이터 불변, 보조 CRC·25개 엔트리 동일 및6개 보호 파티션 불변 확인. 일반 자동 수리 명령으로 대체하지 않음 |
| 5 (다음) | 진동·LED: `experiments/pmic/`, `docs/g965n/PMIC_REVIEW.md` | 소스 수정 후보 있음. PWM 실클럭/핀·모터 전원·색상 전류 한계가 빠짐 | 보수적 실제 출력·정지·재부팅·오류 시 복원 확인 후 표준 input/LED 인터페이스·알림 연동 |
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

## GPS 회귀를 피하기 위한 기록

`serve.py`는 vendor gps.xml을 그대로 덮어쓰지 않고 private trial 복사본의
`hal SensorsEnable`만 false로 만듭니다. 원래 gpsd는 Android HIDL sensorservice가
없을 때 NdkSensorsInfo → NdkSensorsStart에서 null pointer로 충돌했습니다.
주 Ubuntu IIO/Qt 센서 서비스는 계속 사용하며 GPS daemon의 선택적 관성 보조만 끕니다.
HAL stdout이 열린 상태에서도 daemon의 종료를 감지하도록 `watch_hal`이 양쪽을
감시합니다. 예전의 5분 무응답은 대부분 실제 daemon 종료 뒤의 잘못된 대기였습니다.

`assistance.py`는 root 전용 `/var/lib/g965n-gnss-assistance` 캐시만 관리합니다.
원본 SYSTEM gps_psds.conf에 있는 qualified V5 주소를 HTTPS로 올리고, 다운받은
blob은 커밋하지 않습니다. 캐시를 FD4로 HAL에 전달하며 FD3의 NMEA와 분리합니다.
갱신 timer는 daemon의 격리된 network namespace를 풀지 않습니다. 보조 데이터가
없거나 만료되면 standalone 수신을 계속합니다. 위치 캐시는 아직 주입하지 않습니다.

선택적 `G965N_GNSS_DIAGNOSTICS=1`은 임시 root-owned systemd drop-in으로만 켭니다.
기본 설정에서는 꺼집니다. 메시지 필터는 좌표/식별자 문장을 버리고 오류 숫자/URL도
가립니다. 자세한 ptrace/GDB 결과는 private debug 저장소에만 보관합니다.

## 재현 범위

모든 수동 설정을 포함한 새 이미지 설치는 아직 검증하지 않았습니다. root README의
기본 이미지 빌드와 실험 모듈/서비스 설치를 구분하세요. 다음 큰 작업은 현재 기기와
소스의 차이를 설치 manifest/패키지로 통합하고, 복구 가능한 별도 실험에서 새 설치를
검증하는 것입니다. 기존 기기를 지워서 재현성을 추정하지 않습니다.


## 이번 RTC/GPT 후속 상태

RTC IRQ와 보조 GPT는 별도 재부팅까지 검증 완료했습니다. 복구 모드가 남긴
EFS ext4 메타데이터6바이트 변경은 기존4필드 제한 증명으로만 재검증했습니다.
원본 신원 파티션·작업 NV를 덮어쓰지 않았고 이전 확인 기록은 보존했습니다.
`scripts/g965n/revalidate-private-efs.py`와 RTC README에 격리된 재검증 경로를
남겼습니다. 재시도 가드를 삭제하지 않고 정상 재부팅으로 LTE 자동 시작 확인:
모든 주요 서비스 active/failed0, 모뎀 enabled이나 현재 망 idle/데이터 detached입니다.
GPS는 재부팅 후264초/정상2,852문장/오류0이나 위성0·fix없음이며, GPT 검증 재부팅으로
중단한 기록입니다. 예전 창가 fix와 구별하고, 하늘이 보이는 조건의 재부팅 후
재수신 검증을 남겨 두세요. 다음 개발 우선순위는 여전히 진동·LED입니다.
