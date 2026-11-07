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
