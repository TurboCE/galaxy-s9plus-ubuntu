# SM-G965N 현재 지원 현황

## 2026-11-24 — LTE 출처 검증 복구 및 센서 자동 재시작

LTE의 EFS 백업 확인을 중간 snapshot과 후속 정상 방향 변화로 재검증했습니다.
기존 검증 경로로 재부팅 후 모뎀·SIM·rmnet0이 다시 나타났습니다.
지원 패키지1.2.0에서 센서 서비스는 오류 후15초에 다시 시작하며15분에
세 번까지 시작할 수 있습니다. 실제 브로커 종료 시험에서26초 뒤 센서7개와
조도/가속도 값이 돌아왔습니다. ROM 무응답 상태의 자동 복구는 미검증입니다.

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


## 2026-11-24 — 센서 복구 및 지원 패키지 1.1.0

TWRP 경유 Ubuntu 부팅에서 SSP 센서가 복구됐고 일반 재부팅 두 번에서
IIO 센서 7개가 다시 등록됐습니다. 두 번째 재부팅은 지원 패키지의 센서
실행부를 사용했습니다. 조도91–92 lux, 기압 약102kPa, 가속도·자이로·
근접·온도 실제 값과 SensorProxy 조도계/가속도계를 확인했습니다.
최초 전기적 원인과 불량 상태에서의 자동 복구는 미검증입니다. LTE 출처
검증은 별도 미완료입니다. 나침반은 채널 등록만 성공으로 기록합니다.

## 2026-11-24 — 허브 오류 원인 조사

#50 정상 종료 후 전원 재연결, 하드웨어/GPIO SPI 진단에서 ROM 첫16바이트
수신 전부0/ACK0. 준비 GPIO는 high지만 허브 데이터가 돌아오지 않습니다.
실제 허브 IIO 센서 출력은 확인되지 않았고 정상 프로필로 복원했습니다.
전기적 최초 원인과 패키지 통합은 미완료입니다.

## SM-G965N 지원 패키지 및 APT 실기 결과 — 2026-11-24

`g965n-support` 1.0.0 설치. ALSA UCM, WirePlumber 설정, udev 규칙과
전원 키·충전·열 제어·진동·LED·입력 QoS 서비스의 실행 코드와 설정을 관리합니다.
기존 #50 BOOT/모듈과 모델·백업 검증을 사용하는 구성입니다.
실제 Ubuntu 패키지 20개 갱신 후 재부팅 및 동일 BOOT 확인. Wi-Fi/SSH,
Wayland/Panfrost, ALSA UCM·PipeWire 스피커/마이크 시험음, 백라이트와 전원
관련 서비스, NFC·Bluetooth 컨트롤러 등록을 확인했습니다. 충전 관측/보호는
자동 구동했고 41.8°C에서 온도 보호로 충전을 차단했습니다.
센서 허브 ROM 동기화와 LTE 출처 검증 실패는 갱신 전부터 있었고 재부팅 후에도
남았습니다. 모든 기본 기능이 검증된 결과가 아닙니다. [지원 패키지](SUPPORT_PACKAGE.md)

## 패키지 업데이트 검토 — 2026-11-24

현재 APT 모의 실행은20개 갱신·신규/제거0, 커널 이미지 교체 없음입니다.
systemd/udev/GStreamer 변경이 포함되어 실제 업그레이드 후 하드웨어/서비스
회귀 검증이 필요합니다. 패키지 설치나 설정 변경은 수행하지 않았습니다.

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

## 최신 연속 가동 확인 — 2026-11-24 14:07 KST

마지막 부팅은11/23 16:04 KST, 약22시간 연속 가동입니다.
지난밤3시간 관측과 현재 boot가 같으며 야간 재부팅은 확인되지 않았습니다.

## 最新結果 — 2026-11-24 #50 3시간 앱-open 충전 관측

2026-11-23 21:22 KST부터 3시간(10801.7초) 관측 PASS: 표본714개,
평균 보고 순전류 +444.3mA, faults/conditions 모두 없음. 시험 중 같은 boot와
요구 workload unit active 및 source1200mA lease 조건을 표본마다 확인했습니다.
화면 OFF·앱 유휴 관측이며 화면 ON/실제 음성 부하 검증을 대신하지 않습니다.
앱은 이후 설정한11400초 제한으로 종료됐고 monitor는 위험 사유 없이 종료를
관측했습니다. systemd의 해당 timeout 실패 표시는 예정된 시험 수명 종료입니다.
현재 배터리90%·35.7°C, CHG0·input500mA입니다. 누적 충전 wall36010.6초로
10시간 safety_time_expired 보호가 적용됐고 hardware/configuration fault는 없습니다.
타이머를 초기화하거나 충전을 강제하지 않았습니다. 이 상태의 장기 재충전 정책과
실제 음성/물리 전원 키/reboot 회귀는 미완료이며 상시 차량 운영 완료가 아닙니다.

## 최신 우선 상태 — 2026-11-23 #50 전원·발열 보호 시험

아래 이전 시점 요약보다 이 상태와 후속 검증 행을 우선합니다.
현재 충전기에서 선택된 고정 PDO 5V/3A를 읽고, 단일 MUIC 명령 소유자와
15초 커널 입력 lease를 통해900/1200mA 입력을 제한 시험했습니다.
이는 선택 source 한도이며 RDO 동작 전류를 별도로 디코드한 증거가 아닙니다.
CHG450mA/CV4.35V 및 기존41/39°C 충전 보호는 유지했습니다.
화면 OFF·앱 유지 및 화면 ON 유휴 단기 시험은 순충전이었으나, 이전500mA
음성 시험은 저전압·발열로 실패했습니다. 새1200mA 실제 음성은 사용자
시험 불가로 미검증이며 장시간 안전성/Android 동등 동작을 주장하지 않습니다.

CPU/GPU 냉각38/36°C·서비스 watchdog 장애 복구를 실제 확인했습니다.
하드웨어 충전 watchdog은 약80초 무갱신 시 fault11, 소프트웨어 CHG0 확인
후 안전한 해제, 오류 후 재갱신 거부까지 확인했고 guardian에 연결했습니다.
IC 단독의 실제 전류 차단 시각/잔류 전류는 독립 실측하지 못했습니다.
연결 후95초/48회 관측에서 정상 갱신·fault0을 확인했습니다. 앱을 연 새3시간
관측은 진행 중이며, 과열/저전압 시 해당 시험 앱만 종료합니다. 결과는 아직 대기입니다.
현 시험은 /run override와 current-boot 모듈이므로 재부팅 적용·회귀는 미완료입니다.
전원 키는 짧은 물리 시험 성공 뒤 긴 대기에서 깜빡임이 재발했습니다.
강제 ON을 제거한 새 native-wake 후보는90초 OFF 두 차례 자동 시험 통과,
최신 물리 장기 대기 재확인은 미완료입니다. 원래 자발 fault6 원인은 미확정입니다.
개인 앱 설정/계정·원본 로그·기기 식별자·바이너리는 공개 변경에 포함하지 않습니다.

## 최신 추가 검증 — 2026-11-23, native #50

실제 음성 인식·답변 재생은 사용자 확인. 하지만 열린 앱의 화면 ON/음성 부하에서는 발열과 순방전이 재현되어 장시간 실사용 안정성은 미완료다. 배터리2%·42.8°C에서 앱은 유지하고 화면만 OFF했다. 기존 온도 보호·입력500mA 한도를 유지하며 충전기 비교를 기다린다. 읽기 전용 USB-C 상태 모듈은 실기기 읽기까지 확인했으나 실제 PD 전류 계약/고속 충전은 미검증이다. 아래 오래된 #48 요약보다 이 추가 결과와 후속 이력을 우선한다.

갱신: 2026-11-21 KST. 실험 브랜치: `codex/g965n-lte-audio`.
최신 확인 기준은 native #48 + NFC/RTC 수정 + 충전 LED 정책 재부팅 검증입니다.
현재 GPS 작업은 사용자 요청으로 보류합니다.
한 대의 한국향 rev26 기기에서 확인한 범위이며, 전체 하드웨어 지원 완료가 아닙니다.
이 문서는 최신 요약입니다. 이전 빌드의 실패·성공 이력은
[검증표](VALIDATION.md), 변경 순서는 [CHANGELOG](CHANGELOG.md)에 보존합니다.

| 기능 | 현재 상태 | 남은 사항 |
|---|---|---|
| Ubuntu 부팅·저장장치·CPU·RAM | 부팅, USERDATA 확장, 8코어 사용·기기 내 컴파일 확인 | 장기 안정성, 완전 전원 차단 후 복구 시험 |
| 화면·터치 | 실제 사용 및 재부팅 확인 | 일부 앱의 최소 창 크기, 절전 복귀 |
| GPU·화면 전환 | 기존 NEON 가속·픽셀·클린 빌드 검증 유지. 입력 후500ms CPU QoS 보강으로 앱 목록 초기 처리 피크 중앙값23–26→18–21ms, 사용자 현재 수준 수용 | 일부 긴 초기 프레임은 남음. 입력 서비스 별도 재부팅 자동 시작·입력 후 성능 상승/대기 복귀 확인. 장기 전력·부하·코덱 |
| Wi-Fi | 인터넷, 재검색(15 AP), 수동 재접속 확인 | 장기 끊김 복구·공유기 간 로밍 |
| Wi-Fi Direct | 이전 빌드에서 Fold7 연결·양방향 해시 일치 전송 확인 | 최신 빌드에서 연결·전송 회귀 시험 |
| USB 네트워크·SSH | 연결·복구 확인 | USB 분리 상태 보고의 정확성, OTG |
| Wi-Fi 원격 제어 | USB와 별도로 Wi-Fi 주소에 SSH 및 Wi-Fi 지정 HTTPS 확인 | IP 변경 시 연결 정보를 로컬에서 갱신 |
| 스피커·마이크 | 실제 녹음·재생·ChatGPT 음성 응답을 사용자 확인 | 장시간 음질, 헤드셋·통화·다중 마이크·처리 기능 |
| Bluetooth | 사용자 사용 확인, 검색·재부팅 후 powered 상태 확인 | 오디오/HID 등 프로파일별 최신 회귀·절전 복귀 |
| NFC | 실제 대상 인식·4개 레코드 읽기, 3회 전원 반복 및 재부팅 후 재읽기 확인 | 다른 태그 종류·쓰기·에뮬레이션·결제·보안 요소 |
| LTE IPv4 | 특정 SIM으로 실제 DNS·TLS 인터넷 성공 | 현재 SIM은 이번 확인에서 망 검색 중(searching), 데이터 재검증 미완료, IPv6·망 복구·이동 시험 |
| 모바일 네트워크 설정 | Ubuntu WWAN 화면·바로가기, 4G 표시 확인 | APN 편집·수동 망 선택·SIM 잠금 변경은 조작 미검증 |
| 기지국 위치 | GetCellInfo LTE20개/serving1개, SIPC 원본 일치·기본3gpp 위치 값·끄기/켜기 확인 | 등록 성공 상태 비교·다른 RAT·신호 단위·외부 RF 비교 미검증 |
| 통화·문자·다른 무선 모드 | 미완료 | 별도 구현·실기기 검증. 이 백엔드는 LTE만 광고하며 5G 지원 주장을 하지 않음 |
| 조도·자동 밝기 | 실제 조명 ON/OFF, 부드러운 전환·기본 토글 확인 | 광학적 절대 밝기·장기 시험 |
| 가속도·화면 회전 | 실제 회전·터치 좌표·기본 회전 잠금 및 재부팅 확인 | 동적 정확도·절전 복귀 |
| 자이로·근접·기압·Qt 센서 | 실제 데이터, Qt 예제 연결 확인 | 축·절대 정확도, 근접에 따른 화면 정책·보정 |
| 나침반 | 표준/Qt/전용 앱에 실시간 값 연결, 실험 모드 | 기준 방향과 비교한 정확도는 미달. 보정·기울기 정확도 필요 |
| 온도·배터리 | hwmon·UPower 표시·충전 상태 확인 | 절대 온도·열 제어, 고속충전 협상, 배터리 소모 |
| GPS | 과거 실제3D fix·GeoClue 전달 확인. 같은 위치의 다른 Android 위성 신호 사진 확인; S9+는 위성0으로 수신 경로 재검증 중 | 원인 미확정. 사진 속 다른 폰도 No Fix. 실제 fix·냉간/절전 회귀 미검증 |
| RTC | IRQ 타입 경고 수정, 초기 부팅·별도 재부팅 후 시계 진행·실제 알람·시간 유지·Ubuntu NTP 동기화 상태 확인 | 완전 전원 차단 유지·절전 깨우기 |
| 홀/커버 | 자석에 따른 SW_LID·logind 이벤트 확인 | 실제 커버·화면 정책. 현재 덮개 동작은 ignore |
| 화면만 끄기 | 화면 꺼짐 중 센서·인터넷·백그라운드 유지 확인 | 물리 전원 키 전체 동작·Android 대비 소모량 |
| 서스펜드·깊은 절전 | 미완료, suspend 관련 target은 기존 정책으로 차단 | 깨우기 경로·모든 장치 복귀·전력 측정 |
| RGB 알림 LED | 세 색 실제 점등·저전류 코드0..1·regmap 분리 및 재부팅 확인. 충전 red ON/OFF 정책·종료 복구·수동 설정 보존·재부팅 자동 실행 확인 | 완충 green/물리 USB 분리, GNOME 알림, 밝기/색 보정, 하드웨어 패턴 |
| 진동 | 실제26MHz PWM 측정·GPIO 전원·표준 FF_RUMBLE 연결, 반복 출력/자동 정지와 IMU의 기계적 반응·재부팅 자동 구동 확인 | 표준 feedbackd 100ms 실제 호출·상시 열린 장치의 대기 전원 차단 수정 확인. 새 수정의 재부팅 자동 구동·대기 전원 off·재출력 확인. 세기/파형 보정·GNOME 전체 알림 정책·절전 복귀·장기 온도 미검증 |
| 심박·그립·파생 센서 | 소스 목록만 있음 | 실측·데이터 계약·표준 소비자 확인. 광고된 ID만으로 활성화하지 않음 |
| 한글 입력·폰트 | 실제 화면 키보드 조합 및 재부팅 확인 | 수정 패키지를 포함한 전체 새 이미지 재설치 검증 |
| 카메라·지문 | 미지원 | 사용자 요청으로 현재 작업 범위에서 제외 |
| 전체 이미지 재현 | 소스·패치·여러 빌드/검증 절차 보존 | 현재 기기의 모든 수동 설치를 포함한 새 이미지 한 번에 재설치 시험은 미완료 |

## 남은 커널 경고

RTC IRQ63 타입 경고와 관련 호출 추적은 RTC 수정 후 두 번의 부팅에서 0건입니다.
CPU 기능 차이/taint, 모뎀 bus QoS 미구현,
Bluetooth 광고 명령 일부 미지원, RGB/haptic DT 누락 경고가 남습니다.
RGB는 기존 플랫폼 자식에 software node를 붙여 실제 동작하며, 초기 MFD 경고만 숨기지는 않았습니다. 보조 GPT 부재는 원본 메타데이터 백업 후
빈 보조 영역만 복원했고, 별도 재부팅에서 경고0 및 주 정보 불변을 확인했습니다.
NFC의 unsupported 0xf3f는 클럭 수정 후 시험한 부팅에서 0건입니다.
최근 경고가 없다는 관찰을 깨끗한 부팅 또는 모든 기능 정상으로 해석하지 않습니다.

사용자 재부팅 후 전체 ring 재수집: 초기 부팅 헤더 있음, 1,024줄·오류 우선순위57줄·경고68줄,
CPU 레지스터 차이52건·공통 기능 경고1건, 허브 reset 미확인1건, vendor QoS4건.
journal에는 초기 부팅 헤더가 없어 CPU 경고가 누락되므로 journal의0건을
해결 증거로 쓰지 않습니다. Call trace/SError/GPU PLL 실패/관련 GPIO 경고0,
입력·LED·진동·센서 서비스 자동 구동 확인. 우선순위가 높은 모뎀 정상 상태 메시지도 포함되어 있어
57줄을57개 기능 고장으로 해석하지 않습니다.

로그인용 keyring PAM 모듈 누락은 Ubuntu 패키지 설치 후 실제 라이브러리
로드로 수정 확인했습니다. 재부팅 후 누락 모듈 오류 재발0. 기존 자동 로그인에서
암호가 없다는 keyring 경고, GDM 원격 디스플레이 assertion, Bluetooth SAP
초기화 실패는 남아 있습니다. 일반 Bluetooth 어댑터 powered는 확인했으며
SAP 또는 모든 Bluetooth 프로파일 정상 주장은 하지 않습니다. 자세한 분류는
[로그 검토](KERNEL_WARNINGS.md)를 보세요.

GPT의 실제 논리 섹터는 4096바이트이며 Samsung 헤더 길이는512바이트입니다.
주 GPT 헤더·엔트리를 그대로 두고 마지막의 빈 보조 영역20KiB만 복원했습니다.
주·보조 CRC와25개 파티션 엔트리 일치, 재부팅 후 경고 소멸 및 보호 파티션 불변을
확인했습니다. 파티션 이동·크기 변경은 없으며 전후 메타데이터는 비공개 백업에 보존합니다.

## 설치한 사용자 도구

- **시작 프로그램**: Ubuntu `gnome-startup-applications`의 로그인 앱 관리.
  하드웨어 systemd 서비스는 별도이며 여기서 임의로 꺼지지 않습니다.
- **지도**: Ubuntu GNOME Maps. 지도 표시/네트워크 위치와 실제 위성 fix를 구분합니다.
- **GPS 수신 시험**: 5분 실측, 위성·정상 문장·fix 통계를 표시하는 전용 GTK 앱.
  위도·경도/NMEA 원문을 저장하지 않습니다. Wi-Fi 원격 시작·중지 가능.
- **소프트웨어 센터**: gnome-software와 PackageKit/AppStream 설치 완료.
  실제 앱 설치 흐름은 추가 확인 필요.
- **Google Chrome**: 공식 ARM64 패키지 설치 완료. 현재 앱 화면·로그인 관련
  조사는 별도 작업으로 이관했으며 하드웨어 기능 검증과 구분합니다.

다음 작업과 안전한 재개 순서는 [HANDOFF](HANDOFF.md), GPS 설치·실행은
[GNSS README](../../experiments/gnss/README.md)를 읽으세요.


재부팅 후 입력 성능 요청의 자동 시작·500ms 후 복귀·최대 제한 유지,
LED 이름 충돌 수정의 자동 시작·세 색 출력 읽기, 진동100ms와 전원 off,
Wi-Fi 지정 HTTPS204 확인. GPS 기본 위치 서비스 켜짐, GeoClue와 정상
수신 세션 실행 중. 별도 GNSS 실패 기록1건은 GeoClue 전용 소켓의 비허용
계정 접속 거절이며 정상 세션은 유지됩니다. 전체 실패 unit0으로 표현하지
않습니다. 모뎀 QoS·허브 물리 리셋·CPU 기능 차이는 별도 미완료입니다.


xgps 설치·연결: 앱 목록의 GPS 위성 상태 (xgps)에서 실행. 기존 GeoClue
위치 서비스와 읽기 전용 공유하며 실제 NMEA/TPV 전달 확인. 실내 위치 확정과
위성 신호 수신은 별도이며 새 연결 서비스의 재부팅 자동 구동은 미검증입니다.

Final xgps check: connected-port2948 window confirmed through accessibility,
ordinary-user launcher active,145 live TPV messages received with mode1 (no
position fix). Stock launcher was shadowed only by a per-user xgps.desktop
pointing to the connected wrapper; package launcher preserved. The bridge
restart disconnected an earlier viewer; launched a new connected window and
verified delivery after receiver startup. No satellite-fix claim.


최신 위치 검증: SIPC→ModemManager GetCellInfo에서 LTE20개/serving1개 반환,
원본 필드 일치2회·기본3gpp 위치 소스 값·끄기/켜기 확인. 망 등록 성공
상태에서의 비교와 다른 무선 종류/신호 세기 단위는 미검증입니다.
GPS는 사용자가 위성 수신이 어려운 장소라고 확인한 조건에서 측정했습니다.
NMEA/HAL 시작/UTC·XTRA 전달은 확인, 수신 가능한 장소의 최종 fix는 추후
검증입니다. 이 결과를 GPS 드라이버 고장으로 해석하지 않습니다.


위치 fallback 후속: 위치 요청 중 MM 기지국 소스 자동 활성화 확인. 실제
GeoClue 응답 정확도는25km로, 기지국 DB 기반의 좌표 확정 성공은 미검증입니다.


## 2026-11-21 — GNSS start-position assistance

GNSS 보조 위치 주입과 비공개 최근 fix 캐시를 추가했습니다. 삼성 HAL의
추가 위치 요청 콜백 누락으로 발생한 충돌을 수정한 뒤180초 실기기 시험에서
NMEA1688/TPV1225·실제 요청 콜백1회·해당 세션 예외0을 확인했습니다.
시작/위치/UTC/XTRA 주입0,671초 캐시 거부·서비스 재부팅 자동 시작 확인.
수정 HAL 일반 재부팅 후 모델/#48/BOOT/보호 백업/실행파일 핀 재확인.
센서·GNSS 소켓·GPSD bridge·캐시 서비스 자동 active. 재시험91초에서
NMEA687/TPV498, 위치 요청 콜백1회, 해당 부팅 GNSS 예외0 확인.
시작/standalone/UTC/위치/XTRA init/inject0. unit 검증 통과, 배포된
serve.py/seed.py 소스 해시·0600 일치. 위성0/mode1이며 새 fix 증거는 아님.
현재 장소에서는 위성0/mode1이며, 실제 새 fix 캐시·최초 fix 시간 개선·SUPL은
미검증/미완료입니다. 셀 전용 조회는 이번 관찰에서404, IP fallback을 허용한
네트워크 추정은25km였습니다. 이것을 기지국 좌표 확정으로 쓰지 않습니다.


## 2026-11-21 — Same-place Android satellite fix comparison

같은 위치의 다른 Android는 사진에서 위성 신호4개/사용 표시2개,
신호21–27을 보입니다. 해당 사진은 No Fix이며 그 순간 위치 확정 증거는
아닙니다. 이전 실제 fix는 사용자 보고입니다. ‘이곳은 위성 수신 불가’라는
기존 환경 단독 판단을 철회합니다. S9+는300초 시험에서 위성0/mode1입니다.

수신기 요청 뒤 네트워크 보조 위치 응답을 실제 확인했고 수정본을 유지합니다.
수신 준비 후 UTC/XTRA 추가 주입은 효과 없어 원복했습니다. 별도 수신 상태
도구는 tPeF/TimeSource0/궤도 수0을 확인했지만 삼성 메시지 해석·원인은
미확정입니다. 최종 정리 후60초 NMEA356/TPV257로 데이터 전달 복구 확인.
GPS fix 문제는 아직 해결되지 않았습니다. USB 분리는 현재 사용자가
하기 어려워 비교하지 못했습니다. 커널/전원/클럭/펌웨어 변경은 없습니다.


## 2026-11-21 — GPS 제외 후속

최신 요청에 따라 GPS 작업은 보류했습니다. Wi-Fi 재검색3회·각 HTTPS204
통과, 새 escan timeout0입니다. 기존 타임아웃의 원인은 아직 미확정입니다.

충전 LED 정책을 추가했습니다. 실제 충전 상태 전환에 따라 빨간 LED ON/OFF,
서비스 종료 시 원복·수동 설정 보존·재시작과 같은 #48 커널의 재부팅 자동
실행을 확인했습니다. USB500mA에서 화면 부하로 순방전할 수 있고, 화면을
끄면 실제 순충전했습니다. 충전 전류·전압은 바꾸지 않았습니다. 상태 갱신에
UPower 표본 지연이 있으며 완충/초록 LED와 USB 물리 분리는 미검증입니다.

재부팅 후 Wi-Fi HTTPS204, 조도131lux·IIO7개, 관련 서비스 자동 실행 확인.
초기 로그956줄에서 Call trace/SError/GPU PLL 실패/GPIO/escan/RGB 중복0,
CPU 기능 차이52+1·허브 리셋 미확인1·모뎀 QoS4는 남습니다. 현재 모뎀은
셀21개/serving1개를 반환하지만 망 검색 중으로 LTE 데이터 성공은 아닙니다.
CPU/GPU 내부 TMU 보호는 기존대로이며 CPU/GPU 표준 hwmon 표시는 미연결입니다.
전체 기능 정상·커널 경고 전부 해결로 표시하지 않습니다.


## 차량용 자동 시작 — 2026-11-21

사용자 확인: 완전 종료 후 USB 전원 연결만으로는 Ubuntu가 부팅되지 않습니다.
현재 차량 전원 자동 부팅은 미지원/미검증입니다. 일반 재부팅 뒤 서비스
자동 실행 성공과 다릅니다. 충전 연결 시 화면/커널 진입 지점 확인이 남고,
이 검토에서는 기기 전원·BOOT·PMIC·부트로더를 변경하지 않았습니다.
구현 경계와 다음 실물 시험은 [차량 전원 검토](VEHICLE_POWER.md)를 보세요.


## 2026-11-23 — 충전 비활성·배터리 고갈 후 복구

사용자 보고: 케이블 연결 중 종료·삼성 로고/진동 반복. 실제 배터리0%,
3.08–3.20V·순방전, 충전 비트off(inhibit-charge)를 확인했습니다.
사용자 요청 후 모델/#48/BOOT/보호 백업·온도/외부 전원 확인하고 표준 auto
모드만 복구.5–20초 실제 Charging·순충전60–98mA·3.225V 확인.
입력500mA/충전450mA/CV4.2V 제한은 그대로입니다. 충전 비트가 꺼진 원인과
반복 리셋의 정확한 원인·장기/재부팅 회귀는 아직 미확정입니다.


## 2026-11-23 — 안드로이드 충전 정책 동일화: 미완료

순정 비교 후 충전 요청과 실제 CHG 비트를 구분하는 소스 후보를 추가했습니다.
직접 C 테스트8개·ARM64 오브젝트 컴파일 통과. 아직 새 커널 빌드/기기 적용은
안 했고 자동 재활성화 정책도 없습니다. experiments/charging/README.md 참고.
순정의 배터리/USB/충전부 ADC 및 온도·완충·재충전·보호 정책 연결이 남습니다.
현재 배터리0%지만 auto/Charging·3.314V/평균+63mA. 이번 부팅 센서 서비스가
readiness 전에 실패해 IIO0개인 것도 확인했습니다. 재시작·리셋하지 않았으며
온도 입력 검증 없이 강제 충전 루프를 적용하지 않았습니다. 동일화 완료가 아닙니다.


## 2026-11-23 — 최신 충전 상태 및 ADC 진전

배터리8%에서 CHG_EN1인데 NotCharging/Dead였고, 사용자 USB10초 재연결 뒤
실제 Charging/Good·순충전+80–122mA·평균+34mA·약3.67V로 복구했습니다.
원인은 미확정이며 재연결 해제 증거를 소프트웨어 영구 해결로 표시하지 않습니다.
CHGPROT0은 고장/정상 양쪽에 존재합니다. 충전 설정/BOOT은 바꾸지 않았습니다.

ADC v3 4채널 bounded trial 성공·모듈 제거/clock·controls·IRQ 원복 확인.
순정 wired 보정표 대조 완료, 저장 실측 battery37.7/USB35.5/charger39.9C.
이전 FG22C만으로 정상 온도를 판단하지 않습니다. 진단모듈3종 build/link 및
호스트13tests PASS. 상시 calibrated thermal service·상위 보호/완충/재충전
정책·장기/재부팅 charging qualification은 남습니다. README에 재현/한계 기록.

재연결 후 추가4표본/30초에서 Charging/Good 유지, 마지막3.716V/평균+236mA.
순간 부하 방전 표본은 있으므로 공급 상태와 net 평균을 함께 봅니다.


## 2026-11-23 — 현재 충전 원인추적 상태

충전15%/ChargingGood 유지. native 초기화 의도와 IC 실제 timer/restart/
prequal 값 불일치를 확인했으나 초기 미반영인지 이후 변경인지는 미확정.
CAUSES.md의 후보/판별 조건 참고. 강제 unlock/타이머 disable은 하지 않았음.

charge-observer.service active+enabled: 15초 간격 실제 제어값/IC12regs/
온도3종/kernel messages, root-only 제한된 순환 파일에 연속 기록. auditd와
owned control3개 watch 추가; no-write open 시험에서 실제 process/path
감사 이벤트 확인. 조회는 explicit audit.log input 사용. kernel내부 writer나
모든 transient/accepted text를 완전히 기록하는 것은 아님.

온도 hysteresis는 shadow 계산만 연결, actual protection/full/recharge/
swelling/runtime safety 정책은 미완료. 후보 kernel에 readback·caller/
init/cleanup 로그 및 float 설정 오류 전달을 추가했으나 미설치. host23tests/
ARM64 object PASS와 실기 검증을 구분. enable의 actual reboot도 미검증.

순정 wired float4.35V와 native charge ceiling4.4V/design-rating 사용 차이도
발견. 후보 source/DT에서4.35V charge ceiling·보수적 fallback·범위 검증으로
수정했으나 미설치. live4.2V 불변. 최종 observer active/Resultsuccess 및
audit lost0 확인; 기기에서는 계속 기록됩니다.


## 2026-11-23 — #49 실기 적용, #50 보호 복구 후속 준비

#49 BOOT만 새9-partition backup·모델/전원/보호검증 후 적용, 실제부팅과
별도 warm reboot 확인. CV4.35V·timer0/restart3/prequal0 실제 적용.
센서/오디오/BT/cover/LED/haptic/boost 서비스 복귀. 공개 builder 재현 Image
바이트 일치. input/CC는500/450mA 이하로만 낮추어 bootloader900mA 상속 방지.

#49 기록기·inhibit-only 보호 서비스 active. 실제 기록 중단 시 차단 확인.
warm boot 순간 전압강하로 기록기가 늦게 시작되면 차단 뒤 자동 재개되지
않는 한계 확인; 현재는 explicit operator restore로 ChargingGood 복구.
#50에서 사용자 의도·보호 차단을 분리하는 CAS kernel/자동복구 코드를 준비,
빌드 통과했지만 이 시점 #50 실기는 pending. 전압 guard는 유지·bounded
안정값 재시도를 추가. 2h59m 후 fault6 재현 근거로 타이머 경로가 강해졌지만
최초 CHG0 및 기존 설정이 달랐던 이유는 아직 미확정.


## 2026-11-23 — latest: #50 installed, charging protection active

This supersedes #49/pending#50 above. Real #50 BOOT/readback and warm boots
passed. Observer/guardian enabled and active, actual CAS manual-intent protection
and real stale-data stop/automatic recovery verified. CV4.35V, input<=500mA and
CC<=450mA. Final warm boot entered calibrated high-temperature protection pause;
this is not continuous charging qualification. Recorder and bounded three-hour
soak continue privately on device; inspect result status, not process exit alone.
49 targeted tests passed. Physical full/recharge, low-SOC boot, suspend and
long-duration net charging remain unqualified; adaptive stock swelling CV/current
and negotiated fast charge remain incomplete. Timer hypothesis strengthened,
original depletion cause unresolved. See experiments/charging/MANAGEMENT.md.

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


## 2026-11-23 — latest thermal stabilization (qualification in progress)

GPU suspended, battery cooling43.4→41.7C, SOC6%, mean battery current near0.
No further app changes. Screen-off conservative QoS now persists independently
of thermal latch; normal-temperature screen-on releases this overlay. Actual
hot/off application and restart verified; six host tests passed. Module unchanged.
Bounded read-only g965n-thermal-recovery50 is checking automatic charging recovery
and120s screen-off net charging. Pending; charging still blocked above39C.
No reboot or full endurance qualification. Earlier CPU PLL/idle/rendering gaps remain.


## 2026-11-23 — latest: automatic charge recovery and screen-off idle PASS

Natural39.0C triggered automatic charging; reasons cleared, mean current149→
171mA positive. Recovery checker passed122s sampled screen-off window at38.9C,
SOC6%. Screen-off retains650/1066/260MHz/200ms after thermal latch clears.
Actual screenon released to1499.333/2327/572MHz/20ms, off restored limits.
Cold service restart retained the cleared latch. Eleven tests PASS. Partial
record/stale-gap safeguards added. No new module/kernel/voltage/current changes.
Short idle recovery is qualified; reboot/full-cycle/sustained app/build/voice
thermal endurance is not. ChatGPT is still closed. Existing PLL/deep-idle and
offscreen rendering gaps remain; private continuous recording stays active.


Post-cycle idle check: battery38.7C, mean+171mA and Charging, GPU suspended,
observer/guardian/cooling active. Started a NEW bounded10800s read-only
g965n-charging-soak-cooled50.service from this cooled charging baseline.
Stopped the earlier pre-cool soak intentionally; its thermal pauses never
qualified uninterrupted charging. New three-hour result is PENDING; inspect
the result.json inside the directory named by
/var/lib/g965n-charge-observer/latest-soak-path (a private pointer file). This does not reset
guardian safety budgets, change charging controls or auto-restart ChatGPT.

### 충전기 교체 후속

2026-11-23: 사용자 교체 후 DCP 전원 인식을 확인했다. 입력 한도500mA는 그대로이며, 배터리2%·약39.2°C에서 온도 보호 해제를 기다린다. 앱 유지/화면 OFF 후 순방전은 약1~6mA 구간으로 줄었지만 충전 재개·지속 부하 안정성은 아직 미검증이다.
