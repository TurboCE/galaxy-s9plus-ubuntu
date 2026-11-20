# Galaxy S9+ SM-G965N Ubuntu

한국향 S9+에 네이티브 Ubuntu 24.04를 설치하기 위한 소스·빌드 환경·설치 도구입니다.
[SheroAbi의 G965F 포팅](https://github.com/SheroAbi/galaxy-s9plus-mainline-linux)을 기반으로
원본 커널 드라이버, uniLoader, 빌드·설치 코드를 포함합니다.

**G965N에서 Ubuntu 부팅·화면·터치·GPU 가속·Wi-Fi, 실제 음성 입출력과 특정 SIM의 LTE IPv4 통신을 확인했습니다.**
Bluetooth, 자동 밝기·회전 및 센서 앱 연결도 확인했고, NFC는 실제 대상 읽기와
재부팅 후 재읽기를 검증했습니다. 항목마다 검증 범위가 다르며 전체 지원 완료가 아닙니다.
GPS 위치 확정, 진동·알림 LED, 절전·배터리 및 여러 회귀 시험은 남아 있습니다.
카메라·지문은 미지원이며 현재 작업 범위에서 제외합니다.

**현재 작업 브랜치: `codex/g965n-lte-audio`.**
[최신 지원·미지원 현황](docs/g965n/STATUS.md)과
[나중에 이어서 작업하기](docs/g965n/HANDOFF.md)를 먼저 읽으세요.
세부 하드웨어 증거는 [검증표](docs/g965n/VALIDATION.md)에 있습니다.
기본 이미지 빌드만으로 현재 실험 기기의 모든 수동 설정이 재현되는 것은 아닙니다.

## 빌드

Mac/Linux 또는 Windows WSL2의 Bash에서 실행합니다. Docker, Git, Python 3와
공식 Android platform-tools가 필요합니다. 여유 디스크 40GB, Docker 메모리 6GB 이상을
권장합니다. ARM Mac에서도 amd64 도구 환경을 사용하므로 빌드가 더 느릴 수 있습니다.

```bash
git clone --branch codex/g965n-lte-audio https://github.com/TurboCE/galaxy-s9plus-ubuntu.git
cd galaxy-s9plus-ubuntu
bash scripts/g965n/build.sh prepare

# G965N을 TWRP로 부팅한 뒤 adb devices에서 확인한 시리얼을 지정합니다.
export SERIAL=YOUR_DEVICE_SERIAL
python3 scripts/g965n/device.py --serial "$SERIAL" --backup .local/backup
python3 scripts/g965n/extract-firmware.py --serial "$SERIAL"

cp scripts/g965n/image.env.example .local/image.env
# .local/image.env의 IMAGE_PASSWORD를 직접 변경합니다.
bash scripts/g965n/build.sh all
```

빌드는 폰에 쓰지 않습니다. Ubuntu Base와 TWRP 템플릿의 SHA256, Linux v7.1의 정확한
커밋을 검사합니다. Ubuntu 패키지는 공식 업데이트 저장소에서 받으므로 날짜가 다른
이미지는 바이트 단위로 같지 않을 수 있습니다. 패키지·입력 해시와 커밋 기록을 남깁니다.

- 커널: `dist/uniloader/boot-g965n-experimental-*.img`
- Ubuntu: `dist/image-g965n/s9plus-rootfs.img`
- 빌드 기록: `dist/g965n/`, `.local/logs/`

## 실험용 설치

**Android 사용자 데이터가 삭제됩니다. 검증은 G965N rev26 / G965NKSU5FVA2 한 기기 기준입니다.**
[설치·복구 문서](docs/g965n/INSTALL.ko.md)를 읽고 생성된 파일명을 지정하세요.

```bash
python3 scripts/g965n/install.py --serial "$SERIAL" \
  --backup .local/backup \
  --rootfs dist/image-g965n/s9plus-rootfs.img \
  --boot dist/uniloader/boot-g965n-experimental-TIMESTAMP.img \
  --erase-userdata-experimental-g965n
```

모델·복구 환경·파티션 위치·백업 무결성과 EFS/CPEFS 일치를 확인한 뒤 원본의 검증
설치 코드를 호출합니다. USERDATA → BOOT 순서로 쓰고 읽기 검증 후 재부팅합니다.
RECOVERY 및 통신·보정 파티션은 설치 대상이 아닙니다. `dist/m71-*/boot.img`는
uniLoader가 없으므로 설치하지 않습니다.

## 기록·라이선스

- [문제·해결·검증 기록](docs/g965n/CHANGELOG.md)
- [라이선스·재배포 범위](docs/g965n/LICENSING.md), [원본 소스/해시 목록](docs/g965n/source-provenance.json)
- [원본 README](README.upstream.md): 원본 G965F 결과이며 G965N 지원과 구분해야 합니다.

GPL-2.0-only 및 각 파일에 보존된 기존 라이선스를 따릅니다. 삼성/Broadcom 펌웨어,
NVRAM, 개인 백업, 비밀번호, 설치 이미지를 Git에 포함하지 않습니다. 자신의 기기에서
펌웨어를 추출하며 외부 도구는 공식 출처에서 받습니다.

테스트: `python3 -m unittest discover -s tests -v`

로그인 비밀번호는 빌드 시 직접 정합니다. 기본 최소 길이는 8자이며, 명시적으로 짧은
비밀번호를 선택하려면 로컬 image.env에 IMAGE_ALLOW_SHORT_PASSWORD=1을 설정할 수 있습니다.
실험용 드라이버·서비스와 검증 기록은 codex/g965n-lte-audio 브랜치에 있습니다.
확인된 개별 동작과 미완료 항목은 최신 지원표를 기준으로 판단하세요.
