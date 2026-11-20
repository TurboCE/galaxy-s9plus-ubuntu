# SM-G965N 현재 지원 현황

갱신: 2026-11-20 KST. 실험 브랜치: `codex/g965n-lte-audio`.
최신 확인 기준은 native #48 + NFC 클럭/서비스 + RTC IRQ 설정 수정입니다.
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
| GPS | 과거 실제3D fix·GeoClue 전달 확인. 이번 수신 불가 장소에서 HAL 시작/UTC·XTRA/유효 NMEA 전달 확인 | 사용자 확인 환경 제약. 수신 가능한 장소의 최종 fix·이동/냉간/절전 회귀는 미검증 |
| RTC | IRQ 타입 경고 수정, 초기 부팅·별도 재부팅 후 시계 진행·실제 알람·시간 유지·Ubuntu NTP 동기화 상태 확인 | 완전 전원 차단 유지·절전 깨우기 |
| 홀/커버 | 자석에 따른 SW_LID·logind 이벤트 확인 | 실제 커버·화면 정책. 현재 덮개 동작은 ignore |
| 화면만 끄기 | 화면 꺼짐 중 센서·인터넷·백그라운드 유지 확인 | 물리 전원 키 전체 동작·Android 대비 소모량 |
| 서스펜드·깊은 절전 | 미완료, suspend 관련 target은 기존 정책으로 차단 | 깨우기 경로·모든 장치 복귀·전력 측정 |
| RGB 알림 LED | 세 색 실제 점등·저전류 코드0..1·재부팅 자동 구동 확인. 후속 regmap 이름 충돌 수정 후 별도 재부팅 자동 구동·세 색 읽기·기존 PMIC 맵 보존·중복 오류0 확인 | GNOME 알림·충전 정책, 밝기/색 보정, 하드웨어 패턴 |
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
