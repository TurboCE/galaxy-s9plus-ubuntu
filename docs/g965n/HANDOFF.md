# SM-G965N 작업 재개

2026-11-21 KST. 현재 작업 브랜치는 `codex/g965n-lte-audio`입니다.
먼저 [STATUS](STATUS.md)의 최신 요약을 읽고, 필요한 항목만
[VALIDATION](VALIDATION.md)과 [CHANGELOG](CHANGELOG.md)에서 확인하세요.
이전 행의 pending을 후속 성공 이력보다 우선하지 마세요.

## 최신 요청 — GPS 보류, 로그·기본 기능 우선

GPS 작업은 최신 사용자 요청으로 보류했습니다. 충전 LED 후속과 최신
재부팅 검증은 이 문서 마지막 절을 보세요.

사용자가 현재 성능이 충분하다고 수용했습니다. 추가 성능 변경과 그 목적의
재부팅은 중단했습니다. 최신 적용은 g965n-interactive-boost.service:
터치/키 입력 후500ms 동안만 표준 CPU QoS, 대기 바닥값349.916/1066MHz로
복귀. 두 번 실제 DSI 비교와1794MHz 하향 MAX 제약 준수 확인. 현재 부팅에서
별도 사용자 재부팅 후 자동 시작·현재 boot 소유권·실제 입력 후 상승/복귀를 확인했습니다. 소스/빌드/
보호 검사/복구는 experiments/interactive-boost/README.md를 보세요.
이것은 modem vendor bus QoS/ECT 미구현을 해결한 것이 아닙니다.

실효성 없던 성능 시험은 모두 복구했습니다: CPU governor schedutil,
전체 CPU affinity0..7, GPU min260MHz/poll50ms, Ubuntu Dock 활성.
타일 변환 후보는 GPU 정확도는 통과했지만 지연 개선이 없어 child profile을
복구했습니다. 기존 physical-neon48-final만 accepted 상태로 유지됩니다.
QA MAX·임시 키보드 모듈과 미래 시험 timer는 제거/중지 확인했습니다.
최종3초 표본에서 idle CPU 최소349.916/1066MHz 복귀도 확인했습니다.
GPU fault/심각한 커널 패턴/failed unit0이었으며 이는 전체 오류 없음 주장이 아닙니다.

후속 요청: Software Center/PackageKit/AppStream 및 공식 ARM64 Chrome 설치
완료. 설치 완료와 실제 GUI/앱 설치 흐름 검증은 구분합니다. 사용자가 ChatGPT
흰 화면 조사를 다른 컨텍스트로 넘기며 여기서는 중단하라고 했습니다. 앱 종료,
프로필 초기화·로그아웃·개인 자동 시작 설정 삭제는 하지 않았습니다. 앱 UI
조사를 재개하지 말고 원래 커널/시스템 로그 작업에 집중하세요. 개인 앱 설정,
프로필·계정·바이너리는 공용 Git에 넣지 않습니다. 문서 포털 별도 WIP·카메라·
지문은 기존 제외 범위를 유지합니다.

로그 후속: keyring PAM 모듈 누락은 패키지 설치/실제 dlopen으로 수정 확인;
새 로그인은 미검증. RGB0007 --named-regmap은 별도 모듈 빌드·현재 부팅
적용 후 별도 사용자 재부팅에서도 자동 구동·세 색 readback·core map 보존·중복 오류0 확인.
실제 적용 소스/복구는 experiments/pmic/README.md. 전체 ring 재수집의
초기 헤더 있음/error57/warn68, CPU 차이52+1, hub reset 미확인1, modem
QoS4는 남습니다. journal에는 초기 헤더 없음. Call trace/SError/PLL/GPIO
대상 패턴0, 실패 unit0. SAP/GDM/keyring 자동 로그인 경고의 구분·다음 조사
경로는 KERNEL_WARNINGS.md 최신 절에 기록했습니다. 경고 제거만을 위해
CPU strict mask·BT 권한·자동 로그인 또는 포털 설정을 바꾸지 마세요.

## 현재 요청과 경계

카메라·지문을 제외한 드라이버/시스템 기능을 진행합니다. 문서 포털의
별도 WIP 작업을 합치지 않습니다. 개인 요청인 Tailscale·ChatGPT 설치는
공용 이미지/Git 구성에 넣지 않습니다. GPS는 보류하며 재개 시 Wi-Fi를 사용합니다.
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

## 작업별 합격 조건 (GPS 항목 보류)

| 순서 | 작업·관련 소스 | 관찰된 문제 / 다음 조사 | 완료 판단 |
|---|---|---|---|
| 1 | GPS 후속 회귀: `experiments/gnss/` | gpsd NdkSensorsInfo 충돌을 private config의 hal SensorsEnable=false로 수정. 창가 재시험 300초/4,448문장/오류0에서 3D fix, 사용 위성8. GeoClue가 1.2초 이내 위치·보고 정확도3m 전달. 기본 수신/연결 문제 수정 확인 | 기본 fix는 확인됨. 추가 야외 이동/냉간 부팅/절전 복귀·장기 정확도·캐시 만료/오프라인 실제 회귀가 남음 |
| 2 | GPS 보조 데이터 | 순정 gps_psds.conf의 4day/v5 LTO를 HTTPS로 수신. 24h 캐시·4day Last-Modified 제한·해시·원본 설정 일치 검사. XTRA init/inject 모두0, 124,383바이트가 수신기 저장 파일과 일치. hourly 갱신 timer 연결 | 보조 데이터를 사용한 실제 fix는 확인됨. 보조 유무의 첫 fix 시간 A/B 비교는 안 함. SUPL 미구현. 시작 위치 주입은 아래2026-11-21 후속 참고 |
| 3 (확인) | RTC: `experiments/rtc/` | DT의 IRQ_TYPE_NONE 때문에 경고. generic IRQ sysfs는 edge라 표시했지만 실제 GICD_ICFGR의 IRQ63/64 필드 값은1이고 bit1=0(level). generic 표시만으로 EDGE_RISING을 적용하면 안 됨. LEVEL_HIGH 적용 후 초기 부팅·별도 재부팅에서 경고/호출 추적0, 시계 진행·실제 알람·시간 유지 통과. 서비스 receipt 이관 및 재시작 확인 | 기본 회귀 완료. 냉간 전원·절전 깨우기·자동 시각 동기화는 미검증 |
| 4 (확인) | GPT: `experiments/storage/` | 실제 섹터4096, Samsung 헤더512. 원본 메타데이터를 기기·호스트에 보존하고 비어 있던 보조 영역20KiB만 복원 | 재부팅 경고0, 주 메타데이터 불변, 보조 CRC·25개 엔트리 동일 및6개 보호 파티션 불변 확인. 일반 자동 수리 명령으로 대체하지 않음 |
| 5 (기본 출력 확인) | 진동·LED: `experiments/pmic/`, `docs/g965n/PMIC_REVIEW.md` | RGB 실제 세 색·15회 읽기 검증·모듈 정지/재시작·재부팅 자동 구동 통과. g965n-led.service, max_brightness1. 진동은 실제26MHz 카운터·GPIO 공급·FF_RUMBLE·IMU 반응·재부팅 통과 | LED/진동 알림 정책과 장기·절전·파형 보정은 미완료. 이전 SIGBUS/의존성 경고는 아래 후속 정정 참고 |
| 6 | 나침반/센서 | IIO/Qt/표준 앱 데이터 전달은 됨. 방향 정확도 미달 | USB/자석 분리한 기준 방향·기울기 비교 및 보정, 재부팅 후 유지 |
| 7 | GPU | NEON 유지+입력 후500ms QoS 실제 비교로 초기 지연 감소, 사용자 수준 수용 | 성능 추가 튜닝 중단. 이후 실로그 오류 우선, 서비스 별도 재부팅/입력 후 복귀 확인 |
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
재수신 검증을 남겨 두세요. RGB 출력/재부팅은 후속 검증으로 완료했고, 진동 PWM/모터 공급은 후속 검증으로 완료했습니다. 다음 우선순위는 실제 화면 GPU 비교입니다.


## RGB 기능 추가 및 진동 클럭 조사

`g965n-led.service`가 기존 max77705-rgb 자식에만 드라이버를 연결합니다.
본체 PMIC·충전 드라이버는 재연결하지 않습니다. 사용자 확인으로 세 색 실제 점등,
15회 레지스터 검증, 정지/재시작과 별도 재부팅 후 검증까지 통과했습니다.
현재 max_brightness1이고 기본 상태는 모두 꺼짐입니다. GNOME 알림 정책은 미설치입니다.
현재 설치/시험에 사용한 소스·패치·빌드·제어 절차는 experiments/pmic README를 보세요.

진동 경로의 vendor CMUCAL은 PWM gate를 PERIC0+0x2044, Q-channel을+0x3010,
상위 BUS mux/div를 TOP+0x10ac/+0x18b0로 설명합니다. 처음 다섯 레지스터 읽기는
성공했고, PLL_SHARED2 CON0/CON1와 DIV2를 이어 읽는 별도 프로세스는 SIGBUS로
종료됐습니다. 어느 접근에서 차단됐는지는 분리하지 않았으며 더 읽지 않았습니다.
어떤 클럭·PWM·모터 전원 값도 쓰지 않았습니다. 이 읽기 실패를 모터 고장이나
클럭 주파수 확인으로 해석하지 마세요. 고정 가상 클럭을 넣지 말고 기존 펌웨어
클럭 서비스 또는 적절한 커널 provider를 통한 접근 권한/실제 rate부터 조사하세요.


## 진동 후속 검증 — 이전 조사 정정

진동은 현재 g965n-haptic.service로 자동 등록됩니다. 기존 실제 오실레이터26MHz를
Samsung PWM에 연결했고, 카운터 실측26.06MHz로 확인했습니다. 모터 공급은 실제
GPIO gpg1-7, 패드는 gpp3-1이며 표준 FF_RUMBLE 입력명은 g965n-max77705-haptic입니다.
200ms 출력 4회에서 IMU Z변동202..311/대기약4, 자동 정지·전원/바이어스 off를
확인했습니다. 출력 제한과 독립 rail-off fallback, 정상 정지/재시작 및 재부팅 통과.
현재 원본 boost GPIO는 부트로더가1로 남기지만 서비스의 대기 전원은0입니다.
서비스 stop은 소비자를 제거한 후 원래 핀/GPIO 상태로 복원합니다.

앞선 Python SRAM SIGBUS는 접근 금지의 증거가 아니었습니다. 문서화된 ACPM 영역을
정렬된 volatile32-bit로 읽으면 정상이며 실제 펌웨어 PLL 주소 보정도 확인했습니다.
임의 바이트 읽기나 추측한 PLL CON1을 반복하지 마세요. PWM 기능 클럭은 APB 클럭과
별개로26MHz이므로 공유 PLL retune/가짜 fixed-clock가 필요하지 않습니다.
일반 func2 mux 이름도 없어서 Samsung pinconf FUNC API를 사용합니다.
첫 재부팅의 의존성 경고는 PWM class 대신 pwmchip_parent를 참조해 수정했고,
최종 별도 부팅에서 해당 경고/Call trace/Oops/BUG0, RTC/GPT 경고0, failed0입니다.

빌드/설치/권한/시험 재현은 experiments/pmic README와 HAPTIC_TRIAL.json을 보세요.
원본 haptic 소스의 GPL-2.0-or-later/저자 표기는 보존했고 새 board/controller는
GPL-2.0-only입니다. GNOME 알림/키보드 피드백 정책은 아직 연결하지 않았습니다.
GPS 후속300초 시험은 정상3,279문장/오류0이나 현재 위치 위성0/fix없음입니다.
기존 창가 fix 증거와 구별하세요. GPU 실제 화면 A/B는 아래 후속 결과로 대체됩니다.


## GPU 실제 화면 후속 — 현재 유지한 Shell overlay

`physical-neon48-final`이 accepted 상태로 실제 재부팅 후에도 유지됩니다.
부모 `mesa43-full`과 시스템 라이브러리는 보존되어 있습니다. 실행 중인 실제
Shell의 EGL/Gallium/GBM 매핑과 Panfrost render fd를 확인했습니다.
실제 DSI A/B/A paint p95는 약22..25→11..14→22..25ms, readback200프레임
오류0 및256MiB 부하 통과. frame-clock dispatch p95는17..24ms로 잔여 지연이 있습니다.
가상 모니터 비교만으로 개선이 없다고 했던 이전 기록보다 이 실제 출력 증거가 최신입니다.

상태: `/var/lib/g965n-mesa-trial/physical-neon48-final/state.json`.
수동 복귀는 이 상태의 `session.py restore --state <같은 상태 디렉터리>`를
root로 실행합니다. 먼저 자식 overlay를 복귀한 뒤 부모 프로필을 변경하세요.
부모를 먼저 지우거나 기존 라이브러리를 덮어쓰지 않습니다. 새 clean 빌드
경로는 `neon48-clean-rebuild/neon`이며 검증된 실행 라이브러리와 별개입니다.
새 builder는 `--variant neon`으로 두 패치를 새 디렉터리에 적용합니다.

재부팅 후 failed0/심각한 커널·GPU 패턴0, 주요 서비스 active, IIO7개,
Wi-Fi 지정 HTTPS204. 나침반 D-Bus Compass 객체는 Ubuntu 정책상 GeoClue만
직접 접근합니다. root/ubuntu의 AccessDenied는 결함이 아니며 로컬 전용
heading.sock 중계를 사용하세요. 정확도 보정은 여전히 별도 미완료입니다.


새 clean build는 사용자 unit `g965n-mesa-neon48-clean-build.service`에서
1325/1325 완료했습니다(Nice10/CPUQuota100%/jobs2). `neon48-clean-rebuild`의 비공개
로그/receipt와 unit 결과를 확인한 뒤 성공·실패를 기록하세요. SSH 연결과
무관하게 실행되지만 재부팅하면 중단될 수 있습니다. 완료된 새 바이너리를
자동 적용하지 않습니다. 다음 단계는 이 clean 결과의 별도 픽셀/실제 Shell
시험과 남은 frame-clock dispatch 지연 조사입니다. 현재 화면은 시험 전의
꺼짐 상태로 복원했습니다. NTP=yes/NTPSynchronized=yes 및 나침반 사용자
소켓6개 정상 범위 표본도 확인했습니다.


마지막 읽기 전용 확인: 현재 SIM은 searching/power on/unlock 불필요이며 실제
데이터 재검증은 못 했습니다. RTC와 NTP 동기화된 UTC 차이0.53초.
대상 dmesg 패턴 RTC/GPT/touch/sensor/P2P IF_ADD timeout0, vendor bus QoS4,
CPU capability 차이 안내9. QoS는 g965n_compat.h의 실제 미구현 안내이므로
표시만 숨기지 말고 실제 interconnect/frequency provider가 있어야 구현하세요.
clean build 마지막 진행202/1325, 실패 컴파일 표시0, 실행 중입니다.


## 최신 후속: 진동 대기 전원 수정

feedbackd를 설치·연결해 실제 표준 API100ms 출력을 세 번 확인했습니다.
원래 드라이버는 장치를 열어 둔 서비스 때문에 boost/bias가 계속 켜졌습니다.
서비스를 멈추고0006 idle-power 패치를 적용한 모듈만 교체해 해결했습니다.
현재 feedbackd가 열고 있어도 idle boost0/bias0/motor0, 출력 시1/1/1,
자동 종료 시0/0/0. 기존 guarded100ms/8192 검사도 새 idle-aware 도구로 통과.
user g965n-feedbackd.service는 enabled/active입니다. 보편적인 GNOME
알림·키보드 자동 피드백은 연결하지 않았으며 명시적 libfeedback 호출만 검증했습니다.

소스/핀/빌드/배치/복구: experiments/pmic/feedback/README.md,
HAPTIC_IDLE_POWER.json, builder --idle-power. 기존0005 모듈·test·두 pin의
복구본은 기기의 feedback48/pre-idle-module 비공개 경로에 보존했습니다.
되돌릴 때 feedbackd부터 중지/비활성화하고 기존 모듈과 도구·핀을 같이 복구하세요.
이후 전체 클린 Mesa 빌드가 완료됐고, 아래 후속 재부팅으로 새 진동 모듈도 검증했습니다.
기존978/1325 기록은 중간 진행 이력입니다.


후속: clean Mesa 전체 빌드1325/1325·receipt 검증 완료. 새 출력의 실제
Panfrost/Gallium 매핑 확인, readback100프레임/6,553,600바이트 오류0,
256MiB 텍스처 검사 통과. 실행 중인 Shell은 기존 검증 overlay 유지.
이제 새 진동 모듈 재부팅 회귀 시험을 시작했습니다.


## 현재 최종 상태 — idle-power warm boot 완료

새 진동 모듈과 feedbackd가 정상 재부팅에서 자동 시작했습니다. 첫 진동 전
boost0/bias0/motor0, guarded100ms 재출력/자동 off/close off와 표준 fbcli
실제 모터 on→자동 full-off 통과. 새 커널 호출 추적/Oops/BUG0, failed0,
오디오/센서/LED/BT/NFC/LTE 서비스 active. LTE 서비스 기동을 망 등록 성공으로
해석하지 않습니다. 기존 qualified Shell overlay는 그대로 유지됩니다.
clean Mesa 전체 빌드/검증/100프레임 픽셀·256MiB 검사는 완료됐지만 그 새
바이너리의 실제 Shell A/B는 아직 미검증이므로 자동 교체하지 않았습니다.

재부팅 직후 첫 Wi-Fi SSH는 시간 초과였고 다음 읽기 전용 확인에서 Wi-Fi와
USB SSH 모두 열렸으며 재시도로 정상 접속했습니다. 장기 재접속 완료 주장 없음.
다음 우선순위: 잔여 frame-clock dispatch 지연, 실제 provider/주파수 표가
필요한 modem QoS, 현재 SIM 망 등록, 나침반 정확도, 전원·절전 회귀.
카메라/지문 제외, GPS는 Wi-Fi 시험 경계를 유지합니다.


## 사용자 재부팅 후 드라이버 검증 — 2026-11-20

새 입력 서비스 자동 시작/현재 boot receipt 일치와 실제 커널 uinput Shift
시험 통과: 최소1499.333/2327MHz 상승 후349.916/1066MHz 복귀, 최대 불변.
neutral-keyboard-check.c는 독립 QA용이며 임시 입력 모듈/장치와 정리 timer는
제거했습니다. Mutter 내부 가상 입력의 첫 시험은 커널 핸들러 증거가 아닙니다.
LED 이름 변경본도 자동 시작·세 색 읽기·core map 유지·부팅 중복 오류0 통과.
진동100ms/8192 on/auto-off/close-off, Wi-Fi 지정 HTTPS204 및 IIO 값 읽기 확인.

최종 전체 ring1,024줄/error57/warn68, boot header 있음; journal423줄은 초기
header 없음. CPU 차이52+1, hub reset 미확인1, modem QoS4 유지. 정상 GeoClue
GPS 세션은 active. 별도 비허용 계정의 소켓 접속을 거절한 failed GNSS
인스턴스1개는 보존했습니다. user 문서 포털 실패는 별도 WIP 제외 범위입니다.
현재 상태를 전체 실패 unit0으로 쓰지 마세요. 다음 조사는 KERNEL_WARNINGS.md
최신 절과 아래 provider 제약을 따릅니다.

PM_DEVFREQ/INTERCONNECT core는 켜졌지만 실제 devfreq는 GPU만 있고 Exynos
bus/Samsung ICC provider 설정·DT endpoints/ECT 표가 없습니다. CP mailbox
인덱스→실제 rate 표와 CPU cluster 대응부터 확인하세요. 임의 rate/전압·허브
failsafe reset 쓰기나 경고만 제거하는 변경은 하지 않았습니다.


xgps 연결 후속: GNSS README의 xgps 절을 참고. /usr/local/bin/g965n-xgps가
일반 사용자 GeoClue client를 유지하며 GPSD2948로 접속합니다. g965n-xgps
서비스는 private PTY/루프백 전용. serve.py 비차단 tap은 viewer 없이도 기존
GeoClue를 유지하며 viewer 명령을 HAL로 보내지 않습니다. 실제 NMEA/TPV 전달
확인, 위성 fix/실외 정확도와 새 서비스 재부팅은 미검증. 원본 helper는 기기에
비공개 백업. GeoClue 전용 NMEA 소켓 권한을 열거나 직접 진단 접속하지 마세요.

Final xgps check: connected-port2948 window confirmed through accessibility,
ordinary-user launcher active,145 live TPV messages received with mode1 (no
position fix). Stock launcher was shadowed only by a per-user xgps.desktop
pointing to the connected wrapper; package launcher preserved. The bridge
restart disconnected an earlier viewer; launched a new connected window and
verified delivery after receiver startup. No satellite-fix claim.


## 기지국 위치 기능 완료 및 GPS 환경 제약

LOCATION_REVIEW.md를 우선 읽으세요. 새 root-only cell-list-request/cell-info
브로커와 LTE decoder→MM GetCellInfo/3gpp 위치 소스가 실기기에서 동작합니다.
두 차례 일반 재부팅/모델·BOOT·백업·핀 확인, LTE20개/serving1개와 원본 필드
일치2회, 위치 수집 해제 시 clear/재활성 시 복구 통과. 프레임/신호 단위와
다른 RAT를 추측하지 마세요. 현재 EPS2/searching이며 등록 성공 비교는 남음.
원본 plugin/RIL/config/service는 기기에 비공개 보존. 재현은 기존 MM 빌더;
실행 중인 서비스 코드 변경 시 config 파일 핀과 unit config-sha256 함께
갱신하고 once-per-boot guard를 지우지 말고 정상 재부팅을 사용하세요.

GPSD 관찰만으로는 receiver가 켜지지 않습니다. gpsd-summary.py를 허용된
데스크톱 사용자로 실행하면 GeoClue client를 유지합니다. 당시 사용자 설명에 따라 window0sat/no-fix를 환경 제약으로 기록했으나,
같은 위치의 다른 Android 신호 사진으로 그 단독 원인 판단을 철회했습니다.
아래 최신 동일 위치 비교를 우선합니다. 수신 가능한 장소에서 최종 fix 확인이 남고 GPS 드라이버 임의
수정은 하지 않았습니다. standalone/start/UTC/XTRA0와 유효 NMEA 전달 확인.
과거 실기기 fix 성공 증거는 유지합니다. BeaconDB/submit-data=false 보존.


위치 fallback 질문 후속: 요청 중 MM source1 활성화/요청 종료 후 비활성은
정상 on-demand 동작. GeoClue accuracy25000m 반환; 기지국 데이터 전달 완료와
기지국 DB 좌표 조회 성공을 구분하세요. 아직 cell-specific 좌표 검증은 남음.


## 2026-11-21 — GNSS start-position assistance

experiments/gnss/README.md와 LOCATION_REVIEW.md를 읽으세요. seed.py와
FD5 시작 위치 주입, g965n-gnss-seed-cache.service 설치. private cache는
root0700/files0600, 원본 timestamp300s·350m/s 불확실성·100km 상한 정책입니다.
실제 GPSD mode2/3만 GNSS 캐시가 되며 현재 mode1은 저장되지 않았습니다.
좌표·캐시·pin·rollback·원본 디버그 로그는 기기에 비공개 보존합니다.

중요한 ABI 수정: Samsung 위치 요청 콜백이96-byte legacy prefix 뒤에 있어
이전 짧은 테이블이 IPC thread SIGSEGV를 유발했습니다. 명시적104-byte 정적
테이블/offset assert/카운터 핸들러로 고쳤고 실제 콜백1회 및180초 유효 데이터
전달을 확인했습니다. upstream legacy GpsCallbacks에 그 필드가 있다고
가정하지 마세요. 수신 thread 안에서 GeoClue 재진입·네트워크 조회나
GNSS-derived 위치를 independent 응답으로 재주입하지 않습니다.

수정 HAL 일반 재부팅 후 모델/#48/BOOT/보호 백업/실행파일 핀 재확인.
센서·GNSS 소켓·GPSD bridge·캐시 서비스 자동 active. 재시험91초에서
NMEA687/TPV498, 위치 요청 콜백1회, 해당 부팅 GNSS 예외0 확인.
시작/standalone/UTC/위치/XTRA init/inject0. unit 검증 통과, 배포된
serve.py/seed.py 소스 해시·0600 일치. 위성0/mode1이며 새 fix 증거는 아님.
이전 실패·복원·재부팅·known state 보존 절차는 CHANGELOG에 있습니다.
알 수 없는 GPS 상태를 자동 삭제하거나 검증 guard를 우회하지 마세요.
셀-only404와 coarse25km를 구분하고 실제 새 fix cache/TTFF/SUPL을 완료로
쓰지 마세요. SUPL은 AGPS callback/network lifecycle·server/TLS·제한된 transport
설계가 남았습니다. 전역 vendor network isolation 해제는 하지 않았습니다.
GPS는 Wi-Fi로 계속 검증하며 커널/BOOT/펌웨어 변경은 없었습니다.


## 2026-11-21 — Same-place Android satellite fix comparison

환경만으로 위성0을 설명하지 마세요. 다른 Android의 같은 위치 사진은
4신호/2사용·21–27·No Fix입니다. 앞선 실제 fix 보고와 사진이 직접 증명하는
수신을 구분하세요. 사용자는 현재 USB 분리가 어려움; 새 질문으로 반복하지
마세요. GPS 제어는 계속 Wi-Fi이며 USB configured 상태에서만 측정했습니다.

현재 HAL은 network-only request reply가 실제 동작한 d1c926ca... baseline.
seed.py의 sample_accuracy와 FD5 원래 timestamp를 C가 매번350m/s로 증폭해
late replay를 검증합니다. --seed-independent는 network source만 받습니다.
UTC/XTRA callback/first-NMEA retry는 효과/실제 이벤트 검증이 부족해 제거.
source/핀/원본 롤백은 기기에 비공개. 마지막 clean60s356 NMEA/257 TPV,
mode1/0sat입니다. 정상 NMEA를 GPS fix 성공으로 쓰지 마세요.

receiver-status.py는 별도 authorized GeoClue/xgps/GPSD summary가 수신기를
유지할 때 일반 사용자로 --seconds60 실행. checksum/STA common-prefix를
검사하고 식별자·좌표·실제 UTC 없이 aggregate만 출력합니다. tPeF/TimeSource0/
ephemeris0은 Quectel version10 참조의 추론이며 own Samsung version9 공식
규격 확인이 아닙니다. NMEA invalid time을 실제 UTC drift로 계산하지 마세요.

자세한 수치·부정 결과·재현법은 LOCATION_REVIEW/README/CHANGELOG에 있습니다.
임시90-rf-diagnostic.conf 제거·logger/ptracer0 확인. metadata tracing은
불완전했고 남은 known trial state5개를 owner 종료/exclusive lease 후 비공개
보존하여 복구했습니다. unknown state 자동 삭제·수신기 GPIO/전원 추측 변경
하지 마세요. 다음은 RF 수신/보조 정보 실제 소비 확인, 가능할 때 USB 분리
대조, 필요 시 정확한 계층을 증명한 뒤 transport 관측입니다. 정적 mixed-frame
경로 후보는 실제 혼합 패킷을 확인하지 못해 수정하지 않았습니다.


## 2026-11-21 — GPS 제외, 충전 LED/시스템 후속

최신 지시는 GPS 제외입니다. RF/보조 데이터 실험을 재개하지 마세요.
커널/BOOT 변경 없이 같은 #48 일반 재부팅과 정확한 모델/BOOT/보호 백업
검사 통과. Wi-Fi scan3회/HTTPS204·새 timeout0, warm boot HTTPS204 확인.
기존 timeout 해결 또는 BT 프로파일 전체 정상으로 쓰지 마세요.

새 experiments/pmic/power-leds.py 및 g965n-power-leds.service 설치/enable,
재부팅 자동 실행과 현재 boot 소유 상태 확인. red=charging/green=full native
trigger, blue/white 보존·cap1. 실제 Charging/red1→Discharging/red0 확인.
커널 트리거만으로 순전류 전환을 못 갱신해 실제 UPower StateChanged에
재활성화합니다. 전류·전압·PMIC charger 설정은 바꾸지 않습니다.
UPower 표본 지연 존재; 완충 green/물리 USB unplug/장기·절전은 미검증.

Type=simple 조기 종료 경합은 early signal/finally/Type=notify READY로 수정.
start/stop 원복·수동 red 소유권·restart 통과. 초기 실패의 알려진 소유 상태는
guarded stop으로 보존/해제했고 임의 삭제 안 했습니다. 원본 helper/unit은
root 전용 보존. PMIC README의 설치·중지·복구를 따르고 LED pulse 시험 전에는
이 정책을 먼저 stop하세요. UPower Refresh 지원은 객체마다 가정하지 마세요.

최신 early ring956줄 CPU52+1/hub1/QoS4 유지, targeted 심각 패턴0,
새 부팅 failed units0. ALS131lux/IIO7개/관련 서비스 자동 active.
ModemManager introspection으로 실제 GetCellInfo 제공 interface를 찾아
21cells/1serving read 확인; registration2/searching이며 LTE data pass 아님.
온도는 내부 TMU 보호가 이미 있으나 CPU/GPU hwmon 표시는 미연결입니다.
새 커널은 만들거나 설치하지 않았습니다. 개인 ChatGPT 문서 변경48줄은
기존 다른 작업이며 이번 공개 커밋에 섞지 마세요.


## 2026-11-21 — 차량 전원 자동 부팅 실패 보고

사용자가 종료 후 USB 전원을 넣어도 Ubuntu로 부팅되지 않는다고 확인.
자동 시작 앱/일반 재부팅과 구분하고 차량 cold-power-on은 미지원/미검증으로
기록하세요. VEHICLE_POWER.md의 소스 점검과 bounded 시험 경로를 읽으세요.
현재 guard/접속/charger online1만 확인했으며 새 종료·케이블 재연결 시험은
하지 않았습니다. 충전 아이콘/삼성 로고/검은 화면 여부 질문의 답이 필요합니다.
shim은 incoming FDT 대신 embedded DT를 쓰므로 현재 cmdline에 charging
인자가 없다는 사실로 충전 모드가 없다고 단정하지 마세요. INFORM2/3/PMIC
임의 쓰기·S-Boot 업데이트/재잠금 없이 실제 진입 지점을 먼저 확인합니다.
현재 BOOT·설정·개인 앱·GPS는 변경하지 않았고 Codex 차량 서비스도 아직 없습니다.


## 2026-11-23 — 배터리0%/충전 비활성 복구

사용자 삼성 로고/진동 반복 보고. actual USB online1/22C이지만
charge_behaviour=inhibit-charge·배터리0%/3.08–3.20V·순방전 확인.
사용자 충전 복구 요청 후 기존 exact model/#48/BOOT/protected backup guard
통과, private before/after 보존하고 charge_behaviour=auto만 적용했습니다.
5–20초 실제 Charging/순충전60–98mA/평균57mA/3.225V. 입력500mA·충전
450mA·CV4.2V 불변. Wi-Fi는 안 돼 USB SSH 사용; 접속 helper를 메모리에서만
USB 목적지로 바꿔 실행했고 자격 증명·원본 helper는 출력/변경 안 했습니다.
CHG_EN off 이유는 미확정이며 고장 상태를 주기적으로 auto 덮어쓰는 서비스는
추가하지 않았습니다. 이전 커널 로그 공백 때문에 패닉/워치독 배제 불가;
11/19 archived SError를 이번 사건으로 단정하지 마세요. 현재0%라 실제
충전 유지·잔량 상승 확인이 필요. boot/firmware/current/voltage 변경은 없습니다.


## 2026-11-23 — 안드로이드 충전 정책 동일화 후속

새 요청: Android와 CHG 허용비트 운영을 맞추기. experiments/charging/README.md,
REFERENCE.json부터 읽으세요. Native와 같은 PMIC지만 sec-battery 상위 정책과
ADC 온도 입력이 빠져 있어 CHG=1 반복으로 대체하면 안 됩니다.
소스 후보는 intent/actual 분리·mutex·probe-ready gating·read-only 두 속성만
추가. 실제 C 테스트8PASS/이전 source migrationPASS/ARM64 objectPASS.
외부 모듈 link는 qualified Module.symvers 없어 실패; 우회 안 함. 새 커널/
module/기기 적용/자동 enable은 안 했습니다. 빌드와 장치 동작을 구분하세요.
기기는 여전히0%/22C/3.314V/순충전이고 sensor unit failed(하위프로세스
readiness 전 종료)/root IIO0. 재시작·허브 리셋은 하지 않았습니다.
실제 배터리 ADC4/USB ADC1/충전부 ADC3(provider exynos-adc-v3,0x14230000)
및 보정·freshness/오류 처리가 먼저 필요. SSP thermistor와 FG 온도를 대체
입력으로 쓰지 마세요. 공개 EUR rev26 한계값은 소유 Korean firmware와 아직
대조 전이므로 실제 setpoint로 적용하지 않습니다. 저잔량에서 BOOT 교체/
재부팅을 강행하지 마세요. 원래 GPS/카메라/지문/개인앱 제외 유지.


## 2026-11-23 — ADC 실측·충전 중단 재현 후속 (최신)

experiments/charging/README.md 및 REFERENCE.json의 최신 기록부터 읽으세요.
qualified #48 ABI45d68e…로3개 diagnostic 모듈 compile/modpost/link 성공,
실제 ADC5×4 및 regmap snapshot 완료 후 제거. ADC는 firmware-held clock
readiness만 확인하며 gate/PLL/rate를 소유하지 않음; 상시 PM 지원 아님.
저장 sample 변환37.7/35.5/39.9C, FG22C. original BOOT wired table 대조 완료.
public calibration로 diagnostic 변환은 가능하지만 과거 receipt를 live 보호
입력으로 쓰면 안 됨. 공급자 상시화/freshness/thermal policy/full/recharge 남음.

CHG1/NotCharging 상태 snapshot charge6/battery2/input3/lock0. 사용자 USB
10초 재연결 뒤 charge1/battery4/input3/lock0 및 net+80–122mA·8%/3.67V.
입력 재연결로 이 fault가 해제된 실물 증거; 원인과 안전한 software recovery
미확정. lock0만 보고 reset/reinit하지 말 것. Exact Samsung conditional
recovery는8/11에 한정되며6의 복구를 임의 확장하면 안 됨. 장기 charging
관찰 및 persistent calibrated temperature integration을 다음에 진행하세요.
private 설치/receipt는 기기 root 전용; credential helper 출력 금지.
재부팅/BOOT/보호/전류·전압 변경 없음. 이 boot 센서 service 실패는 별도 잔여.

재연결 후30초4표본의 마지막3.716V/평균+236mA, Charging/Good 유지.
이는 짧은 관찰이며 다음에는 장시간 상태/잔량 상승부터 확인하세요.


## 2026-11-23 — 연속기록 운영·다음 충전 조사 (최신)

experiments/charging/README.md·CAUSES.md를 먼저 읽으세요. actual IC CNFG01
0x91(timer1/restart1/prequal1) vs native init0/3/0 불일치가 새 근거입니다.
locked0은 정상충전에도 보였으며 init write가 안 먹었는지 이후 변경됐는지는
모릅니다. upper safety-time/thermal policy 없이 unlock/타이머 disable을
복구라며 강행하지 마세요. charge6 의미를 타 chip datasheet로 단정 금지.

기기 root /usr/local/lib/g965n-adc-trial에 pinned observer5scripts/3modules/
observer-pins.json 설치. g965n-charge-observer.service active/enable.
/var/lib/g965n-charge-observer/samples*.jsonl(4×4MiB), /var/log/audit/
audit.log(4MiB·3files)는 private; boot IDs/raw로그 공개 금지. audit sysfs
3개 owned watch는 helper가 normal discovery 후 복구하며 타 rule 삭제 안 함.
ausearch -if /var/log/audit/audit.log -k g965n_charge_control --raw 사용;
기본 query는 no matches였지만 explicit input 실제 SYSCALL/python/path 검증.
open-for-write만 시험했고 제어 write는 안 했음. kernel 내부 write는 audit
대상이 아님. module getter는 현재 regmap 값을 읽으며 IRQ-clear register 제외.

후보 source readback/mismatch/error propagation/caller/init/cleanup 로깅은
아직 새 커널로 적용 안 함. full/recharge/current/time/swelling enforcement
및 재부팅/절전/장기 관찰이 다음 작업. 온도 gate는 shadow이고 auto-enable
루프 없음. battery15%/기록38개·온도 오류0 확인. startup guard 충분한 잔량
요건 때문에 저잔량 reboot를 강행하지 말 것. 반복 upgrade stop/start의
start-limit-hit는 정상 exit/원복 확인 후 unit reset-failed로 복구했습니다.
개인 문서48줄은 별도 기존 변경이므로 이번 커밋에도 섞지 마세요.

추가 후보: src/mainline-dts battery charge ceiling4.35V(순정3종 일치),
initializer는 design rating 대신 charge ceiling을 쓰고 design 상한/4.2V
fallback/지원범위·에러를 검사. ARM64 object 및 C tests PASS·미설치,
live4.2V 불변. 최종 observeractive/Resultsuccess·auditlost0·dpkgclean.


## 2026-11-23 — 현재 #49, #50 pending (이후 최신 기록 우선)

실제#49 적용·일반 warm boot 완료. profile=/var/lib/g965n-sensors/
kernel49-charging, source receipts/model/BOOT/보호백업 검증 유지.
기존9개서비스 active, CV4350/timer0/restart3/prequal0. CC는bootloader900을
상속해 helper로450 이하·input500 이하 감소. 이전 .local/context/charging49
private에서 build.json/backup path/flash log/원본#48 보관. 공개 builder
같은 timestamp 사용 시 설치 Image와 hash 동일. failed AS/early voltage
refusal 후보는 BOOT에 쓰지 않음.

#49 guardian은 실제 stale측정 차단을 검증했지만 자동 재개가 없어 startup
voltage dip→observer 초기 실패/재시도 뒤 충전off가 남음. 원인은 로그로확인,
manual restore로정상 충전. 해결용#50 CAS 소스·BOOT 후보 .local/context/
charging50 준비; user intent와policyBlocked 분리, manual generation을
동일mutex에서 비교하므로 수동 inhibit를 회복경로가 덮지 않음. 아직50
실기전; controller/manifest도 함께 이관해야 하며 current #49 artifact와
protected9backup을 새로 보존 후 BOOT만 갱신. 현재35가지 host검증은 코드
검증이며 실제50부팅/자동복구/완충/재충전 증거와 구분할 것.

private 원인기록: 첫 fault는 재연결 후10753초, temp38.7/36.4/40.8C·
CHG1/input3/config0x91, control write없음. bounded 한번 CHG edge로 정상
복구. 타이머 추정 강하지만 exactchip 의미/이전 config 리셋 이유 미확정.
개인 문서48줄은 계속 별도이며 이번 공개 커밋에도 포함하지 말 것.


## 2026-11-23 — latest #50 charging continuation

Current real kernel#50 SMP PREEMPT Mon Nov23 06:23:32 UTC2026. Exact model/BOOT/
protected-backup/module guards remain; profile kernel50-charging. Private build,
backup path, migration pins and flash receipt in .local/context/charging50/.
USB staging outage recovered after user replug with sync transport; failed raw
transfer never touched BOOT. Source/build/install helpers and tests are public;
private artifacts are excluded. Preserve unrelated personal48 doc lines.

Both charging units survive warm boot. On50 policy uses CAS generation and
preserves manual intent, including restart/data recovery. Initial qualified
voltage wait stays bounded; do not lower threshold. External-power sleep lease
and BOOTTIME counters are live; final warm boot triggered swelling thermal pause.
Do not force enable to obtain a soak pass. Inspect calibrated temperature,
state.json reasons, actual CHG and mean current. The read-only three-hour soak
unit g965n-charging-soak writes root-only latest-soak-path/result.json; pending
is not pass, protection pause is inconclusive for uninterrupted charging.

Next: inspect soak and continuous logs, qualify actual full/recharge and USB
cycles under safe conditions; implement adaptive stock policy only after review.
No forced thermal extremes or low-battery reboot. Timer config evidence is strong
but first CHG0/original config origin unproved. MANAGEMENT.md lists remaining gaps.

Final observation detail: calibrated battery42.6C/USB37.4C/charger47.6C
triggered conservative swelling stop41C (recover39C). Sixty-second smoke was
INCONCLUSIVE, faults=[]; reported mean current approximately-834mA during
thermal pause. Short-check sample counting was corrected to the recorder's
15-second cadence (not its faster polling interval). Deployed corrected
read-only checker and restarted bounded observation as
g965n-charging-soak-final.service. Positive long-duration charging is pending.

Follow-up calibrated44.5/39.0/50.5C still correctly held CHG off, faults
false. Three-hour final soak and both charging services were active. Current
boot's targeted BUG/Oops/panic/charge-failed search returned no entries
(journalctl exit1 means no match here). Foreground ChatGPT/desktop CPU load
was substantial; requested ordinary GNOME screen blanking to reduce display
load without terminating user apps. Full thermal/load qualification remains open.


## 2026-11-23 — calibrated thermal cooling overlay, live trial

Model/current#50 BOOT/protected-backup guard passed before writes. No reboot or
partition/voltage change. Existing idle undervolt switches remain OFF because
of documented historical hangs. Screen was truly DPMSoff/backlight0, not merely
a locked desktop. GPU remained runtime-active; no touch IRQ growth in3s.

Bounded guarded120s trial capped CPU650/1066MHz and GPU260MHz with independent
240s compare-before-restore rollback. Reported average discharge fell from
about748mA to450-470mA; calibrated battery46.8C did not yet cool. CPU PLL timeout
counter continued~39.5/s. Increasing standard schedutil rate_limit_us20ms→200ms
reduced this counter to~4.7/s over30s; hardware PLL lock handling itself remains
unfixed. Do not claim zero warnings or complete thermal normalization.

Built/loaded dedicated g965n-thermal-qos module against qualified native ABI,
with exact model/BOOT/backup and module hash/vermagic checks. Independent
CPU MAX QoS requests and GPU DEV_PM_QOS_MAX_FREQUENCY requests cap650/1066/260
without replacing user requests or bypassing kernel protections. Actual effective
CPU bounds and GPU260MHz read back. Guarded root-owned enabled service uses
fresh calibrated battery41C/recover39C hysteresis; invalid/stale data retains
cooling. Service failure/stop retains cooling; unloading only the owned module
removes its requests. Cadence ownership preserves later external changes.
Actual restart retained module ownership and cap. Host4 policy tests PASS.

At last sample battery47.1C/USB40.9C/charger51.4C, SOC10%, CHGoff and mean
reported discharge497mA. Upper charging protection still blocks charging. This
is mitigation evidence, NOT a thermal/energy/endurance qualification. GPU idle
reference diagnosis continues with a separate read-only counter module candidate;
no forced runtime suspend, raw rail writes, undervolting or reboot attempted.


### Thermal investigation follow-up — GPU work source and rollback

Optional GPU snapshot read busy1/jobs1/PMref1, then changing job fence sequences
owned by ChatGPT, followed by busy0/jobs0/PMref0. No stuck-job claim. A guarded
20s SIGSTOP of only the verified GPU helper, with PID-start checked independent
35s resume fallback, yielded actual runtime suspended and instantaneous battery
current~+4/+2/-8/-4mA versus~-584mA initially. GPU helper resumed normally;
this demonstrates a material offscreen-rendering contribution, not a completed
long-term thermal test. No automatic app pause is installed.

A separate bounded1% CPU-budget scope experiment did NOT improve GPU runtime
suspension and was rejected. CLI CPUQuota=infinity restore syntax failed; native
D-Bus UINT64_MAX property restored unlimited quota immediately, confirmed by
systemd. The GPU helper was returned to the matching browser/zygote original
cgroup after checking parent relationship. An initial restoration precondition
incorrectly assumed user-0.slice and refused without moving; actual app parent
was in user-1000 app.slice. It was corrected and original grouping verified.
No app pause, CPU quota or permanent app configuration change remains.

Read-only owner snapshot first compile failed on opaque panfrost_job_slot;
corrected exact pinned source-layout definitions retain upstream copyright,
compiled and actually read safely under locks. QA module unloaded afterward.
Cooling service remains active/enabled with actual independent CPU650/1066 and
GPU260MHz limits, cadence200ms. Timer restored the earlier trial's direct user
limits successfully; QoS overlay continues separately. Four policy tests PASS.
Battery48.6C/SOC7%/continued discharge was still observed after app resumed.
Therefore heat, offscreen app rendering and energy balance are NOT resolved.
No hot/depleted reboot qualification or Android-parity claim. See thermal README.


### Latest thermal state — app closed for recovery, cooling retained

Because battery depleted to7% while hot, verified main ChatGPT executable
received graceful SIGTERM (no configuration/data/autostart changes). Main
process exited; at15/30/45s GPU runtime was suspended and instantaneous battery
current approximately+10/-7/+3mA. Later calibrated battery fell48.6→47.3C and
charger52.6→49.5C, mean battery current~-3mA, SOC6%, VBAT3.61V. This confirms
a substantial active offscreen rendering load; no forced charging or app pause
remains. App can be launched normally; reopening may reproduce the workload.

Native cpuidle driver reports none/state count0. Architecture WFI fallback may
still exist; absence of deep idle is a port limitation, not proof of CPU100%
utilization. No speculative PSCI/idle voltage/CPU-off changes made.

Cooling source now also refuses nonprivate/symlink state/install directories;
updated controller restart active. GPU request release exposed572MHz and
reapply260MHz. Immediate CPU readback can precede async QoS policy work; do
not interpret an immediate unchanged bound as failed request removal.
Root-private observer/guardian/cooling remain enabled+active. Actual reboot
and full cold-to-hot-to-recovery cycle for the new service remain pending.

Final QoS release verification waited0.5s for asynchronous CPU policy work:
released bounds1499.333/2327MHz, reapplied650/1066MHz, controller restarted.
This confirms the overlay removes only its own CPU requests. No reboot used.

Latest recovery sample: calibrated battery45.5C (from48.6C), charger47.3C;
GPU suspended, mean battery current+625uA (approximately neutral), SOC6%.
Observer/guardian/cooling all active. Charge remains thermally inhibited; this
is cooling improvement, not resumed or long-duration charging qualification.


## 2026-11-23 — continue thermal recovery with screen-off QoS

Latest controller source experiments/thermal/thermal-control.py deployed after
old/new hash/model/BOOT/protected-backup guard, original saved in root-private
before-display-idle-* directory. Module/pins unchanged. Hot/off state, restart
and transition journal verified. Separate panel/thermal state prevents releasing
clock caps merely because the hot latch clears while display remains off.

Inspect /var/lib/g965n-thermal-qos/latest-recovery-path -> result.json and
g965n-thermal-recovery50.service. It is read-only, bounded1200s; requires actual
hot-stop/cold recovery and120s positive reported net charging under screen-off
ceilings/no faults. Pending is not pass. At last sample41.7C, SOC6%, near0mA.
Keep existing voltage/temperature/backup guards; no hot/depleted reboot.


## 2026-11-23 — thermal recovery PASS, latest code and evidence

Controller now has display-aware QoS, complete-record reader and protected
same-boot thermal latch persistence. Source deployed after actual model/BOOT/
protected-backup and predecessor hash checks; private predecessor backups kept.
Module/pins unchanged. Cold displayon/off and controller restart verified.
On1499.333/2327/572MHz+20ms; off650/1066/260MHz+200ms. Restore timer canceled.

Final g965n-thermal-recovery50-final passed122s sampled positive screen-off
charging following observed hot-stop/natural cold39.0C/automatic CHG recovery.
Private result pointer /var/lib/g965n-thermal-qos/latest-recovery-path. Initial
checker was intentionally interrupted for async-phase/gap fixes, not a device
fault. At qualification38.9C/current+171mA/SOC6%. No reboot or forced enable.
Eleven host tests pass. Sustained workloads/full-cycle/voice and reboot remain
unqualified. ChatGPT remains closed; do not claim its rendering problem fixed.
Do not enable historically failed idle voltage/PSCI or Wi-Fi power-save paths.


Post-cycle idle check: battery38.7C, mean+171mA and Charging, GPU suspended,
observer/guardian/cooling active. Started a NEW bounded10800s read-only
g965n-charging-soak-cooled50.service from this cooled charging baseline.
Stopped the earlier pre-cool soak intentionally; its thermal pauses never
qualified uninterrupted charging. New three-hour result is PENDING; inspect
the result.json inside the directory named by
/var/lib/g965n-charge-observer/latest-soak-path (a private pointer file). This does not reset
guardian safety budgets, change charging controls or auto-restart ChatGPT.
