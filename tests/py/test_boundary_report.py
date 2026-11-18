"""1.3.0 D: 경계 보고와 경계 사이(구현 설계 2절 D, 7판 규칙 1절·4.1).

- 등록표 `boundary`: report(경계 보고를 내는 kind) / between(경계 사이: 알림 한 줄, 물을 것만 즉시 질문) / stage(단계 kind의 명령 승인).
- 경계 목록은 7판 4.1 표 그대로(정할 것 U4). 구현→검증 경계는 구현 묶음 보고라 구현 task는 경계 사이다.
"""
from datetime import datetime

import devflow_lib as lib
import kinds
import screen
from conftest import run_script

V130 = {"started_version": "1.3.0", "rules": "2"}


def result(decide="- 없음", notify="- 없음", unverified="- 없음"):
    return ("# 결과\n\n## 승인 화면\n### 전제\n- 없음\n### 정해 주실 것\n{}\n### 하실 일·허용 요청\n- 없음\n### 알릴 것\n{}\n"
            "### 정한 것\n- 없음\n### 확인 안 된 것\n{}\n### 건수만\n- 없음\n").format(decide, notify, unverified)


def judged(run_dir, points="- 없음"):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    run_dir.judge("T001", "판정자: rjudge-T001 {}\n\n## 통과 못 한 기준\n- 없음\n\n## 판정 표\n| 기준 | 판정 | 근거 |\n|---|---|---|\n"
                          "| 1 | 통과 | 읽음 |\n\n## 짚음\n{}\n\n## 주장-출처 대조\n- 없음\n".format(now, points))
    run_dir.task_dir("T001").joinpath(lib.FACTS_FILE).write_text("# 사실\n", encoding="utf-8")


def build(run_dir, kind, text, points="- 없음", block="설계"):
    run_dir.task("T001", "일", kind=kind, block=block, status="자체검증", **V130)
    run_dir.result("T001", text)
    judged(run_dir, points)
    return screen.build(str(run_dir.path), "T001")


def ask(text, why, breaks="있음 지금 깨짐"):
    return "- {} | 갈래: 물을 것 | 까닭: {} | 깨짐: {} | 근거: a:1\n".format(text, why, breaks)


def test_boundary_list_follows_the_rules():
    assert kinds.BOUNDARY_KINDS == {"question", "req-overview", "brief", "req-detail", "root-cause", "design",
                                    "flow-verify", "deploy-plan"}
    assert {n for n, k in kinds.KINDS.items() if k.boundary == "stage"} == set(kinds.STAGE_KINDS)
    assert kinds.BETWEEN_KINDS == set(kinds.KINDS) - kinds.BOUNDARY_KINDS - set(kinds.STAGE_KINDS)
    assert {"implementation", "fix", "ui-design", "infra-design", "change", "reverify"} <= kinds.BETWEEN_KINDS



# ---------------------------------------------------------------- D2 알림 판단과 짚음의 자리

def test_between_task_with_only_notes_passes_by_notice(run_dir):
    b = build(run_dir, "ui-design", result(notify="- 버튼 색을 규약대로", unverified="- 실제 기기에서 보지 못함"))
    assert b["notify_ok"] is True


def test_between_task_with_a_question_waits(run_dir):
    b = build(run_dir, "ui-design", result(decide="- (가) 위 / (나) 아래 [성질: 없음]"))
    assert b["notify_ok"] is False


def test_breaking_points_become_at_most_two_questions_between(run_dir):
    points = ask("요금이 는다", "비용") + ask("권한 검사", "보안") + ask("이름", "그 밖") + ask("나중 일", "범위", breaks="없음")
    b = build(run_dir, "ui-design", result(), points)
    decide = b["screen"]["정해 주실 것"]
    assert "[독립 확인이 짚음] 요금이 는다" in decide and "[독립 확인이 짚음] 권한 검사" in decide
    assert "이름" not in decide and "나중 일" not in decide
    assert "[다음 경계에서 물음] 이름" in b["screen"]["알릴 것"] and "[다음 경계에서 물음] 나중 일" in b["screen"]["알릴 것"]
    assert b["counts"]["n_decide"] == 2 and b["notify_ok"] is False


def test_boundary_task_asks_every_point(run_dir):
    points = ask("요금이 는다", "비용") + ask("권한 검사", "보안") + ask("이름", "그 밖") + ask("나중 일", "범위", breaks="없음")
    b = build(run_dir, "design", result(), points)
    assert b["counts"]["n_decide"] == 4


def test_harness_fixes_and_kept_points_do_not_ask(run_dir):
    points = ("- 두 문서의 값이 다름 | 갈래: 하네스가 고칠 것 | 까닭: 문서 어긋남 | 근거: a:1\n"
              "- 이름이 길다 | 갈래: 그대로 둠 | 까닭: 관례 | 근거: a:2\n")
    b = build(run_dir, "ui-design", result(), points)
    assert "[하네스가 고칠 것] 두 문서의 값이 다름" in b["screen"]["알릴 것"]
    assert "- ✔ 이름이 길다 (그대로 둠: 관례)" in b["screen"]["정한 것"]
    assert b["notify_ok"] is True


def test_old_tasks_keep_the_old_notice_rule(run_dir):
    run_dir.task("T001", "일", kind="ui-design", block="설계", status="자체검증", started_version="1.2.1", rules="2")
    run_dir.result("T001", result().replace("### 전제\n- 없음\n", "").replace("### 정한 것", "### 답하신 것의 반영"))
    judged(run_dir)
    assert screen.build(str(run_dir.path), "T001")["notify_ok"] is False   # ui-design은 옛 규칙에서 승인만



# ---------------------------------------------------------------- D4 화면 꼴

DESIGN = """# 결과

## 승인 화면
### 리뷰 자료
첫 사진이 느린 문제를 사진 저장 위치를 바꿔 푼다.
### 전제
- 전1 사진 저장소 계정을 만들 수 있는지 해 보시고 알려 주세요 | 막아 세움: 예 | 답: 됨/안 됨/지금 해 보겠음 | 기대는 것: 사진 옮기기
### 정해 주실 것
- 배포 때 DB 이전을 어떻게 할지: (가) 따로 올림 / (나) 같이 올림 ← 추천 [성질: 앞 판단과 다름] | 바뀌는 앞 답: 2026-11-12 "DB는 늘 같이 올려"
  효과 비교: (가) 5분 / (나) 9분
### 하실 일·허용 요청
- 없음
### 알릴 것
- 썸네일 폭을 320으로 [성질: 없음]
- 외부 저장소 요금이 든다 [성질: 비용]
### 정한 것
- ◇ 사진은 원본 그대로 둔다 | 앞 답: 2026-11-10 "원본은 건드리지 마"
- ✔ 썸네일은 서버에서 만든다 | 버림: 브라우저에서 만듦
### 확인 안 된 것
- 실제 휴대폰 망에서 재지 못함
### 건수만
- 관례 3
"""


def shown(run_dir, kind="design", text=DESIGN, points="- 없음"):
    run_dir.task("T001", "사진 저장 설계", kind=kind, block="설계", status="승인대기", **V130)
    run_dir.result("T001", text)
    judged(run_dir, points)
    p = run_script("screen", run_dir.path, "T001", "--save")
    assert p.returncode == 0, p.output
    return p.stdout


def test_boundary_report_order_and_groups(run_dir):
    out = shown(run_dir, points="- 두 문서의 값이 다름 | 갈래: 하네스가 고칠 것 | 까닭: 문서 어긋남 | 근거: a:1\n")
    lines = out.splitlines()
    assert lines[0] == "[설계 → 만들기] 사진 저장 설계" and lines[1] == report_no_ask()
    order = [next(i for i, l in enumerate(lines) if l.startswith(head))
             for head in ("실행 위치", "물을 것 2", "하네스가 고칠 것 1", "정한 것 2", "남긴 것", "■ 정해 주실 것 (2)", "답  진행", "펼침: ")]
    assert order == sorted(order)
    assert ' ↺ 배포 때 DB 이전을 어떻게 할지: (가) 따로 올림 / (나) 같이 올림 (앞 답: 2026-11-12 "DB는 늘 같이 올려") → 질문 2' in out
    assert lines[2].startswith("이 승인에는 돈·계정·바깥 시스템에 닿는 것이 있습니다: 외부 저장소 요금이 든다")
    assert "풀려는 문제" in out and "첫 사진이 느린 문제를 사진 저장 위치를 바꿔 푼다." in out
    assert "← 추천" not in out.split("■ 정해 주실 것")[0]          # 묶음 줄에는 추천을 결론처럼 쓰지 않는다
    assert ' 1 ◇ 사진은 원본 그대로 둔다 (2026-11-10 "원본은 건드리지 마")' in out
    assert " - 외부 저장소 요금이 든다 (비용)" in out and "썸네일 폭" not in out.split("■ 정해 주실 것")[0]
    assert "  답: 2가 / 2나 / 2 확인 먼저 / 2 펼쳐" in out
    assert "■ 전제" not in out and "■ 알릴 것" not in out   # 그 밖의 칸은 펼침에만


def report_no_ask():
    import report
    return report.NO_ASK


def test_new_screen_answers(run_dir):
    shown(run_dir)
    def answer(text):
        return run_script("screen", run_dir.path, "T001", "--answer", text)
    ok = answer("전1 됨, 2가, 진행")
    assert ok.returncode == 0 and "전제: 전1 됨" in ok.output and "항목 2: 가" in ok.output and "전체: 진행" in ok.output, ok.output
    cond = answer("전1 됨, 2나, 진행, 단 배포는 밤에")
    assert cond.returncode == 0 and "배포는 밤에" in cond.output, cond.output
    redo = answer("결정 1 다시")
    assert redo.returncode == 0 and "결정 1 다시: ◇ 사진은 원본" in redo.output, redo.output
    assert answer("2 확인 먼저").returncode == 0
    assert answer("결정 9 다시").returncode == 3
    assert answer("진행, 멈춤").returncode == 3
    assert answer("2다").returncode == 3


def test_old_screen_takes_progress_as_approval_but_not_other_new_answers(run_dir):
    """HB-37: 옛 화면의 `진행`은 전체 승인이다(1.3.0까지는 되물음, 기대값 변경). 그 밖의 새 화면 답은 그대로 되묻는다."""
    run_dir.task("T001", "설계", kind="design", block="설계", status="승인대기", started_version="1.2.1", rules="2")
    run_dir.result("T001", DESIGN.replace("### 전제\n- 전1 사진 저장소 계정을 만들 수 있는지 해 보시고 알려 주세요 | 막아 세움: 예 | 답: 됨/안 됨/지금 해 보겠음 | 기대는 것: 사진 옮기기\n", "")
                   .replace("### 정한 것", "### 답하신 것의 반영"))
    judged(run_dir)
    assert run_script("screen", run_dir.path, "T001", "--save").returncode == 0
    go = run_script("screen", run_dir.path, "T001", "--answer", "진행")
    assert go.returncode == 0 and "전체: 승인" in go.stdout and "전체: 진행" not in go.stdout, go.output
    for text in ("멈춤", "1 확인 먼저", "1 펼쳐", "진행, 단 밤에", "진행, 승인", "1 진행"):
        assert run_script("screen", run_dir.path, "T001", "--answer", text).returncode == 3, text


POINT_WITH_LETTER = ask("질문의 지금 값은 앞 실행 마무리가 같은 전체 검증을 한 번 더 돈다고 했지만 판정 시점의 기록은 다릅니다. "
                        "질문의 지금 값과 근거를 실제로 고치고, 이 답이 (나)와 같은 방향이라는 점을 적어야 합니다",
                        "주장-출처, 사실과 어긋남", "있음 앞 실행 마무리가 이미 줄인 검증으로 돎")


def test_point_without_ways_takes_yes_even_with_a_letter_in_its_text(run_dir):
    """T002 질문 3 꼴(경로 가림): 고치는 길이 없는 짚음의 본문 `(나)`는 선택지가 아니다. 답 줄은 예·아니오이고 `3 예`가 풀린다."""
    out = shown(run_dir, points=POINT_WITH_LETTER)
    # DESIGN 화면: 질문 1은 전1(전제), 질문 2가 (가)/(나) 결정, 짚음이 질문 3
    assert "- [3] [독립 확인이 짚음] 질문의 지금 값은" in out and "이 답이 （나）와 같은 방향" in out, out
    assert "  답: 3 예 / 3 아니오 / 3 확인 먼저 / 3 펼쳐" in out and "3나" not in out
    alone = answer(run_dir, "3 예")
    assert alone.returncode == 0 and "항목 3: 예 | " in alone.stdout, alone.output
    whole = answer(run_dir, "전1 됨, 2가, 3 예, 진행")
    assert whole.returncode == 0 and "항목 3: 예 | " in whole.stdout and "전체: 진행" in whole.stdout, whole.output
    assert answer(run_dir, "3나").returncode == 3   # 대조: 본문의 글자는 고를 수 없다


def test_notice_is_one_line(run_dir):
    out = shown(run_dir, kind="ui-design", text=result(notify="- 버튼 색을 규약대로"))
    human = out.split("\n\ncounts:")[0].strip().splitlines()
    assert human[0].startswith("알림: [설계 중] 사진 저장 설계 — ") and human[1].startswith("펼침: ") and len(human) == 2


def test_instant_question_between(run_dir):
    out = shown(run_dir, kind="ui-design", text=result(decide="- 버튼을 어디에 둘지: (가) 위 / (나) 아래 [성질: 없음]"))
    assert out.startswith("[설계 중] 사진 저장 설계\n") and "물을 것" not in out and "■ 정해 주실 것 (1)" in out
    assert "  답: 1가 / 1나 / 1 확인 먼저 / 1 펼쳐" in out and "답  질문의 답 / 멈춤" in out


PLAN = """# 결과

## 승인 화면
### 전제
- 없음
### 정해 주실 것
- dev에 배포할지: (가) 배포 / (나) 미룸
  ```cmd
  npx wrangler deploy --env dev
  npx wrangler d1 execute app --command "DROP TABLE old_photos"
  ```
### 하실 일·허용 요청
- 없음
### 알릴 것
- 없음
### 정한 것
- 없음
### 확인 안 된 것
- 없음
### 건수만
- 없음

## 본문
### 되돌리기
```cmd
npx wrangler rollback --env dev
```
"""


def test_command_table_comes_before_questions_and_raw_lines_last(run_dir):
    out = shown(run_dir, kind="deploy-plan", text=PLAN)
    lines = out.split("\n\ncounts:")[0].splitlines()
    table = lines.index("명령 표   (승인하실 것은 이 표의 줄입니다. 명령 원문은 맨 끝에 있습니다)")
    question = next(i for i, l in enumerate(lines) if l.startswith("■ 정해 주실 것"))
    raw = lines.index("■ 명령 원문")
    assert table < question < raw and raw > next(i for i, l in enumerate(lines) if l.startswith("답  진행"))
    assert " 1 | npx wrangler deploy --env dev | 쓰기 | 되돌리기 명령 있음" in lines
    assert any(l.startswith(" 2 | ") and l.endswith("| 쓰기 | 어려움") for l in lines)
    assert any(l.startswith("되돌릴 수 없는 것  2번 줄(npx wrangler d1 execute") for l in lines)
    assert "```cmd" not in "\n".join(lines[question:raw])   # 질문 안에는 명령 원문을 싣지 않는다


def test_sheet_shows_the_same_lines(run_dir):
    import visual
    shown(run_dir)
    t = run_dir.tasks()["T001"]
    page = "\n".join(visual._head_blocks(str(run_dir.path), t, lambda x: x))
    assert '<pre class="report">[설계 → 만들기] 사진 저장 설계' in page and "물을 것 2" in page


def test_collect_counts_the_new_forms(run_dir):
    import collect
    shown(run_dir)
    head = run_dir.task_dir("T001") / "task.md"
    head.write_text(head.read_text(encoding="utf-8").replace("## 승인 기록\n", '## 승인 기록\n- 2026-11-17 10:00:00 | 승인 | 승인 | 원문: "2나, 진행"\n'),
                    encoding="utf-8")
    line = collect.v130_line(run_dir.tasks())
    assert line.startswith("- 1.3.0 화면: 경계 보고 1 · 즉시 질문 0 · 알림 0; 질문 2개") and "추천대로 답함 1/1" in line



# ---------------------------------------------------------------- D 리뷰(사람 관점)로 고친 것

def answer(run_dir, text):
    return run_script("screen", run_dir.path, "T001", "--answer", text)


def test_point_question_offers_the_ways_and_hides_reason_marks(run_dir):
    points = ("- 실패를 원격 DB 실패로 보일 곳 | 갈래: 물을 것 | 까닭: (a) (b) | 길: (가) 서버에서 가름 / (나) 문구만 넓힘 | "
              "결과: (가) Worker를 고침 / (나) 운영자가 연결 실패와 기능 결함을 가를 수 없음 | 추천: (가) 문구만으로는 원인을 못 가름 | "
              "깨짐: 있음 지금 틀린 문구 | 근거: a:1\n"
              "- 썸네일 대체 글이 빔 | 갈래: 물을 것 | 까닭: (b) | 깨짐: 있음 화면 읽기 | 근거: a:2\n")
    out = shown(run_dir, kind="ui-design", text=result(), points=points)
    assert "- [1] [독립 확인이 짚음] 실패를 원격 DB 실패로 보일 곳: (가) 서버에서 가름 / (나) 문구만 넓힘" in out
    assert "(a)" not in out and "(b)" not in out and "독립 확인: 고치는 길이 둘 이상 사람이 보는 문구나 동작이 바뀜" in out
    assert "  고르면: (가) Worker를 고침 / (나) 운영자가" in out and "  추천 (가) 문구만으로는 원인을 못 가름" in out
    assert "  답: 1가 / 1나 / 1 확인 먼저 / 1 펼쳐" in out and "  답: 2 예 / 2 아니오 / 2 확인 먼저 / 2 펼쳐" in out
    assert answer(run_dir, "1가, 2 예").returncode == 0
    assert answer(run_dir, "1 예").returncode == 3          # 선택지가 있는 질문에는 예/아니오를 받지 않는다


def test_ways_are_required_when_the_reason_is_two_ways(run_dir):
    t = shown(run_dir, kind="ui-design", text=result(), points="- x | 갈래: 물을 것 | 까닭: (a) | 깨짐: 없음 | 근거: a:1\n")
    assert "(a)(고치는 길이 둘 이상)인데" in t


def test_quoted_letters_are_not_choices(run_dir):
    decide = '- 옵션을 없앨지: (가) 없앰 / (나) 받고 무시 [성질: 앞 판단과 다름] | 바뀌는 앞 답: 2026-10-29 "(다) 운영에도 허용"\n'
    out = shown(run_dir, kind="ui-design", text=result(decide=decide))
    assert "  답: 1가 / 1나 / 1 확인 먼저 / 1 펼쳐" in out
    assert answer(run_dir, "1다").returncode == 3


def test_progress_asks_again_while_questions_are_open(run_dir):
    shown(run_dir)
    assert answer(run_dir, "진행").returncode == 3
    assert answer(run_dir, "2가, 진행").returncode == 3                     # 전제 전1에 답이 없다
    assert answer(run_dir, "전1 됨, 2 확인 먼저, 진행").returncode == 3      # 확인 먼저는 답이 아니다
    assert answer(run_dir, "전1 됨, 진행, 단 밤에, 2가").returncode == 3     # 진행 뒤의 답은 조건 글에 먹힌다
    assert answer(run_dir, "전1 됨, 2가, 진행").returncode == 0


def test_deadline_and_assumption_premises_reach_the_person(run_dir):
    text = DESIGN.replace("### 전제\n", "### 전제\n- 전2 이미지 호스팅 연장 | 막아 세움: 아니오 | 기한: 2026-11-22 사진 옮기기 전\n"
                                       "- 전3 사진은 하루 100장 이하인가요 | 막아 세움: 아니오 | 모르면: 100장 이하\n")
    out = shown(run_dir, text=text)
    assert " - [기한] 2026-11-22 사진 옮기기 전: 이미지 호스팅 연장" in out
    assert "[가정] 전3 사진은 하루 100장 이하인가요" in out and " 전 전3 사진은 하루 100장 이하인가요" in out
    assert answer(run_dir, "전1 됨, 전3 예, 3가, 진행").returncode == 0, answer(run_dir, "전1 됨, 전3 예, 3가, 진행").output


def test_point_against_an_earlier_answer_is_marked_changed(run_dir):
    points = "- 연결 수 앞 답을 보이기만 함으로 읽음 | 갈래: 물을 것 | 까닭: (d) | 깨짐: 있음 상한 없음 | 근거: a:1\n"
    out = shown(run_dir, text=result(), points=points)
    assert " ↺ 연결 수 앞 답을 보이기만 함으로 읽음 → 질문 1" in out


def test_carried_points_become_numbered_questions_in_the_next_report(run_dir):
    run_dir.task("T009", "사진 목록 손봄", kind="ui-design", block="설계", status="완료", approval_mode="승인",
                 approved="2099-01-01 00:00:00", **V130)
    run_dir.judge("T009", "판정자: rjudge-T009 2099-01-01 00:00:00\n\n## 통과 못 한 기준\n- 없음\n\n## 짚음\n"
                          "- 다른 화면과 여백이 다름 | 갈래: 물을 것 | 까닭: (b) | 깨짐: 없음 | 근거: a:1\n\n## 주장-출처 대조\n- 없음\n")
    out = shown(run_dir, text=result())
    assert "[앞 일에서 짚음] 다른 화면과 여백이 다름" in out and "  앞 일: 사진 목록 손봄" in out
    assert " ! 다른 화면과 여백이 다름 → 질문 1" in out and "진행, 단" not in out.split("■ 정해 주실 것")[0]


def test_big_growth_asks_to_attach_or_split(run_dir):
    run_dir.task("T050", "요구사항", kind="req-overview", status="완료", approval_mode="승인",
                 approved="2026-11-10 10:00:00", created="2026-11-10 09:00:00")
    run_dir.task("T051", "설계", kind="design", status="완료", parent="T050", created="2026-11-10 10:01:00")
    for i in range(4):
        run_dir.task("T06{}".format(i), "새 일", kind="implementation", status="대기", parent="T051", created="2026-11-12 09:00:00")
    out = shown(run_dir, text=result())
    assert "늘어난 일을 이번 실행에 붙일지 따로 뗄지: (가) 이번 실행에 붙임 / (나) 따로 뗌" in out
    assert "「설계」에서 나온 일 +4개가 처음 계획 3개보다 큽니다" in out


def test_author_command_notes_fill_the_table(run_dir):
    plan = PLAN.replace("  ```cmd\n", "  줄 2: 옛 사진 표 지움 | 되돌림: 안 됨(백업 없음)\n  ```cmd\n", 1)
    out = shown(run_dir, kind="deploy-plan", text=plan)
    assert " 2 | 옛 사진 표 지움 | 쓰기 | 안 됨(백업 없음)" in out
    assert "되돌릴 수 없는 것  2번 줄(옛 사진 표 지움)" in out


def test_between_task_with_a_cost_note_does_not_pass_by_notice(run_dir):
    b = build(run_dir, "infra-design", result(notify="- 저장소 요금이 월 5달러 [성질: 비용]"))
    assert b["notify_ok"] is False
    b = build(run_dir, "infra-design", result(notify="- 이름을 규약대로 [성질: 없음]"))
    assert b["notify_ok"] is True


def test_option_texts_leave_the_question_and_probe_label_is_plain(run_dir):
    """목적 시험 T051: 정본에 넣을 선택지 문장은 질문 예산에 넣지 않고 펼침에 둔다. `[탐침]` 머리표는 사람의 말로."""
    decide = ("- 풀러일 때 멈출지: (가) 멈춤 ← 추천 / (나) 계속 [성질: 위험]\n"
              "  - 선택지 (가)의 문장: 정본 6.2 \"풀러일 때 멈춘다\"\n  - 선택지 (나)의 문장: 정본 6.2 \"계속한다\"\n"
              "  - 효과 비교: (가) 원격 쓰기 0 / (나) 배포 뒤 실패\n")
    out = shown(run_dir, text=result(decide=decide, unverified="- [탐침] 직결인지 읽지 않음\n"))
    asked = out.split("■ 정해 주실 것", 1)[1].split("답  ", 1)[0]
    assert "의 문장:" not in asked and "효과 비교" in asked and "정본에 넣을 문장은 펼침에" in asked
    assert "[직접 확인] 직결인지" in out and "[탐침]" not in out.split("■ 정해 주실 것", 1)[0]
    shown_doc = run_dir.task_dir("T001").joinpath("result.md").read_text(encoding="utf-8")
    assert "선택지 (가)의 문장:" in shown_doc   # 결과 파일(project_docs가 읽는 곳)에는 그대로


def test_between_notice_passes_the_status_gate(run_dir):
    """진단(목적 시험 뒤): 화면은 1.3.0 ui-design을 알림으로 보내는데 전이 관문은 옛 NOTIFY_KINDS만 봐서 거부했다."""
    assert "ui-design" in kinds.BETWEEN_KINDS and "ui-design" not in kinds.NOTIFY_KINDS
    b = build(run_dir, "ui-design", result(notify="- 버튼 색을 규약대로", unverified="- 실제 기기에서 보지 못함"))
    assert b["notify_ok"] is True
    p = run_script("task_set", run_dir.path, "T001", "--status", "완료", "--record", "알림|지나감|")
    assert p.returncode == 0, p.output
    assert run_dir.tasks()["T001"]["status"] == "완료"


def test_old_ui_design_still_cannot_pass_by_notice(run_dir):
    run_dir.task("T001", "일", kind="ui-design", block="설계", status="자체검증", started_version="1.2.1", rules="2")
    run_dir.result("T001", result(notify="- 버튼 색을 규약대로"))
    judged(run_dir)
    p = run_script("task_set", run_dir.path, "T001", "--status", "완료", "--record", "알림|지나감|")
    assert p.returncode != 0 and "알림으로 지나가지 않는다" in p.output



def _grown(run_dir):
    run_dir.task("T050", "요구사항", kind="req-overview", status="완료", approval_mode="승인",
                 approved="2026-11-10 10:00:00", created="2026-11-10 09:00:00")
    run_dir.task("T051", "설계", kind="design", status="완료", parent="T050", created="2026-11-10 10:01:00")
    for i in range(4):
        run_dir.task("T06{}".format(i), "새 일", kind="implementation", status="대기", parent="T051", created="2026-11-12 09:00:00")


def test_growth_question_without_author_material_warns_the_main(run_dir):
    """목적 시험 T051: 스크립트가 만든 붙일까 뗄까 질문은 재료가 없어 승인자가 '확인 먼저'로 답했다. 메인이 작성자에게 쓰게 한다."""
    _grown(run_dir)
    out = shown(run_dir, text=result())
    assert "[늘어남] 늘어난 일을 이번 실행에 붙일지" in out and "! 늘어남 질문 없음" in out


def test_author_growth_question_replaces_the_fallback(run_dir):
    _grown(run_dir)
    decide = ("- [늘어남] 사진 수정을 내려면 배포 검사부터 고쳐야 해서 일이 늘었습니다: (가) 이번 실행에 붙임 ← 추천 / (나) 따로 뗌\n"
              "  - (가) 검사를 고친 뒤 사진 수정과 함께 dev에 나갑니다 / (나) 사진 수정은 지금 검사로 먼저 나가고 검사는 다음 실행으로\n")
    out = shown(run_dir, text=result(decide=decide))
    assert "사진 수정을 내려면 배포 검사부터" in out
    assert "하네스가 만든 질문" not in out and "! 늘어남 질문 없음" not in out
    assert out.count("[늘어남]") >= 1 and "늘어난 일을 이번 실행에 붙일지 따로 뗄지" not in out


# ---------------------------------------------------------------- 커밋한 코드 task의 즉시 질문 (HB-50 나머지, 설계 harness-defects 5절 B3, AC-05, D-09)

def committed_instant(run_dir, commit):
    """1.3.1에 시작해 커밋한 뒤 묻는 구현 T001과, 같은 흐름에서 승인 요청 뒤에 시작한 T002."""
    run_dir.task("T001", "커밋한 구현", kind="implementation", block="구현", status="승인대기", flow="s1", commit=commit,
                 started="2026-11-18 10:00:00", approval_requested="2026-11-18 11:00:00",
                 started_version="1.3.1", rules="2")
    run_dir.result("T001", result(decide="- 오류 문구를 어디에 둘지: (가) 위 / (나) 아래 [성질: 없음]"))
    judged(run_dir)
    run_dir.task("T002", "뒤에 시작한 구현", kind="implementation", block="구현", status="진행", flow="s1",
                 started="2026-11-18 11:30:00")
    p = run_script("screen", run_dir.path, "T001")
    assert p.returncode == 0, p.output
    lines = p.stdout.splitlines()
    assert lines[0] == "[구현 중] 커밋한 구현", p.stdout   # 새 화면의 즉시 질문이다(양성 대조)
    return lines


def test_committed_code_task_instant_question_shows_commit_lines(run_dir):
    lines = committed_instant(run_dir, "abc1234def5678")
    assert screen.COMMITTED_HINT.format("abc1234") in lines
    assert screen.COMMITTED_ON.format("T002") in lines


def test_uncommitted_code_task_instant_question_has_no_commit_lines(run_dir):
    lines = committed_instant(run_dir, "")
    assert not [l for l in lines if l.startswith((screen.COMMITTED_HINT.split("{}")[0], screen.COMMITTED_ON.split("{}")[0]))]
