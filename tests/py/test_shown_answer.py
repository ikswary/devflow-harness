"""1.2.0 M0-3: 보인 화면 저장(`screen.py --save`), 답의 꼴 해석, 멈춤 측정(설계 8.1절).

- `--save`는 출력한 화면을 `tasks/{id}/screen-shown.md`에 남기고 그 시각을 `asked_at`에 적는다. 꼬리 줄 `메인 컨텍스트:`는 남기지 않는다.
- 답의 꼴은 기계 해석이고, 꼴에 맞지 않으면 None이어서 메인이 되묻는다.
- `--record`는 `asked_at` 뒤에 반환이 왔으나 처리되지 못한 task의 수와 시간을 journal에 적고 `asked_at`을 비운다.
"""
import re
import time

import pytest
from conftest import run_script

RESULT = "## 승인 화면\n### 정해 주실 것\n- 없음\n### 하실 일·허용 요청\n- 없음\n### 알릴 것\n- 없음\n### 답하신 것의 반영\n- 없음\n### 확인 안 된 것\n- 없음\n### 건수만\n- 없음\n"


def make(run_dir, tid="T001", **meta):
    run_dir.task(tid, "시험 " + tid, **meta)
    (run_dir.task_dir(tid) / "result.md").write_text(RESULT, encoding="utf-8")


def test_ga_save_writes_shown_file_and_asked_at(run_dir):
    make(run_dir, status="승인대기")
    p = run_script("screen", run_dir.path, "T001", "--save")
    assert p.returncode == 0, p.output
    shown = (run_dir.task_dir("T001") / "screen-shown.md").read_text(encoding="utf-8")
    assert shown.startswith("[design T001] 시험 T001")
    assert "counts:" in shown
    assert "메인 컨텍스트:" not in shown
    assert str(run_dir.tasks()["T001"].get("asked_at", "")).startswith("20")


def _without_context_line(out):
    # 꼬리 줄은 살아 있는 세션 기록을 읽으므로 두 번의 실행 사이에 값이 바뀔 수 있다
    return [l for l in out.splitlines() if not l.startswith("메인 컨텍스트:")]


def test_na_save_prints_the_same_screen(run_dir):
    make(run_dir, status="승인대기")
    plain = run_script("screen", run_dir.path, "T001")
    saved = run_script("screen", run_dir.path, "T001", "--save")
    assert _without_context_line(saved.stdout) == _without_context_line(plain.stdout)


@pytest.mark.parametrize("status", ["자체검증", "진행", "완료"])
def test_pa_save_outside_waiting_does_not_save(run_dir, status):
    make(run_dir, status=status)
    p = run_script("screen", run_dir.path, "T001", "--save")
    assert p.returncode == 0, p.output
    assert "--save 안 함" in p.stdout
    assert not (run_dir.task_dir("T001") / "screen-shown.md").exists()
    assert not str(run_dir.tasks()["T001"].get("asked_at", "")).strip()


def test_ta_save_on_broken_head_file_reports_instead_of_traceback(run_dir, lib, monkeypatch, capsys):
    import screen
    make(run_dir, status="승인대기")

    def broken(path):
        raise lib.Reject("머리 파일 형식 아님")
    monkeypatch.setattr(lib, "Doc", broken)
    assert screen.main(["screen.py", str(run_dir.path), "T001", "--save"]) == 3
    assert "--save 실패: 머리 파일 형식 아님" in capsys.readouterr().out


def test_da_screen_without_save_writes_nothing(run_dir):
    make(run_dir, status="승인대기")
    run_script("screen", run_dir.path, "T001")
    assert not (run_dir.task_dir("T001") / "screen-shown.md").exists()
    assert not str(run_dir.tasks()["T001"].get("asked_at", "")).strip()


def test_ra_save_rewrites_on_second_ask(run_dir):
    make(run_dir, status="승인대기")
    run_script("screen", run_dir.path, "T001", "--save")
    f = run_dir.task_dir("T001") / "screen-shown.md"
    f.write_text("옛 화면", encoding="utf-8")
    run_script("screen", run_dir.path, "T001", "--save")
    assert f.read_text(encoding="utf-8") != "옛 화면"


def test_ma_save_on_missing_task_keeps_error(run_dir):
    p = run_script("screen", run_dir.path, "T999", "--save")
    assert p.returncode == 2
    assert not (run_dir.task_dir("T999") / "screen-shown.md").exists()


ALLOWED = ("가", "승인", "두지 않음", "남김", "규칙 없음", "이번만", "규칙 2", "문제 없음", "이 코드만 고침", "판단 안 됨")
WITH_TEXT = ("이 코드만 고침", "판단 안 됨")


@pytest.mark.parametrize("text,want", [
    ("T021 ①가", [{"task": "T021", "item": 1, "value": "가"}]),
    ("T021 승인", [{"task": "T021", "value": "승인"}]),
    ("T030 두지 않음", [{"task": "T030", "value": "두지 않음"}]),
    ("T004 남김 ①③⑤", [{"task": "T004", "value": "남김", "items": [1, 3, 5]}]),
    ("T004 두지 않음 ①③", [{"task": "T004", "value": "두지 않음", "items": [1, 3]}]),
    ("3 규칙 없음", [{"item": 3, "value": "규칙 없음"}]),
    ("나머지 남김", [{"rest": True, "value": "남김"}]),
    ("2 빼고 승인", [{"except": 2, "value": "승인"}]),
    ("이의 4", [{"objection": 4}]),
    ("3", [{"number": 3}]),
    ("1. 3", [{"item": 1, "value": "3"}]),
    ("1 이번만, 2 규칙 2", [{"item": 1, "value": "이번만"}, {"item": 2, "value": "규칙 2"}]),
    ("1. 3\n2. 2\n3. 4", [{"item": 1, "value": "3"}, {"item": 2, "value": "2"}, {"item": 3, "value": "4"}]),
])
def test_ba_answer_forms(lib, text, want):
    assert lib.parse_answer(text, ALLOWED) == want


@pytest.mark.parametrize("text,want", [
    ("문제 없음", [{"value": "문제 없음"}]),
    ("판단 안 됨 구조 표", [{"value": "판단 안 됨", "text": "구조 표"}]),
    ("승인", [{"value": "승인"}]),
    ("2 이 코드만 고침 : 값 순환을 끊기", [{"item": 2, "value": "이 코드만 고침", "text": "값 순환을 끊기"}]),
    ("이 코드만 고침 : 첫째, 둘째", [{"value": "이 코드만 고침", "text": "첫째, 둘째"}]),
    ("3 판단 안 됨 구조 표", [{"item": 3, "value": "판단 안 됨", "text": "구조 표"}]),
    ("1 문제 없음, 2 이 코드만 고침 : 가, 나", [{"item": 1, "value": "문제 없음"}, {"item": 2, "value": "이 코드만 고침", "text": "가, 나"}]),
])
def test_bb_answers_with_text(lib, text, want):
    assert lib.parse_answer(text, ALLOWED, WITH_TEXT) == want


@pytest.mark.parametrize("text", [
    "승인 그리고 나머지는 알아서", "문제 없음 같아요", "이 코드만 고침", "이 코드만 고침에도 승인합니다", "이 코드만 고침요", "이 코드만 고침.",
])
def test_bc_text_only_after_the_named_choices(lib, text):
    assert lib.parse_answer(text, ("승인", "문제 없음"), WITH_TEXT) is None


@pytest.mark.parametrize("text", [
    "", "   ", "네 그렇게 하세요", "T21 승인", "다 잘 모르겠음", "①", "²",
    "1 이번만, 그리고 나머지는 알아서", "1 이번만 그리고 나머지는 알아서",
    "T021 ①가 ②나", "2 빼고", "2 개만 고쳐주세요", "T021 왜 이렇게 했어요?",
    "나머지 전부 다시 봐주세요", "나머지 자동 승인",
])
def test_sa_unmatched_answer_is_none(lib, text):
    assert lib.parse_answer(text, ALLOWED) is None


NEW = {"started_version": "1.2.0-dev.1", "rules": "2"}
DECIDE = RESULT.replace(
    "### 정해 주실 것\n- 없음",
    "### 정해 주실 것\n- 저장 위치를 정합니다\n  - (가) 파일\n  - (나) DB\n- 보관 기간을 정합니다\n  (다) 30일\n\n  (라) 90일",
).replace("### 알릴 것\n- 없음", "### 알릴 것\n- 이름을 바꿨습니다").replace("### 확인 안 된 것\n- 없음", "### 확인 안 된 것\n- 없음 (문서만 바꿨습니다)")


def make_numbered(run_dir, text=DECIDE):
    run_dir.task("T001", "시험 T001", status="승인대기", **NEW)
    (run_dir.task_dir("T001") / "result.md").write_text(text, encoding="utf-8")


def numbers_in(out):
    """화면에서 찾은 항목 번호. 기록 점검 걸림이 맨 위에 끼일 수 있으므로 시험이 번호를 짐작하지 않는다."""
    found = {}
    for key, word in (("save", "저장 위치를 정합니다"), ("keep", "보관 기간을 정합니다"), ("note", "이름을 바꿨습니다")):
        found[key] = int(re.search(r"^- \[(\d+)\] " + word, out, re.M).group(1))
    return found


def test_ne_new_task_screen_numbers_items_across_cells(run_dir):
    make_numbered(run_dir)
    out = run_script("screen", run_dir.path, "T001").stdout
    n = numbers_in(out)
    assert n["save"] + 1 == n["keep"] < n["note"]
    assert "■ 하실 일" not in out   # 값이 없는 칸은 제목도 싣지 않는다
    assert "  - (가) 파일" in out and "- [{}] (가)".format(n["keep"]) not in out
    assert "- 없음 (문서만 바꿨습니다)" in out
    assert "- [{}] 없음".format(n["note"] + 1) not in out


def test_ol_old_task_screen_stays_unnumbered(run_dir):
    run_dir.task("T001", "시험 T001", status="승인대기", started_version="1.1.1")
    (run_dir.task_dir("T001") / "result.md").write_text(DECIDE, encoding="utf-8")
    out = run_script("screen", run_dir.path, "T001").stdout
    assert "- 저장 위치를 정합니다" in out
    assert "- [1]" not in out


def save_numbered(run_dir):
    make_numbered(run_dir)
    return numbers_in(run_script("screen", run_dir.path, "T001", "--save").stdout)


@pytest.mark.parametrize("text,line", [
    ("{save} 가", "항목 {save}: 가 | 저장 위치를 정합니다"),
    ("{keep} (다)", "항목 {keep}: (다) | 보관 기간을 정합니다"),
    ("{keep} 라", "항목 {keep}: 라 | 보관 기간을 정합니다"),
    ("{save} 고칠 것이 있음 : 글", "항목 {save}: 고칠 것이 있음 : 글 | 저장 위치를 정합니다"),
    ("나머지 고칠 것이 있음 : 글", "나머지 전부: 고칠 것이 있음 : 글"),
    ("{keep} 빼고 고칠 것이 있음 : 글", "{keep} 빼고 전부: 고칠 것이 있음 : 글"),
    ("{save} 가, 승인", "전체: 승인"),
    ("T001 남김 ①", "항목 1: 남김"),
    ("T999 라", "다른 task: T999 | T999 라"),
    ("T999 3 가", "다른 task: T999 | T999 3 가"),
    ("{save} 가\nT999 ②라", "다른 task: T999 | T999 ②라"),
    ("승인", "전체: 승인"),
    ("T001 승인", "전체: 승인"),
    ("고칠 것이 있음 : 이름을 다시, 짧게", "전체: 고칠 것이 있음 : 이름을 다시, 짧게"),
    ("이의 {note}", "이의: 항목 {note} | 이름을 바꿨습니다"),
    ("{keep} 빼고 승인", "{keep} 빼고 전부: 승인"),
    ("나머지 남김", "나머지 전부: 남김"),
    ("T999 승인", "다른 task: T999 | T999 승인"),
])
def test_sh_answer_resolves_against_the_saved_screen(run_dir, text, line):
    n = save_numbered(run_dir)
    before = (run_dir.task_dir("T001") / "task.md").read_text(encoding="utf-8")
    p = run_script("screen", run_dir.path, "T001", "--answer", text.format(**n))
    assert p.returncode == 0, p.output
    assert line.format(**n) in p.stdout
    assert (run_dir.task_dir("T001") / "task.md").read_text(encoding="utf-8") == before


def test_ci_circled_item_form_resolves(run_dir, lib):
    n = save_numbered(run_dir)
    p = run_script("screen", run_dir.path, "T001", "--answer", "T001 {}다".format(lib.CIRCLED[n["keep"] - 1]))
    assert p.returncode == 0, p.output
    assert "항목 {}: 다 | 보관 기간을 정합니다".format(n["keep"]) in p.stdout


@pytest.mark.parametrize("text", [
    "{note}", "99 가", "이의 99", "99 빼고 승인", "{save} 다", "{keep} 가", "네 그렇게 하세요", "승인 그리고 나머지는 알아서", "나머지 자동 승인", "라",
    "가", "T001 가", "나머지 가", "{keep} 빼고 나", "T001 1", "나머지 1", "{keep} 빼고 3", "{save} 12", "남김",
    "T001 남김 ⑳", "T001 승인 ⑳", "T001 남김 ①⑳", "T001 ⑳가",
    "승인, 보류", "{save} 가, {save} 나", "승인, 고칠 것이 있음 : 글", "나머지 승인, 나머지 보류",
    "이의 {save}, {save} 가", "{keep} 빼고 승인, {keep} 다", "{keep} 빼고 승인, 나머지 남김",
    "고칠 것이 있음에도 승인합니다", "고칠 것이 있음요", "고칠 것이 있음.",
])
def test_re_answer_that_does_not_fit_asks_again(run_dir, text):
    n = save_numbered(run_dir)
    p = run_script("screen", run_dir.path, "T001", "--answer", text.format(**n))
    assert p.returncode == 3, p.output
    assert "되물음" in p.stdout


def test_ng_answer_without_saved_screen_asks_again(run_dir):
    make_numbered(run_dir)
    p = run_script("screen", run_dir.path, "T001", "--answer", "승인")
    assert p.returncode == 3
    assert "지금 열린 화면 없음" in p.stdout


def test_nh_answer_after_a_record_needs_a_new_save(run_dir):
    n = save_numbered(run_dir)
    run_script("task_set", run_dir.path, "T001", "--record", '되물음(이해)|무엇|"뭐죠"')
    answer = "{} 가".format(n["save"])
    assert run_script("screen", run_dir.path, "T001", "--answer", answer).returncode == 3
    run_script("screen", run_dir.path, "T001", "--save")
    assert str(run_dir.tasks()["T001"].get("asked_at", "")).startswith("20")
    assert run_script("screen", run_dir.path, "T001", "--answer", answer).returncode == 0


def test_nk_answer_on_a_finished_task_asks_again(run_dir):
    save_numbered(run_dir)
    text = (run_dir.task_dir("T001") / "task.md").read_text(encoding="utf-8")
    (run_dir.task_dir("T001") / "task.md").write_text(text.replace("status: 승인대기", "status: 완료"), encoding="utf-8")
    assert run_script("screen", run_dir.path, "T001", "--answer", "승인").returncode == 3


def test_nl_items_outside_the_cells_do_not_count():
    import screen
    shown = "■ 통과 못 한 기준\n- [9] 기준 3이 틀렸습니다\n\n■ 알릴 것 (1)\n- [1] 알림\n  (가) 하나\n\n■ 만들 task 1개\n- [1] 제목 (나)\n\ncounts: n_decide=0\n- [7] 뒤\n"
    assert screen.shown_items(shown) == {1: "알림\n  (가) 하나\n"}


def test_gu_answer_uses_the_saved_screen_not_a_new_one(run_dir):
    n = save_numbered(run_dir)
    changed = DECIDE.replace("- 저장 위치를 정합니다", "- 다른 결정입니다\n- 저장 위치를 정합니다")
    (run_dir.task_dir("T001") / "result.md").write_text(changed, encoding="utf-8")
    p = run_script("screen", run_dir.path, "T001", "--answer", "{} 가".format(n["save"]))
    assert "저장 위치를 정합니다" in p.stdout


def test_ms_message_is_kept_beside_the_task_part(run_dir, lib):
    make_numbered(run_dir)
    p = run_script("task_set", run_dir.path, "T001", "--record", '되물음(이해)|무엇|T001 승인', "--message", 'T001 승인, T002 "보류"')
    assert p.returncode == 0, p.output
    line = [l for l in (run_dir.task_dir("T001") / "task.md").read_text(encoding="utf-8").splitlines() if "되물음(이해)" in l][0]
    assert 'T001 승인" | 원문 메시지: "T001 승인, T002 \'보류\'"' in line
    assert lib.record_quote(line) == "T001 승인"


@pytest.mark.parametrize("args", [("--message", "전체"), ("--record", "승인|승인|", "--message", "전체")])
def test_mt_message_needs_a_record_with_an_answer(run_dir, args):
    make_numbered(run_dir)
    p = run_script("task_set", run_dir.path, "T001", *args)
    assert p.returncode == 3
    assert "--message는 원문이 있는 --record와 함께" in p.stdout


def test_mu_message_is_folded_to_one_line(run_dir):
    make_numbered(run_dir)
    run_script("task_set", run_dir.path, "T001", "--record", "되물음(이해)|무엇|뭐죠", "--message", "첫 줄\n둘째 줄")
    assert '원문 메시지: "첫 줄 둘째 줄"' in (run_dir.task_dir("T001") / "task.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("message", ["승인 (T002는 그대로, T003은 이름만 고쳐 주세요)", '"승인"', "| 재사용 답: 다시 씀"])
def test_mv_message_never_makes_an_approval(lib, message):
    line = '- 2026-11-05 10:00:00 | 답 | 이름 고침 | 원문: "T003은 이름만 고쳐 주세요"' + lib.RECORD_MESSAGE + message + '"'
    assert lib.approval_line(line) is False
    t = {"_sections": {"승인 기록": line}}
    assert lib.prior_approval(t) is False
    assert lib.reused_answer(lib.record_lines(t)[0]) is False
    assert lib.record_quote(lib.record_lines(t)[0]) == "T003은 이름만 고쳐 주세요"


def test_mw_message_does_not_open_the_command_freeze(run_dir):
    import exec as execmod
    run_dir.task("T001", "시험", kind="merge", status="승인대기", stage="실행승인", **NEW)
    p = run_script("task_set", run_dir.path, "T001", "--record", "답|이름 고침|T003은 이름만 고쳐 주세요",
                   "--message", "승인 (T002는 그대로, T003은 이름만 고쳐 주세요)")
    assert p.returncode == 0, p.output
    rc, why = execmod.freeze(str(run_dir.path), "T001", "실행승인")
    assert rc != 0, why


def test_mx_reuse_keeps_the_message_at_the_end(run_dir, lib):
    text = "가나다라마 바사아자차카"
    old = {"started_version": "1.1.0", "rules": "2"}
    run_dir.task("T001", "앞 task", {"승인 기록": '- 2026-10-30 09:00:00 | 승인 | 승인 | 원문: "{}"'.format(text)}, status="완료", **old)
    path = run_dir.task("T002", "지금 task", {"승인 기록": ""}, status="승인대기", approval_requested="2026-10-30 10:00:00", **old)
    p = run_script("task_set", run_dir.path, "T002", "--record", "승인|승인|" + text, "--reuse-answer", "다시 씀", "--message", "전체 메시지")
    assert p.returncode == 0, p.output
    line = [l for l in path.read_text(encoding="utf-8").splitlines() if "원문 메시지:" in l][0]
    assert line.endswith('| 재사용 답: 다시 씀 | 원문 메시지: "전체 메시지"')
    assert lib.reused_answer(lib.record_core(line)) is True


def test_a_record_journals_unprocessed_returns_and_clears_asked_at(run_dir):
    make(run_dir, status="승인대기")
    make(run_dir, "T002", status="진행")
    make(run_dir, "T003", status="진행")
    run_script("screen", run_dir.path, "T001", "--save")
    time.sleep(1.1)
    (run_dir.task_dir("T002") / "result.md").write_text(RESULT + "\n", encoding="utf-8")
    p = run_script("task_set", run_dir.path, "T001", "--record", '되물음(이해)|무엇|"뭐죠"')
    assert p.returncode == 0, p.output
    journal = (run_dir.path / "journal.md").read_text(encoding="utf-8")
    assert "멈춤 측정: 처리 못 한 반환 1개, 0분(T002)" in journal
    assert not str(run_dir.tasks()["T001"].get("asked_at", "")).strip()


@pytest.mark.parametrize("point", ["점검 확인|R2 확인|없음", "알림|지나감|없음"])
def test_pa_main_lines_before_the_answer_do_not_measure(run_dir, point):
    make(run_dir, status="승인대기")
    run_script("screen", run_dir.path, "T001", "--save")
    p = run_script("task_set", run_dir.path, "T001", "--record", point)
    assert p.returncode == 0, p.output
    journal = run_dir.path / "journal.md"
    assert not journal.exists() or "멈춤 측정" not in journal.read_text(encoding="utf-8")
    assert str(run_dir.tasks()["T001"].get("asked_at", "")).startswith("20")


def test_ta_failed_measure_keeps_the_answer(run_dir, monkeypatch, capsys):
    import task_set
    make(run_dir, status="승인대기")
    run_script("screen", run_dir.path, "T001", "--save")

    def broken(*a):
        raise OSError("파일이 사라짐")
    monkeypatch.setattr(task_set, "stall_note", broken)
    rc = task_set.main(["task_set.py", str(run_dir.path), "T001", "--record", '되물음(이해)|무엇|"뭐죠"'])
    assert rc == 0
    assert "멈춤 측정 실패" in capsys.readouterr().out
    assert "뭐죠" in (run_dir.task_dir("T001") / "task.md").read_text(encoding="utf-8")


def test_ja_record_without_save_does_not_measure(run_dir):
    make(run_dir, status="승인대기")
    p = run_script("task_set", run_dir.path, "T001", "--record", '되물음(이해)|무엇|"뭐죠"')
    assert p.returncode == 0, p.output
    journal = run_dir.path / "journal.md"
    assert not journal.exists() or "멈춤 측정" not in journal.read_text(encoding="utf-8")


def test_cha_second_record_does_not_measure_twice(run_dir):
    make(run_dir, status="승인대기")
    run_script("screen", run_dir.path, "T001", "--save")
    run_script("task_set", run_dir.path, "T001", "--record", '되물음(이해)|무엇|"하나"')
    run_script("task_set", run_dir.path, "T001", "--record", '되물음(이해)|무엇|"둘"')
    assert (run_dir.path / "journal.md").read_text(encoding="utf-8").count("멈춤 측정") == 1


def test_ka_finished_task_is_not_counted(run_dir):
    make(run_dir, status="승인대기")
    make(run_dir, "T002", status="완료")
    run_script("screen", run_dir.path, "T001", "--save")
    time.sleep(1.1)
    (run_dir.task_dir("T002") / "result.md").write_text(RESULT + "\n", encoding="utf-8")
    run_script("task_set", run_dir.path, "T001", "--record", '되물음(이해)|무엇|"뭐죠"')
    assert "처리 못 한 반환 0개" in (run_dir.path / "journal.md").read_text(encoding="utf-8")


# 2026-11-17-tests 실행 T013(마무리)에 사람에게 보인 옛 꼴 화면(경계 보고 답 줄이 없음) 그대로, 경로만 가림. 사람 답 원문은
# `1 예, 2 아니오, 3가, 4가, 5나, 진행`이었고 메인이 `1 승인, 2 남김`으로 옮겨 기록했다(HB-37)
T013_SHOWN = r"""[wrap-up T013] 마무리
정하는 것: 이 상태로 넣어도 되는가
볼 곳: 정해 주실 것 5, 하실 일 4, 성질 붙은 항목 1 · 대기 중 1개
승인하면: 내보내기 명령을 실행합니다

■ 리뷰 자료
  전체 시험이 순차로 34분 걸리고 규칙과 검사가 따로 자라 하네스를 고치기 어려워서, 고친 결과를 main에 합칩니다. 이번 실행은 전체 시험을 병렬로 돌려 약 5분(순차 2023초, 병렬 316초대)으로 줄였고, 바뀐 파일에서 닿는 시험만 고르는 도구, 관문 훅 실패를 판정 상태와 패널에 남기는 처리, 항목 번호와 이름을 줍는 파서의 정리, 문서의 규칙과 스크립트 상수를 묶는 시험, 지난 세션 폴더에만 있던 목적 시험 준비 스크립트의 저장소 이관을 했습니다. 판본은 1.3.0 그대로 두고(판을 올리지 않음) 로컬 main에 앞감기로 합치기만 하며, origin push와 플러그인 설치는 하지 않습니다.

■ 마무리 리뷰
  ## 먼저 보실 것
  - 넣을 산출물: 승인 없이 들어감 1(아래 칸)
  - 끄기 | tests/py/test_purpose_setup.py:204 | +1/-0 | 이유: 적지 않음 | 대신 지키는 것: 없음 | T015
  ■ 실행 지도: 2026-11-17-tests 흐름 harness-tests 하나 | 결정 14줄 | task 24개(완료 22, 자체검증 1, 백로그 1) | 닫은 인수 기준 10 | 전체: {실행 폴더}\run-map.md
  ## 기준선
  - 기준 커밋: 6e08abb93c9ef01350a9832bd5135806d1769bab
  - T006(b520e8d)부터 claude plugin test . 기준선 158 pass(새 시험 2개), T016부터 159 pass.
  - 흐름 폴더 병렬(-n auto, 공용 venv + xdist 3.8.0): 7797 passed, 2 skipped, 0 failed, 316.83초 / claude plugin test . 156 pass (xjudge-baseline, baseline-run.md)
  - 2026-11-17 6e08abb(approval-1.3.0 = main): 공용 venv 순차 pytest `-q -p no:cacheprovider` 7797 passed, 2 skipped, 0 failed, 2023초(33분 43초) / `claude plugin test .` …
  - 2026-11-17 15:11:13 흐름 폴더 기준선 물을 실패 0 (baseline-run.md 실패 없음, xjudge-baseline·xjudge-baseline-r1)
  ## 넣을 산출물
  - 승인 없이 알림으로 지나감: docs/architecture/flows/harness-tests.md
  - 결정 기록: 병렬 전체 시험은 공용 venv의 pytest-xdist로 돌린다
  - 결정 기록: 시험 효율화 변경은 판을 올리지 않고 main에 합치기만 한다
  - 결정 기록: 사실 검사의 호스트 이름 끝 마디 목록은 일곱 개로 두고 마디 꼴 규칙만 더한다
  - 결정 기록: 흐름별 검증과 재검증에서 코드를 고치기로 한 범위
  - 승인 없이 들어감: docs/plugin-practices.md (표 밖)
    +- 묶는 시험은 `tests/py/test_rule_bindings.py`에 둔다. 문서에서 글자(틀 줄의 칸 이름과 갈래 값, 괄호 목록, 상한 낱말, 절 이름)를 꺼내 상수와 견주고, 틀을 채운 줄을 파서가 읽는지 본다. 시험 안에 문서 문장의 사본을 두지 않는다.
    -| 스크립트 동작 | 상태 전이, 화면, 판정 읽기 | `tests/py` 단위 시험 | 바꿀 때마다(닿는 것), 커밋 전(전체) |
    +| 스크립트 동작 | 상태 전이, 화면, 판정 읽기 | `tests/py` 단위 시험 | 바꿀 때마다(닿는 것: `python tests/py/select_tests.py --run`), 커밋 전(전체: `python -m pytest -q -p no:cacheprovider -n auto`) |
    -| 행동 회귀 | 사람이 판단 재료를 받는가 | 목적 시험(작성자→판정→화면→결과를 모르는 승인자, 정답지 대조) | 판을 낼 때, 모델이 바뀔 때 |
    +| 행동 회귀 | 사람이 판단 재료를 받는가 | 목적 시험(작성자→판정→화면→결과를 모르는 승인자, 정답지 대조). 준비 `tests/purpose/setup_task.py`, 지시문 틀 `tests/purpose/prompts.md`, 차례 `tests/purpose/README.md`. 자료와 정답지는 저장소 밖에 두고 경로로 넘긴다 | 판을 낼 때, 모델이 바뀔 때 |
    -| 규칙과 검사 한 곳 | 빈 곳(진단 5). 1.3.0 결함 대부분의 원인 |
    -| 행동 회귀 | 목적 시험을 처음 함. 준비 스크립트가 scratchpad에만 있어 다시 돌릴 수 없음 |
    +| 규칙과 검사 한 곳 | 판정 쪽은 묶음: 판정 파일 틀(짚음·주장-출처 대조·통과 못 한 기준), 하네스가 고칠 것 다섯, 즉시 질문 상한과 차례, 짚음 글 예산, 사실 파일의 상한과 절 이름. 화면 쪽도 묶음: 알림을 막는 성질, 경계 사이 kind의 알림(화면과 전이 관문), 글자 예산, 선택지 문장의 자리, 답 꼴, 전제 셋 이내(검사 `devflow_lib.PREMISE_CAP`). 둘 다 `tests/py/test_rule_bindings.py`. 묶는 시험이 없던 것이 1.3.0 결함 대부분의 원인이었다(진단 5) |
    +| 행동 회귀 | 목적 시험을 두 번 함(1.3.0). 준비 스크립트·지시문 틀·차례를 `tests/purpose/`에 옮겨 다시 돌릴 수 있음(준비 동작은 `tests/py/test_purpose_setup.py`). 옮긴 뒤 목적 시험 자체는 아직 돌리지 않음 |
    -| validate --strict | 통과. 디렉터리 기준 LICENSE 없음(2026-11-17 사용자 결정: 붙이지 않음, 디렉터리에 내지 않음), 아이콘 없음, 훅 모듈의 관문 훅 셋에 `.catch` 없음 |
    -| 피드백 일반화 | 1.3.0 목적 시험 수정 일부는 사례 그대로의 수정이었다(호스트 이름, 번호 줍기). 결함 수정으로는 맞지만, 같은 갈래(자유 글에서 번호·이름을 줍는 파서)가 두 번 나왔으므로 그 갈래를 한 번 정리할 때다 |
    +| validate --strict | 통과. 디렉터리 기준 LICENSE 없음(2026-11-17 사용자 결정: 붙이지 않음, 디렉터리에 내지 않음), 아이콘 없음 |
    +| 피드백 일반화 | 1.3.0 목적 시험 수정 일부는 사례 그대로의 수정이었다(호스트 이름, 번호 줍기). 결함 수정으로는 맞지만, 같은 갈래(자유 글에서 번호·이름을 줍는 파서)가 두 번 나왔으므로 그 갈래를 한 번 정리할 때다. 번호 줍기는 정리함: 「통과 못 한 기준」 항목 번호를 `devflow_lib.item_key` 하나가 꼴 표 `ITEM_HEADS`로 항목 머리에서만 읽고(재시도 범위와 화면이 같은 함수), 옛 판정 파일 꼴을 본뜬 표본으로 시험한다(`tests/py/test_item_key.py`). 이름 줍기도 정리함: 사실 검사가 이름으로 줍지 않는 꼴을 `judge_facts.NOT_IDENTIFIER_FORMS` 표 하나로 둔다(`tests/py/test_judge_facts.py`) |
  - 위험·미확인 목록: 9건
  - 테스트 지도: 더한 행 11, 지운 행 0, 연결을 못 읽은 줄 21
  ## 남은 확인 안 된 것
  - T002 훅 실패를 시험에서 일으킬 수 있는지 돌려 보지 않았습니다. [성질: 없음]
    - 대시보드 시험 엔진에서 `.catch` 등록, 패널 열기 거부, 도구 호출 훅 몸의 실패를 만들 수 있다고 타입 정의를 읽은 범위에서 봤습니다. 틀리면 그 부분은 행동 시험 대신 validate 출력으로만 닫습니다. 확인: 훅 실패 처리 작업이 시험을 돌릴 때.
  - T002 병렬에서 드물게 깨지는 시험이 다시 돌려도 없다고 가정합니다. [성질: 없음]
    - 설계 때 두 번은 깨짐이 없었습니다. 가장 오래 걸린 시험은 같은 초 안의 변경을 보는 시험입니다. 틀리면 그 시험의 원인을 고치는 일이 병렬 시험 작업에 더해집니다.
  - T002 옮긴 준비 스크립트가 실제 자료에서 끝까지 도는지 돌려 보지 않았습니다. [성질: 없음]
    - 옛 스크립트와 같은 동작이라 돈다고 봅니다. 확인: 목적 시험 이관 작업이 지난 목적 시험의 두 작업 자료로 돌릴 때.
  - T011 옮긴 스크립트로 목적 시험 전체(작성자·판정·화면·승인자)를 돌리지 않았습니다. 준비 단계까지만 확인했습니다. [성질: 없음]
    - 실제 자료로 T051과 T004를 준비하고 `board.py`가 종료 0이며 대상 task가 `진행`인 것까지 봤습니다. 지난 2회차 폴더와 비교하면 다른 곳은 지난 시험이 남긴 산출물, 판본(`1.3.0-dev.1` → `1.3.0`), 출력 경로뿐이었습니다. 그 뒤 단계는 판을 낼 때 사람이 돌립니다(설계 시험 표 예외 행).
  - T011 비공개 금지 낱말 검사는 환경 변수 `DEVFLOW_FORBIDDEN`이 없어 건너뛰었습니다(기준선의 skipped 2에 포함). 새 파일에 다른 프로젝트 이름을 쓰지 않았지만, 비공개 목록으로 대조하지는 않았습니다. [성질: 없음]
  - 나머지 12건(전체는 이 task의 unverified-list.md): T012 1 · 갈 곳 안 적힘 11
  ## 코드 확인
  - 사람이 코드로 본 곳 6, 남긴 곳 2
  - 남김(상한) T010 scripts/devflow_lib.py:1490
  - 남김(상한) T010 tests/py/test_rule_bindings.py:35
  ## 흐름 리뷰 뒤에 바뀐 것
  - [T014] 바뀐 작업 행 하나를 다시 썼습니다(설계 고친 판과 함께 승인되면 대기 중인 작업에 옮겨집니다). [성질: 없음]
    - 항목 번호 파서 정리(T007): 범위에서 판정 표 기준 칸의 지금 동작을 적은 괄호를 설계 문서와 같은 말로 바꾸고, `:398`은 `cell_key(cell) or cell`로 칸 글을 쓴다는 문장을 더했습니다. 판정 기준 7에 번호 없는 칸(`기준 성질`) 표본 하나를 더해, 새 함수 `screen.cell_key`(판정 표 첫 칸의 기준 이름을 읽는 함수)가 `None`을 돌려주고 판정불가 대상 행을 옮긴 줄이 지금과 같은지 시험이 단언하게 했습니다.
  - [T014] 그대로인 작업: 병렬 전체 시험(T004), 시험 고르기 장치(T005), 관문 훅 실패 처리(T006), 사실 검사 이름 줍기 정리(T008), 판정 쪽 규칙 묶음 시험(T009), 화면 쪽 규칙 묶음 시험(T010), 목적 시험 이관(T011), 흐름별 검증(T012), 마무리(T013). 바뀐 줄은 4.4절 한 줄이고, 이 작업들의 머리 파일은 4.4절·`cell_key`·`:398`을 읽지 않습니다. 결정 번호와 인수 기준은 바뀌지 않았습니다. [성질: 없음]
  - [T014] [사실] 원래 폴더 6e08abb의 `scripts/screen.py`를 열어 확인했습니다. `:319`는 `item_key(first) or ("기준" + first if first.isdigit() else None)`이라 그 밖의 칸은 열쇠가 없고, `:398`은 `item_key(cells[0]) or ("기준" + cells[0] if cells[0].isdigit() else cells[0])`이라 그 밖의 칸은 칸 글 그대로입니다. 고친 문장은 이 동작과 같습니다. [성질: 없음]
  - [T018] 목적 시험 준비의 git 환경 분리 (승인, 커밋 3cb94f4acc38b224e92a68c73669775d35153199) | 판단 4건 tests/purpose/setup_task.py:180, tests/purpose/setup_task.py:186, tests/py/test_purpose_setup.py:147
  - [T019] 변경 이력과 원칙 문서의 사실 고침 (승인, 커밋 14b8201e3bcc781dc5f269f854db1e7147128aae) | 판단 1건
  - [T022] 목적 시험 준비 시험의 확인 git 환경 고침 (알림, 커밋 981c6b70e80281cc9d32cd62ca4769ea90985398) | 판단 1건 tests/py/test_purpose_setup.py:160
  - [T023] 목적 시험 준비가 빼는 git 변수를 git 목록으로 넓힘 (알림, 커밋 22bb1e53dd3a88a6ac9846926511bc2dd48cdc55) | 판단 2건 tests/purpose/setup_task.py:52, tests/py/test_purpose_setup.py:178-184
  ## 시험 변화
  - 대리 확인 | AC-08(전체 pytest가 모으지 않음) | 본 것: 실제로 본 것: `tests/purpose/` 아래 `.py` 이름 꼴과 conftest 없음(`test_purpose_setup.py:231-234`) / 못 본 것: 못 본 것: pytest의 실제 수집. 판정 기준 5의 명령이 본다 | 이유: 적지 않음 | 대신 지키는 것: 없음 | T011
  - 기준선 추가 | recon.md 「기준선」 | - T006(b520e8d)부터 claude plugin test . 기준선 158 pass(새 시험 2개), T016부터 159 pass. | 이유: 적지 않음 | 대신 지키는 것: 없음 | 실행

■ 정해 주실 것 (5)
- [1] 원래 폴더 `{원래 폴더}`에서 아래 두 줄 명령을 실행해 흐름 브랜치를 로컬 main에 앞감기로 합칩니다 [성질: 없음]
  - 첫 줄은 원래 폴더가 꺼내 둔 브랜치를 approval-1.3.0에서 main으로 바꾼다. main과 approval-1.3.0은 둘 다 6e08abb라 꺼내도 파일 내용이 바뀌지 않는다. approval-1.3.0 브랜치는 6e08abb에 그대로 남아 main보다 뒤처진다.
  - 지금 상태: 원래 폴더의 작업 트리는 깨끗하다. 흐름 브랜치 `harness/tests/harness-tests`는 6e08abb에서 갈라진 선형 기록이고(커밋 15개, 변경 파일 24개) 앞감기가 된다. 합치기는 main이 꺼내져 있어야 하는데, 흐름 폴더는 별도 작업 폴더라 main은 다른 곳에 꺼내져 있지 않다.
  - 합치는 끝은 문서 커밋을 마친 흐름 브랜치의 끝이고, 그 끝이 최종 CI의 검증 commit이다. 앞감기가 안 되면 실행 전에 거부된다.

```cmd
git checkout main
git merge --ff-only harness/tests/harness-tests
```
- [2] [앞 일에서 짚음] 저장소 안 `_workspace/` 밖이라 거부할 때 문구가 사용자가 쓴 `--out` 대신 realpath로 푼 경로를 보인다(연결로 쓴 경로면 다른 글자가 나옴). 결과에 적히지 않았다
  독립 확인: 사람이 보는 문구나 동작이 바뀜
  고르면: 고치면 문구에 입력 경로가 그대로 나오고 판단은 같음 / 그대로 두면 연결 표기 입력에서 다른 경로가 보임
  앞 일: 코드 확인 고침: setup_task.py
  (예: 고침 / 아니오: 그대로 둠)
- [3] [앞 일에서 짚음] 「확인 안 된 것」(`result.md:22`)은 "흐름 끝 재검증(T012 자식)이 코드를 다시 읽습니다"라고 적었다. 그런데 재검증 T021의 범위는 "고친 지적 V-01~V-04 … 두 수정 커밋의 변경을 읽는다"이고, T021은 T018·T019에만 기대며 T016은 그 대상이 아니다. 실제 세션에서 확인하지 못한 일을 이어받는 task가 없다: (가) 「확인 안 된 것」의 넘길 곳을 고쳐, 실제 세션에서 줄이 사라지는지는 사람이 확인할 것(마무리 리뷰)으로 적음 / (나) T021의 범위와 기준에 T016의 변경을 더함
  독립 확인: 주장-출처, 고치는 길이 둘 이상
  고르면: (가) 실제 세션 확인을 사람이 맡고, 다른 task의 범위는 그대로다 / (나) T021의 머리 파일 범위가 늘어난다. 다만 재검증도 하위 에이전트라 실제 세션 화면을 열 수 없어, 같은 시험 엔진 확인을 한 번 더 하게 될 뿐이다
  추천 (가) 남은 확인은 실제 세션 화면이라 재검증 판정자가 볼 수 없다
  앞 일: 코드 확인 고침: common.ts tool.call 실패 줄
- [4] [앞 일에서 짚음] 새 시험이 "훅 안에서 돌아도" 버틴다고 적었지만(판단 :34, 시험 주석 :147), :159 `monkeypatch.undo()`가 처음에 지운 바깥 git 변수까지 되살립니다. 그래서 절대 경로 `GIT_INDEX_FILE`이 잡힌 환경(훅 안 `git commit -a`)에서는 확인용 git이 남의 색인을 읽어 이 시험이 거짓으로 실패합니다(바깥 색인은 그대로, 재현함): (가) `undo()` 대신 :156-157에서 준 두 변수만 `delenv`해 확인용 git도 변수 없이 부름 / (나) 시험은 그대로 두고 판단 문장만 고침
  독립 확인: 주장-출처, 원인이 코드에 있음
  고르면: (가) 훅 안 전체 시험에서도 이 시험이 통과, 시험 줄 한두 개가 바뀜 / (나) 훅에서 `-a` 커밋으로 전체 시험을 돌리면 이 시험 하나가 거짓 실패로 남음
  추천 (가) 주석이 말한 목적을 한 줄로 지키고 바깥 저장소에는 영향이 없음
  앞 일: 목적 시험 준비의 git 환경 분리
- [5] [앞 일에서 짚음] 변경 이력과 결과가 여덟 개를 "저장소 지정 환경 변수" 전부처럼 적었지만, git 문서 「The Git Repository」에는 `GIT_INDEX_VERSION`·`GIT_CEILING_DIRECTORIES`·`GIT_DISCOVERY_ACROSS_FILESYSTEM`·`GIT_DEFAULT_HASH`·`GIT_DEFAULT_REF_FORMAT`·`GIT_REFERENCE_BACKEND`가 더 있고, git이 저장소를 바꿀 때 지우는 목록(`git rev-parse --local-env-vars`)에는 `GIT_CONFIG_PARAMETERS`·`GIT_SHALLOW_FILE`·`GIT_GRAFT_FILE` 등 여덟이 더 있습니다. 이 가운데 사본 밖을 가리킬 수 있는 것은 `GIT_REFERENCE_BACKEND`(참조 저장 URI)입니다: (가) 목록은 여덟 그대로 두고 문장에 "여덟 개"임을 밝힘 / (나) 문서 절과 `--local-env-vars`를 합친 목록으로 넓힘
  독립 확인: 주장-출처, 고치는 길이 둘 이상
  고르면: (가) 실제 훅이 내보내는 변수(`GIT_INDEX_FILE`·`GIT_PREFIX`)는 막고, 바깥이 `GIT_REFERENCE_BACKEND`나 `git -c`로 지정한 경우는 남음 / (나) 그 경우까지 막지만 지적 V-01의 제안 밖으로 넓어지고 시험이 늘어남
  추천 (가) 관찰한 훅 환경에서 새는 변수가 없고 수정 task는 지적만 고치는 것이 정의(fix 7)
  앞 일: 목적 시험 준비의 git 환경 분리

■ 하실 일·허용 요청 (4)
- [6] 합친 뒤 지울 코드 폴더(메인이 실행을 닫을 때 지움, 이 실행에 끝나지 않은 배포 task 없음): `{코드 폴더}`(`git worktree`)
- [7] 합친 뒤 지울 브랜치: `harness/tests/harness-tests`(`git branch -d`. 합쳐졌을 때만)
- [8] 이 실행 중 받은 임시 권한: 없음(`decisions.md`와 승인 기록에 임시 권한이 없다)
- [9] 지우지 않는 것: `approval-1.3.0` 브랜치(이 실행이 만들지 않았다), 공용 venv `{공용 venv}`(pytest-xdist 3.8.0이 설치된 채 남는다)

■ 알릴 것 (12)
- [10] [사실] 고친 문서: 이 task가 코드 폴더에 새로 쓴 것은 `docs/decisions/0001~0004`(결정 기록 넷)와 `docs/operations/unverified.md`(확인하지 못한 것)이다. 앞 task들이 이미 고친 문서는 `CHANGELOG.md`(`1.3.0(이어서)` 행 아홉), `docs/plugin-practices.md`, `references/main/maintain.md`, `references/formats/screen-cells.md`, `references/formats/result-file.md`다. 새 문서와 아래 넣은 문서는 커밋 전이라 메인이 문서 커밋에 함께 넣는다.
- [11] [사실] README는 고치지 않았다. README에는 시험 명령, 병렬 시험, 시험 고르기, 목적 시험 이관을 설명한 문장이 없어(검색 결과 해당 낱말 0건) 이번 변경으로 틀려진 곳이 없다.
- [12] [사실] 프로젝트에 넣은 문서: `docs/architecture/flows/harness-tests.md`(설계 정본의 결정 기록과 기능 흐름도, 표의 말 "승인 없이 알림으로 지나감"), `docs/generated/test-map.md`(테스트 지도, 더한 행 11, 지운 행 0, 인수 기준과 잇지 못한 줄 21). 둘 다 커밋 전 변경이다.
- [13] [사실] 개발용 의존성에 `pytest-xdist==3.8.0`이 더해졌다. 공용 venv에는 이미 설치돼 있고, 새 환경에서는 `pip install -r requirements-dev.txt`가 필요하다. 마이그레이션, 서버 환경 변수, 외부 서비스 설정의 변경은 없다(선택 환경 변수 `DEVFLOW_FORBIDDEN`은 없으면 그 시험만 건너뛴다).
- [14] [사실] 다음 배포(판을 낼 때)에 확인할 것은 `docs/operations/unverified.md`와 본문 「배포 메모」에 모았다. 이 실행에 배포 task는 없다.
- [15] [사실] 설치본(플러그인 캐시 1.3.0)은 이 변경을 반영하지 않는다. 판본이 1.3.0 그대로라 설치해도 판본으로는 구분되지 않는다.
- [16] [사실] 설계 정본 `design\harness-tests.md:106`·`:108`이 "51개"·"27개"로 남았고 실제는 55개·28개(변경 이력 행과 같음)다. 끝난 task의 산출물이라 고치지 않았고 프로젝트에 넣은 흐름 문서에는 이 두 숫자가 들지 않는다(T019 알림).
- [17] [사실] 이 실행에서 모인 하네스 결함 후보(고치지 않고 백로그 목록에 올림): 판정 파일의 주장-출처 짝 수 거부가 두 번 반복됨(T001·T005), 코드 확인 카드가 안내하는 판단별 답 꼴을 `places.resolve`가 받지 못함(T012), `--place`가 판정자 「파일」 칸을 잘못 쪼갬(T012·T016), 판정 기준의 CHANGELOG 행 수 고정이 뒤 수정으로 깨짐(T018), sonnet 작성자의 결과 파일이 형식 밖(T017).
- [18] [하네스가 고칠 것] 결정 기록 0004의 정한 사람이 T012·T021 답만 적었는데, "화면은 전제를 질문 예산으로 잰다고 덧붙였다"는 T010 답 "1나"(2026-11-17 21:21:33)의 결정이다 (까닭: 주장-출처, 문서 어긋남)
- [19] [하네스가 고칠 것] 결정 기록 0004 「버린 길」 둘째 줄 "전제 300자는 문서만 고치는 길을 골랐다(T012 6가)"는 고른 길이라 버린 길이 아니다(버린 길은 코드로 재는 길) (까닭: 주장-출처, 문서 어긋남)
- [20] [하네스가 고칠 것] 「알릴 것」의 하네스 결함 후보는 다섯인데 본문 「백로그 목록」은 일곱이다(T016 짚음 둘, T014 하네스가 고칠 것 1이 알릴 것에 없음) (까닭: 빠진 줄)
- [21] 최종 CI는 소스를 시험했습니다. 빌드 결과물 자체를 시험한 것은 아닙니다. 빌드 설정과 환경 차이는 배포 뒤 확인이 잡습니다

■ 정한 것 (10)
- [22] ◇ 판을 올리지 않고 로컬 main에 합치기만 한다(판본 1.3.0 그대로, push·설치 없음) | 앞 답: 2026-11-17 "4. 나"
- [23] ◇ 병렬 전체 시험은 공용 venv의 pytest-xdist로 돌린다(이 task의 시험 명령) | 앞 답: 2026-11-17 "1. 가"
- [24] ✔ 내보내기는 병합 방식(`git merge --ff-only`, 프로젝트 설정 「내보내기 방식」) | 버림: PR 방식, 병합 커밋
- [25] ✔ 결정 기록은 결정마다 한 파일로 네 개 | 버림: 한 파일에 모음, 관례 결정까지 기록
- [26] ✔ README는 고치지 않음 | 버림: 시험 명령과 도구 소개를 README에 더함
- [27] ✔ 생성 명령은 제안하지 않음 | 버림: 도면을 코드에서 뽑는 명령을 새로 만들어 제안
- [28] ✔ 결정 기록 0001 근거(2023초·316.83초·같은 결과, 저장소 읽기만)에 인용이 없다. 원천은 run-map.md 기준선 줄과 design/harness-tests.md:47이고 내용은 맞다 (그대로 둠: 주장-출처, 원천 대조 맞음·프로젝트 문서라 인용 불요)
- [29] ✔ 결정 기록 0002 근거(validate·details·목적 시험을 돌리지 않음, tests/purpose 들어감)에 인용이 없다. docs/plugin-practices.md:52-56과 변경 파일 목록에 맞다 (그대로 둠: 주장-출처, 원천 대조 맞음·프로젝트 문서라 인용 불요)
- [30] ✔ 결정 기록 0003 근거(md 5,921개 전후 같음)에 인용이 없다. T008 result.md:22와 맞다 (그대로 둠: 주장-출처, 원천 대조 맞음·프로젝트 문서라 인용 불요)
- [31] ✔ 결정 기록 0004 근거(변수 목록을 --local-env-vars에 맞춤)에 인용이 없다. tests/purpose/setup_task.py:50-56과 이 기계 목록 15개에 맞다 (그대로 둠: 주장-출처, 원천 대조 맞음·프로젝트 문서라 인용 불요)

■ 확인 안 된 것 (0)
- 없음 (판정불가로 남은 인수 기준이 없다. 각 task의 「확인 안 된 것」 23건은 본문 「배포 메모」에 모두 옮겼다)

■ 건수만 (1): 통과한 인수 기준 10개(AC-01~AC-10), 백로그 task 1개(T020) · 확인 방법: retry_diff: tasks/T013/result.md 바뀜 +5 -8, 코드 없음(코드 폴더에 쓰지 않는 kind) · 실행함 1 · 원본 전부 대조 6(2~6은 앞 판정 옮

counts: n_decide=5 n_todo=4 n_notify=11 n_unverified=0 n_children=0
알림 조건: 미충족(wrap-up는 알림으로 지나가지 않는다)
"""


def test_old_screen_takes_yes_no_and_progress_as_written():
    """HB-37: 옛 화면에서도 선택지 글자가 없는 항목에 `예`·`아니오`를 값 그대로 받고(D-15), `진행`은 전체 승인이다."""
    import screen
    lines = screen.resolve_answer(T013_SHOWN, "T013", "1 예, 2 아니오, 3가, 4가, 5나, 진행")
    assert lines is not None
    assert lines[0].startswith("항목 1: 예 | 원래 폴더 ") and lines[1].startswith("항목 2: 아니오 | [앞 일에서 짚음] ")
    assert [l.split(" | ")[0] for l in lines[2:]] == ["항목 3: 가", "항목 4: 가", "항목 5: 나", "전체: 승인"]


@pytest.mark.parametrize("text", ["3 예", "5 아니오", "예", "아니오", "1 예, 진행, 승인", "진행, 단 밤에"])
def test_old_screen_asks_again_for_yes_no_where_letters_are(text):
    """대조: 선택지 글자가 있는 항목(옛 화면은 항목 본문 전체에서 글자를 봄)과 항목을 말하지 않은 예·아니오는 되묻는다."""
    import screen
    assert screen.resolve_answer(T013_SHOWN, "T013", text) is None
