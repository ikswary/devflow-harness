"""승인 화면의 자식 목록 셈과 수치 대조.

`screen.build()`의 `facts`·`claims` 값과 `screen.main()` 출력의 `셈:`·`! 수치 대조`·`! 같은 제목 자식 행` 줄을 본다.
칸 내용·`counts:`·알림 조건이 대조 때문에 바뀌지 않는지는 대조를 끈 같은 결과와 견주어 본다.
"""
import pytest

import screen

JUDGE_OK = ("판정자: rjudge-T001 2026-10-15 10:00:00\n\n## 통과 못 한 기준\n- 없음\n\n## 판정 표\n"
            "| 기준 | 판정 | 근거 |\n|---|---|---|\n| 1 | 통과 | 읽음 |\n")

# 자식 행 19개, kind 6종
KINDS_19 = (["implementation"] * 9 + ["fix"] * 4 + ["design"] * 2 + ["flow-verify"] * 2 + ["change"] + ["wrap-up"])


def row(title, kind, option=None):
    lines = ["### 자식: " + title, "- kind: " + kind, "- flow: s1", "- depends_on: ", "- difficulty: 일반"]
    if option:
        lines.append("- option: " + option)
    lines += ["- 한 줄: " + title + "을 한다", "#### 범위", "- " + title, "#### 판정 기준", "1. " + title + "이 있다",
              "#### 건드릴 파일", "- src/a.py"]
    return "\n".join(lines) + "\n\n"


def result(tid, rows, notify="- 없음", criterion="흐름 단위", unverified="- 없음"):
    return ("# {tid} 결과\n\n## 승인 화면\n### 정해 주실 것\n- 없음\n### 하실 일·허용 요청\n- 없음\n### 알릴 것\n{notify}\n"
            "### 답하신 것의 반영\n- 없음\n### 확인 안 된 것\n{unverified}\n### 건수만\n- 설계대로 한 작업 2\n\n"
            "## 스스로 줄임\n없음\n\n## 본문\n본문\n\n## 자식 목록\n나눈 기준: {criterion}\n\n{rows}"
            "## 규약 추가\n없음\n").format(tid=tid, notify=notify, unverified=unverified, criterion=criterion,
                                       rows="".join(rows))


def rows_19():
    return [row("작업 {:02d}".format(i + 1), k) for i, k in enumerate(KINDS_19)]


def mixed_rows():
    """안 행과 [백로그] 행이 섞인 7행. 비교 집합의 여섯 값이 행·종류 모두 서로 다르다:
    전체 7행/7종, [백로그] 뺀 6행/6종, 안 가 3행/3종, 안 나 5행/5종, 안 가 [백로그] 뺀 2행/2종, 안 나 [백로그] 뺀 4행/4종.
    안 없는 행([백로그] 공통 재검증)이 안마다의 값에 들어가야 안 가 3·안 나 5가 나온다."""
    return [row("가 화면", "implementation", "수정안/가"),
            row("가 수정", "fix", "수정안/가"),
            row("나 설계", "design", "수정안/나"),
            row("나 정본", "change", "수정안/나"),
            row("나 검증", "flow-verify", "수정안/나"),
            row("나 마무리", "wrap-up", "수정안/나"),
            row("[백로그] 공통 재검증", "reverify")]


# 부분 집합마다 그 값만 맞는 주장(다른 부분 집합의 값과 겹치지 않음). (부분 집합, 칸 항목, 행, 종류)
SUBSET_CLAIMS = [
    ("전체", "- 전체는 자식 7행/7종입니다", 7, 7),
    ("[백로그] 뺀 수", "- [백로그]를 빼면 자식 6행/6종", 6, 6),
    ("안 가", "- 안 가를 고르면 자식 3행·3종", 3, 3),
    ("안 나", "- 안 나를 고르면 자식 5행,5종", 5, 5),
    ("안 가 [백로그] 뺀 수", "- 안 가에서 백로그를 빼면 자식 2행 2종", 2, 2),
    ("안 나 [백로그] 뺀 수", "- 안 나에서 백로그를 빼면 자식 4행/4종", 4, 4),
]


def make(run_dir, tid, text, **meta):
    meta.setdefault("status", "승인대기")
    run_dir.task(tid, "자식 나누기", **meta)
    run_dir.result(tid, text)
    run_dir.judge(tid, JUDGE_OK)


def main_lines(run_dir, tid, capsys):
    rc = screen.main(["screen.py", str(run_dir), tid])
    out = capsys.readouterr().out
    assert rc == 0, out
    return out.splitlines()


def warn_lines(lines):
    return [l for l in lines if l.startswith("! 수치 대조")]


# --- 기준 2: 19행/6종 표본 ----------------------------------------------------------------------------------

def test_t015_sample_wrong_claim_gives_row_and_kind_warnings(run_dir, capsys):
    make(run_dir, "T001", result("T001", rows_19(), notify="- 흐름별로 자식 20행/7종으로 나눴습니다"))

    b = screen.build(str(run_dir), "T001")
    lines = main_lines(run_dir, "T001", capsys)

    assert b["facts"]["rows"] == 19 and b["facts"]["n_kinds"] == 6
    assert [(c[0], c[1], c[2], c[3], c[4]) for c in b["claims"]] == [
        ("알릴 것", "자식 20행/7종", "행", 20, 19), ("알릴 것", "자식 20행/7종", "종류", 7, 6)]
    assert "셈: 자식 행 19 ([백로그] 0) · 종류 6 (implementation 9, fix 4, design 2, flow-verify 2, change 1, wrap-up 1)" in lines
    assert warn_lines(lines) == [
        "! 수치 대조: 알릴 것 「자식 20행/7종」 — 셈 행 19(비교 집합 19) " + screen.CLAIM_NOTE,
        "! 수치 대조: 알릴 것 「자식 20행/7종」 — 셈 종류 6(비교 집합 6) " + screen.CLAIM_NOTE]
    assert lines.index(warn_lines(lines)[-1]) < next(i for i, l in enumerate(lines) if l.startswith("counts:"))


def test_t015_sample_right_claim_gives_no_warning(run_dir, capsys):
    make(run_dir, "T001", result("T001", rows_19(), notify="- 흐름별로 자식 19행/6종으로 나눴습니다"))

    b = screen.build(str(run_dir), "T001")
    lines = main_lines(run_dir, "T001", capsys)

    assert b["claims"] == []
    assert warn_lines(lines) == []
    assert any(l.startswith("셈: 자식 행 19 ") for l in lines)   # 같은 표본에서 셈은 돌았다(양성 대조)


# --- 기준 3: 안 행과 [백로그] 행, 꼴 밖 숫자 --------------------------------------------------------------------

def test_mixed_rows_facts_and_comparison_sets(run_dir):
    make(run_dir, "T001", result("T001", mixed_rows()))

    f = screen.build(str(run_dir), "T001")["facts"]

    assert (f["rows"], f["backlog"], f["options"], f["n_kinds"]) == (7, 1, {"수정안/가": 3, "수정안/나": 5}, 7)
    assert (f["row_set"], f["kind_set"]) == ([2, 3, 4, 5, 6, 7], [2, 3, 4, 5, 6, 7])
    assert screen.facts_line(f) == ("셈: 자식 행 7 ([백로그] 1, 안 수정안/가: 3, 안 수정안/나: 5) · 종류 7 "
                                    "(implementation 1, fix 1, design 1, change 1, flow-verify 1, wrap-up 1, reverify 1)")


@pytest.mark.parametrize("subset,item,rows,kinds", SUBSET_CLAIMS, ids=[c[0] for c in SUBSET_CLAIMS])
def test_mixed_rows_claim_of_each_subset_gives_no_warning(run_dir, subset, item, rows, kinds):
    # 이 주장은 이 부분 집합의 값으로만 맞는다. 그 부분 집합을 셈에서 빼면 경고가 된다(변이 확인 지시 7·8)
    make(run_dir, "T001", result("T001", mixed_rows(), notify=item))

    assert [(w, v) for w, v, _ in screen.unit_claims(item)] == [("행", rows), ("종류", kinds)]   # 주장을 뽑았다
    assert screen.build(str(run_dir), "T001")["claims"] == []


def test_mixed_rows_row_forms_one_and_two_give_no_warning(run_dir):
    notify = "\n".join([
        "- 안 가를 고르면 자식 task 3개",       # 꼴 1, 안 가(안 없는 행 + 그 안이 든 행)
        "- 안 나를 고르면 5개 자식 행",         # 꼴 2, 안 나
        "- [백로그]를 빼면 자식 행 6개",        # 꼴 1, [백로그] 뺀 수
    ])
    make(run_dir, "T001", result("T001", mixed_rows(), notify=notify, criterion="안 나에서 백로그를 빼면 자식 4행"))

    b = screen.build(str(run_dir), "T001")

    assert [v for _, v, _ in screen.unit_claims(notify)] == [3, 5, 6]   # 주장을 뽑았다
    assert b["claims"] == []


def test_numbers_outside_the_three_forms_give_no_warning(run_dir):
    # 이 실행 결과에서 본 거짓 후보 꼴. 53·1·9는 행 비교 집합 {2, …, 7}에 없어 잡히면 경고가 된다
    notify = "\n".join(["- 「자식 목록」 첫 줄 53을 고쳤습니다", "- 자식 행 T001의 판정 기준을 다시 읽었습니다",
                        "- 다시 읽은 task 9개"])
    make(run_dir, "T001", result("T001", mixed_rows(), notify=notify))

    assert screen.build(str(run_dir), "T001")["claims"] == []


def test_mixed_rows_claim_outside_comparison_set_is_caught(run_dir):
    # 위 시험들의 양성 대조: 같은 7행에서 비교 집합 밖 값(8행, 1종, 10개)은 칸과 나눈 기준 줄 모두에서 잡힌다
    make(run_dir, "T001", result("T001", mixed_rows(), unverified="- 자식 8행/1종으로 봤습니다",
                                 criterion="자식 10개로 나눔"))

    claims = screen.build(str(run_dir), "T001")["claims"]

    assert [(c[0], c[2], c[3], c[5]) for c in claims] == [
        ("확인 안 된 것", "행", 8, (2, 3, 4, 5, 6, 7)), ("확인 안 된 것", "종류", 1, (2, 3, 4, 5, 6, 7)),
        ("나눈 기준", "행", 10, (2, 3, 4, 5, 6, 7))]


def test_same_title_rows_are_counted_apart_and_warned(run_dir, capsys):
    make(run_dir, "T001", result("T001", [row("가입 화면", "implementation"), row("가입 화면", "implementation"),
                                         row("가입 API", "implementation")]))

    lines = main_lines(run_dir, "T001", capsys)

    assert any(l.startswith("셈: 자식 행 3 ") for l in lines)
    assert "! 같은 제목 자식 행 가입 화면 2" in lines
    assert not any(l.startswith("! 같은 제목 자식 행 가입 API") for l in lines)


# --- 기준 4: 칸·counts:·알림 조건은 그대로 -----------------------------------------------------------------------

def cells_counts_notify(lines):
    """출력에서 대조 줄(셈:, ! 수치 대조, ! 같은 제목 자식 행)을 뺀 칸 내용·counts: 줄·알림 조건 줄."""
    keep = [l for l in lines if not l.startswith(("셈:", "! 수치 대조", "! 같은 제목 자식 행"))]
    start = next(i for i, l in enumerate(keep) if l.startswith("■ 정해 주실 것"))
    end = next(i for i, l in enumerate(keep) if l.startswith("■ 만들 task"))
    counts = [l for l in keep if l.startswith("counts:")]
    notify = [l for l in keep if l.startswith("알림 조건")]
    return keep[start:end], counts, notify


def test_cells_counts_and_notify_are_the_same_without_the_check(run_dir, capsys, monkeypatch):
    make(run_dir, "T001", result("T001", rows_19(), notify="- 흐름별로 자식 20행/7종으로 나눴습니다"))

    on = screen.build(str(run_dir), "T001")
    on_lines = main_lines(run_dir, "T001", capsys)
    monkeypatch.setattr(screen, "count_claims", lambda *a: [])
    off = screen.build(str(run_dir), "T001")
    off_lines = main_lines(run_dir, "T001", capsys)

    assert len(on["claims"]) == 2 and len(warn_lines(on_lines)) == 2 and warn_lines(off_lines) == []
    assert (on["screen"], on["counts"], on["notify_ok"]) == (off["screen"], off["counts"], off["notify_ok"])
    assert cells_counts_notify(on_lines) == cells_counts_notify(off_lines)
    assert cells_counts_notify(on_lines)[1] == ["counts: n_decide=0 n_todo=0 n_notify=1 n_unverified=0 n_children=19"]


def test_code_task_mismatch_still_notifies(run_dir, capsys):
    make(run_dir, "T001", result("T001", [row("목록 화면", "implementation"), row("상세 화면", "implementation")],
                                 notify="- 자식 5행으로 나눴습니다"),
         kind="implementation", block="구현", status="자체검증")

    b = screen.build(str(run_dir), "T001")
    lines = main_lines(run_dir, "T001", capsys)

    assert [(c[2], c[3], c[4]) for c in b["claims"]] == [("행", 5, 2)]
    assert b["notify_ok"] is True
    assert len(warn_lines(lines)) == 1
    assert ("알림 조건(정해 주실 것·하실 일이 비고 통과 못 한 기준·판정불가 없음, 형식 문제 없음): 충족 — "
            "알림 줄에 붙일 것: 알릴 것 1, 확인 안 된 것 0") in lines
