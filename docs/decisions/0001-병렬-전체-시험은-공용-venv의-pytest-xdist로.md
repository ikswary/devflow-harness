# 병렬 전체 시험은 공용 venv의 pytest-xdist로 돌린다

- 날짜: 2026-11-17
- 정한 사람: 사용자(원문 "1. 가" → "추천대로 진행")
- 상태: 유효

## 결정
전체 시험을 병렬로 돌리기 위해 `requirements-dev.txt`에 `pytest-xdist==3.8.0`을 더하고, 공용 venv의 python으로 `-m pytest -q -p no:cacheprovider -n auto`를 돌린다. `-n auto`는 pytest 설정 파일에 넣지 않고 명령에 붙인다(시험 파일 하나를 돌릴 때도 작업자를 띄우지 않으려고).

## 버린 길
- 시스템 python에 설치된 pytest-xdist를 쓰는 길: 이 컴퓨터의 경로에 묶인다.

## 근거
순차 전체 시험이 2023초(약 34분)라 커밋 전 전체 시험을 매번 돌리기 어려웠다. 병렬(`-n auto`)에서는 316.83초이고 순차와 같은 결과(7797 passed, 2 skipped, 0 failed)였다. 시험이 저장소를 읽기만 하고 `tmp_path` 아래에만 쓰기 때문에 시험 고침은 필요하지 않았다.

## 되돌리려면
`requirements-dev.txt`의 한 줄과 `references/main/maintain.md`, `docs/plugin-practices.md`의 시험 명령 문장을 되돌린다.
