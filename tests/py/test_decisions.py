"""결정 요약 `decisions.py --brief` 시험(설계 C 3.5, D-C5).

- 대체 거르기·첫 문장 자르기·형식 밖 셈은 `brief_lines`를 단위로 부르고, 종료 코드는 명령행으로만 보인다(설계 4절 10.1 행).
- 사례 이름의 `{가~마}`가 머리 파일 판정 기준 1의 사례다.
"""
from conftest import run_script, write

import decisions

HEAD = "결정 {}개 (대체 {}개 뺌). 전문은 decisions.md에서 시각으로 찾는다"
KEEP_1 = "- 2026-10-30 02:40:51 | 설계를 A·B·C로 나눔 | 원문: \"A·B·C (Recommended)\" | T001"
KEEP_2 = "- 2026-10-30 10:29:52 | 이번 실행의 값: 동시에 도는 흐름 2 → 3 | 원문: \"동시흐름 3개로\" | -"
OLD = "- 2026-10-30 02:27:53 | 내보내기 main에 병합만 | 원문: \"병합만\" | - → 대체: 2026-10-30 09:00:00"


# --- (가) 대체된 결정은 빼고 원문은 내지 않는다 -------------------------------------------------------------------

def test_ga_superseded_line_is_dropped():
    lines, kept, superseded, malformed = decisions.brief_lines("\n".join([KEEP_1, OLD, KEEP_2]) + "\n")

    assert lines[0].startswith("결정 2개 (대체 1개 뺌)")
    assert (kept, superseded, malformed) == (2, 1, 0)
    assert lines[1:] == ["- 2026-10-30 02:40:51 | 설계를 A·B·C로 나눔",
                         "- 2026-10-30 10:29:52 | 이번 실행의 값: 동시에 도는 흐름 2 → 3"]
    assert not [l for l in lines if "원문:" in l]


# --- (나) 결정 칸의 첫 문장까지 -------------------------------------------------------------------------------

def test_na_decision_cell_cut_at_first_sentence():
    lines = decisions.brief_lines("- 2026-10-30 10:00:00 | A를 정함. 이유는 B | 원문: \"가\" | T001\n")[0]
    assert lines == [HEAD.format(1, 0), "- 2026-10-30 10:00:00 | A를 정함."]
    # 대조: `. `이 없으면 칸 전체
    whole = decisions.brief_lines("- 2026-10-30 10:00:00 | A를 정함(이유 B) | 원문: \"가\" | T001\n")[0]
    assert whole[1] == "- 2026-10-30 10:00:00 | A를 정함(이유 B)"


# --- (다) 형식 밖 줄은 끝 줄로 센다 ----------------------------------------------------------------------------

def test_da_malformed_lines_counted_in_last_line():
    text = "\n".join(["# 결정", "", KEEP_1, "- 2026-10-30 11:00:00 | 칸이 하나뿐"]) + "\n"
    lines, kept, superseded, malformed = decisions.brief_lines(text)
    assert lines[-1] == "형식 밖 2줄: # 결정, 2026-10-30 11:00:00"
    assert (kept, superseded, malformed) == (1, 0, 2)
    # 대조: 형식 밖 줄이 없으면 끝 줄도 없다
    assert decisions.brief_lines(KEEP_1 + "\n\n")[0][-1] == "- 2026-10-30 02:40:51 | 설계를 A·B·C로 나눔"


def test_da_line_without_original_cell_is_malformed_and_shows_time():
    text = "- 2026-10-30 14:35:18 | T015 | V-01은 안 (다)\n" + KEEP_1 + "\n"
    lines, kept, superseded, malformed = decisions.brief_lines(text)
    assert lines[0] == HEAD.format(1, 0)
    assert (kept, superseded, malformed) == (1, 0, 1)
    assert not [l for l in lines if l.endswith("T015")]
    assert lines[-1] == "형식 밖 1줄: 2026-10-30 14:35:18"
    # 대조: 형식대로인 줄만 있으면 끝 줄이 없고 결정 줄만 나온다
    assert decisions.brief_lines(KEEP_1 + "\n")[0] == [HEAD.format(1, 0), "- 2026-10-30 02:40:51 | 설계를 A·B·C로 나눔"]


def test_da_non_bullet_or_pipeless_line_shows_first_30_chars():
    long = "x" * 40
    lines = decisions.brief_lines(long + "\n- 파이프 없는 결정 줄\n")[0]
    assert lines[-1] == "형식 밖 2줄: {}, - 파이프 없는 결정 줄".format("x" * 30)


def test_da_task_id_decision_cell_or_shifted_original_cell_is_malformed():
    shifted = [
        "- 2026-10-30 14:35:18 | T015 | 결정 문장 | 원문: \"가\" | T015",
        "- 2026-10-30 14:35:19 | T015 | 원문: \"가\" | T015",
        "- 2026-10-30 14:35:20 | T15 | 원문: \"가\" | T015",
        "- 2026-10-30 14:35:21 | T015,T016 | 원문: \"가\" | T015",
        "- 2026-10-30 14:35:22 | 결정 문장 | 관련 | 원문: \"가\"",
        "- 2026-10-30 14:35:23 | 원문: \"가\" | 결정 문장",
    ]
    lines, kept, superseded, malformed = decisions.brief_lines("\n".join(shifted) + "\n" + KEEP_1 + "\n")
    assert (kept, superseded, malformed) == (1, 0, 6)
    assert lines == [HEAD.format(1, 0), "- 2026-10-30 02:40:51 | 설계를 A·B·C로 나눔",
                     "형식 밖 6줄: " + ", ".join("2026-10-30 14:35:%d" % n for n in range(18, 24))]
    # 대조: `T`로 시작하는 일반 낱말과 셋째 칸이 `원문:`인 세 칸 줄은 형식 안이다
    inside = "- 2026-10-30 14:36:00 | Test 추가 | 원문: \"가\" | T001\n- 2026-10-30 14:36:01 | T로 시작 | 원문: \"나\"\n"
    assert decisions.brief_lines(inside)[0] == [HEAD.format(2, 0), "- 2026-10-30 14:36:00 | Test 추가",
                                                "- 2026-10-30 14:36:01 | T로 시작"]


def test_da_superseded_line_with_shifted_cells_is_still_superseded():
    old = "- 2026-10-30 14:37:00 | T015 | 결정 | 원문: \"가\" | - → 대체: 2026-10-30 15:00:00"
    lines, kept, superseded, malformed = decisions.brief_lines(old + "\n")
    assert (kept, superseded, malformed) == (0, 1, 0)
    assert lines == [HEAD.format(0, 1)]


# --- (라) 명령행: --brief가 없거나 다르면 사용법과 종료 2 -------------------------------------------------------

def test_ra_cli_without_brief_prints_usage_and_exits_2(tmp_path):
    write(tmp_path / "decisions.md", KEEP_1 + "\n")
    for args in ([tmp_path], [tmp_path, "--full"]):
        r = run_script("decisions", *args)
        assert r.returncode == 2, r.output
        assert "python decisions.py {실행 폴더} --brief" in r.stdout
    # 대조: --brief면 종료 0과 요약
    r = run_script("decisions", tmp_path, "--brief")
    assert r.returncode == 0, r.output
    assert r.stdout.splitlines() == [HEAD.format(1, 0), "- 2026-10-30 02:40:51 | 설계를 A·B·C로 나눔"]


# --- (마) 명령행: decisions.md가 없으면 0개와 종료 0 -----------------------------------------------------------

def test_ma_cli_missing_file_reports_zero(tmp_path):
    r = run_script("decisions", tmp_path, "--brief")
    assert r.returncode == 0, r.output
    assert r.stdout.splitlines() == ["결정 0개 (decisions.md 없음)"]
