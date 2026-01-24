ZIP Text Viewer

ZIP 파일을 압축 해제하지 않고,
내부의 텍스트 파일을 바로 읽을 수 있는 Windows GUI 도구입니다.

로그 ZIP 파일을 열 때마다
압축 해제 → 파일 탐색 → 텍스트 열기 → 다시 삭제
이 반복이 번거로워서 시작한 개인 프로젝트입니다.

✨ Features

ZIP 내부 텍스트 파일 스트림 직접 읽기

임시 파일 생성 없음

UTF-8 / CP949 인코딩 지원

UTF-8 우선 자동 판별 → 실패 시 CP949 fallback

수동 인코딩 선택 가능

텍스트 검색

Ctrl + F 검색창

Enter / Shift + Enter로 다음·이전 검색

줄바꿈(Word Wrap) ON / OFF 토글

문서 / 로그 파일 특성에 맞춘 UX 설계

공백 없는 긴 문자열 WordWrap edge case 해결

Windows GUI (PySide6 기반)

🖼 Screenshots

이미지 파일은 /images 디렉토리에 포함됩니다.

final_result_zip_text_viewer.png

wordwrap_edge_case_no_break.png

🛠 Tech Stack

Language: Python

GUI: PySide6 (Qt)

Archive: zipfile

Packaging: PyInstaller

🧩 Core Implementation
ZIP 스트림 처리

zipfile.ZipFile.open()을 사용해
ZIP 내부 파일을 메모리 스트림으로 직접 읽음

디스크에 임시 파일을 생성하지 않음

인코딩 처리

UTF-8로 디코딩 시도

실패 시 CP949로 fallback

사용자가 수동으로 인코딩 변경 가능

검색 기능

QTextDocument.find() 기반 구현

QTextDocument.FindFlags 사용

Ctrl + F, Enter, Shift + Enter 단축키 지원

WordWrap UX 설계

기본 WordWrap의 단어 경계 제한 문제 발견

WrapAtWordBoundaryOrAnywhere 옵션 적용

공백 없는 로그/해시 문자열에서도 정상 줄바꿈

🐞 Issues & Fixes

eventFilter 오류

event.KeyPress → QEvent.KeyPress 수정

Enum 소속 오류

QTextDocument.FindFlags, QTextCursor.Start 정정

WordWrap edge case

단어 기준 줄바꿈 한계 분석 후 옵션 변경

인코딩 테스트 불일치

테스트 파일과 실제 로그 파일 차이 원인 분석

📦 Distribution

onefile exe

개인 실사용용

onedir 배포

포트폴리오 설명용

의존성 구조 확인 가능

패키징은 PyInstaller를 사용했으며,
아이콘이 포함된 실행 파일을 생성합니다.

📝 Documentation

Notion에 프로젝트 정리 완료

개발 과정을 기록한 블로그 연재 시리즈 작성

문제 정의

GUI 구조 설계

인코딩 처리

이벤트/에러 디버깅

WordWrap UX 설계

배포 전략 (onefile vs onedir)

회고

🔮 Future Work
7z 지원 확장 (설계 완료)

7z 파일 내부 텍스트 직접 읽기

ZIP과 동일한 UI/UX 유지

아카이브 타입에 따른 backend 분리

기타

다중 파일 탭 지원

대용량 ZIP 파일 성능 최적화

코드 리팩토링 및 모듈화

🎯 Why This Project Matters

이 프로젝트는 단순한 ZIP 뷰어가 아니라,

불편함에서 출발한 문제 정의

GUI UX를 고려한 설계

Qt 내부 동작을 이해하고 해결한 경험

실사용 + 포트폴리오를 동시에 고려한 배포 전략

까지 포함한,
하나의 완결된 개인 도구 개발 경험을 목표로 했습니다.
