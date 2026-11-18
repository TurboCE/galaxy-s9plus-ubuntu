# SM-G965N 설치·복구

실기: Exynos9810 rev26, 256GB, Android 10 G965NKSU5FVA2.
G965F와 같은 기기로 간주하거나, S9/G960N 및 Snapdragon 모델에 적용하지 않습니다.
현재 Ubuntu 부팅은 미검증입니다. 아래 내용이 모든 기기의 시행착오를 없앤다는 뜻은 아닙니다.

## TWRP: 실기 검증 완료

1. Android 개발자 옵션의 OEM 잠금 해제와 USB 디버깅을 켜고 호스트를 허용합니다.
2. Android를 인터넷에 연결합니다. 이 기기에서는 오프라인 KG Prenormal이 RECOVERY를
   막았고 Wi-Fi 연결 뒤 Checking으로 바뀌었습니다. RMM/FRP는 별도 확인해야 하며,
   모든 기기가 즉시 풀리거나 반드시 7일이면 풀린다는 뜻은 아닙니다.
3. 공식 [TWRP star2lte](https://twrp.me/samsung/samsunggalaxys9plus.html)의 3.3.1-0과
   [samloader 2.2.0](https://github.com/topjohnwu/samloader-rs/releases/tag/2.2.0)을 받습니다.
   Knox 보증 비트가 영구 변경될 수 있습니다. 필요한 데이터는 먼저 보존하세요.
4. TWRP SHA256은 `5b5d2290940203316024a94581107ffad17670bb2f596fd27ef483d3d2685994`입니다.
5. `adb -s "$SERIAL" reboot download` 후 `samloader detect --json`으로 SM-G965N을 확인합니다.

```bash
samloader flash --partition RECOVERY twrp-3.3.1-0-star2lte.img --no-reboot
```

PIT 쓰기·재분할·erase·부트로더 업데이트는 하지 않습니다.
전원+볼륨 아래를 눌러 화면이 꺼지면 전원은 계속 누른 채 볼륨 아래를 놓고,
볼륨 위+빅스비를 추가해 복구 화면까지 유지합니다. 일반 Android 부팅은 순정 복구로
덮어쓸 수 있습니다. 화면 제목 **Team Win Recovery Project**를 확인하고 Keep Read Only를
선택합니다. 암호 입력은 취소할 수 있습니다. 아직 Format Data나 시스템 변경 허용은 불필요합니다.

```bash
adb -s "$SERIAL" shell getprop ro.twrp.version
adb -s "$SERIAL" shell id -u
# 실제 관측: 3.3.1-0, 0
```

도구 종료 코드만으로 설치 성공을 판단하지 않습니다. 실제 복구 부팅과 읽기 검증이 기준입니다.

## 백업·펌웨어 추출: 실기 검증 완료

README의 `device.py --backup`은 BOOT/DTB/DTBO/EFS/CPEFS/RADIO/MISC/RECOVERY/PARAM
9개를 읽고 크기와 원본 SHA256을 확인합니다. RECOVERY는 TWRP이고 순정 복구가 아닙니다.
SYSTEM/VENDOR/USERDATA 전체 백업도 아닙니다. `.local/backup`을 별도 디스크에도 보관하세요.
EFS/CPEFS와 원본 로그는 공개하지 않습니다.

`extract-firmware.py`는 VENDOR를 `ro,noload`로 임시 마운트하여 저널 재생 없이 읽습니다.
Wi-Fi 코드/NVRAM/CLM을 추출하고 해시 확인 후 언마운트합니다. 추출 파일은 Git에서 제외됩니다.
G965N의 코드/NVRAM은 G965F와 달랐습니다. 추출 성공은 mainline Wi-Fi 동작 검증이 아닙니다.

## 빌드·설치: 아직 실험 단계

README의 Docker 흐름을 사용합니다. rootfs 빌드의 SYS_ADMIN 권한은 Docker Linux 환경의
chroot/마운트에 사용하고, USB·Docker 소켓·호스트 루트를 전달하지 않습니다.
다른 작업과 빌드 볼륨을 공유하지 마세요. 비밀번호는 `.local/image.env`에서 지정합니다.

설치 전 모델·본인 기기의 EFS/CPEFS·백업 검증, 이미지 크기, USERDATA 미마운트 여부와
복구 진입 방법을 확인합니다. `install.py`는 사용자 데이터 삭제에 대한 명시 옵션이 필요합니다.
기존 설치 코드는 USERDATA를 128MiB 청크로 복사·검사하고 전체 읽기 검증 뒤 BOOT를 씁니다.
BOOT도 읽기 검증 후 재부팅합니다. RECOVERY와 라디오 파티션은 쓰지 않습니다.
`adb exec-in`은 이 복구 환경에서 데이터를 버릴 수 있어 이미지 전송에 사용하지 않습니다.
원본 설치기는 연결 복구 중 호스트 ADB 서버를 재시작할 수 있어 다른 폰 작업과 동시에 쓰지 마세요.

## 첫 부팅·실패 대응

이 빌드의 USB 주소는 폰 172.16.42.2이고, 호스트는 DHCP로 172.16.42.10–20을 받습니다.
자동 할당이 실패하면 호스트에 172.16.42.1/24를 수동 지정해 진단할 수 있습니다.
G965N의 USB SSH와 GNOME/Wi-Fi는 아직 검증해야 합니다. 로그인은 본인의 image.env 값입니다.
응답이 없으면 반복 플래시하지 말고 TWRP에서 로그·BOOT를 확인합니다.
stock BOOT만 복구해도 Ubuntu로 교체한 USERDATA는 복원되지 않으므로 Android 복귀에는
해당 기기 순정 펌웨어·데이터 파일시스템 복구가 별도로 필요합니다. 부트로더 다운그레이드나
재잠금을 복구 수단으로 사용하지 않습니다.

USB SSH → 저장소 → 화면·터치 → Wi-Fi → 충전·온도 → 반복 재부팅 순으로 검사합니다.
LTE·오디오·절전은 별도 개발·검증 항목입니다. 결과를 CHANGELOG와 VALIDATION에 남깁니다.
