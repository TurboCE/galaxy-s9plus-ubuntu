# G965N experiments and fixes

## 2026-11-24 — LTE 출처 복구·센서 서비스 재시작

- LTE 검증 거부는 복구 환경에서 두 EFS 시간 필드가 동일 폭으로 뒤로
  이동한 사례. 일상 엄격 검증은 유지. 현재/중간/이전 백업에 대해 EFS 네
  승인 필드 외 동일, 총 카운터·write 제한 및 CPEFS/RADIO 검증을 만족하는
  명시적 root-only 유지보수 경로 추가. 격리된 기존 lease와 증명 절차로
  private receipt만 재확인, 이전 영수증 및 working NV 보존. 파티션 쓰기 없음.
- 재부팅 후 기존 LTE 런타임의 hash/출처 통과, modem·SIM·rmnet0 확인.
  첫 SIM 망 등록 시간 초과; 해당 SIM 데이터 회선 정상 여부 미확인.
- support1.2.0에서 15초 지연/15분 최대3회 시작 제한으로 센서 서비스 복구.
  dpkg 설치 시 이전 패키지 pristine conffile만 교체 허용. 첫 시험은
  커널 proc children 항목 부재로 주입 전 중단. 동일 서비스 cgroup, 실제
  supervisor의 broker PID 확인 후 SIGTERM 시험:26초·재시작1회·IIO7개와
  실제 조도/가속도 복구. ROM 자체가 무응답인 경우는 별도 미검증.
- host LTE 출처/격리 유지보수45개 검증 통과. 비공개 백업·식별자 제외.

새 데이터 SIM(KT)은 LTE home 등록·packet attached·IPv4를 얻었습니다.
첫 cold boot 데이터 세션은 약30초 뒤 no-carrier, IPv4 HTTPS도 timeout.
일반 재부팅 후 rmnet0에 강제 바인드한 인증서 검증 HTTPS204와 실제
RX25→34/TX25→39 확인. 일반 경로 Wi-Fi는 유지. 모뎀 DNS 재검증 및
장기 안정성은 미확인입니다. 이와 별개로 실제 SSI ROM ACK0는 cold boot에서
재현됐고 제한된 서비스 재시작으로 해결되지 않았습니다.

마지막 TWRP→Ubuntu 전환 중 사용자가 한 차례 실패 및 재부팅을 관찰했습니다.
이후 실제 Ubuntu 진입에서 hub ready를 확인했습니다. EFS는 승인 필드6 bytes
변경만 확인해 새 읽기 전용 백업으로 외부 파티션·LTE 출처 검증을 복구했습니다.
후속 일반 재부팅에서 센서·LTE·충전 서비스 동시 active, 실제 조도106 lux,
rmnet0 강제 바인드 HTTPS204와 RX +7 패킷까지 확인했습니다.


## 2026-11-24 — TWRP 경유 센서 복구와 support 1.1.0 검증

- 일반 종료/전원 연결과 두 SPI 방식의 이전 ACK0 실패를 비교하기 위해
  보호 백업·현재 BOOT 검증 후 TWRP를 경유했습니다. 처음 시도는 DT 경로가
  맞지 않아 재부팅 전 중단, 실제 경로에서 reboot mode를 확인한 뒤 정상
  재부팅. 사용자 Reboot → System 뒤 hub ready 및 실제 IIO 센서7개 등록.
- TWRP 이후 EFS 변경으로 기존 보호 검증이 일부 서비스 시작을 거부했습니다.
  이전의 정확한 검증 백업과 비교해 기본 ext4 superblock의 승인된 네 필드
  이외 byte 동일·변경8 bytes를 확인. 아홉 파티션 읽기 전용 snapshot을 별도
  보존하고 센서 프로필·시스템 보호 백업 pin 세트를 갱신했습니다. BOOT/EFS 등
  원본 partition 쓰기 없음. LTE의 더 오래된 출처는 시간 경계 초과로 보존.
- 첫 정상 재부팅 후 같은 #50에서 hub ready 및 IIO7개 자동 등록 확인.
  이후 기존 승인 센서 supervisor를 support 1.1.0에 묶고 root-private
  기존 프로필 pin과 서비스 격리를 유지하는 drop-in으로 실행했습니다.
- 두 번째 별도 정상 재부팅에서 패키지 경로의 실행 프로세스, 새 boot,
  IIO7개, 실제 조도91–92 lux·기압 약102kPa·가속도/자이로·근접·온도 값과
  SensorProxy 조도/가속도 노출을 확인. 충전/전원 서비스 복귀. 나침반
  채널 등록과 방향 정확도는 구분. Apt 파일 무결성·dpkg audit, host48 시험 통과.
- TWRP가 초기 상태를 회복시키는 효과는 확인했으며 전기적 최초 원인 및
  불량 상태 자체를 소프트웨어로 항상 복구하는 방법은 미확정입니다.
  초기 진단과 보호 백업 증거는 구분하여 기록하고 비공개 원본은 공개 제외.

## 2026-11-24 — 센서 허브 ROM 연결 실기 진단

- #50/BOOT/보호 백업 확인 후 기존 standby 연장(1/3/9초)과 허브 LDO37
  차단 옵션을 각각 시험. 연장 시 일부 held MCU_RESP0까지 관찰했지만
  첫16바이트 ACK0/ROM 동기화 실패는 지속. LDO restore 및 옵션 OFF 확인.
- 정상 종료 후 케이블만 다시 연결해 새 Ubuntu 부팅. 첫16바이트 ACK0 재현.
  정상 프로필과 일치하는 임시 진단(ACK 메타데이터만)으로 hardware SPI와
  GPIO SPI 비교. 모두 MCU_RESP1/HOST_REQ0, 첫16바이트 ACK0, 수신 all-zero.
  strict ACK를 끄거나 가짜 센서값을 등록하지 않음. 패드/배선·허브 내부 상태와
  선택/전원 신호의 전기적 원인은 구분하지 못함.
- 임시 systemd override 제거, 기존 모듈/프로필·strict ACK 기본 구성 복원.
  IIO 3회 조회에서 허브 센서 채널 없음, 별도 배터리 ADC만 등록.
  지원 패키지/BOOT/보호 파티션 수정 없음. 성공 조건 미충족으로 이 기록은
  작업 트리에만 보존하고 패키지 통합 및 원격 Git 반영을 보류.

## 2026-11-24 — G965N 지원 패키지 및 APT 실기 시험

- 단일 arm64 support 1.0.0 빌더·보호된 이관 도구·상태 점검 추가.
  ALSA UCM/오디오 타이밍, udev/로그인·화면 대기 설정, 8개 기기 서비스의
  실행 코드와 설정을 패키지 관리로 이관. 기존 검증된 #50 드라이버 묶음과
  기기별 비공개 설정/펌웨어/백업은 별도이며, BOOT/보호 파티션 쓰기 없음.
- 기존 파일과 코드 일치 및 dpkg 소유권 확인, 이전 설정 tar 생성.
  20개 갱신의 이전 버전 패키지를 dpkg-repack으로 보존. 중복 고압축 복구본
  작업은 발열 때문에 종료하고 저압축 작업으로 완료. 복구본 실제 설치는 미시험.
- 실제 apt upgrade 20개 설치, systemd/udev 255.4-1ubuntu8.19 및
  GStreamer 1.24.2-1ubuntu0.2, 추가/제거0. 이후 dpkg audit/파일 검증 이상 없음.
  배터리/모델/BOOT/백업 확인 후 정상 재부팅. 동일 BOOT와 새 부팅 확인.
- Wi-Fi SSH, Wayland Panfrost, 표준 UCM 및 PipeWire 실제 시험음 왕복 확인.
  초기 X11 GLX/첫 시험 파일은 각각 Wayland 세션/재부팅으로 사용 불가하여
  Wayland EGL 검증 및 시험 파일 재전송으로 완료. 녹음 원본 저장 안 함.
  충전 보호·냉각/전원 키/진동/LED 서비스 active, ADC41.8°C에서 thermal hold.
- 갱신 전후 센서 허브 동기화 및 LTE 보호 출처 검증 실패 지속. 이전 상태를
  복구로 오판하거나 기능 완료로 표기하지 않음. 앱 설정/계정/식별자 비공개.
  기존 host 검증50건 통과(충전39/전원키4/모듈패키징7).

## 2026-11-24 — APT 업그레이드 읽기 검토

현재24.04 LTS 패키지 목록으로 apt-get -s upgrade만 수행:20개 upgrade,
신규/제거0. 실행 커널/BOOT 이미지 교체 항목 없음; linux-libc-dev는 사용자
개발용 헤더입니다. systemd/udev/GStreamer 등 서비스 기반 변경은 포함되므로
실제 설치 후 회귀 검증은 별도 필요. apt hold 없음. 선택한 시스템 패키지의
현재 dpkg 파일 검증에 mismatch 없음; 이는 포팅 overlay의 미래 호환성 보장 아님.
apt update/upgrade 설치·hold/pin/코드·설정 변경 없음. 개인 앱 목록/버전은 제외.

## 2026-11-24 — 전원 재연결 자동 부팅 실제 확인

외부 전원 online0·배터리89%·모델/현재 BOOT/보호 백업 검증 후 정상 종료.
사용자는 화면이 꺼진 채 약10초 유지 후 버튼 없이 케이블만 연결했다고 확인.
Wi-Fi SSH 복귀·새 boot ID·동일 Ubuntu#50·기존 BOOT/보호 백업 검증 통과.
현재 설치 BOOT 구조상 uniLoader 경유 부팅으로 판단합니다. 개별 instruction
trace는 없으며, 충전 아이콘만 보였던 과거 실패의 원인은 여전히 미확정입니다.
코드·설정 변경 없이 이 조건에서 자동 부팅 성공1회; 모든 충전기/배터리 상태,
완전 배터리 전원 차단·차량 ACC 반복 동작을 보장하는 결과는 아닙니다.
SSH/display-manager/observer/guardian/냉각/power-key active 확인. 재부팅으로
runtime MUIC1200mA/WDT trial은 사라지고 원래 입력500mA/기본 guardian 경로입니다.
새 부팅 후 보호 fault=false, 약37.6°C를 읽었으며 입력·충전 정책은 변경하지 않음.

## 2026-11-24 — 야간 재부팅 여부 읽기 검증

14:07 KST Wi-Fi 확인: 현재 uptime 약22.05시간, 시작11/23 16:04 KST.
부팅 journal 최신 세션도 해당 시각부터 이어지고21:22 시작한3시간 시험의
boot와 현재 boot가 일치합니다. 지난밤 연결 이후 새 재부팅 증거 없음.
설정/기기 쓰기·보호 초기화 없음. 원본 journal/boot 식별자는 공개하지 않음.

## 2026-11-24 — 3시간 시험 결과 수집 (설정/기기 쓰기 없음)

- Wi-Fi 읽기로 최신 private result/guardian/ADC/IC 상태 수집. 새 runtime 설정,
  충전 강제, 보호 예산 초기화, BOOT/펌웨어/파티션·재부팅 변경 없음.
- 11/23 21:22 KST 시작한 앱-open 관측이10801.7초/714표본 PASS,
  평균 보고 순전류+444.3mA·faults[]/conditions[] 확인. 같은 boot 유지.
  화면 OFF 유휴 앱 증거이며 실제 음성/화면ON 지속 사용을 성공으로 확대하지 않음.
- 시험 앱은11400초 RuntimeMaxSec의 예정 SIGTERM으로 종료. systemd timeout
  실패 표시를 앱 crash로 오인하지 않음. monitor11400.2초 workload exit 확인,
  위험 reason=null. 입력 lease/관측/monitor의 bounded 종료도 확인.
- 후속 배터리90%·35.7°C, CHG0/input500mA. guardian wall36010.6초로10h
  safety_time_expired 보호 유지, hardware/configuration fault=false/WDT expiry0.
  보호 한도 이후 상시 전원 유지·재충전은 미완료. 타이머 초기화로 우회하지 않음.
- 공용4문서에 집계 결과만 반영. 원본 로그/boot ID/개인 앱 설정·기존 개인48줄 제외.

## 2026-11-23 — #50 입력 전력·충전 IC watchdog·전원 키 후속

- 실제 모델/BOOT/보호 백업·이전 파일/module hash/ABI 검증 후 Wi-Fi runtime
  시험. BOOT/firmware/보호 파티션·bootloader·재부팅 변경 없음. 공개 자료 핀과
  기존 GPL 공지 유지; 개인 앱 구성·계정·바이너리·원본 로그는 공개하지 않음.
- 단일 MUIC 소유자 명령 mutex/CURRENT_SRCCAP parser/표준 source power_supply,
  900/1200mA 제한 입력 lease 추가. 실제 선택5V/3A source PDO 확인; 독립RDO
  decode는 미완료. 15초 갱신 중단 시500mA·이전 generation 거부 확인.
  외부 감류는 소유권 철회하나 다른 charger writer와의 원자성/실시간 보장 미검증.
- 실제 음성에서 입력과 CHG hold를 묶은 이전 정책이500mA에 머물러 약−562mA,
  36초3.544V, 이후43.5°C까지 악화. 관측기 종료가 앱 종료는 아니었음.
  앱을 안전히 닫고 냉각했고 입력 source 공급과 CHG hold를 분리함.
  실제40.4°C/CHG0/input900mA 확인. CHG450mA/CV4.35V/41→39°C 보호는 불변.
- 입력 controller 이전 generation 무효/종료 transient restart 실패는 새 현재
  상태를 확인한 bounded unit 생성으로 처리. 재시작 guardian의500mA 초기화가
  기존 source lease를 철회한 것도 실제 확인; 오래된 요청을 자동 재탈취하지 않음.
- 냉각38→36°C와 systemd20s watchdog/ExecStopPost fail-closed cap 적용.
  SIGSTOP 후 watchdog recovery와 caps 실제 확인. 최초 시험기의 transitional
  is-active exit3 중단은 별도 journal/readback으로 구분해 검증함.
- 고부하2worker/1worker 시험은40°C로 중단, 지속 부하 PASS 아님. 앱 닫힘 및
  native blank 후 냉각/순충전은 확인. 선택 workload의42°C·저전압/데이터 소실
  보호 추가; 낮춘35°C 실제 정지 검증. 새1200mA 음성은 사용자 시험 불가.
- 전원 키 직접DPMS/초기 상태 후보 실제 실패 기록 유지. 단순 ON/OFF 짧은
  사용자 성공 뒤 긴 대기 on/off/on 재발. modifier-only uinput과 native wake만
  쓰도록 강제 ON 제거. 자동90초 OFF×2 뒤5초 유지 통과, 최신 물리 재확인 대기.
- MAX77705 WDT 초기 후보의 absolute regmap 주소는 read 실패/활성화 없음.
  native logical header index로 수정해 실제~80초 미갱신 fault11 확인.
  v2 해제 시 CHG 요청이 남아 자동 충전 복귀하는 문제 발견; v3는 CHG0을 먼저
  요구하고 armed self-ref로 normal unload 차단, 소유 expiry 이후 feed 거부.
  v3 실제79.933초 fault·세 거부 동작·CHG0 disarm 후3초 유지 확인.
- guardian 선택 hardware-watchdog 경로는 먼저 CAS inhibit, current-boot receipt,
  실제 state/readback, fresh ADC/fault 판단 후5초 feed. 불명/만료 fault 자동 reset
  없음. /run 서비스 trial만 적용, 새 reboot/boot-time watchdog 설치는 미완료.
- 통합 guardian 실제95초/48회 feed 중 expiry0 확인. 앱-open 새3시간 관측을
  시작하고 선택 앱 최대 수명·monitor 종료 정리를 제한. monitor SIGTERM 시
  소유 fixture 실제 종료 확인. 첫 프로세스 검사기는 executable 대소문자로0을
  보고해 cgroup/정확한 실행파일 검사로 정정; 실제 자식/스레드 배치를 검증함.
- 공개 build-only MUIC/uinput/WDT 절차, 핀/attribution과 관련 host51 tests 통과.
  최신 canonical MUIC/WDT executable .text는 실기 module과 일치. 빌더 flash 없음.
  원래 spontaneous fault6와 최초 CHG0/config 변경 원인은 계속 미확정.

## 2026-11-23 — 열린 앱 음성·전력 비교, USB-C 읽기 전용 진단

- #50에서 사용자가 실제 음성 인식과 답변 재생을 정상 확인했다. 짧은 오디오 스트림 관찰에서 오류 카운터 0이었으며 장시간 음질 합격은 아니다.
- 앱을 열어 둔 화면 OFF에서는 GPU suspend와 양의 배터리 전류 약147mA를 관찰했다. 화면 ON 고밝기에서는 방전·발열이 재현됐다. 기본 밝기98→30 비교로 방전이 줄었지만 에너지 균형은 회복하지 못했다. 자동 밝기는 유지했다.
- 실제 음성 부하 약115초에서 평균 약−650mA, 배터리42.7°C·3.45V·6%를 관찰했다. 관찰기가 종료된 것은 앱 종료나 하드웨어 보호 동작을 뜻하지 않는다. 이후2%·42.8°C를 확인해 앱은 유지하고 표준 DisplayConfig로 화면만 OFF했다. 지속 음성/화면 ON 안정성은 실패/미완료다.
- 기존 온도 보호에 따라 충전이 차단됐다. 입력500mA/충전450mA/CV4.35V는 유지했고 보호 우회·전류 상향·BOOT 교체는 하지 않았다. 충전기 비교는 물리 교체 확인 대기다.
- GPL 공개 레지스터 자료를 핀한 read-only USB-C 모듈을 기존 I²C 클라이언트에 연결했다. BC SDP, sink, CCI3 및 PD ready를 반복 관찰했다. CCI 광고만으로 실제 PD 계약 전류나 Mac의 공급 한도를 확정할 수 없다. IRQ-clear·명령·리셋·IC 쓰기는 하지 않는다.
- 임시 어두운 테마 실행 인자는 화면 변화가 없어 원래 개인 실행 래퍼를 바이트 단위로 복구했다. 개인 프로필/설치/실행 설정·스크린샷·원본 로그는 Git에 포함하지 않는다. Wi-Fi SSH/root 연결은 USB와 별도로 확인했다.

Record symptom, evidence, action, verification and remaining limits for every change.
Do not include identifiers, raw private logs, backups, extracted firmware or passwords.

## 2026-11-18 — Source-only project and reproducible tools

Baseline SheroAbi/galaxy-s9plus-mainline-linux at bcee6014fc2e44a4c4f1c34bca0a880d4b543ec3.
Copied original source with its notices, omitted ten firmware/regulatory files and original Git history.
Original paths/hashes are in source-provenance.json; original README is retained separately.
Added Docker environment, fixed Ubuntu Base/TWRP hashes, kernel tag+commit guards,
read-only firmware extraction, verified backups and explicit-consent installation wrapper.
New Dockerfile built successfully. New backup and firmware tools ran successfully on G965N.
Seven automated guard/integrity tests passed. Full new kernel/rootfs recipe still needs qualification.
Original local ARM64 rootfs build completed: 3200MiB, e2fsck successful, exit 0.
No Ubuntu BOOT/USERDATA writes or G965N Linux first boot have occurred.

## 2026-11-18 — OEM allowed did not mean custom recovery permitted

Symptom: RECOVERY rejected with Only official released binaries are allowed.
Evidence: OEM allowed and flash.locked=0, but KG Prenormal with no Internet.
Action: booted stock Android and connected Internet Wi-Fi; KG transitioned to Checking.
Verification: TWRP subsequently booted, ADB root worked, RECOVERY prefix matched official image.
Limit: not proof about every RMM/KG restriction; no universal seven-day unlock promise.

## 2026-11-18 — Ambiguous flash logs and recovery identification

A zero exit code with hidden progress output was not enough evidence of installation.
Source review found messages routed through an active progress bar can disappear from logs.
One reported recovery screen was later corrected to stock recovery.
Fix: verify exact heading, ADB recovery state, TWRP version, root and actual RECOVERY bytes.
Document immediate recovery key combination; normal Android boot can replace custom recovery.

## 2026-11-18 — Remote dd stderr corrupted a binary export

First BOOT export was 92 bytes too long: remote exec-out included dd's byte-count report.
Fix: remote `dd if=... bs=1048576 2>/dev/null`, exact size and source-device SHA256 checks.
Verification: all nine actual partitions passed; public device.py repeated the backup successfully.
Regression test rejects appended/corrupted data. Invalid early exports must never be used.

## Next

Complete the new full build; extract/compare stock G965N BOOT device trees; review rootfs;
then perform an explicitly authorized experimental install. Record first boot, USB console/SSH,
Wi-Fi, graphics, charging, temperature and repeated reboot separately. LTE/audio are separate work.

## 2026-11-18 — Firmware publication filter

A dry-run file audit found that stock NVRAM names end with txt_r02a_b2, not txt.
Replaced extension-based ignores with deny-all firmware/* and an allowlist for Markdown.
The public source repository was created with a clean root commit and no proprietary files
in reachable history. An earlier draft was made private and archived; it is not the public source.
Added a Git-ignore regression test covering NVRAM suffixes, firmware, regulatory data and credentials.

## 2026-11-18 — Runtime Wi-Fi NVRAM line endings

Original stock NVRAM keeps its input bytes/hash; the runtime rootfs copy normalizes CRLF to LF,
matching the existing kernel embedding path and brcmfmac requirements. Regression test verifies
source preservation and transformed runtime bytes. This is not a Wi-Fi hardware success claim.

## 2026-11-18 — Structural G965N/G965F comparison before first boot

Read stock BOOT DTBH: chip 0x2652, rev26 selected by range 26–255. TWRP runtime
shows framebuffer 0xcc000000 and firmware debug reservations below loader payload
0x92000000. RAM banks and touch bus/address align with existing mainline assumptions.
Details and limitations are in HARDWARE.md; inspection script reads backups only.
Experimental Ubuntu installation and first-boot diagnostics are now explicitly
authorized by the device owner. Preserve recovery and verified EFS/CPEFS/radio backups.

## 2026-11-18 — Automatic USB host address assignment

Mac host requires administrator permission for manual IPv4 setup. Added isolated
USB-only DHCP using dnsmasq-base and a static phone address 172.16.42.2/24.
Hosts receive 172.16.42.10–20; router and DNS DHCP options are suppressed so the
host uplink remains independent. Only usb0 is served; no NAT or Wi-Fi DHCP server.
Image configuration checks dnsmasq syntax before enabling the service. Hardware
lease/SSH verification remains pending until G965N first boot.
Reference: https://thekelleys.org.uk/dnsmasq/docs/dnsmasq-man.html

## 2026-11-18 — Wi-Fi guard recovers variable interface names

The inherited guard hard-coded wlp1s0 and could retry while state 40 was already
connecting. It could also wait indefinitely on a wedged nmcli call. Replaced it
with dynamic Wi-Fi discovery, retries only after two disconnected/failed checks,
saved infrastructure profiles with autoconnect enabled, and bounded commands.
Disabled radio/manual-only profiles remain untouched. Three regression tests
cover interface naming, ongoing authentication/configuration and explicit choices.
All ten recovery/network checks pass; actual G965N link recovery still awaits boot.

## 2026-11-18 — ACPM diagnostic read must not change touch power

Static review found touch-rail writes incorrectly nested under the DVFS command;
a valid DVFS query fell through and could power down LDO35/LDO43. Restored a
separate tsp on/off dispatch, with invalid values rejected before any MFD write.
Added lazy MMIO initialization and aligned/ranged SRAM/mailbox checks, rejecting
the known faulting first three SRAM pages before ctypes dereference. info skips
queue inspection when a descriptor points into a blocked region. Four regressions
pass, including DVFS query issuing zero MFD writes. No diagnostic MMIO was run
on the handset; hardware verification remains pending. Fourteen tests pass.

## 2026-11-18 — Isolated LTE/audio development

Pinned LineageOS exynos9810 lineage-20 kernel at 6a9461f9460ca51d1217e5069a5d5556fcc79e63
and ztOS at 8bfb09011757f06c68a055fbfd95ea07d5e4fbe1 for comparison. G965N
recovery exposes Star-Madera/CS47L93, ABOX and umts/rmnet modem interfaces.
Added only explicitly GPL-2.0 ABOX code, with star2lte + explicit enable guard,
minimum amplifier default, capture off and modem voice-memory mapping off.
Read-only VENDOR extraction verified three own-device Calliope blobs privately.
Object compilation passed. Full module initially failed: hidden SND_PCM was
removed by olddefconfig; external modules also lacked symbol/link preparation.
Added an explicit PCM-selecting Kconfig option, modules_prepare, exact vmlinux
export table, and clean external outputs. Full .ko linking then passed without
unresolved symbols. Complete experimental packaging workflow is being rerun.
No audio module or modem experiment has been loaded on the device. LTE port
still requires compatible vendor IPC/mailbox code and native userspace control;
unlabelled GPL-3.0 compatibility headers are not copied into GPL-2.0-only modules.

## 2026-11-18 — Docker builds from managed Git worktrees

Experimental kernel, .ko and wrapped boot image built, then metadata recording
failed because .git is a host-absolute worktree pointer unavailable inside /src.
Pass the host-resolved commit explicitly into Docker rather than mounting the
parent repository or relying on host paths. Kernel source commit is still
resolved inside its own Linux build tree. No flash was attempted on failure.

## 2026-11-18 — Compile-stage Shannon modem API port

Prepared GPL-backed vendor/Lineage modem IPC and mailbox sources, with original
notices/hash inventory. Wrote Linux 7.1 compatibility adapters without copying
the unlabelled third-party GPL-3.0 header. Replaced writes to const netdev MAC
with eth_hw_addr_random, and removed obsolete revision GPIO APIs in favour of
validated DT revision. Corrected an internal/public mailbox header mix-up.
Full g965n-modem.ko linking passed without unresolved-symbol suppression.
The board overlay is deliberately empty, so hardware initialization is blocked
even if opted in. No device module load, SIM registration or LTE test occurred.
Owner can insert an active SIM later; that does not block core Ubuntu installation.

## 2026-11-18 — G965N modem hardware-node comparison

Mailbox/shared-memory nodes match the stock handset byte-for-byte apart from
local phandle declarations. The modem node differed only in revision GPIO
phandle numbers. These are invalid outside their original tree, so the candidate
overlay drops them and declares the observed revision explicitly for the adapted
get_system_rev. Verification compares remaining properties and all 23 modem
subnodes against private stock BOOT and checks revision 26. All checks pass.
The active module blob remains deliberately empty: no hardware probe yet.

## 2026-11-18 — First G965N Ubuntu hardware boot

Rootfs ae4ca7012f47a06119b92a7e12fd65f39ad5de7dd08e9cbe0ff94b89703b23ff
and baseline BOOT b95db6e62e9a534cb43212a936a8cf0f0276d43b66f43efebc150a65410ea8c9
were written with complete readback verification. RECOVERY and radio/identity
partitions were preserved. Ubuntu booted: 8 CPUs, 230GiB root, zero failed units.
Owner verified desktop/touch and connected Wi-Fi; Wi-Fi-bound HTTPS200 and NTP
passed. GPU reported Mali-G72/Panfrost direct hardware acceleration, GLES3.1.
Native Git clone/pull and pinned per-CPU C compilation passed on all 8 cores
with identical object hashes. Added required developer/ALSA packages to future images.

An intentional wired disconnect removed USB reachability. Console login found
the Wi-Fi path; privileged nmcli activation and usb-gadget restart restored the
Mac's DHCP lease and USB SSH. This was user-requested disconnect, not a proven
driver failure. Recovery procedure should preserve Wi-Fi and use console/SSH.

The owner clarified full Lineage-supported hardware parity as the acceptance
target. Bluetooth has no controller, sensors no IIO/class nodes; LTE/audio
prototypes have not been loaded. USIM was inserted for later LTE testing.
Full feature parity is not achieved; see the expanded validation matrix.

## 2026-11-18 — Filesystem failure must stop before BOOT

Review found the original writer ran e2fsck and blkid in one shell and ignored
its result, so blkid could mask a filesystem failure. Added an explicit status
marker and accept only clean/repaired (0/1); missing status and transport errors
stop installation. Three regressions cover masked inner failures and lost status.
First successful installation used the previous path and optimized directories
without reported errors. The stricter guard applies to future installations.

## 2026-11-18 — Reproducible first-boot and recovery profile

Published the observed basic success profile with local artifact hashes, explicit
remaining hardware gaps, and no credentials/blobs. Added a manual on-device
USB recovery helper matching the tested Wi-Fi/console recovery sequence.
Git/build/ALSA tools are now included in the recipe rather than a forgotten
post-install step. Added host-resolved source-commit metadata for worktree builds.
Local password policy remains configurable with an explicit short-password
opt-in; no actual device password is published or stored in the profile.

## 2026-11-18 — GPU evidence, board ports and reversible kernel tests

The baseline log contains nautilus INSTR_INVALID_ENC and GNOME/Xwayland
DATA_INVALID_FAULT jobs. A prior on-screen gears result was screen-locked and
is not a meaningful FPS benchmark. Added an independent surfaceless EGL test:
Mali-G72 rendered and read back 100 changing texture patterns (6,553,600 bytes)
with zero mismatches; the bounded kernel log plus cooldown had no new faults.
This does not resolve the earlier desktop faults.

Imported explicitly GPL-2.0 Bluetooth and BCM4773 transport files with pinned
source hashes/notices. Compared UART, expander, wake/handshake and amplifier
addresses/pins against this handset's private stock revision-26 tree. Added
model/opt-in guards, Bluetooth partial-registration cleanup and board quirks.
Removed sensor firmware arrays and replaced them with request_firmware.
Fixed transport init-error propagation/partial cleanup and patch read bounds.
Extracted the own-device hub patch from original BOOT, structurally validated
it and checked it equals the reference Android10 payload. Output remains private.
Read-only VENDOR inspection and own Calliope staging passed. A read-only EFS
check found no Wi-Fi module-vendor record at wifi/.cid.info; no EFS write.
Installed EGL development libraries and BlueZ for controlled tests.

Built the experimental kernel with ALSA, Broadcom HCI, SPI and OF overlays,
and linked all four external modules without unresolved-symbol suppression.
BOOT SHA256 ac5a362c9309ff9b84b4776f1e48ca4eb97c84836ac3087548b17fe485b5b11d,
27,084,816 bytes; kernel build #6. No driver loaded or new kernel booted yet.
Added an explicit BOOT-only installer mode that runs the existing G965N and
nine-partition backup/identity checks while preserving USERDATA and RECOVERY.
The consent regression initially failed on argparse wording; restored explicit
consent validation before any device access. All 20 guard regressions pass.

## 2026-11-18 — Experimental #6 hardware boot and desktop integration

Kept a full private copy of the working Ubuntu BOOT. The first kernel update
stopped before writing because EFS differed from the previous raw backup.
Compared copies offline: all 127 regular files identical, no additions/removals;
only superblock mount/write times/count metadata changed. Exact source of that
metadata change is not established. Took a fresh nine-partition verified backup;
did not weaken identity checks. BOOT-only write/readback passed and #6 booted
with USB SSH and zero initial failed system units. USERDATA was preserved.
systemctl reboot recovery was rejected; the supported --reboot-argument=recovery
form reached TWRP. No bootloader or RECOVERY update.

Audio manual load with cp_vss=0 booted Calliope CRL0 and registered speaker PCMs.
2s zero-data playback took 2.185s, no watchdog recovery. Reloaded with capture=1,
mic_gain=0 after stopping the user audio services; codec 0x6371 rev1 initialized.
3s capture produced 576,000 bytes, nonzero samples on both channels. A 5s
speaker/microphone test showed the expected separated 700/1300Hz peaks; owner
confirmed hearing two quiet tones. No recording is published. This is basic
path evidence, not speech/headset/call-audio quality or long-term qualification.

Owner reported no Sound input/output devices. Restored the stopped services;
generic ALSA probing exposed playback only. Added a GPL UCM profile for playback
device0 and capture device2, installed alsa-ucm-conf/pulseaudio-utils/rtkit, and
restarted WirePlumber. Phone speakers and Phone microphone appeared, GNOME
Settings connected to the real capture stream; both set as defaults, output25%.
Future images include these packages/profiles.

Bluetooth manual board load created ttySAC0; btattach loaded own-device Semco
candidate HCD and registered hci0. Discovery saw 12 distinct peers (IDs private).
Setup reported missing CMAC: CRYPTO_AES was modular but no module was deployed.
The first individual build used the obsolete aes_generic.ko target and failed;
Linux7.1 uses crypto/aes.ko. Built/loaded that exact module; cmac(aes) appeared
and controller off/on passed without another CMAC error. Future kernel recipe
forces AES built in. Pairing, A2DP and automatic restart remain unverified.

Hub transport manual load created bbd/ttyBCM/SSP endpoints. Initial standby
attempts left MCU_RESP high; not taken as a working sensor result. Added our
own restricted stock-vendor runtime: SYSTEM/VENDOR ro,noload, individual char
nodes only, no identity block devices. First lhd invocation aborted because
its default /data/etc/lhd.conf was absent. Private Android log capture exposed
the error; stock init confirms the /vendor/etc/sensor/lhd.conf argument. With
that argument, kernel reported hub ready. A deliberate 30s test-service timeout
then stopped the daemon and produced NOTREADY/CRASHED teardown notifications;
those are not evidence of a spontaneous firmware crash. No sensor samples yet.

Replaced the modem's empty embedded overlay with a bounded local DTBO request,
kept model/opt-in checks and added an exact reserved-memory layout check. The
GPL candidate still passes private stock comparison. Manual load bound mailbox,
shared-memory and modem drivers and created control/rmnet endpoints. Logs show
unimplemented vendor QoS/ECT and missing legacy reset GPIO; no CP boot/SIM/data
claim. RADIO/EFS/CPEFS are not written by this stage.

Owner reported oversized Firefox. Automatic3x left 480px logical width; applied
persistent2x via Mutter API, yielding720x1480, with auto-maximize/centering on.
The first call's optional layout-mode property was rejected; omitting it passed.
The reusable helper initially indexed the mode's scale list incorrectly; corrected
to field5 and ran it successfully. Saved a fresh-image display profile. Larger
application minima remain a limitation; no all-app fit guarantee.

Owner reported Korean squares: no Korean font was installed. Added Noto CJK and
emoji, explicit ko->KR fallback and font-cache refresh. fc-match selects Noto
Sans CJK KR; Pango's Korean sample has zero missing glyphs. Existing app caches
may need reopening. GPU acceleration remains active but additional GNOME job
faults were observed on #6, including JOB_BUS_FAULT; not marked stable.

## 2026-11-18 — SSP write contract, bounds and first motion readings

An original GPL-2.0 diagnostic client based on Lineage protocol definitions
rejected the first command's write result. The board character driver returned
the BBD transport count (user size plus2), violating write(2)'s byte contract.
Review also found a1024-byte accepted user packet could overflow the internal
1022-byte payload array. Added a bound inside bbd_send_packet and a1022-byte
character-device limit; empty writes do nothing, accepted writes return user
bytes, and queue exhaustion returns EAGAIN rather than false success.

Rebuilt the sensor module, stopped the bounded lhd test, unloaded/reloaded the
transport and restarted the own stock daemon/config. The fixed SSP client read
chip0x55, firmware21031900 and the sensor mask, then19 accel and18 gyro samples.
All axes varied during the short run; values remain raw with no claimed units
or orientation calibration. One other frame was not decoded. Sensor removal
commands were serialized and no AP sleep/wake commands were sent.
On-device zero-length write returned0;1023/1024-byte writes returned EMSGSIZE
before reaching the hub. No calibration or identity partition was written.
Raw motion readings are verified, but IIO/automatic-rotation integration and
longer power/restart tests remain open.

## 2026-11-18 — Protected modem boot, SIM recognition and GPU isolation

Extended the private vendor runtime with extracted backup-file NV working
directories and a read-only regular RADIO copy. No original EFS/CPEFS mount.
Verified a closed systemd device policy actually denies access to all three
physical block devices; cbd receives only its modem character-device allowlist.
The first bounded cbd run could not access private files after dropping to
Android radio UID1001. A private strace showed EACCES, not a CP driver failure.
Made the chroot root/search directories traversable inside the root-only host
parent; granted UID1001 ownership only of cloned nodes, firmware and NV files.
Adjusted the private Android log socket for that UID. Original paths untouched.

With corrected permissions, CP reached ONLINE. Opening IPC/RFS channels completed
the AP startup gate; the state probe received SIM status0 (ready),130 (initialized),
and phone-state1. AT queries also returned CPIN READY. CFUN=1 was accepted;
subsequent queries show LTE operator selection/search (CEREG0,2), packet attach0,
and CFUN query still0. This is not registration or Internet success. Owner says
the SIM was used for laptop data; subscription/device eligibility is not established.
The current state-only probes drain but do not answer RFS; a complete persistent
control/filesystem path remains necessary. No SMS/calls/PIN/identity queries.
Physical EFS/CPEFS/RADIO SHA256 values still exactly match the fresh backup.
Bounded cbd test timeouts are deliberate and must not be called spontaneous crashes.

Built a second kernel, with AES built in, from source commit eb75af0:
BOOT a87cf82f9e4bb9cede1365492b8ae8ce76e934730f5f27210b04edf57c2f2415,
27,088,912bytes. Not flashed/boot-qualified yet.

Firefox/desktop activity produced real GPU scheduler timeouts on #6. Tested
always_on=Y from23:12:14: four100-frame readback runs passed without mismatch or
fault in their bounded interval. A later GNOME DATA_INVALID_FAULT at23:19:47
disproved this as a complete repair. Restored always_on=N; no persistent policy
change. Battery sensor35.6C observed; CPU thermal limiting remained active.
Vendor and mainline both derive DMA address width from GPU MMU properties;
stock G965N DT has no coherency override. No speculative DMA/coherency edit made.

## 2026-11-19 — Private RFS replies, LTE registration and staged startup

Implemented an original GPL-2.0-only bounded RFS server using public protocol
definitions, not GPL-3.0 userspace implementation code. Reassembles fragmented
requests; only fixed private nv_data.bin working copies can be read/written.
Checks salted MD5 before use, rejects symlinks, validates ranges, fsyncs updates
and replaces the working checksum. Remote filesystem paths are refused. Actual
100286-byte and approximately20KiB NV writes received replies; a subsequent
restart accepted the resulting working checksum. Three regressions verify
copy-only writes, range/path rejection and checksum/symlink rejection.

RootDirectory with default API mounts hid the prepared runtime; disabling API
mounts with that launch failed203/EXEC. Explicit host chroot with MountAPIVFS=no
works while retaining the closed device allowlist. Early AT configuration could
time out before readiness; added bounded harmless AT readiness checks while RFS
continues running. State-changing AT commands are not blindly retried.

Owner replaced the laptop SIM with an active KT phone SIM. Packet-only service
domain still did not provide EPS registration. With combined CS/PS domain, the
bounded test received IPC access-technology0x21/domain3/registration2 and repeated
AT +CEREG:0,1 (home EPS registration). This establishes LTE registration, not PDP
activation, an address or Internet access. SIM and configuration both changed;
do not attribute the result solely to subscription eligibility. An earlier
registration status4 was described too strongly as rejection: the older public
IPC definition means emergency-only, so rejection causes remain unproven.
No SMS, calls, PIN or subscriber-identity queries were sent. RFS/cbd are bounded
tests, not persistent services. Physical protected partitions require another
post-test hash check before making a new unchanged-partition claim.

Built source-only module receipts and an opt-in startup installer. Staged audio
and Bluetooth services for BOOT a87cf82f9e4bb9cede1365492b8ae8ce76e934730f5f27210b04edf57c2f2415
with built-in AES. Each service checks the running kernel, actual BOOT prefix
and module SHA before loading. No modules loaded during staging. The handset
still runs kernel#6; #7 and startup persistence have NOT been boot-verified.

Installed glmark2-es2-wayland. Mali-G72/Panfrost GLES3.1 Mesa25.2.8 rendered three
512x512 offscreen benchmarks with readback and no new kernel fault in that
interval. This does not clear earlier GNOME job faults or scheduler timeouts.
No fixed-clock or no-AFBC setting has been installed at this checkpoint.

## 2026-11-19 — Reproduced GPU hangs under a complete scene sequence

On kernel#6, ran all33 glmark2 GLES/Wayland512x512 scenes (one-second
scene duration). The program printed a score but the bounded kernel delta
contained repeated job-slot0 scheduler timeouts. A score is not acceptance.
The earlier three short offscreen/readback scenes did not expose this failure.

Parked the lab modem with its documented CP power-off ioctl because bounded
RFS/IPC services had ended; this avoids leaving an unsupported CP session running.
Temporarily capped GPU devfreq at260MHz with its minimum already260MHz. The same
sequence still timed out. Restored max572MHz. Disabling flush reduction also
produced timeouts before a later overlapping test; that overlapping tail cannot
be used as a controlled comparison. Restored flush reduction=Y. A separate
non-overlapping PAN_MESA_DEBUG=noafbc run still timed out, so disabling AFBC
for an individual client is not a complete repair. A sync-mode run did not
complete within55seconds and still had a timeout in its kernel delta; no global
Mesa debug setting installed. Runtime-PM override remainsN and step-voltage
reduction remainsN. No new kernel was flashed.

Paused disruptive GPU workloads/reboot tests while the owner uses the handset.
GPU correctness, compositor smoothness and long-term stability remain open.

## 2026-11-19 — GPU backing failures and diagnostic kernel preparation

An interactive desktop renderer also raised DATA_INVALID_FAULT. Later a desktop
client repeatedly hit the WARN at panfrost_mmu_map's get_pages_sgt failure path;
GPU shrinker purges were frequent while MemAvailable still exceeded2GiB. This
suggests allocation pressure in the restricted DMA zone, but the exact allocation
error and its relationship to job faults are NOT yet proven. The port currently
forces every new Panfrost BO below4GiB to permit DECON imports, although Mali's
own MMU supports wider addresses. Do not confuse that policy with a Mali limit.

Enabled Panfrost dump_core temporarily for private fault capture; no dump or
framebuffer content belongs in Git. Added source diagnostics for timeout owner
and backing-allocation errno/size, preserving failure returns. Added a runtime
s9p_lowmem_bos switch for NEW allocations only, defaulting to the old policy.
No existing buffer is moved; unrestricted allocations may fail DECON import and
require rollback. These are diagnostic changes, not a claimed GPU repair.
The owner explicitly authorized continuing reboot tests after using the device.

Diagnostic kernel#8 built: BOOT0084314ebcdfbe15d57e804b20e72d254682f840b5e5dd905e62fa9c95204b17,
27,088,912bytes, UTS#8 Nov18 15:32:53UTC. The direct container call initially
could not resolve the host worktree's external .git pointer, leaving a blank
source receipt. Regenerated the receipt with the actual host a3f3c66 revision;
a mistyped intermediate receipt was corrected before deployment. Added a
fail-fast source-revision check for future direct container calls. The normal
host build wrapper already supplies the revision. Kernel/image bytes unchanged.
Staged exact#8 audio/Bluetooth guards; no module load during staging. Repeated
physical EFS/CPEFS/RADIO hashes exactly match the pre-kernel backup after RFS tests.
Requested recovery reboot; BOOT not yet written at this checkpoint.

## 2026-11-19 — Diagnostic kernel boot and allocation comparison

Fresh nine-partition recovery backup passed size/hash checks. The guarded BOOT-only
writer verified image0084314e... readback, then Ubuntu booted kernel#8. Exact-BOOT
audio/Bluetooth startup guards passed; both services active, hci0 and PCM nodes
present, PipeWire exposes Phone speakers and microphone. This proves startup
binding/policy, not another acoustic or Bluetooth peer test. #7 was never flashed.

Default#8 completed100 exact readback frames and all33 scenes, but35 matching GPU
error log lines made qualification fail. The new timeout diagnostic identifies
actual glmark jobs as well as compositor jobs. Turned s9p_lowmem_bos=N only after
that suite ended. Unrestricted new allocations still completed the suites but
produced73 error log lines, so this does NOT fix scheduler hangs. A separate
memory-pressure reproduction is still necessary for the backing-allocation issue.

Next isolated runtime suspend using the GPU device's power/control=on (not just
the G3D-domain always_on override, which still allows Panfrost internal core/L2
shutdown). A POSIX-sh readback command used unsupported brace expansion after
the write; explicit paths confirm the device policy is on. Test outcome pending.
Review also found the original readback test slept AFTER reading pixels, which
could flush dirty contents before idle. Moved idle before readback without an
intervening upload/redraw to test preservation more directly. Not yet run.

## 2026-11-19 — CRC hang isolation, reboot pass and memory-pressure failure

Keeping internal GPU power on, even combined with a fixed260MHz clock, did not
clear the33-scene hangs. Restored power/control=auto and max572MHz. Isolated the
ideas scene using sync mode: nofp16, nocache and linear still aborted with a GPU
timeout. nocrc passed; noafbc also passed that single scene. This implicates the
CRC/AFBC path but does not prove which hardware/driver mechanism is responsible.

With only PAN_MESA_DEBUG=nocrc (no sync), normal DVFS/runtime PM and the original
low-memory BO policy,100 exact frames and all33 scenes passed with zero GPU
error lines. Added nocrc to the image environment and current handset; preserved
the original environment privately. Warm reboot succeeded. Repeated the suite
while an interactive client ran: zero errors,100 exact frames,33 complete scenes,
and G3D counters increased by27 power-on/off pairs. The revised readback waits
before reading, so dirty output spans idle without another upload/draw.

A separate Firefox WebGL test compared120 frames /31,457,280bytes with zero
mismatches/context loss. Firefox exposed the privacy-normalized renderer string
'Mali-G51, or similar'; the native EGL probe reports the physical Mali-G72, and
Firefox holds renderD128. Do not describe the privacy string as another GPU.
This is bounded functional evidence, not a long desktop soak or video-codec test.

Added an optional live-texture pressure test. At768MiB nominal texture data, the
original low-RAM policy failed with CREATE_BO errno12 and the new diagnostic
confirmed BO backing err=-12, while system MemAvailable remained over2GiB.
Unrestricted allocation repeated that workload but produced a pixel mismatch
and DATA_INVALID_FAULT. Immediately restored s9p_lowmem_bos=Y. Thus merely
removing the restriction is unsafe and is NOT an installed fix. No default for
unrestricted buffers or a no-suspend/fixed-clock policy was installed.

The Lineage kernel configuration selects bv_r38p1. Its GPL device initialization
unconditionally chooses AArch64 page tables; the current generic Panfrost match
uses legacy Mali-LPAE. Hardware MMU_FEATURES=0x2830 advertises48-bit VA/40-bit PA.
This is a specific source-backed lead for the high-bank failure, not a confirmed
cause. A board-specific match using upstream's existing AARCH64 support is next.

## 2026-11-19 — Board-specific AArch64 MMU trial prepared

Confirmed the selected Lineage bv_r38p1 device/mali_kbase_device.c line312 chooses
kbase_mmu_mode_get_aarch64(). Added an Exynos9810-compatible Panfrost match ahead
of generic Bifrost, copying its existing supply/PM contract and selecting only
upstream GPU_QUIRK_FORCE_AARCH64_PGTABLE. Other GPU compatibles are unaffected.
Added a once-per-device log of the actual page-table mode. No vendor binary or
implementation was copied. This candidate has NOT yet been built/boot-tested;
keep the low-RAM policy and nocrc mitigation until hardware evidence says more.

## 2026-11-19 — AArch64 boot, high-bank pressure pass and microphone report

Kernel#9 BOOT93c36f5dbfa05ebf7a986374a31162cc77431f9bc813defe3d7e9001315c3150
(27,088,912bytes) passed a fresh nine-partition backup, guarded BOOT readback and
native boot. Kernel log confirms AARCH64_4K page tables. With lowmem=N and nocrc,
the same768MiB retained-texture workload that corrupted output on#8 now passes:
100 exact frames, all retained textures checked again, no matching kernel error.
CRC-enabled full33 scenes still fail, so the MMU fix does NOT replace nocrc.
Full33 scenes plus readback with nocrc and unrestricted allocations pass cleanly.

Prepared a safe kernel default: unrestricted BOs only for the Exynos9810 match
using AArch64 tables; legacy/other matches retain the prior low-address policy.
The diagnostic lowmem flag can force the old allocation policy. No userspace
startup write is used, so BOOT rollback cannot accidentally enable high addresses
on legacy#8. This default still needs its own boot/persistence qualification.

Owner reports a voice application cannot hear speech. Pulse input is unmuted
and the actual Chromium RecordStream is linked to the microphone. Numeric-only
capture reports low levels; no audio file saved. Changed runtime mic_gain0 to40
(+20dB, the driver's original speech default) and reopened capture. Levels rose
but owner still reports no recognition. L/R correlation near1 rules out strong
opposing-channel cancellation in that sample; this does not prove intelligible
speech. Gain change is a diagnostic trial, not an installed microphone fix.
GPU#9 tests proceeded while microphone routing was inspected. Stock IN3L/IN3R,
AIF1 registers and ABOX UAIF format/polarity match the reviewed source. Stock
media-mic additionally routes IN3L through LHPF/ASRC; direct prototype path remains
under investigation. Do not label voice recognition or full microphone support working.

## 2026-11-19 — Microphone supply bypass defect found in source/readback

Codec readback after capture showed MICBIAS1=0x8066. Its reset BYPASS bit1 remained
set: codec_start updated mask0x81e1, which changes the1.8V selector but never clears
bypass. The stock G965N DT requires a regulated1.8V MICBIAS1; the Lineage Madera
supply/bypass path clears this bit for regulated operation. Changed mask to0x81e3
and added a readback check, disabling the bias and returning EIO if it does not
latch. Child active-discharge settings remain as the stock DT specifies. This is
register-configuration evidence, not a physical voltage measurement or speech pass.

Prepared speech-default mic_gain40 in the opt-in startup package (speaker gain
unchanged). The previous gain40-only trial failed user recognition; do not call
this a gain-only solution. Kernel#10 with safe GPU allocation default was built
but never flashed; next build includes the microphone supply correction as well.

## 2026-11-19 — Kernel#11 boot, microphone recording and display-import regression

Kernel#11 BOOT b3210c87fc1a679136a2f98ad915590ed89bbd83f88099c651d45f1fb59f5ee1
(27,088,912bytes) passed fresh nine-partition backup, guarded BOOT write/readback
and native boot. RECOVERY/EFS/CPEFS/RADIO were not flashed. Actual MICBIAS1 readback
8065 clears bypass while capture runs; the configured1.8V is not a measured
physical voltage. Owner still reports no application speech recognition.

With explicit recording/playback authorization, added a bounded private-tmpfs
record/replay helper. The first10s sample had peak690/RMS56.4 and replay used9.5x
normalization; owner heard sound and white noise. Owner subsequently clarified
that they had not spoken for this test, so this is NOT speech/intelligibility
evidence. A clearly announced repeat was started. No recordings enter Git.

Tested a temporary WebRTC voice processing source. One-shot pw-cli load exited
and removed its nodes; keeping an interactive client alive produces a real source.
Initial AGC trial clipped14 samples; disabled AGC rather than promoting it as a
fix. The no-AGC stream returns samples with no clipping in a15s numeric probe;
quiet tail monoRMS3.2..3.9. Those are different ambient intervals, not a measured
SNR improvement. Default input remains the physical microphone. AEC, intelligible
speech and Lineage multi-mic parity remain unverified; no persistent filter yet.

GPU#11 AArch64/nocrc passed1024MiB retained-texture readback, but real desktop
clients exposed DECON swiotlb buffer exhaustion when high BOs were exported.
The prior acceptance regex missed these display errors. Added this signature
and a regression test. Restored runtime lowmemY and conservative source defaultY,
including repair of previously patched build trees. Installed#11 still defaultsN
after reboot; source change alone is not device persistence. Private-vs-shared
BO allocation needs a coordinated kernel/Mesa fix before unrestricted defaults
can be considered. No full GPU-normal claim is made.

Owner spoke in the announced repeat:10s, peak832/RMS95.6, normalization7.88x.
Owner recognizes their voice but reports robotic/crackling sound: speech is
captured, but quality FAILS acceptance. Stopped the temporary WebRTC filter;
it was not the default input for this recording. PipeWire logs show repeated
playback follower resyncs (hundreds suppressed) and a prior broken-pipe recovery.
A reversible handset-only WirePlumber trial now requests1024-frame periods,
1024-frame headroom and non-mmap I/O for the ABOX nodes. The same recording is
replayed to separate playback corruption from capture corruption. This is an
unqualified diagnostic setting, not the installation default or a quality fix.

The owner initially reported robotic/crackling artifacts gone on the same-file
replay, then clarified speech is much clearer but occasional crackling remains.
Record this as partial improvement, not a quality pass. The bounded replay logged
no new PipeWire errors and both nodes expose the requested properties. Added the
exact GPL-only WirePlumber0.4 trial rule and rollback instructions under the audio
experiment; no base-image default or unverified processing feature was enabled.
A cue-assisted repeat is in progress. The first cue wrapper invocation missed
its required recording flag and exited before the cue/capture; corrected arguments
and restarted the bounded test. No extra recording was produced by that failure.

The subsequent cue-assisted10s spoken test (peak455/RMS61.4, replay14.4x) was
confirmed by the owner as clear with no crackling. No new PipeWire errors were
logged in that bounded interval. This establishes short spoken recording/replay,
not long stability or all microphone functions. Included the exact ABOX-only
WirePlumber0.4 rule in the image overlay so the tested path is reproducible;
it does not enable the optional driver. Added optional quiet cue/start delay and
exclusive recording lock to the helper to avoid ambiguous instructions/overlap.
Application speech recognition is being tested separately. No app installation
or personal configuration is published.

## 2026-11-19 — Voice recognition confirmation and GPU#12 guarded deployment

After the timing rule, owner confirms the voice application recognizes speech
and responds. This is an actual bounded application test, not all audio/mic
functions or telephony parity. Removed only our four private runtime recording
pairs after comparison. Installed the exact source rule under its canonical name,
retaining the previous trial text privately; did not leave two active rules.

Owner reports black shapes at the top/bottom across desktop applications. A local
GNOME screenshot does not contain them; owner photo does. Owner reports they are
not visible in TWRP. This narrows investigation but does not by itself exclude
panel damage (different backgrounds/output configuration). No fresh GPU fault
lines in the inspected interval. Added a screenshot utility for diagnosis; all
screenshots/logs remain private. Initial direct screenshot API was denied; the
normal screenshot utility succeeded.

Kernel#12 built from63f8768, BOOT
2b1dffe3aab8e968f41baa428d88e66b6397e2893ab68b20ac7862d866f87dd4
(27,088,912bytes), restores conservative low BO allocation at boot. Passed a fresh
nine-partition backup and guarded BOOT-only write/readback. Exact-BOOT audio/BT
startup staged before reboot. Native boot and physical artifact check are still
pending; build/readback is not device success. No protected partition was flashed.

Kernel#12 native boot confirmed exact UTS and conservative lowmemY without a
runtime override. Exact-BOOT audio/BT services active; both UCM nodes and timing
rule persisted. Owner reports black top/bottom shapes gone. The reboot and
allocation default changed together, so the precise cause is not isolated.
Full33 GLES scenes plus100 exact readback frames pass on physical Mali with
nocrc and default PM/DVFS; new kernel fault signatures, including swiotlb, count0
in that cursor-bounded interval. Whole-boot logs still contain optional regulator,
other driver probe/P2P and initramfs warnings; a clean test interval is not a
clean whole boot. Desktop animation smoothness is explicitly not yet qualified.
Added an ignore for private chat attachments; no photo is committed.

## 2026-11-19 — Optional GPU regulator mismatch candidate

Whole-boot audit found `_opp_set_regulators: no regulator (mali) found`, even
though later DVFS/render tests ran. Source confirms Panfrost treats ENODEV here
as optional and continues. The Exynos board match had copied the generic Linux
regulator list, but this port's s9p-g3d clock provider actually programs BUCK6
through ACPM before publishing the clock, and refuses publication on failure.
Prepared board data with no Linux regulator supply and skip OPP regulator setup
only when num_supplies is zero. Frequency OPPs/devfreq and real ACPM failures
remain active; other boards with supplies keep their original validation.
This models existing rail ownership; it does not mask a failing voltage command
or prove animation performance. Candidate build/boot qualification pending.

## 2026-11-19 — Actual animation latency captured

Installed the distribution Sysprof capture development package for diagnosis.
Its library/header notices remain external; none are copied into the project.
GNOME denied automatic ShowApplications; stopped that attempt and restored the
prior overview state. Did not bypass that access restriction. Captured25s via
the normal Sysprof FD API while the owner exercised the UI.257 FrameClock marks
have p95=34.74ms/max240.52ms; paint-view p95=29.34ms, swap max157.92ms and queued
input processing max229.25ms. This confirms latency spikes but not their cause;
mark durations are not presented FPS. Raw capture stays private. Added source
capture/API analysis helpers and repeat instructions; no raw trace committed.

Kernel#13 candidate with corrected rail ownership built successfully from08e6464,
BOOT e86e3b48b3765b60c1eb5a7b85929a7e983684597253a8e8fc4784c89d5662ac.
It is not installed/boot-qualified yet; running device remains#12.

## 2026-11-19 — Kernel#13 native rail-ownership validation

Fresh nine-partition backup completed. An initial installer invocation named a
nonexistent timestamped image; preflight refused it before any write. Re-ran with
the actual manifest-matching artifact, verified BOOT-only readback and native
boot#13. BOOT e86e3b48b3765b60c1eb5a7b85929a7e983684597253a8e8fc4784c89d5662ac,
27,088,912bytes, UTS Nov18T17:14:11UTC. Protected partitions were not flashed.
The `_opp_set_regulators` missing-mali-supply error is absent from this full boot,
not just the benchmark interval. GPU initializes at572MHz/950mV in the dedicated
clock provider, AARCH64_4K and conservative lowmemY confirmed. No matched GPU/
display faults, panic/oops/WARNING/SError/lockup in the inspected whole-boot log.
Audio/BT exact-BOOT services active, hci0 and both GNOME audio nodes present;
this does not repeat the earlier owner's acoustic/ASR test after this reboot.
No failed system units in the check. The next bounded GPU/DVFS check is running.

Other boot messages remain: clkout probe-22, initial s6sy761 probe-110,
MAX77705 child DT-node messages, Wi-Fi roam/P2P failures and SO_PASSSEC unsupported.
The existing uniloader build script explicitly records why its20byte empty-gzip
external ramdisk is retained: changing it to an empty cpio historically hung
before console. Kept that known warning path unchanged rather than repeating
that unsafe workaround. It is not represented as an entirely clean boot.
Raw animation traces used runtime storage and expired on reboot; numerical
summaries above were read before reboot. Future repeat captures should use a
persistent private output path when follow-up analysis is required.

Kernel#13 full33 scenes and100 exact readback frames passed with0 matching
GPU/display errors.50ms frequency samples observed260/455/572MHz (239/14/580
samples), rail-setting readback950000uV throughout;15 more power-on/off cycles.
Both CPU policies also changed frequencies (little350..1499MHz, big1066..2327MHz)
during this bounded test. This establishes functioning observed DVFS, not a
physical rail-voltage measurement or animation smoothness. No fixed-frequency
or always-on performance workaround was installed.24 host guard tests passed.

## 2026-11-19 — FIFO pacing baseline and sequencing candidates

On native#13, three512x512 Wayland FIFO/vsync scenes (build/texture/ideas,4s each)
all measured31fps /32.4..32.9ms, despite the much higher unconstrained score.
Source audit found DECON waits for shadow latch then arms the event for the
FOLLOWING vblank. Prepared completion on the already-counted presenting edge,
only if both shadow latch and FRAME_START sequence advance are observed.
Otherwise retain the core's armed-event fallback. Vblank references are obtained
before programming the flip and transferred/released on exactly one path. Added
a runtime diagnostic old-policy switch and completion counters; no fixed clocks,
animation-disable setting, IRQ/TE timing or framebuffer reuse protection removed.
This candidate is not hardware-qualified yet.

Boot logs show touch I2C timeout BEFORE ACPM's successful touch rail reset, then
successful rebind. Prepared a board-only readiness/defer guard until the existing
reset and one-second startup delay complete. Actual post-ready I2C failures still
propagate. Rail reset limits/retry logic preserved. Added SECURITY_NETWORK support
for the SO_PASSSEC socket option requested by journald; the kernel socket source
explicitly returned EOPNOTSUPP when this configuration was absent. This does not
claim an enforcing LSM or fix by suppressing logs. All candidates await build,
guarded boot and hardware validation.

GNOME shell also logged missing Dbusmenu introspection support. Installed the
distribution gir1.2-dbusmenu-gtk3-0.4 dependency on the handset; a fresh gjs process
successfully imports Dbusmenu. Added that dependency to the existing desktop
AppIndicator package list. Existing GNOME process caches imports, so absence of
the startup error still needs the upcoming session restart. No personal app
installation, account or setting is part of this source change.

Added optional FIFO acceptance to gpu-validate.py and two guard regressions:
31fps cannot qualify even alongside a high score; missing/duplicated scene labels
cannot qualify.26 host regressions pass. Current kernel build still uses the
committed228d4bd driver inputs; later diagnostic/package-only edits do not alter
its BOOT receipt. No candidate has been published as hardware-qualified yet.

Checked installed package/kernel-hook inventory: no distribution linux-image
package or kernel-postinst hook manages this handset's BOOT. Documented ordinary
userspace updates versus explicit custom-kernel/module replacement and major
userspace format compatibility. Added no blanket package holds or automatic
flash/update hook. Current source-only recipes retain exact-BOOT module guards.

Kernel#14 built from228d4bd: BOOT
11e29751187be847f4e856e346c9e6cc570390a62950eb304586fff8f0cd8122,
27,088,912bytes, UTS Nov18T17:42:33UTC. Build succeeded; native boot remains
pending. Staged matching audio/BT startup and requested recovery for a fresh
backup and BOOT-only deployment. New diagnostic helpers are userspace-only.
The full SECURITY_NETWORK rebuild used the existing isolated build container;
its CPU quota was raised from2 to3 then4 while other containers were idle.
No unrelated container was changed. Owner prioritizes GPU over the newly
requested short-power-key screen-only mode; that feature is queued, not installed.

Kernel#14 fresh nine-partition backup and guarded BOOT-only write/readback passed;
native exact UTS and owner boot confirmation obtained. Audio/BT startup remains
active. Touch binds after one LDO cycle with no initial I2C timeout/probe-110;
its separate upstream non-MT axis warning remains under investigation. AF_UNIX
SO_PASSSEC set/get now returns1 (old#13 returned errno95); journald's missing-option
message is absent from the inspected boot. GNOME missing-Dbusmenu import messages
count0 after restart. No failed system units in this check. FIFO old/new-policy
comparison is in progress; animation repair is not claimed yet.

On the SAME#14 kernel, old-policyN FIFO build/texture/ideas measured31/31/31fps;
latch-policyY measured60/61/61fps. Both processes exited0 on physical Mali-G72.
Counters show1310 latch completions and415 deferred completions after comparison;
the latter includes the intentional old-policy interval. RestoredY in finally.
Owner reports improvement but remaining animation stutter: full smoothness is
NOT claimed. The following25s manual profiler capture contained only its256byte
header, and the numeric touch window saw no events; these are not valid frame/
physical-touch evidence. Summary correctly rejected the empty capture; a follow-up
JSON read of the empty output failed and must not be treated as a result. Need
capture/UI overlap validation and a repeat with actual frames. FullGPU+FIFO
acceptance is now running, not overlapping the manual profile.

Full#14 acceptance now passes:33 complete scenes,100 exact readback frames and
all three FIFO scenes at61fps,0 matching GPU/display errors,16 additional G3D
power cycles. Default runtime PM/DVFS/CRC mitigation and conservative low-memory
policy retained. No forced frequency or disabled animation workaround installed.
This qualifies the one-frame completion repair for these bounded tests; owner
still observes residual desktop stutter. MemAvailable~4.6GiB and boot-to-check
pgscan_direct/allocstall/compact_stall counters0 do not support current direct
reclaim as the explanation in that sampled interval. The separate high-memory
allocation/export limitation remains an open pressure issue.

A controlled four-window GTK transition trace (normal application launch, no
restricted Shell API) contains621208bytes/126 FrameClock marks. Dispatch p95=
31.102ms/max112.062ms, paint p95=7.117ms/max81.563ms, swap p95=4.426ms/max6.15ms.
This differs from the earlier manual overview workload and is NOT an equal-workload
before/after percentage. It proves profiling works when UI activity overlaps.
Raw trace persists privately; animations remain enabled and display power mode0.

Prepared a second DECON candidate: use counted FRAME_START as a wakeup hint,
then still verify the real shadow latch under the original total50ms deadline.
The old250us polling policy is available by runtime switch. IRQ wait timeout/read
counters allow an actual old/new overhead comparison. Missing IRQs retain the
hardware-poll fallback; no event is completed based on IRQ alone. Candidate not
yet built/boot-qualified. Also included the ACPM driver's own prototype header,
and corrected the touch diagnostic to check its actual MT axes rather than
unused legacy ABS_X/Y. Real unset-MT-axis warnings remain active.

## 2026-11-19 — Kernel#15 measured wakeup reduction and independent validation

Kernel#15 (sourceccd8994), BOOT
410c776ed2cdaaf37bb798bf2138a7af35e58c5a1c029f952adbfcaf74db7c12,
27,088,912bytes, passed fresh nine-partition backup, guarded BOOT-only readback
and native boot. Exact audio/BT startup retained; touch MT-axis diagnostic now
checks real axes and no false legacy-axis warning appears in this boot.

Same-kernel IRQ-wait N/Y/N comparisons, three4s FIFO scenes each: N reads43559,
Y reads1463, N reads43473. Scene rates59..61fps throughout; Y has732 waits,
0 IRQ timeouts and0 deferred events in the interval. Whole-system context-switch
deltas129774/46039/129835 are contextual evidence under those workloads, not a
battery-saving percentage. Final Y policy restored. Peer code review identified
a possible stale-count timestamp race around request programming; a generation-
associated completion candidate is being prepared separately, not assumed fixed.

A private root-run comparison created the shared validation lock root-owned.
The next desktop-user validation correctly refused it; checked its regular-file,
no-symlink/unlocked state and restored desktop ownership/mode0600. No GPU test
ran in that failed invocation. Future privileged comparisons must create the
lock as the desktop user, rather than weaken the shared lock checks.

Two full attempts passed readback/all33 immediate scenes with0 matching kernel
faults but FIFO timed out. The first found display power mode3; the next kept
power on but the screen shield remained active. Such hidden surfaces receive no
FIFO callbacks. Added temporary GNOME idle inhibition plus power/overview/lock
preflight and end-state checks; no persistent idle preference change. Actual
inhibitor readback false→true→false passed. Standard administrative session unlock
was requested and asynchronous completion confirmed false/LockedHint=no before
the next test; no unsafe Shell evaluation or access-control workaround used.

Independent read-only audio/BT validation confirms exact BOOT/module hashes, active services,
actual SPA1024/1024/non-mmap settings, correct unmuted mic and powered hci0 with
profiles registered. Read Transmit Power warning is the existing board quirk's
intentional diagnostic, not a new command failure; it was not removed. New peer
pairing/A2DP/SCO and post-reboot acoustic quality remain untested.

Network agent confirms USB SSH, DNS and Wi-Fi-bound HTTPS200. A prior optional
accessibility package fetch failed transient DNS; no DNS setting was changed
because it no longer reproduced. Retried at-spi2-core install and actual a11y bus
address retrieval succeeded. Added it and already-installed libspa-0.2-bluetooth
to the public dependency list; no personal app installation/configuration added.
Current LTE transport is not loaded after reboot; historical KT registration
must not be represented as current LTE data service.

Power audit found real charger source defects: ICL inverse encoding,6bit CC
ceiling, CHG enable field versus CNFG09 setup bit, STATUS enum mix-up, ignored
reads and AICL minimum underflow. Prepared candidates and7 production-C/faultable-
regmap tests; hardware control tests still pending. No current limit was raised.
A60s low-load trace had positive battery current150..208mA (mean185mA), unlike
prior heavy-GPU negative current; display state was not captured alongside it,
so this is not labelled screen-off standby or an Android battery comparison.

## 2026-11-19 — Light hub protocol verified, optical response still pending

Exact#15 BOOT/module and own firmware validated before one sensor-transport load.
Only SYSTEM/VENDOR ro,noload runtime and bounded isolated lhd were used; original
identity/radio partitions were not exposed, gpsd not started. Stock argv is
/vendor/bin/hw/lhd /vendor/etc/sensor/lhd.conf. Hub ready1,chip0x55,firmware21031900,
LIGHT_SENSOR9 advertised. One5s sample and later60s stream each contain1 actual
light sample, lux/RGBW0,CCT1452,integration17,gain64,0 parsing errors. Repeated
stream lines are cached last values, not60 fresh samples. Physical cover/illumination was not confirmed, so optical response is UNVERIFIED,
not failed or normal. Bounded daemon stops/ready0 are intentional teardown.

Probe now has board/chip/layout guards, atomic bounded record parsing, unsupported/
zero-sample nonzero exit and all-sensor/SIGTERM cleanup.13 targeted regressions
pass. Prepared default-off --ap-awake asynchronous D1/D3 experiment matching
pinned SSP protocol; NOT yet sent on hardware. No coefficient/calibration/EFS
write is included. IIO/automatic brightness are separate unimplemented layers.
Further physical optical/peer tests remain unverified; code/device checks continue separately.

With the visible/unlocked desktop preconditions met, kernel#15 full acceptance
passes33 scenes,100 exact frames and FIFO61/61/61fps,0 matching kernel faults,
0 IRQ-wait timeouts and15 runtime power cycles. Display/unlocked checks remain
true at completion. The temporary inhibitor is released; actual IsInhibited
readback false→true→false was verified independently. This resolves the test-
harness false-negative cause, not every desktop performance issue.

Peer review prepared generation-associated DECON completion rather than raw
vblank-count comparison. A short bounded100us IRQ-only check accommodates latch
clear lag; ACK ordering/pending recheck and an MMIO readback avoid stale status
recount. Driver-private locks never overlap core DRM event locks. Separate IRQ-
side read counters expose that bounded work; process polling counts do not hide
it. Candidate still requires compile/boot/FIFO validation before publication.

## 2026-11-19 — Charger and generation-completion candidates for kernel#16

Charger candidate keeps original notices/reference intact and accepts cache
migration only from the exact known previous port-source hash. CHGIN encodes
current/25mA-1 (500000 requested previously read525000); CC uses its distinct
6bit3150mA ceiling rather than input7bit3200mA ceiling. Charge enable uses
CNFG00bit0 as in pinned Lineage charger state control; legacy CNFG09bit7 setup
is preserved independently, not toggled as charging inhibition. Correct STATUS
enum and read-error propagation, low-voltage health initialization and AICL
minimum underflow handling are included.7 tests execute actual production C
functions with injected regmap failures and boundary values. No live current
increase or charge-control write has been used to qualify these candidates.

The same build will include generation-associated DECON IRQ completion and
separate IRQ-read accounting. Both changes await the exact next kernel compile,
fresh backup/guarded BOOT deployment and bounded hardware tests. Existing tested
#15 remains a rollback image. No original identity/radio/recovery writes planned.


## 2026-11-19 — Kernel#16 hardware acceptance: completion generations and charging

Built source ccd336120685edfd5dddde071d0cb4c69a5cc90b, verified a fresh
nine-partition backup, then guarded BOOT-only write/readback and native boot
passed. Kernel#16 BOOT SHA256 is
06db513aac38376cda20f551523ff2af9046e9be428832581e00f34b5bbee259.
RECOVERY/EFS/CPEFS/RADIO were preserved. Exact-BOOT audio/BT startup receipts
match; this is startup evidence, not a new acoustic or peer test.

With the desktop visible/unlocked, actual Mali rendering passed100 exact frames,
all33 scenes and FIFO build/texture/ideas61/61/61fps. No matching kernel faults.
DECON deltas:2795 generation marks,2795 IRQ shadow reads,5590 process shadow
reads,2795 latched events/IRQ waits;0 new deferred events,0 IRQ-wait timeouts
and0 atomic latch-check timeouts. Runtime PM remained auto50ms, DVFS stayed
simple_ondemand260..572MHz,16 power cycles observed. Generation-associated
completion therefore passes this bounded cadence test; desktop stutter, nocrc
requirement and low-memory BO limitations remain unresolved.

Charging now reads the requested500000uA input limit rather than525000uA.
A bounded inhibit test reported Not charging/N/A for three samples with battery
current937,0,3125uA; finally restoring auto reported Charging/Fast and171250uA.
The first test expected the text None and failed its assertion: the kernel
correctly renders CHARGE_TYPE_NONE as N/A. Auto was restored in its finally
block and the corrected test passed. Fast denotes charging phase, not negotiated
USB fast charging. No current limit was increased. Original charge-control
register defect is fixed and hardware inhibition/restoration verified; full
charging negotiation, idle drain and long thermal behavior remain unqualified.

Owner is unavailable for further physical tests. Light illumination response,
new acoustic tests and peer Bluetooth tests remain unverified; no user action
is assumed.


## 2026-11-19 — Post-test idle vblank timeout; next candidate not qualified

After the successful bounded#16 GPU test, a separate idle-period kernel warning
reported drm_atomic_helper_wait_for_vblanks timing out at04:01:55KST. The
screen-button agent had not yet changed DPMS, so that test is not its cause.
The earlier test's zero-fault result applies only to its recorded interval.
No failed system units were present when inspected. Other boot warnings remain,
including CPU feature variation, clkout/MFD matching and Wi-Fi P2P creation.

Source review finds the default atomic tail waits for another vblank after
pipe_update has already delivered its latch-associated event. A command-mode
idle transfer may not provide another FRAME_START. Prepared a standard helper
tail using tracked flip_done completion instead, preserving modeset/plane/hw_done/
cleanup order and old-buffer lifetime. Existing atomic_commit initializes
internal events even when userspace supplies none. This hypothesis/candidate
requires review, compile, boot, idle-transition and full rendering validation;
it is not yet a hardware fix and no warning is suppressed.

The first candidate compile failed before image packaging because dereferencing
drm_atomic_state needs its defining drm_atomic.h header. Added the explicit
include and retried; no device write took place for that failed build.

Retry compiled and packaged kernel#17 (source ce61485aff680948b58d057e7160dbf563596e9c,
UTS Nov18 19:14:34UTC, BOOT
c159ad82b03af430c6c1afe28f7f9de95c3a7e2a9cd31010e2c58e6163bed479).
Matching opt-in modules were packaged privately. Build success alone does not
qualify the new tail; no installation or idle-timeout fix is claimed here.


## 2026-11-19 — Screen-only power handler: software path tested on#16

Added a model-guarded non-root GPIO short-release handler, user service and
active-seat uaccess rule. Raw input access is narrowed to the named touchscreen
and this model's GPIO keys. No event grab, input-group membership, suspend,
poweroff or session unlock is used. Complete short releases are debounced;
repeats, long/orphan presses and SYN_DROPPED do not trigger a display toggle.
GNOME short-button action is nothing; existing lock and long-press policies
remain independent. python3-gi is an explicit image dependency.10 host checks
pass. Source installation enables the user service for the graphical session.

After exact#16 BOOT checks and private config backups, live service ran as
UID1000 with only the intended GPIO fd, active-seat ACL and direct user-open
verified. Direct normal-API off/on took279.19/210.70ms. During8s display-off,
a separate SSH connection confirmed PowerSaveMode3 and KMS CRTC active0;
a background heartbeat continued16 times, maximum501.51ms gap for a500ms
period. No new matching GPU faults or vblank timeout in that test interval.
Original display-off/locked state was restored in finally, with no unlock
request. This verifies the software screen-only/background path, not actual
physical short/long button behavior or Android-equivalent standby drain. The
interaction between a physical key wake and release-driven toggle is pending
owner testing. Service health alone is not physical-button acceptance.


## 2026-11-19 — Private modem migration and pre-CP guards (source checks)

Added same-handset backup provenance, content-preserving legacy clone archive,
explicit fresh staging and reboot resume. Extraction uses verified root-private
snapshots rather than mutable user paths. Opaque receipts and clone content/
metadata are checked after archive; original EFS/CPEFS/RADIO are never mounted
or written. Independent review found and corrected snapshot TOCTOU and receipt
preservation issues before device use. Symlink/hardlink/special-file and bounded
NV/checksum guards fail closed. Shared client-lifetime leases prevent exclusive
runtime migration while new RIL/CBD clients hold the runtime; old clients must
be stopped. Pre-CP launchers check provenance and actual private bindings,
including read-only ordinary RADIO, before modem-off or vendor execution.

Host checks passed22 runtime,3 preflight and4 reference PDP tests. Original
reference protocol encoders/parsers describe127/103/27/4-byte legacy layouts;
these do not qualify S9's proposed105/257-byte messages. Live activation stays
blocked instead of guessing offsets. Registration or candidate IP is not data
connectivity. Migration/resume remains hardware-unqualified at this checkpoint.
Full instructions and partial-failure limits are in PRIVATE-MODEM-RUNTIME.md.


Peer review identified an existing initial/re-enable event accuracy problem:
the default planes phase invokes update before enable, so the old path could
complete an event before programming the first frame. Kernel#17 was therefore
not flashed. The next candidate retains that active-but-disabled event without
taking a vblank reference, then enable starts IRQ accounting and reuses the
normal generation/latch update path. Inactive disable commits retain immediate
event completion. This protects the completion-tail contract across initial
enable, re-enable and modesets; hardware validation is still pending.


Independent review then found a service enqueue/lease handoff race in the new
modem tooling. Added child-side validation after obtaining the lifetime lease:
parent fixes the exact verified receipt SHA, child rechecks receipt/model/NV/
RADIO/private binding before IPC or vendor exec. No additional original block
access is granted to the closed test units. CBD uses a separate flock monitor
so vendor descriptor cleanup cannot silently release the lease.24 runtime,
4 launcher and4 reference PDP checks pass; reviewer found no further immediate
blocker. Actual CBD foreground/cgroup lifetime and hardware migration still
need device checks. Nothing here qualifies LTE internet connectivity.


## 2026-11-19 — Kernel#18 installed; completion validation in progress

The reviewed initial-enable/commit-tail source88af955f61a79a670bdba6929beb23449bfeaab9
built as#18 Nov18 19:22:18UTC. Fresh complete nine-partition backup verified,
guarded BOOT-only write/readback passed and native SSH returned. BOOT SHA256
41eee11031e8287090661658445b0c72e12a3a274cb022e4c0c2ab92dec6c0f8,27088912bytes.
Protected partitions were preserved. Audio/BT services are active and exact
BOOT/module manifest checks pass. One manual check first supplied the nonexistent
audio.json filename; it stopped before verifying/loading anything. Retried using
the actual shared manifest.json and both feature checks passed.

The software regression suite now passes88 tests. New benchmark size choices
allow bounded512x512,720x1480 and1440x2960 requested surfaces; previous61fps
results were512x512 and must not be presented as native full-screen performance.
Kernel#18 rendering/idle/DPMS qualification is still in progress at this entry.

The first post-boot readback compile mistakenly requested the uninstalled and
unneeded wayland-client pkg-config package. Compilation stopped before the GPU
test ran. This diagnostic uses surfaceless EGL/GLES only; compiling against
egl/glesv2 succeeded and the hardware suite was restarted. No package install
or driver workaround was needed for that harness invocation error.


Kernel#18 bounded acceptance passed100 exact frames, all33 scenes and
FIFO61/61/61fps at requested512x512, with0 matching kernel faults and awake/
unlocked completion. Runtime PM auto50ms, DVFS260..572MHz unchanged;15 power
cycles. IRQ check-timeout counter was1 before this suite and remained1, so this
is not a claim of zero since boot. During the suite generation/latched marks
increased2795, process shadow reads5590 and IRQ shadow reads2795; no new deferred
events or IRQ wait timeouts. Idle and DPMS qualification is a separate test.


Kernel#18 screen transition qualification:3 cycles off229.34/254.32/270.16ms,
on180.43/160.52/172.90ms; off idle8/2.5/2.5s and on idle2.5s each all read
back as requested. First8s off retained16 heartbeat ticks; overall49 ticks,
maximum504.01ms gap at500ms period. A fourth cycle off237.50/on163.08ms kept
the display off12s and a fresh separate SSH connection read Mutter mode3.
KMS debugfs state was unavailable in this extra observation, not asserted.
No new vblank-wait, flip_done, latch/shadow, Panfrost fault/timeout or SWIOTLB
error since the recorded cursor. Screen-button service active with0 restarts,
original mode0/unlocked state restored in finally. Physical key behavior and
long-term idle remain unverified; bounded DPMS/idle no longer reproduces the
previous warning.

Private modem migration attempts stopped before archive/stage: first legacy
STATE root0755 failed new private0700 requirements; verified nofollow directory
FD then tightened only STATE to0700, preserving DATA and contents. Retry prepared
read-only runtime but rejected an existing EFS symlink under strict NV guards.
No clone rename/deletion/freshstage/CP start occurred. Read-only diagnosis found
the same debug-only cpdebug/node symlink in the verified original EFS backup,
so blind retry would also fail fresh stage. A preservation-only archive plus
explicit complete-source quarantine/ordinary working-copy transform is being
prepared; arbitrary links remain prohibited in working NV. Private failure
logs, uploads and inputs are retained. No LTE data success is claimed.


## 2026-11-19 — Native-resolution stress exposes remaining GPU timeout

At reported1440x2960 windowed, readback/all33 scenes and FIFO61/61/61fps
completed, but3 actual glmark JS0 scheduler timeouts produced6 matching kernel
fault lines. Overall acceptance FAILED despite the frame rate. nocrc, lowmemY
and default flush reduction were retained. CPU thermal traces briefly reached
86C and reduced allowed CPU frequency; that correlation does not establish the
GPU timeout cause. Core-dump BO-no-sgt diagnostic was also present. A bounded
flush-reduction comparison is planned without increasing voltage/clocks/job
timeouts or suppressing diagnostics. GPU is not fully stable.

The acceptance fault filter now includes vblank-wait and flip_done timeouts
as well as GPU/scanout failures; tests cover the actual warning strings.
Requested and benchmark-reported sizes are recorded separately.

Independent reviews and37 host checks passed the legacy preservation update:
opaque nofollow archive inventories preserve corrupt legacy bytes and
symlink/special metadata without opening targets. Verified source extraction
is fully retained in private quarantine. Only the exact stock EFS cpdebug/node
diagnostic symlink is excluded when constructing an ordinary working clone;
its target hash and source provenance remain in private receipts. Unreviewed
links/specials still stop staging before clone creation. Fresh-stage live retry
is authorized separately; no success is assumed from host tests.


Native-resolution flush comparison: disabling only job-slot flush reduction
(nocrc/lowmemY retained) still completed100/full33/FIFO61x3 but FAILED with4 GPU
timeouts/8 matching lines, including one GNOME compositor JS1 job. OriginalY
was restored in finally. Same-scene UTC/monotonic output and thermal samples
are retained privately; line-completion timing does not uniquely identify the
causal scene. Initial big59/GPU49C, sampled peaks78/71C, kernel big81C between
samples. This rejects flush reduction alone as the repair; no permanent disable
or clock/voltage/scheduler-timeout increase was introduced. A bounded runtime-PM
comparison is separate and still pending.

Private migration retry now succeeded on#18: source EFS/CPEFS/RADIO hashes
match the fresh verified backup; legacy opaque archive and complete extraction
quarantine inventories match; exactly cpdebug/node is absent from working NV
and retained as a symlink in both preservation copies. Salted NV checksum,
private bind identities and read-only SYSTEM/VENDOR/RADIO checks passed.
STATE0700/DATA0755 retained. No CP/CBD/RIL/PDP started. Reboot resume and actual
modem service lifetime remain separate unverified steps.


Targeted native-resolution reproduction uses interleaved buffer-map, function
low and first loop scenes8s each, followed by5s observation. Runtime PM auto
and on each produced5 JS0 scheduler timeouts/10 matching lines. In on mode
parent power counters remained78/78 throughout, demonstrating that the runtime
reference actually prevented power cycling; always_on stayedN. Thus domain
off/on alone is insufficient to explain the issue. Original auto restored.

One further bounded comparison retained PM-on and fixed only the devfreq floor
to the existing stock maximum572MHz, without voltage/timeout increases. All59
samples read572000kHz/950000uV, parent counters80/80, GPU thermal peak71C with
no observed cap, yet6 JS0 timeouts/12 lines occurred. This rules out DVFS
transitions as a necessary condition in that run. Original min260/max572MHz,
simple_ondemand and PMauto restored in finally. No new DECON errors in either
comparison. Further arbitrary configuration stress was stopped in favor of
BO synchronization/IRQ/scheduler source diagnosis. These are negative controls,
not repairs, and do not qualify GPU stability or Android battery parity.


## 2026-11-19 — Timeout register diagnostics candidate and sensor failure

Prepared timeout-only Panfrost snapshot after the existing synchronize_irq/
fence recheck. It takes a reference only if already active/in-use, snapshots
queue/fence state and job/MMU/GPU interrupt registers under the existing short
job lock, then prints outside that lock. No interrupt acknowledgement, recovery
policy, frequency/voltage or scheduler deadline changes. Sequential MMIO reads
are explicitly not an atomic hardware snapshot. Exact-anchor application and
idempotence checks pass against pinned Linux7.1; compile/boot still pending.

One bounded#18 sensor window verified exact BOOT/module/own firmware, loaded
the hub transport once and refreshed only reviewed character nodes into the
existing runtime under its exclusive lease. Shared-lease isolated lhd started,
hub ready briefly read1, but the first chip query received no valid response
within2s. Baseline exited1 with0 samples; AP-awake was never transmitted. lhd
was stopped immediately, no process remained and ready returned0. This does
not qualify sensor operation or optical response; no calibration/identity
writes or automatic restarts were performed.


## 2026-11-19 — Source-qualified S9 PDP candidate, not yet activated

Read-only static analysis of the owner's stock RIL established S9-specific
wire facts independently: definition127, activation105, IP157/base or257/
extended, status9 bytes. Original encoders/parsers now implement those fields
with strict truncation/CID/flag/address/mask/MTU checks. No vendor binary,
disassembly implementation or handset identifiers are redistributed. Raw end
reason and throttle fields are retained without guessing 3GPP mappings/units.
Peer review matched offsets to the private evidence.51 relevant host checks
and both CLI help entrypoints pass.

Activation defaults off, requires two explicit S9 opt-ins and recent complete
registration, CID1/no-auth IPv4, ordered acknowledgements and a bounded single
activation. CP reset/registration loss fail closed; no CFUN recovery loop in
this opt-in path. Best-effort deactivation is attempted at most once. Candidate
IP requires ACK+active status+valid IPv4 and is emitted once to private journal
without raw payload, credentials or device identifiers. It is explicitly not
verified internet access; no route/DNS/address modification is included.
Fixed an existing CEREG prefix regex that could misread status10 as1.
No CP/CBD/RIL/PDP execution has yet qualified this source candidate.

Timeout-snapshot kernel#19 compiled and packaged successfully; installation
and actual diagnostic reproduction still require guarded device validation.


## 2026-11-19 — Kernel#19 observations and read-only EFS comparison

Fresh nine-partition backup verified, guarded BOOT-only write/readback and
native#19 boot passed; exact audio/BT manifest matches. Source4e0740872ddd790e233fd3dc74a195b78dc86f73,
BOOT c5a3bf384f1ff0cb887199bde8aa4414fd0b2f8c7747c6829220d381831d31f8,27088912bytes.
A default-state targeted3-scene run reproduces6 JS0 timeouts and one Soft-stop
failed warning. Snapshots show the expected unsignaled queue head and pending
next job; job/MMU raw interrupt status0 with enabled masks, no GPU error IRQ.
This gives no evidence of an outstanding unhandled DONE/MMU interrupt at that
instant, but cannot exclude every IRQ race. No new display-latch failures.
This is diagnostic evidence, not a stability fix.

A separately bounded nocrc,noafbc targeted comparison also produced6 glmark
JS0 timeouts and Soft-stop failed, with no compositor timeout in that interval.
Thus that debug configuration did not repair the failure. The actual render
target modifier was not captured in this comparison, so it does not establish
that AFBC was absent; externally imported buffers need separate verification.
No global noafbc setting was
installed; all clocks/voltage/runtime-PM settings and desktop state retained.
The helper accepts that exact combined debug option for reproducible diagnosis.

Fresh recovery backup revealed EFS full-hash drift versus#18. Read-only image
comparison found exactly8 changed bytes, all within primary ext4 superblock
mount time, write time, mount count and lifetime-write fields. All bytes outside
those fields are identical;127 file contents, links and on-disk inode data are
unchanged. Current recovery mount list contained DATA/CACHE only. These images
do not prove which component mounted it or when. Existing provenance correctly
refuses automatic resume; explicit verified-superblock maintenance is being
prepared, without relabelling a changed image as identical or replacing NV.

## 2026-11-19 — Sensor readiness candidate and private PDP status diagnostics

Transport ready is only lhd's ESW:READY callback; reference SSP initializes MCU
separately after waiting for init completion/delay and bounded retries. The
#18 CRASHED control message followed deliberate daemon stop, so is not evidence
of spontaneous firmware crash. Probe now pumps read-only data for5s and retries
only an exact missing chip-identity reply, at most3 attempts with1s gaps on the
same increasing sequence. Wrong identity, lost ready, malformed response or
short writes fail immediately. Sensor/AP-state commands are never retried;
chip55 plus firmware/mask must reply first.21 host checks pass; new live
readiness qualification is pending.

S9 PDP private status reports now retain selected raw state/reason/throttle
fields for rejection diagnosis, without payload, credentials or identifiers.
S9 plan tests14 pass. Units and 3GPP cause meanings are not guessed.


## 2026-11-19 — Explicit superblock provenance maintenance candidate

Added an opt-in revalidate-efs-superblock action requiring the exact old EFS
image/old private receipt and complete fresh backup/current-original checks.
CPEFS/RADIO must be unchanged. EFS comparison masks only four primary ext4
superblock maintenance fields; any other changed byte, wrong magic, backwards/
out-of-bound counters or times stops the action. Old receipt is preserved
byte-for-byte before atomic new publication with proof/history; original
partitions, working NV, RADIO, archives and quarantine are verified unchanged.
35 runtime checks and independent review pass. Host proof on the actual images
finds8 changed bytes: mount/write deltas1602s, mount count+1 and lifetime+4KiB.
Actual receipt maintenance/resume has not yet run at this entry.

With the bounded readiness delay on#19, baseline and AP-awake probe invocations
both completed with chip55/fw21031900 and0 unparsed records; motion values
varied and cleanup/daemon stop succeeded. Their aggregate sample counts include
startup settling, so cannot qualify sampling-window rates or AP-state improvement.
Both light observations remained lux/RGBW0,CCT1452,time17,gain64. Optical
response is still unverified. Phase-separated counting is being corrected.


## 2026-11-19 — Independent recovery-state correction candidate

Adapted only Arun Iyengar's upstream mailing-list proposal v3 patch12/14
(2026-11-13, Message-ID recorded beside the patch), preserving attribution/GPL
terms. It polls live JS_STATUS for all slots rather than the IRQ-clear snapshot
JOB_INT_JS_STATE before draining reset queues, and safely returns NULL on an
unexpected empty dequeue. The initiating scheduler500ms and soft-stop10ms
budgets/reset policy remain unchanged; no long-job grace-period policy from
patch13 is included. Our#19 observation of snapshot0 with live ACTIVE8 supports
this recovery-state discrepancy, not a claim to explain the first GPU hang.
Exact pinned-source/idempotence checks pass; compile and hardware recovery
qualification are still pending. Original proposal:
https://lists.openwall.net/linux-kernel/2026/11/13/872


Explicit#19 EFS maintenance and existing-copy resume now pass on hardware.
One private history entry records the8-byte proof; exact old receipt preserved
mode0600. Working NV hashes remain identical to#18 staging, archive/quarantine
inventories unchanged, original hashes match fresh#19, private binds and
read-only SYSTEM/VENDOR/RADIO validated. No daemon was started for these checks.
This verifies the explicit maintenance path, not silent acceptance of arbitrary
EFS changes.

Sensor reports now separate pre-enable counts, each sensor's enable phase and
the actual timed receive window. Each sensor array is cleared immediately
before its own A1 and all arrays again at window start. On-change initial
readings may qualify post-enable observation separately, while startup-only
data cannot qualify sampling.25 host checks pass. Previous#19 aggregate counts
remain raw startup-inclusive observations, not corrected window measurements.
No additional state command or physical-response claim was introduced.


## 2026-11-19 — Cold modem boot panicked before PDP; recovery evidence preserved

One explicitly gated#19 trial passed model/BOOT/module/source/provenance/NV/bind
preflight, then lost USB SSH. Independent targeted ADB found automatic TWRP
recovery. Preserved pstore, last-kmsg, journal and complete private modem state
to owner-private host storage before further boot. No new BOOT image was written.
Offline copied NV salted checksum remains valid. No recovery/identity/radio
flash or data replacement occurred.

Evidence contains no IPC, AT, RFS or PDP commands from the lab: the failure is
before activation. Kernel trace identifies cbd's IOCTL_SECURITY_REQUEST secure
monitor call followed by asynchronous SError/panic. Earlier MODEM_OFF central
sequence wait and CP-init interrupt-pending wait timed out, but legacy callers
ignored errors, marked initialization done and continued security requests.
The first secure response was CP_NOT_WORKING; a later request panicked. Exact
module offset maps to the security callback. This does not demonstrate an
incorrect105-byte PDP layout because no PDP request ran.

No retry, security bypass or forced PMU wait relaxation was attempted. A
fail-closed error-propagation/readiness candidate is under source review; cold
bring-up remains unresolved. Vendor mode2 positive statuses and clock-order
semantics must be audited rather than assuming every status is fatal. Returned
the unchanged#19 Ubuntu BOOT to its baseline after preserving evidence; native
SSH returned, modem is not autoloaded and transient experiment units do not
persist through reboot. CP physical readiness is not asserted from that boot.
Kernel#20 compiled but was never installed; pending work remains explicitly
unqualified.


## 2026-11-19 — CP failure containment candidate (not cold-boot repair)

Source now propagates failed PMU init/reset/off instead of continuing security
SMCs or falsely caching initialization. Checked process power transitions and
security share a mutex; IRQ handlers only advance a nonblocking failure epoch.
Only a verified explicit reset can reopen a failed session. Graceful shutdown
marks its expected offline completion before waiting; fatal/watchdog events
still invalidate the transition, including a final epoch-publication race.

SSS clock ordering required by the original secure CTRL path is preserved with
symmetric cleanup; internal positive clock errors become negative errno. The
owner CBD's independently verified mode2 nonnegative vendor-status ABI remains
unchanged. Optional pre-init RAM logging defers with EAGAIN without cold-starting
or poisoning a clean session; its former direct security path uses the same
gate. Negative secure CTRL-write errors are no longer treated as success.
Firmware authentication, SMC arguments, PMU wait sequences/budgets and protected
partitions are not bypassed or modified.

21 fault/concurrency scenarios compile and execute actual production C,
including real pthread exclusion of security during OFF, normal/fatal shutdown
completion, PMU failures issuing0 security calls, clock cleanup/status ABI and
IRQ publication boundaries. Independent review passed;19 earlier scenarios
also ran in the Linux builder. This is host/source containment evidence, not
hardware qualification. Fresh-module seq5 alone cannot reconstruct a previous
failed physical session, so automatic reload/retry remains prohibited and no
new CP trial is authorized on the post-panic unknown physical state. Native
Ubuntu baseline is restored with modem autoload disabled.


## 2026-11-19 — Build the modem overlay from tracked source

Closed a reproducibility gap: experimental modem kernel builds now compile
the tracked GPL device-tree overlay into the module package, with path/size/
SHA and source/Lineage attribution in the receipt. Optional explicit owner
stock BOOT input is validated and bound read-only; a cached image is never
silently adopted. Without that input the receipt says comparison not performed,
not hardware qualified. Existing audio/BT module shape remains compatible.

DTC output and full three-subtree comparison against the owner's manifest-
verified original stock BOOT/revision26 passed.6 package regressions and shell/
Python checks pass. Source-to-artifact-to-manual-guarded-stage instructions are
in MODEM_OVERLAY_BUILD.md. Build never stages, flashes or autoloads anything;
firmware/image publishing in CI remains disabled. No private stock BOOT or
firmware content is included in Git.


Timeout snapshot v2 additionally captures all three live job slots and full-width
shader/tiler/L2 present, ready and transition masks, to distinguish a stalled
producer or unavailable core. It remains timeout-only, under the existing
already-active PM reference and short queue lock; all printing is outside
that lock and no MMIO acknowledgement/configuration writes are added.
Exact known-v1 migration, idempotence and modified-v2-cache refusal checks pass.
Compilation/actual register capture are still pending; no root cause is inferred
from fields that have not yet been observed.


## 2026-11-19 — Kernel#21 build, guarded BOOT update and baseline boot

Source d681693a0cee894818062379a9036a8204da1f83 built kernel#21
Nov18 20:51:24UTC with the recovery correction, timeout snapshot v2 and
host-tested CP containment. Experimental module package now includes the
source-built modem overlay; explicit read-only original stock BOOT comparison
passed for all required subtrees.133 software regressions passed before the
separate public targeted-runner enhancement. Build success is not modem proof.

Fresh complete nine-partition backup verified; BOOT-only write/readback and
native SSH passed. BOOT SHA256
e792170f622d652d5d3e641479706bb7ece9cafbdaa0d51d3621bafbf1ff44a8,27088912bytes.
Exact audio/BT manifests verify, both startup services active and no failed
system units at inspection. Modem module is absent and no CP experiment was
restarted. No recovery/identity/radio flash occurred. Current EFS metadata
changed across recovery again, so existing private provenance is not silently
reused. Actual GPU v2 diagnosis and acoustic/physical sensor/CP acceptance are
separate pending tests.


## 2026-11-19 — Preserve the stock CBD cold/warm bootstrap sequence

Independent read-only analysis of the owner's CBD shows its normal path calls
STATUS, skips RESET for raw0, otherwise requests RESET, then mode2 security,
firmware transfer, mode0 verification and MODEM_ON. Removed the experimental
parent launcher's unconditional pre-boot MODEM_OFF, an extra destructive step
not in that path and a candidate contributor to the observed cold PMU state.
No new query/reset policy, security bypass or SMC arguments were added.
6 launcher regressions include real main/preflight-before-launch behavior and
absence of the parent's boot-node open/OFF ioctl.

STATUS is not assumed to be a pure physical-state read: the driver can consume
SIM events and advance NV-rebuild state. No extra status pre-query was added
that could alter CBD's decision. Logical offline/fresh module alone is still
not proof of physical cold state; this source correction has not been retested
on hardware and no CP retry is authorized on the post-panic state.

Attribution audit of pinned Lineage revision26 DTS found no original copyright
or license header to restore; its repository COPYING specifies GPLv2, matching
the existing GPL-2.0-only overlay declaration. Original source/commit attribution
is retained; no invented notice or proprietary data was added.


## 2026-11-19 — Publish the actual bounded GPU reproduction harness

Public gpu-validate.py now includes the exact three8s targeted scenes plus
optional private line-time capture; default full-profile commands/deadlines
remain unchanged. Targeted completion checks actual scene order/options and
positive finite FPS, distinguishes its three scenes from full33 qualification
and records requested/reported surface size. Existing captured#19 real output
passes that parser; raw evidence stays private.12 regressions cover missing/
duplicate/partial/malformed or zero-FPS rows and silent/partial-output/descendant
process timeout cleanup. Timing is received-line completion, not proof of GPU
job start/end or causation. No workload flag is installed globally.
New profile's first#21 hardware run remains pending at this entry.


Kernel#21 public targeted/timeline profile completed all3 scenes at reported
1440x2960 but FAILED with5 actual scheduler timeouts (4 glmark JS0,1 GNOME
JS1) and5 soft-stop failures. Diagnostic line count55 is not55 timeout events.
All five snapshots show shader present==ready0x05771777 (18 sparse cores),
tiler/L2 present==ready1 and all power-transition masks0; affinity matches
present. At fragment timeouts JS1 was idle with no pending producer. Thus these
observations do not support missing-ready-core or active-producer explanations.
The live-slot recovery correction exposes real10ms non-idle observations; it
did not repair the initiating timeout. No voltage/clock/PM/debug-global changes.
Original locked/display-off state was restored in finally.

An existing GPU devcoredump was preserved read-only in owner-private host
storage before expiry for descriptor/BO metadata analysis. No pixel content or
raw dump is included in Git. Missing heap SGT in one dump object does not mean
every other object/register was absent. Initial field-size/source arithmetic
audit finds no proven tiler/header overflow at native resolution; the16MiB
render-buffer size correlation is a hypothesis only. Further diagnosis remains
open, and no new CP security trial has been performed.


## 2026-11-19 — Inspect existing GPU metadata without another stress run

Read-only structural analysis of the preserved#21 dump finds eight valid BOs
and one invalid sparse-heap object. The invalid object's bytes are not decoded:
the missing SGT makes those bytes unqualified, not evidence of GPU contents.
No pixels, textures, private dump or identifiers are published.

The valid fragment descriptor reports an actual1440x2896 render target,
distinct from the window's reported1440x2960 size. Its target is AFBC32x8
wide/split RGBA8; CRC reads/writes are disabled as expected with nocrc. Header,
body alignment and worst-case buffer extent fit the backing allocation in this
snapshot. This rules out that specific simple size/stride mismatch, not all
AFBC or synchronization defects. Previous noafbc comparisons checked the
environment only; they did not capture an actual modifier, so AFBC is not
excluded as a contributor. No global compression change is made.

The valid command pool also retains a completed indexed-vertex descriptor
whose tiler pointer matches this fragment's tiler context. Both associated
shader pointers resolve inside valid BOs. Private analysis using the official
Mesa25.2.8 Bifrost disassembler finds straight-line vertex/fragment programs
with end markers and no branches; the fragment declares no texture/sampler
inputs. There is no evidence of a shader-code infinite loop in that snapshot.
This does not establish total overdraw cost or exclude fixed-function, cache,
memory or synchronization stalls. Shader bytes/disassembly remain private.

A subsequent read-only health check still finds native kernel#21, no failed
system units, the modem module absent and five cumulative GPU scheduler
timeouts, unchanged from the completed targeted run. Physical light-response
and acoustic tests are deferred while the owner is unavailable. No further
CP security operation, reboot, flash or GPU stress run was performed here.


## 2026-11-19 — Define invalid GPU dump bytes without changing validity

Source review found that a failed BO mapping still reserves its full size in
the vmalloc-backed dump but does not fill that range. Add __GFP_ZERO to the
existing dump allocation; retain all validity flags, headers, offsets and
existing failure behavior. This avoids exposing untouched allocation bytes.
It neither decodes the old invalid heap nor populates absent sparse pages.
No new page/DMA locking, timeout policy or normal rendering path is changed.
The extra zeroing cost occurs only during the existing one-shot dump capture.
This is a diagnostic-data correction, not a fix for the initiating GPU stall.
The full patch script applied twice to the actual pinned kernel cache; the
dump source hash stayed identical on the second application. ARM64 compilation
of panfrost_dump.o passed. No new image was installed: native kernel#21 still
runs the previous dump implementation, so hardware qualification is pending.
Sparse-heap capture remains unsupported; marking zero-filled holes valid would
misrepresent missing memory and is deliberately not done.


## 2026-11-19 — Verify actual presented modifiers in the noafbc comparison

One bounded#21 targeted comparison used nocrc,noafbc with process-local
WAYLAND_DEBUG=client. Exact BOOT and default clock/voltage/PM/lowmem/flush
settings passed preflight; start big/GPU temperatures55/44C, peaks74/63C.
Five created Wayland buffers and all11731 attached/committed uses carry
modifier0x0800000000000062: ARM AFBC32x8, SPLIT and SPARSE. No LINEAR,
INVALID or unidentified committed buffer was observed. Most committed buffers
have height2896 after the initial2960 configuration. Thus noafbc did not
remove compression from this client's presented buffers in this run.

Five glmark scheduler timeouts and five soft-stop failures remain. Protocol
stderr interleaved inside scene stdout lines, so the public runner correctly
did not qualify scene completeness. Private reconstruction removing only
timestamped protocol lines finds the three expected scenes complete; this is
diagnostic evidence, not an unmodified-runner or performance pass. Raw logs
remain private. Original display-off/locked state and all GPU settings were
restored. No dump re-arm, CP call, firmware change or flash occurred.

Mesa25.2.8 source distinguishes default modifier selection, explicit modifier
creation and import validation. Explicit creation can choose an AFBC candidate
despite has_afbc=false; the client environment alone is not proof of layout.
A separate display-GPU copy can also make a presented LINEAR buffer differ
from the render target. The observation above establishes presented AFBC;
runtime render/display FD identity was not captured. Do not generalize it to
all import paths or every internal render resource. A creation-filter change
and isolated-driver build are under source review, not yet deployed.


## 2026-11-19 — Separate protocol tracing from benchmark scene parsing

The explicit gpu-validate.py --wayland-protocol option now captures glmark
stderr in a separate private binary log while retaining stdout scene parsing.
Both streams share the fixed deadline and process-group cleanup; --timeline
is optional and records stdout receipt only. Tracing is set on the glmark
child environment only. Without the option, existing output/environment
behavior is unchanged. Receipts state the presented-buffer and timing limits.
16 host regressions pass, including large newline-free stderr, split stdout
scene lines, silent streams, timeout reaping/pipe closure and child-only flags.
No further hardware workload has used this new capture option yet.

For the separate isolated Mesa build, installed native build prerequisites
after checking a zero-upgrade/zero-removal package plan:62 new packages, no
existing graphics replacement. Before/after package inventories, the exact
plan and installation log are retained privately. The pinned upstream25.2.8
archive hash matches its official release notes. This is build preparation;
no custom Mesa library has been installed into system paths or GPU-tested.


## 2026-11-19 — Check capabilities before explicit Mesa modifier creation

Added a Mesa25.2.8 candidate patch under experiments/mesa, with its upstream
MIT copyright/permission notice and pinned pristine/patched source hashes.
Both native/emulated explicit creation loops now consult the existing
is_dmabuf_modifier_supported callback. That callback reflects has_afbc and
format restrictions. An AFBC+LINEAR list can choose LINEAR when AFBC is
disabled; an unsupported AFBC-only list fails with NULL rather than choosing
an unrequested layout. Preserve the old only-INVALID implicit fallback.
Imports, default creation and the capability callback are unchanged.

13 host C scenarios compile the actual original/patched selector and reproduce
the baseline bypass, supported fallback, unsupported rejection, preference,
allocation failure and INVALID behavior. The check also proves every byte
outside that function unchanged, including import code and original notices.
These tests passed independently; full Mesa compilation/native acceptance are
still pending. This fixes a diagnostic-option selection path, not yet the GPU
timeout or compositor smoothness.

Native private Meson bootstrap initially requested a binary-only1.4.2 install;
that wheel was unavailable. Corrected to the available1.4.1 wheel, which meets
Mesa's >=1.4.0 requirement. The private venv now reports1.4.1; no global pip
installation occurred. A failed wheel lookup does not establish that the
upstream1.4.2 source release is absent. The source archive copied to the phone
has the exact official SHA256. System services still show no failed units.


## 2026-11-19 — Start the isolated native Mesa build and correct prerequisites

Pinned build-only script supports separate baseline/patched source/build trees,
exact archive/patch/resource/tool hashes, private Meson1.4.1 and coherent private
EGL/Gallium/GBM output receipts. It never installs or launches graphics. Two
host regressions reject source/variant drift; review also corrected self-test
failure exit status before publication. Native patched prepare from the
committed source snapshot09942cf passed archive checks and zero-fuzz patching.

The first actual configure stopped at missing wayland-egl-backend development
metadata. libwayland-dev alone is insufficient on Ubuntu24.04. Preserved that
partial configure and its logs; added libwayland-egl-backend-dev to the public
dependency recipe. A separately checked plan adds this one package with no
upgrade/removal. This failure is not a GPU or image boot result. A fresh private
work directory will retain the original failed tree for comparison.

Additional source-only sparse-core audit finds no count/range under-allocation:
mask0x05771777 has18 cores, ID range27/highest index26. Mesa keeps those values
separate; TLS/WLS/scratch/query allocation uses the range, while the kernel
exports the original mask. This is source evidence against that specific
hypothesis, not a runtime measurement of every descriptor allocation.

The fresh patched work tree then configured successfully on native ARM64 using
the tracked builder and exact private Meson1.4.1. Also supplied libclc-18's
runtime SPIR-V builtins: development headers alone do not contain them. Its
separate checked plan adds one package without upgrading/removing existing
packages; both required mesa3d SPIR-V files are now present. Public dependency
instructions include both packages.

Actual two-job compilation is running as a bounded user service with3GiB memory
cap, no swap, at most two CPU equivalents and low background priority. Its
output and receipt stay private; it does not install libraries or start GPU
tests. Completion, output verification and actual rendering remain pending.

At440/1325 build steps, the big CPU sensor reached83C. Reduced only this user
service's CPU quota from200% to100%; readback1s CPU quota per second passed,
the service stayed active and the next sample fell to80C at516/1325. Memory
remained over4GiB available and no fatal compile error had appeared. Kept the
85C stop threshold and recorded the bounded-service recipe; no hardware clock,
voltage or compositor configuration was changed. Full build remains pending.

The native patched build subsequently completed1325/1325 with successful user
service exit and built receipt. Five output hashes, launcher/link hashes,
private absolute EGL JSON target and all four ELF ARM64/little-endian headers
passed independent read-only verification. Maximum sampled big temperature83C;
available memory stayed over4GiB. Nothing was installed into system graphics
paths, and no rendering qualification follows from these checks.

Pre-launch source review found the diagnostic launcher's forced Panfrost name
could bypass kmsro when Wayland chooses the Exynos display fd. The build already
includes kmsro automatically. Future launchers now clear inherited overrides
and retain normal fd-based selection. The completed09942cf build/receipt stays
unchanged; any experiment using that immutable launcher must explicitly invoke
its child through env -u MESA_LOADER_DRIVER_OVERRIDE. This selects the same
verified libraries without editing the receipt or misrepresenting a rebuild.

## 2026-11-19 — Isolated Mesa tiny readback passes before native-size testing

The frozen source/binary smoke program is128x128, not512x512. Pre-run review
caught the requested-size wording error, retained the unchanged program and
qualified only its actual dimensions. With the verified patched launcher and
child-only override removal,100 frames/6553600 bytes compared exactly with0
mismatches. Exit0 in2.972s within the30s deadline; child reaped. Actual Mali-G72
renderer and dynamic-loader init paths prove private EGL/Gallium/GBM libraries
were loaded. The separate dri_gbm backend was not used in surfaceless mode.

Kernel cursor delta has0 new matching GPU/DECON faults. Original display-off,
locked state and PM/clock/voltage/driver settings were unchanged; big/GPU
temperatures55/49C before and48/48C afterward. Raw logs remain private. This
is a small offscreen correctness pass, not a native-size timeout repair or a
desktop driver switch. The next bounded targeted modifier comparison is a
separate pending qualification.

## 2026-11-19 — Patched native-size windowed target passes, limits retained

One bounded targeted run with the isolated patched libraries and nocrc,noafbc
passed the public runner:3/3 scenes, physical Mali, exit0,0 new matching kernel
faults,0 scheduler timeouts and0 soft-stop failures. Actual glmark process maps
prove private EGL/Gallium/GBM load. DECON latch-check counter stayed1 and IRQ
wait counter0. Five created buffers/all11373 attach+commit uses are explicit
ARM U-tiled0x0810000000000001, not AFBC; no unidentified commit. Big/GPU
temperatures51/50C before, maximum78/68C; original display-off/locked state and
all clock/voltage/PM/driver settings restored. No system compositor switch.

Initial two commits were1440x2960, but the other11371 were1440x2896. The latter
raw32bpp color payload is16680960 bytes, below16MiB; backing BO size was not
captured. The earlier AFBC snapshot's allocation exceeded16MiB. Thus this run
does not separate compression from every buffer-size/layout effect, nor prove
all GPU workloads fixed. Presented-buffer evidence also has the documented
render/display copy limitation. Raw maps/protocols/results stay private.

Added an explicit --fullscreen reproduction option after checking the installed
glmark help. It replaces the window-size request without changing readback or
deadlines, so actual steady full-height buffers can be measured separately.
That new option has not yet been exercised on hardware at this entry.

## 2026-11-19 — Full-height patched target also passes

One separate fullscreen targeted run passed3/3 scenes, exit0 and physical
Mali; actual glmark maps again prove private patched EGL/Gallium/GBM. All four
created buffers/all11772 attach+commit uses are1440x2960 with explicit ARM
U-tiled0x0810000000000001; no unknown commit. There are0 new matching kernel
faults, scheduler timeouts or soft-stop failures. Big/GPU temperatures50/48C
before, maximum73/66C. Original display-off/locked state and all GPU settings
restored; no further workload or system driver switch.

This removes the reduced window-height limitation for these three scenes.
The full-height32bpp raw color payload exceeds16MiB, but actual BO allocations
were not captured, so no universal allocation-limit conclusion is made. Full33,
FIFO, desktop animation and long endurance with this stack remain unverified.

## 2026-11-19 — Audit remaining boot warnings without hiding them

Independent read-only#21 audit found no failed system services but confirmed
Wi-Fi Direct interface creation times out waiting for IF_ADD. Ordinary Wi-Fi
being up does not qualify P2P. Roam-trigger failure -52 is a collapsed firmware
error, not proof of UNSUPPORTED; raw firmware status needs diagnosis. Optional
txcap blob absence is separate and must not be filled with another device's data.

MAX77705 MFD expects RGB/charger/haptic child DT nodes, while this board uses
the charger on a separate I2C sibling and has no such children. Charging state
still verifies; that does not qualify haptic/RGB. Exynos9810/exynos7-PMU fallback
has no matching CLKOUT entry. Need actual consumers/register definitions before
adding support; do not invent a5433 compatibility alias.

External-initramfs trailing-data, UFS supply metadata and alternate-GPT fallback
warnings also remain for separate source/backup inspection. No GPT repair,
partition write, firmware substitution or warning suppression was performed.
Raw boot logs and supply details stay private.

## 2026-11-19 — Require completed full-suite scene results

Source review found that the full-profile checker counted33 scene banners and
a score without requiring a completed FPS/FrameTime row for each. Require33
actual complete rows with finite positive FPS and frame time; targeted checks
also validate both numbers. Announcements/skips/zero/malformed data now fail.
18 host regressions pass. A peer applied the new checker read-only to an
existing actual#18 full33 log and all33 complete rows were accepted. No raw
fixture is published. This is workload-completion validation, not an identity
audit of every possible benchmark scene or a substitute for GPU fault checks.
The next hardware full-suite run remains separate from this source check.

## 2026-11-19 — Isolated full-height full-suite rendering completes

One strict full-profile run passed100 exact128x128 readbacks, all33 complete
positive FPS/FrameTime scenes and fullscreen FIFO61/61/61fps, with0 new matching
GPU journal faults, scheduler timeouts or soft-stop failures. Actual scene/FIFO
glmark maps prove private patched EGL/Gallium/GBM. All13605 scene and728 FIFO
commits are1440x2960/U-tiled; no unknown commit. Big/GPU maximum76/68C, no thermal
abort. Restored original display-off/locked state/settings; no glmark remains.

The100us IRQ shadow-check rejection counter increased1→2 inside the public
workload interval. The40ms generation-wait timeout counter stayed0; generation
marks and waits both increased5836→8571. This counter rejects an IRQ that cannot
yet certify the pending generation and is not itself a50ms flip failure. No
per-scene counter sample exists, so its frame impact remains undetermined.
Neither ignore it nor label a proven missed frame from this observation alone.
The system compositor still uses system Mesa; desktop animation and long
endurance with the new stack remain separate qualifications.

## 2026-11-19 — Source fixes for bounded Wi-Fi diagnosis and PMIC correctness

Integrated exact-hash source helpers into the build-only kernel patch step.
Wi-Fi logs only rate-limited numeric selected command/firmware status and P2P
IF-event metadata. No payload/MAC/SSID/credentials. A separate minimum IF-event
length check rejects0..4-byte records before existing readers and frees once;
valid event behavior is unchanged. This does not implement a P2P workaround.

PMIC patches correct RGB single/multicolor object identity, LEDEN mask/value
order and error propagation, plus verified MAX77705 bias02/bit7 and supply-error
rollback. Preserve all upstream license notices, including ISC Wi-Fi and the
GPL-2.0-or-later haptic notice; project helpers/tests retain GPL-2.0-only.
16 actual PMIC C scenarios and exact-hash/idempotence checks passed; Wi-Fi
production-function tests passed AddressSanitizer/UndefinedBehaviorSanitizer,
filter/redaction/return/short-event checks. Root independently repeated both
Linux-host test sets successfully. No DT/config/hardware enabling, kernel
deployment or RGB/haptic/P2P hardware success is implied. ARM64 compilation
and actual device trials remain separate pending steps.

The complete kernel patch step applied twice to the actual pinned cache with
unchanged second-pass hashes for all four Wi-Fi/PMIC files. ARM64 compilation
of fwil.o, fweh.o, leds-max77705.o and max77693-haptic.o passed. No image was
flashed and RGB/haptic configuration remains disabled; native#21 is unchanged.

## 2026-11-19 — Prepare a timed user-session Mesa trial

Added a separate explicit deployment helper, never invoked by build scripts.
It checks selected G965N BOOT/startup receipt and complete private backup
provenance before staging unique user-only environment/Shell wrapper files.
Normal driver detection, coherent private library/vendor hashes and generated
vendor JSON pins are enforced. Unknown existing GPU overrides/path conflicts
are refused. Greeter/system Mesa and personal application preferences stay
outside this trial.

The actual Shell service refuses direct manual restart; preserve its no-argument
gnome-shell command and recreate the graphical session through GDM instead.
A root system rollback timer is reserved and verified before profile writes;
global reservation and per-trial lifecycle locks prevent overlap. State updates
are atomic, user paths are created/removed as the user, modified files are
preserved/reported, and explicit root evidence is required to cancel rollback.
Manual rollback remains possible after acceptance. Legacy D-Bus activation
environment is deliberately untouched because absent variables cannot be
faithfully restored through that API; those apps need independent map checks.

17 host tests passed, including concurrent reservations, timer ordering,
atomic-state failure, rollback/accept races, active JSON tamper and runtime-link
escape checks. Test lifecycle operations are mocked; their printed restart
messages are not device evidence. No profile application or GDM restart has
occurred at this source-review checkpoint.

## 2026-11-19 — First desktop trial exposes incomplete graphical rollback

Rehashed all nine host backup images, then actual trial preflight verified
selected#21 BOOT and current EFS/CPEFS/RADIO provenance. The first user-only
profile loaded a real Shell with private EGL/Gallium/GBM/dri_gbm; fresh SSH,
system service health and GPU journal boundary passed. No extra GPU load ran.
The independent timer fired naturally at304s and removed all four owned files,
restoring the original user-manager PAN_MESA_DEBUG=nocrc without changed-file
conflicts. That file/environment result was not a successful graphical return.

GDM remained running but Wayland Shells failed EGL initialization; no Shell
survived. Xorg fallback also failed because Xorg is not installed. Systemd
failed-unit count0 alone was misleading. No new GPU kernel fault or retained
DRM client was found. No changed system/GDM GPU environment was demonstrated;
stale session-bus state was a hypothesis, not an established single cause.

One controlled normal-admin recovery stopped GDM, restarted user@1000.service,
then started GDM with original configuration. Fresh SSH and a new Shell using
actual system EGL/Gallium/GBM/dri_gbm proved graphical recovery. Restored the
original screen-off/locked state, confirmed exact#21 BOOT, no new GPU faults and
unchanged DECON2/0 counters. The compound recovery does not isolate which user
session state caused the earlier failure. No second trial was attempted yet.

Source trial helper now uses that clean user-manager sequence for both apply
and rollback and requires three stable actual Shell/library observations,
rather than treating GDM job success as desktop recovery. File/environment/
desktop restoration have separate atomic state fields; failed recovery is
reported without an automatic retry loop.21 host tests pass; the new sequence
still needs its own natural-timer hardware trial. This restarts all user-manager
services; it is not a promise to preserve their background work.


## 2026-11-19 — Clean-session automatic rollback verified; fix app environment priority

The second trial used the corrected clean-session lifecycle. Its independent
300s timer fired naturally; root service exited0 and all four owned files were
removed. File/environment/desktop restoration state fields all verified true.
Fresh SSH, a new stable stock Shell with system EGL/Gallium/GBM/dri_gbm, normal
display API and original PAN_MESA_DEBUG=nocrc prove actual graphical recovery.
No manual retry, acceptance or timer cancellation occurred. Restored screen-off/
locked state; exact#21, no new GPU fault and DECON2/0 unchanged. FUSE portal
failure remains separate. The trial was not accepted as persistent deployment.

The trial Shell had nocrc,noafbc but user-manager apps inherited nocrc only.
Actual source cause:99-environment.conf reads /etc/environment after the trial's
91-prefixed file and overwrites PAN. Future owned environment files now sort
after that99 file; no global/PAM configuration is edited. Post-startup manager
environment must match the whole intended whitelist exactly, including missing
versus empty. Rollback also checks the final effective manager environment.
25 host tests pass. This latest priority fix still needs its own device trial.


## 2026-11-19 — Defer document portal work to a separate WIP branch

At the owner's request, removed the document-portal/FUSE compatibility recipe
from this driver/system branch and moved its source and dedicated verification
notes to codex/g965n-document-portal-wip, preserved as draft PR#1
(https://github.com/TurboCE/galaxy-s9plus-ubuntu/pull/1). The host-only module build
completed, but no module was loaded or installed on the handset. No kernel
configuration, startup service or portal setting was changed. Earlier portal
observations inside GPU session logs remain historical context, not an active
repair task. Further work here focuses on drivers and basic hardware/system
functions. The working tree is kept clean after the split.


## 2026-11-19 — Follow boot/kernel evidence; built-in initramfs contract

Owner directed work toward actual boot/kernel errors rather than repeated
individual function trials. Read-only native #21 warning review confirms the
external-initramfs unpack failure, CLKOUT parent mismatch, pinctrl IRQ metadata,
MAX77705 child-node warnings and Wi-Fi roam/P2P errors remain. CPU feature
variation and cache hierarchy messages need source/DT interpretation; no CPU
capability is fabricated and no warning filter is applied. Historical GPU
timeouts in the same boot remain historical evidence, not new failures.

The external image is a valid empty gzip placeholder, while the intended /init
is built into Linux. Explicit INITRAMFS_FORCE selects that existing design;
a post-olddefconfig contract rejects absent flags, wrong source, empty/wrong
entry or symlinks before Image build. Loader bytes/addresses are unchanged.
Four host regression tests and shell syntax pass; isolated real olddefconfig
retains the intended settings. Hardware warning removal is not yet verified.

The prior final desktop trial rejected a post-startup manager environment
mismatch and restored all owned files, original environment and actual stock
Shell automatically. Fresh SSH, unchanged DECON2/0 and no new GPU faults were
verified; normal screen-off/locked state restored. The initiating differing
key was not retained, so its cause is unknown. The helper now saves the
whitelisted apply observation privately before rollback, separately from the
rollback observation; 26 host regressions pass. No further desktop trial or
persistent private-Mesa acceptance is claimed. Individual trials are deferred
under the owner's latest instruction.


## 2026-11-19 — Kernel #22 build and guarded boot-log comparison preparation

Full kernel plus audio/Bluetooth/sensors/modem package built from96ed0a3.
Final config retains INITRAMFS_FORCE=y and the exact embedded init source.
The package is pinned to #22; private audio/Bluetooth startup was staged for
that exact BOOT without loading any module. Modem/sensor services remain off.
Preserved private pre-update kernel/system warning logs, then requested TWRP
for a fresh nine-partition backup and guarded BOOT-only update. At this
checkpoint no new BOOT has been written. Build warnings from inherited sensor
and modem compatibility code remain; compilation is not runtime qualification.


Boot-warning source triage: UFS's absent vdd-hba/vccq/vccq2 and optional
vcc-max-microamp use documented always-on/default handling; the owner's
stock rev26 DT also lacks them. No invented rails/current limits were added.
Bluetooth's Read Transmit Power message is the existing board-scoped broken
command quirk explanation; core skips the unsupported LE query. Removing that
quirk would remove protection, so it remains. Neither result qualifies full
UFS/Bluetooth operation or tests unsupported firmware commands.


Kernel #22 hardware result: fresh complete nine-partition backup and guarded
model/identity checks passed. BOOT alone was written and byte/hash readback
matched before reboot; RECOVERY/EFS/CPEFS/RADIO were not written. Native #22
booted, fresh USB SSH and actual BOOT receipt verified, zero failed system
units; exact audio/Bluetooth startup services active. This is startup evidence,
not renewed acoustic/profile qualification. No initramfs unpack failure remains
in the new boot log. No panic/Oops/SError/GPU scheduler timeout was found; an
initial broad SError search matched the word ramoops, so it was inspected and
not counted as a fault.

Pinctrl IRQ, CLKOUT, MFD and Wi-Fi errors remain. New bounded Wi-Fi diagnostic
records cmd55/ifidx0/fwerr-3 for roam-trigger failure; the old errno-52 alone
could not establish its firmware cause. P2P creation still times out. No modem
bring-up or individual peripheral trial was run. Private before/after logs
remain on-device outside Git.


CPU/cache source audit: cache hierarchy attributes and next-level-cache links
are absent in both current and owner-stock DT. ARM64 CLIDR enumeration alone
does not recover size/sharing. Treating the OF failure as success would expose
unverified fallback sharing (all levels above L1), so no warning-only bypass
was applied. A55/M3 SANITY differences are real ID fields; the pinned feature
code computes lower-safe common values before reporting strict mismatches.
System HWCAP/LSE selection uses sanitized values and mismatched CTR has its
existing trap/emulation path. No overexposure defect was found in this audit;
this is not complete heterogeneous-CPU qualification. Do not weaken strict
masks, forge compatible strings or invent cache topology to clear warnings.


## 2026-11-19 — Correct Exynos9810 pinctrl interrupt topology

Boot-log root cause: ALIVE/CMGP contain wakeup/non-interrupt banks, but their
controller data invokes the separate generic GPIO-group initializer without
an aggregate IRQ. Remove only those two inapplicable callbacks; retain every
bank, wakeup handler and suspend/resume hook. Separately, mainline gpa4's two
individual parent IRQs are missing. Pinned Lineage rev26 maps pin0/1 to SPI446/447;
restore those exact parents using the existing mainline wakeup-bank convention.
This restores interrupt topology rather than changing diagnostics or removing
devices. Source/patch hashes are pinned, drift rejected and reapplication exact.
Three actual-data host tests with ASan/UBSan pass; build integration added.
Not part of #22 and no native correction claimed until the next boot.

MAX77705 topology audit is documented separately: a phantom platform charger
cell differs from the working sibling I2C driver; RGB/haptic require real board
connections. No empty child nodes or invented motor supplies were added.


#22 raw roam diagnostic interpretation: pinned fwil error table maps -3 to
BCME_BADOPTION, distinct from BADARG(-2) and UNSUPPORTED(-23). Pinned vendor
101_16 blocks legacy roam-trigger changes under PRODUCT_WBTEXT policy5 and
uses optimized preinit without cmd55. This is a concrete policy-conflict
hypothesis, not a confirmed live policy value. No forced policy change,
unconditional skip or unsupported-error reclassification is applied.

Pinctrl regression was independently rerun under the Linux builder: two tests
passed and the optional local-Lineage-tree crosscheck skipped (the same
crosscheck passed on the Mac). Wi-Fi diagnostics tests, experiment-package
tests and PMIC actual-C correctness tests also passed. No feature exercise
was added.


Kernel #23 built from4c471d4 with pinctrl topology corrections. Verified exact
private module hashes and staged only audio/Bluetooth startup for its BOOT,
then requested recovery for fresh backups. No sensors/modem loading, HCI
queries, graphical stress or physical interaction was requested.


#23 hardware boot-log result: fresh nine-partition backup complete; guarded
BOOT-only update and byte/hash readback passed. Actual native #23 BOOT matches
its package; fresh USB SSH, zero failed system units and exact audio/Bluetooth
service startup confirmed. External initramfs unpack failures remain zero. All
three earlier samsung-pinctrl IRQ topology diagnostics are now absent. No new
WARNING/BUG/Oops/panic/Asynchronous SError or GPU scheduler/soft-stop failure
signatures were found in this boot observation. This is boot/log qualification,
not physical button/wakeup/suspend or all-feature qualification.

CLKOUT parent failure, MAX77705 missing children and Wi-Fi roam/P2P errors
remain; CPU/cache messages retain their documented limitations. No logging
filter, clock/voltage workaround, partition repair or unrelated feature test
was introduced. Private complete before/after logs remain outside Git.


## 2026-11-19 — Resume physical sensor qualification with owner present

On native #23 no sensor transport/daemon was running. A first service-verifier
invocation used the staging package directory rather than the installed flat
service layout and rejected a missing audio module before hardware changes.
Corrected preflight called the existing exact BOOT/kernel verifier plus the
manifest's sensor module path/hash. Loaded that exact sensor transport once.
Prepared only SYSTEM/VENDOR ro,noload isolated runtime; no original identity
partitions exposed, no modem bring-up. Started a shared-lease lhd with stock
config and independent600s lifetime limit, no restart. Hub ready1,chip0x55,
firmware21031900 and advertised mask137422698175 verified.

Light baseline uses own-device lux18 layout. Enable produced480lux,4397K and
nonzero RGBW;10s measurement window then had no new sample/unparsed frame.
Pinned Android LIGHT report mode is ON_CHANGE, so missing periodic data alone
is not a fault. Historical all-zero readings are not reproduced here. Owner
requested restarting the cover test; sent SIGTERM to the first bounded probe
for its normal sensor-disable cleanup, then started a fresh60s window.
No calibration/threshold/glass/coefficient write was made. Optical-response
qualification remains pending actual owner timing and new readings.

Extended source diagnostic groups for exact pinned compass(2/3/4),pressure5,
proximity7/raw10 payload formats, retaining legacy all=0/1/9. Explicit mask
check precedes enable;29 host parser/phase/cleanup regressions pass. No native
expanded-sensor results claimed yet.

Light restarted physical window completed with owner-confirmed four cover/
uncover repetitions:204 post-enable samples over60.022s, lux68..391, varying
RGBW and0 unparsed frames. Two enable-time samples counted separately. This
qualifies observed optical response, not calibrated absolute lux or desktop
automatic brightness. Source upload to the root-private result directory was
correctly denied; copied diagnostic source to the existing user staging path
instead, leaving private result permissions unchanged. Expanded probe now
runs a separate proximity window with the owner; no persistent settings changed.

Proximity physical window: owner confirmed four close/far repetitions.
Sensor7 provided10 post-enable events over60.064s, detect bit0/1 and ADC118..1105;
two enable-time events separate,0 unparsed frames. Both close/far states and
raw optical variation observed. This is not a calibrated distance in cm or
call-screen integration qualification. Motion/compass physical trial started
with explicit owner movement request; no calibration commands sent.

Owner-confirmed movement window: native#23 accel/gyro each140 samples/25s,
all axes varied;0 malformed frames. Compass IDs2/3/4 each yielded125/139/125
post-enable samples with0 malformed frames, but only raw/uncalibrated vectors
varied: calibrated ID4 remained exactly[-541,-1130,824,0,0] despite movement.
No heading/calibration qualification; simultaneous-mode interference or
missing vendor initialization remains under source review. Pressure probe
started separately; no user maneuver or calibration write required.

Calibrated compass isolated ID4 trial completed40.085s with200 samples:
vector axes varied, accuracy advanced0→2, overflow remained0 and no malformed
frames. No orientation/PDC/calibration/fuse command was sent. The earlier
combined-factory trial versus elapsed calibration convergence is not causally
isolated. Default compass now selects ID4 alone; raw/uncalibrated remain
explicit diagnostic options. Read-only fuse option is source-tested but was
not invoked.32 sensor regressions pass. Do not claim calibrated heading or
absolute direction accuracy from vectors/accuracy status alone.

Pressure returned84 samples/15.101s, raw4161524..4161650 and temperature
3983..3995 (39.83..39.95C under the pinned factory formatting contract).
Absolute pressure units/calibration are unqualified; no hPa conversion guessed.
All probes ended with their disable cleanup. Deliberately stopped lhd, observed
ready0, tore down runtime and unloaded transport without residual lhd clients.
No new matching fatal/GPU/BUG/WARNING signatures during sensor trials. Sensor
autostart, automatic brightness/rotation and desktop integration remain absent.

Prepared source-only one-shot Wi-Fi policy observations before existing roaming
writes. S9+/BCM4361/primary-interface guard; exactly two GET queries; numeric
results invalidated on failure; existing settings/return paths unchanged. Four
actual-C/sanitizer regression tests pass. No native policy result claimed yet.


## 2026-11-19 — Add guarded Exynos9810 dual CLKOUT provider

Pinned vendor definitions establish two outputs at PMU+A00/A0C,6-bit muxes,
TCXO slots1/0,active-low gate bit0 and original AUD/NFC consumers. Added a
9810-only dual provider plus PMU known-TCXO parent description. Unknown mux
inputs remain orphans, never mislabeled TCXO. Existing single-output paths
remain byte-identical outside the new branch. No audio/NFC consumer is newly
connected;9810 CLK_IGNORE_UNUSED prevents unused-clock cleanup from gating
bootloader outputs. That flag does not prohibit explicit future consumer
disable or mux changes; their qualification is still required.

Three host actual-C/fake-MMIO sanitizer tests pass, including probe with no
MMIO writes,6-bit/active-low masks,8 failure unwind stages,two-register
save/restore and pinned original definition checks. Independent source review
found no immediate blocker. Those tests do not emulate full CCF/orphan resolution
or cross-driver PMU concurrency. Integrated exact-hash recipe into build stage;
no native provider registration/clock operation claimed before the next boot.


Auxiliary sensor window used a separately bounded180s lhd after exact#23
BOOT/module revalidation; no automatic restart. ID34 thermal special-report
probe returned0 samples in15s and two unparsed frames; a5s repeat returned0
samples and no rejected record metadata. No unsupported-layout conclusion
was drawn. Source shows ID34 participates in threshold/overheat notification;
its silence at ordinary temperature is not a failed periodic thermometer.
No overheat threshold was written or heating test performed.

Rotation IDs16/17 each returned84 samples/15.094s with one unparsed frame.
Last raw byte246 is not interpreted as Android accuracy0..3; pinned kernel
passes it through without semantic/scaling definition. Quaternion units and
correct orientation are unqualified. All auxiliary probes disabled on exit,
then lhd was deliberately stopped(ready0), runtime unmounted and transport
unloaded. No daemon remains from these windows.

SX9320 grip is outside SSP. Pinned Lineage enables its I2C node but owner's
stock rev26 marks it disabled, so physical population/stock activation remains
unconfirmed. Current DT/config does not enable it; mainline SX9324 has a
different WHOAMI and cannot be used as a false compatible alias. No new
I2C access, supply or IRQ activation attempted for grip.


Built native candidate#24 from49b7591 with exact feature package. All hashes
verified; audio/Bluetooth startup staged for its BOOT. Fresh nine-partition
backup and guarded model/identity checks passed before BOOT-only update.
Readback verified by installer before automatic reboot. Await native boot-log
comparison for CLKOUT registration and numeric Wi-Fi policy observations.
Source-only read-thermal-adc option passes38 regressions; no ADC hardware
result claimed at this checkpoint. No heat/threshold test is planned.


#24 native boot result: actual kernel/SSH returned,0 failed system services,
audio/Bluetooth startup active and no matching new fatal/GPU/BUG/WARNING
signatures in the boot window. Both CLKOUT providers now register and former
parent/probe errors are absent. CCF reports output1 known26MHz/disabled;
output0 is enabled with unknown parent/rate0. Preserved that inherited mux
without a guessed switch; registration is not full output/audio/NFC clock
qualification. No new consumer connection or hardware clock change was made.

Wi-Fi boot observer reports preinit query ret-52/invalid, WBTEXT query success
with policy5; legacycmd55 still returns rawBADOPTION(-3). This confirms the
product-policy guard's live prerequisite, but preinit failure remains generic
Linux mapping. Proposed next fix is scoped to successful policy5 and mirrors
stock's prohibition on legacy trigger writes; other policies/failures retain
original behavior. No policy is changed.

#24 direct thermistor read: exact BOOT/module checked before bounded120s
lhd runtime. Read-only factory channel0/1 commands returned ADC2154/2220;
no stream enable, threshold, coefficient or heating command was sent. One
unparsed asynchronous frame remained; no temperature conversion/absolute
calibration or overheat-event delivery is qualified. Normal cleanup stopped
lhd(ready0), unmounted runtime and unloaded transport.38 host regressions pass.


## 2026-11-19 — Preserve product WBTEXT roaming policy

Actual #24 policy5 result plus pinned stock set-roam-trigger guard justify a
scoped behavior correction. Each qualified S9+/BCM4361/primary setup reads
fresh WBTEXT policy; only successful value5 preserves firmware's existing
product profile by omitting legacycmd55. No WBTEXT/profile is written. Other
policies/query failures/boards/chips/interfaces retain original command55
and error behavior. Beacon timeout,roam_off,delta write order/payload and
returns remain unchanged. First-setup numeric diagnostics remain bounded;
subsequent setup reads policy anew without repeated diagnostics. Exact#24
source migration verifies old→pristine→new hashes before applying. Five
host tests including actual-C ASan/UBSan cases pass; native fix pending.


## 2026-11-19 — Remove phantom MAX77705 charger platform cell

The MFD declared a platform charger although the real driver is I2C-only at
charger@69; binding requires an I2C reg and the MFD child schema lists RGB and
haptic, not a charger platform device. Removed that single unused cell line.
The real I2C driver,board DT,IRQ domain/source masks,battery topology and
RGB/haptic registrations remain unchanged. Actual-C original/patched arrays
and unchanged IRQ source tests pass on Mac/Linux, plus original16 PMIC cases.
Native #24 baseline retains charger@69 binding,online1,input limit500000uA,
charger statusCharging while battery reportsDischarging; that baseline is not
a claim of increasing net battery charge under this load. No current limit
or supply register is changed by this source correction. Native verification
of phantom warning removal and real binding awaits #25.


Kernel#25 built fromaf1524f,exact module hashes verified and matching audio/
Bluetooth startup staged. Fresh complete nine-partition backup and guarded
model/identity preflight passed. BOOT-only write and byte/hash readback passed
before reboot; no RECOVERY/EFS/CPEFS/RADIO write. Native verification follows.


#25 hardware verification: actual kernel and BOOT receipt matched, fresh USB
SSH returned and system failed units0. WBTEXT policy5 still reads successfully
and neither command55 BADOPTION diagnostic nor roam-trigger setup error now
appears. This verifies the scoped initialization correction, not handover
between access points. HTTPS explicitly bound to wlp1s0 returns204.

The phantom max77705-charger child-node warning is absent. Real I2C1-0069
remains bound to max77705-charger with online1,statusCharging,input500000uA.
No charging-limit adjustment. Audio/Bluetooth exact-package startup active.
Former initramfs/pinctrl/CLKOUT errors stay absent; no matching new fatal/GPU/
BUG/WARNING signatures in this boot observation. Sensors/modem not started
in #25. RGB/haptic missing child nodes and P2P IF_ADD timeout remain; CPU/cache
limitations and desktop sensor integration remain documented. No all-feature,
roaming,endurance,heading,absolute-temperature or suspend success claimed.


## 2026-11-19 — Install requested sensor frontends; integration remains absent

Owner requested sensor apps and asked whether GNOME already consumes sensors.
Read-only native#25 inspection found no IIO devices, no loaded hub transport
and no prior iio-sensor-proxy installation. Installed Ubuntu repository sensor
explorer/demonstration,Psensor/lm-sensors,Qt runtime and iio-sensor-proxy. No
package upgrades/removals or kernel/firmware writes were requested. Added
phone-sized desktop launchers and an original minimal Qt Compass frontend
that never synthesizes headings and stays waiting without fresh real readings.
Upstream third-party Compass source was inspected on the host only; its device
whitelist/demo fallback was not installed or redistributed. The local frontend
and launchers are recorded separately under experiments/sensor-apps for reuse.

Desktop entries validate; Compass/Explorer/sensor-demo processes remain active
in the real ordinary-user Wayland session without initial QML failure. Launch
checks are not sensor-reading qualification. A Psensor launch found an already
running instance, which was preserved. iio-sensor-proxy exits successfully
without IIO devices; attempted DBus property queries lost their recipient,
not a service crash. lm-sensors reports no hwmon devices. GNOME orientation/
brightness settings, SSP autostart and driver configuration were not changed.
Automatic rotation/brightness and application compass readings remain absent;
previous raw sensor tests are not system integration. No FUSE/portal changes.


## 2026-11-19 — Begin real IIO integration; axis qualification deferred

Native#25 read-only checks confirm CONFIG_IIO is disabled and no standard
sensor devices exist. Exact BOOT/module checks preceded a bounded lhd window;
identity0x55/fw21031900/mask verified,actual E1 full-scale query returned8G.
Pinned LSM6DSL factory contract4096counts/g supports scale9.80665/4096.
Owner cannot hold device for six-pose qualification now. No inferred mounting
matrix or automatic rotation is applied. Stopped lhd,unmounted isolated runtime
and unloaded transport normally after the read-only range check.

Added an opt-in real IIO feed module plus typed48-byte exclusive root writer
ABI. It publishes only actual validated SSP readings, lazily registers devices
after first data and invalidates/removes them on writer close. ALS-only is
default; all acceleration frames fail before state changes unless explicit
accel opt-in and validated mounting matrix. Heartbeat does not revive stale
continuous acceleration; on-change light stays valid only while its broker
is alive. No fake sysfs or mock DBus provider, no compass-heading substitute.
Two actual-C host sanitizer harnesses pass; exact-kernel IIO packaging guards
pass7 tests. Kernel/core and module build integration added under explicit
S9_EXPERIMENTAL_IIO_BRIDGE. No IIO module/native boot qualification yet.


Candidate#26 Image/core compiled but external bridge build failed because
Linux7.1 removed no_llseek. No artifact was installed and native#25 stayed
running. Replaced the legacy field with stream_open()+llseekNULL using the
pinned kernel's stream semantics; actual-C host tests verify nonseekable
FMODE_STREAM and denial paths. New full build required.

Owner returned for mounting checks. Idle canonical SSP lock verified as
root-owned ordinary/single-link/exclusively free,then explicitly migrated0644
→0600 without truncation. New nofollow lock helper refuses unsafe metadata
and passes42 host tests. Exact#25 transport and bounded900s lhd restarted.
First three labeled poses had near-identical dominant rawX; do not infer
orientation from them. Continuous movement comparison requested to separate
physical target/pose timing from a stuck data path. No matrix installed.


Six-pose operator qualification completed on#25. Initial unchanged-axis values
were explained by yaw with phone top kept upright, not a stuck sensor. Explicit
portrait/photo-landscape roll instructions produced independent signed axes.
One unstable landscape capture was repeated; all six then passed the explicit
handheld15deg discrete-axis policy (strict mode unchanged). Qualified matrix
0,1,0;1,0,0;0,0,-1 has determinant+1. Raw observations and evaluation remain
private; no continuous precision-calibration claim. New REMOVE_SENSOR uses
the actual200ms enable delay, matching pinned stock; bounded post-remove
read after drain observed0 acceleration samples/3s. Transport was then stopped/
unmounted/unloaded normally. Earlier zero-delay removals did not establish
semantic stop, although final lhd/transport shutdown remained effective.

Source sensor-only supervisor, typed broker and desktop trial rollback added.
Runtime does not expose modem/identity nodes; staged exact node rwm creation
permission narrows to rw before children. Host runtime17,broker7,rollback3 and
orientation9 regressions pass. Kernel#27 core+bridge/module package built from
ef06a8b after#26 API correction. Fresh9backup complete and BOOT-only install
started; successful device boot and IIO publication remain separate checks.
Owner now requests no verification subagents; all earlier agents are finished
and further implementation/verification is performed by the main agent.


Native#27 boot,exactBOOT receipt and audio/Bluetooth startup verified. First
sensor-service trial failed before enabling data because broker queried the
transport immediately while lhd was still starting. Ordered failure cleanup
removed its owned runtime; no IIO devices or dangling child remained. Added
a bounded receive-only ready wait before SSP identity, respecting STOP/EOF;
8 broker host tests pass. No automatic hardware reset/retry loop added.

Second explicit start succeeded: real IIOaccel/rawxyz/scale0.002394202 and
qualifiedmountmatrix plus real processed illuminance appeared. Stock Ubuntu
SensorProxy reports HasAccelerometer=true/HasAmbientLight=true. SSH-launched
monitor asUID1000 was correctly denied by active-session policy; launching
through that user's normal systemd manager succeeded and actual lux values
updated(219..268 in observed window). Policy was not weakened. A normal
no-device/defaultLightLevel0 is not promoted to a valid measurement.

Exact runningDeviceAllow shows onlyBOOT/SYSTEM/VENDOR read plus reviewed
char nodes rw(no m or broadmisc grant). Source template's helper children
emitted one rejected notify message; primary READY succeeded, provenance
is being traced before final persistence. Orientation remains locked while
raw service qualification runs; independent240s original-display restore
timer armed for the next real GNOME rotation trial. No backlight device
exists: current panel implements only fixed gamma/dimming setup, so auto
brightness is not claimed merely from ALS success.


Native#27 GNOME integration qualification: SensorProxy normal state maps to
actual logical display transform0; owner photo-landscape produces left-up and
actual transform1. PanelOrientationManaged=true. Owner explicitly confirmed
landscape desktop and correct touch alignment. Independent restore timer was
then cancelled and original ambient setting restored. This is evidence for
normal/left-up transition, not every display pose or all sensor features.

Ordered production stop invalidated/unregistered both IIO devices,closed lhd
and removed owned mounts with serviceResultsuccess. Broker published4144frames
in that window,processCPU6.337s and service peak90.5MB. A subsequent start
succeeded. Sanitized NOTIFY_SOCKET inheritance fixed the rejected child helper
notification; primary READY remains intact. Bounded unselected sample arrays
prevent unrelated known records accumulating;9 broker regressions pass.

Enabled guarded service and performed a real reboot of the same#27 BOOT.
Sensor service auto-started successfully in the fresh boot, both real IIO
devices reappeared,HasAccelerometer/HasAmbientLight remainedtrue and GNOME
PanelOrientationManaged=true. Audio/Bluetooth startup active and no matching
new fatal/GPU/BUG/WARNING signatures observed. Owner again confirmed automatic
rotation and touch after reboot. No verification subagents used after the
owner's instruction. Qt LightSensor in the ordinary user manager received
actual272/271/270lux; its initial cache0 was not counted as physical evidence.

Panel backlight interface remains absent and no brightness setter is invented;
ALS integration does not establish automatic screen brightness. Compass still
needs qualified heading integration; prox/gyro/barometer/thermal system paths
and full LTE/GPU/suspend parity remain separate. Sensor runtime currently owns
the shared vendor-runtime lease; do not start modem migration tools concurrently.
The exact service has Restart=no: a failure stops/invalidates readings rather
than repeatedly resetting hardware. Long endurance/power remains unqualified.

## 2026-11-19 — Native GNOME rotation lock confirmed

The owner initially reported the Auto Rotate tile missing, then found it in
quick settings and physically confirmed that disabling it prevents rotation.
Live read-only verification found orientation-lock=true, sensor service active
and both real acceleration/illuminance IIO devices present. Mutter's panel
orientation management was already verified true. Documented the existing
GNOME control and its inverse relationship to the orientation-lock setting;
no replacement UI or device configuration write was necessary. Rotation lock
across a further reboot remains untested. Rechecked that no panel backlight
interface exists; working ALS and rotation lock do not qualify automatic
brightness or compass heading.

## 2026-11-19 — Bounded calibrated-magnetometer capture candidate

Added an explicit private magnetic_capture profile option to the existing
single-reader broker. It enables calibrated ID4 alongside qualified accel/ALS
without raw2/3 or firmware calibration/position writes. It records separate
received batches, never fabricated simultaneous pairs or heading angles, in
a root-only exclusive JSONL file, bounded to600s/2MiB. On expiry it removes
ID4 with the real enable delay and continues normal accel/ALS service.
The default profile remains unchanged. Broker12/runtime17 host tests pass;
one runtime mock initially lacked the optional broker validator, fixed by
loading it only when the diagnostic option is present. Native sampling and
heading qualification are pending. Automatic brightness still lacks the
actual takeover driver's DSIM brightness command path, not merely a frontend.

## 2026-11-19 — Duty-only backlight source candidate (not qualified)

The active display path is the custom inherited-state DECON takeover, not the
unused mainline S6E3HA8 panel driver. Added an opt-in panel_aor backlight there:
16 stock star2_a3_s0 AOR duty values, inherited gamma/voltages preserved, no
HBM or speculative DCS51 command. Zero uses display-off. DSIM packets are
limited to1..3bytes, FIFO waits bounded, batching mode refused, vendor key
closure attempted after every failed transaction. One mutex serializes DPMS
and backlight updates; asleep requests are cached and restored on wake.
Native model gating still relies on the guarded G965N install workflow; the
shared DT reports star2lte/SM-G965F and is not independent proof of G965N.
S9_EXPERIMENTAL_PANEL_AOR=1 explicitly opts the build into the trial; default
remains off. Actual C failure-injection/sequence tests and shell syntax pass.
No successful build, boot, visible dimming or automatic brightness claimed.
Original Samsung GPL register/table attribution retained in panel-aor.h.

## 2026-11-19 — Physical cardinal magnetic trial and calibration candidate

On native#27 the bounded broker trial kept real accel/ALS available and
received calibrated ID4 without raw2/3. Owner completed8-shaped motion and
four flat cardinal poses against a second compass. Each cardinal window had
60magnetic and67acceleration samples; accuracy stayed1,overflow0. A tentative
shared-axis planar calculation differed from reference by up to36.8degrees
(west). This is a failed heading-quality check, not a working compass. Raw
records remain private. Capture stopped appending at600s while sensor service
and both IIO devices stayed active; the explicit ID4 remove path returned.

Prepared an offline-only own-backup extractor: verifies G965N manifests and
BOOT/EFS hashes, matches actual revision26 stock sensor properties, reads
only the existing25byte FactoryApp/gyro_cal_data via read-only debugfs and
keeps the13byte magnetic state plus27byte own board PDC private. No original
EFS mount, O_CREAT fallback, NVM save or zero-filled calibration allowed.
Actual verified own extraction passed with nonzero NVM state. Added explicit
private-pinned trial initialization matching stock fuse-read,FD PDC,46 state
commands; neverF1 because that could invalidate qualified acceleration axes.
Host payload/command/backup guards pass; native initialization and its effect
on heading quality are pending. Owner has left; no further physical pose or
visible-brightness confirmation is available now.

Backlight candidate built successfully as kernel#28 from1b2d58e,BOOT
10cbb650cb6bc78b3035c2451a09f0c91fb27da72a5cb1b67c1569acf8673541,
27219984bytes. No new-kernel boot or actual brightness success yet.

Native#27 own-init trial passed valid fuse read and volatileFD/46 command
handshakes;280magnetic records all reported status3 and overflow0. This is
stronger firmware-quality status, not proof that north/tilted heading is
correct. No F1 or persistent calibration write was sent. Before reboot the
one-shot capture/init profile was removed and original production profile
restored, avoiding intentional exclusive-output failure on restart.

Fresh nine-partition pre#28 backup completed and guarded BOOT-only write
readback matched10cbb650...8673541/27219984bytes. Native#28 boot succeeded.
As intended, the old sensor BOOT pin rejected startup until exact#28 receipt,
modules and fresh backup manifest were privately staged; production service
then started with one-shot magnetic options absent. Audio/BT startup active.
Backlight max16,requested16,actual16; GNOME Screen Brightness100 exposed.
Independent45s maximum-brightness rollback was armed for a manual sweep.
Requested16,12,8,4,1,0,16 each matched completed actual readback; original
ambient policy restored and rollback timer cancelled after success. No
matching panel/BUG/WARNING/SError/Oops/Panfrost-fault entries in that window.
This proves bounded native command completion, not optical brightness, full
Samsung gamma/HBM parity or automatic dimming. ALS3lux/currentbrightness100
requires a standard GNOME ambient normalization/light-change trial.
Added private exact-BOOT brightness-rollback helper (2tests) and read-only
bounded real ALS/backlight observer; no fake sensor inputs or policy bypass.

Native#28 follow-up: GNOME's ordinary Brightness Set25 produced requested/
actual4. Three independently wake-timer-guarded DPMS cycles read actual0
asleep and restored4 awake; sensor service stayed active, no matching new
panel/fatal/GPU entries. The display later became idle/locked: raw ALS
continued changing but GNOME released its light claim and retained old3lux.
This must not be misclassified as a stuck hardware ALS or automatic dimming.
Normal bounded session idle inhibition and wake were used for the next trial.
ScreenSaver SimulateUserActivity was absent; IdleMonitor ResetIdletime was
explicitly test-only and refused, and the GNOME power unit refused manual
restart. No test/debug mode or lifecycle/polkit restriction was bypassed.
A normal logind session-unlock signal refreshed the active-session light
claim; read raw/SensorProxy803lux after owner remotely switched lights on.

A bounded max/min/max/min battery-current comparison was inconclusive for
optical dimming: medians25.6/31.1/23.0/27.7mA while the session was locked.
Current is net battery current with charger/background load, not panel power
or a luminance measurement. Original level/policy restored. No physical
brightness success inferred from this comparison.

Added originalGPL2 offline tilt-compensated heading geometry with explicit
separate mounting matrices and quality/overflow/gravity/vertical/receive-age
gates. Four math regressions pass. Actual oldnorth capture is rejected by
default (59quality1,1missing closeaccel); diagnostic-only lowquality outputs
N15.89/E91.72/S182.09/W307.53. These are not a calibrated system backend and
are not used by the installed Compass app. New initialization's actual
cardinal/tilted heading and reference magnetic/true-north semantics remain
pending while owner is away.

Owner remotely switched the real room light ON/OFF/ON/OFF. Read-only ALS
observers captured approximately2..4lux dark and up to802lux bright. After
normal session activity, with no manual brightness writes in the final
light-change intervals, requested/actual brightness rose4→16 and fell16→3.
The last complete bright/dark phases included real571..802lux and2..4lux
with final command levels16 and3. This qualifies the real ALS→SensorProxy→
GNOME→DSIM control path in that active-session window, not optical nits or
long-term/color/flicker parity. Initially PowerSave0/unlock alone left an
old idle state; one reviewed gpio-keys software volume event reset activity
and original PulseAudio volume/mute were restored. No physical-key test
claimed, permanent idle bypass or synthetic lux injected.

For stronger hardware evidence, a temporary ordinary-user white GTK window
was confirmed focused/fullscreen, with automatic75s close. Under guarded
manual16/1/16/1, net battery-current medians were approximately-321.9/+11.2/
-317.7/-0.9mA, with max-level voltage about4.017V versus4.078V at minimum.
The repeated0.32..0.33A change with voltage sag is physical electrical-response
evidence beyond a cached brightness number, but is not calibrated panel power
or an optical luminance/color/flicker measurement. Private records retained,
original brightness/ambient policy restored, test window closed and fallback
timer cancelled after success. Source white-window helper is included.

Performed another real reboot of the same#28 BOOT after updating production
sensor pins. Sensor, audio and Bluetooth services auto-started successfully;
backlight requested/actual3 restored. GNOME ambient-enabled=true and owner
rotation-lock=true persisted. SensorProxy HasAmbientLight/HasAccelerometer
true and real4lux read. No failed system units or matching new panel/fatal/
GPU error signatures in this fresh boot window. Temporary test observers/
white window/rollback timers ended; the bounded idle inhibitor had already
expired and was not carried into the new boot. Original idle/lock policy
was not changed. RECOVERY/EFS/CPEFS/RADIO live bytes matched every corresponding
fresh pre#28 backup hash after the trials/reboot. Compass remains unimplemented
in production; its trial status3 and offline geometry must not be represented
as a working post-reboot app. Physical magnetic reference work waits for the
owner's return; no fake heading or guessed mounting matrix published.

## 2026-11-19 — Full error-priority log audit after brightness qualification

Owner asked whether all modules/sensors and the kernel log are now normal.
A fresh full err-priority audit of the current#28 boot disproves a zero-error
claim: touch probe returned-110 at5.40s, Wi-Fi P2P creation timed out/-5 at5.86s,
and SSP TX reported three0-of36byte retry failures at9.52s. Touch subsequently
bound and registered its input device at7.59s; real accel/raw and ALS566lux
were readable during this audit and sensor/audio/BT services active. These
startup errors are not being declared repaired just because services recover.
No matching BUG/WARNING/SError/Oops/GPU/panel-error entries and no failed system
units were seen, which is narrower than an error-free kernel or full hardware
parity. No device setting, module, firmware or partition was changed by this
audit. LTE/PDP/voice/SMS, full BT audio/pairing, deployed desktop GPU stability,
compass backend, camera/GPS/NFC/fingerprint/haptics and suspend parity remain
unqualified as listed in VALIDATION.

## 2026-11-19 — Touch power-on readiness candidate

Native#28 showed rail power-on at4.106s, an early I2C timeout at5.401s
and successful input registration at7.589s. The readiness gate and worker
both waited only1s. Changed both to one explicit4s power-on settle interval,
covering the observed~3.5s successful interval; off-time, voltage and bounded
probe/power-cycle budgets unchanged. This is a hardware-motivated timing
candidate, not a verified fix until new BOOT/repeated boot logs pass.
Source audit also found SSP TX can return SPI success after flow-control
retries exhausted with zero bytes acknowledged, while the worker already
advanced its ring tail. That potential silent-loss path needs a separate
ACK/queue/error review; the startup retries are not yet declared repaired.

Native#29 built from9861b49,BOOT b22c443158bba817ec087ff2161758b9ce855e4f9bbac6110ba228ff10098a1c/27219984bytes. Fresh9backup,guardedBOOTwrite/readback and nativeboot passed. First recovery-to-native boot bound touch at8.325s after rail-on4.101s without the timeout. However two subsequent warm boots both timed out around8.44s and only bound around10.63s. Thus4s is NOT a verified general fix; no success label. Sensors/audio/BT start with exact29 package/profile; SSP ACK candidate was not installed. Investigating real boot-complete IRQ readiness rather than hiding the early I2C failure with a larger guessed delay.

An opt-in strict_tx_ack source candidate now tracks positive acknowledgements, commits only those ring bytes, rejects exhausted/oversized ACKs, uses overlap-safe movement and bounded backpressure, and latches a failed stream instead of kernel replay/reset. Fault masks IRQ requeue, poll/write/read fail, and consumer readiness is invalidated without firmware reset. New exclusive LHD open is the only reset of this per-stream fault; strict close drains old work before releasing ownership. Default remains off pending bootstrap/data-contract qualification. Actual C ACK-state regression and full AArch64 module compile pass; no hardware improvement claimed. A first multi-file patch failed anchor validation and applied nothing, then corrected.

## 2026-11-19 — Real IRQ trial narrows first-touch-access failure

Added a separate opt-in bounded GPIO observation module using referenced
gpio_device/gpiod raw reads, without pin request/mux/direction writes. Native
read-only test reported idleIRQ1. Authorized exact29BOOT/backup-checked trial
armed independent60s reboot recovery, unbound touch and repeated the existing
LDO35/43 masked off2s/on sequence. Actual IRQ1→0 occurred at103ms after power
restoration, yet first manual bind~1s later returnedETIMEDOUT. Kernel then
registered touch input~160ms after that error; second manual bindEBUSY meant
it was already bound, not another failed probe. Binding verified, diagnostic
unloaded, fallback timer cancelled and sensor/audio/BT active. No fake ready
value, IRQ/pin drive, persistent voltage change or original-partition write.

An actual boot IRQ before first failure and immediate recovery following
HSI2C's normal error reset suggest controller handover state rather than a
long ASIC boot delay. Reverted failed4s experiment to original1s guard. Added
a read-only ACPM power-generation API and a scoped first-transfer HSI2C reset
after both clocks enabled, once per real touch rail cycle; only Star2 bus
104b0000/address48. Other adapters, normal error propagation, voltage and
retry budgets unchanged. This remains a hypothesis until new BOOT trials.
Added optional strict-ACK supervisor policy inferred from pinned ELF modinfo:
new-capability modules default to explicitN, preventing adoption of a loadedY
trial under a default profile; old modules remain compatible and rejectY.
Runtime18/C-ACK1 regressions pass. No strict-ACK hardware test yet.

## 2026-11-19 — Touch controller handover fixed in bounded native trials

Kernel30 built from7cdb737,BOOT cf7aa7119df88db4157ec15403e71a0483deb3952fefad58fa2f254f3fc7183d/27219984bytes. Fresh9backup,guardedBOOTwrite/readback/nativeboot passed. First native boot reset TSP bus at5.269s and registered input at5.285s without timeout. Three further warmboots all reset stale controller status000a0006→00080001 before first access and registered input at5.295/5.297/5.289s without-110. This supports the post-power HSI2C handover correction, not a longer ASIC delay. Sensor/audio/BT auto-started each time. Cold/deep-suspend/endurance and new physical-touch interaction remain separate.

New exact30 sensor profile pins supervisor policy and explicitly selects strict_tx_ack=false; native strict/fault flags N/N. Other pinned modules and real accel/ALS runtime stay qualified. No checked-ACK hardware improvement claimed yet. Added exact-BOOT private baseline rollback helper+inert90s-onboot timer/service for a separately armed strict trial: validate state/profile/unit hashes/model/kernel before action; knownNbaseline, atomicfile restore, disable one-shot timer and explicit reboot.4rollback tests pass. Builds do not install/enable this helper.

WiFiP2P source review found required DOWN/APSTA/UP/discovery-disable errors were ignored by setup and the caller. Added exact-source-pinned Star2/4361/primary-only checks with numeric step diagnostics, preserve normal UP restoration on APSTA rejection, and propagate errors before IF_ADD wait. Other boards retain old behavior, no fabricated interface or capability suppression. ActualC failure injection2tests and full AArch64p2p.o compile passed. First test logging stub discarded arguments and failedWerror; fixed stub only. This candidate is not in native30 and does not establish working P2P.

Checked-ACK unattended-trial preparation on native30: preserved root-onlyNprofile/unit snapshots with exact state/profile/unit/BOOT/kernel pins. Added read-only rollback preflight mode. An actual transient unit using the same NoNewPrivileges/PrivateTmp/closed-device policy (onlyBOOTread) passed baseline/BOOT verification without actions. Inert90s-onboot recovery units staged but not yet armed; no success of restoration claimed until a real trial.

## 2026-11-19 — Checked SSI native boot observations and real recovery

Exact kernel30 checked-ACK profile trial boot reached sensor readiness and
published621 real frames before the independent90s recovery restored the
pinned non-trial configuration and rebooted. Actual recovery journal confirms
restore, timer disable and reboot; subsequent N/N parameters, accel/ALS reads
and sensor/audio/BT services active. USB SSH address temporarily timed out;
alternate authenticated remote connection recovered access without partition
writes. Initial post-handoff journal indexing returned an earlier warm boot;
whole-journal time filtering resolved the actual recovery events. No failed
trial inference was made from that unrelated shutdown-readiness traceback.

Repeated live checked-ACK trial plus two further warm boots observed strict=Y,
fault=N, sensor readiness and actual accel/ALS reads. Each repeat armed the
exact-BOOT fallback before reboot and cancelled it only after live checks.
A single initial0-of36 ACK retry remains in these observations; unlike the
prior three exhausted retries it did not latch the strict stream fault.
This establishes bounded startup/data-feed evidence, not full packet integrity,
long-term stability, compass qualification or elimination of all SSP errors.
General default remains off; the experimental handset profile explicitly opts
in. Fallback remains disabled after successful tests. No firmware published.

Kernel31 built successfully from224a67d with the previously source-tested
required P2P setup checks. BOOT ba4e4a88de19a85cae3f49248a5a9b6adcb0d529cbd6c753cf386d6135455d00,
27219984bytes; native boot and P2P behavior are pending. Build is not boot.

## 2026-11-19 — Native31 narrows P2P failure; protected-area comparison

Full fresh9backup and guardedBOOT-only write/readback/native31 passed. Actual
#31 kernel matches packaged receipt; sensors strictY/faultN, actual accel/ALS
and audio/BT services active. Fresh31 backup manifest copied into the protected
sensor profile and unit re-pinned; ordered sensor restart/readiness passed.
Old exact30 recovery timer disabled before kernel replacement. Recovery reboot
argument syntax initially rejected by systemctl; corrected explicit reboot
argument entered TWRP. No bootloader update/relock performed.

Pre-install comparison with the earlier30backup failed the EFS equality check;
the shell continued to the guarded installer, which independently validated
all fresh31backup images and matching current EFS/CPEFS before BOOT writing.
This sequencing failure is recorded rather than presenting that comparison
as passed. EFS differed at only six bytes in block0: ext4 mount/write times,
mount count and lifetime-write accounting; no file/identity payload blocks
changed. RECOVERY/CPEFS/RADIO/DTB/DTBO/MISC identical, PARAM differed. These are
recovery-session observations, not claims that the installer wrote EFS/PARAM.
Future combined precheck/write commands must use fail-fast execution so a
failed comparison cannot fall through. No EFS restoration or identity edit.

NativeP2P stage0..4 all returned0, but IF_ADD still timed out; required-command
error propagation alone does NOT repair P2P. Native31 strictSSI had two initial
0/36 retries, then live faultN/readiness/data. No elimination-of-SSI-errors claim.
Added a scoped read-only event-mask observation after successful P2P setup:
bounded256byte buffer, validated firmware-mask length, reports only numeric
IF-subscription bit/result/length, no addresses or event payload, no replay or
subscription write. Original Broadcom notice retained. This new observation
is source-stage until another native kernel boot.

## 2026-11-19 — Native32 rules out disabled IF-event subscription

Kernel32 built fromf6bef1e, #32 SMP PREEMPT Thu Nov19 05:38:06 UTC2026;
BOOT419c260c3d09f5b3f3732228919098113f50985cf655fe206e100b64cd7adfc0,
27219984bytes. Fresh9backup passed, fail-fast precomparison verified
RECOVERY/CPEFS/RADIO unchanged and all EFS byte changes confined to the known
ext4 recovery mount-accounting fields; guardedBOOTwrite/readback passed.
Native boot reached sensors/audio/BT active, strictY/faultN, actual accel/ALS.
TSP first-access reset5.269s without-110. Read-only P2P event-mask observation
returned0 with length27 and actual IFbit1; all setup0..4 returned0, yet IF_ADD
still timed out6.053s. Thus a disabled IF subscription is not supported as the
cause. No subscription write, fake event, forced-success interface or firmware
replacement. No initial SSI retry in this one32 observation; this does not
invalidate31's two retries or prove all-mode/long-run integrity.

Pinned Lineage101_16 discovery logic uses real p2p_dev query/index with control
interface index0 rather than IF_ADD completion. A future compatibility path
must qualify actual firmware BSS context and preserve primary-interface
mapping/flow cleanup; merely treating timeout as success is not acceptable.
No such path is enabled by this diagnostic patch. Actual32 fresh backup/profile
pins staged before the next native reboot; no modem service enabled.

Native32 further warm reboot passed: post-powerTSP reset5.269s with old
status000a0006→00080001 and no initial-110; sensor/audio/BT auto-start active,
strictY/faultN, three live accel/ALS samples, failedsystemunits0. One initialSSI
retry returned on this reboot, so the earlier no-retry boot is not generalized.
P2P again readback IFbit1/len27/ret0 and timed out. Timer remains disabled;
latest32 fresh backup/profile pins active. No pending diagnostic reboot timer,
firmware publication or uncommitted device driver source left by this trial.

## 2026-11-19 — Native ambient switch and smoother-brightness candidate

Owner requested continued P2P/kernel work plus Ubuntu's native automatic-
brightness switch, then requested less abrupt transitions. On native32,
SensorProxy HasAmbientLight=true with actuallux. Stock Control Center46.7
Power panel contains a visible/checked Automatic Screen Brightness checkbox.
Actual accessibility toggle changed ambient-enabled true→false→true; finalon.
Remote initial launch lacked XDG_CURRENT_DESKTOP and exited with an explicit
GNOME-session requirement; setting the launch-only actual GNOME/Wayland
session environment opened the stock panel. No panel fork or duplicate daemon.

Candidate output smoothing retains native GNOME/sensor values: expand16 coarse
AOR levels to401 unique stock PAC512 duty values, ordered monotonically for
fixed inherited gamma. First attempt to use original PAC256 order was rejected
because gamma-boundary duty reversals would be inappropriate without gamma
updates. No interpolated duty/voltage/gamma/HBM or fabricated lux. Delayed work
advances at most4 levels per40ms (~4s full traversal), retargets latest request,
stops on transport failure, keeps actual readback distinct from target.
Zero/DPMS off bypasses ramp; DPMS/device cleanup drains work, wake restores
current target directly. ActualC transaction/ramp policy and worker sleep/
retarget/error tests pass. New panel behavior is not yet hardware-qualified.

P2P next bounded observation queries real p2p_dev only on the scoped discovery
IF_ADD timeout, logging numeric return/BSS index. First unscoped transform
anchor matched multiple timeout blocks and refused without kernel-tree writes;
restricted the exact create_p2pdev function before replacement. No forced
success or compatibility fallback. SPI transport adds the BCM4773 ID matching
its existing OF compatible (SPI core expects vendor-stripped modalias), keeping
existing ssp-spi binding. Warning disappearance and sensor data require native
boot proof. CPU heterogeneity, GPT and unqualified RGB/haptic warnings are not
being hidden or declared repaired by these changes.

Brightness recovery helper now accepts only the exact saved16or401 range and
waits up to6s for completed maximum output. WrongBOOT/range refusal and old/new
recovery tests pass. No timer is automatically created by the helper or build.
No native401 deployment yet; build underway fromba712c2 kernel inputs.

First full smoothing kernel compile failed because the helper parameter name
current expands to Linux's current-task macro (hostC lacks that macro).
Renamed it applied; no failed-build artifact was installed. Kernel compilation
remains a required check in addition to the standalone algorithm tests.

## 2026-11-19 — Native33 smoother output and owner confirmation

Full rebuilt kernel33 from023b225 (kernel #33 SMP PREEMPT Thu Nov19
05:55:12 UTC2026), BOOT7edad38474ad5c967791639944dcb61111d9bace3dac2af260a6f261dabde5ba/
27219984bytes passed fresh9backup, fail-fast protected payload comparison,
guardedBOOT-only write/readback and native boot. Sensors/audio/BT active;
strictY/faultN, actual accel/ALS. Fresh33 backup/profile pins installed and
ordered sensor restart passed. Existing SPI OF/ID warning absent while actual
sensor data still works, qualifying the BCM4773 alias correction for this boot.

Actual401-level output 401→1 and1→401 took4.947/4.951s with100 observed
changes, each at most4levels and strictly toward target.401→57 took4.247s/86
changes. Owner then physically tested ambient changes and answered that the
result was sufficiently smooth. GNOME native ambient switch stays on. Previous
16-level raw reference is near new57 (stock AOR0a90); standard reference14%
was selected after range migration, preserving approximately the earlier duty.
No optical nits/color/flicker or fullSamsung gamma parity claim.

First manual ramp assertion failed before trace persistence; independent
maximum-output recovery completed and left ambient off as explicitly intended,
then the controlled90s trial obtained the traces above and restored ambienton.
Early DPMS probes also assumed accepted D-Bus policy changes had already settled
and exact raw-request retention; those assertions were not driver-failure proof.
Normal GNOME brightness25/75/14% trials subsequently confirmed actual0 asleep
and target103/302/60 restored within0.169/0.154/0.179s of wake. Explicit zero and
57 restore passed; sensors remained active. Trial timers/inhibitors stopped.
Requested and applied values were checked separately, not forced equal during
transitions. No sensor samples were fabricated or filtered for these tests.

Native33 P2P timeout diagnostic returned real p2p_dev BSS2 withret0, despite
noIF_ADD. This is hardware evidence of the firmware discovery context, not
working peer discovery/group traffic. A scoped opt-in control-context candidate
is being prepared with failure/lifecycle tests; it is not in native33.

## 2026-11-19 — Opt-in firmware-backed discovery control candidate

Native33's real BSS2 and pinned Lineage101_16 ifidx0 protocol justify a separate
control-only path instead of inventing IF_ADD. New root-only opt-in parameter
is defaultfalse. Strict gates require Star2/4361, MSGBUF, legacy-netdev option
off, no protocol del_if data lifecycle, intact primary slot/mapping. Validate
real p2p_dev query/range/free slot before allocating an existing non-netdev
context with control ifidx0; no primary route/flow mapping changes. Create
failure disables only the discovery just enabled and preserves original error.
Delete cancels ROC, checks SCAN/discovery-disable results, then uses existing
host cleanup without waiting for a nonexistent IF_DEL. Cleanup recognition
does not depend on the mutable opt-in. Duplicate non-netdev IF_ADD refuses
before the original null-netdev dereference. No fake firmware event, success
on a failed query or arbitrary BSS index.

ActualC tests cover query/enable/allocation/cleanup failures, invalid indices,
occupied slots, protocol/primary/data-lifecycle refusal and intact mapping;
whole-source pin/idempotence/notice tests pass. First unbounded deletion anchor
also matched detach and refused; restricted exact delete function. A transient
same-second Python bytecode cache held the old calculated hash; invalidated
only local generated caches and re-ran tests against actual new source hashes.
All-source validation precedes writes. Generated C additions explicitly permit
ISC or GPL-2.0-only; original Broadcom ISC notices remain. Build option
S9_EXPERIMENTAL_P2P_CONTROL=1 only adds the explicit kernel opt-in; defaultoff.
No native control-path success claimed. First kernel trial will keep opt-in off
until independently guarded runtime testing; full P2P RF/group traffic remains
unqualified even if context creation succeeds.

## 2026-11-19 — Native34 baseline and bounded control trial preparation

Full kernel34 from44d48b9, #34 SMP PREEMPT Thu Nov19 06:16:17 UTC2026,
BOOTd77b39664d0c4069fd0b0e55a16c05b0986c2ec7b9d5055ad4e7de22d9bae593/
27219984bytes passed fresh9backup, fail-fast protected payload comparison,
guardedBOOT-only write/readback/nativeboot. Control opt-in=N as intended;
sensors/audio/BT active, real accel/ALS, touch reset5.269s/no initial-110.
Real P2P query again BSS2. No control-path success yet; default-off trial build
continues to expose the old event timeout until explicitly selected.

Added a root/model/exact-BOOT/kernel/private-receipt+backup-pin trial helper:
refuses existing P2P ownership, arms its own90s reboot fallback only after
prechecks and successful Wi-Fi HTTPS, switches runtime opt-in only, creates/
starts/optionally scans/stops/deletes only its test-owned wdev, checks primary
identity and post-delete HTTPS. Cleanup resets runtime opt-in; failure leaves
fallback armed, never guesses ownership; private0600 logs remain excluded.
No partition/firmware writes. Inventory/guard host tests2passed; iw on native34
contains required __p2pdev syntax. Actual trial is still pending.

## 2026-11-19 — First control trial: real lifecycle, malformed scan, recovery

Native34 runtime opt-in trial created the real BSS2 control context, started
it, then stopped/deleted it successfully in failure cleanup. One-channel scan
returnedENOENT: the diagnostic request omitted the P2P Listen Channel IE;
primary cfg80211_get_p2p_attr in the actual scan-prep path requires it. This
failed request is not working RF discovery. Trial helper now supplies the
standard global-class81/channel1 Listen Channel attribute, within cfg80211's
normal regulatory checks; it does not alter regdomain or invent sensor data.

Remote SSH was unavailable during the failed trial/recovery window. Actual
90s independent reboot recovery ran; native34 baselineN returned with all
sensor/audio/BT services, failedsystemunits0, ambienttrue and bound-WiFi HTTPS204.
USB SSH became usable again and is now preferred for radio tests. Records show
create/start/stop/delete returned0, scan-2; no peer/group/data-parity claim.

Source review found the legacy branch still called upstream primary DOWN/
APSTA/UP setup before creating its context, which can disrupt a live STA.
New prepare step reads actual APSTA; configured1 uses only discovery/address
commands and never resets primary. If APSTA needs initial setup, CONNECTED or
CONNECTING SME state refusesEBUSY; only an idle initial primary can use the
original setup. Gate/query failures propagate. ActualC connected/configured,
connected/unconfigured, connecting and idle setup-failure tests pass, as do
exact previously-built-source migration and source-integrity tests. This is a
candidate mitigation until real primary data survives the new trial.

## 2026-11-19 — Native35 scan/lifecycle and preserved STA data verified

Kernel35 from3c24446, #35 SMP PREEMPT Thu Nov19 06:32:10 UTC2026,
BOOT1b982dbe1107d7103c759a846e02ced71a9f4a502fba88f29538bd18b7162e23/
27219984bytes passed fullbuild/fresh9backup/protected comparison/BOOTwrite/
readback/nativeboot. Baseline opt-inN, sensor/audio/BT active, real ALS/accel
and bound-WiFi HTTPS204. Fresh35 backup/profile pins installed with ordered
sensor restart. New trial helper protected under kernel35-tools and hash
checked against the actual public source before root execution.

Runtime opt-in trial performed TWO complete test-owned create→start→single-
channel DIRECT- scan→stop→delete cycles successfully. Both scans completed;
both post-delete primary ifindex/address remained unchanged and bound-WiFi
HTTPS returned204. Correct Listen Channel IE supplied. Runtime opt-in restoredN,
no test-owned device or recovery timer left; success summary confirmed from
private log and systemd completion. This qualifies bounded firmware-backed
context lifecycle/scanning plus preserved primary data for the APSTA-aware
preparation change. It is not peer discovery, GO/client negotiation or actual
peer-data proof. A persistent opt-in build/reboot qualification is next.
Owner has opened Fold7 Wi-Fi Direct for a separate real-peer test.

## 2026-11-19 — Native36 persistent P2P and real bidirectional peer discovery

Kernel36 from42484ba built with S9_EXPERIMENTAL_P2P_CONTROL=1, #36 SMP PREEMPT
Thu Nov19 06:38:38 UTC2026, BOOT5937715b3728efe6453e1995b274f680db726077c91b853f1b4d521d58426ab5/
27219984bytes. Fresh9backup/fail-fast protected comparison/guardedBOOTwrite/
readback/nativeboot passed. Runtime parameterY, one native P2P device created
at4.476s using realBSS2/ifidx0; old IF_ADD timeout absent and primary Wi-Fi
HTTPS204. Fresh36 protected sensor receipt/module/backup/profile pins staged;
ordered sensor restart/data passed. Audio/BT active, native ambienttrue and
401-level brightness retained.

Added bounded NetworkManager peer observer with exact model/BOOT/kernel and
private input pins. Its optional read-only guard mode permits an already-on
production path; actual mutation trial still defaults to refusingY (regression
covered). First Find call used uint32 timeout and was rejected by the native
API requiring int32; corrected request only, without any driver change. The
15s native NetworkManager Find then found TWO new peers with a Fold7-name match,
no API error; StopFind cleanup executed. Owner independently saw the S9 peer on
Fold7 and supplied an address; private comparison matched the actual S9 P2P
address. No addresses, peer names or raw IE/logs are published. This establishes
real bidirectional discovery, not pairing/group negotiation/file or IP traffic
between peers. Existing primary Wi-Fi traffic was separately verified.

Further warm boot preserved runtimeY/oneP2Pdevice, no IF_ADD timeout, TSP reset
5.274s/no-110, real ALS/accel, audio/BT services, ambienttrue and requested/applied
brightness56of401. Bound-WiFi HTTPS204 and failedsystemunits0; full unfiltered
error-priority kernel log had0lines in both observed36boots. This is bounded
boot evidence, not error-free hardware/full Lineage parity. Warning audit still
finds CPU feature differences, RGB/haptic missingDT, alternateGPT, hub reset
uncertainty and unsupported BT transmit-power command; see KERNEL_WARNINGS.

Read-only GPT header/table CRC audit: sda primary header+entries valid, alternate
header invalid despite an in-range finalLBA; sdd primary+alternate headers valid.
Logical sectors4096bytes. No GUIDs/partition data were printed/published and no
GPT sector was modified. This remaining metadata warning is not repaired by
hiding it or by an unreviewed table rewrite.

Final post-warm readback confirms checkedSSI strictY/faultN and no remaining
trial/recovery timers or idle-test units. A native Power Settings launch was
requested; its process had ended before the later accessibility snapshot, so
no additional36 UI-presence result is inferred. The earlier actual native
checkbox off/on test and owner-confirmed smoothing remain the UI evidence;
latest36 ambient setting istrue with requested/applied56of401. No debug/log
mask, forced feature-ID change or GPT rewrite was used to obtain the result.

## 2026-11-19 — Korean touch-input investigation and current modem readiness

Owner reports Hangul source selection still produces Latin text. Installed
Noble ibus/ibus-hangul/im-config/GTK3/GTK4 integration and set native sources
US + IBus Hangul, initial Hangul mode and disable-latin-mode. Restarted IBus and
performed one normal kernel36 Ubuntu reboot; USB SSH returned. Merely selecting
the engine did not fix input. Native IBus input-context comparison on the actual
phone reproduces physical keycodes: six handled keys, commit `가나다`; virtual
keycode0: zero handled keys, empty commit. GNOME46 handleVirtualKey supplies0;
Ubuntu ibus-hangul1.5.5 unconditionally remaps it through the hardware keymap.
Candidate preserves the supplied keysym only for0, retaining physical layout
normalization. Pinned upstream/Ubuntu source and patch-only build recipe added;
image build integrates the same local package. Device build/after-fix input and
owner touch test are still pending at this checkpoint. No input success claimed.

Read-only PMU readiness audit, gated by exact G965N/current BOOT, observes reset
sequencer0x504=0 and central sequence0x284=0. No secure control reads, register
writes, SMC, CP reset, modem module load or original NV mount performed. The
newly inserted SIM has not yet been recognized in this boot; prior registration
is historical evidence only. Cold bring-up/PDP remains unqualified.

Two bounded native peer searches completed without API error. Each saw one
peer, but neither supplied an unambiguous Fold7 identity. No arbitrary peer was
paired. Fold7 test-owned ADB UI/dump directory prepared; connection, IP traffic
and file transfer remain pending. Peer names/addresses and raw dumps stay private.

## 2026-11-19 — Korean touch input and real Fold7 P2P transfer verified

Native ARM64 build of1.5.5-2build2+g965n1 succeeded from pinned Ubuntu archives;
upstream engine test1/1 passed, separate desktop integration test skipped by
its own environment check. Package SHA256
b673c0837ed163c7219009d05286298b1d5e706e94d8fe0247ade1f209442f37.
Installed and restarted the user's standard GNOME IBus unit. The same input
comparison now handles six keys and commits `가나다` for BOTH physical codes
and virtual0. Owner confirms actual Korean touchscreen text entry works.
Fresh complete image build and another-login persistence are not inferred.
No extracted/vendor binary or user text/log is published.

Owner reopened Fold7 Wi-Fi Direct. A third guarded15s native search found two
peers with a unique Fold7 match. Exact model/currentBOOT/protected-backup guard
passed; created one explicitly non-autoconnecting, unsaved PBC test profile,
IPv4 auto/never-default and IPv6 disabled. A bounded cleanup timer protected the
trial. Fold7 presented the expected immediate connection request and the test
accepted it. Native NetworkManager activation succeeded and a real
p2p-wlp1s0-0 obtained a dedicated IPv4 address. No primary route was replaced.

Served a deterministic1048576-byte file only on the P2P address. Fold7 curl
explicitly bound its P2P source address and downloaded it; SHA256 matched.
Reverse Fold7 netcat transfer also explicitly bound that source; the S9 receiver
checked the incoming peer and exact1048576 bytes/hash, all passed. This is real
bidirectional peer data, not discovery or traffic over the preexisting LAN.
Bound primary Wi-Fi HTTPS204 and zero failed system units during the group.
Stopped owned test servers/timers and down/deleted only the owned volatile
profile; P2P device disconnected, primary Wi-Fi/USB remained connected, subsequent
bound primary HTTPS204 passed. An initial combined stop returned nonzero because
a completed transient server unit had already unloaded; cleanup was rerun with
unit-existence checks and verified, without deleting unowned state.

Full unfiltered current-boot kernel error stream contains four lines: SSP first
write0/36 retry1, two action-frame retry5 failures before pairing acceptance,
and chanspec query-52. No IF_ADD timeout, firmware trap, call trace or SError in
the bounded transfer window. Transfer success does not erase these errors;
remaining transport/query failures need causal review and repeat qualification.
No CP module load/reset/security request, partition write or bootloader change
was performed in this phase.

## 2026-11-19 — Modem probe exposes legacy interrupt-type warnings

Reverified all nine recovery backup files locally; exact running G965N/BOOT,
module and firmware-overlay hash guards passed, no modem clients or original
EFS/CPEFS/RADIO mounts. Loaded the matching kernel36 modem module once with
explicit enable_g965n=1. Nine modem misc channels registered; CP reset and central
sequencer status both stayed0. No CBD/RIL/security request or SIM/PDP claim.
Sensors and standard IBus remained active, failed units0.

The probe exposed six irq-gic WARNs (plus their call traces): legacy DT interrupt
flags are NONE for CP mailbox/fail/watchdog. Mainline explicitly warns for NONE.
Read-only GICD_ICFGR audit using the live controller base0x10101000 verifies bit1
clear (level) for hardware IRQ101/106/472; the displayed /proc interrupt label
alone is misleading when the descriptor has no specified sense. Adapted only
those exact stock SPIs to explicit LEVEL_HIGH; no IRQ identity, polarity, register
range or other hardware property changed. Strict stock verifier accepts only
this exact0→4 migration and rejects arbitrary IRQ/flag changes; two host tests
passed. New source-built overlay compares successfully with all three original
stock BOOT subtrees after the explicit revision/interrupt migrations. Native
updated-overlay reload/boot warning result is still pending at this checkpoint.
The modem driver has no complete removal path; no unsafe hot unload is used.

Updated overlay SHA256
08d7aff3095c694ef6b26e19e018aa1560aad8c8c895c4b7dcc1a24456fd3cd8
staged with exact old/new hashes and current model/BOOT guards; previous overlay
preserved root-private. Normal reboot completed on the same kernel36; USB and
Tailscale SSH returned. The previous loaded driver shutdown retains its checked
CP-off/reset sequence even when already offline; no security authentication or
CBD/RIL was requested. No hot unload or BOOT/partition write used. Audio/sensor
and IBus services active after reboot, primary Wi-Fi connected. Full pre-probe
kernel error stream has one line, separately retained for remaining review.

Loaded exactly the previous matching module with only the reviewed new overlay,
following repeated model/BOOT/artifact/no-client guards. Nine misc channels
registered; invalid-type and gic_irq_domain_translate warning counts both0.
All three original hardware IRQs now display Level in /proc/interrupts; before
this change they misleadingly displayed Edge while GIC configuration was level.
This qualifies native interrupt-description/probe warning correction. Actual
IRQ delivery from an active CP, SIM, LTE/PDP/voice and modem endurance remain
unverified; the modem is not autostarted or powered by this qualification.

Post-reboot IBus virtual-keycode0 comparison again commits `가나다`; standard
user IBus service auto-started, so login persistence is now observed. The complete
new boot's sole pre-modem error was the same SSP initial0/36 retry1; subsequent
vendor modem probe emits additional error-priority progress/config messages
(including absent optional reset GPIO, ECT tables and packet logger). Those raw
messages are preserved privately rather than suppressed. The six IRQ translation
WARNs are absent; CP sequencer/central remain0. No new SIM/data proof inferred.
Fold7 test-owned received file and UI dump removed after transfer qualification.

## 2026-11-19 — Continued LTE/runtime and residual error qualification

Owner requested continuing through remaining LTE/sensor/Wi-Fi/kernel issues.
Refreshed native kernel36 state: modem opt-in module remains loaded, sensor
service active, failed units0. Uploaded pinned reviewed public runtime/test
sources into a new private lab; no vendor daemon started. Read-only private
runtime preflight refuses stale original-partition provenance ("Incomplete
backup provenance receipt"); modem-specific private bindings are absent in the
currently sensor-only runtime. Preserved existing NV/receipts/archives; no guard
bypass, restaging, original mount or CP security call. Comparing verified backup
metadata to identify the exact provenance drift before any modem trial.

Provenance drift comparison found exactly the four approved EFS primary ext4
fields changed: timestamps +39047/+39048s, mount count+16, lifetime write+64KiB;
zero differing bytes outside those fields. The ordinary max4 one-hop policy
correctly refuses this accumulated history. Located and reverified complete
nine-partition archived backups at mount counts19→23→27→31→35. Added explicit
ordered-checkpoint maintenance: every hop retains original max4 and byte-level
restrictions, same bootloader/CPEFS/RADIO, with total time/write budgets unchanged.
It cannot accept an arbitrary drift or silently replace NV. Forty runtime tests
pass, including large-hop, intermediate data corruption, incomplete/checksum/
wrong-handset manifests and cumulative-time rejection. Device execution pending.

First maintenance attempt stopped because sensor shutdown intentionally tears
its private runtime down; sensor service was restarted in finally. Corrected
the procedure to prepare a modem-only runtime while holding the exclusive lease,
then perform maintenance/resume. Actual checkpoint proof and preservation checks
passed; no original bytes changed, old receipt archived and private copies reused.

A10s bounded own-vendor CBD trial on native36 then completed cold CP init:
mode2 returned11 (stock conditional RE_INIT status), mode0 authentication0,
CP sequencer5, IOCTL_MODEM_STATUS4/ONLINE, mailbox interrupt count308 with
CP fail/watchdog0 and SError0. This is a real cold-boot/secure firmware result,
not SIM or PDP proof. Test unit stopped and its cgroup/clients ended; modem-only
runtime cleaned, sensor runtime restarted successfully. The tracing helper reused
its legacy fixed filename, so the new trace was preserved separately and the
helper is being changed to allocate a new private exclusive file per trial.
No raw trace/identifiers are published. Online CP remains available for a
separate status-checked RIL attachment without another CBD/reset cycle.

Online-only RIL attachment added: parent and child both read MODEM_STATUS and
require exactly ONLINE4 before transmitting; no CBD start/reset on this path.
The existing private-NV lease, model/provenance/payload checks and closed device
policy remain. A first remote wrapper had a quoting SyntaxError before its
finally block could run; sensor service was immediately restarted, the embedded
payload compiled locally before another device change, then retried once.
No vendor/CP command ran in the failed wrapper.

Actual online-only child attached without CBD, SIM status0 then130 observed;
AT readiness and CFUN1 acknowledged, attach/profile requests sent once with the
KT LTE APN from KT's published settings. Initial CEREG0 is not registered; the
bounded registration/PDP observation is still running. No IP or internet claim.

The90s online-only trial completed with SIM0/130, RFS9 private-copy replies,
three profile ACKs0x8000 and no AT timeout. CEREG progressed0→2 and stayed
searching across eight later polls; no PDP plan/activation/candidate IP issued.
The client ended, private runtime teardown and sensor restart passed. Added an
explicit online observe-only mode that omits radio configuration/PDP and queries
CSQ/CFUN/COPS/CGATT/CGREG/CREG. A separate120s status-only observation is running;
no repeated CBD, reset or CFUN transition in that observation. Unique private
trace-file allocation also passed actual native creation/0600/distinct-name
checks; only its two empty test files removed, prior evidence preserved.

Status-only observation passed its120s bound and restored sensors. SIM READY,
signal CSQ11, functionality query0, packet attach0, CEREG2 and CS/PS registration3
were observed, without AT timeout. Status getters alone do not establish service.
Own stock IpcProtocol41 radio-power builder audit independently identifies
command0107, EXEC kind1, two-byte normal0202; its alternate second byte applies
to ATT/AIO/TFA property handling, not this KT trial. Corrected the bring-up to
use that exact KT normal packet after existing explicit profile/AT readiness
checks; removed automatic AT CFUN4/1 toggling. Primary Lineage pwr.h independently
agrees on normal0202, but the own-vendor builder establishes the S9 packet kind.
Corrected its reference repository name to android_external_libsamsung-ipc.
No binary/disassembly is published; only protocol facts/original implementation.

Native radio3 online-only trial proves phone-state GET1 (low power), then the
new EXEC yields phone-state2 (normal). No new CBD/CP reset. CEREG nevertheless
remains searching across the120s observation, with no PDP activation/candidate.
Thus the functionality transition is corrected, while registration/data are not
claimed. Further native network-mode/service-domain/status mapping is being
audited; do not infer S9 layouts solely from the older protocol reference.

Read-only native network getters confirmed preferred mode11, service domain1,
selection2 and phone normal2; native data-registration GET returned ACT4/domain3/
state1, consistent with no confirmed packet registration. AT still reports
searching/unattached; CEER provides no cause. A separate private home-network
query confirms450/08 (KT). Its entire subscriber-response stream is redacted
before journaling; only MCC/MNC retained, with no14–16-digit identity in the
observed journal. Actual SIM subscription activity still needs confirmation;
owner queried asynchronously while development continues.

Own stock radio/network audit found an omitted PS-attach transaction: native
IpcTxPsAttach uses SET0d03 with attach010000. Initial LTE profile IPv4 is type5
(and roaming type5) in its194-byte message, distinct from PDP-definition type2;
previous bring-up used2 for both profile fields. Added independent source
encoders, once-only PS attach after normal phone-state and explicit profile
configuration, and PS ACK requirement before the existing single PDP activation.
No detach/reset/retry loop. Conservative100-character S9 APN bound prevents
slice expansion past its fixed field. Five radio/field/privacy tests and14 PDP
plan tests pass; actual attach6 trial pending. No binary/disassembly published.

Attach6 native trial accepted updated profile, mode/domain and PS attach, but
registration changed to CEREG0 and no PDP plan was issued. The next select7 trial
also sent one independently checked native automatic-selection SET; firmware
returned raw generic result100 for0802, while0107 EXEC returned0x8005 with phone
already normal2. Profile080a/0d14/0808 and PS0d03 SETs returned0x8000. Registration
remained absent. These are unsuccessful registration trials, not LTE fixes.
GET/SET ACK kinds are now logged/checked explicitly to avoid a GET satisfying a
SET prerequisite. No automatic radio/selection/CP retry added.

The next trial was started before the prior sensor restart job had completed;
its stop canceled that restart, leaving a failed/canceled sensor job. Modem trial
leases prevented simultaneous modem runtimes. Select7 subsequently ended, its
private runtime was removed and sensor restart completed; current sensor active,
checked SSI faultN and CP read-only ONLINE4. Future trials must await the entire
previous wrapper/cleanup completion, not just client exit. No data/partition loss.
Owner confirms current KT SIM recently had working LTE in a phone; continue
port-side investigation rather than assuming inactive subscription.

Previous-boot journal correlation pinpoints the remaining chanspec-52 at owned
P2P connection deactivation/deletion, after successful bidirectional payloads.
Prepared a narrowly scoped BCM4361/star2/MSGBUF channel-state predicate: idle P2P
client/GO returns ENODATA before querying a nonexistent current firmware channel;
active P2P/primary/other chips remain on original error-propagating path. Original
log severity is unchanged. Actual injected-C scope/state test and five existing
Wi-Fi diagnostic tests pass. Kernel build/reboot/group teardown proof pending.

Prepared shutdown/status safety corrections before the next build: only stable
CP sequencer0/off and5/initialised qualify; other states returnEAGAIN instead of
being treated as off. Shutdown skips secure reset only for matching offline+
zero status, preserves any prior failure latch, and rejects a contradictory
online/zero state. The top-level callback now reports a failed shutdown rather
than unconditionally overwriting the software state as offline. Actual-C tests
cover all raw sequencer values plus24 existing/new power/security scenarios.
These source changes are build/device pending, not shutdown hardware proof.

The first next-kernel invocation selected the older initial-build cache volume
instead of the established reproducible volume. It was compiling against the
correct pinned Linux base/source but would use a separate obsolete build counter
and require a full rebuild. Stopped only that owned build container before an
image/deployment. The canonical volume is s9-g965n-repro-build (verified UTS36 and
counter36); restarting there preserves consistent next-build identity. No device
write/flash was part of either build command.

Added optional bounded root-private RFS OPEN/CLOSE capture for a future cold
initialization comparison. It never captures NV read/write payloads and does not
resolve/allow requested filenames. Existing files/symlinks and nonprivate parents
are refused, limits128records/64KiB each/1MiB total, each record fsynced. Two host
file/security tests and eight runtime preflight tests pass; native capture and
requested-file necessity remain pending. This can distinguish an omitted vendor
file dependency without granting a general filesystem namespace.

Canonical build completed native37 (#37 SMP PREEMPT Thu Nov19 08:48:18 UTC2026),
source0ba8889, BOOT3f060b3ae6a55b2e00d2d07d44afe092368730ed114799b163596addc16a7621/
27219984bytes. Five matching modules/overlay frozen and uploaded privately;
stock overlay comparison passed all three subtrees. Build is not a boot result.
Owner confirms the intervening native36 reboot was intentional; no spontaneous
reboot inferred. That reboot correctly left modem opt-in module unloaded, so
identity8 online-only preflight refused missing modem channels without trying
to start/reset a CP. Sensor runtime cleanup/restart passed; no identity result.

Preparing recovery/fresh backup. This systemctl does not accept a positional
reboot target ("Too many arguments", no reboot). Inspected actual login1 API:
SetRebootParameter is supported. Using its recovery parameter + normal login1
Reboot for orderly shutdown and the board's volatile syscon reboot-mode, rather
than direct forced reboot or a MISC/bootloader write.

Fresh nine-partition recovery backup37 completed. An initial strict preinstall
comparison stopped before writing because PARAM differed. Byte-level review
identifies only six appended N/R timestamp reboot-history records in its existing
log region; every byte outside that append is identical. This is not an arbitrary
PARAM relaxation or a PARAM write. DTB/DTBO/CPEFS/RADIO/MISC/RECOVERY unchanged;
EFS accepts the bounded four-field metadata proof. All nine backup files and
rollback native36 BOOT prefix/new37 image hashes reverified before installation.

Native37 BOOT-only write/readback and actual USB SSH boot passed. Preserved old
sensor profile/pins and all three startup units root-private, staged exactly
pinned package37/fresh nine-backup metadata, changed only receipt/BOOT/module
profile fields and the matching unit pin. Qualified orientation, vendor/program
pins and user settings retained. Audio/Bluetooth/sensor startup services active,
matching four modules loaded, BOOT/profile hash readback passed. Three actual
IIO accel samples vary; ALS400lux, checked SSI faultN. Bound primary Wi-FiHTTPS204,
failed units0 and full unfiltered error-priority kernel stream0 at this initial
post-stage observation. No chanspec/IF_ADD/CallTrace/SError/GPUfault in this bounded
baseline. P2P group teardown and new modem module/cold path still need separate
hardware tests; no whole-device or LTE success inferred from a clean baseline.

Native37 owner-assisted Fold7 peer discovery and group connection passed.
Both source-bound 1MiB transfers matched the deterministic source SHA256;
reverse receiver verified the expected peer. An explicit active-group current
channel query succeeded. Primary STA HTTPS204 remained available during and
after transfer. Owned group/profile/services were removed; post-teardown
chanspec errors0. One action-frame retry batch remains in the full kernel log,
so this is bounded channel-state fix evidence, not an error-free Wi-Fi claim.
A second attempt using the old cached peer failed with peer-not-found and no
group. Removed only its owned volatile profile/timer, then repeated bounded
fresh discovery: unique Fold7 name match found. Fresh-peer repeat pending.

Fresh-discovery repeat37 completed: second dedicated group, explicit active
channel query and both source-bound 1MiB transfers passed with exact hashes.
The reverse helper initially used a nonexistent filename (operator error, no
receiver started); corrected to an exclusive private helper, then verified
1048576bytes/expected source/hash. Preserved that failed unit evidence before
clearing only its failed state. Removed owned services/profile and Fold7 test
files. Full boot log still has action-frame retry batch1, chanspec0, IF_ADD
timeout0; no additional AF error on this repeat. STA HTTPS204, failed units0.

Preparing native37 one bounded cold RIL-before-CBD initialization with private
OPEN/CLOSE capture. Reverified all nine fresh backup hashes and exact old EFS,
current source uploads and wrapper syntax. Exact model/BOOT/module/overlay
guards, exclusive runtime ownership, ordinary four-field EFS maintenance and
working-NV preservation remain required. Only the reviewed opt-in module is
loaded; no module unload or forced CP reset loop. Sensor-only runtime will be
stopped during this incompatible vendor runtime and restored after cleanup.
This preparation does not establish modem startup or network registration.

Native37 guarded opt-in modem load and ordinary EFS metadata revalidation
passed with private working NV/RADIO preserved. One cold RIL-before-CBD trial
completed; root-private bounded RFS capture contains five OPENs/two CLOSEs,
only known optional audio/learned-frequency/diagnostic filenames, consistent
with upstream's documented denied-open behavior. No arbitrary file access
was added. SIM READY/init/phonebook-complete and AT CPIN READY observed;
network450/08, CSQ18, CEREG0,2/search, CGATT0. Phone state2; profile/mode/domain
ACK8000, redundant radio/PS attach returned8005. No registration/PDP/internet
claim. Subscriber digits absent from journal. Invalid IRQ type/GIC translation
WARNs0, SError0, CallTrace0. Own clients stopped, runtime cleaned, all three
audio/BT/sensor services active again.

Found an actual status bookkeeping defect in that trace: SIM phonebook
completion0x83 cleared readiness after READY/init. Lineage sec.h identifies
it as PB_INIT_COMPLETE, not removal/error. Preserve an existing ready state
for that notification only; it cannot grant readiness on its own, and all
lock/removal/error/unknown states remain fail-closed. Eight radio/privacy/state
tests pass. Runtime deployment/live status validation pending; this fix is not
a demonstrated cause or solution of LTE registration failure.

Deployed current lab source for a bounded existing-online observe-only trial
(no CBD/reset/radio configuration). On-device replay of all11 captured cold
SIM statuses now ends ready after phonebook completion, where the previous
assignment cleared it. This is replay evidence, not a fresh live0x83 event or
LTE data proof. A specifically prefixed +CGSN response candidate passed
synthetic tests but did not resolve the native unknown result; removed that
unsubstantiated parser expansion. No invalid-device conclusion is drawn.
Observed startup-unit cache warning left by kernel37 manual profile staging;
reloaded systemd unit definitions and verified NeedDaemonReload=no. No unit
content or driver was changed merely to hide the warning.

Existing-online observe-only60s completed without a CBD/reset request; EPS
still searching and packet attach0. No subscriber digits leaked. Runtime
cleanup finished and all three driver services active. Reviewed the Bluetooth
transmit-power warning against the actual kernel: it is hci_broken_table's
announcement of the deliberately set BROKEN_READ_TRANSMIT_POWER quirk, and
hci_le_read_tx_power_sync skips the unsupported operation when that bit is set.
The existing board-scoped patch already implements this safeguard. Retain the
notice; no log suppression or speculative Bluetooth capability claim.

Preparing native37 existing-online read-only30s trial to classify unknown
CGSN response shape. New diagnostic emits only fixed booleans and up to eight
numeric-field lengths, never digits/hash/raw reply; existing fragment redaction
is retained. Nine radio/privacy/state tests and eight runtime preflight tests
pass. Exact protected BOOT/model/fresh-backup guard precedes sensor stop and
exclusive runtime preparation. No CBD/reset or radio configuration requested.

Native37 shape3 observe-only trial completed and fully restored sensors.
Unknown CGSN reply has exactly one15-digit field, no terminal error, no CGSN
prefix or quoted field. The bare-line-only diagnostic parser was too strict.
Changed only read-only status parsing to accept exactly one whole14..16-digit
field in the completed bounded CGSN reply; rejects multiple fields, substrings
of longer numbers and terminal errors. No radio/PDP decision uses this result.
Nine radio/privacy/state tests pass, including labels/quotes/ambiguity/errors.
Native37 identity4 observe-only trial then reports IMEI format/Luhn valid and
nondefault, while every fragment remains redacted; journal has no14..16-digit
subscriber/device value. Original identity/NV never altered. Exact BOOT/model/
backup guards, source hashes and private-copy lease checks preceded each test.
Both trials stopped own clients and restored sensor service; failed units0.
This excludes the earlier parser-unknown/default-format hypothesis, not a
carrier registration/whitelist/RF problem. LTE data remains unverified.

Prepared optional single COPS test network scan under existing-online
observe-only mode, with no operator selection/radio/PDP configuration. Parent
and child reject incompatible/short trials before device launch. One scan
has90s AT allowance inside a120s bounded unit; timeout is inconclusive, not
proof of absent coverage. All scan fragments are redacted before journaling;
summary retains only operator/status/technology counts, no names or PLMNs.
Ten radio/privacy/state tests and nine runtime preflight tests pass. Preparing
a native37 guarded scan with private-copy provenance/lease and final sensor
restoration, no CBD/reset. Long scan allowance follows ModemManager's official
3GPP scan guidance; this lab does not pretend to be a complete MM backend.

Native37 AT network scan completed with a terminal modem error and zero
parsed operators. This is a rejected/inconclusive command, not absent RF
coverage. Own clients stopped and sensor service restored before next trial.
Read-only IPC getters still answer in all later online trials (6/6/8 frames),
so no evidence here supports a deaf IPC or forced-reset workaround.

Reviewed own stock IpcTxNetGet/CancelAvailableNetworks and IpcRxNetPlmnList:
bodyless0804 GET2/SET3; count at body0,10-byte entries, status at entry0,
PLMN entry1..6, technology entry7. Prepared independently written opt-in
Samsung scan under the same online-only/no-radio/PDP preflight;90s timeout
requests its own stock cancel once, never reset. Exact count/size decode
outputs numeric counts only. Eleven radio/privacy/protocol tests and ten
runtime preflight tests pass. Native result pending. Own RAT converter jump
table additionally maps raw33 to Android14/LTE; existing emergency-state
notifications therefore show LTE observation, not successful registration.

Native37 Samsung0804 GET was explicitly rejected by generic response raw100;
no list/coverage result. The lab recognized rejection and did not issue an
unnecessary cancel or reset. Native clients/runtime cleaned and sensors
active before preparing the next observation. Reviewed own NetRegState
constructor: fail-cause byte is packet17/body10, matching the independent
Lineage net.h layout. Added numeric cause-only status output while excluding
intervening LAC/cell identity bytes. Twelve radio/privacy/protocol tests and
ten runtime preflight tests pass. Preparing guarded online-only30s status
observation; no new modem power operation or network-selection attempt.

Native37 cause7 online-only observation returned0805kind2/body19 with
ACT4/domain3/registration1/failure-cause6. Own stock constructor passes byte17
(body10) directly as the cause integer; no LAC/cell data emitted. Standard
3GPP/AOSP cause6 is Illegal ME, but the raw record alone does not prove a
carrier block or the precise rejection procedure/domain. Native IMEI format
was valid/nondefault; neither identity validity nor this cause establishes
network authorization. Asked owner whether this exact handset had working
Android LTE before porting; no physical action needed. Do not retry power/
security, alter identity or assume an inactive SIM to explain the result.
All clients/runtime cleaned, audio/BT/sensors active, failed units0, no identity
digits in private journal. LTE registration/data remains unresolved.

Sensor board source audit found PMIC error-reporting holes: mcu_power show/
store ignored ACPM read/write failures, optional supply-cut ignored its off
write failure, and a positive firmware failure could escape as a successful
sysfs byte count/module-init result. ACPM's actual API returns negative
transport errors or positive firmware codes, with zero only on success.
Added checked normalization (positive failures logged and returned as EIO),
checked LDO37 mode readback after enable, and abort-before-pin-release on
write/readback failure. Stock always-on/off-no-op policy and all reset holds
remain unchanged; supply-cut stays opt-in/off. The MCU_RESP warm-reset warning
remains unresolved, not suppressed or converted to a hard-reset success.
Actual extracted-C tests compile/pass injected transport errors, positive
firmware failures, bad readback, sysfs behavior and sequencing/no premature
hub release. Native new module/build/reboot verification pending. Preparing
a fresh source-pinned kernel build instead of hot-reloading an active hub.

OWNER BASELINE CORRECTION (latest voice handoff, supersedes current-SIM
assumptions above): this exact S9+ was previously used on stock Android;
there is currently NO physical USIM inserted. Earlier CP SIM READY/CIMI/
registration-failure reports cannot establish present physical SIM presence
or a live carrier refusal. Their freshness/cache/hot-detection needs separate
validation after a confirmed insertion. Raw cause6 alone is not evidence of
a blacklist or a settings defect; the owner's settings explanation remains
a hypothesis. Stop further LTE registration/data experiments until an active
SIM is physically confirmed. Sensor/kernel work continues independently.

OWNER DEVICE-ATTRIBUTION CORRECTION: the immediately preceding no-USIM/
previous-stock-use voice statement referred to S8+, NOT this S9+. Withdraw
that statement's S9+ attribution. Final explicit owner statement confirms a
physical SIM IS inserted in S9+. Previous stock-Android LTE use of this exact
S9+ remains unknown. Restore physical insertion as the latest S9+ baseline;
SIM preparation/subscription/registration are still separate, and cause6 is
not a conclusive blacklist/settings diagnosis. No CP operation occurred
between these handoffs; sensor-only build38 continues unchanged.

Latest SIM qualification: owner clarifies the SIM currently in S9+ is a
data-sharing SIM. Earlier main-SIM READY is recalled but not LTE-data proof.
5G-only provisioning or carrier device/plan policy is an unconfirmed
hypothesis; no current blacklist/settings conclusion. Prior other-phone LTE
report must not be assumed to describe this newly clarified current SIM.
No further repeated registration/power trial is justified by that ambiguity.

Kernel38 build-only completed: #38 SMP PREEMPT Thu Nov 19 09:51:34 UTC 2026, source8fcb3a1,
BOOT97661273f8a1e35b21ca202653abf1e731e3c6185460a7faefa135fe9c76246e/27219984bytes.
Frozen five-module package and owner-stock overlay comparison passed. Sensor
PMIC candidate source/fault tests passed; native module and boot pending.
Preparing controlled recovery, fresh nine-partition backup and BOOT-only
update; original recovery/identity/radio/bootloader remain preserved.

Fresh recovery backup38 has all nine byte/hash checks passed. DTB/DTBO/
CPEFS/RADIO/RECOVERY/MISC unchanged versus backup37; EFS differs only by
approved primary ext4 mount/write timestamps (+3525s), mount count+1 and
lifetime write4KiB. Initial extra PARAM audit stopped on a too-strict all-zero
append assumption before any BOOT write. Reviewed the current NUL-terminated
reboot-history area: exactly two N/R timestamp records extend the terminator
into a stale unused suffix; every byte outside that38-byte extension plus
terminator is identical. Not a PARAM write or a general comparison waiver.
Exact new BOOT hash and rollback37 prefix verified; proceeding with guarded
BOOT-only installation using this fresh matching-device backup.

Native38 BOOT-only write/readback passed and actual USB SSH reports#38. An
extra adb reboot found no recovery target because the installer had already
returned the phone to Ubuntu; no second reboot/write occurred from that
failed command. Frozen package/backups uploaded; exact model/BOOT/kernel/
module/profile pins verified. Preserved prior profiles/three units, updated
only selected package/kernel/backup pins, kept orientation/vendor/user policy
intact. All three driver services active. Actual LDO37 mode-readback verified
message emitted by the new code; mcu_power reads1, strict SSI Y/faultN.
Four real accel samples vary, ALS0lux in the dark room, STA-bound HTTPS204.
Initial unfiltered error-priority kernel lines0, failed units0, no matching
SError/CallTrace/chanspec/AF/invalid-type faults. Modem remains opt-in unloaded.
This qualifies the normal new PMIC path/initial boot, not physical voltage
measurement, injected hardware failures, hub hard reset, or LTE registration.
Preparing one normal warm reboot to verify persistent startup without TWRP.

Native38 normal warm reboot completed without a TWRP pass. Since the prior
boot journal is not retained here, verified the current boot epoch is12s
after the saved initial38 pre-reboot checkpoint, with fresh uptime and#38,
rather than falsely treating unavailable previous-boot logs as proof. Warm
startup services all active; fresh varying four-sample accel/ALS0, mcu_power1,
new checked-readback path executed, strictSSI Y/faultN, STA HTTPS204, failed
units0 and full error-priority kernel0. MCU_RESP reset warning still present;
no hard-reset qualification inferred.

The systemctl unit-cache warning recurred after an untouched warm boot.
Inspection identifies runtime DevicePolicy/DeviceAllow drop-ins written by
the sensor supervisor's guarded SetUnitProperties setup/revoke sequence.
Thus the earlier attribution solely to manual kernel staging is incomplete;
this is runtime policy serialization/cache status, not an unexpected unit edit.
A normal daemon reload clears NeedDaemonReload; verified effective policy
remains closed and setup mknod permission revoked. No systemd/portal patch,
weakened permission or persistent policy change was made.

Native38 remains on three active driver services with no new matching
SError/CallTrace/Wi-Fi faults. Reset-warning source audit identifies a
measurement ambiguity: MCU_RESP is checked after AP_SLEEP/SPI restoration,
enable high and100ms wake. Added numeric MCU_RESP/SHUB_INT observation at the
end of the existing standby hold, before any restore/re-enable. Holds, rail
policy, GPIO writes, retry decisions and existing warning remain unchanged.
The observation alone will not qualify a hard reset. Actual power/error-path
C test still passes; preparing kernel39 to collect both phases on hardware.

Read-only audit found the current journal has111kernel lines and no Linux
boot header, while dmesg retains694lines including the boot header and all
52 CPU register-variation warnings (+one unsupported-variation notice).
Both error-priority counts are0, so the earlier bounded error count holds,
but journal-only collection cannot support early-warning absence. Added
exact model/BOOT/backup-guarded kernel-health.py: captures non-clearing dmesg
all/error/warning streams plus kernel journal/error stream, stores raw logs
root-private0700/0600 without overwriting, emits numeric counts/coverage only.
Two host privacy/file-preservation tests and native38 capture pass. Ring has
64warning-priority lines:53CPU notices, cache hierarchy1, RGB/haptic2, GPT1,
4informational initramfs banners, module taint1, BT quirk1, MCU reset1.
No severity/filter changed; no whole-device qualification inferred.

Diagnostic kernel39 build completed from097dc37: BOOTcc36bae3da165a266d6a41aee2331842c1ffbd1e68c881e28ed8670e8f8f51a5/
27219984bytes, #39 SMP PREEMPT Thu Nov19 10:04:39 UTC2026. Five matching
modules/stock-compared overlay frozen. Build only; standby observations still
need native boot evidence before any change to reset policy.

Recovery39 transition exceeded the short host observation window; the first
backup inspection refused an absent ADB target before creating a directory
or any write. Observed the exact G965N recovery/model three times once USB
settled, then a new bounded backup completed. All nine hashes verified; six
protected partitions unchanged, EFS approved four metadata fields only, PARAM
only bounded N/R timestamp-log extension, rollback38/new39 BOOT verified.
Proceeding with the model/backup/consent-guarded BOOT-only installer; no
identity/radio/recovery/bootloader write or reset-policy change.

Native39 actual BOOT/readback/profile/module checks and driver startup pass.
Early-ring collector verifies error-priority0/warning64 and three held-phase
observations. The initial response was0, then all100/1000/3000ms held phases
and post-wake phases show MCU_RESP1, SHUB_INT0. Fresh accel samples vary,
ALS0, strict SSI faultN, all three driver services active. This rules out a
post-wake-only sampling explanation; reset remains unconfirmed.

Source review identifies powered standby driving active-low SPI CS active.
Prepared correction: on the normal always-on policy, verify LDO37 enable/
readback before GPIO manipulation and park CS inactive; explicit supply-cut
path retains low CS against back-power. Voltage mask/reset holds/retry policy
unchanged. Held diagnostics now include programmed CS/GPS_PWR_EN levels.
Actual-C tests cover both policies and fail-before-GPIO/pre/post-readback
errors; pass. Preparing40 build; no native success claim for this candidate.

Kernel40 build-only complete: #40 SMP PREEMPT Thu Nov 19 10:15:51 UTC 2026, sourcebc6915f,
BOOTf4382c00a1b68d582b4a3fbbed75ed0625b851179037fbd5d448b1f91c383715/27219984bytes.
Five modules/stock-compared overlay frozen. Preparing fresh guarded recovery/
backup and BOOT-only update for the powered-standby CS candidate. No reset
policy or full hardware success inferred from the build.

Fresh40 recovery/model observed stably with a longer bounded transition
window; backup all nine hashes passed. Six protected partitions unchanged,
EFS approved metadata only, PARAM bounded reboot-history extension only,
rollback39/new40 BOOT verified. Guarded BOOT-only update follows; no original
identity/radio/recovery/bootloader mutation or experimental rail cut.

Native40 BOOT/profile/module staging and actual feeds pass, but powered-
standby CS hypothesis is NOT confirmed: all100/1000/3000ms observations show
MCU_RESP1, SHUB_INT0, programmed CS1 and GPS_PWR_EN0; post-wake still1.
Warning remains, ring error0/warning64, varying accel/ALS0, SSI faultN and
three services active. Reverted the unproven functional CS/pre-power changes
to the qualified38/39 control sequence; retained only numeric held-phase
CS/GPS level observation. No speculative pull/supply-cut experiment follows.
Preparing41 as the reproducible reverted-control build; reset remains open.

Kernel41 reverted-control build completed: #41 SMP PREEMPT Thu Nov 19 10:23:14 UTC 2026, source78a38db,
BOOT90ccc1300f2791db872ad13da006030081be89828f1786326ebe84299bc95231/27219984bytes.
Frozen package; build-only, actual reboot/driver feed evidence pending.

Fresh41 recovery backup completed and all nine hashes passed. Six protected
partitions unchanged, EFS four allowed metadata fields only, PARAM bounded
reboot history only. Preserved40 evidence/rollback bytes; verified41 artifact
before BOOT-only installation of reverted control plus held-pin diagnostics.

Native41 BOOT write/readback and actual USB SSH boot/staging passed. The
qualified38/39 control path is restored: held phases confirm CS0/GPS_PWR_EN0
with MCU_RESP1, so standby/reset warning remains unresolved. Fresh accel
samples vary, ALS0, SSI faultN, three services active and STA HTTPS204.
New full ring capture reports error2/warning65 (not a clean baseline): ABOX
DSP did not take messages5/234 and2/16 during startup, ipc_retries20.
No SError/CallTrace/Wi-Fi/PMIC failure, failed units0. Investigate DSP startup
separately; active services do not establish an error-free audio initialization.

A bounded nonpersistent audio flow check then passed one second of silent
Pulse playback and exact96000-byte/one-second mono capture. Frames retained
only in process memory, no recording or mixer setting saved/changed. Capture
IRQ+223, new IPC retries0, pointer stalls/backsteps0; aggregate RMS1771.99/
peak15453 are not speech/acoustic-quality proof. Historical startup errors
remain visible. This qualifies present basic flows only; startup race/firmware
message handling remains open.

Native41 audio investigation confirms stored ALSA state includes DSM Read=0.
An isolated private state containing only that control, restored with init/UCM
fallback disabled, emits one real ELEM_WRITE ioctl; original mixer state file
unchanged. It does not yield a DSM reply or a new timeout in that settled
trial, so both startup errors are not yet causally proved to come from it.
ALSA-utils1.2.9 state.c restores writable controls even when their current
value is unchanged; diagnostic command persistence is nevertheless a real
interface defect.

Prepared driver correction: retain legacy DSM Read name/control position/
range/getter as read-only so existing saved state skips it without renumbering
other controls or editing user settings. Explicit reads move to root-write-only
dsm_read_cmd; same four-parameter request, bounded entire range, serialized
with stream_lock and rejected while DSP unavailable/suspending/faulted.
Existing timeout/retry/error behavior unchanged; failure logs add length and
a fixed alsactl-caller boolean, never payload/calibration data. Actual extracted
C tests pass bounds, no replay put callback, DSP guards, mutex/errno paths.
Preparing42 build; native before/after restore and boot/flow checks pending.

Kernel42 audio diagnostic interface build completed (#42 SMP PREEMPT Thu Nov
19 10:45:52 UTC 2026), source4007122, BOOT89d9d850a23a2f648df09787948735c18ecf56c0197f4cf70427b02cfe26a365/
27219984bytes. Initial reused discovery guard correctly rejected opt-in Y;
no reboot/write occurred. Used its model/BOOT/backup checks without the
unrelated discovery-off requirement for the approved recovery transition.
Fresh42 backup all nine lengths/hashes passed, six protected partitions
unchanged, EFS four approved metadata fields only and PARAM bounded N/R
history extension only. Rollback41 and new42 BOOT verified. Preparing
BOOT-only update; build is not native startup or diagnostic fix proof.

Native42 BOOT-only write/readback, actual USB SSH boot and matching guarded
audio/BT/sensor startup passed. Full ring retains early Linux header, error0/
warning64 (journal omits early boot). Prior41 ABOX errors2/retries20 are not
reproduced; CPU variation and MCU reset warnings remain. The exact same
isolated legacy DSM state restore now exits0 with ELEM_INFO1/ELEM_WRITE0
(native41: write1); original asound.state unchanged, command permissions0200.
Five invalid command inputs rejected. Bounded silent1s Pulse playback and
exact96000-byte mono capture passed, capture IRQ+268, retries/stalls/backsteps/
watchdog recovery/codec errors all0. Audio stayed in memory; no new acoustic
speech claim. Primary Wi-Fi HTTPS204, failed units0. Initiated a separately
guarded normal warm reboot after preserving prior boot identity privately.

Native42 normal warm boot independently confirmed by changed private boot ID
and boot time later than the saved checkpoint. All three drivers auto-started;
IPC retry/stall/backstep/watchdog/codec counters0. Full ring includes early
header and reports error0/warning64, no CallTrace/SError/PMIC/AF/chanspec
failure; primary HTTPS204 and failed units0. Both initial/warm observations
qualify the saved diagnostic replay correction and bounded startup only, not
all audio routes, endurance, LTE or full hardware parity. Remaining64 warning
lines retain CPU variation/cache, optional-device/GPT and MCU reset issues.

Native42 read-only cache audit: all eight L2 shared maps are0-7, M3 L3 maps
4-7, geometry attributes absent. Actual source DT has CPU map but no cache
links; generic kernel fallback after DT cache setup failure assumes global
sharing above L1. This is a source-correlated metadata deficiency, not proof
of actual cache wiring. No guessed geometry/topology patch applied. Fresh
post-warm IIO accel samples vary; physical pose was not requested.

Prepared opt-in one-shot CPU cache register probe for missing topology audit.
It samples actual online CPUs with hotplug lock; temporary CSSELR selection
is IRQ-protected/restored before returning. No cache maintenance, clocks,
physical memory, partition or persistent changes. Actual-C mock test passes
all cache types/reserved skips, multilevel selectors and prior IRQ restoration;
module links against exact42 prepared kernel. Samsung M3 primary presentation
confirms private L2/shared L3, but A55 geometry remains hardware-unverified.
Preparing guarded bounded load/unload; no automatic DT/topology change.

Native42 exact model/BOOT/backup and probe hash guard passed. One-shot cache
probe sampled all8 CPUs; every selector restored and probe unloaded. Measured
A55 L1I/D32KiB and unified512KiB architectural L2; M3 L1I/D64KiB, private512KiB
L2/shared4MiB L3 geometry agrees with Samsung design. Full register logs stay
private; decoded capacities/line/ways/sets documented in CPU_CACHE.md. Prepared
board DT candidate with measured geometry and explicit cache ownership. No
CPU feature masking, cache maintenance or clock policy change. A55 no-private-
L2 interpretation still being checked against Arm primary documentation;
source candidate is not boot-qualified.

Arm A55 TRM B2.23/page330 confirms shared outer-cache encoding when no
private L2 is present; all measured A55 CCSIDR values match its512KiB case.
Initial standalone DT compile rejected added subnodes before existing root
properties; moved cache nodes after all root properties. No image/device
write followed the failed compile. Recompiled real DTB now passes cache
phandle graph/geometry verification, and a deliberately wrong cache size is
rejected. Added this check to the build-only kernel pipeline. Actual probe
callback test and shell syntax pass. Preparing43 build; native cache graph,
scheduler and absence of cache warning remain unverified.

Kernel43 build-only completed, source91d74ac, #43 SMP PREEMPT Thu Nov19
11:02:49 UTC2026, BOOT1afe82bad2a9080ea7de228385869da155023405ff67ed1c73cd0b588fad0034/
27219984bytes. New compiled-DTB gate passed in the real build; five matching
modules/stock-verified overlay frozen. Exact native42 BOOT/model/backup guard
passed before orderly recovery. Preparing fresh nine-partition backup and
BOOT-only update; no native43/cache-warning success claimed from compilation.

Fresh43 backup completed; all nine hashes/lengths passed, six protected
partitions unchanged, EFS four approved metadata fields only, PARAM bounded
reboot-history extension. Rollback42 prefix and new43 artifact verified.
Prepared exact pinned stage wrapper and began guarded BOOT-only installation.
No bootloader/recovery/radio/identity modification; actual43 boot pending.

Native43 BOOT readback and actual USB SSH boot/staging passed. All8 online
CPUs now expose the exact measured sizes/line/sets/ways: A55 cluster L2 map
0-3, private M3 L2 maps single CPU, shared M3 L3 map4-7. Original cache
hierarchy warning absent in full early ring; error0/warning63 (prior42:64).
CPU register variation52 plus unsupported notice and MCU reset warning remain.
No new PMIC/AF/chanspec/SError/CallTrace, audio counters0, fresh accel varies,
all3 services active, primaryHTTPS204 and failedunits0. Scheduler debug-domain
files unavailable, so no domain/performance qualification inferred. Initiated
guarded normal warm reboot after privately saving prior boot identity.

Native43 distinct normal warm reboot verified by changed private boot ID and
new boot time. All8 CPU cache geometry and ownership exactly match initial
readback; hierarchy warning absent in full early ring, error0/warning63. Three
driver services active, fresh accel varies, audio retry/stall/backstep/codec/
watchdog counters0, primaryHTTPS204 and failedunits0. No physical help required.
This qualifies measured DT cache description/persistence, not performance
gain, remaining CPU sanity warnings, complete sensor reset or LTE data.

Read-only43 review confirms the remaining52 CPU differences cover13 actual
registers across four M3 cores; generic kernel strict feature checks retain
unsupported-variation taint. No fabricated ID or warning masks applied. Prior
LTE private observations still show normal phone mode and configured automatic
selection but no actual data/confirmed current carrier-reject diagnosis; no CP
reset trial performed43. Preparing guarded per-user patched-Mesa desktop
trial with the independent300s rollback timer. All26 lifecycle host tests
pass; prior trials are rolled back. Desktop apps will restart; no system Mesa,
firmware, bootloader, original NV or personal app Git changes.

The first desktop invocation used an unsupported action name and exited in
argument parsing, with no profile change. Corrected native43 apply captured
PAN_MESA_DEBUG expected nocrc,noafbc vs actual nocrc after login. It rejected
the mismatch and completed rollback: stock desktop recovered, original manager
environment restored and no changed owned files. Read-only search locates the
exact older PAN assignment in /etc/environment. No CP startup occurred.

Prepared explicit login-environment trial option: migrate only exact known
nocrc assignment after saving original private bytes and arming/checking300s
system timer; preserve all other bytes/mode/owner. Protected root no-follow
input, ambiguous baseline rejection, pre-replacement content/inode/metadata
checks, conflict-preserving rollback and acceptance ownership checks.34host
lifecycle tests pass, including real temporary-file apply/restore, CRLF/private
byte preservation, conflicts, racing changes and timer-before-root-write.
Native whole-session and natural timed rollback remain to be verified.

Native43 explicit login-environment trial passed whole-profile startup: private
Shell EGL/Gallium/GBM maps verified through fresh SSH, all requested manager GPU
variables match after login, login assignment matches trial. Independent timer
remains active; no acceptance. Fullscreen1440x2960 targeted3/3 positive scenes
and FIFO build/texture/ideas61/61/61fps pass with physical Mali and0new GPU faults.
Snapshot differences are readonly presentation/power counters only, not knob
changes; screen state restored. Attempted standard ShowApplications DBus test
was denied by Shell, so no app-grid response/animation claim or unsafe API
bypass.36host tests now include conflict-preserving rollback and refusal to
accept edited login configuration. Awaiting natural timer restoration proof.

Native43 natural300s timer fired without acceptance; rollback system job
Result=success/ExecMainStatus0. Fresh SSH confirms original login bytes/mode/
owner/group, all4 owned files removed, original manager environment and actual
stock Shell libraries restored. Post-rollback full early ring error0/warning63,
no GPU/AF/chanspec/SError/CallTrace, three driver services active/failedunits0.
This verifies the optional exact login-setting migration and natural recovery;
private Mesa is not yet accepted/persistent. Full scene/readback/browser/
endurance and app-grid animation measurements remain pending. /dev/uinput is
absent; no virtual-input module or unsafe Shell mode was enabled for the
denied app-grid request. No Tailscale/ChatGPT install/preferences committed.

Started native43 mesa43-full trial after confirming prior natural recovery
and unchanged exact BOOT/model/verified backup. The same guarded login option
and private coherent build pass startup;300s rollback remains armed. Rebuilt
tracked synthetic readback source locally on ARM64 and pinned source/hash,
then began full33-scene/fullscreen/FIFO/readback qualification. No system
libraries, firmware, personal profiles or original identity partitions changed.

Native43 full desktop33/33 scenes, exact100-frame synthetic readback and
fullscreen1440x2960 FIFO60/61/61fps passed on physical Mali with0new GPU faults.
Fresh SSH verified private EGL/Gallium/GBM maps, whole manager/login environment
and zero full-ring errors. Accepted mesa43-full only with saved post-startup
evidence; its rollback timer stopped. Guarded normal reboot then independently
confirmed changed boot identity, stable private libraries and all selected
settings persisted. Three services active, full early ring error0/warning63.
This is accepted bounded desktop deployment, not all GPU/browser/endurance.

First fresh-profile Firefox URL test returned a90s result timeout; no kernel
GPU error, two browser processes mapped graphics libraries. No browser pixel
pass inferred. Added explicit visible WebDriver trial using an ephemeral
automation profile and loopback-only services, page focus/visibility/headless
checks, strict120-frame/byte comparison and physical-renderer qualification.
Host evidence test rejects incomplete/software/headless/hidden/malformed
reports. Mozilla geckodriver0.37.1 ARM64 downloaded privately from official
release and digest verified; MPL2 binary/logs/profiles excluded from Git.
No forced GPU/sandbox preference or personal browser profile supplied.
Preparing actual focused-page rerun with normal wake/unlock and idle inhibitor.

The controlled visible Firefox160.0.1 WebGL trial passes120frames and
31,457,280 compared bytes with0mismatch/context-loss; focused/visible true,
headless false. Audited prefs.js/user.js contain no graphics/sandbox overrides.
Browser reports generic Mali-family label rather than the exact G72 model;
that label is not used as a model identity. Screen state restored. Final
runner also explicitly bypasses HTTP proxies for loopback control/browser
traffic; validating that exact final source before publication.

Final loopback-direct WebDriver source passes native pixel/focus/policy test;
host proxy regression confirms local control ignores external HTTP proxy
variables. After accepted-profile warm boot, a separate fullscreen targeted
render pass completed all3 scenes but FIFO dropped to11/11/11fps: overall
qualification FAIL despite0GPU faults. Retained failure and accepted deployment
is not labelled animation-stable. No speculative clock/policy change applied.

Added optional visible small-canvas animation callback observation. Native
120callback run passes70.5/s, median15ms/p95 21ms with focus/visibility and no
context loss; this is not hardware scanout proof. A later isolated fullscreen
FIFO build scene returns60fps without policy changes. During that60fps repeat,
CPU big1066..2327MHz/little350..1499MHz, GPU260..572MHz and sampled GPU45..49C;
these are not measurements from the earlier11fps case. Warm-trial changed
fields are readonly IRQ/power counters only, with0new generation/wait failure.
Intermittent cadence cause remains open; next correlate focus/frame callbacks
and clocks during a failing reproduction rather than masking or guessing.

Prepared native43 LTE observation with current readiness fix and improved
read-only EPS diagnostics. AT+CEREG=? queries supported reporting modes; no
subscription/setter/reset command added. Numeric CEREG query parsing drops
location/timer fields and reports reason domain separately without interpreting
vendor cause6 as a confirmed carrier rejection. Initial PDP registration gate
now updates only from a complete acknowledged own CEREG query, not a partial
or unrelated chunk. Four new diagnostics tests,14PDP and10runtime-launch tests
pass. Extended interleaved-URC subscription remains unqualified/not enabled.

Verified all9 lengths/hashes in archived37/40/43 backups, unchanged CPEFS/RADIO,
and both bounded EFS-superblock-only hops. Preparing exact43 module/BOOT/backup
checks and private receipt maintenance through checkpoint40. Original identity/
radio/recovery/bootloader untouched; working NV copies and old receipt preserved.
A fresh bounded stock CBD/RIL trial will verify live phonebook readiness and
EPS reporting capability, with no blind auth/reset retry loop.

Native43 guarded private provenance revalidation through checkpoint40 passed;
matching modem/stock-verified overlay loaded and bounded CBD/RIL ran once.
Fresh SIM0/130/131 events retain readiness true, verifying phonebook completion
no longer clears the initial-PDP readiness gate. Completed EPS queries are
acknowledged/redacted; reporting capability is only[0,1,2]. Mode3 was NOT sent.
EPS moved0->2 and remained searching; no initial PDP activation/data proof.
RIL bounded job exited0, no AT timeouts. CBD monitor hit its existing90s bound
and terminated while the RIL observation was120s; that is not an exit0 claim.

The loaded-modem full ring is NOT clean: observed136error-priority lines and
67warnings,0CallTrace/SError/GIC-type failure. Many lines are vendor register/
open diagnostics, but four ECT-missing paths and four explicit unimplemented
bus-QoS warnings are genuine support gaps. Optional packet-log creation fails;
closing the RIL channel while CP remains online also yields three not-open/
demux failures. No severity/filter change or guessed QoS table was applied.

Private OPEN capture identifies requested CP audio/default files absent from
the verified private EFS/CPEFS trees and diagnostic paths including
err/csdiag_mmrj_Info.dat. Current RFS intentionally denies every file-based
OPEN/CLOSE; only bounded legacy NV reads/writes work. This is not evidence that
all CP file services are implemented. No arbitrary namespace or fake file was
enabled. Review exact owner/public protocol before a bounded private diagnostic
file service; do not assume cause6 has a proven standard reject domain.

Private working NV checksum and unchanged-original provenance verify after
trial; all source/working/receipt history preserved. Ordered normal reboot
returns43 to modem-opt-in-off, accepted private Mesa persists. Latest cleanup
boot has two initial sensor zero-accepted-byte retry lines (not error-free);
strict ACK Y/faultN, fresh accel varies, three drivers active, failedunits0 and
primaryHTTPS204. Original recovery/radio/identity/bootloader not written. The
sensor retries and remaining modem support/data failures stay open.

Modern RFS interface review identified command3 READ,4 WRITE,5 SEEK,6 CLOSE,
17 OPEN. Owner ARM64 interface passes requested OPEN flags to the OS, reads
fd/count from offsets6/10, and uses bounded14-byte result/errno replies (SEEK
has18bytes with a reserved word). Added original opt-in implementation for ONLY
the two observed diagnostic names, mapped to new0700 lab storage/0600 files.
No CP audio/calibration defaults synthesized; no arbitrary path resolution or
original EFS access. Limits: two256KiB files,64KiB per I/O,8live virtual handles,
4096operations; no truncate/append flags, symlink/nonempty reuse refused.
Default runtime still denies file OPENs; new opt-in does not enable itself.

Ten RFS host tests (five new isolation/protocol cases), ten launcher preflight,
four CEREG and fourteen PDP tests pass. These are not CP/hardware proof. An
explicitly guarded native43 cold trial is being prepared with fresh private
storage, current backup/model/module/BOOT/provenance validation and ordered
cleanup. Existing native43 sensor-ACK fault remainsN and failed units0. No
claim that diagnostic file support fixes LTE registration or vendor QoS gaps.

Native43 bounded cold diagnostic trial completed: real CP OPEN17 -> SEEK5 ->
WRITE4(25bytes) -> CLOSE6 all return errno0 and the RF diagnostic file is25bytes.
Network-reject diagnostic was NOT requested in this observation; READ3 has host
round-trip proof only. Missing audio/FLL defaults remain denied. Checked mounted
read-only owner SYSTEM/VENDOR too: no matching default files. No fabricated
contents or changes to original partitions/identity. Private NV checksum and
original-source provenance still verify. Exact source hashes retained privately.
RIL exits0, twelve acknowledged EPS queries remain0/2, no PDP activation or LTE
data. CBD RuntimeMax is120seconds for this trial, expires with Resulttimeout/
status15; this is distinct from the earlier90s observation, not corrected history.

Loaded-trial ring406error-priority/88warnings does NOT retain the early boot
header. No CallTrace/SError, but ECT4/QoS gaps and optional packet-log failure
remain. Of93 demux failure groups,91 target IPC after bounded RIL closes while
CP remains online (monotonic1356.8..1417.0); other not-open observations include
RFS2/router1. Ordered shutdown/channel lifecycle is still unresolved. No log
filter or severity change applied; returning to module-off does not fix this.

Guarded normal cleanup reboot completed, modem module absent. Fresh full ring
has boot header, error0/warning63; journal lacks early boot, not used alone.
After initialization settles all three sensor/audio/Bluetooth services active,
strict ACK Y/faultN, accel samples vary, failed units0 and Wi-Fi HTTPS204.
Accepted private Mesa profile persists. Early activating service/absent IIO
sample was recorded before readiness, then rechecked successfully. Reloaded
systemd metadata after a stale-unit-cache notice; no unit source edit. Broader
LTE/compass/GPU/other hardware limits remain. Final39 host RFS/launcher/CEREG/PDP
tests pass including private diagnostic writes leaving both NV copies unchanged.

Prepared opt-in cold-test RF quiesce before IPC/RFS close. Owner RadioPower
OFF interface and Lineage pwr.h agree on SIPC0107 EXEC body0100 (LPM); this is
not physical CP shutdown or a secure reset. Existing-online/observe-only use
refused before I/O. Exit requests prior PDP/scan cleanup, consumes stale input,
requests LPM once and keeps RFS/IPC open for at most10seconds plus a2second tail
inside that bound. Only fresh exact phone-state LPM response/notification may
confirm it; generic ACK, late reply, restart, return to normal or rejection
cannot. Incomplete pre-request frames fail closed, no retries or reset fallback.
Five transport/state/guard host tests and ten launcher tests pass; pending
native cold trial. Default behavior unchanged until explicitly opted in.

Native43 cold90s LPM trial: one request, fresh LPM confirmed, eight IPC/RFS
frames serviced and full2second tail completed, no physical reset requested.
RIL exits0. EPS codes0/2 only, no PDP or data proof. Private NV/source provenance
verify. Full loaded ring retains early header,128error-priority/67warnings,
0CallTrace/SError. Preliminary post-close IPC count0 later becomes1 at
monotonic624.535; startup RFS-not-open1 at496.468 also remains. These are NOT
fully resolved. Earlier non-LPM trial had91IPC-not-open events, but different
observation durations prohibit a controlled reduction/performance claim. ECT/
QoS/optional packet logging and module diagnostics remain. No log masking.

Ordered normal cleanup reboot returned43 to modem-off. Next investigate the
parent starting CBD asynchronously without proof that child IPC/RFS descriptors
are open: the initial RFS packet may race service readiness. Do not replace
this with a guessed sleep, or assume a future readiness barrier already works.

Settled LPM-trial cleanup boot: full ring header present/error0/warning63,
three services active, failedunits0, strictACKY/faultN, accel changes -601->-607,
source-bound Wi-Fi HTTPS204 and accepted private Mesa persists. Reloaded stale
systemd metadata without changing unit source. This module-off baseline does
not erase the loaded-trial support gaps above.

Prepared actual child readiness barrier for cold startup. Transient RIL service
now Type=notify/NotifyAccess=main with10s start bound; child reports READY only
after private receipt/lease/NV checks, IPC/RFS/router descriptors, buffers and
cleanup handlers are set up. Parent waits for notify active/running with live
main PID before invoking CBD. Failed/stopped/wrong-type/no-main/timeout states
stop the child without vendor launch or physical power control. This replaces
an asynchronous start-job assumption, not a guessed delay. Five new readiness
host tests and ten launcher tests pass; native startup-race correction pending.

Native43 readiness trial passes: manager reports Type=notify/NotifyAccess=main,
active/running after child IPC/RFS-ready notification; only then CBD launches.
SIM0/130/131 retains readiness. RF LPM cleanup confirms with6frames/fulltail,
RIL exits0. The initial RFS message remains, disproving its earlier tentative
classification as a packet lost during CBD startup. Kernel trace places it in
shmem_init_comm BEFORE the second userspace open and BEFORE CBD boot; it returns0
while waiting for its paired endpoint, not rx_demux failure. No log-level change
was made. Readiness gating remains useful for actual startup ordering/failure
handling but is not labelled a fix for that expected peer-wait diagnostic.

Source review now identifies an additional handshake issue to investigate:
shmem_init_comm can write the clock table/send INIT_END while link is OFFLINE,
before CBD boot resets cp_boot_done. CP_START separately checks rild_ready and
sends INIT_END. Need qualify deferring the open-side handshake until link IPC
without losing the later-ready case. No speculative IRQ/clock/power change
applied in this trial; ECT/QoS and late post-close IPC traffic remain unresolved.

Final readiness-trial loaded snapshot: full ring header present,125error-priority
lines/67warnings,0CallTrace/SError; only initial init_comm RFS peer-wait count1,
no closed-IPC message within this bounded snapshot (not endurance proof). Nine
EPS queries0/2 only, no data/PDP. Normal guarded cleanup reboot verifies distinct
boot and modem absent; full ring error0/warning63/header present, three drivers
active/failedunits0, strictACKY/faultN, accel -602->-596, Wi-Fi HTTPS204 and
accepted private Mesa persists. Systemd metadata reloaded, no unit source edit.
All49 focused RFS/readiness/startup/quiesce/CEREG/PDP host tests pass. Original
partitions, bootloader, identity and private evidence untouched/unpublished.

Prepared source-only shared-link handshake correction: opens while OFFLINE do
not publish a clock table/INIT_END before CBD resets shared memory. CP_START
publishes link IPC only after successful reset, writes the existing clock-table
header before INIT_END, and later-open pairs complete under the same state lock.
Boot-on clears completion and link state together under lock. Existing CP_START
ack retransmission and IOSM completed-open fast path retained. No frequency
values, security reset, IRQ configuration or log severity changed. Actual-driver
C harness passes early/late/reversed/partial endpoints, duplicate references,
new boot, existing retransmit and reset-failure cases. Native module/CP startup
still pending; no LTE or handshake hardware-success claim yet.

Patched modem module builds against retained native43 kernel output/vermagic.
Existing shmem_send implicit-fallthrough build warning remains, not attributed
to this change. Prior committed driver fails the same early-handshake C harness
instrumentation; patched version passes. Preparing module-only guarded native43
trial with exact candidate SHA/vermagic, current model/BOOT/backups/provenance
checks. Baseline package/module preserved; no BOOT/partition write required.

Native43 candidate60b65b06 module-only cold trial passes early-open handshake:
CP_START once -> existing CT0 header once -> INIT_END once; no pre-boot INIT_END,
no paired-endpoint wait, no rx_demux/not-open message in the final bounded ring.
Full ring retains boot header,123error-priority/67warnings (vendor diagnostics,
ECT/QoS gaps still present),0CallTrace/SError. SIM0/130/131 readiness true, RIL
exits0, LPM/two-second tail confirms with7frames. Nine EPS queries0/2 only;
PDP/data unresolved. Verified private NV checksum and unchanged-source provenance.
Candidate SHA/vermagic and matching native43 BOOT/current backup checked before
load, baseline package/module retained. Normal guarded cleanup reboot requested;
SSH disconnect during reboot is not interpreted as failed device boot. No BOOT,
original EFS/CPEFS/RADIO, recovery or bootloader write. Separate native late-open
trial and full new image qualification remain pending despite C harness coverage.

Cleanup boot confirmed distinct and modem absent: full ring header present,
error0/warning63; three drivers active/failedunits0, strictACKY/faultN and
Wi-Fi HTTPS204. First two X-axis samples matched; eight follow-up full triples
were all distinct, confirming current updates. Accepted private Mesa persists.
Systemd metadata reload only. Actual-function C and two IRQ migration tests pass.
Baseline startup profile remains unchanged; candidate is not yet an always-on
LTE service, a native late-open pass or a rebuilt-image installation pass.


Owner evidence clarification: audio output, microphone, Wi-Fi, Wi-Fi Direct
and Bluetooth were already confirmed functional in actual use. Recorded as the
baseline without deleting narrower historical failures or expanding that claim
to every profile/endurance case. Recent cleanup checks concerned service return
after modem trials. No change to approved task scope, priority or test policy
is inferred; an earlier relayed scope restriction was explicitly withdrawn.
No device operation performed for this clarification.

Prepared native late-open qualification with the same exact tested module and
current43 model/BOOT/backup/overlay/provenance guards. CBD starts first; observe
CP_START with no IPC/RFS userspace opens or INIT_END, verify read-only STATUS4
through boot endpoint, then stop the monitor and attach bounded observe-only
RIL. No RF configuration, PDP activation, reset retry or bypass of online guard.
No code change yet; this is a separate hardware case, not implied by early-open
success or C harness. Preserve private evidence and original NV-source history.

Native43 late-open case: CP_START observed with neither IPC/RFS open nor any
INIT_END, read-only boot-endpoint STATUS4 verified, then bounded online-only
observe RIL attached without CBD restart/reset. Link completes when RFS opens:
CT0/INIT_END at353.776s. One queued CP_START at353.830s gets the retained retry
ack and then stops;12 CP_START/2clock headers/2INIT_END total. Existing legacy
'abnormal' diagnostic appears once; no actual crash/watchdog/SError/CallTrace.
Phone state1/LPM is preserved, SIM0/130/131 ready and six EPS queries0 only;
RIL exits0. This proves the late-open link handshake, not RF/data operation.

Full loaded ring183error-priority/67warnings/header present. Ten RFS demux
failures occur at441.783..441.791s, AFTER RIL closes all channels at413.795s;
not startup loss. Two other RFS-not-open entries are expected peer waits.
Persistent file servicing/ordered physical shutdown remains unresolved; no
loss-free lifecycle claim. Private NV/source checks pass, original blocks are
unchanged. Normal guarded cleanup reboot requested. Offline owner-library audit
confirms a legacy RIL_Init entry and Android/HIDL dependencies; no owner RIL
execution, new power transition or firmware redistribution was attempted.

Cleanup confirms distinct native43 boot/modem absent, three services active,
failedunits0, strictACKY/faultN and4distinct accel triples. Full ring retains
header/error1/warning63: one SSP initial zero-accepted-byte retry at9.543s;
not a clean-error-log claim. Device baseline owner-confirmed audio/wireless
functionality is retained. Metadata reload only, no general feature re-test.

Prepared original dependency-only Bionic probe; it never calls RIL_Init or any
radio request. Before dlopen it installs an architecture-checked deny-default
syscall filter: read-only opens, writes only to stdio, no sockets/device ioctls/
file mutations/exec/mount/ptrace. Local Linux self-test verifies rejected modem
ioctls, writable open, non-stdio write, socket, unlink, F_SETOWN and pwrite.
Native test remains pending. Owner libc startup ABI/fini offset16 verified
privately; no startup implementation/header or owner ELF is copied into Git.

Initial cross-build failed on missing ARM64 UAPI headers; raw kernel headers
also correctly failed userspace checks. Generated proper headers_install output
from the pinned kernel instead. Link requires owner Bionic libc/libdl and its
ld-android loader exports; verified loader SONAME/shared-globals export and
allowed only transitive shared-library unresolved symbols (own references still
must resolve). Hardened PIE/RELRO/stack-protector build now passes. All owner
inputs/binary/disassembly remain ignored/private; no image/firmware publishing.
Preparing model/backup/BOOT checked module-off, read-only private-unit self-test
BEFORE any owner-library load. No NV bindings, RIL initialization or CP controls.

Native Bionic self-test passes on43 with modem absent and no private modem
bindings. First library inspection fails on a denied fstatfs metadata query;
added statfs/fstatfs read-only metadata calls while retaining all mutation,
network and ioctl denials. Second version self-test passes; loading then fails
because libandroidicu.so search path omitted the runtime APEX parent lib64.
Including that read-only owner path fixes loading. Same hardened policy now
loads owner libsec-ril and resolves RIL_Init, with entry explicitly NOT called.
No controller transition, radio request, NV or original-partition write.

Added reviewed-input build helper and guarded public native launcher: explicit
model/current BOOT/backups/helper/binary hashes, module absent, bindings absent,
root-private fresh evidence, same-boot self-test prerequisite and fixed boolean
output. Five guard/privacy/tamper tests pass. Initial reuse of the board guard's
optional opt-in-off check rejected because it refers to Wi-Fi P2P; corrected to
preserve that working feature and check modem absence independently. No Wi-Fi
setting changed. Public launcher itself passes both native phases with return0/
verifiedtrue, not just the private orchestration. All failed trials preserved.
Known build/search-path success route documented; no owner ELF, binary or raw
log is added to Git, CI remains source-only. Full RIL initialization/LTE is still
pending; loader success does not establish callbacks, services or connectivity.

Owner returned and replaced the data-sharing/test SIM with the owner's personal
phone SIM, confirmed KT network. Treat this as a new physical SIM observation,
not proof retroactively changing earlier results. Preparing fresh guarded cold
trial with the same hardware-qualified handshake candidate and KT attach APN;
model/BOOT/backups/current private NV-source provenance checked, no identity/NV
reset or original partition write. Existing working NV/history preserved.

Owner confirms this exact S9+ had LTE data under Android. Personal KT SIM first
cold observation still EPS0/2/searching over120s with no PDP activation; LPM
cleanup confirms/fulltail6frames, RIL exits0. Preserve this separately from the
older data-sharing SIM. Owner notes SIM changes may need repeated initialization.
After guarded whole-device reboot, prepare one additional bounded fresh modem
startup with the same reviewed module/APN and private NV history. This is not
factory data erasure, NV replacement or an unbounded reset/authentication loop.

Prepared module-off owner RIL initialization stage after checking public RIL
callback ABI and owner callback slots/function-table version12/state getter.
Original four-callback environment and bounded main-thread timer queue record
counts only, never tokens or payloads. Timer capacity64/dispatch128/time2s bound;
negative/full/reentrant queue cases tested. Added only same-process thread clone
flags and same-TGID signals to the read-only filter; fork/new namespace/socket/
file mutation/controller ioctls remain denied. clone3 is rejected with ENOSYS so
libc uses the reviewed legacy thread path. Real Linux self-test verifies thread
callback delivery and retained mutation/fork denials; seven guard tests pass.
Native offline entry invocation is still pending. No radio API/request permitted.

Personal KT SIM retry2 after a verified distinct whole-device boot remains
EPS0/2 without PDP. Raw vendor causes now include19/10, unlike older cause6;
namespace remains unconfirmed. Owner confirms Android LTE history for this exact
S9+, so do not label it unsupported or assume a bad SIM. Retry loaded ring has
123error-priority/67warnings/header present,0CallTrace/SError; working NV/source
provenance preserved. Guarded cleanup reboot completed before next attempt.

Critical protocol correction found while reviewing original initialization:
owner string conversion maps IP->internal1, IPV6->internal2, IPV4V6->internal3.
The attach builder maps internal1 to wire2, internal2 to wire5, internal3 to
wire6. Our prior attach helper incorrectly treated internal2/wire5 as IPv4,
while its PDP definition correctly used wire2. Correct home+roam attach fields
to2, preserving all other reviewed bytes. Prior host test asserted the same
wrong constant and did not validate the string-to-enum boundary; corrected that
assertion and added cross-message consistency. No modem fix claimed before
hardware test. Prepared offline-init probe changes are preserved privately as
WIP and removed from the active diff to prioritize this concrete LTE bug.

Corrected IPv4 attach native trial now registers EPS1 and yields confirmed
active CID1 plus modem IPv4/DNS/MTU. This is first actual initial-PDP activation
proof, not yet internet proof. First independent data test stops BEFORE any
network mutation because this kernel lacks IP rule/multiple-table routing.
No test packet or route was applied in that failed preflight. Prepare direct
/32 host routes only for modem DNS/test destination, preserve default/Wi-Fi,
bind sockets to BOTH modem address and rmnet0, require verified TLS/HTTP204,
and restore temporary state. A fresh online attachment (no CP/CBD reset) will
run the helper automatically as soon as the bounded PDP context appears.

## 2026-11-20 — Personal KT SIM LTE IPv4 data verified

Corrected attach profile reaches EPS1 and activeCID1 with assigned IPv4/DNS/MTU.
An online-only follow-up keeps the same loaded candidate and validates its live
GNU build-id against the pinned module; no CBD or physical reset is requested.
Network helper runs immediately on a fresh live PDP candidate. First policy-route
preflight was unsupported and changed nothing; verified kernel config lacks
IP_ADVANCED_ROUTER and IPv6 multiple tables. Proper temporary /32 host routes
avoid that missing feature while preserving main default routing.

Actual source+device-bound rmnet0 DNS query succeeds using modem DNS. TCP/TLS
certificate+hostname validation and HTTPS /generate_204 returns204. Interface
counts increase RX10/TX9,4176RX/1204TX bytes with0RX/TX errors. Temporary
routes/address/link/MTU restore verified. This is first real IPv4 Internet proof,
not a claim from registration, an IP address or a Wi-Fi request. Private result
and original logs retained; no addresses/identifiers/raw logs committed. Parsed
DNS and active-candidate expiry tests plus12radio/14PDP tests pass. Production
auto-connect/reconnect, persistence after reboot, advanced routing, IPv6,
voice/SMS and loaded-kernel support gaps remain. Do not mark full modem complete.

Cleanup after the data trial completed a verified distinct normal reboot.
Modem module is absent (default opt-in preserved), no failed systemd units;
audio/Bluetooth/sensor services are active. This is service restoration, not
a repeat physical test of every owner-confirmed feature or a clean-ring claim.


Cold-start repeat after the successful data trial registers EPS1, but does not
start PDP: radio EXEC and explicit PS-attach SET return raw0x8005 while the
completed read-only AT+CGATT? query reports1/OK. Do not interpret raw0x8005 as
success or infer its namespace. Existing PDP gate required the SET acknowledgement
and therefore ignored independently verified existing attachment. No network
mutation/data request occurred in this repeat.

Prepare a second gate path using only an echoed, completed, unambiguous
AT+CGATT? response1/OK no older than15seconds, plus the existing fresh EPS/SIM/
radio/AT prerequisites. Unknown/negative/malformed/error/duplicate responses
invalidate that read path; CP boot notification clears it. Poll the read query
alongside registration only for explicit PDP trials. Never manufacture an ACK,
remove the registration guard, or retry a radio mutation blindly. Thirteen radio,
14PDP and4CEREG host tests pass; this addition awaits hardware qualification.


Native cold trial with the query-aware candidate again verifies EPS1, activeCID1,
modem-only DNS and certificate/hostname verified HTTPS204. RX10/TX9,
4175RX/1204TXbytes,0interface errors; temporary state restoration passes.
Completed CGATT queries report false then true while readiness advances.
This boot returns actual0x8000 for both EXEC and PS-attach SET, so it verifies
cold-start data and live query parsing, but does not hardware-qualify the specific
no-SET-ACK alternate gate. Retain that limit; no always-connected claim.


After query-aware cold trial: orderly PDP cleanup requested, LPM acknowledged
and RFS drain reports no failure; RIL exit0. Current model/BOOT/backup and private
NV/provenance validated before normal cleanup reboot. Distinct boot returns
modem-off, all three driver services active and failed units0. Full early ring
retained: error-priority1 (initial SSP zero-write retry), warning63, CallTrace0,
SError0. Strict ACK isY, supply-cut/bitbangN; accelerometer values vary and ALS
is readable. This is restored sensor feed/service evidence, not a clean-kernel
claim, ambient-light-change test or physical wireless/audio retest.


## 2026-11-20 — LTE data with the sensor service running

Split the opt-in modem mount tree and scratch data from the sensor view.
The modem launchers propagate the selected root through RIL and CBD, and
the CBD monitor holds both the existing NV lease and the modem mount lease.
Setup and teardown take the modem mount lease exclusively while sharing
the NV lease. Legacy NV maintenance keeps its existing exclusion.

Native43 hardware: the same running sensor service remained active from
before the cold trial through LTE DNS and certificate-verified HTTPS204
and through trial teardown. Accelerometer and light feeds were readable.
Both mount views were checked live: the sensor root had no modem nodes or
private EFS mount, and the modem root had no BBD/ttyBCM sensor nodes.
EPS1 and active CID1 were reached. Modem interface counters advanced
RX10/TX9 with zero errors, and temporary network state was restored.
PDP deactivation was requested, the RF low-power response arrived, and
the drain reported no failure. The modem mount tree was removed while the
sensor mount tree stayed active. A guarded normal reboot was requested
after verifying the model, BOOT, backup and working NV provenance.

This verifies coexistence during a bounded session. The shared NV lease
still prevents an independent sensor stop/start transition while a modem
client is live. Persistent service recovery and automatic LTE routing
remain open.

The distinct cleanup boot restored the normal modem-off state and all
three driver services, with zero failed units. The retained early ring
had 63 warnings and two error-priority SSP zero-write retry messages.


Prepare an experimental modem kernel with IPv4 and IPv6 multiple routing
tables. The build verifies the resolved Kconfig dependencies. Native43 lacks
this support, which prevented policy routing before the first data trial.
The earlier host-route proof remains valid. No live route or boot behavior
is claimed for this build change.

Added an opt-in, bounded IPv4 policy-routing qualification to the modem data
probe. Linux namespace rehearsal verified that the source-bound lookup selects
the separate table and an ordinary lookup still uses the existing interface.
The probe refuses a pre-existing table or rule priority, checks the two paths
before HTTPS and verifies teardown. On-device qualification is pending.
The existing kernel43 boot recorded two retries accepting zero of 36 bytes
about 1.5 ms apart, with strict ACK enabled and no latched transmit fault.

### 2026-11-20 — Restarting sensors during a live LTE context

Added an optional dedicated mount tree, scratch directory and lease for the
pinned sensor profile. The existing profile format keeps its legacy default.
The dedicated view refuses modem preparation and modem device nodes. Sensor
service shutdown and startup no longer take the modem NV lease in that view.

On native43, migrated the sensor service with the pinned BOOT, backup and
program checks. Retained the previous unit and profile for recovery. The
new service started with readable accelerometer and illuminance feeds.
In a cold bounded LTE run, DNS and verified TLS returned HTTPS204 before
and after an intentional sensor service restart. The sensor invocation
changed and both feeds returned. The RIL invocation and PDP session stayed
live. The modem interface saw RX10/TX9 packets before and RX11/TX10 after,
with zero errors in either test. Temporary route state was restored after
both probes. Modem teardown left the sensor view active, with zero failed
units. This does not qualify automatic LTE startup, reconnection or
continuous app routing.

### 2026-11-20 — Native kernel with multiple routing tables

Built kernel44 with the resolved IPv4/IPv6 policy-routing options and the
matching driver modules. Fresh TWRP backup verified all nine partitions.
Compared the protected backup partitions with the prior checkpoint and
verified the rollback BOOT bytes. The EFS comparison permits only the four
previously reviewed ext4 superblock fields. The BOOT-only installer
verified the write by reading back the whole new image. Native Ubuntu
then reported kernel44 and readable IPv4 and IPv6 rule lists. The pinned
audio, Bluetooth and dedicated sensor service started with no failed units.
The main IPv4 default remained the Wi-Fi interface.

The first cellular test preflight correctly refused provenance revalidation
without a mounted modem view. The corrected setup first prepares that
separate view and takes exclusive state and runtime leases before EFS
provenance revalidation. It does not write the EFS partition or change
working modem NV. Test results are recorded separately.

Native44 cold trial passed real modem DNS and certificate-verified
HTTPS204. The source-bound route resolved through the separate modem
table while the ordinary lookup selected the existing interface. The
main default did not change. RX10/TX9 packets and zero interface errors
were recorded. The temporary rule, table route, address, MTU and link
state were restored. The independent sensor service stayed running and
both IIO feeds remained readable. IPv6 rule listing works, but no IPv6
PDP or traffic was exercised. An ordinary application still uses the
existing Wi-Fi default. Automatic LTE routing and reconnection are open.

The distinct cleanup reboot returned the modem to its opt-in off state.
All three driver services started, accel and ALS feeds were readable,
and no trial rule remained. The Wi-Fi default and interface-bound HTTPS204
were verified. The full boot ring had zero error-priority lines, 63
warnings, no Call Trace or SError and no SSP zero-ACK retries in this
boot. Zero failed units. Earlier intermittent SSP retries remain open.

### 2026-11-20 — Hold an already-qualified LTE context

The explicit bounded cold trial can hold a qualified PDP beyond the original
activation deadline. The deadline still applies to the unqualified phase.
A held context fails when its registration evidence goes stale, SIM or AT
readiness is lost, IPv4 route parameters change, or the CP invalidates the
context. Existing shutdown and no-reset constraints apply.

On native44 the same RIL invocation and context carried actual modem DNS and
verified HTTPS204 immediately after qualification and again 27.1 seconds
later with a 20-second activation limit. Both source-policy trials restored
all temporary state, kept the Wi-Fi default and recorded RX10/TX9 with zero
interface errors. The same independent sensor service remained active.
Teardown requested PDP deactivation, then verified RF low-power response and
completed the RFS tail drain. It did not establish explicit PDP deactivation
acknowledgement or CP power-off. Long-lived startup, application fallback and
automatic reattachment remain open.

### 2026-11-20 — Observe PDP release before RF teardown

A qualified held context now gets a separate three-second observation
after its one release request and before RF low-power is requested. The
observer discards already queued IPC replies, continues servicing RFS,
records only matching generic result codes and same-CID status codes, and
stops the RF sequence if the CP restarts. The older best-effort failure
path is unchanged.

Native44 again verified modem-routed DNS and certificate-verified HTTPS204.
Release then returned result 0x8000 and context state 3 in the observation
window, without a CP restart. The later LPM handshake completed separately.
This qualifies the observed release sequence for the tested CID and firmware.
A same-session reactivation after release and automatic failure recovery
have not yet been qualified.

After the release trial, the distinct cleanup reboot restored the
modem-off state, all three driver services and readable accel/ALS.
No failed units or error-priority lines appeared. The ring contained
63 warnings and no SSP zero-ACK retry in this boot.

### 2026-11-20 — One controlled LTE reconnection in the same CP session

Added a one-shot, opt-in request for a qualified held cold trial. It invalidates
the current route candidate before issuing the release. The next activation
requires a single matching release success and the same CID's observed state 3,
then fresh registration and packet attachment queries after the release window.
The network helper requires an explicit matching generation for each probe and
refuses a stale candidate from the previous context.

On native44, generation 1 and generation 2 both passed actual modem DNS and
certificate-verified HTTPS204 using the source-policy route. Each direction
recorded RX10/TX9 and zero interface errors in each probe. Both temporary route
configurations were restored and the Wi-Fi default did not change. The same
RIL invocation stayed live and the independent sensor service did not restart.
Release returned 0x8000 and same-CID state 3 before the second activation. The
second context was released and RF low power was confirmed on exit. This was an
operator-requested reconnection, so unattended loss recovery, reboot startup and
application fallback are still unqualified.

The distinct cleanup boot returned to modem off with all three driver
services active and both sensor feeds readable. Zero failed units or error
lines, 63 warnings and zero SSP retries were observed on that boot.

### 2026-11-20 — Ordinary IPv4 application failover from Wi-Fi to LTE

The explicit bounded fallback probe requires an active qualified context,
exact model and backup checks, a verified direct USB management path and
the current Wi-Fi profile. It installs a temporary higher-metric rmnet0
default and validates that an ordinary, unbound curl process still uses
Wi-Fi. It then disconnects Wi-Fi and verifies that LTE becomes the default.
The probe configures modem DNS on the LTE link for that phase and sets a
temporary systemd recovery timer for the existing Wi-Fi profile.

Native44 verified HTTPS204 while Wi-Fi was preferred. With Wi-Fi
disconnected, an uncached system-resolver query selected rmnet0 and an
unprivileged, unbound curl used the modem IPv4 address and returned
HTTPS204. Modem interface counters advanced RX9/TX12, with zero errors.
After cleanup the old Wi-Fi profile and default were restored, and a new
unbound HTTPS204 request used Wi-Fi again. The recovery timer and service
were gone. The same sensor service remained active through the trial.
The test intentionally stopped Wi-Fi and set per-link DNS during the
fallback phase. It does not enable system-wide automatic LTE at startup,
monitor Wi-Fi transitions continuously, or qualify IPv6 failover.

A distinct normal cleanup boot restored the modem-off state, Wi-Fi default,
and all three driver services. Accelerometer and illuminance were readable,
with zero failed units, zero error-priority lines, 63 warnings and zero SSP
zero-ACK retries on that boot.

### 2026-11-20 — Route and resolver ownership tied to the live LTE context

The bounded isolated RIL can publish an expiring IPv4 lease in /run for
its exact systemd invocation. Route ownership stays in a separate process
so route and resolver commands do not delay RFS. The owner installs its
metric 20000 default only with a fresh qualified lease. It chooses the modem
DNS only when the modem is the preferred IPv4 default and withdraws its
route when the lease is invalidated, expires, or the RIL exits.

First device trial stopped before route or Wi-Fi changes. An IPv4-filtered
address query returned no records for the empty modem interface and the
preflight wrongly indexed that result. The corrected test uses the
family-neutral link address view, and accepts only an empty address list.
A read/write clock-race tolerance was also added for atomically renewed
leases. Unit coverage checks missing, expired and invalid leases.

Native44 then passed ordinary unbound nonroot HTTPS204 on preferred Wi-Fi,
on LTE after test-controlled Wi-Fi disconnect, and again on restored Wi-Fi.
An uncached system lookup selected rmnet0 during LTE. The route owner
enabled and reverted LTE DNS in response to the default route, rather than
the harness configuring DNS. A controlled PDP cycle removed generation 1
and installed generation 2 in the same RIL session. Both route teardowns
reported success. Sensor invocation and feeds stayed available. The RIL
and route worker stopped and left only the Wi-Fi default, no modem lease
and no active modem mount tree before the guarded cleanup reboot.
This remains a bounded opt-in test with normal service teardown. It does
not qualify an abrupt route-worker kill, autonomous radio reconnect or an
installed boot-time LTE service.

The distinct cleanup boot returned to modem off with the Wi-Fi default, all
three driver services active, readable accel and ALS, and no failed units.
The ring had 63 warnings and two error-priority SSP zero-ACK retry lines.
These intermittent startup retries remain open.

### 2026-11-20 — Recover LTE route state after the route worker is killed

The route owner writes a private, boot-scoped ownership receipt on tmpfs
before its first interface mutation. It uses an explicit address label and
route protocol tag. The common cleanup path checks the original ifindex,
address, route marker, MTU and resolver scope. Unrelated modem-interface
configuration causes cleanup to stop and retain the receipt for review.
Use the owner's cleanup mode as systemd ExecStopPost so recovery also runs
when the worker cannot execute its normal shutdown handler.

Native44 verified ordinary HTTPS204 and active modem DNS with Wi-Fi down.
The route worker was then actually killed with signal 9. systemd ran cleanup,
which removed the address, route, resolver settings and receipt and restored
the original link state. The RIL and the sensor service stayed in their
original invocations. Restoring Wi-Fi returned unbound HTTPS204. The test
did not restart the route worker automatically, and did not simulate radio
loss or modem failure. There is no boot-time LTE service installed.

The distinct cleanup boot restored the Wi-Fi default, modem-off state and
all three driver services. There were no failed units. The boot ring had
63 warnings and one error-priority SSP zero-ACK retry, which remains open.

### 2026-11-20 — One-shot LTE startup from systemd at boot

Added a boot-session controller and an opt-in unit example. The controller
checks the private configuration pin, all launcher sources, the exact
running SM-G965N BOOT, current backup, qualified stock overlay and module,
and existing private NV provenance. One arm is consumed before module
loading and one start is allowed per boot. The launcher keeps its RIL,
CBD and lease-based route owner in a bounded session with an
ExecStopPost cleanup. It does not load a second modem onto a running CP.

On native44, the enabled unit started after a distinct normal reboot
without an SSH start command. It consumed its arm and brought up the
modem data route. Ordinary nonroot HTTPS204 was verified on Wi-Fi,
on LTE after Wi-Fi interruption, and again on restored Wi-Fi. An uncached
system DNS query selected the modem link in the LTE phase. The sensor
service stayed active. Stopping the controller removed its isolated
runtime, temporary routes and lease records. The test unit was disabled
afterward and a normal cleanup reboot was requested. This qualifies
one-shot guarded boot startup and real IPv4 data, with continuous
operation and spontaneous packet-data loss recovery still pending.

The cleanup reboot restored the Wi-Fi default, modem-off state and all three
driver services. Accel and illuminance were readable and no unit failed.
There were 63 warnings and one error-priority SSP zero-ACK retry.

### 2026-11-20 — Five-minute LTE startup soak and Ubuntu WWAN prerequisite

The qualified boot controller can explicitly select a 300-second held
session. The isolated boot companion and route owner are bounded above
the RIL deadline so the RIL can finish release and drain first. Default
trial limits remain in place.

Native44 started the extended unit automatically after a distinct boot.
Modem-bound, uncached DNS and certificate-verified HTTPS204 passed at
26.0, 135.7 and 270.7 seconds. All three samples had nonzero RX/TX and
zero interface errors. The same RIL and sensor invocation persisted, and
the RIL logged 13 RFS command events. Natural expiry produced a successful
PDP release, acknowledged RF low power, the completed tail drain and
controller exit. The route, lease and runtime were removed. User-space
bounded units were disabled after the test. Persistent boot enablement
and unattended packet loss recovery are still separate work.

For the owner's Ubuntu Mobile Network request, installed and enabled
Ubuntu ModemManager and its mobile provider database on the actual
handset, with NetworkManager WWAN enabled. Stock ModemManager 1.23.4
returned no modems while the SM-G965N native modem module was present.
The Samsung IPC/AT access nodes are in the miscellaneous subsystem;
rmnet0 is a data netdev. This confirms a missing native control adapter,
not missing LTE packet connectivity. GNOME Mobile Network UI control
has not been qualified. No probe tags were forced onto the raw ports.

### 2026-11-20 — Associate G965N cellular ports with the real modem device

The native module can opt in to linking only the primary Samsung router
control port and rmnet0 data interface to their shared platform modem
device. Other SIPC channel parents and legacy behavior are preserved.
The option is off by default and does not expose the raw router as a
generic AT modem.

Rebuilt the module for native44. On the handset, umts_router and rmnet0
moved from separate virtual sysfs paths to one mif_sipc5 platform
parent. umts_ipc0 and rmnet1 stayed virtual, and the device names did
not change. A cold LTE trial with the option enabled passed source-bound
DNS and certificate-verified HTTPS204, RX10/TX9 and zero RX/TX errors.
The Wi-Fi default was preserved and the temporary route restored.
With the candidate running actual LTE, stock ModemManager 1.23.4
still reported no modems, so the GNOME mobile network controls remain
unavailable. The sensor service and both feeds stayed up.

A distinct cleanup boot restored modem off and the Wi-Fi default.
Audio, Bluetooth, sensors and ModemManager were active, with readable
accel/ALS and no failed units. The ring recorded 63 warnings and one
error-priority SSP zero-ACK retry, which remains open.

### 2026-11-20 — Serialized WWAN query channel for the native adapter

Added an opt-in root-private Unix socket to the guarded isolated held
RIL. The exact RIL invocation owns the socket. Three typed queries use
the existing AT dispatcher and the original command/response serialization.
A different request does not send a command. The socket returns only
the registration code, packet-attach state, or RSSI code. It does not
expose raw AT, location, SIM identifiers, PIN operations, or control
commands. Modem loss and teardown invalidate the outstanding request.

On native44 with the physical modem parent candidate, the read-only
queries returned EPS registration state 1, attached packet service and
RSSI code 21, while the existing bearer passed modem-bound DNS and
certificate-verified HTTPS204. Invalid request rejection, root co-owned
socket permissions, unchanged sensor invocation and socket removal on
stop were verified. Stock ModemManager still did not enumerate this
modem. This qualifies the real status-query boundary for a future adapter.
It does not qualify desktop controls or NetworkManager bearer handoff.

The distinct cleanup boot returned to Wi-Fi and modem off. Audio,
Bluetooth, sensors and ModemManager were active, accel/ALS were
readable, and no unit failed. The ring had 63 warnings and one recurring
SSP zero-ACK retry.

### 2026-11-20 — Explicit LTE data connect and disconnect for the WWAN adapter

Added a separately opted-in bearer control mode to the existing RIL
socket. The first IPv4 session waits for an explicit request. The socket
reports request acceptance separately from modem completion, withdraws the
lease at disconnect, and only permits another activation after confirmed
release and fresh registration and packet-attach queries.

The first native44 attempt exposed a socket reset when querying bearer
state during AT startup. Read the fixed request before waiting on the AT
dispatcher and allow bearer state queries during startup. A subsequent
attempt was stopped by the sensor readiness guard before loading the
modem. The next attempt qualified the first bearer but used a stale
traffic probe without generation selection. It was cleaned up and rerun
with the current pinned probe.

The final trial started idle with no lease. On the same RIL invocation,
two explicit connects passed modem-bound DNS and certificate-verified
HTTPS204, each with its own data generation. Both disconnects obtained
the exact release acknowledgment and matching inactive status, removed
the lease, and remained idle until another explicit request. Invalid
requests and duplicate connects were rejected. The probe restored its
temporary routes, sensors remained active with both feeds readable, and
the socket disappeared at teardown. Stock ModemManager remained active
and reported no modems. Ubuntu's desktop Mobile Network controls still
need the Samsung IPC adapter and NetworkManager bearer handoff.

The cleanup boot restored the Wi-Fi default and left the lab modem
unloaded. ModemManager, sensors and Bluetooth were active with no failed
units and readable acceleration and light sensors. The kernel recorded
63 warnings and one SSP transmit retry.

### 2026-11-20 — Native44 sensor transmit timing trial

Tried an opt-in 4–5 ms wait before the first checked sensor-hub write,
using a pinned module for the existing kernel and a saved startup profile.
The first two activation attempts stopped before applying any change.
The preflight incorrectly treated a disabled service and absent transient
units as command failures. The corrected preflight verified they were
inactive and applied the experimental profile for one boot.

The hardware loaded the option, but still logged one zero-byte
acknowledgment for a 36-byte write. The sensor service reached active and
acceleration and light readings were available. Restored and verified the
original module, profile and service on a distinct boot. The restored
system had no failed units, 63 kernel warnings and one zero-byte SSP
retry. The timing change was discarded. The retry remains open.

### 2026-11-20 — Real SIM readiness and radio state for the WWAN adapter

Added two read-only socket requests for SIPC SIM readiness and the
confirmed normal radio state. This state comes from the existing modem
owner and can be read without waiting on the AT dispatcher. Unknown
radio state is reported explicitly. The SIM readiness result carries
no unlock reason or SIM identity.

The native44 handset reported ready SIM and normal radio state during
two explicit LTE data connections and after both confirmed releases.
Both data generations passed modem-bound DNS and certificate-verified
HTTPS204. Sensor service identity and readings remained available
through teardown. This verifies the adapter's state inputs. The native
ModemManager plugin linked and loaded on a separate x86-64 build.
Device enumeration and the desktop data controls still need hardware
verification.

The cleanup boot restored the Wi-Fi default and left the trial modem
unloaded. ModemManager and the sensor service were active. Acceleration
and light readings were available, with no failed units. The kernel
ring reported 63 warnings and one SSP zero-byte retry.

### 2026-11-20 — Match desktop LTE requests and cancel by data generation

Added an explicit APN match against the guarded radio owner's
configuration and a generation-scoped cancel operation. Cancel can
drop a queued connection immediately. Once activation has begun it
waits for the current modem transition before attempting release.
The first hardware run found a gap in the traffic probe journal after a
queued cancellation. Recorded the invalidated generation explicitly.
The second run verified generation 2 data but exposed the probe's old
two-generation argument limit. The probe now accepts the positive
generation range used by the broker.

The third native44 trial rejected a mismatched APN, canceled generation
1 while queued, and rejected its stale cancel after a later connection.
Both generations 2 and 3 passed modem-bound DNS and certificate-verified
HTTPS204. A generation-specific cancel of the established context and a
regular disconnect each returned to idle after exact release evidence.
Sensor readings and the existing Wi-Fi route survived the trial.
Cancel during an outstanding activation acknowledgment and operation
through GNOME or NetworkManager remain to be checked separately.

The final cleanup boot restored the Wi-Fi default with the trial modem
unloaded. ModemManager and the sensor service were active and both IIO
feeds were readable. There were no failed units, 63 kernel warnings and
two SSP zero-byte transmit retries.

### 2026-11-20 — First ARM64 ModemManager LTE session on the handset

Cross-built the reviewed SIPC adapter against the pinned Noble 1.23.4
source. Tested the resulting ARM64 daemon and plugin on the exact
native44 device in a private D-Bus session. Temporary udev metadata
was isolated to its namespace. The plugin selected the actual physical
rmnet0, exported a SIM based on confirmed modem readiness and enabled
the modem. An explicit IPv4 APN request through ModemManager Simple
Connect produced a qualified bearer on rmnet0.

With that bearer active, modem-bound DNS and certificate-verified
HTTPS204 passed. The scoped traffic probe then removed its temporary
network state. ModemManager Bearer Disconnect obtained a confirmed
release, and the RIL returned to idle without a data lease. Wi-Fi and
the running sensor service survived. Stock ModemManager continued to
report no modems. Generic inherited AT callbacks logged unavailable
serial ports. System NetworkManager configuration and GNOME settings
still need direct verification.

Published the adapter source, narrow upstream patch and pinned build
entry point. A fresh invocation reproduced the ARM64 executable and
plugin from the same source contents. The cleanup boot restored the
Wi-Fi default and unloaded trial modem. Sensors and stock ModemManager
were active, both IIO feeds were readable and no unit failed. The
kernel had 63 warnings and two SSP zero-byte retries. No stock services
or partition contents were replaced.

### 2026-11-20 — System NetworkManager LTE traffic through the ARM64 adapter

In a separate native44 trial, the reproduced ARM64 adapter temporarily
owned the system ModemManager name using a runtime service override.
The built-in Ubuntu NetworkManager activated a temporary GSM profile
and installed an IPv4 default route through rmnet0 at metric 20000.
Wi-Fi retained the preferred default. With those routes installed by
NetworkManager, LTE-bound DNS and certificate-verified HTTPS204 passed.
The standalone LTE route worker and temporary policy probe were not
used in this test.

NetworkManager disconnected the profile and removed the LTE route.
The RIL confirmed release and withdrew the IPv4 lease. Removed the
temporary profile and runtime override, verified that the installed
ModemManager binary was running again, and canceled the rollback
timer. No user profile or reserved partition was modified.
A distinct cleanup boot confirmed Wi-Fi, stock ModemManager and
readable acceleration and light feeds with no failed units. The
kernel had 63 warnings and one SSP transmit retry. GNOME settings
interaction and persistent use remain unqualified.

### 2026-11-20 — Desktop LTE boot startup and system switch cycle

The first system switch trial confirmed off released the LTE context
and removed its route. Its on check mistook NetworkManager's activating
profile for a ready bearer. Corrected the check to wait for the live
lease and installed route. The next warm boot had no Wi-Fi default
and the trial stopped before replacing ModemManager. NetworkManager
recorded a supplicant disconnect after association. Reconnecting the
existing Wi-Fi profile restored the default route without changing the
profile or driver. The Wi-Fi trigger is still unconfirmed.

An exact-model, pinned one-shot service then ran on a distinct native44
boot and disabled itself. It used the reproduced ARM64 adapter and the
system NetworkManager. Setting `WwanEnabled=false` removed the LTE route
and released the bearer. Turning it on again automatically activated
the temporary GSM profile and created a new bearer. Both LTE
generations passed DNS and certificate-verified HTTPS204, with the
second repeating after 30 seconds. Wi-Fi retained its preferred route.
Turning mobile data off a second time verified release and route
cleanup again.

The service ended successfully, restored the installed ModemManager and
WWAN switch state, and deleted the temporary GSM profile and service
override. The one-shot service remained disabled. Direct GNOME UI
interaction and continuous startup remain unqualified.

### 2026-11-20 — Locate the recurring sensor hub short acknowledgment

Added opt-in, rate-limited SSI diagnostics for transaction number,
attempt, acknowledgment, status, advertised credit and MCU-ready state.
The metadata excludes frame contents. The supervisor requires checked
ACK mode and the matching module parameter before enabling collection.

On an exact native44 boot, the 36-byte write that received no
acknowledgment was the first attempt of transaction 455. The MCU-ready
line was high. The previous advertised credit was 12288 bytes, while
the response status and advertised credit were zero. The checked retry
path recovered and acceleration and light readings remained available.
This localizes the retry beyond the first stream write and establishes
what the host saw. It does not identify why the receiver returned zero.

Restored the original sensor profile and module on a separate boot.
Acceleration and light remained readable, Wi-Fi held the preferred
route and no unit failed. The diagnostic option was absent from the
loaded module. The kernel had 63 warnings and one SSP retry.

### 2026-11-20 — Keep desktop LTE alive beyond the bounded modem trial

Added an explicitly selected lifetime mode for the isolated WWAN
launch path. It requires the desktop LTE supervisor to be active.
Both RIL and CBD bind to the same supervisor and run without the
old child deadline. The new mode excludes lab trace capture and
retains the exact-model and private runtime checks.

On native44 the system NetworkManager connected a temporary profile
using the ARM64 adapter. The same bearer and RIL invocation passed
real LTE DNS and certificate-verified HTTPS204 at 0.7, 90.6 and
306.5 seconds. CBD was still active at every sample. Wi-Fi kept its
preferred default, and the test released the bearer, removed the
profile and restored stock ModemManager. The test supervisor itself
was bounded. A persistent boot installation and unexpected-stop
recovery still require separate verification.

### 2026-11-20 — Opt-in desktop LTE on ordinary boots

Added a pinned startup supervisor and a systemd unit for the approved
native44 profile. It verifies model, kernel, backup, module and
program digests, then starts the isolated modem stack and lets
NetworkManager create the LTE route. An optional temporary GSM
profile waits for the system WWAN setting to allow activation.

Manual service start passed LTE DNS and HTTPS204. The first stop
released the context and reached radio low power, but the explicit
ordering after ModemManager delayed its restart until a timeout.
Removed that unit ordering and moved the stock-manager readiness
check into the supervisor. Then verified real LTE traffic on two
distinct ordinary enabled boots, with Wi-Fi preferred. Between the
two boots a normal stop confirmed release ACK and idle indication,
radio low power, no remaining lease or LTE route, and restoration of
stock ModemManager. The runtime profile and private modem mounts were
removed. The service remains enabled and connected on native44.

The second enabled boot had no failed units and readable acceleration
and light values. The kernel ring contained 67 warnings and 121
error-priority messages, including 120 SIPC startup diagnostics and
one SSP zero-byte retry. These messages remain visible. Direct GNOME
interaction, unexpected-stop recovery and extended access after
network loss have not been qualified.

### 2026-11-20 — Check SIPC probe prerequisites and configured features

The enabled modem boot exposed unconditional error messages for absent
ECT frequency tables and a disabled packet logger. The non-ECT build
now skips table lookups and reports the CP frequency-vote limitation
once. Packet logger initialization is conditional on its build option.
Mailbox and shared-memory setup report successful progress at info
level. Mapping failures, malformed metadata and IRQ request failures
retain error handling.

Shared-memory probe now rejects a failed map before accessing the
header, bounds the header to the mapped page, and copies it using the
MMIO accessor. Mailbox probe returns a negative IRQ lookup result
before requesting that IRQ. The failure branches were reviewed and
compiled. The phone exercised the successful paths.

Rebuilt the module for native44 and installed it after the enabled
desktop service released the modem and restored its stock manager.
On the next enabled boot, LTE autoconnect, LTE-bound DNS and HTTPS204,
Wi-Fi HTTPS204, and acceleration and light reads passed. The optional
packet-log failure and repeated ECT error were absent. The full boot
still had 103 error-priority messages and 67 warnings, with no failed
units or SSP retry on this boot. The matched module remains in service.

### 2026-11-20 — Restore desktop state after an abrupt LTE supervisor exit

The desktop service now records the owned modem runtime and RIL
invocation for its stop hook. The hook revalidates the pinned
configuration, stops the child units, detaches the private modem view
under its lock and checks any invocation files before removing them.
The regular stop path uses the same cleanup.

On native44, first verified active LTE DNS and HTTPS204, then killed
only the desktop supervisor. Systemd recorded the expected signal
failure and successful stop hook. The RIL reported bearer release and
radio low power, both child units stopped, and the temporary profile,
route, lease, socket and mount were gone. The stock manager was
running again and the Wi-Fi default remained. This exercises
supervisor loss. Unexpected CP or RIL failure and network loss still
need separate verification.

After the distinct recovery boot, the enabled service automatically
connected again and LTE-bound DNS and HTTPS204 passed. Wi-Fi retained
the preferred route, acceleration and light values were readable, and
there were no failed units. That boot logged 104 error-priority entries
and 67 warnings, including one SSP retry. The service was left enabled.

### 2026-11-20 — Abrupt RIL exit and checked sensor retry completion

Killed the RIL main process while its native44 LTE bearer was active
and Wi-Fi remained preferred. The enabled desktop supervisor detected
the child exit. Its cleanup removed the stale invocation lease/socket,
private mount, temporary profile and LTE route, and restored the
installed ModemManager. Wi-Fi HTTPS204 passed. The abrupt RIL exit did
not provide release or radio-low-power evidence. The distinct reboot
automatically connected LTE again and passed LTE-bound DNS and HTTPS204.

Added a rate-limited, opt-in sensor diagnostic on the successful
checked-ACK completion path. On that reboot, transaction 454 requested
36 bytes with the MCU-ready line high. The first response carried
status 0x00, zero credit and zero acknowledged bytes. About 2.1 ms
later the second attempt acknowledged all 36 bytes with status 0x16
and 12288 bytes of credit. Readable acceleration and light values
and active LTE confirmed that this retry recovered on the device.
The observation does not establish why the first response was zero.

Stopped the active desktop LTE service, verified its normal release,
and restored the original sensor module and profile on a separate
boot. LTE automatically reconnected and passed bound DNS and HTTPS204.
Wi-Fi stayed preferred, acceleration and light remained readable, and
there were no failed units. The kernel logged 104 error-priority
messages and 67 warnings, including one sensor hub retry.

### 2026-11-20 — SIM maintenance readiness

Stopped the desktop LTE session and verified bearer release, radio low
power and Wi-Fi connectivity. Restored the boot enablement after the
maintenance check. The current LTE session remains stopped until reboot.

### 2026-11-20 — LPS22H pressure through Linux IIO

Added an opt-in SSP ID 5 pressure stream to the verified root broker and
IIO bridge. The bridge rejects out-of-range and stale data independently
of acceleration, lux and heartbeats, and registers only after a valid
hardware frame. The scale follows the pinned LPS22H configuration and
the ST datasheet, converting raw counts to the Linux IIO unit of kPa.

Verified the native #44 BOOT and nine-partition backup, saved the original
sensor profile, unit and pins, and hot-replaced only the IIO bridge. The
sensor service stopped cleanly and restarted while the SSP module and
running kernel remained in place. The new service stayed active. An
ordinary Ubuntu user read 300 pressure samples over 60 seconds, with
120 distinct counts corresponding to 101.4119–101.4160 kPa.
Acceleration and lux remained readable at each poll. Wi-Fi-bound
HTTPS returned 204. No new sensor-related kernel warning was reported
after the service reached readiness.

The pre-existing boot log still includes a sensor hub reset-line
warning and one successfully recovered SSP transmit retry. The desktop
LTE unit had already reported that the modem did not provide a ready
SIM on this boot. ModemManager was active and the pressure trial left
the modem untouched. Pressure accuracy against a reference, Android
per-device compensation, and pressure startup after a distinct boot
remain unverified.

### 2026-11-20 — Clean desktop LTE exit without a SIM

The enabled desktop service previously reported a startup failure
after its ready-SIM deadline, even though the modem had twice
reported SIPC card-not-present (0x80). The RIL now reports that
explicit state to the supervisor. The supervisor gives the SIM the
same startup window to become ready, then exits successfully only
if recent polls consistently report absence. An unknown or stale
state, a socket failure, and a child failure retain their error paths.

Verified the exact native #44 BOOT and nine-partition backup before
staging the two scripts and preserving the previous service and pins.
On a distinct normal boot without a SIM, two hardware indications
reported 0x80. The desktop service exited successfully after 44
seconds. The modem children stopped, the private mount and invocation
files were removed, the stock ModemManager stayed active, and
Wi-Fi-bound HTTPS returned 204. There was no LTE default route or
failed systemd unit. The RIL reported that it had not requested the
radio; it did not send a low-power request in this case. The service
remains enabled for a subsequent boot with a SIM.

The same boot automatically restored the pressure IIO device. An
ordinary Ubuntu user read 60 samples over 15 seconds, with 41
distinct counts corresponding to 101.4132–101.4166 kPa. Acceleration
and light remained readable. The kernel ring still held 108
error-priority entries and 67 warnings, including a hub reset-line
warning, two early transmit retries and the Bluetooth capability
notice. SIM-present reconnection on this changed build, hot
reinsertion, and pressure accuracy against a reference remain pending.

### 2026-11-20 — TMD4906 proximity through the stock Ubuntu SensorProxy

Added opt-in SSP ID 7 to the pinned IIO broker and bridge. The hub's
binary detection bit becomes IIO levels 0 (far) and 2 (near), which
straddle the proxy's integer level 1 and its hysteresis. The runtime
requires a real hardware frame before registering the device. On-change
state requires a live broker and is cleared when the broker closes.

After verifying the native #44 BOOT and nine-partition backup, saved
the old sensor unit and profile and hot-replaced the IIO bridge.
The stock `monitor-sensor --proximity` claimed the new sensor and
reported far. An ordinary Ubuntu user read 80 far samples over 20
seconds while acceleration, lux and pressure remained readable.
Wi-Fi-bound HTTPS returned 204 and no systemd units failed. No
warning-priority kernel entries were logged after sensor readiness
in the observation window. Earlier native #23 physical near/far tests
covered the raw hub output. The new Ubuntu path's physical transitions,
distinct boot and suspend/wake behavior remain pending.

### 2026-11-20 — Raw LSM6DSL gyroscope IIO and sensor startup proof

Added opt-in SSP ID 1. The broker forwards three signed 32-bit hub
values and registers the IIO gyroscope only after an actual sample.
The three raw attributes stop returning data when the stream is stale.
The original stock sensor description identifies the LSM6DSL, but the
hub's count-to-radians conversion and axis mapping still require
qualification. The bridge publishes the original hub axes and values.

Verified the native #44 BOOT and nine-partition backup, saved the
previous sensor configuration, and hot-loaded the bridge. On a
distinct ordinary boot, the gyro and proximity started automatically
alongside acceleration, lux, and pressure. An ordinary Ubuntu user
read 100 gyro vectors over 25 seconds, with 12/14/9 distinct counts
by axis. Ubuntu's stock SensorProxy claimed proximity and showed far;
the physical near/far transition was not repeated. Wi-Fi HTTPS204 and
the Wi-Fi Direct control interface were present, with no failed units.
The enabled LTE service completed its no-SIM cleanup at 69 seconds of
uptime, just after the first observation, and passed the subsequent
check. Physical gyro scale/mounting and Wi-Fi Direct peer transfer on
this boot remain unqualified.

### 2026-11-20 — Native44 Wi-Fi Direct discovery and modem ring bounds

Ran three eight-second NetworkManager discovery cycles over the
existing Wi-Fi Direct control interface using USB for management.
Primary Wi-Fi returned HTTPS204 during and after all three cycles,
with the same connection and station interface index. The P2P
device returned to disconnected, and no new Wi-Fi/P2P kernel
warnings or errors appeared. One discovered peer could not be
identified as the intended Fold7. The native44 group and payload
paths remain untested.

The SBD driver now checks channel indexes, 16-bit ring fields, and
the combined descriptor and payload sizes before clearing or
writing shared memory. Host tests exercised rejected layouts and
confirmed that the invalid cases leave shared memory untouched.
The AArch64 module compiled for native #44. The old module,
configuration, and service were backed up after verification of the
running BOOT and nine-partition backup.

A distinct S9+ boot loaded the new module, verified by its live
build ID. All 18 rings fit inside the existing shared IPC region.
The last data buffer ended at 4,276,224 bytes of 5,242,880, and the
driver sent PIF_INIT_DONE. The no-SIM service exited cleanly, the
stock ModemManager stayed active, and Wi-Fi HTTPS204 and five IIO
devices passed startup checks. The successful path was exercised on
the handset. Out-of-bounds layouts were tested on the host.
SIM-present data traffic with this module remains pending.

### 2026-11-20 — Validate the modem controller's IRQ resources

The verified Exynos9810 overlay uses the PMU for modem reset and has
no legacy CP reset GPIO. The port's integer GPIO shim always returned
absent, which the controller had reported as an invalid pin. The
controller now rejects unsupported GPIO configurations explicitly and
validates both required Linux IRQs before registering either. If a
later IRQ registration fails, the controller releases the registrations
it acquired. The caller propagates the original setup errno, including
probe deferral.

After verifying the running native #44 BOOT and backup, saved the old
module pins and installed the matching candidate. A distinct S9+ boot
confirmed the loaded build ID, registered CP_FAIL and CP_WDT handlers,
and reached PIF_INIT_DONE without the previous invalid-GPIO error.
The no-SIM service exited successfully, Wi-Fi HTTPS204 passed, all five
IIO devices returned readings, and systemd reported no failed units.
Host fault-injection covered missing resources and failed interrupt
registrations. Actual fail/watchdog interrupt delivery and SIM-present
LTE traffic with the changed module remain pending.

### 2026-11-20 — Board thermistor readings through Linux IIO

Compared the public Exynos9810 revision 26 UP/SUB calibration
tables with the verified stock device tree. Both 23-point tables
matched. The optional broker path checks the live revision and
hub advertisement, then reads ADC channels 0 and 1 every five
seconds. It uses the matched tables to interpolate valid values
and makes the pair available as standard IIO millicelsius
readings. A failed reading skips the pair, and the bridge expires
old values even while other sensor data remains fresh.

Verified the #44 BOOT and backup and saved the original sensor
profile before hot-loading the matching bridge. An ordinary Ubuntu
user read 180 pairs over 45 seconds. Nine pairs were distinct.
Channel 0 reported 32.2–32.4 °C and channel 1 reported 28.7–29.1 °C.
Acceleration, gyro, lux, proximity and pressure remained readable
throughout. Wi-Fi HTTPS204 passed and there were no thermistor retry
messages or new sensor kernel warnings following readiness in
this window. Absolute accuracy, a distinct restart and thermal
or charging policy behavior remain separate verification items.

### 2026-11-20 — LPS22H die temperature and thermistor startup

The pressure sensor's SSP sample now supplies its signed temperature
alongside pressure on the same IIO device. The broker keeps forwarding
pressure when the temperature is unavailable. The bridge accepts
legacy pressure-only frames, and rejects or expires invalid or stale
temperature instead of substituting a value. The pinned factory code
formats the SSP field as hundredths of a degree Celsius. The IIO
`in_temp_input` attribute reports millicelsius.

Verified the running #44 BOOT and backup and staged a matching
broker and bridge with the original profile preserved. The first
local staging command stopped on a path mismatch before reaching
the handset; the corrected staging and normal reboot passed.
An ordinary Ubuntu user read the new die channel 160 times over
40 seconds. It reported 38.00–38.27 °C with 28 distinct values.
Pressure continued to read 101.3816–101.3856 kPa. The board
thermistors started on the same boot and produced nine distinct
pairs. All six IIO devices were readable, Wi-Fi HTTPS204 and no-SIM
cleanup passed, and no systemd unit failed. No thermistor read
failure was logged in the observed boot. Reference calibration
and thermal/charging policy remain unqualified.

### 2026-11-20 — Shorter sensor hub startup on native44

The original warm startup held the hub in standby for 1, 3 and 9
seconds. MCU_RESP read high during and after all three holds. The
sensor service eventually reached readiness in 21.783 seconds.

Added an explicit boot option that performs only the first standby
attempt, leaving the original power, pin, manual reset and default
startup policies in place. The driver now reports a high MCU_RESP
as an unconfirmed reset and propagates a GPIO read error instead of
interpreting it as a low response. The checked transport and live
hub and sensor readiness requirements still gate the service.

Verified the #44 BOOT and backup, saved the previous profile, and
staged the matching transport and supervisor. Two distinct normal
reboots with the option enabled reached sensor-service readiness in
9.046 and 8.974 seconds. There was one 1-second standby attempt and
one recovered zero-ACK write retry on each boot. The warning
remained because the hardware reset was unconfirmed. Both boots
passed six live IIO reads, Wi-Fi HTTPS204, P2P interface presence and
normal no-SIM cleanup without failed systemd units. Cold boot and
suspend/resume with the option remain unqualified.

### 2026-11-20 — Screen-only background operation and suspend preflight

Verified the active native44 BOOT and backup, and that the installed
button handler matched the repository. The first proof command
stopped on the nonzero status returned by `systemctl is-enabled` for
a masked unit. The corrected proof read UnitFileState and used the
installed handler's normal display method as the desktop user.

In two 8.2-second intervals Mutter reported display power off and the
panel CRTC became inactive. A background process successfully read
all six IIO devices 32 and 33 times, with maximum sample gaps of
253.8 and 255.9 ms for a 250 ms target. Wi-Fi HTTPS204 passed before,
during and after. The original display and session lock state were
restored, with the same boot and handler process.

The running kernel lists only `s2idle` under `mem_sleep` and has no
RTC class device. Stock revision 26 describes the on-SoC RTC with
the Exynos8 variant, whose stock driver skips explicit clock control.
The pinned Ubuntu kernel has the S3C RTC driver built in, but lacks
the Exynos8 match and a live RTC device-tree node. Sleep targets
remained masked. This check qualifies screen-only background
operation; physical power-key behavior, suspend wake and comparative
battery drain still require hardware tests.

### 2026-11-20 — Fix sensor firmware watchdog cancellation

Replaced the firmware patch timer and its second queued callback with a
single native Linux delayed work item initialized once. Repeated starts,
completion and teardown now synchronize with the previous work before
continuing. Delay conversion is bounded before multiplication. The
optional statistics timer also uses the native callback signature.
The AArch64 #44 build no longer emits the incompatible timer function
pointer warning. Host cases exercised rearm, cancel, expiry and teardown.

Verified the #44 BOOT and backup, saved the previous sensor profile and
staged the matching module. On a distinct handset boot the loaded build
ID matched. Firmware armed the 10-second watchdog and canceled it after
1.272 seconds. Six IIO devices continued to deliver 80 reads each over
20 seconds, including beyond the original watchdog deadline, without a
reset request. Wi-Fi HTTPS204 and no-SIM cleanup passed and no unit
failed. Intentional watchdog expiry was qualified on the host only.

### 2026-11-20 — Isolate each BBD control command

The control character device previously reused storage across opens and
could pass leftover bytes or a partly copied command to its string parser.
Each write now owns a bounded, NUL-terminated copy. Failed copies are
returned to the caller before dispatch. Existing bounds, command syntax
and successful byte counts are preserved. Host tests cover writes with
and without a supplied terminator, length bounds and failed copies.

Built against native #44 and verified the BOOT and backup before changing
the sensor service module pin. On a distinct warm boot the loaded build
ID matched, and normal LHD startup armed and canceled the firmware
watchdog in 1.277 seconds. All six IIO devices passed 80 reads each over
20 seconds. Wi-Fi-bound HTTPS204, P2P interface presence, successful
no-SIM cleanup and zero failed units were observed. No sensor reset
request was logged. The boot journal still contained 105 modem IPC/RFS
error-priority messages and one SSP error-priority message in the
observation window. Failed-copy cases ran on the host; a peer transfer
and SIM-present reconnection were outside this handset trial.

### 2026-11-20 — Distinguish modem SBD setup progress from failures

The preceding no-SIM boot reported 44 ordinary SBD setup and descriptor
messages as errors. Moved those details to debug logging without
kernel addresses. Successful initialization now reports the number of
rings and the final data buffer offset. Layout rejection and ring
initialization failure each report the original errno. Host tests
exercise both failure stages and require a summary only on success.

Built against native #44, checked the BOOT and backup, and staged the
replacement module while saving the original module and service
configuration. A distinct handset boot confirmed the loaded build ID,
18 rings and a data buffer end of 4,276,224 within 5,242,880 bytes.
PIF_INIT_DONE was sent, none of the 44 SBD lines recurred at error
priority, and 62 other error-priority messages remained. The no-SIM
service stopped successfully and stock ModemManager was active. Six
IIO devices were readable, Wi-Fi HTTPS204 passed, a P2P interface was
present and no units failed. SIM-present traffic and P2P transfer were
not exercised on this boot.

### 2026-11-20 — Preserve an early cellular boot completion

The BOOT_OFF wait previously reinitialized the CP completion even if
the shared-memory CP_START handler had already completed the handshake.
BOOT_ON now clears the completion while resetting the link state under
the same lock used by the completion producer. BOOT_OFF only waits.
The driver harness verifies that a new boot clears the previous signal,
an early CP_START satisfies the later wait, and no signal still returns
the original timeout error without enabling the watchdog.

Built for native #44, checked BOOT and backup provenance, preserved the
previous module and service configuration, and booted the exact new
module. The handset followed the normal order: BOOT_OFF preceded
CP_START, INIT_END was sent once, the modem reached ONLINE, and the
watchdog IRQ was enabled. There was no boot-completion timeout.
No-SIM shutdown, stock ModemManager restoration, six IIO devices and
Wi-Fi HTTPS204 passed, with a P2P interface present and no failed units.
The early signal and missing signal were qualified on the host only.
This boot did not exercise SIM-present data or P2P file transfer.

### 2026-11-20 — Respect manual Wi-Fi disconnect during recovery

The recovery service treated NetworkManager's disconnected state as
retryable even when the user had blocked device autoconnect. It now
requires the device's autoconnect permission on each sample and
rechecks the device before activating an eligible saved profile.
Host tests cover manual disconnect, a late change before activation and
missing device permission alongside the automatic retry path.

Checked the model and BOOT/backup provenance, saved the original service
script and applied the new one. The running service left a real
NetworkManager device disconnect in place for 72 seconds, past two
polling intervals. Manually reactivating the original profile restored
Wi-Fi and HTTPS204. The guard remained active; no unit failed and no
new Wi-Fi/P2P kernel warnings or errors appeared in that window.

After manual reconnection, three 10-second stock NetworkManager P2P
find/stop cycles also passed. The original Wi-Fi profile and interface
index stayed the same, with Wi-Fi HTTPS204 during and after every cycle
and no new Wi-Fi/P2P warning/error. One peer was reported; its name
and previously verified address did not identify it as the Fold7.
No group connection or transfer was attempted with that peer.

### 2026-11-20 — Bound modem packet previews to the available packet data

Replaced the modem diagnostic formatter's variable-length stack array
with the kernel hex formatter. The existing preview limit is 16 bytes.
The skb path now obtains the prefix through the kernel accessor that
can read from fragments, and skips formatting if those bytes cannot be
read. The host harness covers empty, short, capped and fragmented
previews and the accessor's failure path. The native #44 module no
longer emits the packet formatter's variable-length-array warning.

Checked the model, BOOT and backup, preserved the previous module and
configuration, and verified the new build ID after a distinct warm boot.
All nine real modem packet previews had the expected lengths and
format, including two capped at 16 bytes. Modem initialization and
no-SIM shutdown passed. Six IIO devices, Wi-Fi HTTPS204 and the P2P
interface remained available, and no unit failed. Packet contents were
excluded from the evidence. Fragment handling was verified on the
host; the no-SIM boot did not verify LTE traffic.

### 2026-11-20 — Reject incomplete sensor SPI responses

The sensor transport now requires the SPI controller's reported actual
length to match the request before returning success or logging the
response. A mismatched length returns EIO. An explicit controller error
still returns its original errno. Host tests covered success, short and
empty transfers reported as successful, and a controller error return.

Built for native #44, checked BOOT and backup provenance, and saved the
previous pinned sensor profile and module before staging. A distinct
handset boot confirmed the exact module build ID, hub firmware startup
and watchdog cancellation after 1.277 seconds. Six IIO devices delivered
80 reads each over 20 seconds. Wi-Fi HTTPS204 and no-SIM cleanup passed
with a P2P interface and zero failed units. One 36-byte write still
needed its checked ACK retry despite the controller reporting the
expected length. The check rules out a reported short transfer for
that retry; physical bus timing remains unmeasured.

### 2026-11-20 — Time the sensor firmware ACK retry

Extended the existing opt-in short-ACK diagnostics with the duration
of the SPI call, time and size of the preceding accepted transaction,
and before/after HOST_REQ and MCU_RESP samples. The timing is observed
by the host, with no frame contents logged by the new diagnostics.

After checking model, BOOT and backup and preserving the previous
sensor configuration, booted the exact #44 module with diagnostics
enabled. The 36-byte transaction received a zero ACK after a 39.8 us
SPI call, 49.249 ms after a complete 14-byte transaction. HOST_REQ was
low at both samples and MCU_RESP high at both. The second attempt
accepted all 36 bytes. The patch finished 146.8 ms after the short
ACK. All six IIO devices delivered 80 samples each, Wi-Fi HTTPS204 and
no-SIM cleanup passed, and no unit failed. A short previous-transfer
gap was not present in this observation; neither the GPIO samples nor
the host timestamps measure sub-transfer edges or prove a root cause.

Restored diagnostics to the default off setting with the same module
binary on a second warm boot. All six IIO devices, Wi-Fi HTTPS204 and
no-SIM cleanup passed again. The default boot logged two zero ACK
attempts for 36-byte writes, with no reported length or controller
errors. On this setup the board's hardware SPI path programs prescaler
3 independently of the advertised device speed. The timestamps above
measure the driver's elapsed time and do not establish SCK frequency.

### 2026-11-20 — Reject the local SPI divider as a verified speed control

Checked the model, BOOT and backup, and saved the original sensor profile
and unit before booting the same native #44 module with a private trial
profile requesting prescaler 7 instead of 3. The running parameter was 7,
but both controller clock register reads returned zero instead of the
value written by the driver. The 36-byte zero ACK still occurred once and
recovered on the second attempt. Patch, six IIO devices, Wi-Fi HTTPS204,
and no-SIM cleanup passed. This experiment did not establish a different
physical SCK frequency and cannot rule out sensitivity to clock rate.

The [LineageOS Exynos9810 clock register definitions](https://github.com/LineageOS/android_kernel_samsung_exynos9810/blob/6a9461f9460ca51d1217e5069a5d5556fcc79e63/drivers/soc/samsung/cal-if/exynos9810/cmucal-sfr.c)
identify the CHUB USI00 divider and mux in the clock management unit.
The [clock node definitions](https://github.com/LineageOS/android_kernel_samsung_exynos9810/blob/6a9461f9460ca51d1217e5069a5d5556fcc79e63/drivers/soc/samsung/cal-if/exynos9810/cmucal-node.c)
connect that divider to the same USI00 input-clock gate the board driver
already opens. No clock management register was changed in this trial
beyond the board driver's existing setup.

Restored the saved sensor profile and verified prescaler 3 and
diagnostics off on a distinct warm boot using the same module. One
zero ACK recurred. Firmware startup, 80 reads from each of six IIO
devices, Wi-Fi HTTPS204 and no-SIM cleanup passed with no failed units.

### 2026-11-20 — Test the CHUB USI00 clock management divider

A read-only snapshot on the running #44 handset showed the CHUB USI00
divider field at 0, mux select 1, and the input-clock gate at 0x00300000.
The local SPI clock register read zero. The model, BOOT and backup
checks passed before the existing sensor module and profile were
saved for a bounded trial. The first test module build hit a kernel
macro name collision; renaming the local readback variable fixed it.

The trial module changed only the identified USI00 divider field from
0 to 1 during board setup. The field was stable on repeated setup and
on an independent live read. This boot still had two zero ACKs in one
36-byte transaction; the third attempt accepted all bytes. The first
two SPI calls took 44.3 and 41.9 us, comparable to the earlier
39.8 us reference. The physical SCK rate was not measured. Firmware
startup, six IIO devices, Wi-Fi HTTPS204 and no-SIM cleanup passed,
with no failed units. No production clock change was selected.

Reinstalled the saved module configuration and verified a distinct
warm boot with the USI00 divider field back at 0, diagnostics off, and
the original module build ID. One 36-byte zero ACK recovered. The
firmware watchdog canceled normally, all six IIO devices delivered
80 reads, Wi-Fi HTTPS204 and no-SIM cleanup passed, and no units failed.

### 2026-11-20 — Test additional sensor SPI chip-select setup time

The board source documents a timeout when the whole firmware patch
uses GPIO-driven SPI. Kept the hardware controller and used the SPI
core's chip-select setup interval to vary only the time between
asserting chip select and starting a transfer. Verified model and BOOT
backup, saved the original module profile, built a private native #44
module, and verified the exact binary on a distinct warm boot.

With an added 25 us configured interval, the 36-byte transaction
still returned one zero ACK. The first SPI call took 89.9 us and
started 48.160 ms after the previous accepted 14-byte write. The
second attempt accepted all 36 bytes. Patch completion, 80 reads from
each of six IIO devices, Wi-Fi HTTPS204 and no-SIM cleanup passed,
with zero failed units. No chip-select setup change was selected
for the production profile.

Restored the saved module and diagnostic-off profile on a second
warm boot. Verified the original build ID and absence of the trial
setting. One zero ACK still recovered; firmware startup, six IIO
devices, Wi-Fi HTTPS204 and no-SIM cleanup passed again.

### 2026-11-20 — Correlate sensor firmware reads and the zero ACK

Extended the existing opt-in diagnostics to mark successful reads
at the beginning and end of the firmware file. The short-ACK log
also reports whether all received SPI bytes were zero, checking
only the length actually transferred. The new messages contain
no firmware bytes or packet payloads.

Checked model, BOOT and backups, preserved the previous sensor
profile and booted the exact instrumented #44 module. The first
36-byte attempt occurred 65.696 ms after the final firmware file
read and returned an all-zero SPI response. The second attempt
accepted all 36 bytes, and patch completion followed. All six IIO
devices returned 80 reads each, Wi-Fi HTTPS204 and no-SIM cleanup
passed, and no units failed. The file-read milestone measures the
loader's read from Linux, allowing later buffered transmission
to remain possible.

On a second warm boot, the same module with diagnostics off emitted
neither file milestone. One zero ACK recovered again. Sensors, Wi-Fi
HTTPS204 and no-SIM cleanup passed.

### 2026-11-20 — Add a scoped settle interval for the firmware tail write

A private #44 trial added 8–9 ms before the 36-byte write that
follows an acknowledged 14-byte write by 40–60 ms during active
firmware loading. The two distinct warm boots each matched once.
Their measured waits were 9.012 and 9.029 ms, and the first attempt
accepted all 36 bytes on both. The preceding gaps were 49.123 and
49.384 ms. No 36-byte zero ACK was reported. Both boots passed patch
startup, 80 reads each from six IIO devices, Wi-Fi HTTPS204 and no-SIM
cleanup, with no failed units.

Added the opt-in `transport.patch_tail_settle` sensor profile
setting. It requires checked acknowledgements and a matching
module parameter. The matched delay runs only while the firmware
watchdog is pending. The regular acknowledgement checks and
retry behavior still apply. Host tests cover capability, default
and disabled checks, unrelated transactions, and the timing window.

The first host run exposed an overly broad control-function test
fixture boundary. Moving the watchdog query outside that fixture
restored the suite and all 378 tests passed.

After verifying model, BOOT and backup provenance, kept a rollback
copy and booted the exact built module with the profile option on
and diagnostics off. The targeted 36-byte write passed on its first
attempt. Zero length/controller errors and zero 36-byte ACK retries
were recorded. Patch startup, all six IIO feeds, Wi-Fi HTTPS204 and
no-SIM cleanup passed again with no failed units. The option remains
enabled on the test handset. Cold starts, other firmware and the
underlying hub transition remain unqualified.

### 2026-11-20 — Revalidate the calibrated magnetometer on native #44

The first staging check compared the calibration provenance to the
current kernel rollback backup. That is a different backup set from
the original stock BOOT and EFS sources, so the check stopped before
changing the sensor profile. Located both original source images
and independently reran the own-backup extractor. It checked the
two partition manifests, reproduced the saved calibration, and kept
the bytes private.

Verified the current BOOT and rollback backup separately, then added
a bounded 28-second capture using the existing pinned profile. The
native #44 handset returned 135 calibrated magnetic samples at
reported quality 3, no overflow, and 155 acceleration samples. The
broker disabled the magnetic channel after capture. All six existing
IIO devices remained readable, Wi-Fi HTTPS204 and no-SIM cleanup
passed, and there were no failed units or 36-byte ACK retries.
Ubuntu's stock SensorProxy still reported no compass to GeoClue.
The stationary trial provides no cardinal or tilt reference and
therefore does not qualify a heading for publication.

Restored the saved profile without magnetic capture or initialization.
A distinct warm boot verified the original sensor module, all six
IIO feeds, Wi-Fi HTTPS204 and no-SIM cleanup with no failed unit.

### 2026-11-20 — Retest display cadence immediately after a native #44 boot

With the running Wayland session unlocked and the accepted Mali-G72
Mesa profile, ran three FIFO scenes each in full-screen, windowed,
then full-screen mode under a temporary idle inhibitor. The established
boot returned 60–61 FPS in all nine scenes. The full-screen surface
was 1440x2960 and the windowed surface 720x1280.

Scheduled a normal warm reboot and started the same sequence at
13.25 seconds uptime. Per-scene results were 58/61/61, 59/61/61,
and 61/61/61 FPS. GPU clock samples ranged 260–572 MHz, GPU
temperature 53–58 C, and the big CPU sensor reached 80 C. Neither
test window had a matching new GPU/display fault. The early boot
also reported zero DECON latch wait timeouts, one successful
firmware tail settle with no 36-byte ACK retry, Wi-Fi HTTPS204,
and no failed units. No display or clock policy was changed.
The historical 11 FPS result did not recur. GNOME overview animation
and long playback endurance were outside these tests.

### 2026-11-20 — Measure real GNOME app-list transitions on native #44

Built the pinned Linux uinput source as a temporary native #44
module and used GNOME's configured Super+A shortcut. The cross
compiler lacked userspace headers, so the keyboard helper was
compiled on the handset.
The first attempt incorrectly used that shortcut to close the
overview as well. It left the overview visible and the cleanup
still unloaded the input module. The corrected run used Escape
to return to the desktop, with session state verified after
each of five opens and five closes.

The built-in GNOME profiler measured paint-view p95 of 18.378 ms
and frame-clock dispatch p95 of 24.596 ms in the 800 ms windows
after opening. Five of 65 paint marks exceeded 16.7 ms. Closing
had paint p95 4.280 ms and dispatch p95 6.299 ms, with a 65.466 ms
maximum dispatch. These are compositor operation durations.
The desktop was restored and the temporary module unloaded,
with zero failed units and zero matching GPU/display faults
in the surrounding three-minute log window. The capture stays
private. The source of the slow app-list work remains open.

### 2026-11-20 — Compare CPU and GPU clocks during app-list transitions

On native #44, ran three bounded A/B/A comparisons using the same
GNOME profiler and four actual app-list opens/closes per phase.
The CPU trial temporarily held the big cluster at its existing
2327 MHz limit. The GPU trial raised the devfreq floor to the
existing 455 MHz step. The task-scoped trial set the GNOME Shell
main thread's minimum utilization clamp to 512 of 1024.

| Intervention | Open paint p95 baseline/trial/restored (ms) | Open dispatch p95 baseline/trial/restored (ms) |
|---|---|---|
| Big CPU performance governor | 21.271 / 17.790 / 22.636 | 30.285 / 23.078 / 30.114 |
| GPU floor 455 MHz | 22.988 / 20.203 / 20.944 | 30.669 / 30.549 / 34.709 |
| GNOME Shell main-thread clamp | 17.795 / 19.450 / 18.060 | 30.999 / 26.576 / 24.514 |

GPU sampling stayed at 260 MHz throughout the CPU comparison's
opening windows. During the GPU trial, 62 of 63 opening samples
showed 455 MHz, with a 1066 MHz median big-cluster frequency in
all phases. Each phase of each comparison still had four paints
above 16.7 ms. The CPU intervention shortened the heavier opening
work, but changing the GPU floor or GNOME Shell main-thread clamp
gave no consistent opening improvement across both controls.

Verified CPU schedutil, GPU floor 260 MHz, original main-thread
clamp, desktop state and temporary input teardown after the trials.
Sensors and Wi-Fi HTTPS204 passed, with no failed units or matching
GPU/display faults in the surrounding log window. These short trials
do not qualify any permanent power-policy change.

### 2026-11-20 — Isolate shared overview and app-grid frame work

Reanalysed the existing CPU A/B/A capture. During opening,
`Meta::Display::handle_event()` p95 was 27.93 / 14.90 / 46.44 ms,
paint p95 was 21.27 / 17.79 / 22.64 ms, and framebuffer swap p95
was 5.42 / 3.36 / 5.86 ms. The markers may be nested. They describe
where time was observed and do not identify a specific blocking call.

Ran four opens/closes per phase using the configured Super shortcut
for the window picker, Super+A for the app grid, then Super again.
GNOME Shell 46 implements distinct window-picker and app-grid
targets under one overview transition path. See the
[GNOME Shell overview controls](https://raw.githubusercontent.com/GNOME/gnome-shell/46.0/js/ui/overviewControls.js).

| Opening target | Paint p95 (ms) | Paint marks over 16.7 ms | Relayout p95 (ms) | Frame-clock dispatch p95 (ms) |
|---|---:|---:|---:|---:|
| Window picker, first | 18.062 | 4/55 | 2.594 | 28.145 |
| App grid | 18.645 | 4/51 | 4.888 | 24.951 |
| Window picker, repeat | 21.097 | 4/48 | 4.182 | 29.636 |

Both overview targets exceeded the 60 Hz frame budget. The measured
app-grid relayout increase does not explain the shared slow paints.
The test restored the desktop and removed the temporary input module.
Sensors and Wi-Fi HTTPS204 passed, with no failed units or matching
GPU/display faults in the surrounding three-minute window.

### 2026-11-20 — Find the overview texture-conversion hotspot

Extracted Ubuntu's ARM64 perf tools privately instead of installing
system packages. The first launch reported three missing libraries;
extracting the corresponding signed Ubuntu dependency packages
allowed the profiler to run as the GNOME Shell user. Scoped the
software CPU clock sampling to the Shell main thread and userspace.
Captured 417 samples during six real opens/closes of each overview
mode. Removed the temporary input module, verified the desktop was
restored, and kept the raw capture private.

In the first 400 ms after opening, `convert_ubyte` was the top
resolved leaf symbol, with 7 of 73 window-picker samples and
9 of 86 app-grid samples. Across the complete recording, all 43
leaf hits of that symbol followed the same texture allocation and
upload stack from Cogl into Mesa. The loaded Mesa's line table
mapped all 43 to the byte-to-byte branch in `format_utils.c`.
The dominant instructions advanced the source and destination by
four bytes per pixel and individually selected the four channels.
This identifies a CPU optimization candidate on the real path.

An Intel Mac cannot execute the ARM SIMD candidate, so ran its
standalone comparison as an ordinary user on the S9+. Address and
undefined-behavior sanitizers passed all 1296 valid swizzles,
both normalization modes, counts 0–33, unaligned buffers, and
in-place conversion. A synthetic 1440x2960 buffer took 2.99 ms
with the prototype versus 13.49 and 12.19 ms in the surrounding
scalar runs. The prototype was not built into or installed as Mesa.
Actual compositor improvement and integrated rendering remain open.

### 2026-11-20 — Build and verify the Mesa NEON swizzle candidate

The live GNOME Shell mapped the accepted Mesa build tree directly.
Cloned the source and build into a private location, verified separate
inodes, and applied the swizzle patch with matching before/after
source hashes. A relocated Ninja dry run proposed 571 rebuild steps.
Ran only the exact recorded commands for the changed object, its
archive and the Gallium link. The resulting ARM64 object contained
NEON table instructions. The accepted source and library hashes
matched their pretest values.

The tracked patch's exact helper passed the sanitized ARM64 swizzle
regression. In isolated offscreen sessions, both the accepted and
candidate Mali-G72 stacks mapped their intended Gallium libraries.
Each passed 100 alternating RGBA/BGRA texture upload and readback
frames, with all 6,553,600 output bytes equal to expected. No matching
GPU/display error appeared in the surrounding log window. The
desktop remained on its accepted Mesa profile. Actual GNOME
animation timing on the candidate remains pending.

### 2026-11-20 — Compare the Mesa swizzle builds in isolated GNOME

Ran three GNOME Shell 46 sessions on native #44 with a 1440×2960
virtual monitor and three identical test windows in each session.
Verified the exact mapped Gallium library and Panfrost renderer before
timing six app-grid and six window-picker transitions per phase after
warmup. Opening paint p95 in baseline/candidate/baseline order was
6.589/6.482/6.878 ms for the app grid and 4.229/4.266/4.274 ms for
the window picker. Opening duration medians remained within the
range of the two baseline runs for the grid, and differed by less
than 4 ms across all runs for the picker.

The virtual session did not reproduce the physical desktop's
over-budget opening paints. It provides no consistent evidence of a
meaningful improvement or of physical presentation timing. No
matching GPU/display kernel fault or failed system unit was found.
The test sessions exited and the live desktop still mapped its
original Gallium library. Physical desktop A/B remains pending.

### 2026-11-20 — Isolate a G3D PLL resume failure

The native #44 kernel journal recorded one runtime power-on where
the 260 MHz PLL did not lock and restoring the 455 MHz setting also
timed out. The programmed rail read back at 950 mV and runtime power
gating remained enabled during the subsequent observation. Forty
GPU readback runs each began after runtime suspend and passed 100
alternating RGBA/BGRA frames with zero mismatches. Power-on and
power-off counters increased by 442 and 441, respectively. The
sampled rate after each run was 260 MHz. No new matching PLL or
Panfrost fault appeared. This does not cover repeated 455→260 MHz
transitions.

The reference PLL_1018X specification lists a 2–8 MHz PLL reference
input and a 600–1200 MHz VCO range. With a 26 MHz oscillator the
current 455 MHz tuple yields a 1 MHz reference and 455 MHz VCO, and
the 572 MHz tuple yields a 2 MHz reference and 572 MHz VCO. The
260 MHz tuple is in range. Calculated replacement tuples for the
two upper rates yield a 3.25 MHz reference and 910/1144 MHz VCOs,
respectively, with the same GPU rates and rail policy. Compiled the
candidate ARM64 driver object in isolation. The intermittent
260 MHz lock failure's cause and the candidate's hardware behavior
remain unverified. No device settings changed in this test.

### 2026-11-20 — Build the isolated #45 G3D PLL candidate

Cloned the exact #44 build tree and rebuilt an ARM64 Image with only
the two upper G3D PLL tuples changed. The initial build container
lacked Make, so the isolated copy was transferred to the existing
cross-build container. The loader's older Kconfig does not support
`olddefconfig`; the standard `star2lte_defconfig` reproduced the #44
loader config byte for byte. The kernel config also matched #44.

Read the tuples directly from both linked ELF images and independently
unpacked the new BOOT candidate. The embedded device tree, outer
device-tree table and ramdisk matched #44. Verified the stored
nine-partition backup and the live #44 BOOT image. Live read-only
checks also matched the archived RECOVERY, EFS, CPEFS, RADIO, DTB and
DTBO. This is a build and recovery preflight. The #45 image has
not been installed or booted.

### 2026-11-20 — Exercise native #44 high-rate GPU resume

Ran offscreen fragment load with the default governor and G3D
runtime power policy. An initial run stopped after two completed
bursts because it assumed runtime suspend always implied a cached
260 MHz setting. The GPU was suspended with 455 MHz reported, and
the kernel recorded no new matching clock error at the stop.

Repeated with six paced load bursts, waiting for runtime suspend
independently of the reported clock. Sampled 260, 455 and 572 MHz,
and the devfreq counters registered two 455→260 MHz and four
572→260 MHz transitions. Checked 600 exact RGBA/BGRA frames after
load and idle, with 74 power-ons, 73 power-offs and no matching
PLL/Panfrost kernel error. Clock values are driver reports. The
earlier intermittent timeout was not reproduced in this baseline
and the #45 hardware comparison remains pending.

### 2026-11-20 — Distinguish the hub reset warning from service readiness

On the current #44 boot, MCU_RESP was high both during the 1-second
standby hold and after releasing the hub. The subsequent firmware
transfer accepted the targeted 36-byte write on its first attempt
and signalled hub readiness at 6.461 s. In a later passive GPIO
check, MCU_RESP was low. A successful firmware start does not
establish that the earlier hardware reset occurred.

During a separate 120-second observation on the same boot, the
hub readiness flag stayed set and the supervisor PID was unchanged.
All six IIO devices passed 241 reads each, with a maximum sampling
gap of 501.7 ms on a 500 ms schedule. The stationary light and
proximity inputs remained constant. All 13 HTTPS requests bound
to Wi-Fi returned 204. No new matching hub or Wi-Fi fault or
failed systemd unit appeared. No reset policy or hardware setting
was changed. The standby warning's cause remains open.

### 2026-11-20 — Build the Exynos8 RTC driver and device tree

The revision 26 reference declares the RTC at `0x141e0000` with
alarm and tick interrupts 31 and 32. Its Exynos8 driver match
skips explicit clock lookup and uses the S3C6410-style alarm IRQ.
The installed #44 kernel includes the S3C RTC driver but has
neither that match nor the RTC node.
[Reference revision 26 device tree](https://github.com/LineageOS/android_kernel_samsung_exynos9810/blob/6a9461f9460ca51d1217e5069a5d5556fcc79e63/arch/arm64/boot/dts/exynos/exynos9810-star2lte_eur_open_26.dts),
[reference RTC driver](https://github.com/LineageOS/android_kernel_samsung_exynos9810/blob/6a9461f9460ca51d1217e5069a5d5556fcc79e63/drivers/rtc/rtc-s3c.c).

Prepared the Exynos8 match and board node in a separate build.
The existing compatibles retain their clock requirements. The
clock API handles a missing handle for the Exynos8 path. Compiled
the ARM64 object and inspected the generated device tree for the
single RTC node, register range and both interrupts. The first
standalone tree check needed the kernel's DTS include prefixes and
the node's actual location under `/soc@0`.

Clock source behavior, counter readout, alarm IRQ and suspend wake
still need hardware evidence. The initial hardware trial should
isolate the RTC from automatic system-to-RTC and RTC-to-system
clock synchronization. The live system remains on #44.

### 2026-11-20 — Check no-SIM cleanup and modem setup diagnostics

The current #44 desktop LTE boot logged the no-SIM result and exited
successfully. Stock ModemManager was active with no enumerated modem.
The temporary manager override, modem runtime mounts, bearer lease
and control socket were absent. The eight kernel rmnet interfaces
remained down, with zero addresses, no IPv4 or IPv6 routes and no
resolved DNS scope or default route. Wi-Fi-bound HTTPS204 passed
and there were no failed units.

The same boot emitted ten ordinary shared-memory link construction
messages at error priority. Prepared an isolated candidate to move
these setup messages to info/debug and remove mapped addresses from
them. The mapping failures and the missing ACPM crash-dump region
remain visible as before. Built and inspected the ARM64 module with
the same release, config and module-symbol table as #44. The
candidate has only build evidence. SIM-present reconnection and
current-build LTE data still require a physical SIM test.

### 2026-11-20 — Verify automatic and manual Wi-Fi Direct discovery stop

On verified #44, issued NetworkManager discovery requests with
5-, 8- and 12-second timeouts. Observed the corresponding
`FindStopped` signal from the actual wpa_supplicant station
interface after 5.024, 8.024 and 12.028 seconds. A separate
10-second request stopped after 2.040 seconds when explicitly
canceled. Each stop left the P2P device disconnected and allowed
the next discovery request to start.

The original station connection and interface index held, with
eight Wi-Fi-bound HTTPS204 responses during and after the scans.
The kernel logged no new matching Wi-Fi/P2P warning or error and
no systemd unit failed. This trial covered the discovery lifecycle.
Active peer negotiation and file transfer on #44 remain pending.

### 2026-11-20 — Isolate the GPIO diagnostics warning

A read of the GPIO debug listing during the earlier sensor GPIO
check triggered 23 warnings on #44. The shared trace begins in
`gpiolib_dbg_show()` and reaches a missing optional direction
callback. The Samsung pinctrl driver has no such callback. This
warning is separate from Bluetooth's existing unsupported
transmit-power-command quirk.

Fetched Christophe Leroy's upstream fix, accepted by Bartosz
Golaszewski, and applied it to an isolated copy without changing
the original tree. The exact diff only guards the direction
lookup in the debug listing. The AArch64 GPIO object compiled.
Hardware boot and a repeated debug listing on the fixed kernel
remain pending.
[Upstream commit d761c7e38a00](https://github.com/torvalds/linux/commit/d761c7e38a000603a9d16270a1af770a0e8efb5e).

### 2026-11-20 — Read verified magnetic capture files directly

The offline heading tool now accepts the SSP broker's private JSONL
format alongside the earlier pose JSON. It checks the format header
and preserves the host-receive-time and quality gates. Tested the
CLI on the handset using its recorded #44 capture. It accepted all
135 high-quality batches; the earlier calibrated #27 capture yielded
280 usable batches, and the uncalibrated #27 capture rejected all
2,997 batches at the default quality threshold. The two calibrated
captures each had circular concentration above 0.9999 with the
candidate magnetic matrix and the live acceleration mount matrix.

These captures provide no new independent direction reference. The
stock SensorProxy compass path still reports `HasCompass=false` to
GeoClue. Its buffered backend requires a tilt-compensated heading
channel and its `magn_3d-devN` trigger. Validating the magnetic
mount matrix and headings before exposing that path remains pending.

### 2026-11-20 — Detect current kernel warnings in the health report

The health tool previously matched only the old sensor reset warning
text. It now matches both versions and reports the identified G3D
PLL failures, GPIO direction warning and unsupported modem bus QoS.
The kernel buffer and system journal have independent counters.
Priority totals and private raw-log handling stay as before.

Ran the updated summary against both live #44 sources and checked the
counts against the actual log messages. Both contained one hub reset
warning, one PLL lock failure, one PLL rollback failure, 23 GPIO
direction warnings and four modem QoS messages. The kernel buffer
retained the boot header. The journal had started later. The QoS
messages describe an implementation gap: the only registered devfreq
device on this build is the GPU, and no CP frequency-vote activity
was logged during the observed no-SIM boot.

### 2026-11-20 — Report Wi-Fi Direct observer cleanup failures

The bounded discovery observer used to write a cleanup error into its
receipt while returning a successful process status. A failed StopFind
now propagates after the private receipt and public count summary are
written. An earlier scan failure remains the primary error if cleanup
also fails. The receipt file opens after read-only device discovery
and before starting a scan.

The host regression injects an error from StopFind and checks both
the receipt and process failure path. On verified native #44, the
updated CLI completed a six-second scan and stopped cleanly. The P2P
device was disconnected after the trial and station-bound HTTPS204
passed. One peer was seen without a verified Fold7 match. Pairing and
payload transfer remain pending on this build.

### 2026-11-20 — Build the combined GPU and GPIO test image

Built #46 from an isolated copy of #45 with the upstream GPIO
debug-listing guard. The only kernel source file differing from
#45 is `drivers/gpio/gpiolib.c`. Kernel configuration and exported
module symbols match. Independently unpacked both BOOT images and
verified that the embedded device tree, outer device-tree table
and ramdisk agree. The #45 PLL-only image is preserved for
comparison.

Prepared a device check that reads the GPIO listing three times
and checks the resulting journal window for the reported trace.
The running handset is still on #44. Both test images await
hardware boot and verification.

### 2026-11-20 — Check IPv6 and dual-stack PDP request fields

Reviewed the owned modem library's attach and PDP definition paths.
IPv4, IPv6 and IPv4v6 use wire values 2, 5 and 6 in both builders.
The independent source builders now accept those three protocol
names and use one mapping for the home, roaming and definition
fields. Existing callers retain their byte-identical IPv4 default.
The first on-device code check needed the approved RFS helper path
to import the standalone tool. With that path, the ARM64 check
passed for all three protocols without opening the modem.

This covers request construction. IPv6 activation, prefix discovery
and LTE-only DNS and data remain pending with a usable SIM.

### 2026-11-20 — Prepare a bounded IPv6 address observation trial

Prepared a local trial patch that uses the reviewed IPv6 and
dual-stack protocol values in both attach and context definition.
It collects the observed address families from valid same-context
responses and ends after observation, through the existing
deactivation and radio cleanup path. The trial uses an isolated
cold session and cannot export an IPv4 lease or install routes.

The first host suite exposed launcher fixtures without an explicit
protocol argument. With the compatibility default restored, all
384 host tests passed. The ARM64 handset fixture accepted separate
IPv6 and IPv4 responses for one dual-stack context and issued only
one cleanup request, without opening the physical modem. Only
fixture and preflight evidence is available. The live trial patch
stays local pending SIM-present testing.

### 2026-11-20 — Validate DNS answers against the actual test query

The LTE data probe previously checked the transaction ID and accepted
the first IPv4 answer regardless of its owner. It now checks the echoed
question and accepts an address only for the requested name or its
alias chain. The parser supports A and AAAA records and checks compressed
names for bounds. The existing modem probe continues to issue A queries.
[DNS message format](https://www.rfc-editor.org/rfc/rfc1035#section-4.1),
[IPv6 DNS records](https://www.rfc-editor.org/rfc/rfc3596#section-2).

Verified the new decoder on the #44 handset with real A and AAAA
responses received over its Wi-Fi-bound socket. The test found no
IPv6 default on Wi-Fi and did not attempt any IPv6 data route. Host
tests cover wrong questions, unrelated address records, compressed
aliases and alias loops. LTE-bound IPv6 DNS and data remain pending.

### 2026-11-20 — Verify IPv6 source and interface binding

Reused one bound-socket helper for the existing LTE IPv4 data
probe and the IPv6 transport checks. It binds the interface and
source address, selects IPv6-only sockets for IPv6, and uses the
selected interface's scope for link-local addresses. It closes the
socket if setup fails.

On #44, the S9+ exchanged exact IPv6 TCP and UDP payloads with the
Mac over USB networking. Checked the socket's source and interface
and verified that Linux rejected binding the USB link-local source
to Wi-Fi. The same helper passed IPv4 DNS and certificate-verified
HTTPS204 over Wi-Fi. No modem route was involved. IPv6 LTE address
and route provisioning and actual carrier traffic remain pending.

### 2026-11-20 — Boot and verify GPU clock and GPIO fixes on #46

With the owner's go-ahead, verified SM-G965N in TWRP, took a fresh
readback-verified nine-partition backup and verified the working #44
BOOT. Installed only the candidate BOOT and matched its readback.
Native #46 started and accepted USB SSH.

Three full reads of the GPIO debug listing returned 3,783 bytes
each and produced no direction warning or call trace. The same
operation on #44 had produced 23 warnings. The build recipe now
applies upstream `d761c7e38a00` to the pinned source and verifies
the patched bytes. A second application is a no-op, and source
drift is rejected.

Ran six GPU load/idle trials with the original governor and three
more with a temporary 455 MHz ceiling. Devfreq counted four
455→260 MHz and five 572→260 MHz transitions. The tests checked
900 exact RGBA/BGRA readback frames across 109 GPU power-ons.
No matching Panfrost, PLL lock or PLL rollback error appeared.
Restored the 572 MHz ceiling, verified 950 mV and Wi-Fi HTTPS204.
The in-range G3D tuples now match the tested build. These bounded
trials do not establish a fix for every intermittent resume
failure or qualify GNOME animation smoothness.

The planned #44 rollback stopped before writing because EFS differed
from the first backup. The owner requested keeping #46. A second
complete recovery backup matched installed #46 BOOT. Comparison
proved EFS differences were confined to the approved ext4 superblock
fields. RECOVERY, CPEFS, RADIO, DTB and DTBO matched across the two
backups. Rebooted the already installed #46 without another write.

The four original service pins correctly rejected the different
kernel. Preserved their settings and rebound them to the verified
#46 BOOT, backup and unchanged module ABI. The six IIO devices
returned values, the audio driver exposed playback/capture devices,
and BlueZ powered its controller. Modem provenance maintenance first
stopped because its private runtime was down. Repeated under the
exclusive lease with the isolated runtime mounted read-only from
SYSTEM/VENDOR and no modem daemon, then tore down the runtime. The
old provenance and working NV were preserved.

After a separate warm boot, #46 remained active and three GPIO
listings again produced no direction warning or call trace. The six
IIO devices and three ALSA PCM endpoints were present, BlueZ reported
a powered controller, and Wi-Fi-bound HTTPS returned 204. The desktop
LTE supervisor failed before CBD startup: the transient RIL service
started and then stopped without reaching confirmed channel readiness.
Stock ModemManager was active afterward. The earlier #44 no-SIM
startup result does not qualify this boot, and no LTE data test was
run on #46.

### 2026-11-20 — Check stock Ubuntu sensor integration on #46

Ubuntu 24.04's installed IIO Sensor Proxy was active. In the signed-in
GNOME Wayland session, automatic brightness was enabled and rotation
lock was off. Direct sensor claims returned 341 lux and proximity far.
The accelerometer reported available, with orientation undefined in
the observed nearly flat pose. This check did not move the phone or
vary the light. The owner had previously qualified both desktop
controls with physical changes.

The Ubuntu user read acceleration, light, pressure, barometer
temperature, proximity, angular velocity and both board temperatures
from the six IIO devices. GeoClue is installed, but its Sensor Proxy
compass backend was unavailable. No verified heading backend is exposed.
An ordinary remote process was denied a Sensor Proxy claim by stock
PolicyKit; the bounded diagnostic used an authorized root claim and
released it. No package, setting or access policy change was needed.

### 2026-11-20 — Measure compass response with a local display

Confirmed on #46 that GeoClue can read the standard compass object at
`/net/hadess/SensorProxy/Compass` and gets `HasCompass=false`. The kernel
has IIO direct mode but lacks the buffer and trigger support required
by Ubuntu 24.04's stock compass backend.

The first bounded cardinal capture reported magnetic quality 0 in the
four flat poses. The nominal tilted pose was flat and was excluded.
Automatic restore initially refused the wrong kernel receipt left in
the trial wrapper. Corrected the pin, restored the original profile
and verified the existing sensor service. A second capture after a
figure-eight still reported quality 1 at north and restored normally.

For the owner's direct check, opened a temporary Wayland sensor window
showing the live magnetic X/Y/Z readings, calibration state and
overflow. Verified Wi-Fi and Tailscale SSH against the known host key.
The capture ran independently of USB. The owner saw the readings
change and calibration reach 2–3 after removing the cable. All five
wireless reference windows contained 15 quality-3 magnetic samples
with no overflow. The accelerometer distinguished the tilted pose.

Compared the five reference poses with all 24 proper magnetic
axis mappings. The best candidate still differed by about 15°, 19°,
35°, 44° and 115° for north, east, south, west and tilted north.
These angles and the quality indication measure different properties.
The trial did not qualify an orientation matrix or heading. No angle
was sent to GNOME or GeoClue.

The owner reconnected USB after the reference measurements. Ended
the transient capture, verified the saved service unit and profile
byte-for-byte, and confirmed the sensor broker and Sensor Proxy were
active with all six original IIO devices. The viewer reported
measurement end. The phone stayed on #46, with no partition writes.

Built the candidate buffered IIO core and bridge object for AArch64
with the stock Sensor Proxy channel and trigger naming. The broker
uses the existing heading math and rejects incomplete or out-of-range
reference evidence. Host tests passed, including stale-angle
withdrawal. Stopped the full kernel build after the direction trial
failed. No candidate image was installed or claimed to boot.

### 2026-11-20 — Enable experimental compass on native #47

The owner requested enabling the standard compass before finishing
calibration and authorized a BOOT-only update. Added explicit experimental
profile support and retained the verified profile option. The trial accepts
SSP quality 1 and above with valid geometry, recent gravity data and no
overflow. Bounded calibration capture can now run alongside heading output.

Built the full ARM64 kernel and buffered IIO bridge, verified the packaged
image contents, entered TWRP and verified a fresh nine-partition backup
against the running #46 BOOT. Wrote BOOT only and matched its readback.
Native #47 accepted USB SSH. Verified the exact new bridge and migrated
the existing kernel pins with their previous service settings saved.

The new IIO compass reported the stock `iio-buffer-compass` udev type
and 0.001 degree scale. As the GeoClue service account, claimed the
compass through Ubuntu's installed Sensor Proxy and read five real,
changing headings around 63°. Repeated the same check after a distinct
warm boot. All seven IIO sensors were present, the sensor, audio and
Bluetooth services were active, and Wi-Fi HTTPS returned 204. The
pre-existing no-SIM desktop LTE startup failure was still present.
A temporary live Wayland window read the same standard heading.
Physical reference accuracy and tilt calibration remain open.

### 2026-11-20 — Connect board and barometer temperatures to hwmon

Native #47 had functioning IIO temperature data and the existing
Ubuntu `lm-sensors` package, with no hwmon class. Built the unmodified
upstream hwmon core and IIO consumer as external modules against the
exact #47 output. Added optional IIO maps for the barometer die and
both board thermistors. The sensor supervisor verifies module pins,
loads the core and consumer in order, and brings up the guarded bridge.

Checked SM-G965N, exact live #47 BOOT and the verified recovery backup.
Saved the original sensor profile and unit before changing userspace
and modules. No partition was written. Ubuntu's `sensors -u` returned
37.890, 31.266 and 27.653 °C. After a separate warm boot it returned
37.620, 30.900 and 27.551 °C. These are hardware readings exposed for
monitoring. No thermal or charging policy is attached to the new maps.

The first warm boot exposed a compass dropout. A bounded private trace
with hwmon and compass both enabled yielded 95 magnetic samples at
calibration state 0, all without overflow, plus 111 acceleration
records. With the existing threshold the geometry rejected all 95
batches. All 95 passed the geometry check at minimum calibration
state 0. Restored the original capture settings. Following the owner's
earlier request to activate before calibration, the explicit experimental
profile now publishes these live readings when the geometry and freshness
checks pass. The verified profile retains its original quality threshold.
GeoClue's account read five live compass samples around 67° while all
three hwmon channels remained readable.
The final warm boot reproduced both features together. Two IIO hwmon
devices reported three temperatures (38.210, 31.633 and 28.503 °C),
the standard compass returned five headings around 67°, and the
proxy reported acceleration, light and proximity present. Audio and
Bluetooth services were active and Wi-Fi HTTPS returned 204. The
pre-existing no-SIM desktop LTE unit was still failed.

### 2026-11-20 — Audit remaining GNSS, NFC and fingerprint interfaces

The handset's own read-only vendor runtime supplies the Broadcom GPS
daemon and GNSS HAL. The active hub daemon publishes the matching
private GPS IPC FIFO. Ran a bounded GPS startup probe with separate
mount, PID and network namespaces, Android GPS UID, scratch state and
no BBD or block device exposed. An initial service check inside the
network namespace could not reach systemd; moved it outside. The
stock ELF initially lacked its vendor search path and Android runtime
ICU library path. Supplying the vendor, system and runtime library
directories allowed the daemon to run to the trial timeout and create
its control and HAL IPC FIFOs. No NMEA or fix was verified and no
GeoClue source was enabled.

The owner stock device tree exposes secure-mode SPI and identifies
the Egis ET510 reader. The fingerprint HAL references the Samsung
biometric service and the vendor image contains the Trustonic stack.
No native libfprint backend or enrollment was validated. The owner
NFC configuration identifies S3NRN82 at the stock NFC I²C controller.
The running kernel has NFC off, and the available mainline Samsung
driver identifies S3FWRN5. Board wiring and protocol support still
need a controller probe before exposing NFC through Linux. The stock
tree also identifies Hall, optical heart-rate and separate grip inputs.
No new probe drove those buses or input lines.

### 2026-11-20 — Exercise the GNSS HAL and read the cover input

Built a small Android 10 LP64 GNSS client using the handset's own
Bionic DSOs in temporary private storage. The first link could not
traverse the root-only runtime. An unprivileged build using read-only
copies resolved that. Disabled glibc fortification and outlined
atomics for the Bionic link after the initial undefined references.
No vendor code or binary was published.

In the empty trial runtime, the HAL returned an 80-byte interface,
then acknowledged initialization, standalone mode and start. With
the active hub's dedicated GPS IPC directory in the isolated trial,
observed successful HAL and LHD pipe reads and writes and the actual
BBD core-on and core-off messages. A process guard originally used an
unsupported quiet flag; corrected the guard and verified cleanup.
Satellite, NMEA and valid-fix callbacks remained at zero in the short
initial trials.

The isolated Android logging socket identified repeated refused RILD
connections. Explicitly disabling SUPL, LBS and HTTP LTO in the scratch
GNSS configuration did not change the result. The core turned off
about 0.5–1.2 seconds after the start requests in those traces. This
does not establish that the RILD failure causes the transition.

An interruption-safe 60-second observation produced one satellite
callback and 14 NMEA callbacks. A separate 90-second run produced 14
checksum-valid sentences and delivered all 14 through a local streaming
socket to the GeoClue service account. It received one GGA, one RMC,
eight GSA and four vendor messages. Neither run reported a valid
latitude/longitude fix. No coordinates or NMEA payload were printed or
recorded.

An initial desktop-service proof timed out obtaining a client from a
root session. Obtaining a client as the desktop user succeeded, but
starting it was denied because location is disabled for that user.
The temporary GeoClue trial drop-in was removed. No desktop location
preference was changed.
After all trials, confirmed GPS daemon exit, moved only newly created
GPS scratch artifacts out of the active IPC directory, and verified
the original LHD lock and two server FIFOs remained. Sensor Proxy
and the sensor service were active and all three hwmon temperatures
remained readable.

For cover detection, confirmed the owner's stock GPIO assignment
and requested GPA3 line 6 as an input using Linux GPIO v2. The initial
level was high. Waiting for a physical open/close check before
choosing the input polarity and exposing a lid switch to Ubuntu.

### 2026-11-20 — Verify GeoClue connection with desktop location enabled

The owner explicitly requested leaving the GNOME location setting on.
Set it for the desktop account and confirmed it was enabled. Used a
temporary GeoClue configuration that selected the local NMEA stream
and disabled other providers for source isolation. The desktop proof
client started and the relay verified that the real GeoClue daemon
connected to its socket. No coordinates were printed.

The owner moved the phone near an open view of the sky. The standalone
HAL trial ran for 205 seconds. It returned one satellite-status callback
and 14 checksum-valid NMEA sentences, and all 14 were forwarded.
There was no valid latitude/longitude callback and no GeoClue location
object during its 215-second observation. Removed the temporary source
and authorization drop-in and restored the preceding GeoClue service
state. The GNOME location preference remained enabled.

For Hall detection, expanded the read-only diagnostic to observe the
stock flip-cover input (GPA3 line 6) and accessory input (GPA0 line 2),
including periodic reads to catch a level change without an interrupt.
The owner clarified that the stimulus was a magnet at the earpiece.
The accessory input recorded three rising and three falling interrupts
with matching levels. The flip-cover input stayed high in that trial.

During the follow-up magnet sweep, GPA3 line 6 recorded five falling
and five rising edges, each with a matching GPIO level. The line came
back high with the magnet away. The distinct GPA0 accessory input
also toggled. These were magnet stimulus results, with no physical
flip cover fitted.

Built and installed the opt-in G965N GPIO keys module after verifying
the model, active #47 BOOT and backup receipt. The module exposes the
active-low GPA3 input as Linux `EV_SW/SW_LID`. The input device appeared
with the standard udev `power-switch` tag and logind read open. Enabled
its exact-BOOT service for future startup. The system's existing
logind lid action is `ignore`. No partition or lid policy was changed.

### 2026-11-20 — Qualify native flip-cover transitions

The reply to the first native-input test arrived after its 95-second
observer had exited. A new event observer saw no transitions on the
first repeat. During a subsequent slow magnet sweep, sampled the
bound GPIO level and interrupt count while reading the native input
events. GPA3 line 6 changed level and the interrupt counter advanced.
The stock input emitted eleven close/open pairs, and logind logged
the matching transitions. The final state was open with the magnet
removed. This qualifies the real GPIO to evdev to logind path under
magnet stimulus. A fitted cover and screen/suspend action were not
tested. The configured lid action is `ignore`.

### 2026-11-20 — Install on-demand GPS as a standard GeoClue source

The owner requested registering the GPS module without requiring a
position fix as an installation gate. Installed a persistent local
GeoClue NMEA source and systemd socket on native #47 after verifying
the model, exact BOOT and full backup receipt. Desktop Location
Services remains enabled. No partition was written.

The socket is limited to the GeoClue account and starts one guarded
vendor GPS session per connection. It reuses only read-only Android
files and the existing leased GPS IPC directory. Network, PID and
mount namespaces isolate the GPS process, and the session forwards
only checksum-valid NMEA. The first Bionic client link exposed a
glibc errno accessor reference. Used Bionic's accessor and rebuilt.

The installed Ubuntu GeoClue daemon started the real receiver by
connecting to the persistent socket. Its 64-second proof session
received 14 NMEA sentences. Closing the client ended the worker,
released the sensor lease and left only the listening socket. The
temporary proof app's authorization was removed. No fix was observed.
A second connection as the GeoClue service account independently read
14 checksum-valid sentences and returned the receiver to idle again.

### 2026-11-20 — Connect the desktop Compass app to live Sensor Proxy

The old launcher used the Qt Sensors compass backend and stayed in
its waiting state. On the same boot the GeoClue account read five
real magnetic headings around 104° from Ubuntu Sensor Proxy.
Replaced that frontend with the local GTK app and an on-demand relay
running as the existing GeoClue account. The socket belongs only to
the selected desktop user. It releases the compass on disconnect
and does not change D-Bus, PolicyKit or system location permissions.

Saved the old desktop entry and installed the new launcher and
enabled socket on the running #47 handset after the model, BOOT and
backup checks. The ordinary desktop account received a real 103.729°
heading. `gtk-launch` was absent, so used the actual installed desktop
entry through `gio launch`. Verified the real Wayland window displayed
168.6° through accessibility. Standalone direction accuracy remains
unqualified.

### 2026-11-20 — Connect five G965N hardware sensors to Qt 5

The Ubuntu Qt 5 examples lacked usable backends for tilt, proximity,
gyroscope and pressure. The distribution Qt compass backend waited
for data in the ordinary desktop session. Installed the Qt 5 build
dependencies and the locally built plug-in on the running #47 device
after checking the model, BOOT and recovery backup. No partitions
were flashed. The default backend file did not previously exist.

The plug-in reads the existing read-only IIO attributes and uses the
private desktop compass socket. It applies the acceleration mount
matrix and proximity threshold, and reports pressure and die
temperature in Qt's units. Local inspection of the same device's
stock Android HAL confirmed the signed SSP gyro stream is passed
through in axis order and scaled at 0.035°/s per thousand counts.
No Android binary or extracted firmware is distributed.

On the actual Wayland user session, exercised the packaged example
QML and Explorer model via their sensor-selection and Start handlers.
The first harness pass checked the QML proximity field name rather
than Explorer's native `close` property and stopped the compass before
the relay finished warming up. With those checks corrected, multiple
runs showed fresh timestamps and rendered values for all five
sensors. The packaged Tilt, Light and Proximity example also
displayed both angles and Far via the configured defaults. The legacy
Qt Quick Controls table emitted delegate warnings and sometimes left
its Running column at false while Properties showed live readings.

This run establishes data delivery to Qt 5. It sampled far proximity,
stationary gyro and the current magnetic heading. Controlled motion
accuracy, compass calibration and another reboot were not exercised.

### 2026-11-20 — Restore the native #47 desktop modem and check stock services

The enabled desktop LTE service had failed before preparing the modem
or loading its module. The protected EFS partition differed from its
private receipt while CPEFS and RADIO still matched. Located the exact
old and live-matching recovery backups. The existing byte-level proof
accepted a single step limited to the four permitted primary ext4
superblock fields. Verified SM-G965N, the running BOOT and the pinned
nine-partition backup before refreshing the private receipt under both
leases. Kept the old receipt and working modem data. No block device
was written. The sensor service stayed active during maintenance.

The first retry preflight found the failed service's empty runtime
directory. Removed only that empty directory and archived the prior
attempt marker after confirming the modem module was never loaded
during that failed attempt. A fresh service invocation exposed the real
SIM and one internal device through ModemManager, then NetworkManager
listed rmnet0 as GSM. The RIL broker returned radio on, SIM ready, EPS
searching, no packet attachment and nonzero signal. ModemManager timed
out waiting for registration and the mobile data profile did not
connect. Wi-Fi-bound HTTPS204 passed, and no systemd units remained
failed. Cellular traffic and the reason for the operator registration
timeout remain unqualified on this boot.

Verified UPower exposes both stock sysfs power supplies and a present
desktop DisplayDevice at 99%, fully charged with USB online. Sensor
Proxy still exposes acceleration, ambient light and proximity. BlueZ
reports a powered adapter. The GNSS and compass sockets remain active.

NFC and camera class devices are absent with NFC and media disabled in
the running kernel. Comparison with the Linux Samsung NFC drivers
shows the S3FWRN82 driver uses UART while this board has the S3NRN82
on I²C with a clock request and regulator setup. A driver match by
similar chip name is insufficient. The secure ET510 still needs a
native biometric integration. No new probe drove any of these buses.

### 2026-11-20 — Enable and verify the Exynos8 hardware clock on native #48

Reused the revision 26 hardware evidence to add the Exynos8 match,
firmware-clock path, binding and S9+ RTC node. Compiled the driver
and DTB against the current native #47 sources. The first standalone
DTB preprocessing attempt lacked the kernel include-prefix path.
Added it and verified the resource address and both interrupts.
Built the full ARM64 #48 Image and uniLoader with the new inner DTB.
Kernel release and module symbol table matched #47. The only config
changes disabled automatic RTC-to-system and system-to-RTC updates.
The verified BOOT package retained the existing outer DT and ramdisk.

Confirmed operator consent, model, USB link and battery. Verified a
fresh nine-partition TWRP backup and #47 rollback image, wrote only
BOOT and verified its readback. Ubuntu started on #48. Restored the
guarded startup receipts for sensors, audio, Bluetooth, cover and
desktop LTE. The fresh recovery backup differed from the previous
EFS checkpoint only in the four permitted superblock fields, so
revalidated the modem receipt using the existing proof. The prior
receipt and working private modem data were preserved.

Linux registered /dev/rtc0. The initial calendar was invalid. A
first initialization attempt used a buffered handle unsuitable for
a non-seekable RTC device. Opened the character device directly
and initialized the RTC from synchronized UTC. Readback agreed
within three seconds, the counter advanced and an awake alarm
delivered RTC_AF through /dev/rtc0. Cleared the trial alarm. On a
distinct warm reboot the RTC retained an advancing time. Standard
systemd timedated reported a matching RTC time, and audio, Bluetooth,
cover, sensor, GNSS, compass and desktop modem services were active.
Wi-Fi-bound HTTPS204 passed. Power-off retention, sleep wake and
automatic RTC sync were not exercised.

### 2026-11-20 — Verify Ubuntu Mobile Network data after the #48 warm reboot

After the approved RTC installation and separate normal reboot,
the existing desktop LTE service started automatically with the
revalidated private receipt. The real SIM registered on its home
network and NetworkManager connected the standard GSM profile.
An uncached IPv4 DNS query used rmnet0 and certificate-verified
HTTPS bound to rmnet0 returned 204. The cellular interface gained
10 RX and 13 TX packets with no interface errors. A separate
Wi-Fi-bound HTTPS request also returned 204. No systemd units
were failed. The earlier #47 registration timeout did not recur
in this check. The reason for the previous registration delay,
long-term reconnect behavior, IPv6, voice and SMS remain open.

### 2026-11-20 — Provide synchronized UTC to the standalone GNSS receiver

On native #48, a three-minute request through the GeoClue socket
returned GGA, GSA and RMC messages without a valid fix or any satellites
used. Added UTC assistance through the handset's existing ARM64 Android
HAL. The worker receives the option only after this Ubuntu boot records
a time synchronization and timedated confirms the system clock remains
synchronized. The helper uses CLOCK_BOOTTIME as its monotonic reference.
Standalone operation continues when that gate is unavailable.

Built with the owner's read-only Android libraries and compiler warnings
as errors. Checked the model, exact BOOT and complete backup, preserved
the old private installation, and installed the new helper and matching
pin while the listener was idle. The live HAL returned zero for UTC
assistance. The GeoClue account subsequently received 14 checksum-valid
sentences during a second three-minute observation, with no GGA fix or
valid RMC position. A fresh socket request received 14 more sentences
and the worker exited after disconnect. No coordinates or sentence
content were logged. Five host checks exercised missing, false, failed, valid and timed-out
clock-state checks. Twenty-two sensor runtime regressions passed.

The read-only driver inventory confirmed that the live kernel exposes
neither the NFC controller at stock address 0x108e0000 nor the second
I²C controller at 0x10930000 needed for the PCAL6524 enable/firmware
GPIOs. The stock design also requires a shared 1.8 V rail and a separate
clock request. The kernel exposes no V4L2 or TEE devices. Camera streaming
requires the Exynos FIMC-IS media pipeline, and the ET510 device requires
the native secure SPI/biometric path. NFC tag reads, camera streaming
and fingerprint enrollment remain pending. No controller bus was driven
during this inventory. The mobile modem remained connected, Wi-Fi
HTTPS204 passed and audio, Bluetooth, cover and sensor services were active.

### 2026-11-20 — Build the two NFC-related PERIC1 I²C buses

Compared the public revision 26 reference to the device tree from the
owner's checksum-verified SM-G965N stock BOOT backup. Initial extraction
used the newer backup schema and assumed the DTBH chip field contained
the SoC product number. Checked the legacy manifest structure and the
actual Samsung table identifier, then selected the unique revision 26
entry. The owner tree confirms the NFC device at address 0x27 on
0x108e0000 and the PCAL6524 at address 0x22 on 0x10930000. The first bus
uses USI08 in I²C mode. The second uses the USI10 dedicated I²C clock
and does not need the adjacent USI mode select.

Use the vendor register tables to distinguish the PERIC1 bus and IP
parents, the full USI08 gates, and the USI10 dedicated gates. Built an
isolated DTB candidate with both AutoV9 controllers and no I²C child
devices. Did not add an unverified CLKREQ option write to the dedicated
controller. Verified both ranges, IRQs, stock pin groups, actual pinctrl
references and exact clock-table additions. The 200 MHz fixed input
follows the stock request and still needs measurement on hardware.

Rebuilt uniLoader and unpacked the private candidate BOOT to verify the
same #48 Linux Image, outer DT and ramdisk with only the new inner DTB.
The handset continued running its existing #48 BOOT and reported a
connected mobile interface. No controller register, regulator or flash
partition was touched during this review. The PCAL6524 GPIO reset is
identified as GPG3 line 6; its supply and safe reset policy remain
separate from the bus candidate.

- [Stock Exynos9810 clock registers](https://github.com/LineageOS/android_kernel_samsung_exynos9810/blob/6a9461f9460ca51d1217e5069a5d5556fcc79e63/drivers/soc/samsung/cal-if/exynos9810/cmucal-sfr.c)
- [Stock Exynos9810 clock mapping](https://github.com/LineageOS/android_kernel_samsung_exynos9810/blob/6a9461f9460ca51d1217e5069a5d5556fcc79e63/include/dt-bindings/clock/exynos9810.h)

### 2026-11-20 — Boot the NFC bus trial and read the PCAL6524

With the exact SM-G965N, USB recovery, charged battery and complete
backup verified, wrote and read back the client-free NFC trial BOOT.
Restored the guarded service receipts for the new BOOT. Recovery and
the protected radio partitions matched the previous backup. EFS
differed only in the four approved ext4 fields, so revalidated the
private modem receipt while preserving the old receipt and its data.

Both AutoV9 controllers bound and registered I²C adapters. The kernel
read back the new clock and reset settings. A direct read of the clock
tree showed the PERIC1 IP parent selected from PLL_SHARED2 (800 MHz),
two upstream divide-by-two stages and local divisors of four and one.
The inferred controller inputs are 50 MHz for full USI08 and 200 MHz
for dedicated USI10 I²C. The existing boot still describes both as
200 MHz. The electrical SCL rate has not been measured.

The first targeted PCAL6524 input-register read timed out. A temporary
clock-request bit test produced the same result and restored the
original bit. The pinctrl owner display showed the correct group, but
the actual GPP6 mux nibbles remained zero. The existing Bluetooth
module uses the same two pins for its software I²C adapter. After
stopping its service and reapplying the native controller pinmux,
both nibbles read back as three and a targeted PCAL6524 read returned
one input-register byte.

The first test shell emitted its Python heredoc opener as text. The
subsequent dedicated read completed. Bluetooth could not restart
directly because its service stop leaves the module loaded. After
manual reload the UART was assigned ttySAC1, while the service still
expected ttySAC0. A normal reboot restored BlueZ's powered controller,
audio, cover and sensors, and re-registered both I²C adapters. Wi-Fi
HTTPS204 passed. The board still needs a single PCAL6524 owner before
Bluetooth and NFC can share its outputs reliably.

The owner inserted a replacement data SIM. The running system did
not recognize it immediately. Restarting the modem with the verified
receipt made the new SIM ready. On subsequent boots, EPS remained
searching and packet attachment stayed false despite a nonzero
signal. A separate one-minute observation after the final reboot
never acquired a mobile bearer. Ubuntu Wi-Fi and the original modem
service remained running. Prior end-to-end IPv4 evidence involved
the previous SIM.

### 2026-11-20 — Share the native PCAL6524 with Bluetooth and load Linux NFC

Added an explicit native-expander option to zrn-bt. It locates the
exact G965N I²C controller through the device tree, verifies the
PCAL6524 client and its GPIO driver, and claims BT_EN as a GPIO
consumer. It does not create a second I²C adapter in this mode.
The existing startup path remains the default.

Built the ARM64 Bluetooth module. Kbuild emitted it in the output
tree, and the first copy tried the source directory. On the verified
#48 BOOT, stopped the legacy service and unloaded its module,
rebound the native controller, and instantiated a temporary
PCAL6524 client. gpio-pca953x bound and reported an absent vcc
description with a dummy regulator. The existing powered chip
answered. Loaded the new module, attached the actual UART and
observed the BCM firmware and powered BlueZ controller. A discovery
scan observed 13 peers with no device addresses retained. The legacy
i2c-96 adapter was absent and Wi-Fi HTTPS204 passed.

Built the upstream nfc and nci modules for the same release with
CONFIG_NFC=m and CONFIG_NFC_NCI=m. The first modpost attempts
saw an empty Module.symvers left by an external module build.
Reused the preserved vmlinux symbol table that had matched #48
during its build and linked without suppressing unresolved symbols.
Loaded both modules on the verified handset. AF_NFC opened and
generic netlink resolved the nfc family. Bluetooth was still
powered. No NFC radio registered, and the handset's configured
Ubuntu repositories offered no neard package candidate. The
S3NRN82 I²C driver and its power/clock path remain separate work.

The temporary Bluetooth unit, native GPIO client and NFC core
modules are live in this boot. No BOOT or persistent startup
configuration was changed by this trial.

### 2026-11-20 — Start the shared NFC stack on reboot and probe S3NRN82

Installed a guarded Bluetooth service drop-in and root-private pinned
modules after checking SM-G965N, exact BOOT and its complete backup.
The helper binds the standard PCAL6524 driver, loads the NFC core and
the native-expander Bluetooth module, and finds the live UART rather
than assuming ttySAC0. A distinct warm boot verified the expander,
NFC/NCI modules, and a powered BlueZ adapter without i2c-96.
Wi-Fi HTTPS204 and active sensor services were confirmed.

The revision 26 vendor source identifies PCAL6524 lines 11 and 9 for
VEN and FIRM/wake, GPA1 line 2 for data IRQ and GPA2 line 6 for CLK_REQ.
It selects TCXO for PMU CLKOUT1 and uses S2MPS18 LDO38 at 1.8 V.
A first direct trial used the disabled GPIO v1 ioctl. Switched to the
kernel's GPIO v2 ABI. Verified the stock 1.8 V register selector,
briefly forced LDO38 on, enabled the NFC clock gate and applied the
stock VEN/wake order. Writes to I²C address 0x27 returned ENXIO.
An isolated trial that restored the stock 200 MHz USI08 input also
returned ENXIO. VEN/FIRM readbacks followed the requested states,
while CLK_REQ and the data IRQ stayed low. The temporary GPIO, clock
and rail changes were restored. Physical voltage and TCXO waveform
at the chip were not measured.

Compiled an ARM64 S3NRN82 I²C-to-NCI driver candidate. Its guarded
CORE_RESET check also returned ENXIO on the handset, so it rejected
registration. Removed the temporary I²C client and unloaded that
driver. The handset exposes zero NFC radios. The driver candidate
stays in local experiment storage pending a working transport.
Persistent Bluetooth, shared GPIO and the NFC core remain in service.

### 2026-11-20 — Repeat NFC controller response checks

Rechecked VEN/FIRM, data IRQ and CLK_REQ against the handset's own
revision 26 BOOT tree. Its phandle numbering differs from the public
reference, but the resolved GPIO bank and line assignments agree.
Normal mode and a firmware-mode query both returned ENXIO at 0x27.
Neither CLK_REQ nor the data IRQ rose during the bounded observations.

A separate normal-mode trial retained the inherited 50 MHz USI08 input
and lengthened the bus clock period by four. The initial timing-register
check used the HS rather than FS register and failed its assertion
before changing it. Corrected to the driver-defined FS3 offset 0x68.
The slower transfer also returned ENXIO. Restored and read back the
USI08 divider (3), FS3 timing (0x00240000), CLKOUT1 (1) and LDO38
(0xac). BlueZ was powered, audio and sensors active, Wi-Fi HTTPS204
passed and no systemd units were failed.

No NFC radio or tag read was verified. These checks do not establish
that the chip receives its physical supply or reference clock. Further
progress requires resolving chip power/clock delivery or obtaining a
working stock NFC baseline on this exact damaged handset.

### 2026-11-20 — Correct VEN polarity and register the live S3NRN82

The owner confirmed this handset's NFC worked previously. Re-read the
stock sec_nfc.h definition: SEC_NFC_PW_ON is zero and PW_OFF is one.
Earlier probes incorrectly drove VEN active-high. GPIO controller
readback from those probes therefore did not qualify NFC power-on.
Correcting VEN to active-low immediately produced a successful
CORE_RESET response over I2C.

The native driver now claims active-low VEN through the shared
PCAL6524, enables the stock LDO38 and CLKOUT1 settings and raises wake
after normal-mode startup. Its first Linux NCI activation timed out.
Added a 100 ms post-wake delay and a level-triggered oneshot data IRQ.
The controller then registered and Linux DEV_UP plus START_POLL and
STOP_POLL all succeeded. Driver diagnostics contain packet header
types and lengths only.

Installed the pinned controller module in the shared startup path.
A distinct warm reboot automatically registered nfc0, the standard
PCAL6524 and a powered BlueZ adapter. Audio and sensor services were
active with no failed systemd unit. Repeated Linux NFC activation,
polling and cancellation successfully after that boot. The real
physical tag test is pending tag presentation. No tag content, tag
identifier or secure-element operation was recorded.

This corrects the prior suggestion that physical power/clock
measurement was the necessary next step. The active-low definition
in the available stock source resolved the initial nonresponse.

### 2026-11-20 — Complete Qt acceleration and qualify repeated NFC lifecycle

The owner was away, so continued tests that require no physical
movement. The native acceleration IIO source already powered GNOME
orientation but the local Qt backend lacked QAccelerometer.
Added the backend using the exported scale and mount matrix, then
installed the compiled ARM64 plug-in after the running BOOT/model
and backup guard. Preserved the prior library and settings locally.
The global default settings now select the native acceleration
backend in newly opened Qt applications.

The actual installed Sensor Explorer QML and model returned
timestamped X/Y/Z around -0.15, -0.14 and 9.53 m/s². A rendered
Properties screenshot displayed the live acceleration values. The
existing tilt, proximity, gyro, pressure and compass backends also
delivered samples. Enabling QAccelerometer allowed the standard Qt
generic rotation backend to report gravity-derived pitch and roll.
Its yaw remains zero. No physical motion accuracy claim is made.

Separately, ten native NFC activation, poll, cancellation and power
down cycles passed. Two complete Bluetooth service stop/start cycles
removed the owned module and restarted on the actual UART with a
powered BlueZ adapter. nfc0 and its shared PCAL6524 stayed registered.
The user was away, so no physical tag detection or content test was
performed. The last NFC lifecycle test left the radio powered down
and available for the next application.

### 2026-11-20 — Add standard neard service and desktop NFC controls

The configured Ubuntu 24.04 package repositories have no neard
candidate. Built upstream linux-nfc/neard at the pinned revision
f4b6db9ec482208079f684a0ed6762fd37371d2b on the handset with tag-type
plugins, tools and examples. All three upstream NDEF/SNEP suites
passed. Preserved upstream source and notices in the local build.
The committed recipe builds only and does not install or flash.

The first installed daemon could not own its D-Bus name because the
/usr/local prefix installed the policy outside Ubuntu's system bus
configuration directory. Installed that exact upstream policy under
/etc/dbus-1/system.d, reloaded configuration and started the daemon.
Its ObjectManager enumerates the native radio and its Adapter API
reports the controller's supported protocols. The ordinary desktop
user successfully powered the radio on and off and started/stopped
polling through the standard D-Bus interface.

Installed a local GTK NFC settings and tag-view frontend. GNOME has
no native NFC page here, so it is a separate launcher. It displays
neard NDEF text/URI records without automatically opening links.
Added asynchronous control calls and excluded status refresh while
a command is pending. The accessibility action tests could not
activate the GTK controls reliably. A visible GTK instance then
exercised the real checkbox and button handlers under the ordinary
desktop account. All six off/on/poll/stop/off checks matched the
visible status. The service is enabled after the shared Bluetooth
driver and available through org.neard. A service restart repeated
the ordinary-user control checks. Physical tag detection and NDEF
content were not tested because the owner was away.

The replacement data SIM remains in network-searching state in the
current observation. Actual data registration, GNSS fix, camera and
fingerprint remain open.

### 2026-11-20 — Expose native WWAN settings and audit camera/fingerprint

Opened the real GNOME Settings WWAN panel on the #48 handset and enumerated
its accessibility tree. Mobile data, roaming, network mode, network selection,
APNs, SIM lock, modem details and the master mobile-network switch are present.
The control center refuses a bare SSH desktop environment; its application-
scoped GNOME environment allows a normal launch. The stock panel desktop file
is intentionally NoDisplay, and GNOME hides the panel when no supported modem
is enumerated. The exact cause of the owner's earlier missing menu was not
captured. A later AT-SPI attempt to activate the APN button failed because its
accessible object exposed no action at index zero. The button's presence is
verified; APN editing was not exercised. Added and installed a separate
application launcher that opens this
standard page. The first launcher check found an ambiguous category hint and
no gtk-launch executable. Corrected the category and verified launch via gio;
desktop-file-validate then passed without output.

The SIPC subclass inherited an ANY mode despite advertising only an LTE
backend. This caused GNOME to display 2G, 3G, 4G and 5G. Added an asynchronous
supported-mode result for the implemented 4G backend. This is software
capability reporting, not an RF-mode command or a chipset-wide support claim.
The first clean ARM64 builder attempt failed because patch was absent. A fresh
build using the existing cross builder and pinned 1.23.4 source archive passed.
Rechecked exact SM-G965N identity, current BOOT, backup and old plugin pin;
preserved the previous plugin/configuration/unit privately. Installed the
candidate, updated the plugin and configuration hashes, and restarted only
ModemManager. It enumerates the physical modem and one 4G mode. The visible
native panel now says “4G Only”. Desktop LTE and Bluetooth services remained
active, Wi-Fi-bound HTTPS204 passed and no units were failed. The current SIM
remains unregistered, so this does not claim a new successful cellular data
trial. No PIN change or manual operator change was attempted. No reboot was
performed for this update.

Installed ordinary Ubuntu Cheese and fprintd packages. Initial package setup
completed before the explicit live guard recheck; that subsequent check passed
against the unchanged #48 BOOT and verified backup. No partition was written.
Cheese opens but the kernel exposes no video/media device; preferences probing
also emits GLib missing-device errors. Closed the empty application. The native
fprintd manager starts on demand and returns an empty device array, while
fprintd-list reports No devices available. The live configuration disables
MEDIA_SUPPORT and TEE, with no enumerated SPI reader. The existing Samsung
media source covers older pipelines; it does not establish Exynos9810 FIMC-IS
support. The stock secure ET510 still requires its transport/security protocol
and a compatible biometric backend. Camera capture and fingerprint enrollment
remain unavailable. No fake camera/reader or PAM authentication change was
installed. Documented reproducible desktop setup and these boundaries in
DESKTOP_HARDWARE.md. Private package/runtime logs and all identity data remain
outside Git.

### 2026-11-20 — Verify live Wi-Fi station scanning

At the owner's request, explicitly requested a NetworkManager rescan on
wlp1s0, waited four seconds, and read its AP listing without recording SSIDs
or BSSIDs. The scan command succeeded and the listing contained 15 AP entries,
including the current connection, with signal strengths 22–100/100. A subsequent
HTTPS request explicitly bound to Wi-Fi returned 204. This bounded observation
verifies station scanning and continued connectivity, not scan endurance or AP
handover. No driver, network profile or device configuration was changed.

### 2026-11-20 — Audit current-boot kernel warnings before stopping

Read both the current-boot journal and the kernel ring buffer. The journal
contained 1,102 lines and only two broad error-keyword matches; it did not
contain all early boot warnings, so it is insufficient for a clean-boot claim.
The ring buffer had 234 warning-or-higher lines, including stack/register
context. It contained two RTC-probe GIC warnings for hardware IRQ 63 with an
invalid type, CPU feature variations across the heterogeneous cores (kernel
CPU_OUT_OF_SPEC taint), four unimplemented vendor modem bus-QoS messages,
14 unsupported NFC vendor notifications (opcode 0xf3f), three Bluetooth
advertised-but-unsupported transmit-power commands, and the old cbd v2
capability warning. MAX77705 RGB/haptic nodes were not found and the alternate
GPT was invalid with primary-GPT fallback. None of these are marked fixed.

No new warning-priority ring-buffer entry appeared within the preceding
15 minutes and systemd listed no failed units. There was no observed kernel
panic, real Oops report, BUG report or matching Panfrost/DECON fault. An initial
unanchored Oops keyword count falsely matched the normal ramoops backend
startup line; inspected its context rather than treating it as a crash.
The BBD timeout keyword line reports the configured ten-second wait and is
not, by itself, proof that the wait expired. Current use is quiet, but this is
not a warning-free boot or complete feature qualification. No device setting,
partition or driver was changed during this audit.

### 2026-11-20 — Qualify a physical NFC target and fix clock/startup lifecycle

The owner prepared a credit card with contactless/transport support. Started
ordinary-user neard polling and a bounded, private observation of tag/record
counts and property names only. The initial physical placement produced no
RF discovery or tag. Standard command responses alone had not qualified RF.
Compared the stock vendor configuration with Samsung's published HAL at
LineageOS android_hardware_samsung_nfc revision
61bc89fa5fb6b6c3fa47f99f9aaf6cf7967fc061. The owner configuration specifies
FW_CFG_CLK_SPEED=0x12 and that HAL sends a one-byte vendor command 0x28 before
CORE_RESET. Implemented it in the Linux NCI init callback with an explicit
proprietary response handler. No firmware image, RF-register file or secure
state was uploaded. No proprietary binary was added to the repository.

The first module build selected the host compiler and failed on ARM64 options.
Rebuilt with the ARM64 cross compiler, the matching NFC kernel configuration
and the preserved full kernel/NFC symbol tables. After exact model, current
BOOT, backup and candidate-hash verification, powered down NFC and hot-loaded
only the trial controller module. Bluetooth remained active. The clock command
completed; RF_DISCOVER response latency fell from roughly 444 ms to 10 ms and
the immediate unsupported vendor notification did not recur. The owner then
confirmed recognition. neard exposed one physical tag and four records. Neither
UID nor record values were retained in the summary or committed.

The first repeat test failed to power off while the card stayed present:
neard returned EBUSY because it retained its initiator socket. Added the tracked
GPLv2 patch to release that socket and its presence timer before power-down,
and corrected its negative-errno error formatting. The upstream source and
Intel notices remain intact. The daemon built successfully. Its first test run
failed because previous root-owned test logs prevented ordinary-user writes;
corrected ownership of only those test log files, then all three upstream
NDEF/SNEP suites passed. Preserved the original daemon privately and installed
the candidate. With the owner holding the target in place, three complete
power-off/on/poll/read cycles each returned one tag and four records. A final
power-off with the tag still active succeeded.

Rechecked the model/BOOT/backup guard and saved the original installed controller
and startup pins privately. Installed the qualified clock module with its
matching hash. The first distinct warm boot exposed a service readiness race:
neard was ordered after the simple Bluetooth unit, but started before the
helper had loaded the NFC generic-netlink family and failed. Bluetooth and
nfc0 subsequently registered. Added a bounded read-only readiness gate for the
actual controller driver and child NFC radio to neard's ExecStartPre. It does
not write hardware. Installed a frontend update that explicitly distinguishes
a detected tag with no NDEF records from no target.

The gate passed on the running device. After a second distinct warm reboot,
neard and Bluetooth started automatically, BlueZ was powered, and no unit was
failed. An ordinary-user power-on and poll again read one tag and four records.
The installed controller matched its startup pin. Wi-Fi-bound HTTPS204 passed;
this boot had zero unsupported-0xf3f notifications, NFC receive errors or failed
NCI sends, and no matching neard failure/critical log. NFC UI was reopened and
the owner was told the card could be removed. The earlier RTC/CPU/GPT warnings
are unrelated and are not marked fixed. Other tag technologies, card writing,
payments, secure-element functions, emulation and endurance are not qualified.
The tracked recipe now applies the neard patch; README records clock source,
installation readiness and the successful hardware scope.

### 2026-11-20 — Wireless GNSS test, desktop tools and resumable support state

The owner excluded camera/fingerprint and authorized continuing other system
features, requested startup management, GPS testing and a map app, and asked
for a maintained GitHub status that supports later continuation. Added latest
STATUS and HANDOFF documents, linked them from README/VALIDATION, corrected
stale README claims of entirely untested LTE/audio/Bluetooth, and added the
continuation entry points to AGENTS. Kept historical evidence and the explicit
fresh-image reproduction gap. Personal Tailscale/ChatGPT configuration and the
separate document-portal work remain outside this shared setup.

Read-only RTC inspection found the alarm on hwirq63 in edge mode while the
tracked DT uses IRQ_TYPE_NONE. No RTC or BOOT change was applied. The first
read-only GPT probe incorrectly assumed 512-byte sectors and found no header;
its initial command also had an unmatched Python parenthesis and did not run.
Corrected both and used the actual 4096-byte logical sector size. The primary
GPT header and entry array CRCs are valid, and its referenced last-LBA backup
header has no GPT signature. No metadata or partition geometry was written.
Recorded both investigations as remaining work, not fixes.

The owner reported USB removed and sky-facing placement. Used the handset's
Wi-Fi SSH destination, confirmed Wi-Fi-bound HTTPS204, and ran a private
300-second consumer as GeoClue on the existing guarded GNSS source. The UDC
sysfs state still said configured; retained that discrepancy rather than
claiming it independently proved cable removal. Fourteen valid NMEA sentences
arrived around 30 seconds, with GGA/RMC, eight GSA and four vendor sentences.
The final observation still had 14, zero invalid checksums, zero used satellites,
GSA fix type1, no GSV and no position fix. No coordinates or raw NMEA were saved.
UTC injection exists; SUPL/PSDS/LTO and prior-position assistance are not yet
implemented. Missing assistance may slow acquisition, but does not establish
the cause of absent continuous data. Added separate next-step investigations.

After the model/BOOT/backup guard passed, installed Ubuntu packages
gnome-startup-applications and gnome-maps. Added a GPS Test GTK frontend and
an unprivileged GeoClue test unit, bounded to five minutes, exposing only
counts/fix flags in a summary. A narrowly scoped Polkit rule lets the selected
account start/stop only that unit, including SSH; no generic unit management
or login autostart was enabled. The producer accesses only the existing
GNSS Unix socket, preserving the root supervisor's hardware/profile checks.
The app distinguishes old results and unknown satellite visibility when no
GSV arrives. Maps/network position is not treated as proof of satellite fix.

Service and desktop-file validation passed. Accessibility enumeration confirmed
real Startup Applications Preferences, Maps and GPS Test windows. The GPS GUI
showed the actual 14 valid sentences/no-fix state at 242 seconds in an additional
observation. Normal-user D-Bus start and systemctl start/stop passed without a
root desktop session. Updated cancellation handling and verified a new
three-second trial writes final/cancelled, then the unit reports success and
inactive. The initially written socket-pair test harness incorrectly used a
tuple as a context manager; corrected it to close both sockets. Five meaningful
fix/no-fix/checksum/malformed-coordinate/socket-summary tests then passed, as
did nine initial boundary checks and Python syntax validation. The checked
summary contains no coordinates or NMEA. Firmware, identities, private logs,
SSH keys/addresses and personal app settings were not added to Git.

Final app-install health check found no failed units, with sensor, Bluetooth,
neard and the GNSS socket active. The diagnostic unit was inactive/success
following cancellation, Wi-Fi HTTPS204 passed and no matching GPU/display
fault appeared in the current ring buffer. This does not clear unrelated
boot warnings or qualify a GNSS fix.

### 2026-11-20 — Fix GPS daemon crash and verify satellite/desktop location

Resumed GPS over Wi-Fi with the existing exact-BOOT/profile/backup guard.
All current FIFO inode pairs matched between GPS daemon, HAL and LHD. A
payload-suppressed metadata trace showed the daemon terminating with SIGSEGV,
while the HAL and old supervisor stayed waiting. Native GDB (installed from
Ubuntu, no frame arguments/debuginfod) located a null pointer in NdkSensorsInfo,
called by NdkSensorsStart and SensorsImpl's thread. The missing dependency is
Android HIDL sensorservice, not proof of an RF or assistance-only failure.
Raw traces/backtraces remain private and are not committed.

Added non-coordinate HAL capability/extension counters and strict status-line
forwarding. The actual HAL exposed gps-xtra, agps, agps_ril, gps-debug and
configuration interfaces, with capability mask198. UTC injection returned0.
The supervisor now watches the daemon even when the HAL's output pipe stays
open, drains complete status bursts, and terminates/reaps the remaining client
on failure. An opt-in root-owned diagnostic log socket selects errors only,
drops location/identity messages and redacts numbers/URLs. It was used briefly
and its temporary systemd environment drop-in was removed for normal trials.

Samsung's published Broadcom config documents hal SensorsEnable=false, and
this owner's daemon contains the setting. Generate a private copy of the
pinned gps.xml with only this attribute changed. Preserve the original file,
RF parameters, daemon binary and main Ubuntu sensor services. This disables
only the optional Android inertial-sensor dependency. The first 300-second
trial then produced3,291 valid sentences, invalid0, rather than stopping at14;
no fix at that initial window placement. The daemon stayed alive.

Added a root-only LTO cache using only the owner's SYSTEM gps_psds.conf V5
sources, certificate-verified HTTPS, bounded size, server Last-Modified age,
config/blob hashes and 24-hour reuse. A bare HEAD request received403; the
configured-source GET with the diagnostic user agent returned200, binary data
124,383bytes and a recent Last-Modified. No receiver firmware was flashed.
The standard gps-xtra callback ABI initialized with0 and accepted data with0;
the receiver's stored lto2.dat matched the cache SHA256. A full aided300s run
again delivered3,291 valid sentences and invalid0 but initially no fix.
Added the bounded refresh unit and hourly cache-check timer; service start
reported success. Downloads stay outside the vendor worker's isolated network
namespace, and missing/stale aid falls back to standalone. No blob is in Git.

The owner offered opening the window for a new trial. Normal-mode reception
without the temporary log socket reached a real fix by the138-second summary.
The full300s observation had4,448 valid sentences, invalid0, GSA3D, GGA/RMC fix,
GSV maximum10 within one constellation and GGA maximum8 used satellites.
Clarified that GSV's per-system maximum is not total all-constellation visibility.
The HAL's separate live count also showed changing satellite callbacks and
actual location callback counts. No coordinates or NMEA were printed/stored
by these diagnostics.

Added a real GeoClue delivery checker under the installed GPS Test desktop ID,
with permission scoped to the selected desktop UID. Root querying another
client's metadata failed, so no cross-client read was used. Restarted GeoClue
to load the selected-ID policy, then an ordinary-user client received a fresh
location1.2s old with reported accuracy3m. The checker reads only existence,
accuracy and timestamp, never latitude/longitude. Invoked Maps' actual window
current-location action; accessibility found no connection/location-disabled
error. This qualifies basic framework delivery, not map-centering ground truth
or surveyed3m accuracy. Direct raw GPS Test and Maps share a singleton receiver
source, so the app now tells users to close Maps before a raw test.

Built the successive own-Bionic helpers with warnings as errors; each replaced
HAL had its pin updated after guard checks and private rollback copies were
preserved. Tests cover real child-process failure detection, buffered status
privacy, XML-only option change, malformed config, stale/tampered/foreign aid
rejection and coordinate-free summaries. Camera/fingerprint were untouched.
Cold restart, suspend, moving outdoor accuracy, SUPL, previous-position aids
and a controlled aid/no-aid TTFF comparison remain open.

Read-only preparation for the next RTC step found GICD_ICFGR IRQ63/64 fields1:
bit1 is clear (level). The generic IRQ sysfs 'edge' label was insufficient and
would have led to the wrong edge candidate. No IRQ register was written.

After the successful fix/desktop checks, reviewed negative GNSS trial instance
states were archived privately and reset; their journal/debug evidence was
retained. This cleanup is separate from the hardware correction. The normal
receiver run uses no temporary log-capture environment, and Wi-Fi connectivity
was checked again. RTC-only BOOT preparation is a separate following change.


## 2026-11-20 — RTC IRQ candidate and guarded recovery transfer investigation

Prepared a BOOT-only trial changing the two RTC interrupt flags from NONE to
LEVEL_HIGH. Direct GIC distributor inspection showed level delivery; the generic
IRQ sysfs edge label was not sufficient evidence. The build tool checks the
actual inner FDT and permits exactly two changed bytes in the existing wrapper.
No kernel Image, ramdisk, outer DT, bootloader or protected partition is changed
by this candidate. Hardware qualification is pending.

Recovery sync upload stalled before creating its temporary image. Cancelled the
selected upload before BOOT write. Raw exec-in transferred the complete image
and matched SHA256, but left subsequent recovery shell channels stalled until
a selected-device reconnect. Added bounded raw transfer, reconnect, checksum
verification and bounded legacy fallback to the BOOT uploader. Four isolated
transport tests pass, including rejection of corrupt/discarded transfers.

The next guarded installer stopped because EFS no longer matched the earlier
snapshot; PARAM also differed during read-only review, while BOOT and the other
seven partitions matched. Repeated EFS reads were stable and EFS was not mounted
in recovery. The cause of the intervening metadata change is not established.
No protected partition was restored and no identity check was bypassed. Taking
a new complete nine-partition backup before any further BOOT update.


Fresh snapshot comparison localized EFS differences to ext4 superblock metadata
(mount/write time, mount count and written-byte counter fields); PARAM differed
in one block. No private field contents are included here. All nine new backup
files passed byte-count and SHA checks. The guarded installer then passed EFS
identity checks, reused only the checksum-matching temporary BOOT image, wrote
BOOT and verified its readback before rebooting. The native trial booted.

Migrated sensor/audio/Bluetooth/cover/LTE receipt pins only after checking the
new BOOT and full RECOVERY/EFS/CPEFS/RADIO/DTB/DTBO hashes against the fresh
snapshot. Native Bluetooth drop-in pins were included. All four driver services
became active. Live RTC flags are (0,31,4,0,32,4); invalid IRQ warnings and call
traces were both0. RTC advanced and a four-second awake alarm reached /dev/rtc0;
its alarm was cleared and the system clock was not changed.

A separate warm reboot retained/advanced RTC time and again had0 invalid IRQ
warnings and0 call traces. The first repeat command referenced a temporary file
removed by reboot, so it did not execute the alarm check; copied the public
verify-awake.py and reran successfully. Driver services, NFC device/neard,
Bluetooth powered, seven IIO devices and one sound card returned. Wi-Fi-bound
HTTPS returned204. Physical tag/audio/profile tests were not repeated here.
The public awake checker retains an existing alarm, uses an explicit bounded
trial and does not disable safety checks under python -O.

The remaining bbd_enable_lk timeout:10 sec line is informational watchdog
scheduling in bbd.c, not evidence that its timer expired. Preserve it and
separate it from real timeout failures. GPT fallback and missing haptic wiring
remain unresolved; no GPT/PMIC write has been performed in this RTC step.


## 2026-11-20 — Secondary GPT repair preparation

Read-only geometry/CRC checks confirmed 4096-byte logical sectors, 25 used
partition entries, valid primary header/array, and zero-filled reserved secondary
array/header sectors outside every partition. The Samsung header length is512
with a zero extension, not the usual92; the first strict tool refused it before
any write. Added explicit zero-extension handling preserving512 and tested the
full-header CRC. Five synthetic tests cover copy consistency, nonzero-tail
refusal, bad CRC refusal and out-of-bounds partitions.

Saved private primary and tail metadata snapshots on the handset and copied
them to the host. Host SHA checks and independent regeneration matched the
candidate. Current SM-G965N BOOT and six protected partition hashes matched
the verified model/backup receipts. The proposed maintenance writes only the
five empty reserved tail sectors; no primary/header entry, partition boundary,
GUID, filesystem, bootloader or protected partition is changed. Reboot and
post-write kernel/partition checks remain required before marking fixed.


The explicit secondary-only maintenance wrote/read back20KiB in the reserved
empty tail. Both header/array CRCs are valid, all25 primary/secondary entries
are identical, and Samsung header length512 was retained. A separate warm
reboot removed Alternate GPT is invalid (0), with original primary metadata
and restored secondary bytes unchanged. RECOVERY/EFS/CPEFS/RADIO/DTB/DTBO all
still match the verified backup. RTC invalid IRQ/call trace/panic/Oops/BUG
markers remain0. Driver services/neard/GNSS timers and Wi-Fi HTTPS204 returned.

The desktop-LTE service then refused its private provenance after recovery's
six-byte EFS superblock bookkeeping change. The exact trusted old EFS snapshot
was found; both old/new complete nine-partition backups passed full file/hash
checks. The existing bounded four-field proof passed; all nonapproved bytes
were identical. An initial legacy CLI attempt correctly refused Runtime not
mounted without modifying provenance. Prepared the isolated modem view under
exclusive state/runtime leases with no character devices or identity bindings,
ran explicit proof/revalidation, preserved old receipt and all NV/source data,
and tore the view down in finally. No original partition was written. Requested
normal desktop-LTE restart; actual current-SIM data service remains unqualified.

GPS warm-reboot regression was interrupted at264s by the GPT verification
reboot:2,852 valid sentences, invalid0, no visible/used satellites or fix in
that current placement. This confirms sustained receiver output, not a repeat
of the earlier successful window fix. No coordinates were retained. Earlier
basic fix evidence remains valid; warm-reboot fix reacquisition is still open.


Immediate LTE restart was refused by its once-per-boot attempt marker, created
by the earlier provenance failure before hardware load. Preserved that guard
and used a normal warm reboot rather than deleting the marker. Private runtime
provenance passed exact live original-partition checks before reboot. Following
boot again has0 GPT/RTC IRQ warnings, call traces and panic/Oops/BUG markers;
waiting for sensor-dependent automatic LTE startup. The storage maintenance
source also explicitly flushes its private receipt and rejects duplicate backup
entries; these host-only hardening changes do not require another GPT write.


Final reboot after provenance maintenance: desktop LTE, sensors, audio,
Bluetooth, cover and neard all active; failed units0, modem module loaded and
ModemManager enabled. Current registration is idle/packet service detached,
so this is service recovery, not LTE Internet verification. Wi-Fi HTTPS204.
Published the actual isolated maintenance sequence as a pinned-source wrapper
for future recovery-only EFS metadata changes; it retains the existing bounded
proof and preserves an occupied runtime rather than tearing it down.


Maintenance regression checks: existing private-runtime suite41 passed, and
three new wrapper tests cover both exclusive leases during proof/cleanup,
cleanup after proof refusal, and preserving an already mounted runtime. The
first wrapper test fixture hit unittest Mock's reserved assert_* naming rule;
explicit method mocks corrected that fixture and all three then passed. This
was a host test-fixture error, not a handset change. The wrapper source captures
the already executed successful sequence; it was not used to repeat a live
provenance write after the receipt had already been updated.


## 2026-11-20 — Real RGB output, standard LED class and warm-boot persistence

Baseline recheck: native #48, failed units0, no RTC/GPT/call-trace regression,
no LED/PWM class devices, existing unbound max77705-rgb/haptic platform children.
Reviewed the pinned Lineage RGB driver: channels1/2/3 are red/green/blue, channel0
is white, default low-power register code5. Built a separate derived trial from
the already corrected upstream LED source, preserving its copyright/license.
The trial attaches three software nodes to the selected existing RGB child,
checks star2lte/parent address0x66, registers standard indicator LEDs with
brightness cap1, and uses software timing rather than unqualified HW blink.
No PMIC parent/charger reprobe, DT/BOOT write, firmware or regulator change.
Readback is restricted to the four documented LED registers.

The first warnings-as-errors build exposed kernel API-name differences for
software-node groups/device attribute groups; corrected to the actual kernel
APIs and rebuilt successfully. Verified exact input/output/patch/Module.symvers
pins, matched module vermagic to the qualified running ABI, and checked current
BOOT/model and RECOVERY/EFS/CPEFS/RADIO backup hashes before device changes.
Loaded the standard multicolor dependency and explicitly bound only the RGB
child via driver_override. Initial enable was00, all outputs off. No PMIC IRQ
register dump was used.

Fifteen bounded low-current pulses across red/green/blue passed current/enable
and off readbacks, with finally leaving all off. The owner reported blue, red
and green blinking. The published guard/control script then passed a test,
stopped/unloaded only the selected driver, restarted it and passed another
test. Enabled g965n-led.service and performed a normal warm reboot. Service
active, all three class nodes/max_brightness1 restored, new readback test passed
and failed units0. RTC/GPT/call-trace/Oops/BUG markers remain0 in that check.
Existing early MFD missing-node messages were not hidden. GNOME notification/
charging policy and calibrated brightness/HW patterns remain unimplemented.

Rebuilt through the new public build-only recipe in a fresh directory; exact
patched-source hash and module build passed. The broad existing PMIC C tests
first lacked repository-relative DTS, then correctly rejected an old full-DTS
pin. Reviewed CPU-cache-only commit91d74ac against the original and proved the
charger node byte-identical. Refreshed only that topology reference pin. All
three actual-C fault-injection/charger-topology checks now pass. No firmware,
private module bundles or identifiers were added to Git.

Haptic preparation located the vendor PWM gate/Q-channel and parent CMUCAL
mux/div registers. Read-only values: PERIC0 mux0x10, gate0x200000, QCH0x3f0002,
TOP parent mux1/div5. This does not prove a clock rate. A separate follow-up
reading PLL_SHARED2 CON0/CON1 and DIV2 terminated with userspace SIGBUS; the
specific blocked read was not isolated and was not retried. No clock/PWM/motor
power register was written. Haptic remains pending a reviewed firmware/provider
access route and real rate/supply verification; do not substitute a dummy clock.


## 2026-11-20 — Haptic clock investigation and PWM-only preparation

The owner requests autonomous continuation and prioritizes vibration. A new
five-minute GNSS run after boot completed with3,279 valid sentences/invalid0,
but satellites0/fixfalse at the current unattended placement. No location
reacquisition claim is made.

Pinned vendor ra.c/fvmap.c show runtime firmware correction of PLL addresses.
A Python SRAM metadata read again received SIGBUS. Replaced byte/slice MMIO
with aligned volatile32-bit reads, matching the actual ACPM kernel driver:
framework plugin metadata and all13 frequency-map domain headers then parsed.
Firmware maps two TOP PLL addresses to offsets0x1a0/0x2a0 rather than the old
source offsets. Aligned32-bit reads at those firmware-qualified addresses passed.
This establishes that the prior failure was not proof of an access prohibition;
it does not justify reading arbitrary/unmapped registers or whole firmware.
No firmware dump is published and no ACPM command/PLL write was sent.

The decisive PWM wiring evidence is vendor pwm-samsung.c: counter arithmetic
uses pwm_sclk, while pwm_pclk only enables the register interface. Its clock
provider registers pwm-clock as fin_pll1:1 (26MHz). Preparing a separate board
module aliases the existing real oscillator to mainline's timers clock and
opens only the dedicated PWM APB gate, restoring its prior bits at teardown.
It registers the built-in Samsung PWM driver with the exact stock s3c6400
variant and output channel1 only. No dummy clock, shared PLL retune, motor
power or pad mux enable is part of this PWM-only stage. Warnings-as-errors
ARM64 module build succeeded; hardware counter measurement is next.


PWM-only hardware trial passed: source_hz26,062,180, reload47, prescaler26,
divider1,60,179 valid sample intervals. The counter was disabled and unexported
in finally. This agrees with the real26MHz oscillator path, not the APB parent.
Subsequent pin inspection corrected an insufficient assumption: the bootloader
had already left gpp3-1 function2 and motor boost gpg1-7 outputHIGH. The PWM
stage did not change these pins or write PMIC MOTOR_EN, but its initial MOTOR_EN
was not read and it must not be described as confirmed rail-off throughout.
The initial motor-board guard correctly refused this unexpected function2.
Reviewed the exact stock PWM2 function/unclaimed ownership, then accepted that
known initial state with restoration; no unrelated alternate function allowed.

A first pin map used a nonexistent generic func2 mux name and probe refused.
Used Samsung's actual PINCFG_TYPE_FUNC pinconf under an exclusive GPIO claim.
This registered the real GPIO-backed motor regulator with boost forcedLOW,
period48,828ns PWM1 and the standard rumble consumer. Legacy PWM lookup-table
functions were not exported by7.1; switched to the exported standard translator,
managed release and real controller linkage. The exported helper initially
needed an explicit prototype for warnings-as-errors; corrected that build.
No force-loading/unchecked symbol or parent-PMIC reprobe was used.

The generic trial preserves upstream notices, limits magnitude32767/duty75%,
uses the reviewed MAX77705 bias fix and exposes a distinct FF_RUMBLE input.
Initial state boost0/bias1/motor0/config82. A bounded100ms/magnitude8192 effect
showed boost1/bias1/motor1/configc2, automatic motor0/config82, then boost0/bias0
on close. An independent systemd rail-cut fallback was armed before output.
Four200ms/magnitude16384 cycles passed. Simultaneous accelerometer Z standard
deviation was280.34/283.97/202.39/310.89 during pulses versus3.94 before and4.07
after; read errors0, supporting actual mechanical response. Intermediate quiet
periods included decay. Raw samples stayed private; no audio/coordinates saved.

Public control test, ordered unload/reload/retest and normal Ubuntu user open/
close passed. Added only this dedicated input's uaccess rule and automatic
startup service. First complete cross-build failed on missing ARM64 libc
headers; added libc6-dev-arm64-cross to the build Dockerfile/environment.
The final new-directory recipe built all modules and four bounded/read-only
ARM64 tools. The actual patched magnitude function passed393,216 strong/weak/
period cases with ASan/UBSan, not a separate mathematical implementation.

First warm boot retained output but reported device_links_driver_bound WARNING:
the custom link targeted the unbound PWM class device. Fixed it to the actual
pwmchip_parent exactly as PWM core does, rather than hiding the warning or
removing ordering. Preserved the earlier candidate, stopped the service,
verified original pad function2/boostHIGH restoration, replaced only the board
module and its pin, restarted/tested, then rebooted separately. The final boot
has active haptic/LED services, successful rumble/automatic stop, settled
boost0/bias0/motor0, device-links warning0, call-trace/Oops/BUG0 and RTC/GPT
warning0; failed units0. The temporary warning is superseded only for that
fixed scope. Stock waveform parity, calibrated force, long-term heating,
suspend restoration and GNOME notification policy remain open.


## 2026-11-20 — Physical compositor swizzle A/B preparation

On native #48 after haptic qualification, compiled a fresh upstream uinput
module against the current qualified kernel output, preserving its original
source notices. Used only a bounded temporary virtual keyboard for configured
Super/Super+A/Escape actions and removed it after capture. Three fixed Cairo
GTK windows exercised the actual connected DSI desktop, not a virtual monitor.
The first precheck found display DPMS off and refused before input loading.
Preserved that failure, established the normal session idle inhibitor first,
then woke display power and repeated; original idle/lock preferences were not
rewritten. Original screen power/lock state is preserved privately for cleanup.

Baseline1 captured24 actual transitions with private Sysprof data. Opening
paint p95 was23.236/23.128/22.297ms for picker/grid/picker-repeat; corresponding
frame-clock dispatch p95 was30.175/30.933/28.967ms. These are operation timings,
not direct presentation FPS. Physical over-budget paints were reproduced.

Prepared a timed per-user Shell-only profile for the already tested NEON
candidate. It preserves every accepted profile file and library, verifies the
known baseline/candidate Gallium hashes, identical remaining coherent build
outputs and local links, and uses a separate wrapper/vendor/drop-in. A root
four-minute restoration job is armed before any user-file change. The initial stage included no permanent accept action; hardware candidate
comparison and restoration were pending at that point. The following evidence
supersedes that pending state; system libraries remain unchanged.


## 2026-11-20 — Physical Mesa NEON A/B/A, retained overlay and reboot

On the actual connected DSI display, each phase used three fixed Cairo GTK
windows, four warmup cycles and24 configured overview/app-grid transitions.
Opening paint p95 in ms (picker/grid/picker-repeat): baseline1
23.236/23.128/22.297; NEON10.778/10.835/13.537; restored baseline2
22.519/24.655/22.322. Paints above16.7ms were4/4/4,0/1/0,4/4/4.
Frame-clock dispatch p95 remained17.165/23.628/21.849ms with NEON: this
improves the identified conversion/paint hotspot, not all animation latency.
These are Sysprof operation durations, not presentation FPS. Raw captures and
input timestamps remain private. First baseline2 SSH connection timed out before
the test began; both network paths were reachable on recheck and retry passed.
No network root-cause repair is claimed.

The first timed overlay was actually removed and original Shell DSO mapping
restored before baseline2. A separate final overlay was applied, checked using
fresh SSH and three stable coherent Shell mapping observations, then explicitly
kept. Added keep requires guarded current BOOT/protected backups, unmodified
parent files, physical comparison, pixel checks and post-startup evidence. It
cancels the independent four-minute restoration timer only after these checks.
Parent profile/library files and system Mesa remain intact; restore the child
overlay before modifying the parent. Source: experiments/mesa/physical-session.py.

Two exact RGBA/BGRA GPU readback runs used Mali-G72/Panfrost and the candidate
Gallium mapping:200 frames/13,107,200 bytes/zero mismatches. The second also
allocated256MiB of live textures with zero mismatches. The first command had
invalid env option ordering and failed before executing the test; corrected
command passed and the failure log was retained privately. Shared test source:
experiments/mesa/gpu-readback-bgra.c.

Subsequent actual warm reboot retained the candidate Shell mapping and actual
Panfrost DRM render descriptor. Serious kernel patterns/Call trace/Oops/BUG and
matching GPU faults were0; failed units0. Audio, Bluetooth, NFC, modem, sensors,
haptic and LED units were active, seven IIO devices enumerated, RTC readable.
This is startup regression evidence, not fresh audio/NFC peer validation.
Initial HTTPS check incorrectly selected wlan0; actual interface wlp1s0 returned
HTTPS204. No network configuration was changed. Compass root/desktop direct
D-Bus access was denied by Ubuntu's intentional GeoClue-only policy; querying
as geoclue returned HasCompass=true. Do not weaken this policy.

Added clean Mesa builder variant neon, pinned both patch hashes and original/
patched format_utils hashes. New isolated native source preparation applied
both patches at zero fuzz and verified the entire source tree. Existing build
receipts/binaries were preserved. Builder self-tests passed. First native
swizzle test staging omitted its companion C source and failed before compile;
staged that existing public file and reran:1,296 swizzles, both normalization
modes,0..33 pixels, unaligned and in-place all passed. Native clean configure/
full rebuild is tracked separately from the already-qualified incremental
candidate; neither builder installs or flashes anything.


The desktop-only compass socket delivered6 finite0..360-degree samples after
reboot. Direct root/ubuntu D-Bus rejection therefore does not indicate a broken
backend; the existing geoclue-owned socket relay remains the intended route.
Sensor supervisor journal error lines since boot0. Standard timedatectl reports
CanNTP=yes/NTP=yes/NTPSynchronized=yes. This verifies Ubuntu network time sync,
not a cold RTC retention or suspend wake test. Restored the pre-benchmark screen
power-off state; no idle/lock preferences changed. While charging at95% and
battery30C, started a separate normal-user clean Mesa build with Nice10,
CPUQuota100% and two build jobs. First progress57/1325 with failed compile
markers0; output adoption/hardware qualification remains pending. Service:
g965n-mesa-neon48-clean-build.service (user), private work neon48-clean-rebuild.


## 2026-11-20 — Post-NEON remaining-function read-only review

Current SIM modem power is on, state/3GPP registration both searching, no
access technology reported and no unlock required. No SIM identity/APN/raw
modem log exported; no attach/data success inferred. Existing historical
specific-SIM IPv4 success remains valid. No radio reset or network settings
were changed during this review.

RTC versus synchronized system UTC differed0.53s. Targeted current full dmesg
patterns: RTC IRQ/GPT/touch timeout/sensor timeout/P2P IF_ADD timeout0.
Vendor bus QoS notice4 and CPU capability-difference notices9 remain; this is
not a globally warning-free boot. Modem g965n_compat.h deliberately reports
missing vendor QoS rather than pretending a working frequency/interconnect
policy; no invented frequency table or warning suppression was added.
Clean user build remains active at202/1325 with failed compile markers0.
No new binary was installed. These observations supersede earlier idle state
only for this current modem query, not the previously verified LTE trials.

## 2026-11-20 — Remaining-warning review and standard feedback investigation

Rechecked current native48 and background Mesa clean build:394/1325, unit
active and no compile failure markers, failed system units0. Current kernel
warning review found only the previously recorded missing RGB/haptic child DT
nodes, four missing vendor QoS notices and Bluetooth advertised transmit-power
quirk among targeted driver error/warning patterns. Pinned hci_sync.c explicitly
logs HCI_QUIRK_BROKEN_READ_TRANSMIT_POWER in its known-quirk report; btbcm.c
already applies it on star2lte. It is not a new command timeout to hide.

Ubuntu feedbackd was absent. After current SM-G965N/BOOT/protected-backup
preflight, started installing the stock no-recommends feedbackd package with
private apt log, to investigate standard haptic consumers. No new udev match,
notification hook or vibration theme is enabled yet; package installation is
not evidence of real feedback output. Desktop integration qualification pending.


## 2026-11-20 — Persistent-client haptic idle-power bug fixed on hardware

Installed Ubuntu feedbackd0.2.1-1build2 (normal package license unchanged).
Reviewed its original Ubuntu source locally; initial Debian0.2.1 source URL
returned404, then the Ubuntu original archive succeeded. No upstream binary,
source archive, identifiers or private measurements enter Git. New dedicated
udev match and user D-Bus/unit use only this board's rumble input and an own
no-parent theme: single100ms events, full/quiet, silent empty; no periodic or
LED pattern. fbd-theme-validate passed. Original driver's standard fbcli trial
returned0 and observed motor on then off, but actual idle state with persistent
evdev open was boost1/bias1/MOTOR_EN0. Disabled/stopped feedbackd immediately;
closing it returned all0. Do not call that earlier idle state power-off.

Added0006 patch, scoped to MAX77705: evdev open no longer powers hardware;
actual playback enables bias/supply, successful stop disables PWM/supply/bias.
Enable failures unwind, PMIC stop failure still disables PWM and real supply,
and power-off failures retain state for close retry and produce error logging.
Other PMIC variants keep their original policy. HAPTIC_IDLE_POWER.json pins
input/patch/output; builder --idle-power applies it separately from the original
0005 variant. Original notices preserved. Actual extracted production functions
passed ASan/UBSan:100 held-open cycles, repeated enable/close, injected bias/
supply/PWM/start/stop errors and retry cleanup. Initial module build passed;
added explicit power-on error reporting and rebuilt before any device use.

After fresh model/BOOT/protected backup preflight, preserved old installed
module and pin privately, stopped feedbackd/haptic, replaced only the haptic
consumer module and its checksum, and restarted guarded haptic service. No
BOOT/firmware/identity partition changed. With feedbackd holding evdev open,
idle was boost0/bias0/MOTOR_EN0. Three real standard fbcli calls each returned0,
observed boost1/bias1/MOTOR_EN1 and then all0 automatically while the same daemon
remained active. Each trial had a separate4s root rail-cut fallback cancelled
only after success. Raw register-timing samples remain private.

Updated bounded diagnostic compile-time idle expectation for this variant,
preserved/replaced the installed test binary and its program pin, and passed
guarded100ms/8192 rumble: actual on, automatic full-off before close and off
after close. Original builder default retains old diagnostic expectation.
Enabled the qualified feedbackd user service only after these checks. Final
idle all0, serious kernel patterns0 and failed system units0. Warm reboot of
this new module is pending; it was not forced during the independent active
Mesa clean compilation (latest978/1325, compile failure markers0).
Standard libfeedback caller integration is verified, not an automatic GNOME
notification/keyboard hook. See experiments/pmic/feedback/README.md for source,
installation order, safeguards, limitations and rollback. Whole-device battery
savings and long-term motor heating are not measured by rail-off readback.

Source review before reboot also found firmware may retain bias/MOTOR_EN at
boot. Added explicit checked motor-off/bias-off initialization before registering
the MAX77705 input; failed writes now fail probe instead of exposing a device
with unknown initial state. Added actual init-function tests for retained bits
and both write failures. Rebuilt the entire optional module/tool recipe in new
private output, preserving earlier candidates. Fresh guarded module/pin-only
replacement and restart passed: idle all0 before feedbackd opens and after it
opens, then guarded100ms output/automatic rail-off/close-off all passed. Original
pre-idle module/tool backups remain intact; intermediate lazy module retained
separately. Latest clean Mesa build1286/1325/failed compile markers0, still active.

Clean Mesa source build subsequently completed1325/1325, no failed compile
markers, receipt phase built. Output remains separate from the qualified live
Shell. Initial Git whitespace review flagged unified-patch context prefixes,
not generated C defects; regenerated0006 with zero context, updated patch hash
and verified zero-fuzz application yields the identical already-tested source
hash. No runtime binary/source semantics changed for that formatting correction.


Clean build verify passed all source/output/launcher/link pins. Actual normal-
user launch mapped the newly clean-built Gallium, Mali-G72/Panfrost and passed
100 RGBA/BGRA frames/6,553,600 bytes/zero mismatches plus256MiB live textures.
It was not substituted into Shell; physical animation qualification remains
separate. After confirming build unit inactive/success/exit0 and fresh protected
backup/module preflight, initiated ordinary reboot under existing consent to
verify the new idle-power consumer path. No BOOT flash was needed.


## 2026-11-20 — Idle-power final warm boot verified

First SSH shortly after reboot timed out; read-only recheck found both Wi-Fi
and USB SSH reachable, and retry connected. No network configuration changed.
Fresh protected preflight passed. Haptic/LED/sensor/audio/Bluetooth/NFC/LTE
services active, feedbackd user service active. Before any effect, actual
boost0/bias0/MOTOR_EN0, including firmware-retained state initialization.
Guarded100ms/8192 output/automatic full-off/close-off passed after reboot.
Separate standard API fbcli trial also observed1/1/1 during playback and0/0/0
at automatic completion; independent4s rail fallback cancelled after success.
Serious kernel patterns0 and failed system units0. Existing qualified Mesa
Shell overlay stable mapping confirmed separately; clean-built Mesa remains
an isolated tested candidate. This supersedes only idle-power warm-boot pending
entries above, not all profiles/suspend/notification policy qualifications.

## 2026-11-20 — Residual physical animation latency investigation

Fresh SM-G965N/kernel48/protected-backup guard passed. Current qualified NEON
Shell allows CPUs0..7; policy4 CPUs4..7 schedutil min1066/max2327MHz, policy0
CPUs0..3 schedutil min349.916/max1499.333MHz. Both advertise only performance
and schedutil. Started fresh actual-DSI overview/grid profiling with the same
three fixed Cairo surfaces and configured shortcuts, capturing all opening
operation marks rather than only paint/dispatch. Earlier captures remain
private and unmodified. Original screen/lock state preserved in a separate
private trial directory. No clock/governor/affinity setting changed yet.

Fresh NEON control1 reproduced actual DSI opening dispatch p95
17.732/23.776/17.566ms (picker/grid/repeated picker), while paint p95 was
10.492/11.033/10.569ms.24 transitions with60/56/61 opening dispatch samples.
No compiler was running. Prepared a separately protected original-governor
snapshot/restore program and armed an independent180s root restoration before
switching the two existing CPU policies temporarily from schedutil to their
advertised performance governor. No max frequency/voltage/thermal/GPU change.
Performance capture runs the same fixed scene/shortcuts; no persistent policy
adoption is implied. Detailed Sysprof traces remain private.

The bounded all-CPU performance capture completed24 transitions and restored
both governors to schedutil, cancelling the independent restoration timer.
Dispatch p95 was10.240/18.279/17.253ms, paint10.747/10.873/10.557ms;
maximum dispatch still27.260/27.872/26.713ms. This intervention helps portions
of dispatch but does not eliminate long frames; no permanent fast-governor
policy was installed. Started separate main-thread userspace perf sampling,
using the existing native perf tool and private frame-pointer stacks, on the
restored governor policy. Sampling is separate from timing comparisons.

Main-thread perf sampling on restored governors captured24 transitions. Opening
samples were86 picker and105 grid. Mesa was only3 top-frame samples for picker,
18 for grid (3 tiled-image helper hits); GJS/SpiderMonkey/GLib/GObject work was
distributed. This does not identify a new single dominant Mesa function.
Temporary main-thread util_min768 produced mixed results: dispatch p95
17.422/23.307/10.759ms; maxima25.053/28.775/22.419ms, app-grid over-budget
count9 versus control7. Restored original clamp0; no persistent clamp adopted.
CPU capacity was already asymmetric (little368/big1024), with the existing
measured DT calibration, so no missing-topology patch was invented. Began a
separate bounded all-Shell-thread big-cluster affinity trial with per-thread
original affinity/start-time snapshots and an independent180s restoration.
No CPU frequency bounds/governors or other apps' affinity changed.

The all-thread big affinity trial was not a consistent improvement: dispatch
p95 22.216/21.638/17.700ms, grid max36.427ms. Restored each existing thread's
original affinity/start-time match and cancelled fallback; no affinity policy
adopted. Current logical monitor is scale2, physical1440x2960 at59.986Hz, so
no incorrect scale1 topology workaround was applied. GPU simple_ondemand polls
at50ms, current/min260MHz and validated states260/455/572MHz. Started a separate
bounded455MHz-floor trial after the NEON correction; this repeats the older
pre-NEON hypothesis under the changed bottleneck. Independent180s restore
returns min260MHz/poll50ms. No voltage/max-clock/thermal override.

GPU455-floor trial did not consistently repair latency: dispatch p95
17.284/19.532/17.735ms and max28.747/29.383/40.370ms, including two picker
paints above16.7ms. Restored260MHz min and50ms poll; no persistent floor.
Started bounded Ubuntu Dock extension isolation with normal gnome-extensions
API and an independent180s re-enable timer. This is a root-cause experiment,
not permission to permanently remove the dock or disable general animations.

Dock isolation was also inconsistent (dispatch p95 14.546/24.166/23.056ms;
grid max30.022ms); restored the extension. Installed GNOME Shell and libmutter
already match configured Ubuntu updates/security candidates, so no speculative
package upgrade was performed. Idle CPU sampling showed no heavy background
compiler/indexer bottleneck (largest sampled process2% of one core).

Prepared separate MIT-derived AArch64 little-endian NEON32-bit tiled-image
candidate, restricted to existing aligned/non-depth/stencil fast path. Original
source notices retained in the source/adjacent MIT notice. Exact scalar-loop
comparison passed2,688 store/load cases with tile offsets, row padding,
source/destination guards, including permissive skew cases in the scalar shim;
ASan/UBSan and optimized native tests both passed. Early O2 scalar helper lacked
the production forced-inlining contract, so its10x microbenchmark was discarded.
Reran at O3 with forced-inline scalar helper and compiler memory barriers:
0.913172s scalar versus0.234384s vector in the synthetic1024-square loop.
This is not an integrated scene/performance success. Started isolated native
rebuild of the actual tiled object/archive/Gallium in a new complete build copy;
original source/runtime libraries are preserved, no desktop change yet.

First isolated tiling build guard refused two absolute read-only linker inputs
(dri.sym/dri.dyn) before creating any copy. Reviewed/rebased only those inputs
into the new tree; then object/archive/Gallium rebuild passed. Candidate actual
GPU readback passed100 frames/6,553,600 bytes/zero mismatches and256MiB live
textures on the candidate Gallium. Added a parent-overlay inventory reader that
parses only pinned wrapper literals (never executes user wrapper code), checks
five coherent inputs/local links and requires child drop-in sorting after the
parent. Enabled a separate four-minute child overlay without modifying the
qualified NEON parent. Initial host fixture used unresolved macOS temp paths;
resolved the fixture root and reran four tests (valid parse, wrapper drift,
output drift, escaping link) successfully.

Actual DSI tiling trial did not establish a scene improvement: dispatch p95
17.536/22.842/21.596ms, grid paint p95 13.185ms/max17.309ms and dispatch
max38.462ms. Explicitly removed the child and verified the prior NEON mappings.
No tiling optimization accepted as a desktop fix. Restored control2 dispatch
p95 18.182/18.813/21.937ms; no JS_/GJS_/MOZ_ runtime overrides were set.

Prepared a separately disabled-by-default star2lte input-frequency QoS module.
It uses only standard cpufreq policy min requests on the two already-qualified
policies, caps targets at the current policy max (within1499.333/2327MHz),
raises for500ms after touch-position or keyboard-press events, and has no idle
polling or frequency floor. Thermal/max policy remains authoritative. Handler
filters out FF/sensor-only inputs and does not record keys/coordinates. Worker/
release paths are serialized and exit cancels work/removes both requests.
Cross-build against the qualified native48 ABI passed; hardware trial pending.

First input-QoS qualification failed: no floor change was observed. The shell
wrapper initially continued to the exploratory benchmark after the Python
assertion, so that first boost-labelled capture is invalid as an active-boost
comparison. Unloaded the module and switched subsequent wrappers to set -eu.
A separate diagnostic preserved unchanged input-time policy values privately.
Found current input core iterates device IDs while id->flags (not driver_info),
so the initial wildcard terminated before attachment. Replaced it with explicit
EV_KEY/EV_ABS flags plus existing capability filters. Added the actual ID table
to host tests, alongside production worker expiry/retrigger/stale-work/jiffies-
wrap/partial-failure/shutdown checks; ASan/UBSan passed. Rebuilt separately.

Corrected hardware qualification observed policy min/max1499.333/1499.333 and
2327/2327MHz after the real virtual-keyboard event, then original min349.916/
1066MHz after expiry. Guarded load and independent180s unload fallback. First
qualified active-input capture24 transitions: dispatch p95 17.090/17.811/
10.333ms, medians5.548/10.062/5.516ms; app-grid max19.062ms versus restored
control2 max28.059ms. Picker max34.463ms remains. Unloaded module/restored floors
and cancelled fallback. These initial results justify repeat A/B measurement,
not a claim of all long frames removed. Running restored control3 then a second
qualified input-boost capture before considering persistence.

Restored control3 followed by a second qualified input-boost run reproduced
an improvement in app-grid worst dispatch34.768→24.547ms (first pair
28.059→19.062ms). Controls' picker/grid/repeat medians were7.463/12.542/
7.308ms versus repeat boost6.075/10.798/6.141ms. All idle floors restored
on unload. Not all dispatches meet16.7ms.

Added per-opening analysis because pooled p95 near four startup outliers is
sensitive to whether a scene has61 or62 frame samples. This can exaggerate a
p95 improvement. Four-opening median of app-grid peak durations was26.215/
23.921/22.837ms in the three controls and18.280/21.199ms in the two active
boost runs. Median app-grid first-completion notification71.353/76.967/
76.093ms versus62.571/72.299ms. Notification gaps are compositor event timing,
not photometric/scanout FPS. Started one additional bounded comparison with
only the Shell main thread on CPUs4..7 (workers unchanged), plus the qualified
input boost, with separate180s affinity/boost restoration timers.

The combined main-thread-affinity trial worsened app-grid dispatch p95 to
27.769ms/max36.543ms and12 over-budget marks. Restored main affinity and
unloaded the trial; no affinity override installed. Kept only the repeatably
beneficial bounded input-QoS approach for current-boot adoption.

Refined initialization to target the lesser of CPU-info max and the qualified
1499.333/2327MHz ceilings, allowing standard MAX constraints to take precedence
instead of permanently latching a transient boot cap. Rebuilt all module/QA
sources through the source/ABI-pinned builder. Installed a new root-private
checksum/ABI/model/backup guarded controller and service, after verifying exact
staged source/module bytes; no existing user files or partition were replaced.

Actual lower-MAX QA loaded only a1794MHz big-policy maximum request. A keyboard
event under the adopted boost yielded min/max1499.333/1499.333 and1794/1794MHz,
then idle349.916/1066MHz after expiry. Removed QA request/helper and temporary
keyboard: prior maxima1499.333/2327MHz returned. Independent QA/unload fallbacks
cancelled after success. Enabled the guarded current-device service. No raw
clock/voltage write or CPU/GPU maximum increase. Native MAX constraints were
verified, not high-temperature accuracy or whole-device energy savings.

Owner then said current performance was sufficient. Stopped additional tuning
and did not perform the planned further reboot. The new service is active and
enabled in this boot; its next-boot startup remains unverified. Final read-only
cleanup/health review and documentation follow; no further tuning is authorized
by that acceptance. Negative/invalid trials remain recorded to avoid repetition.


Final current-boot read-only review: adopted input service active/enabled,
CPU governors schedutil, main affinity0..7, original NEON parent accepted and
tiling child rolled back, Dock restored, QA MAX/temporary keyboard unloaded.
First sample caught elevated input-time minima; a separate3-second follow-up
observed only the original349.916/1066MHz minima. Do not call an input-time
snapshot a stuck idle floor. No future trial timers remained. Failed system
units0, serious kernel patterns0 and matching GPU faults0. Full startup of this
new service on a future reboot is intentionally pending after owner acceptance.

Owner then requested a software center and Chrome, followed by log-error-first
priority. Started installing stock gnome-software (APT backend, without adding
snap) after fresh model/BOOT/protected-backup preflight. Official Google support
now documents Linux ARM64 packages; initiated direct official ARM64 Chrome
package download, architecture/name verification and separate apt installation.
These are requested app installs, not default image contents. Package binaries,
private apt logs and personal app settings remain outside Git. Outcome pending.

## 2026-11-20 — Log-first follow-up: missing PAM module and RGB regmap identity

Error-priority boot journal grouped58 kernel entries (mostly legacy modem
normal-state messages at error priority),12 GDM,2 Bluetooth SAP and one user
im-launch scope failure. Real missing pam_gnome_keyring.so was repeated after
session restarts. Installed stock libpam-gnome-keyring/gnome-keyring and actual
native PAM library dlopen passed. No PAM password policy, password, keyring
contents, login/session or document-portal source was altered; fresh GDM login
replay is not verified without another login. Kept other records for investigation
rather than globally suppressing error priority.

App requests: gnome-software46.0 and PackageKit/appstream backend installed;
No snap was added. Official Google ARM64 Chrome158.0.8127.36 package downloaded
and architecture/name checked before apt installation. It is not included in
public image recipes and no proprietary binary/profile/log is committed. Initial
plain launch did not remain running; a new-tab check used an inappropriate
10s subprocess lifetime and timed out, so its UI outcome is unverified. Moved
subsequent launch to a normal-user manager scope and retained sandbox/profiles.
Actual GUI navigation remains a separate check; process counts alone are not
accepted as rendered-page evidence.

The regmap collision is the separate relative-offset RGB map on the *same*
I2C0x66 device as the top PMIC; the separate charger is0x69 and is not replaced.
Added only regmap_config.name="g965n-rgb" in a separately pinned0007 patch.
No register addresses, offsets, current limits, access masks or charger/haptic
configuration change. Optional build-led-trial.py --named-regmap applies0007
on the existing0004 result; fresh ABI-pinned build passed. After model/BOOT/
protected-backup preflight preserved old module/pin, stopped only LED service,
installed the checked module and restarted. Three low-current actual register
on/off tests passed, all LEDs off. Named debugfs3-0066-g965n-rgb exists alongside
preserved core3-0066, new duplicate-error count0. Original boot message remains
historical. No reboot or kernel image write was needed; next boot of this name
change has not been tested.

A delegated personal-app request also added exactly one enabled GNOME ChatGPT
autostart item reusing the one existing ChatGPT launcher. Configuration/profile
paths stay private and are not public defaults. No new profile or auto-login
setting changed. Current-session launch/login startup verification still pending;
no logout/reboot is performed for that test.

## 2026-11-20 — Resume hardware/system work; retain complete warning evidence

Owner reported a white ChatGPT window, then explicitly stopped that investigation
to continue it in another context. Stopped personal-app/UI investigation here;
did not close existing apps/tabs, erase profiles, change login, remove the
enabled personal autostart or claim the white page repaired. Software Center,
PackageKit/AppStream and official ARM64 Chrome packages are installed, but
rendered-page/catalog/install-flow verification is not complete. Personal
app configuration/binaries remain excluded from public recipes and Git.

Fresh exact-device/BOOT/protected-backup preflight passed. Reused the checked-in
read-only kernel-health collector without changing drivers/settings. Private
collection retained full boot header/978 ring lines/error57/warn68; journal378
lines lacked its initial header. A journal-only CPU-warning query misleadingly
returned0; complete ring shows52 register variations plus1 unsupported notice.
This is collection coverage, not a repaired architecture warning. Hub reset
unconfirmed1 and modem vendor bus QoS4 remain. Call trace/SError/GPU PLL failure/
rollback/GPIO-direction counts0; separate serious-kernel/GPU-fault queries0.
Failed system units0; adopted input/LED/haptic/Bluetooth services active.

Existing automatic login is enabled and no password is supplied to keyring PAM.
The library is now present/loadable, but this is distinct from the remaining
keyring unlock warning. No empty keyring password, password reset, auto-login
change or login replay was used. BlueZ5.72 adapter1/poweredtrue; SAP interface
absent. Stock experimental mode is off. Upstream SAP dummy initialization can
fail before RFCOMM socket setup and returns-1, so the displayed EPERM alone
does not justify CAP_NET_RAW or a claim that the controller failed. Real SIM
APDU bridging is unimplemented; no dummy SAP service was enabled as a fix.
GDM46.2 upstream remote-display factory subscribes to the shared display store
then asserts remote type; this matches the observed assertion text, but the
installed Ubuntu patch stack/reproduction needs separate verification. Kept
the local working session and did not restart GDM or disable remote features.

PMIC/Mesa rebuild/rollback documentation and current summaries updated. Re-ran
production input worker/filter ASan/UBSan tests,4 parent-overlay tests,3 timing
analysis tests,2 Mesa builder tests and source/patch pin/syntax checks: pass.
Preserved negative tiling/tuning results and explicit pending next-boot evidence.


## 2026-11-20 — Owner reboot: input and named RGB persistence qualified

Revalidated SM-G965N/BOOT/protected backups after owner reboot. Input/LED/
haptic/sensor/Bluetooth auto-started; input ownership receipt matched new boot.
Idle governors/minima/maxima retained. Named RGB/core maps coexist and boot
duplicates0; guarded three-color low-current on/off readback passed/all off.

A bounded Mutter virtual-keyboard Shift trial did not raise kernel QoS and is
not qualified input-handler evidence; closed the temporary session. Added a
GPL-2.0-only neutral-keyboard-check.c QA client, compiled natively with Werror.
After exact input-module SHA/vermagic checks and model/backup preflight, used
a root-private temporary module copy with independent45s unload fallback. Only
Shift press/release emitted, no text/pointer movement. Actual kernel input
raised minima1499.333/2327MHz then returned349.916/1066MHz; maxima unchanged.
Removed temporary device/module and cancelled fallback. No governor, thermal/
MAX policy, desktop configuration or runtime driver source changes.

Haptic100ms/8192 observed boost/bias/motor1 then0 at auto-stop/close; independent
rail-cut timer cancelled after success. Wi-Fi-bound HTTPS204; finite standard
IIO accel/gyro/pressure/proximity raw and ALS/temperature processed reads pass.
No physical sensor accuracy, full profile or compass buffered-heading replay.

Final private full ring1,024lines/error57/warn68 includes boot header, journal
423lines lacks early header. CPU variations52+unsupported1, hub reset1, modem
QoS4 persist; call trace/SError/GPU PLL/GPIO/action-frame/chanspec0. Standby
held MCU_RESP1 with CS0/GPS_PWR0 and response stayed1 after wake. Source already
registers shutdown; no missing-shutdown cause established. Did not execute
unused failsafe reset-register writes without a qualified hardware contract.

Provider review: GPU is sole devfreq device. Generic PM_DEVFREQ/INTERCONNECT
enabled; Exynos bus/Samsung ICC providers not configured, DT ICC endpoints0/
ECT node absent. CP index tables/cluster mapping need verified data before
modem votes; legacy CL0/CL1 comments alone are insufficient. No guessed rate/
voltage, generic-framework-only fix or warning suppression adopted.

Keyring PAM library missing error did not recur after login. Real keyring/GCR
services active; two short-lived autostart helper scope races are not missing
daemons. Automatic-login unlock/GDM/SAP messages persist. Portal remains WIP
excluded; no account/security/portal settings changed. Location permission true,
GeoClue and authorized GNSS socket session active. Separate failed GNSS instance
rejected non-GeoClue peer before hardware startup; kept evidence and ACL. Final
failed system count1 refers only to that rejected connection, not a receiver
crash. xgps is available in Ubuntu gpsd-clients, candidate3.25-3ubuntu3.2, not
installed. It needs a reviewed adapter for the private GNSS path; no package
install or private NMEA connection was inferred from the user's app question.


## 2026-11-20 — Install and connect xgps

After model/BOOT/protected-backup preflight, installed Ubuntu gpsd-clients/gpsd
3.25-3ubuntu3.2, preserving prior GNSS helper privately. Added optional nonblocking
root-private NMEA diagnostic fanout, credential-checked PTY bridge and loopback-only
GPSD2948; no receiver commands return to HAL, raw positions/logs not saved. Added
ordinary-user xgps launcher holding an authorized GeoClue client and application
menu entry GPS 위성 상태 (xgps). Bridge enabled for startup; next reboot untested.
Restarted only GeoClue to adopt helper/policy; sensors remained running. Initial
25s GPSD query had only handshake responses during receiver startup. Subsequent
live query received221 NMEA and160 TPV records. This proves actual data delivery,
not a satellite fix or outdoor accuracy. Optional packet-count logging contains
no location. Closed/reopened only the task-owned viewer following bridge restart.
Other-context app edits preserved separately; no firmware, credentials or private
backups published. Installation/rollback documented in GNSS README.

Final xgps check: connected-port2948 window confirmed through accessibility,
ordinary-user launcher active,145 live TPV messages received with mode1 (no
position fix). Stock launcher was shadowed only by a per-user xgps.desktop
pointing to the connected wrapper; package launcher preserved. The bridge
restart disconnected an earlier viewer; launched a new connected window and
verified delivery after receiver startup. No satellite-fix claim.


## 2026-11-20 — SIPC cell information and standard location integration

Owner requested layer-first review. Initial exact-model/BOOT/protected-backup
checks passed. Existing plugin had no GetCellInfo/location implementation or AT
port. Existing RIL diagnostics deliberately removed cell identities. Observed
19-byte SIPC0805 bodies; own-stock core LAC/CI offsets match GPL reference net.h.
Added privacy-preserving cell presence status plus explicit own-stock0811 GET
and strict four/five-count envelope validation through the existing owner.
First normal reboot loaded diagnostics without bypassing the once-per-boot
LTE guard: CP returned20 LTE records while EPS was searching/2, demonstrating
a real cell-list response without successful registration.

Implemented bounded LTE identity decoder and root-only typed cell-info endpoint
with15s freshness, no identity logging. Implemented plugin GetCellInfo and
standard3gpp location gathering with10s active-only polling, CP serving flag,
stale/disable clearing and object-lifecycle cleanup. Unqualified signal units
and other radio-family identities remain absent. Original licences retained;
no vendor binaries/disassembly/private identifiers published.

Full isolated174-target ARM64 MM build passed. Corrected declaration placement
warning; final plugin compile/link clean. One incremental attempt lacked the
original cross-file mount; restored that mount and rebuilt successfully. With
fresh model/BOOT/backups and original source/plugin/config/service rollback
copies, installed SHA-checked plugin/RIL, updated all private pins and unit
config hash, daemon-reloaded and performed a second normal reboot. No kernel,
BOOT image, firmware, bootloader or protected partition was changed.

Hardware: after startup completion, GetCellInfo returned20 LTE entries/1 serving;
two rounds exactly matched private SIPC operator/TAC/CI/PCI/serving values.
Location source1 became nonempty; disable cleared it and re-enable restored it.
System failed units0 at check. EPS registered1/5 comparison remains untested.
Reported19 nonserving records are not an independent fresh-RF scan guarantee.
BeaconDB host api.beacondb.net/submit-data=false preserved; IP estimate and
cell-derived/GNSS positions are separate evidence.

GPS: first GPSD-only observer had no active receiver and only handshake records,
so it is not an RF test. Fixed observation helper to hold its own authorized
GeoClue request. Window181s:1699 NMEA/1233 TPV, mode1/no fix. Detailed180s:
1687 NMEA/1225 TPV, no GSV and HAL satellite/fix0. Final45s after plugin reboot:
207 NMEA/148 TPV, mode1. Numeric standalone/HAL-start/UTC/XTRA-init results all0
confirmed after extending the strict nonlocation status whitelist; XTRA bytes
124383 accepted. Source filtering/transport is alive; no RF fault inferred.
Owner explicitly clarified this is a location where satellites cannot be
received. Record these as reception-environment-limited, not evidence requiring
a GPS driver repair. Favorable-location GPS fix remains pending; historical
real fix evidence retained. No speculative receiver/kernel change.

Host verification:7 cell/CEREG,14 radio-power,21 PDP and7 GNSS supervisor tests
passed. Read LOCATION_REVIEW.md for reproducing/building, privacy, rollback and
remaining registration/open-sky/signal/family limits. Independent personal-app
edits in these shared documents were preserved outside this commit.


Location fallback check: GeoClue3g source configured enabled. During an
authorized desktop location request, MM source1 was enabled; after the request
it was disabled on demand. GeoClue returned accuracy25000m. This confirms
a network estimate, not successful cell-database resolution. CP cell exposure
and actual cell-derived coordinates remain distinct; no provider/settings
change made for this read-only check.


## 2026-11-21 — GNSS start-position assistance

Added independently authored seed.py, legacy inject_location FD5 support,
strict numeric-only status forwarding and a private real-GPS-fix cache service.
Root cache0700/files0600; no coordinates/cell IDs logged or published. User
location preference gates lookup/cache use. HTTPS BeaconDB queries use at most
32 observed LTE cells, bounded reads/timeouts and no redirects; no submissions.
Network estimates remain separate from genuine GPS fixes. Only fresh GPSD TPV
mode2/3 with valid timestamp/uncertainty enters the GNSS cache. Seeds expire
at300s, uncertainty grows350m/s and values above100km are rejected. No aiding
data deletion, kernel/BOOT/firmware/partition/bootloader change.

Exact SM-G965N/current #48/protected-backup checks passed at each deployment.
Compiled own source natively against private read-only Bionic DSOs, removing
temporary library copies afterward. Initial build harness placeholder collision
failed before device execution; corrected unique placeholders. pytest was
unavailable; unittest ran21 GNSS tests including ASan/UBSan of the actual C
seed parser and callback slot. Original HAL/pins/supervisor/helper privately
snapshotted; only owned source, rebuilt HAL and its exact pin/unit installed.
Existing provider and submit-data=false preserved. Cell-only lookup returned
HTTP404 in this observation; IP-fallback-allowed network lookup accuracy25000m.

Initial candidate returned0 for position/start/UTC/XTRA but produced no NMEA
and repeated worker exits. Early no-seed control was confounded by five stale
known trial artifacts; stopped GNSS owners, checked no vendor/HAL process and
exclusive lease, preserved artifacts privately before retry. Restored old HAL/
supervisor/pins and ordinary rebooted. After guarded known-state preservation,
old-source241s baseline delivered2348 NMEA/1706 TPV, mode1/no fix. Clean initial
candidate retry again exited245; private GDB confirmed SIGSEGV in vendor IPC
location-request dispatch. No private trace/disassembly/binary published.

Cause: own-device Samsung HAL reads a two-boolean location-request callback
after the96-byte legacy callback prefix, absent from the previous client.
Added explicit104-byte callback layout, compile-time offset assertion and
persistent callback table. Handler only counts requests, with no reentrant
GeoClue/network call or GNSS-to-independent-location feedback. Added safe
numeric request counters and worker exit status for diagnosis. This corrects
the ABI gap rather than suppressing the signal or changing receiver/kernel.

Corrected candidate180s hardware test:1688 NMEA/1225 TPV, one real location
assistance callback, no exception in that GNSS instance, mode1/no fix. HAL
start/standalone/UTC/position/XTRA-init/inject all0; XTRA124383bytes. Private cache
service auto-started after the earlier reboot;671s-old network seed rejected,
fresh25km estimate prepared in1.14s. No mode1/IP record became a GNSS cache.
Successful receiver session stopped cleanly with no known trial artifacts;
new ordinary reboot performed for corrected-HAL persistence qualification.

수정 HAL 일반 재부팅 후 모델/#48/BOOT/보호 백업/실행파일 핀 재확인.
센서·GNSS 소켓·GPSD bridge·캐시 서비스 자동 active. 재시험91초에서
NMEA687/TPV498, 위치 요청 콜백1회, 해당 부팅 GNSS 예외0 확인.
시작/standalone/UTC/위치/XTRA init/inject0. unit 검증 통과, 배포된
serve.py/seed.py 소스 해시·0600 일치. 위성0/mode1이며 새 fix 증거는 아님.
Real new fix cache capture/reuse, offline/expired-cache field tests, open-sky
TTFF A/B, motion/suspend accuracy and SUPL remain pending. Current location is
owner-confirmed unable to receive satellites, not a new RF failure conclusion.


## 2026-11-21 — Same-place Android satellite fix comparison

Owner reported another Android GPS app obtained a satellite fix at the same
location. Subsequent supplied screenshot directly shows4 signals/2 in use,
strength21–27 and No Fix: it proves reception, not a completed fix in that
frame. Earlier environment-only interpretation is withdrawn; do not replace
it with an unproved driver/hardware diagnosis. USB remains configured because
the owner currently cannot disconnect it. All commands/measurements use Wi-Fi.

Fresh exact model/#48/BOOT/protected-backup/HAL-pin checks passed.300s same-
place observation2996 NMEA/2177 TPV,0sat/no GSV/mode1. Added existing filtered
logger through a temporary runtime unit drop-in, with private rollback receipt.
180s1677/1217 likewise no fix. Logger saw optional trace-directory failure and
RIL connection refusal; neither is proved to cause RF failure. No clock,
GPIO/regulator, kernel/BOOT/firmware/protected-partition change.

Found async location callback was counted but not answered after startup aid.
Added main-loop network-only seed reply, FD5 rewind and strict independence
flag; prior-GNSS cache is never replayed as an independent network reply.
Preserve original sample accuracy/time in host handoff and inflate uncertainty
350m/s at each C injection, including late replies; reject over100km/300s.
Fresh source built natively, exact pins updated under private HAL/pins/helpers
snapshots. Actual initial+requested position injections returned0, replay1;
301s3018 NMEA/2193 TPV still0sat/mode1. This qualifies request handling, not RF.

Tested a UTC/XTRA callback-response candidate: request counters0/0,181s1699/
1233 no fix; those paths not exercised. Tested one-shot UTC/XTRA after first
NMEA: both API0, one XTRA init/two injections,181s1698/1232 and receiver state
unchanged. Extra candidates removed; rebuilt/retained the actually exercised
network-request baseline SHA d1c926ca325e678e782e64ee121febe3f2752adc88d6f8602902432eee70373a.

Added checksum-checked aggregate-only receiver-status.py, installed ordinary-
user readable with private installation receipt.60s actual observation32 STA/
32 UNC records; common version9 prefix matched, tPeF, TimeSource0, ephemeris0,
field5=4294.967, full-power F. Mapping time/ephemeris availability from published
same-chipset-supplier version10 is explicitly an inference, not qualified
Samsung semantics/root cause. No NMEA/coordinates/UTC timestamps/cell or
satellite IDs emitted.26 current GNSS host tests pass, including actual C seed
parser/callback policy ASan/UBSan, privacy/layout/invalid receiver records.

Readonly private interface inspection found an80-byte standard legacy table;
no extra-slot ABI theory or immediate-return-zero explanation was adopted.
Private vendor traces/disassembly never published. Kernel KPROBES/FTRACE/
BPF_EVENTS unavailable; a possible static mixed-frame routing issue was not
proved with real packets and no driver change installed. File-metadata ptrace
was inconclusive; next direct attach had no daemon because interrupted startup
left known trial state. Handshake-only runs are not RF observations. All
ptracers detached; with source units stopped/no vendor/HAL process/exclusive
GNSS lease, five known artifacts privately preserved. Final clean60s356 NMEA/
257 TPV, mode1/no fix, source hashes match deployed helpers. Temporary logger
drop-in removed and logger/ptracer count0. Last normal startup works; GPS fix
remains unresolved. Current RF/aid-consumption cause, disconnected USB control,
favorable-reception TTFF and newer-code reboot regression remain pending.


## 2026-11-21 — Non-GPS system follow-up (in progress)

Owner deferred GPS; camera/fingerprint, document-portal WIP and personal app
configuration remain outside this work. Exact model/#48/BOOT/protected-backup
guards passed before LED writes. No kernel/BOOT/charger-current/voltage changes.

Three real NetworkManager scans advanced LastScan and returned15/23/25 APs;
station stayed connected and Wi-Fi-bound HTTPS204 passed each time, with no
new escan timeout. Earlier timeout remains unexplained, not marked fixed.
BlueZ is powered and advertises A2DP/AVRCP/HFP; PipeWire/WirePlumber and actual
neard service are active. No paired headset/HID peer is available, so these
checks do not establish current profile-level hardware operation.

Found no charging LED policy. Guarded red/green native battery-trigger trial
preserved blue/white and original state privately. USB gadget advertises500mA
and actual charger input cap is500000uA; screen-on load can discharge the
battery despite external power. A single ordinary-user display connection
held screen off35s and measured positive net current/Charging after6.5s, then
restored its prior mode. This is load-dependent charging, not evidence to raise
USB current limits. A first repeated-runuser trial woke the display and is
not accepted as a screen-off endurance observation.

Kernel battery triggers alone failed: battery changed to Charging while red
stayed0 throughout a separate35s screen-off test. Installed backed-up guarded
UPower StateChanged bridge to resample the native triggers, initially disabled
for boot; real transition/lifecycle qualification is in progress. A test using
UPower Device.Refresh encountered UnknownMethod on an enumerated device;
finally restored display mode. This is a diagnostic API failure, not a battery
or LED hardware pass. No original failures/logs were cleared.

Thermal inspection: CPU/GPU existing TMU policy polls and caps frequencies;
cached values were55/47/47C. These cached CPU/GPU channels are not exported to
standard hwmon, unlike existing battery/IIO temperatures. No protection policy,
thermal threshold, voltage, polling cadence or kernel config was changed.

Actual StateChanged trial: kernel Charging at6.5s, UPower State1/red1 by26.6s;
later actual Discharging/State2/red0 passed. Screen remained off through30.7s
but was on at32.7s; cause is unconfirmed, so this is not screen-off endurance
evidence. Natural UPower state lag remains; no timer or fake battery state.

Lifecycle test found a startup/termination race: Type=simple reported active
before the process installed its signal handler, and early stop left owned
runtime state. Manual red selection itself was preserved. Captured known state
was released through the guarded stop action, not deleted blindly. Moved signal
setup ahead of preflight, included start in finally cleanup and changed unit to
Type=notify/READY after both trigger and UPower subscriptions are installed.
Callback errors now terminate with cleanup instead of being swallowed by GLib.

Lifecycle retest passed: ready start, graceful stop restoring off/none and no
owned state; manual red1/none preserved across stop, then restored by the test
owner; restart passed. Enabled service only after those checks. Same qualified
#48/BOOT normal warm reboot changed boot ID and again passed exact model/BOOT/
protected-backup checks. Policy auto-started with current-boot state; RGB,
haptic, sensors, audio, Bluetooth and neard all active. Deployed source/unit
match repository bytes, helper0600; unit verification and desktop PipeWire/
WirePlumber/screen-button active checks passed. No kernel or BOOT replacement.

Warm-boot actual repeat:48s display-off observation stayed mode3 throughout;
kernel Charging12.6s, UPower State1/red1 by22.7s. Original display mode restored;
subsequent actual Discharging/red0 and LED enable0 confirmed. Blue/white remain
off, all current codes<=1. Full-charge/green transition and physical USB unplug
remain unverified. UPower sampling lag is not claimed eliminated.

Full fresh early ring956lines/header present: CPU variation52+1, hub reset1,
modem QoS4 remain; escan timeout/call trace/SError/GPU PLL failure/GPIO warning/
RGB duplicate patterns0. Failed units0 in this new boot; prior GPS failures were
not cleared. ALS131lux readable,7 IIO devices, Wi-Fi-bound HTTPS204. Current
modem aggregate21 cells/serving1 but State7/registration2(searching), not LTE
data success. First diagnostic used GetCellInfo on the wrong3GPP interface and
received UnknownMethod; introspection located the real method and read passed.
Two collector wrapper delimiter mistakes caused command/name errors after
read-only output, not device faults; corrected wrapper used for final checks.
No GPS test, permission change, log clearing or private-data publication.

Additional fixed-race regression: start --no-block then stop after100ms, before
readiness, left no owned state and original red/green off/none. Subsequent
ready start active/running, NRestarts0 and ExecMainStatus0. Source/unit pin
comparison and post-boot Discharging/LED enable0 passed; policy remains enabled.


## 2026-11-21 — Vehicle USB cold-power-on is not qualified

Owner confirmed that USB connection after full shutdown does not boot Ubuntu.
This is a hardware-use failure report, distinct from prior warm-reboot/service
passes. Requested charging-attach screen state; that evidence is pending.
Read-only actual model/#48/BOOT/protected-backup guard passed, running Ubuntu
reachable and charger online1; pstore had0 files. Current uptime/previous
shutdown markers do not reproduce the off-mode failure. No shutdown, register
write, boot/firmware replacement or agent service installation.

Inspected actual shim entry/main/board/kernel handoff and native init/DT:
no charger-only shim decision, incoming bootloader FDT replaced by embedded DT;
existing INFORM2/3 recovery/reset support is not USB cold-start support.
Samsung GPL sec_reboot reference distinguishes power-off/reset and low-power
charging, but the current early path/root cause remains unmeasured. Recorded
bounded observation/test and recovery conditions in VEHICLE_POWER.md. Do not
apply Android lpm edits or speculative INFORM/charger writes, or update/relock
Samsung bootloaders. Source review is not an implemented/verified autoboot fix.


## 2026-11-23 — Low battery / disabled charging recovery

Owner reported unexpected shutdown and repeated Samsung logo/vibration with
USB connected. Read-only observation: charger online1 but charge_behaviour
auto[inhibit-charge], battery0%,3.08–3.20V and net discharge, temperature22C.
Input cap500mA, charge current450mA/CV4.2V. Earlier LOW Battery journal entries
exist. Latest prior boot lacks complete retained kernel/end-of-system evidence;
current panic/OOM/lockup/thermal patterns0 do not exclude a previous fault.
Archived SError panic file mtime2026-11-19, not attributed to this incident.
Low battery/disabled charging is the leading explanation, not proven exclusive
reset cause. Charge-behaviour getter reflects hardware CHG_EN; it does not
prove a person or userspace policy deliberately disabled charging.

Owner then requested charging restoration. Wi-Fi unavailable, USB SSH worked.
Exact model/#48/BOOT/protected-backup guard PASS, charger online/healthGood and
22C checked; pre-change values preserved root-private. Wrote only auto through
standard charge_behaviour sysfs. Readback[auto], input/current/CV caps unchanged.
After5–20s charger and battery Charging, net current+60..98mA, average+57mA
at20s, voltage3.225V,22C. Actual charging restored;0% recovery takes longer.
Post-reboot persistence, full-charge behavior and reason CHG_EN became0 are
unresolved. No new service, periodic auto-enable, kernel/BOOT/firmware change or
current/voltage increase. Earlier read-only restriction superseded only for
owner-requested normal charging restoration. Private receipt remains on device.


## 2026-11-23 — Android charging parity review and intent candidate

Compared pinned LineageOS/android_kernel_samsung_exynos9810 commit6a9461f9
(charger/sec-battery/sec-adc/common header/public EUR rev26 DT). Wrong repository
fetches returned404; corrected repository and pinned hashes recorded in
experiments/charging/REFERENCE.json. No extracted firmware redistribution.
Android keeps charge_mode/is_charging separate from CHG hardware and selects
charge modes through cable, ADC temperature/hysteresis/swelling, full/recharge,
voltage faults and safety-time policy. Native charge IRQ currently only notifies
power_supply; equivalent upper policy and real ADC channels are absent.

Source candidate wraps unchanged charger data with mutex-protected accepted
request intent and readiness. Manual charge behaviour touches the same CHG bit;
failed I/O preserves prior intent, early requests returnEAGAIN. Added read-only
charge_requested and charge_enabled on the charger I2C device. Existing standard
charge_behaviour/status semantics and current/CV/input limits unchanged. No
periodic force-enable, protection bypass, thermal setpoint or automatic recovery
was implemented. This is the first diagnostic/ownership layer, not policy parity.

Actual-C property/error/neighbor-bit/startup/intent tests8pass; exact prior
reviewed source migration pass. ARM64 v7.1 driver-object compile pass. First
compile failed unavailable plural devm_device_add_groups; corrected singular
API. External-module linkage failed missing qualified Module.symvers/unresolved
exports; no bypass. Object compile is not module linkage/kernel build/device boot.

Device read-only follow-up: still0%,22C,3.314V/average+63mA/Charging/auto.
No new device writes/reboot/BOOT/module trial. Actual sensor service failed
this boot with Sensor child exited before readiness, root IIO provider count0.
Did not restart/reset sensors or infer SSP board thermistors equal battery ADC.
Battery depletion and missing/failed temperature paths preclude deploying an
Android-equivalent automatic enable policy now. The existing one-time charge
restoration remains active. Further ADC/provider/policy work and actual thermal/
full/recharge/reconnect/boot qualification remain explicitly incomplete.


## 2026-11-23 — ADC v3 실측 및 충전 IC 입력 재연결 복구

- exact SM-G965N/native #48/BOOT/RECOVERY·EFS·CPEFS·RADIO 백업 guard 확인 후
  opt-in ADC v3 두 모듈과 read-only charger snapshot 모듈을 root 전용 경로에
  배치. 자격 증명/firmware/실측 원본/개인 식별 정보는 private receipt로 보존.
- 첫 external module modpost는 잘못된 out의 Module.symvers 부재로 실패.
  qualified #47 export ABI(45d68e…)/RTC-only #48 incremental을 대조해 올바른
  out으로 3모듈 compile/modpost/link 성공. API of_node_to_fwnode는 지원되는
  of_fwnode_handle로 수정. 빌드 전용 재현 스크립트 추가(설치/flash 없음).
- ADC v3 DATA0x08/reset4→2/CTIME6/12bit/IRQ completion·100ms timeout 구현.
  firmware-held gate readiness만 확인하고 CMU/PLL/gate/rate는 쓰지 않음.
  SPI8 기존 owner 거부, 변환 전 제어값 보존, stale/중복 IRQ 방어 및 finally
  unload. 첫 trial은 charger health fault로 거부. 충전 판단과 독립적인
  진단 읽기만 허용하도록 수정했으며 충전 보호/전류/전압은 변경하지 않음.
- 실기 5회×4채널 완료: ADC4 1474–1475, ADC1 1558, ADC3 1385–1391,
  ADC11 2357–2673. 모듈 제거·clock 관찰값/ADC controls/IRQ type 원복 확인.
  상시 서비스/재부팅/절전 qualification은 아님.
- original BOOT manifest와 일치하는 private 원본을 읽기 전용 분석.
  rev26 3종의 wired battery/USB/charger 보정표·관련 보호/완충/재충전 항목은
  pinned 공개 소스와 일치. 총74필드 중 2종74/74,1종73/74이며 차이는
  wireless LCD-on 항목. private DT/원본 firmware는 공개하지 않음.
- temperature.py의 5개 trimmed mean 및 C signed division 변환/invalid·
  오래된 capture 거부 추가. 저장된 실측 battery37.7C/USB35.5C/charger39.9C.
  FG22C와 달라 FG 온도만으로 정책 판정 불가. ADC11 전압 변환 미검증.
- live charger owner regmap의 non-clearing 값만 읽고 snapshot 제거.
  충전 중단 시 CHG_DTLS6/BAT_DTLS2/CHGIN3/CHG_EN1/CHGPROT0/WDTEN0.
  8%/3.64V/near-zero discharge였으며 Dead 표시는 영구 배터리 고장 증거가 아님.
- 사용자 10초 USB 분리/재연결 뒤 Charging/Good, net+80–122mA, 평균+34mA,
  약3.67V. read-only snapshot CHG_DTLS1/BAT4/CHGIN3/CHG_EN1/CHGPROT0.
  모듈 제거 확인. 입력 재연결로 이 발생 건은 해제됐지만 최초 원인/소프트웨어
  복구 절차는 미확정. lock0은 정상 충전에도 존재하므로 reset 증거로 쓰지 않음.
- 호스트 실제 ADC C IRQ/오류/ownership/cleanup ASan·UBSan 및 보정 전체구간
  C 대조 5PASS, 기존 charger8PASS. 커널/BOOT/charger limits/firmware 미변경.
  Android 동일화·지속 충전·완충/재충전·상시 온도 정책·재부팅 검증은 미완료.

추가 30초×4표본 확인: Charging/Good 유지, 약3.66→3.72V,
마지막 평균+236mA. 순간 부하로 음전류 표본도 있어 상태명만으로 판단하지
않았으며 평균 양전류를 확인했습니다. 장기/완충 qualification은 아닙니다.


## 2026-11-23 — 충전 최초원인 추적·연속기록 활성화

- 사용자 요청: Android/native 코드 비교, 충전 제어·IC·온도 연속 기록,
  최초원인 조사 및 Android 충전 관리 후속. 기존 exact model/#48/BOOT/보호
  백업 guard 후 작업. BOOT/충전 limits/firmware/RECOVERY 등은 변경하지 않음.
- 원인 후보를 experiments/charging/CAUSES.md에 근거/판별 조건과 구분 기록.
  실제 CNFG01=0x91에서 fasttimer1/restart1/prequalification1을 확인해 native
  init 의도0/3/0과 불일치. 초기 write 미반영 vs 이후 reset/다른 writer 미구분.
  lock0만으로 reset 판정하지 않고 타이머를 강제로 끄지 않음.
- snapshot 모듈은 load-time 값 대신 매 읽기 live owner regmap을 사용하도록
  수정. root-read-only12개 non-clearing registers; IRQ 상태/설정 쓰기 없음.
  qualified ABI build/modpost/link 및 실기 반복 읽기 확인.
- charge-observer.service 설치/enable. 15초마다 control readback·IC config/
  state·ADC5회 trimmed 온도3종·available kernel messages 기록. root-only
  fsync JSONL4×4MiB 순환. before/after clock/ADC/IRQ 및 owned module unload
  확인. 기존 snapshot/스크립트/설정과 설치 receipt는 root private 보존.
- 표준 auditd 설치는 기기 네트워크에서150초 timeout. dpkg 변경 전 실패로
  확인한 뒤 Mac에서 공식 ARM64 auditd/libauparse2개를 APT metadata SHA256
  검증 후 전송·설치. audit enabled1/daemon active, 로그4MiB·num_logs3로
  제한하고 이전 auditd.conf 보관. dpkg --audit clean. 별도 daemon/전역
  audit 정책을 helper가 임의 변경하지 않으며 owned3개 control watch만 추가.
- 처음 기본 ausearch의 no matches로 attribution 검증 실패. regular-file
  probe도 같은 현상; explicit -if /var/log/audit/audit.log로 실제 syscall/
  process/path를 확인해 query 수정. 임시 regular watch는 제거. 실제 제어
  파일은 open(O_WRONLY) 후 close만 했고 아무 값도 쓰지 않았으며 readback
  불변 확인. 감사 이벤트는 open/write intent이지 accepted buffer 전체가 아님.
- 서비스 반복 stop/start 및 원복 검증 과정에서 start-limit-hit 발생
  (ExecMainStatus0, NRestarts0). exact guard 및 정상 stop receipt 확인 후
  해당 unit의 실행 카운터만 reset-failed하고 재시작. 보호 검사는 유지.
  enable은 설정 완료이나 actual reboot/suspend qualification은 아직 없음.
- thermal-policy.py: pinned wired normal hot50/recover45·cold0/recover5·
  USB80/recover75·swelling41/recover39 hysteresis를 shadow 계산으로 기록.
  invalid sample로 latch 해제 안 함. 실제 enable/disable/한계값 변경 없음.
  full/recharge/swelling/current/runtime safety-time 정책 완성은 미완료.
- native 소스 후보: CHG write 뒤 actual readback·silent mismatch 오류 반환,
  request/result/caller·cleanup disable·init 전후/error config 로깅 추가.
  무시되던 float voltage 초기설정 오류 전달. readback 실패는 accepted intent
  갱신 안 함. 이전 소스 exact SHA migration만 허용. 아직 기기 미설치.
- native ARM64 candidate object PASS, live snapshot link PASS, 실제 C fault
  injection 포함 충전 관련23tests PASS. 38개 observer 표본 온도 오류0,
  배터리15%로 상승·Charging/Good, 약38.3/36.1/40.6C. 단기 관찰 결과이며
  최초원인 확정/전체 Android parity/장기·완충·재충전 성공으로 표기 안 함.

추가 소스/순정 비교: owner rev26 3종 wired float4350mV vs native DT charge
ceiling4400mV·initializer design-voltage 사용. 미설치 후보에서 charge
ceiling4350mV로 수정하고 design rating4.4V와 분리; fallback4.2V/상한
design 제한/지원범위 검증 및 오류 전달. 실제 C 경계/누락/부적합 값 시험과
ARM64 object compile PASS. live CV4.2V는 그대로; 과전압 최초원인 판정 아님.
최종 observer active/Resultsuccess/NRestarts0·fresh 온도38.4/36.3/40.8C,
오류없음·audit lost0·dpkg clean 재확인. actual reboot/후보 커널 적용은 안 함.


## 2026-11-23 — #49 실기 적용·보호 경로 및 #50 후속 준비

연속 기록836표본에서 charge1→6/BAT2 전환을 포착. 마지막 USB 재연결
receipt에서10753초(약2h59m), 기록 시작 후3926초. CHG1/input3 유지,
배터리38.7C, config0x91 유지, 감사 기록에 control write64 없음(기존
no-write open56 및 auditctl206만). 타이머 경로의 강한 근거지만 MAX77705
정확한 code6 의미/왜 init 의도와 config가 달랐는지는 미확정. 최초CHG0
발생과 구분. 원본 로그는 root private archive로 보존.

처음 전압 guard가 거부해 재부팅/BOOT write는 없었고 recovery 대기는
timeout. fresh ADC/전원/기존 auto·정확 fault tuple·고정500/450/4.2V 확인
후 한 번만 CHG off→on300ms 시험. once-per-boot marker로 반복 금지.
실제 ChargingGood·순충전+6~130mA·평균+54mA 복구, limits 불변.
restart-once.py로 실제 사용 경로를 공개; 자동 fault reset 루프는 아님.

qualified #48 private output을 복사해 driver/timestamp만 재컴파일 및
정상 kallsyms 검증 relink. 첫 AS -EL GCC 오류는 -mlittle-endian으로 수정;
기록된 command의 trailing true 오류 은폐를 제거하고 Image version 확인.
초기 DT root-key 탐색 오류는 정확 inner DTB 확인·strict compatible/tree
비교로 교정. 실패 후보는 flash 안 함. 공개 builder로 설치 #49와 같은
timestamp 재현 Image SHA256 일치(d0de141e…63858bf5). build는 flash 안 함.

SM-G965N/#48/BOOT/보호 백업·fresh thermal·전원 guard 후 TWRP 재부팅,
새9개 파티션 backup byte/hash 검증. BOOT만 #49로 write/readback; 모든
보호/USERDATA 보존. 실제 Ubuntu#49 부팅. 새BOOT/model/backup/ABI 검증
서비스 receipt를 새root로 복사 이관하고 이전설정 보관; exact BOOT 검사
유지한 LED/haptic guard에49 허용. audio/BT/cover/sensors/observer active.

실제 before-init CNFG0=15/CNFG1=b8/CV=13/protection0c/input23, after-init
05/38/13/6c/a3. live CV4350mV·timer0/restart3/prequal0 적용 확인.
원인 후보의 init 미반영 vs 이후 변경은 이전#48 초기 로그가 없어 미구분.
bootloader가 CC900mA를 남기는 것도 확인; 첫 guardian 설치가 가정450과
달라 거부. 현재 input500/CC450 이하로만 낮추는 helper·startup 연결 후
실기 readback 확인(한도 증가 없음). SOC는 재부팅 시13→26 재추정했으므로
실제 저장 전하 증가로 해석하지 않고 전압/평균 전류를 함께 기록.

#49 inhibit-only guardian: fresh 온도/설정 drift/안전시간/완충 조건 차단,
실제 CHG0/explicit restore1 확인. observer 실제 stop42초로 stale 측정
차단(CHG0) 검증; recording 재시작 후 operator restore로 충전 복구.
Type=notify 첫 표본·guardian 첫결정 이후 READY, guardian Wants observer로
기록기 실패 때도 차단 수행. 일반 warm boot에서 순간3.5V 미만으로 observer
1차 시작 거부·60초 뒤복구, guardian stale 차단 후 수동복구 필요함을 포착.
전압 기준은 낮추지 않고2회 연속 안정값을 최대30초 기다리는 코드 추가.

#49 warm boot 후9개 관련서비스 active·심각 kernel 패턴0. 후기 ADC 약
40.4/36.4/43.5C. startup stale가 해소되어도 inhibit-only가 자동 재개하지
않는 한계를 고치려고 #50 user intent/policy block 분리·generation CAS
후보 추가. 실제 C read/write fault·stale generation·manual inhibit 보존
테스트 통과, ARM64#50 build/BOOT package 완료; 아직 이 시점 실기 미적용.
#50 후속은 다음 기록에서 실제 적용 여부를 구분합니다.


## 2026-11-23 — #50 charging policy installed and warm-boot verified

- #50 initial raw ADB staging stalled before any BOOT write. Bounded selected
  reconnect and host server restart did not recover; user USB reattachment did.
  Rechecked G965N/old#49 BOOT unchanged; uncompressed sync upload/hash succeeded.
  Production uploader now prefers sync, revalidates recovery/model on reconnect,
  never writes an incomplete stage. Fresh9-partition backup, BOOT-only write
  and readback completed; protected partitions/data preserved.
- Actual kernel#50 (2026-11-23 06:23:32 UTC) and guarded profile migration passed.
  Existing sensors/audio/BT/cover/LED/haptic/boost services returned. CV4350mV,
  input<=500mA/CC<=450mA; no unqualified negotiated-current increase.
- Hardware CAS checks passed: policy stop, manual inhibit, stale generation
  EAGAIN/no write, policy recovery preserving manual off, and manual auto unable
  to bypass an active protection block. Actual recorder loss42s stopped CHG;
  fresh data recovered with unchanged manual generation. Manual off remained
  through guardian restart. Warm boots restored enabled observer/guardian.
- CLOCK_BOOTTIME now includes suspended time in measurement age/safety counters.
  Owned external-power sleep inhibitor observed live. Final warm boot again
  restored both services; actual high-temperature swelling protection paused
  charging. Thermal pause is not a continuous-net-charging pass.
- Conservative hot/cold swelling stops and runtime/full/recharge logic added;
  adaptive stock CV/current policy and complete physical cycles remain pending.
  49 relevant host tests passed. Root-only bounded soak result distinguishes
  failed/inconclusive/passed; three-hour observation is not yet a completed pass.
- First original fault10753s after attach/config0x91/no watched write strengthens
  timer hypothesis; exact chip fault cause/old config origin/initial CHG0 remain
  unresolved. No automatic repeated fault resets. See charging/MANAGEMENT.md.

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


## 2026-11-23 — heat investigation, read-only snapshot

Calibrated battery45.0C/USB40.6C/charger51.9C; CHGoff/input valid, guardian
swelling stop and no hardware/config latch. Battery gauge reports35.5C,
so its thermal-zone reading underreports relative to calibrated battery ADC.
Reported battery average -748mA, SOC14%. CPU snapshot96% idle, yet cpufreq
reports cluster maxima2.327/1.499GHz; big min1.066GHz vs hardware min400MHz.
GPU reports572MHz; devfreq residency787668ms at572 vs28108ms at260 and880ms
at455. ScreenSaver GetActive=true; touch IRQ unchanged across3s (no storm
in that interval). Thus earlier app load alone does not explain sustained heat.
Investigate GPU idle/devfreq accounting, CPU QoS minimums and thermal/cooling
integration; clock/residency readback alone does not prove actual powered GPU
utilization. No charging/clock/protection settings changed by this diagnostic.


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


## 2026-11-23 — screen-off cooling retention and recovery qualification

- Continued thermal recovery: calibrated battery43.4→42.6→41.7C, mean battery
  current near0, GPU runtime suspended, SOC6%. Prior active-app log peak49.4C
  distinguishes the earlier rendering/failed-budget period from current cooling.
- Extended the existing QoS controller to retain conservative650/1066/260MHz
  ceilings and owned200ms governor cadence while the unique DSI panel reports
  disabled+DPMSoff, even after thermal hysteresis clears. Unknown/ambiguous
  panel state retains cooling; screen-on only releases if thermal state permits.
  Thermal latch is independent of display state. No app/process/voltage changes.
- Six host tests passed, including display ambiguity and screen-on restoration
  decisions. Actual#50/model/protected backups and old/new source hashes verified;
  previous root-private controller backed up, source replaced and service restart
  verified. Existing module binary/pins remain unchanged. Actual hot/off state
  and transition journal present; cold recovery is not yet claimed.
- Installed guarded read-only recovery-check.py and started bounded1200s
  g965n-thermal-recovery50.service. It must observe hot-stop→<=39C/CHGon→120s
  positive average current with safe temperature, panel-off limits and no faults.
  Private result pending; neither startup nor test exit0 means qualification.


### Thermal stabilization — real cold recovery and panel-cycle PASS

Completed-sample tail reading now tolerates concurrent partial records while
enforcing35s freshness. Same-boot thermal latch survives controller restart;
unknown/new boot remains conservative. Guarded source backup/hash deployment
and actual restart verified; existing module/pins unchanged. Eleven tests PASS.

First read-only recovery unit was interrupted to correct asynchronous cold→CHG
phase timing and stale-gap validation. Final recovery50-final observed hot-stop,
natural39.0C, automatic CHGon/reasons[], then122s sampled positive screen-off
charging at38.9C/current+171mA/SOC6%. No forced charge or changed limits.

Guarded panel-cycle-check verified actual displayon: level0, CPU1499.333/2327
and GPU572MHz maxima,20ms cadence. Displayoff: level1,650/1066/260MHz,200ms.
Independent30s original-off restore timer canceled after success. Subsequent
cold service restart retained thermal_hot=false and screen_off_idle. No apps
launched/paused, kernel flash, reboot, voltage/current/threshold or APT changes.
Sensors/audio/BT and charging/cooling services remained active; targeted new
BUG/Oops/panic/G3D timeout search empty. Service state is not full hardware QA.
ChatGPT remains closed; offscreen rendering, PLL/deep-idle and sustained load
thermal/energy behavior remain unresolved. This is short idle qualification.


Post-cycle idle check: battery38.7C, mean+171mA and Charging, GPU suspended,
observer/guardian/cooling active. Started a NEW bounded10800s read-only
g965n-charging-soak-cooled50.service from this cooled charging baseline.
Stopped the earlier pre-cool soak intentionally; its thermal pauses never
qualified uninterrupted charging. New three-hour result is PENDING; inspect
the result.json inside the directory named by
/var/lib/g965n-charge-observer/latest-soak-path (a private pointer file). This does not reset
guardian safety budgets, change charging controls or auto-restart ChatGPT.

## 2026-11-23 — 충전기 교체 후 비교

사용자가 충전기 교체를 완료했다. Wi-Fi로 BC type1(SDP)→3(DCP), sink/VBUS를 읽어 전원 종류 변화를 확인했다. 실제 계약 전류나 고속 충전 전압을 확정한 것은 아니다. 배터리2%·3.44V·39.1°C, 화면 ON에서 순방전 약273mA였다. 앱을 유지하고 표준 DPMS OFF를 적용해 readback했고,45초 관찰 후39.2°C·순전류 약−1~−6mA 구간을 확인했다. 입력500mA/충전450mA와 기존 온도 보호는 유지했다. guardian 사유는 swelling_temperature_stop이며 하드웨어/설정 고장 latch는 false였다. 39°C 이하 냉각 후 자동 충전 재개와 장시간 화면 ON 부하는 아직 확인되지 않았다.
