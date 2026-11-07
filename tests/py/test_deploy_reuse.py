"""배포 계획 재사용: 항목별 절차서 저장, 항목별 기계 판정, 작성자 몫 조립, 승인 화면, 측정.

1.2.0부터 시작한 실행에만 적용한다. 첫 계획은 작성자가 `고정`으로 표시한 항목만 남긴다. 근거가 바뀐 항목만 다시 쓰고,
처음부터 쓰는 것은 절차서가 없거나 손상된 경우, 환경을 읽지 못한 경우, 사람이 지시한 경우뿐이다. 명령은 접지 않는다."""
import json
import re
import subprocess

import pytest

from conftest import RunDir, run_script, write
import delegation
import deploy_reuse
import devflow_lib
import exec as execmod
import screen
import test_deploy_identity as ident

NEW = {"started_version": "1.2.0-dev.1", "rules": "2"}
OLD = {"started_version": "1.1.1", "rules": "2"}
GIT_ID = ["-c", "user.name=dryrun", "-c", "user.email=dryrun@example.invalid", "-c", "commit.gpgsign=false"]
PASS_RUN = "판정자: xjudge-T011 2026-10-15 10:00:00\n\n## 통과 못 한 기준\n- 없음\n"
MEMO_OK = "## 본문\n### 배포 메모\n- 배포 전 확인: 예시 값이 있음\n- 미룬 실물 확인: 메일함을 본다\n"
FIXED_MARKS = "- 명령 1~3: 읽기\n- 명령 4: 쓰기\n- 명령 5: 쓰기\n- 명령 6: 쓰기\n- 되돌리기 1: 쓰기\n"


def git(cwd, *args):
    return subprocess.run(["git", *GIT_ID, *args], cwd=str(cwd), check=True, capture_output=True,
                          text=True, encoding="utf-8").stdout.strip()


def commit_file(repo, path, text, message="변경"):
    write(repo / path, text)
    git(repo, "add", "-A")
    git(repo, "commit", "-m", message)
    return git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(workspace):
    r = workspace / "project"
    r.mkdir()
    git(r, "init", "-q", "-b", "dev")
    write(r / "package.json", "{}\n")
    write(r / "docs" / "deploy.md", "# 배포\n")
    write(r / "docs" / "guide.md", "# 안내\n")
    write(r / "docs" / "checks.md", "# 확인\n")
    write(r / "tools" / "deploy" / "run.sh", "echo 올림\n")
    write(r / "src" / "app.js", "1\n")
    write(r / "wrangler.jsonc", "{}\n")
    git(r, "add", "-A")
    git(r, "commit", "-m", "처음")
    return r


def settings(workspace):
    write(workspace / devflow_lib.PROJECT_SETTINGS,
          "# 설정\n\n## 경로 목록\n- 화면 경로: 없음\n- 인프라 경로: wrangler.jsonc, db/migrations/**\n- 문서 경로: docs/**\n")


def bash_path(p):
    s = str(p).replace("\\", "/")
    m = re.match(r"^([A-Za-z]):/(.*)$", s)
    return "/{}/{}".format(m.group(1).lower(), m.group(2)) if m else s


def set_run(run_dir, workspace, integration, base="dev"):
    """배포 폴더는 시험 저장소이고 원래 폴더는 다른 경로다(같으면 뜻이 둘인 값이다)."""
    text = (run_dir.path / "run.md").read_text(encoding="utf-8")
    head = "project: {}\nintegration_dir: {}\nbase_branch: {}\n".format(workspace / "original", integration, base)
    write(run_dir.path / "run.md", text.replace("---\n", "---\n" + head, 1))


def plan_lines(folder, commit, run_path, wrap="T009"):
    f = bash_path(folder)
    return [
        "cd {} && test \"$(git rev-parse HEAD)\" = {}".format(f, commit),
        "cd {} && test -z \"$(git status --porcelain)\"".format(f),
        "grep -n \"검증 commit\" {}/tasks/{}/judge-run.md".format(bash_path(run_path), wrap),
        "cd {} && ./tools/deploy/run.sh".format(f),
        "[사용자 실행] npm run lock",
        "[유지 뒤] git -C /d/somewhere push origin main",
    ]


def plan_result(lines, undo, title="T010 배포 계획", marks=FIXED_MARKS):
    fence = "\n".join("  " + x for x in lines)
    return ("# {} 결과\n\n## 승인 화면\n### 정해 주실 것\n- **[되돌릴 수 없는 단계 포함] 명령을 정해 주세요.** 첫 자원 만들기는 되돌릴 수 없음.\n  ```cmd\n{}\n  ```\n\n"
            "### 하실 일·허용 요청\n- 없음\n\n### 알릴 것\n- 올릴 커밋\n\n### 답하신 것의 반영\n- 없음\n\n"
            "### 확인 안 된 것\n- 없음\n\n### 건수만\n- 명령 {}줄\n\n"
            "## 본문\n### 사전 조건\n앞 환경 T110의 값을 봅니다.\n| # | 항목 | 줄 |\n|---|---|---|\n| 1 | [고정] HEAD가 올릴 커밋 | 1번째 줄 |\n"
            "| 2 | [고정] 잠금 값이 있음 | `docs/checks.md` |\n| 3 | 이번만 보는 값 | `docs/guide.md` |\n\n"
            "### 명령 목록과 근거\n- 4번 줄: `docs/deploy.md` 1절, `tools/deploy/run.sh`\n\n"
            "### 고정 항목\n{}\n"
            "### 배포 뒤 확인\n실행 판정이 돌립니다.\n1. [고정] 사이트 헤더를 읽는다(`docs/checks.md`).\n2. AC-1을 닫는 화면을 본다.\n"
            "3. [고정] 접수 POST 쓰기 확인을 한다(`docs/guide.md`).\n\n"
            "### 되돌리기\n도구가 스스로 되돌린다.\n```cmd\n{}\n```\n\n### 배포 뒤 적을 문서\n없음\n"
            ).format(title, fence, len(lines), marks, "\n".join(undo))


def freeze_file(d, point, lines):
    write(d / "approved-cmds-{}.md".format(point), "# 승인된 명령\n\n" + "".join("{}. {}\n".format(i, x) for i, x in enumerate(lines, 1))
          + "\n해시: {}\n얼린 시각: 2026-10-15 10:00:00\n".format(execmod.digest(lines)))


def finished_run(workspace, repo, name="run-a", commit=None, env="dev", outcome="유지", judge=PASS_RUN,
                 meta=NEW, status="완료", lines=None, marks=FIXED_MARKS, undo=None, mut=None):
    """지난 실행: 마무리 T009, 계획 T010, 유지로 끝난 실행 T011."""
    settings(workspace)
    commit = commit or git(repo, "rev-parse", "HEAD")
    r = RunDir(workspace / name)
    set_run(r, workspace, repo)
    r.task("T009", "마무리", kind="wrap-up", block="마무리", status="완료", stage="끝", exported_commit=commit, **meta)
    r.result("T009", MEMO_OK)
    lines = lines or plan_lines(repo, commit, r.path)
    undo = undo or ["cd {} && npx rollback".format(bash_path(repo))]
    r.task("T010", "배포 계획: {}".format(env), kind="deploy-plan", block="배포", status="완료", parent="T009",
           depends_on=["T009"], split_criterion="환경 {}, 시점 지금".format(env), **meta)
    text = plan_result(lines, undo, marks=marks)
    r.result("T010", mut(text) if mut else text)
    r.task("T011", "배포 실행: {}".format(env), kind="deploy-exec", block="배포", status=status, stage="끝", parent="T010",
           deploy_outcome=outcome, deployed_commit=commit, **meta)
    d = r.task_dir("T011")
    write(d / "judge-run.md", judge)
    freeze_file(d, "실행승인", lines)
    freeze_file(d, "되돌림", undo)
    return r


def next_run(workspace, repo, commit=None, name="run-b", env="dev", memo=MEMO_OK, meta=NEW):
    """다음 실행: 마무리 T020, 진행 중인 계획 T021."""
    commit = commit or git(repo, "rev-parse", "HEAD")
    r = RunDir(workspace / name)
    set_run(r, workspace, repo)
    r.task("T020", "마무리", kind="wrap-up", block="마무리", status="완료", stage="끝", exported_commit=commit, **meta)
    r.result("T020", memo)
    r.task("T021", "배포 계획: {}".format(env), kind="deploy-plan", block="배포", status="진행", parent="T020",
           depends_on=["T020"], split_criterion="환경 {}, 시점 지금".format(env), **meta)
    return r


def save(r, tid="T011"):
    return deploy_reuse.save(str(r), r.tasks()[tid])


def decide(r, tid="T021"):
    return deploy_reuse.decide(str(r), r.tasks()[tid])


def stored(r, env="dev"):
    return deploy_reuse.parse_procedure(devflow_lib.read_text(deploy_reuse.procedure_path(str(r), env)))


def item_blocks(r, env="dev"):
    """절차서의 항목 {제목: 그 항목의 글자 그대로}."""
    _, body = stored(r, env)
    return devflow_lib.sections(body["항목"], level=3)


def stored_items(r, env="dev"):
    return {x["id"]: x for x in deploy_reuse.parse_items(stored(r, env)[1]["항목"])}


def flagged(d):
    return [x["id"] for x in d["items"] if x["status"] == deploy_reuse.REWRITE]


def by_id(d, iid):
    return next(x for x in d["items"] if x["id"] == iid)


OWN = ("## 올릴 커밋\n{commit}\n\n## 되돌릴 수 없는 단계\n없음\n\n## 배포 전 확인\n- 예시 값이 있음\n\n## 배포 뒤 확인\n- AC-9: 화면을 본다\n\n"
       "## 미룬 실물 확인\n- 메일함을 본다\n\n## 배포 뒤 적을 문서\n없음\n\n{extra}")


def composed(workspace, repo, extra="", prior=None, path="src/app.js", **kwargs):
    """유지로 끝난 실행 뒤 커밋을 하나 더 하고, 다음 실행의 작성자 몫까지 조립한다. (실행, 새 커밋)."""
    a = prior or finished_run(workspace, repo, **kwargs)
    assert save(a)[0]
    new = commit_file(repo, path, "바뀜\n")
    b = next_run(workspace, repo, new)
    assert decide(b)["decision"] == deploy_reuse.REUSE
    write(b.task_dir("T021") / deploy_reuse.OWN_FILE, OWN.format(commit=new, extra=extra))
    rc, msg = deploy_reuse.compose(str(b), "T021")
    assert rc == 0, msg
    return b, new


def rewrite_block(iid, *lines):
    return "### {}\n{}\n".format(iid, "\n".join(lines))


def flagged_run(workspace, repo, path="docs/deploy.md"):
    a = finished_run(workspace, repo)
    save(a)
    new = commit_file(repo, path, "바뀜\n")
    b = next_run(workspace, repo, new)
    decide(b)
    return b, new


def compose_with(b, new, extra):
    write(b.task_dir("T021") / deploy_reuse.OWN_FILE, OWN.format(commit=new, extra=extra))
    return deploy_reuse.compose(str(b), "T021")


def new_run_line(repo, tail=" --new"):
    return "cd {} && ./tools/deploy/run.sh{}".format(bash_path(repo), tail)


def run_exec(b, tid="T021", new=None, exec_id="T022"):
    d = b.task_dir(tid)
    lines = devflow_lib.cmd_lines(devflow_lib.decide_cell(str(d)))
    b.task(exec_id, "배포 실행: dev", kind="deploy-exec", block="배포", status="완료", stage="끝", parent=tid,
           deploy_outcome="유지", deployed_commit=new, **NEW)
    e = b.task_dir(exec_id)
    write(e / "judge-run.md", PASS_RUN)
    freeze_file(e, "실행승인", lines)
    freeze_file(e, "되돌림", devflow_lib.cmd_lines(execmod.heading_section(devflow_lib.read_text(d / "result.md"), "되돌리기")))
    return deploy_reuse.save(str(b), b.tasks()[exec_id])


# ---------------------------------------------------------------- 저장: 표시한 항목만

def test_save_replaces_run_values_with_places(workspace, repo):
    a = finished_run(workspace, repo)
    commit = git(repo, "rev-parse", "HEAD")
    ok, msg = save(a)
    assert ok, msg
    assert deploy_reuse.procedure_path(str(a), "dev").replace("\\", "/").endswith("policies/deploy/dev.md")
    head, body = stored(a)
    assert head["saved_commit"] == commit
    fixed = body["항목"]
    assert commit not in fixed and "T009" not in fixed and "run-a" not in fixed and bash_path(repo) not in fixed
    assert "{{올릴 커밋}}" in fixed and "{{배포 폴더" in fixed and "{{마무리 task}}" in fixed and "{{실행 폴더" in fixed


def test_only_marked_items_are_saved(workspace, repo):
    # 표시가 없으면 이번 실행 몫이다: 일회성 마이그레이션과 앞 task 이야기가 남지 않는다
    commit = commit_file(repo, "db/migrations/0012_backfill.sql", "update t set a=1;\n")
    a = finished_run(workspace, repo, commit=commit)
    lines = plan_lines(repo, commit, a.path) + ["psql \"$DB\" -f db/migrations/0012_backfill.sql"]
    freeze_file(a.task_dir("T011"), "실행승인", lines)
    ok, msg = save(a)
    assert ok, msg
    text = devflow_lib.read_text(deploy_reuse.procedure_path(str(a), "dev"))
    assert "0012_backfill" not in text and "T110" not in text and "이번만 보는 값" not in text and "실행 판정이 돌립니다" not in text
    assert "도구가 스스로 되돌린다" not in text and "AC-1" not in text
    assert "[고정]" not in text   # 표지는 남기지 않는다
    assert "접수 POST" in text and "HEAD가" in text


def test_plan_with_no_marks_is_not_saved(workspace, repo):
    a = finished_run(workspace, repo, marks="- 없음\n", mut=lambda s: s.replace("[고정] ", ""))
    ok, msg = save(a)
    assert not ok and "고정" in msg
    assert not (workspace / "policies" / "deploy" / "dev.md").exists()


def test_marked_row_without_marked_commands_is_not_a_procedure(workspace, repo):
    a = finished_run(workspace, repo, marks="- 없음\n")
    ok, msg = save(a)
    assert not ok and "명령" in msg


def test_every_item_is_bound_to_its_own_evidence(workspace, repo):
    a = finished_run(workspace, repo)
    save(a)
    items = stored_items(a)
    blob = lambda name: git(repo, "rev-parse", "HEAD:" + name)
    assert items["C4"]["evidence"] == {"docs/deploy.md": blob("docs/deploy.md"), "tools/deploy/run.sh": blob("tools/deploy/run.sh")}
    assert items["C5"]["evidence"] == {"package.json": blob("package.json")}   # npm 줄
    assert items["R1"]["evidence"] == {"package.json": blob("package.json")}   # npx 줄
    # 작성자가 읽기로 표시한 줄과 git 줄은 파일에 기대지 않는다. 명령을 가리키는 사전 조건은 그 명령의 근거를 따른다
    assert (items["C1"]["basis"], items["C6"]["basis"]) == (deploy_reuse.BASIS_NONE, deploy_reuse.BASIS_NONE)
    assert (items["C1"]["mode"], items["C4"]["mode"]) == (deploy_reuse.READ, deploy_reuse.WRITE)
    assert items["P1"]["basis"] == deploy_reuse.BASIS_NONE
    assert items["P2"]["evidence"] == {"docs/checks.md": blob("docs/checks.md")}


def test_unmarked_mode_is_a_write(workspace, repo):
    a = finished_run(workspace, repo, marks="- 명령 1~6\n- 되돌리기 1\n")
    assert save(a)[0]
    items = stored_items(a)
    assert items["C1"]["mode"] == deploy_reuse.WRITE and items["R1"]["mode"] == deploy_reuse.WRITE


@pytest.mark.parametrize("kw", [{"outcome": "되돌림"}, {"outcome": "보류"}, {"outcome": ""},
                                {"status": "보류"},
                                {"judge": "판정자: x\n\n## 통과 못 한 기준\n- 기준 2: 실패\n"}])
def test_failed_or_reverted_deploy_is_not_saved(workspace, repo, kw):
    a = finished_run(workspace, repo, **kw)
    ok, msg = save(a)
    assert not ok and msg
    assert not (workspace / "policies" / "deploy" / "dev.md").exists()


def test_old_run_does_not_save(workspace, repo):
    a = finished_run(workspace, repo, meta=OLD)
    assert not save(a)[0]
    assert not (workspace / "policies" / "deploy" / "dev.md").exists()


def test_marked_line_with_a_stale_value_must_be_rewritten(workspace, repo):
    first = git(repo, "rev-parse", "HEAD")
    second = commit_file(repo, "src/app.js", "2\n")
    third = commit_file(repo, "src/app.js", "3\n")
    a = finished_run(workspace, repo, commit=third, marks=FIXED_MARKS + "- 명령 7~8: 읽기\n")
    lines = plan_lines(repo, third, a.path) + ["git diff {} {}".format(first, second), "grep x {}/tasks/T777/x.sql".format(bash_path(a.path))]
    freeze_file(a.task_dir("T011"), "실행승인", lines)
    ok, msg = save(a)
    assert ok, msg
    new = commit_file(repo, "src/app.js", "4\n")
    d = decide(next_run(workspace, repo, new))
    assert d["decision"] == deploy_reuse.REUSE
    assert flagged(d) == ["C7", "C8"]
    assert by_id(d, "C8")["why"] == deploy_reuse.WHY_OTHER and "T777" in by_id(d, "C8")["detail"]


@pytest.mark.parametrize("text", ["앞 환경 T110의 값", "T077의 경과", "T110 값", "(T115)"])
def test_task_id_with_a_particle_is_a_stale_value(text):
    # B11: 한글 조사가 붙어도 task id다
    assert deploy_reuse.generalize(text, {})[1] != []


@pytest.mark.parametrize("text", ["PT110의 값", "T110A", "T110-x", "XT1234"])
def test_longer_word_is_not_a_task_id(text):
    assert deploy_reuse.generalize(text, {})[1] == []


def test_marked_row_with_a_task_id_and_particle_must_be_rewritten(workspace, repo):
    a = finished_run(workspace, repo, mut=lambda s: s.replace("| 2 | [고정] 잠금 값이 있음 | `docs/checks.md` |", "| 2 | [고정] 앞 환경 T110의 값을 본다 | `docs/checks.md` |"))
    assert save(a)[0]
    b = next_run(workspace, repo)
    d = decide(b)
    assert "P2" in flagged(d) and "T110" in by_id(d, "P2")["detail"]
    new = git(repo, "rev-parse", "HEAD")
    rc, msg = compose_with(b, new, "## 다시 쓴 항목\n" + rewrite_block("P2", "근거: 없음", "그대로: 괜찮음"))
    assert rc != 0 and "그대로 둘 수 없음" in msg
    rc, msg = compose_with(b, new, "## 다시 쓴 항목\n" + rewrite_block("P2", "근거: 없음", "| 2 | T115의 경과를 본다 |"))
    assert rc != 0 and "T115" in msg


def test_irreversible_answer_is_masked_before_saving(workspace, repo):
    # I5: `own.md`의 글도 절차서에 평문으로 남지 않는다
    secret = "abcd1234secretvalue9999"
    a = finished_run(workspace, repo)
    save(a)
    new = commit_file(repo, "src/app.js", "2\n")
    b = next_run(workspace, repo, new)
    decide(b)
    write(b.task_dir("T021") / deploy_reuse.OWN_FILE, OWN.format(commit=new, extra="").replace(
        "## 되돌릴 수 없는 단계\n없음", "## 되돌릴 수 없는 단계\n- API_TOKEN={} 로 지운 값은 되돌릴 수 없음".format(secret)))
    assert deploy_reuse.compose(str(b), "T021")[0] == 0
    assert run_exec(b, new=new)[0]
    text = devflow_lib.read_text(deploy_reuse.procedure_path(str(b), "dev"))
    assert secret not in text and "되돌릴 수 없음" in text


def test_previous_deploy_commit_becomes_a_place_and_renders_as_saved_commit(workspace, repo):
    first = git(repo, "rev-parse", "HEAD")
    second = commit_file(repo, "src/app.js", "2\n")
    a = finished_run(workspace, repo, commit=second, marks=FIXED_MARKS + "- 명령 7~8: 읽기\n")
    lines = plan_lines(repo, second, a.path) + ["git diff --stat {} {}".format(first, second), "echo {}".format(first[:7])]
    freeze_file(a.task_dir("T011"), "실행승인", lines)
    assert save(a)[0]
    third = commit_file(repo, "src/app.js", "3\n")
    d = decide(next_run(workspace, repo, third))
    assert d["decision"] == deploy_reuse.REUSE and flagged(d) == []
    assert "git diff --stat {} {}".format(second, third) in [x["rendered"] for x in d["items"]]
    assert "echo {}".format(second[:7]) in [x["rendered"] for x in d["items"]]


def test_save_after_reuse_keeps_reused_items_and_updates_rewritten_ones(workspace, repo):
    a = finished_run(workspace, repo)
    save(a)
    before = item_blocks(a)
    new = commit_file(repo, "docs/deploy.md", "새 방식\n")
    b = next_run(workspace, repo, new)
    d = decide(b)
    assert "C4" in flagged(d)
    extra = ("## 추가 명령\n```cmd\necho 이번만\n```\n\n## 다시 쓴 항목\n"
             + rewrite_block("C4", "근거: tools/deploy/run.sh", "```cmd", new_run_line(repo), "```"))
    assert compose_with(b, new, extra)[0] == 0
    ok, msg = run_exec(b, new=new)
    assert ok, msg
    head, body = stored(b)
    assert head["saved_commit"] == new
    after = item_blocks(b)
    assert "이번만" not in body["항목"] and "AC-9" not in body["항목"] and "메일함" not in body["항목"]
    assert "--new" in after[next(k for k in after if k.startswith("C4 "))]
    for key, text in before.items():
        if not key.startswith("C4 "):
            assert after[key] == text, key   # 재사용 항목은 바이트까지 그대로


def test_hand_edited_line_with_a_stale_value_is_rewritten_next_time(workspace, repo):
    # I4: 승인 전에 손으로 넣은 지난 값이 저장 뒤 판정을 지나가지 않는다
    b, new = composed(workspace, repo)
    res = b.task_dir("T021") / "result.md"
    write(res, devflow_lib.read_text(res).replace("&& ./tools/deploy/run.sh", "&& ./tools/deploy/run.sh --task T077"))
    assert run_exec(b, new=new)[0]
    newer = commit_file(repo, "src/app.js", "3\n")
    d = decide(next_run(workspace, repo, newer, name="run-c"))
    assert "C4" in flagged(d) and "T077" in by_id(d, "C4")["detail"]


def test_secret_is_masked_before_saving_and_rewritten(workspace, repo):
    # I5
    commit = git(repo, "rev-parse", "HEAD")
    a = finished_run(workspace, repo, marks=FIXED_MARKS + "- 명령 7: 쓰기 | `docs/deploy.md`\n")
    secret = "abcd1234secretvalue9999"
    lines = plan_lines(repo, commit, a.path) + ["API_TOKEN={} curl -H x https://x.example".format(secret)]
    freeze_file(a.task_dir("T011"), "실행승인", lines)
    assert save(a)[0]
    assert secret not in devflow_lib.read_text(deploy_reuse.procedure_path(str(a), "dev"))
    d = decide(next_run(workspace, repo))
    assert "C7" in flagged(d) and "비밀값" in by_id(d, "C7")["detail"]


# ---------------------------------------------------------------- 항목별 판정

def test_one_changed_file_flags_only_items_bound_to_it_rest_byte_identical(workspace, repo):
    a = finished_run(workspace, repo)
    save(a)
    before = item_blocks(a)
    same = decide(next_run(workspace, repo, name="run-same"))
    new = commit_file(repo, "docs/checks.md", "바뀜\n")
    b = next_run(workspace, repo, new)
    d = decide(b)
    assert d["decision"] == deploy_reuse.REUSE
    bound = {x["id"] for x in stored_items(a).values() if "docs/checks.md" in x["evidence"]}
    assert bound == {"P2", "V1"} and set(flagged(d)) == bound
    for iid in bound:
        assert by_id(d, iid)["why"] == deploy_reuse.WHY_EVIDENCE and "docs/checks.md" in by_id(d, iid)["detail"]
    assert item_blocks(a) == before   # 판정이 절차서를 건드리지 않는다
    for x in d["items"]:
        if x["id"] not in bound:   # 나머지 항목의 틀은 바이트까지 같다
            assert x["text"] == by_id(same, x["id"])["text"] and x["status"] == deploy_reuse.KEEP
    assert compose_with(b, new, "## 다시 쓴 항목\n" + "".join(rewrite_block(i, "근거: docs/checks.md", "그대로: 확인함") for i in sorted(bound)))[0] == 0
    text = devflow_lib.read_text(b.task_dir("T021") / "result.md")
    for x in d["items"]:
        if x["kind"] != "cmd" and "{{" not in x["text"]:
            assert by_id(same, x["id"])["rendered"] in text   # 값 자리가 없는 항목은 결과에 글자 그대로 있다


@pytest.mark.parametrize("path,must", [("docs/deploy.md", ["C4"]), ("package.json", ["C5", "R1"]), ("tools/deploy/run.sh", ["C4"])])
def test_changed_evidence_flags_those_items(workspace, repo, path, must):
    a = finished_run(workspace, repo)
    save(a)
    new = commit_file(repo, path, "바뀜\n")
    d = decide(next_run(workspace, repo, new))
    assert d["decision"] == deploy_reuse.REUSE
    for iid in must:
        assert by_id(d, iid)["why"] == deploy_reuse.WHY_EVIDENCE and path in by_id(d, iid)["detail"]
    assert "C1" not in flagged(d)


@pytest.mark.parametrize("path", ["wrangler.jsonc", "db/migrations/0001.sql", "tools/deploy/new.sh", ".github/workflows/ci.yml"])
def test_deploy_path_no_write_item_cites_flags_all_writes(workspace, repo, path):
    a = finished_run(workspace, repo)
    save(a)
    new = commit_file(repo, path, "바뀜\n")
    d = decide(next_run(workspace, repo, new))
    assert d["decision"] == deploy_reuse.REUSE
    for iid in ("C4", "C5", "C6", "R1"):   # 배포 줄, 사용자 실행, git 쓰기, 되돌리기
        assert by_id(d, iid)["why"] == deploy_reuse.WHY_EVIDENCE and path in by_id(d, iid)["detail"], iid
    assert not {"C1", "C2", "C3"} & set(flagged(d))   # 작성자가 읽기로 표시한 줄은 그대로다


def test_deploy_setting_cited_only_by_a_precondition_still_flags_writes(workspace, repo):
    # B6: 쓰기 명령이 인용하지 않은 배포 설정이면 다른 항목이 인용했어도 쓰기 명령을 다시 본다
    a = finished_run(workspace, repo, mut=lambda s: s.replace("| 2 | [고정] 잠금 값이 있음 | `docs/checks.md` |", "| 2 | [고정] 이름이 맞음 | `wrangler.jsonc` |"))
    assert save(a)[0]
    new = commit_file(repo, "wrangler.jsonc", "{\"name\": \"b\"}\n")
    d = decide(next_run(workspace, repo, new))
    assert {"P2", "C4", "R1"} <= set(flagged(d))


def test_git_write_line_follows_trigger_rule_change(workspace, repo):
    # B6, 사용자 결정 2의 (가): push가 배포를 일으키는 프로젝트. HEAD만 옮기는 줄은 작성자가 읽기로 표시해 그대로 둔다
    commit = commit_file(repo, ".github/workflows/deploy.yml", "on: push: prod\n")
    a = finished_run(workspace, repo, commit=commit, marks=FIXED_MARKS + "- 명령 7: 쓰기\n- 명령 8: 읽기\n")
    lines = plan_lines(repo, commit, a.path) + ["git push origin dev:prod", "git fetch origin"]
    freeze_file(a.task_dir("T011"), "실행승인", lines)
    assert save(a)[0]
    assert stored_items(a)["C7"]["basis"] == deploy_reuse.BASIS_NONE
    new = commit_file(repo, ".github/workflows/deploy.yml", "on: push: release\n")
    d = decide(next_run(workspace, repo, new))
    assert "C7" in flagged(d) and "C8" not in flagged(d)


def test_rollback_tool_change_flags_undo_even_when_a_command_cites_it(workspace, repo):
    # B4: 되돌리기는 그 도구를 근거로 묶는다
    commit = commit_file(repo, "tools/deploy/rollback.sh", "echo a\n")
    a = finished_run(workspace, repo, commit=commit, marks=FIXED_MARKS.replace("- 명령 4: 쓰기\n", "- 명령 4: 쓰기 | `tools/deploy/rollback.sh`\n"))
    assert save(a)[0]
    new = commit_file(repo, "tools/deploy/rollback.sh", "echo --version 필수\n")
    d = decide(next_run(workspace, repo, new))
    assert "R1" in flagged(d) and "rollback.sh" in by_id(d, "R1")["detail"]


def test_deploy_tool_change_flags_undo_too(workspace, repo):
    a = finished_run(workspace, repo)
    save(a)
    new = commit_file(repo, "tools/deploy/run.sh", "바뀜\n")
    d = decide(next_run(workspace, repo, new))
    assert "C4" in flagged(d) and "R1" in flagged(d) and "run.sh" in by_id(d, "R1")["detail"]


def test_unrelated_change_flags_nothing(workspace, repo):
    a = finished_run(workspace, repo)
    save(a)
    new = commit_file(repo, "src/app.js", "2\n")
    d = decide(next_run(workspace, repo, new))
    assert d["decision"] == deploy_reuse.REUSE and flagged(d) == []
    assert d["items"][0]["rendered"] == "cd {} && test \"$(git rev-parse HEAD)\" = {}".format(bash_path(repo), new)
    assert any("run-b/tasks/T020/judge-run.md" in x["rendered"] for x in d["items"])


def test_doc_written_after_save_only_matters_when_it_is_evidence(workspace, repo):
    a = finished_run(workspace, repo)
    save(a)
    new = commit_file(repo, "docs/history.md", "배포 기록\n")
    assert flagged(decide(next_run(workspace, repo, new))) == []
    newer = commit_file(repo, "docs/deploy.md", "절차가 벌어짐\n")
    d = decide(next_run(workspace, repo, newer, name="run-c"))
    assert "C4" in flagged(d) and "C1" not in flagged(d)


def test_docs_state_needing_a_check_flags_items_bound_to_that_doc(workspace, repo):
    a = finished_run(workspace, repo)
    save(a)
    write(workspace / "policies" / "docs-state.md",
          "## 문서\n| 문서 | 지키는 경로 | 기준 커밋 | 상태 | 출처 |\n|---|---|---|---|---|\n"
          "| docs/deploy.md | tools/** | abc | 확인 필요 | T001 |\n")
    d = decide(next_run(workspace, repo))
    assert "C4" in flagged(d) and "docs/deploy.md" in by_id(d, "C4")["detail"]
    assert "C1" not in flagged(d)


DOC = "# 배포\n\n## 2.1 값 파일\n값 파일을 둔다.\n\n## 2.2 로그인\n로그인한다.\n\n## 7.2 순서\n순서대로 올린다.\n"


def doc_run(workspace, repo, changed, doc=DOC, citing="`docs/deploy.md:7.2`, `tools/deploy/run.sh`", second="`docs/deploy.md:4`"):
    """배포 문서의 절을 인용한 계획을 저장한 뒤 문서의 한 곳을 고친다."""
    commit = commit_file(repo, "docs/deploy.md", doc)
    grounds = lambda s: s.replace("- 4번 줄: `docs/deploy.md` 1절, `tools/deploy/run.sh`", "| 4 | 올리기 | {} |\n| 2 | 작업 트리 | {} |".format(citing, second))
    a = finished_run(workspace, repo, commit=commit, mut=grounds)
    assert save(a)[0]
    new = commit_file(repo, "docs/deploy.md", doc.replace(*changed) if isinstance(changed, tuple) else doc + changed)
    return decide(next_run(workspace, repo, new)), a


def test_item_citing_a_doc_section_is_bound_to_that_section_only(workspace, repo):
    d, _ = doc_run(workspace, repo, ("로그인한다.", "다르게 로그인한다."))
    assert "C4" not in flagged(d) and "C2" not in flagged(d)


def test_item_citing_the_changed_section_is_flagged(workspace, repo):
    d, _ = doc_run(workspace, repo, ("순서대로 올린다.", "다른 순서로 올린다."))
    assert "C4" in flagged(d) and "7.2" in by_id(d, "C4")["detail"] and "C2" not in flagged(d)


def test_item_citing_a_line_follows_the_section_holding_that_line(workspace, repo):
    d, _ = doc_run(workspace, repo, ("값 파일을 둔다.", "값 파일을 옮긴다."))
    assert "C2" in flagged(d) and "C4" not in flagged(d)


def test_item_citing_a_removed_section_is_flagged(workspace, repo):
    d, _ = doc_run(workspace, repo, ("## 7.2 순서", "## 8 다른 순서"))
    assert "C4" in flagged(d)


DUP = "# 배포\n\n## dev\n\n### 순서\n\ndev 순서\n\n## 운영\n\n### 순서\n\n운영 순서\n\n## 기타\n\n없음\n"


def test_same_heading_is_told_apart_by_position(workspace, repo):
    # B5: 운영 절의 줄을 인용했으면 dev 절이 바뀌어도 그대로고 운영 절이 바뀌면 다시 쓴다
    n = DUP.split("\n").index("운영 순서") + 1
    d, a = doc_run(workspace, repo, ("dev 순서", "dev 다른 순서"), doc=DUP, citing="`docs/deploy.md:{}`".format(n))
    assert "C4" not in flagged(d)
    assert any("운영" in k and "순서" in k for k in stored_items(a)["C4"]["evidence"])


def test_changed_section_under_same_heading_flags_the_item(workspace, repo):
    n = DUP.split("\n").index("운영 순서") + 1
    d, _ = doc_run(workspace, repo, ("운영 순서", "운영: 폐기, 새 도구 필수"), doc=DUP, citing="`docs/deploy.md:{}`".format(n))
    assert "C4" in flagged(d)


def test_heading_that_cannot_be_told_apart_binds_the_whole_file(workspace, repo):
    doc = "# 배포\n\n## 순서\n\n하나\n\n## 순서\n\n둘\n"
    n = doc.split("\n").index("둘") + 1
    d, a = doc_run(workspace, repo, ("하나", "셋"), doc=doc, citing="`docs/deploy.md:{}`".format(n))
    assert "docs/deploy.md" in stored_items(a)["C4"]["evidence"]
    assert "C4" in flagged(d)


def test_line_past_the_end_binds_the_whole_file(workspace, repo):
    d, a = doc_run(workspace, repo, ("로그인한다.", "다르게"), citing="`docs/deploy.md:999`")
    assert "docs/deploy.md" in stored_items(a)["C4"]["evidence"] and "C4" in flagged(d)


def test_unbound_section_change_is_announced_not_flagged(workspace, repo):
    # B5, 사용자 결정 1의 (가): 어느 항목에도 안 묶인 절이 바뀌면 제목을 알리고 작성자가 더한 항목으로 처리한다
    d, _ = doc_run(workspace, repo, "\n## 올리기 전 필수\n\n백업을 먼저 돌린다.\n")
    assert "C4" not in flagged(d)
    assert any("올리기 전 필수" in x for x in d["notices"])
    b_line = deploy_reuse.decision_line(d)
    assert "알림 1건" in b_line


def test_announced_section_reaches_reuse_file_and_screen_head(workspace, repo):
    commit = commit_file(repo, "docs/deploy.md", DOC)
    mut = lambda s: s.replace("- 4번 줄: `docs/deploy.md` 1절, `tools/deploy/run.sh`", "| 4 | 올리기 | `docs/deploy.md:7.2`, `tools/deploy/run.sh` |")
    a = finished_run(workspace, repo, commit=commit, mut=mut)
    assert save(a)[0]
    new = commit_file(repo, "docs/deploy.md", DOC + "\n## 올리기 전 필수\n\n백업을 먼저 돌린다.\n")
    b = next_run(workspace, repo, new)
    decide(b)
    assert "올리기 전 필수" in devflow_lib.read_text(b.task_dir("T021") / deploy_reuse.DECISION_FILE)
    assert compose_with(b, new, "")[0] == 0
    t = b.tasks()["T021"]
    assert any("올리기 전 필수" in x for x in deploy_reuse.screen_head(str(b), t))


def _replaced(text, old, new):
    head, body = deploy_reuse.parse_procedure(text)
    return head, {k: v.replace(old, new) for k, v in body.items()}


def test_stored_blob_differs_flags_item_even_if_diff_is_clean(workspace, repo):
    a = finished_run(workspace, repo)
    save(a)
    path = deploy_reuse.procedure_path(str(a), "dev")
    blob = git(repo, "rev-parse", "HEAD:package.json")
    deploy_reuse.write_procedure(path, *_replaced(devflow_lib.read_text(path), blob, "0" * 40))
    d = decide(next_run(workspace, repo))
    assert by_id(d, "C5")["why"] == deploy_reuse.WHY_EVIDENCE


def test_unreadable_evidence_flags_every_item_as_other(workspace, repo):
    a = finished_run(workspace, repo)
    save(a)
    path = deploy_reuse.procedure_path(str(a), "dev")
    head, body = deploy_reuse.parse_procedure(devflow_lib.read_text(path))
    deploy_reuse.write_procedure(path, dict(head, saved_commit="0" * 40), body)
    d = decide(next_run(workspace, repo))
    assert d["decision"] == deploy_reuse.REUSE
    assert all(x["why"] == deploy_reuse.WHY_OTHER for x in d["items"])


def test_item_without_readable_basis_is_rewritten_as_other(workspace, repo):
    a = finished_run(workspace, repo, mut=lambda s: s.replace("1. [고정] 사이트 헤더를 읽는다(`docs/checks.md`).", "1. [고정] 눈으로 본다."))
    save(a)
    d = decide(next_run(workspace, repo))
    item = next(x for x in d["items"] if "눈으로" in x["text"])
    assert item["status"] == deploy_reuse.REWRITE and item["why"] == deploy_reuse.WHY_OTHER


def test_write_command_without_evidence_is_rewritten_as_other(workspace, repo):
    a = finished_run(workspace, repo, mut=lambda s: s.replace("- 4번 줄: `docs/deploy.md` 1절, `tools/deploy/run.sh`", ""),
                     lines=None)
    commit = git(repo, "rev-parse", "HEAD")
    lines = plan_lines(repo, commit, a.path)
    lines[3] = "cd {} && ./bin/없는도구".format(bash_path(repo))
    freeze_file(a.task_dir("T011"), "실행승인", lines)
    save(a)
    d = decide(next_run(workspace, repo))
    assert by_id(d, "C4")["why"] == deploy_reuse.WHY_OTHER and "근거" in by_id(d, "C4")["detail"]


@pytest.mark.parametrize("damage", ["digest", "section", "head", "empty", "items"])
def test_damaged_procedure_means_from_scratch(workspace, repo, damage):
    a = finished_run(workspace, repo)
    save(a)
    path = deploy_reuse.procedure_path(str(a), "dev")
    text = devflow_lib.read_text(path)
    if damage == "digest":
        text = text.replace("{{올릴 커밋}}", "손으로 고침", 1)
    elif damage == "section":
        text = text.replace("## 항목", "## 다른 절", 1)
    elif damage == "head":
        text = text.split("---", 2)[2]
    elif damage == "empty":
        text = ""
    write(path, text)
    if damage == "items":
        head, body = deploy_reuse.parse_procedure(text)
        deploy_reuse.write_procedure(path, head, dict(body, 항목="### C1\n- 글: x"))
    d = decide(next_run(workspace, repo))
    assert d["decision"] == deploy_reuse.FRESH and d["kind"] == deploy_reuse.WHY_DAMAGED


def test_place_left_after_render_flags_only_that_item(workspace, repo):
    a = finished_run(workspace, repo)
    save(a)
    path = deploy_reuse.procedure_path(str(a), "dev")
    deploy_reuse.write_procedure(path, *_replaced(devflow_lib.read_text(path), "{{마무리 task}}", "{{모르는 값}}"))
    d = decide(next_run(workspace, repo))
    assert d["decision"] == deploy_reuse.REUSE
    assert flagged(d) == ["C3"] and "모르는 값" in by_id(d, "C3")["detail"] and by_id(d, "C3")["why"] == deploy_reuse.WHY_OTHER


def test_rendered_lines_pass_cmd_line_problems(workspace, repo):
    a = finished_run(workspace, repo)
    save(a)
    d = decide(next_run(workspace, repo))
    for x in d["items"]:
        if x["kind"] == "cmd":
            assert devflow_lib.cmd_line_problems(x["rendered"], cwd=str(repo)) == [], x["rendered"]


def test_render_that_breaks_cmd_line_problems_flags_that_item(workspace, repo):
    a = finished_run(workspace, repo)
    save(a)
    path = deploy_reuse.procedure_path(str(a), "dev")
    deploy_reuse.write_procedure(path, *_replaced(devflow_lib.read_text(path), "cd {{배포 폴더:bash}} && ./tools", "cd {{배포 폴더:win}} && ./tools"))
    d = decide(next_run(workspace, repo))
    if "\\" in str(repo):   # 윈도우 경로에서만 치환 값이 백슬래시를 넣는다
        assert by_id(d, "C4")["status"] == deploy_reuse.REWRITE and by_id(d, "C4")["why"] == deploy_reuse.WHY_OTHER
        assert "C1" not in flagged(d)


# ---------------------------------------------------------------- 환경

@pytest.mark.parametrize("env,other", [("운영", "dev"), ("dev", "운영")])
def test_other_environment_procedure_is_not_used(workspace, repo, env, other):
    a = finished_run(workspace, repo, env=other)
    assert save(a)[0]
    d = decide(next_run(workspace, repo, env=env))
    assert d["decision"] == deploy_reuse.FRESH and d["kind"] == deploy_reuse.WHY_NONE


def test_procedure_renamed_to_other_environment_is_damaged(workspace, repo):
    a = finished_run(workspace, repo, env="운영")
    save(a)
    src = workspace / "policies" / "deploy" / "운영.md"
    write(workspace / "policies" / "deploy" / "dev.md", src.read_text(encoding="utf-8"))
    d = decide(next_run(workspace, repo, env="dev"))
    assert d["decision"] == deploy_reuse.FRESH and d["kind"] == deploy_reuse.WHY_DAMAGED


@pytest.mark.parametrize("meta,want", [
    ({"split_criterion": "환경 운영, 시점 dev 뒤", "title": "x"}, "운영"),
    ({"split_criterion": "환경 dev, 시점 지금", "title": "x"}, "dev"),
    ({"split_criterion": "환경 prod", "title": "x"}, "운영"),
    ({"split_criterion": "환경 production", "title": "x"}, "운영"),
    ({"split_criterion": "환경 개발", "title": "x"}, "dev"),
    # 제목에서 낱말로 추측하지 않는다
    ({"split_criterion": "", "title": "배포 계획 — 운영(af2e958)"}, ""),
    ({"split_criterion": "배포 실행 1행", "title": "배포 계획 — dev"}, ""),
    ({"split_criterion": "", "title": "배포 계획 — 스테이징(dev 뒤)"}, ""),
    # 토큰 전체가 맞아야 한다
    ({"split_criterion": "환경 pre-prod"}, ""),
    ({"split_criterion": "환경 non-prod"}, ""),
    ({"split_criterion": "환경 prod-jp"}, ""),
    ({"split_criterion": "환경 운영전"}, ""),
    ({"split_criterion": "환경 dev2"}, ""),
    ({"split_criterion": "환경 스테이징, 시점 dev 뒤"}, ""),
])
def test_environment_is_read_only_from_the_explicit_value(meta, want):
    assert deploy_reuse.env_of(meta) == want


def test_unknown_environment_means_from_scratch(workspace, repo):
    a = finished_run(workspace, repo)
    save(a)
    b = next_run(workspace, repo)
    b.task("T021", "배포 계획: dev", kind="deploy-plan", block="배포", status="진행", parent="T020", depends_on=["T020"], **NEW)
    d = decide(b)
    assert d["decision"] == deploy_reuse.FRESH and d["kind"] == deploy_reuse.WHY_UNMEASURED


def test_save_uses_the_environment_recorded_at_the_decision(workspace, repo):
    # 자식을 쓴 뒤 split_criterion이 나눈 기준으로 덮여도 판정 때의 환경으로 저장한다
    b, new = composed(workspace, repo)
    b.task("T021", "배포 계획: dev", kind="deploy-plan", block="배포", status="완료", parent="T020", depends_on=["T020"],
           split_criterion="배포 실행 1행", **NEW)
    ok, msg = run_exec(b, new=new)
    assert ok, msg


def test_missing_environment_with_a_procedure_is_not_silent(workspace, repo):
    # N1: 절차서가 있는데 환경을 못 읽으면 고치는 길을 `!` 줄로 낸다
    a = finished_run(workspace, repo)
    save(a)
    b = next_run(workspace, repo)
    b.task("T021", "배포 계획: dev", kind="deploy-plan", block="배포", status="대기", parent="T020", depends_on=["T020"])
    p = run_script("task_set", str(b), "T021", "--status", "진행")
    assert p.returncode == 0, p.stdout + p.stderr
    line = next(x for x in p.stdout.splitlines() if "배포 계획 재사용" in x)
    assert line.startswith("!") and "split_criterion" in line and "--decide" in line
    # 값을 적고 다시 부르면 재사용이다
    p = run_script("task_set", str(b), "T021", "split_criterion=환경 dev")
    assert p.returncode == 0, p.stdout + p.stderr
    p = run_script("deploy_reuse", str(b), "T021", "--decide")
    assert p.returncode == 0 and p.stdout.startswith("배포 계획 재사용: 재사용")
    assert deploy_reuse.read_decision(b.tasks()["T021"])["decision"] == deploy_reuse.REUSE


def test_missing_environment_without_a_procedure_stays_quiet(workspace, repo):
    settings(workspace)
    b = next_run(workspace, repo)
    b.task("T021", "배포 계획: dev", kind="deploy-plan", block="배포", status="진행", parent="T020", depends_on=["T020"], **NEW)
    line = deploy_reuse.decision_line(decide(b))
    assert not line.startswith("!")


# ---------------------------------------------------------------- 배포만

def test_deploy_only_takes_the_commit_from_origin(workspace, repo):
    # B9: 기준 브랜치 끝이 아니라 origin이 검증한 커밋을 받는다
    a = finished_run(workspace, repo)
    save(a)
    verified = commit_file(repo, "src/app.js", "검증된 것\n")
    a.task("T030", "마무리", kind="wrap-up", block="마무리", status="완료", stage="끝", exported_commit=verified, **NEW)
    a.result("T030", MEMO_OK)
    commit_file(repo, "src/app.js", "아직 검증 안 된 것\n")
    r = RunDir(workspace / "only")
    set_run(r, workspace, repo)
    r.task("T021", "배포 계획: dev", kind="deploy-plan", block="배포", status="진행", split_criterion="환경 dev", origin=str(a.task_dir("T030")), **NEW)
    d = decide(r)
    assert d["decision"] == deploy_reuse.REUSE and d["commit"] == verified and not d["notices"]
    assert flagged(d) == ["C3"]   # 마무리 task가 이 실행에 없어 그 항목만 다시 쓴다


def test_deploy_only_without_origin_commit_falls_to_base_branch(workspace, repo):
    a = finished_run(workspace, repo)
    save(a)
    r = RunDir(workspace / "only")
    set_run(r, workspace, repo)
    r.task("T001", "배포 계획: dev", kind="deploy-plan", block="배포", status="진행", split_criterion="환경 dev", **NEW)
    d = deploy_reuse.decide(str(r), r.tasks()["T001"])
    assert d["decision"] == deploy_reuse.REUSE and flagged(d) == ["C3"] and d["commit"] == git(repo, "rev-parse", "dev")


def test_deploy_only_with_unreadable_origin_means_from_scratch(workspace, repo):
    a = finished_run(workspace, repo)
    save(a)
    r = RunDir(workspace / "only")
    set_run(r, workspace, repo)
    r.task("T001", "배포 계획: dev", kind="deploy-plan", block="배포", status="진행", split_criterion="환경 dev", origin=str(workspace / "없는 폴더"), **NEW)
    d = deploy_reuse.decide(str(r), r.tasks()["T001"])
    assert d["decision"] == deploy_reuse.FRESH and d["kind"] == deploy_reuse.WHY_UNMEASURED


# ---------------------------------------------------------------- 새 자원, 전이

@pytest.mark.parametrize("memo,noticed", [
    (MEMO_OK + "- 새 자원: R2 버킷을 만든다\n", True),
    (MEMO_OK + "- 배포 방식을 바꾼다: 컨테이너로\n", True),
    (MEMO_OK + "- 새 자원은 없습니다.\n", False),
    ("## 본문\n내용\n", True),   # 배포 메모를 읽지 못함
])
def test_new_resource_adds_items_and_does_not_stop_reuse(workspace, repo, memo, noticed):
    a = finished_run(workspace, repo)
    save(a)
    d = decide(next_run(workspace, repo, memo=memo))
    assert d["decision"] == deploy_reuse.REUSE and flagged(d) == []
    assert bool(d["notices"]) == noticed


def test_design_and_infra_task_notice_new_resource(workspace, repo):
    a = finished_run(workspace, repo)
    save(a)
    b = next_run(workspace, repo)
    write(b.path / "design" / "x.md", "# 설계\n\n## 배포 계획\n- dev: 새 배포 방식으로 올린다\n")
    b.task("T015", "인프라 결정", kind="infra-design", block="설계", status="완료", **NEW)
    d = decide(b)
    assert d["decision"] == deploy_reuse.REUSE
    assert any("새 배포 방식" in x for x in d["notices"]) and any("T015" in x for x in d["notices"])
    assert "더한 항목" in devflow_lib.read_text(b.task_dir("T021") / deploy_reuse.DECISION_FILE)


def test_no_procedure_writes_from_scratch_with_one_line(workspace, repo):
    settings(workspace)
    d = decide(next_run(workspace, repo))
    assert d["decision"] == deploy_reuse.FRESH and d["kind"] == deploy_reuse.WHY_NONE
    assert "\n" not in d["reason"].strip() and d["reason"]


def test_old_run_gets_no_decision(workspace, repo):
    a = finished_run(workspace, repo)
    save(a)
    b = next_run(workspace, repo, meta=OLD)
    assert deploy_reuse.on_plan_start(str(b), b.tasks()["T021"]) is None
    assert not (b.task_dir("T021") / deploy_reuse.DECISION_FILE).exists()


def test_task_set_start_runs_the_decision(workspace, repo):
    a = finished_run(workspace, repo)
    save(a)
    new = commit_file(repo, "src/app.js", "2\n")
    b = next_run(workspace, repo, new)
    b.task("T021", "배포 계획: dev", kind="deploy-plan", block="배포", status="대기", parent="T020", depends_on=["T020"],
           split_criterion="환경 dev, 시점 지금")
    p = run_script("task_set", str(b), "T021", "--status", "진행")
    assert p.returncode == 0, p.stdout + p.stderr
    assert "배포 계획 재사용" in p.stdout
    assert (b.task_dir("T021") / deploy_reuse.DECISION_FILE).is_file()


def finishing_run(workspace, repo, outcome="유지"):
    """완료 관문을 지나는 실행 task: 소스 시험의 최종 CI, 동일성 근거, 깨끗한 배포 폴더 기록."""
    commit = git(repo, "rev-parse", "HEAD")
    a = finished_run(workspace, repo, status="진행", outcome=outcome)
    write(a.task_dir("T009") / "judge-run.md", ident.judged(
        "\n## 최종 배포 후보 CI\n- 범위: 전체 검증\n- 검증 commit: {}\n- 검증 artifact: {}\n".format(commit, ident.SOURCE)))
    a.judge("T009", ident.READ)
    d = a.task_dir("T011")
    lines = plan_lines(repo, commit, a.path)[:4]
    freeze_file(d, "실행승인", lines)
    write(d / "exec.md", ident.tree_lines(*[(x, commit, "0") for x in lines]))
    write(d / "judge-run.md", ident.judged(ident.proof(check=commit, deployed=commit, build=commit + "-20261106")).replace("T001", "T011"))
    return a


def test_task_set_finish_saves_the_procedure(workspace, repo):
    a = finishing_run(workspace, repo)
    p = run_script("task_set", str(a), "T011", "--status", "완료", "--record", "결과승인|유지|유지")
    assert p.returncode == 0, p.stdout + p.stderr
    assert "배포 절차서: dev 절차서 저장" in p.stdout
    assert (workspace / "policies" / "deploy" / "dev.md").is_file()


def test_task_set_finish_of_a_reverted_deploy_saves_nothing(workspace, repo):
    a = finishing_run(workspace, repo, outcome="되돌림")
    p = run_script("task_set", str(a), "T011", "--status", "완료", "--record", "결과승인|되돌림|되돌림")
    assert p.returncode == 0, p.stdout + p.stderr
    assert "저장 안 함" in p.stdout
    assert not (workspace / "policies" / "deploy" / "dev.md").exists()


# ---------------------------------------------------------------- 작성자 몫과 조립

def test_compose_builds_result_and_keeps_all_commands(workspace, repo):
    b, new = composed(workspace, repo)
    d = b.task_dir("T021")
    text = devflow_lib.read_text(d / "result.md")
    lines = devflow_lib.cmd_lines(devflow_lib.decide_cell(str(d)))
    assert len(lines) == 6 and new in lines[0]
    assert "AC-9" in text and "메일함을 본다" in text and "예시 값이 있음" in text
    assert "npx rollback" in execmod.heading_section(text, "되돌리기")
    assert "{{" not in text
    for cell in ("정해 주실 것", "하실 일·허용 요청", "알릴 것", "답하신 것의 반영", "확인 안 된 것", "건수만"):
        assert "### " + cell in text


def test_compose_child_row_is_a_valid_deploy_exec_row(workspace, repo):
    import spawn_children
    b, _ = composed(workspace, repo)
    text = devflow_lib.read_text(b.task_dir("T021") / "result.md")
    criterion, children = spawn_children.parse_children(text)
    assert len(children) == 1 and children[0]["meta"]["kind"] == "deploy-exec"
    assert "환경 dev" in criterion


def test_compose_rejects_wrong_commit_and_missing_sections(workspace, repo):
    a = finished_run(workspace, repo)
    save(a)
    new = commit_file(repo, "src/app.js", "2\n")
    b = next_run(workspace, repo, new)
    decide(b)
    own = b.task_dir("T021") / deploy_reuse.OWN_FILE
    write(own, OWN.format(commit="0" * 40, extra=""))
    assert deploy_reuse.compose(str(b), "T021")[0] != 0
    write(own, "## 올릴 커밋\n{}\n".format(new))
    rc, msg = deploy_reuse.compose(str(b), "T021")
    assert rc != 0 and "배포 전 확인" in msg and "되돌릴 수 없는 단계" in msg
    assert not (b.task_dir("T021") / "result.md").exists()


def test_writer_answers_irreversible_steps_each_time(workspace, repo):
    # I3: 지난 글을 그대로 잇지 않고 이번 답을 싣는다. 지난 글은 참고로 reuse.md에 있다
    a = finished_run(workspace, repo)
    assert save(a)[0]
    new = commit_file(repo, "src/app.js", "2\n")
    b = next_run(workspace, repo, new)
    decide(b)
    assert "첫 자원 만들기는 되돌릴 수 없음" in devflow_lib.read_text(b.task_dir("T021") / deploy_reuse.DECISION_FILE)
    write(b.task_dir("T021") / deploy_reuse.OWN_FILE, OWN.format(commit=new, extra="").replace("## 되돌릴 수 없는 단계\n없음", "## 되돌릴 수 없는 단계\n- 이번에 넣는 표는 되돌릴 수 없음"))
    assert deploy_reuse.compose(str(b), "T021")[0] == 0
    cell = screen.build(str(b), "T021")["screen"]["정해 주실 것"]
    assert "[되돌릴 수 없는 단계 포함]" in cell and "이번에 넣는 표는" in cell and "첫 자원 만들기" not in cell


def test_writer_text_sections_go_to_the_body(workspace, repo):
    b, _ = composed(workspace, repo, extra="## 설명\n이번 배포의 설명\n\n## 연결 경로 대조\n| 경로 | dev |\n")
    text = devflow_lib.read_text(b.task_dir("T021") / "result.md")
    assert "이번 배포의 설명" in text and "### 연결 경로 대조" in text


def test_compose_requires_every_flagged_item(workspace, repo):
    b, new = flagged_run(workspace, repo)
    rc, msg = compose_with(b, new, "")
    assert rc != 0 and "C4" in msg
    assert not (b.task_dir("T021") / "result.md").exists()


def test_rewritten_command_goes_in_the_fence_with_diff_on_the_screen(workspace, repo):
    b, new = flagged_run(workspace, repo)
    rc, msg = compose_with(b, new, "## 다시 쓴 항목\n" + rewrite_block("C4", "근거: tools/deploy/run.sh", "```cmd", new_run_line(repo), "```"))
    assert rc == 0, msg
    lines = devflow_lib.cmd_lines(devflow_lib.decide_cell(str(b.task_dir("T021"))))
    assert lines[3] == new_run_line(repo) and len(lines) == 6
    material = screen.build(str(b), "T021")["screen"]["리뷰 자료"]
    assert "C4" in material and "앞: " + new_run_line(repo, "") in material and "새: " + new_run_line(repo) in material


def test_rewrite_needs_an_evidence_line_and_real_files(workspace, repo):
    b, new = flagged_run(workspace, repo)
    block = "```cmd\n{}\n```".format(new_run_line(repo))
    rc, msg = compose_with(b, new, "## 다시 쓴 항목\n" + rewrite_block("C4", block))
    assert rc != 0 and "근거" in msg
    rc, msg = compose_with(b, new, "## 다시 쓴 항목\n" + rewrite_block("C4", "근거: tools/없는.sh", block))
    assert rc != 0 and "없는" in msg


def test_rewrite_citing_a_missing_section_is_rejected(workspace, repo):
    b, new = flagged_run(workspace, repo)
    rc, msg = compose_with(b, new, "## 다시 쓴 항목\n" + rewrite_block("C4", "근거: docs/deploy.md#없는 절", "그대로: 같음"))
    assert rc != 0 and "없는 절" in msg


def test_evidence_line_keeps_commas_inside_a_heading():
    value = "docs/a.md#목록 > 9. 확인 (AC-1, FR-2 (c), 실행), tools/run.sh, docs/b.md:7.2"
    assert [x.strip() for x in deploy_reuse.EVIDENCE_SPLIT.split(value)] == ["docs/a.md#목록 > 9. 확인 (AC-1, FR-2 (c), 실행)", "tools/run.sh", "docs/b.md:7.2"]


def test_dot_file_is_not_bound_to_every_command(workspace, repo):
    # 맨 위의 점 파일은 이름 앞이 비어 있어 모든 줄에 맞으면 안 된다
    commit = commit_file(repo, ".gitignore", "x\n")
    a = finished_run(workspace, repo, commit=commit)
    assert save(a)[0]
    assert ".gitignore" not in stored_items(a)["C4"]["evidence"]
    assert [x.strip() for x in deploy_reuse.EVIDENCE_SPLIT.split(".env.example, .gitignore, a.md")] == [".env.example", ".gitignore", "a.md"]


def test_write_command_cannot_answer_no_evidence(workspace, repo):
    # I1: 한 번의 `근거: 없음`으로 묶음이 영구히 풀리지 않는다
    b, new = flagged_run(workspace, repo)
    rc, msg = compose_with(b, new, "## 다시 쓴 항목\n" + rewrite_block("C4", "근거: 없음", "그대로: 괜찮음"))
    assert rc != 0 and "근거" in msg


def test_read_and_text_items_can_answer_no_evidence(workspace, repo):
    a = finished_run(workspace, repo)
    save(a)
    new = commit_file(repo, "docs/checks.md", "바뀜\n")
    b = next_run(workspace, repo, new)
    decide(b)
    assert compose_with(b, new, "## 다시 쓴 항목\n" + rewrite_block("P2", "근거: 없음", "그대로: 같음") + rewrite_block("V1", "근거: 없음", "그대로: 같음"))[0] == 0


def test_rewrite_with_shape_problem_is_rejected(workspace, repo):
    b, new = flagged_run(workspace, repo)
    rc, _ = compose_with(b, new, "## 다시 쓴 항목\n" + rewrite_block("C4", "근거: tools/deploy/run.sh", "```cmd", "git -C D:\\x status", "```"))
    assert rc != 0


def test_fence_with_a_space_outside_command_sections_is_rejected(workspace, repo):
    # I6
    a = finished_run(workspace, repo)
    save(a)
    new = commit_file(repo, "src/app.js", "2\n")
    b = next_run(workspace, repo, new)
    decide(b)
    rc, msg = compose_with(b, new, "## 정해 주실 것\n- 질문\n  ``` cmd\n  rm -rf /d/x\n  ```\n")
    assert rc != 0 and "정해 주실 것" in msg


def test_later_environment_needs_dependency_and_pre_checks(workspace, repo):
    # I8: 같은 실행에 앞 환경 계획이 있으면 운영 계획의 의존과 배포 전 확인을 기계가 본다
    a = finished_run(workspace, repo, env="운영")
    assert save(a)[0]
    new = commit_file(repo, "src/app.js", "2\n")
    b = next_run(workspace, repo, new, env="운영")
    b.task("T019", "배포 계획: dev", kind="deploy-plan", block="배포", status="완료", parent="T020", split_criterion="환경 dev", **NEW)
    decide(b)
    rc, msg = compose_with(b, new, "")
    assert rc != 0 and "depends_on" in msg
    assert compose_with(b, new, "## 자식\n- depends_on: T019\n")[0] == 0
    write(b.task_dir("T021") / deploy_reuse.OWN_FILE, OWN.format(commit=new, extra="## 자식\n- depends_on: T019\n").replace("- 예시 값이 있음", "없음"))
    rc, msg = deploy_reuse.compose(str(b), "T021")
    assert rc != 0 and "배포 전 확인" in msg


def test_branch_name_is_only_generalized_in_git_arguments():
    # I7
    values = {"통합 브랜치": "release"}
    out, _ = deploy_reuse.generalize("git push origin release && npm run release", values)
    assert out == "git push origin {{통합 브랜치}} && npm run release"


def test_same_folder_with_two_meanings_stays_a_value_to_rewrite(workspace, repo):
    # I7: 배포 폴더와 원래 폴더가 같으면 어느 쪽인지 모른다
    a = finished_run(workspace, repo)
    text = (a.path / "run.md").read_text(encoding="utf-8")
    write(a.path / "run.md", text.replace("project: {}".format(workspace / "original"), "project: {}".format(repo)))
    assert save(a)[0]
    d = decide(next_run(workspace, repo))
    assert "C4" in flagged(d) and "뜻이 둘" in by_id(d, "C4")["detail"]


def test_keeping_a_flagged_item_as_is_counts_as_rewritten(workspace, repo):
    b, new = flagged_run(workspace, repo)
    rc, msg = compose_with(b, new, "## 다시 쓴 항목\n" + rewrite_block("C4", "근거: tools/deploy/run.sh", "그대로: 옵션이 같음"))
    assert rc == 0, msg
    lines = devflow_lib.cmd_lines(devflow_lib.decide_cell(str(b.task_dir("T021"))))
    assert lines[3] == new_run_line(repo, "")
    plan = deploy_reuse.line_plan(str(b), b.tasks()["T021"])
    assert (plan["rewritten"], plan["why_evidence"], plan["why_other"]) == (1, 1, 0)
    assert plan["lines"][3][1] == deploy_reuse.REWRITTEN
    material = screen.build(str(b), "T021")["screen"]["리뷰 자료"]
    assert "그대로 둠 1: C4" in material and "앞: " not in material
    assert any("옵션이 같음" in x for x in deploy_reuse.check(str(b), "T021")[1])   # 이유는 판정자가 본다


def test_reused_item_changed_by_writer_is_raised_not_failed(workspace, repo):
    b, new = composed(workspace, repo, extra="## 다시 쓴 항목\n" + rewrite_block("C2", "근거: 없음", "```cmd", "git status", "```"))
    t = b.tasks()["T021"]
    plan = deploy_reuse.line_plan(str(b), t)
    assert plan["drifted"] == ["C2"] and plan["lines"][1][1] == deploy_reuse.DRIFT
    assert any("달라진 재사용 항목 1" in x for x in deploy_reuse.screen_head(str(b), t))
    ok, lines = deploy_reuse.check(str(b), "T021")
    assert ok and any("달라진 재사용 항목" in x and "C2" in x for x in lines)


def test_result_edited_by_hand_is_raised_not_failed(workspace, repo):
    b, _ = composed(workspace, repo)
    res = b.task_dir("T021") / "result.md"
    write(res, devflow_lib.read_text(res).replace("./tools/deploy/run.sh", "./tools/deploy/other.sh"))
    t = b.tasks()["T021"]
    plan = deploy_reuse.line_plan(str(b), t)
    assert plan["drifted"] == ["C4"] and plan["lines"][3] == (4, deploy_reuse.DRIFT, new_run_line(repo, "").replace("run.sh", "other.sh"))
    assert any("달라진 재사용 항목 1" in x for x in deploy_reuse.screen_head(str(b), t))
    ok, lines = deploy_reuse.check(str(b), "T021")
    assert ok and any("달라진 재사용 항목" in x for x in lines)


def test_undo_changed_by_hand_reaches_head_check_and_screen(workspace, repo):
    # B3
    b, _ = composed(workspace, repo)
    res = b.task_dir("T021") / "result.md"
    bad = "npx rollback --to other-version && rm -rf dist"
    write(res, devflow_lib.read_text(res).replace("npx rollback", bad))
    t = b.tasks()["T021"]
    plan = deploy_reuse.line_plan(str(b), t)
    assert "R1" in plan["drifted"] and plan["undo"][0][1] == deploy_reuse.DRIFT and bad in plan["undo"][0][2]
    assert any("달라진 재사용 항목 1" in x for x in deploy_reuse.screen_head(str(b), t))
    assert bad in deploy_reuse.annotate(str(b), t, screen.build(str(b), "T021")["screen"]["정해 주실 것"])
    ok, lines = deploy_reuse.check(str(b), "T021")
    assert ok and any("달라진 재사용 항목" in x and "R1" in x for x in lines)


def test_prose_changed_by_hand_reaches_head(workspace, repo):
    b, _ = composed(workspace, repo)
    res = b.task_dir("T021") / "result.md"
    write(res, devflow_lib.read_text(res).replace("사이트 헤더를 읽는다", "사이트 헤더를 안 읽는다"))
    t = b.tasks()["T021"]
    assert "V1" in deploy_reuse.line_plan(str(b), t)["drifted"]


def test_editing_manifest_too_does_not_hide_the_change(workspace, repo):
    # I2: 조립 기록까지 함께 고쳐도 기대 줄은 절차서에서 다시 만든다
    b, _ = composed(workspace, repo)
    t = b.tasks()["T021"]
    m = deploy_reuse.read_manifest(t)
    y = next(x for x in m["items"] if x["id"] == "C2")
    good = y["rendered"]
    bad = good + " && rm -rf /d/x"
    y["rendered"], y["old"], y["text"] = bad, bad, bad
    write(deploy_reuse.manifest_path(t), json.dumps(m, ensure_ascii=False))
    res = b.task_dir("T021") / "result.md"
    write(res, devflow_lib.read_text(res).replace(good, bad))
    plan = deploy_reuse.line_plan(str(b), t)
    assert "C2" in plan["drifted"] and plan["lines"][1] == (2, deploy_reuse.DRIFT, bad)
    assert any("달라진 재사용 항목" in x and "C2" in x for x in deploy_reuse.check(str(b), "T021")[1])


def test_manifest_dropping_an_item_silently_is_raised(workspace, repo):
    b, _ = composed(workspace, repo)
    t = b.tasks()["T021"]
    m = deploy_reuse.read_manifest(t)
    m["items"] = [x for x in m["items"] if x["id"] != "C2"]
    write(deploy_reuse.manifest_path(t), json.dumps(m, ensure_ascii=False))
    assert "C2" in deploy_reuse.line_plan(str(b), t)["drifted"]


def test_added_and_removed_items_are_visible_and_saved(workspace, repo):
    b, new = flagged_run(workspace, repo)
    extra = ("## 뺄 항목\n- C4: 도구가 없어짐\n"
             + "\n## 더한 항목\n### A1 | 명령 | C5 앞\n근거: tools/deploy/run.sh\n```cmd\n" + new_run_line(repo, " --v2") + "\n```\n"
             + "### A2 | 배포 뒤 확인\n근거: docs/checks.md\n- 새 자원을 읽는다\n"
             + "### A3 | 명령 | C1 앞\n종류: 읽기\n근거: 없음\n```cmd\ngit status --short\n```\n")
    rc, msg = compose_with(b, new, extra)
    assert rc == 0, msg
    lines = devflow_lib.cmd_lines(devflow_lib.decide_cell(str(b.task_dir("T021"))))
    assert lines[0] == "git status --short" and lines[4] == new_run_line(repo, " --v2") and len(lines) == 7
    t = b.tasks()["T021"]
    head = deploy_reuse.screen_head(str(b), t)[0]
    assert "더함 3" in head and "뺌 1(C4)" in head
    cells = screen.build(str(b), "T021")["screen"]
    assert "--v2" in cells["리뷰 자료"]
    assert "[뺀 항목] C4" in cells["알릴 것"] and "도구가 없어짐" in cells["알릴 것"]
    assert run_exec(b, new=new)[0]
    items = stored_items(b)
    assert any("--v2" in x["text"] and x["evidence"] for x in items.values()) and any("새 자원을 읽는다" in x["text"] for x in items.values())
    assert "C4" not in items   # 지운 번호를 다시 쓰지 않는다
    assert next(x for x in items.values() if "--short" in x["text"])["mode"] == deploy_reuse.READ


def test_writer_can_drop_a_reused_stale_line_and_it_stays_visible(workspace, repo):
    a = finished_run(workspace, repo)
    save(a)
    new = commit_file(repo, "src/app.js", "2\n")
    b = next_run(workspace, repo, new)
    decide(b)
    assert compose_with(b, new, "## 뺄 항목\n- C5: 이번부터 잠금이 필요 없음\n")[0] == 0
    t = b.tasks()["T021"]
    lines = devflow_lib.cmd_lines(devflow_lib.decide_cell(t["_dir"]))
    assert len(lines) == 5 and not any("npm run lock" in x for x in lines)
    head = deploy_reuse.screen_head(str(b), t)
    assert "뺌 1(C5)" in head[0] and "달라진" not in head[0]
    cells = screen.build(str(b), "T021")["screen"]
    assert "[뺀 항목] C5" in cells["알릴 것"] and "npm run lock" in cells["알릴 것"]
    assert run_exec(b, new=new)[0]
    assert "C5" not in stored_items(b)


def test_drop_list_rejects_unknown_item_and_needs_a_reason(workspace, repo):
    b, new = flagged_run(workspace, repo)
    assert compose_with(b, new, "## 뺄 항목\n- C99: 없는 항목\n")[0] != 0
    assert compose_with(b, new, "## 뺄 항목\n- C4\n")[0] != 0


def test_compose_refuses_when_procedure_moved_after_the_decision(workspace, repo):
    a = finished_run(workspace, repo)
    save(a)
    new = commit_file(repo, "src/app.js", "2\n")
    b = next_run(workspace, repo, new)
    decide(b)
    write(b.task_dir("T021") / deploy_reuse.OWN_FILE, OWN.format(commit=new, extra=""))
    path = deploy_reuse.procedure_path(str(a), "dev")
    write(path, devflow_lib.read_text(path).replace("{{올릴 커밋}}", "x", 1))
    assert deploy_reuse.compose(str(b), "T021")[0] != 0


def test_compose_without_reuse_decision_is_refused(workspace, repo):
    settings(workspace)
    b = next_run(workspace, repo)
    decide(b)
    assert deploy_reuse.compose(str(b), "T021")[0] != 0


def test_person_can_order_from_scratch(workspace, repo):
    a = finished_run(workspace, repo)
    save(a)
    b = next_run(workspace, repo)
    decide(b)
    rc, _ = deploy_reuse.fresh(str(b), "T021", "사용자 답: 처음부터")
    assert rc == 0
    d = deploy_reuse.read_decision(b.tasks()["T021"])
    assert d["decision"] == deploy_reuse.FRESH and d["kind"] == deploy_reuse.WHY_HUMAN


def test_check_lists_values_and_rewritten_items(workspace, repo):
    b, new = flagged_run(workspace, repo)
    assert compose_with(b, new, "## 다시 쓴 항목\n" + rewrite_block("C4", "근거: tools/deploy/run.sh", "```cmd", new_run_line(repo), "```"))[0] == 0
    ok, lines = deploy_reuse.check(str(b), "T021")
    assert ok, lines
    joined = "\n".join(lines)
    assert "올릴 커밋 = " + new in joined and "다시 쓴 항목 1" in joined and "C4" in joined


def test_check_fails_on_a_place_left_in_result(workspace, repo):
    b, _ = composed(workspace, repo)
    res = b.task_dir("T021") / "result.md"
    write(res, devflow_lib.read_text(res) + "\n{{올릴 커밋}}\n")
    ok, lines = deploy_reuse.check(str(b), "T021")
    assert not ok and any("자리 값" in x for x in lines)


# ---------------------------------------------------------------- 줄 번호

def test_line_references_follow_the_real_numbers(workspace, repo):
    # B12: 추가 명령이 앞에 들어와도 사전 조건이 가리키는 번호는 실제 줄이다
    b, _ = composed(workspace, repo, extra="## 추가 명령\n```cmd\necho 이번만\n```\n")
    text = devflow_lib.read_text(b.task_dir("T021") / "result.md")
    assert "HEAD가 올릴 커밋 | 2번째 줄" in text
    assert "줄 번호는 절차서 기준" not in text


def test_procedure_keeps_a_line_link_by_item(workspace, repo):
    a = finished_run(workspace, repo)
    save(a)
    assert "{{줄:C1}}번째 줄" in stored_items(a)["P1"]["text"]


def test_reference_to_a_dropped_line_is_rejected(workspace, repo):
    a = finished_run(workspace, repo)
    save(a)
    new = commit_file(repo, "src/app.js", "2\n")
    b = next_run(workspace, repo, new)
    decide(b)
    rc, msg = compose_with(b, new, "## 뺄 항목\n- C1: 필요 없음\n")
    assert rc != 0 and "P1" in msg and "C1" in msg
    assert compose_with(b, new, "## 뺄 항목\n- C1: 필요 없음\n- P1: 같이 뺌\n")[0] == 0


def test_writer_text_refers_to_a_line_by_item_and_gets_the_real_number(workspace, repo):
    # N4: 추가 명령이 앞에 들어와도 작성자 글의 번호가 실제 줄이다
    a = finished_run(workspace, repo)
    save(a)
    new = commit_file(repo, "src/app.js", "2\n")
    b = next_run(workspace, repo, new)
    decide(b)
    own = OWN.format(commit=new, extra="## 추가 명령\n```cmd\necho 이번만\n```\n").replace(
        "## 되돌릴 수 없는 단계\n없음", "## 되돌릴 수 없는 단계\n- 명령 {{줄:C4}}의 첫 자원 만들기")
    write(b.task_dir("T021") / deploy_reuse.OWN_FILE, own)
    rc, msg = deploy_reuse.compose(str(b), "T021")
    assert rc == 0, msg
    cell = screen.build(str(b), "T021")["screen"]["정해 주실 것"]
    assert "명령 5의 첫 자원 만들기" in cell
    lines = devflow_lib.cmd_lines(devflow_lib.decide_cell(str(b.task_dir("T021"))))
    assert "run.sh" in lines[4]
    assert "{{" not in devflow_lib.read_text(b.task_dir("T021") / "result.md")


@pytest.mark.parametrize("section,old", [
    ("되돌릴 수 없는 단계", "없음"), ("배포 전 확인", "- 예시 값이 있음"), ("배포 뒤 확인", "- AC-9: 화면을 본다"),
    ("미룬 실물 확인", "- 메일함을 본다"), ("배포 뒤 적을 문서", "없음"),
])
def test_literal_line_number_in_writer_text_is_rejected(workspace, repo, section, old):
    a = finished_run(workspace, repo)
    save(a)
    new = commit_file(repo, "src/app.js", "2\n")
    b = next_run(workspace, repo, new)
    decide(b)
    write(b.task_dir("T021") / deploy_reuse.OWN_FILE, OWN.format(commit=new, extra="").replace("## {}\n{}".format(section, old), "## {}\n- 명령 4를 본다".format(section)))
    rc, msg = deploy_reuse.compose(str(b), "T021")
    assert rc != 0 and section in msg and "{{줄:" in msg
    assert not (b.task_dir("T021") / "result.md").exists()


@pytest.mark.parametrize("extra", ["## 설명\n3번째 줄이 배포다\n", "## 정해 주실 것\n- 명령 2~3을 뺄까요\n", "## 자식\n- 판정 기준: 명령 4가 통과한다\n"])
def test_literal_line_number_is_rejected_in_every_free_section(workspace, repo, extra):
    a = finished_run(workspace, repo)
    save(a)
    new = commit_file(repo, "src/app.js", "2\n")
    b = next_run(workspace, repo, new)
    decide(b)
    assert compose_with(b, new, extra)[0] != 0


def test_line_count_phrase_in_writer_text_is_fine(workspace, repo):
    b, _ = composed(workspace, repo, extra="## 설명\n이번은 명령 6줄입니다\n")
    assert "명령 6줄" in devflow_lib.read_text(b.task_dir("T021") / "result.md")


def test_writer_text_pointing_at_a_dropped_or_unknown_item_is_rejected(workspace, repo):
    a = finished_run(workspace, repo)
    save(a)
    new = commit_file(repo, "src/app.js", "2\n")
    b = next_run(workspace, repo, new)
    decide(b)
    assert compose_with(b, new, "## 설명\n{{줄:C99}}번을 본다\n")[0] != 0
    assert compose_with(b, new, "## 뺄 항목\n- C5: 필요 없음\n\n## 설명\n{{줄:C5}}번을 본다\n")[0] != 0


def test_rewritten_item_with_a_line_number_is_linked_again(workspace, repo):
    b, new = flagged_run(workspace, repo, path="docs/checks.md")
    assert compose_with(b, new, "## 추가 명령\n```cmd\necho 이번만\n```\n\n## 다시 쓴 항목\n" + rewrite_block("P2", "근거: docs/checks.md", "| 2 | 잠금은 명령 3으로 본다 |")
                        + rewrite_block("V1", "근거: docs/checks.md", "그대로: 같음"))[0] == 0
    assert run_exec(b, new=new)[0]
    assert "{{줄:C2}}" in stored_items(b)["P2"]["text"]   # 실제 3번은 고정 줄 C2다


def test_line_count_phrase_is_not_a_line_reference():
    # B1: 「명령 6줄」은 6번 줄이 아니다
    assert deploy_reuse.linked_lines("아래 명령 6줄을 실행합니다") == set()
    assert deploy_reuse.linked_lines("명령 4를 봅니다, 2번째 줄, 7번 줄") == {2, 4, 7}


# ---------------------------------------------------------------- 화면

SHOWN = re.compile(r"^\s*(\d+)\. \[([^\]]+)\] (.*)$", flags=re.M)


def test_screen_shows_every_command_with_number_and_label(workspace, repo):
    b, new = composed(workspace, repo, extra="## 추가 명령\n```cmd\necho 이번만\n```\n")
    t = b.tasks()["T021"]
    run_lines = devflow_lib.cmd_lines(devflow_lib.decide_cell(t["_dir"]))
    full = screen.build(str(b), "T021")["screen"]["정해 주실 것"]
    assert devflow_lib.cmd_lines(full) == run_lines
    shown = [(int(a), l, c) for a, l, c in SHOWN.findall(deploy_reuse.annotate(str(b), t, full))]
    assert [c for _, _, c in shown] == run_lines and [n for n, _, _ in shown] == list(range(1, len(run_lines) + 1))
    assert shown[0][1] == deploy_reuse.THIS_RUN and all(l == deploy_reuse.KEEP for _, l, _ in shown[1:])
    _, frozen = execmod.source(str(b), {"T022": {"parent": "T021", "kind": "deploy-exec"}, "T021": t},
                               {"parent": "T021", "kind": "deploy-exec"}, "실행승인")
    assert frozen == run_lines


def test_screen_labels_rewritten_and_added(workspace, repo):
    b, new = flagged_run(workspace, repo)
    extra = ("## 다시 쓴 항목\n" + rewrite_block("C4", "근거: tools/deploy/run.sh", "```cmd", new_run_line(repo), "```")
             + "\n## 더한 항목\n### A1 | 명령\n근거: tools/deploy/run.sh\n```cmd\n" + new_run_line(repo, " --more") + "\n```\n")
    assert compose_with(b, new, extra)[0] == 0
    t = b.tasks()["T021"]
    shown = {c: l for _, l, c in SHOWN.findall(deploy_reuse.annotate(str(b), t, screen.build(str(b), "T021")["screen"]["정해 주실 것"]))}
    assert shown[new_run_line(repo)] == deploy_reuse.REWRITTEN and shown[new_run_line(repo, " --more")] == deploy_reuse.ADDED


def test_screen_always_carries_undo(workspace, repo):
    b, _ = composed(workspace, repo)
    t = b.tasks()["T021"]
    out = deploy_reuse.annotate(str(b), t, screen.build(str(b), "T021")["screen"]["정해 주실 것"])
    assert "되돌리기 1. [재사용] cd {} && npx rollback".format(bash_path(repo)) in out


def test_every_reused_check_is_on_the_screen(workspace, repo):
    # B10: 운영 쓰기 확인을 글자로 가려내지 않고 재사용 확인을 전부 싣는다
    mut = lambda s: s.replace("3. [고정] 접수 POST 쓰기 확인을 한다(`docs/guide.md`).", "3. [고정] 문의 폼에 값을 넣어 접수하고 메일 도착을 본다(`docs/deploy.md`).")
    a = finished_run(workspace, repo, env="운영", mut=mut)
    assert save(a)[0]
    new = commit_file(repo, "src/app.js", "2\n")
    b = next_run(workspace, repo, new, env="운영")
    decide(b)
    assert compose_with(b, new, "")[0] == 0
    cells = screen.build(str(b), "T021")["screen"]
    assert "문의 폼에 값을 넣어" in cells["알릴 것"] and "사이트 헤더" in cells["알릴 것"]


def test_screen_head_and_no_folding_left(workspace, repo):
    b, new = composed(workspace, repo)
    b.task("T021", "배포 계획: dev", kind="deploy-plan", block="배포", status="승인대기", parent="T020",
           depends_on=["T020"], split_criterion="환경 dev, 시점 지금", **NEW)
    p = run_script("screen", str(b), "T021")
    assert p.returncode == 0, p.stdout + p.stderr
    n = len(deploy_reuse.read_manifest(b.tasks()["T021"])["items"])
    assert "재사용 {}, 다시 씀 0(근거 바뀜 0, 그 밖 0), 이번 실행 몫 3".format(n) in p.stdout
    assert "접음" not in p.stdout and "--full" not in p.stdout
    lines = devflow_lib.cmd_lines(devflow_lib.decide_cell(str(b.task_dir("T021"))))
    assert all(x in p.stdout for x in lines)
    assert "[재사용]" in p.stdout


def test_folding_code_is_gone():
    assert not hasattr(deploy_reuse, "fold") and not hasattr(deploy_reuse, "is_read_line")


def test_screen_head_counts_rewritten_by_reason(workspace, repo):
    a = finished_run(workspace, repo, mut=lambda s: s.replace("1. [고정] 사이트 헤더를 읽는다(`docs/checks.md`).", "1. [고정] 눈으로 본다."))
    save(a)
    new = commit_file(repo, "docs/deploy.md", "바뀜\n")
    b = next_run(workspace, repo, new)
    d = decide(b)
    other = next(x["id"] for x in d["items"] if "눈으로" in x["text"])
    assert compose_with(b, new, "## 다시 쓴 항목\n" + rewrite_block("C4", "근거: tools/deploy/run.sh", "그대로: 같음")
                        + rewrite_block(other, "근거: 없음", "1. 화면을 눈으로 본다."))[0] == 0
    head = deploy_reuse.screen_head(str(b), b.tasks()["T021"])[0]
    assert "다시 씀 2(근거 바뀜 1, 그 밖 1)" in head


def test_sheet_carries_all_commands_and_undo(workspace, repo):
    import visual
    b, _ = composed(workspace, repo)
    t = b.tasks()["T021"]
    page, _ = visual.sheet_html(str(b), t)
    lines = devflow_lib.cmd_lines(devflow_lib.decide_cell(t["_dir"]))
    for n, line in enumerate(lines, 1):
        assert visual.html.escape("{}. [재사용] {}".format(n, line)) in page or visual.html.escape(line) in page, line
    assert "npx rollback" in page


def test_from_scratch_plan_screen_is_unchanged(workspace, repo):
    settings(workspace)
    b = next_run(workspace, repo)
    decide(b)
    b.result("T021", plan_result(["echo 하나"], ["echo 되돌림"]))
    t = b.tasks()["T021"]
    full = screen.build(str(b), "T021")["screen"]["정해 주실 것"]
    assert deploy_reuse.annotate(str(b), t, full) == full
    assert deploy_reuse.screen_head(str(b), t) == []


# ---------------------------------------------------------------- 사람 승인

def test_reused_plan_does_not_close_without_a_human_answer(workspace, repo):
    b, _ = composed(workspace, repo)
    b.judge("T021", "판정자: rjudge-T021 2026-10-15 10:00:00\n\n## 통과 못 한 기준\n- 없음\n")
    b.task("T021", "배포 계획: dev", kind="deploy-plan", block="배포", status="승인대기", parent="T020",
           depends_on=["T020"], split_criterion="환경 dev, 시점 지금", **NEW)
    ok, _ = screen.notify_status(str(b), "T021")
    assert not ok


def test_delegation_does_not_close_a_reused_plan(workspace, repo):
    b, _ = composed(workspace, repo)
    t = b.tasks()["T021"]
    cells = screen.build(str(b), "T021")["screen"]
    gate = delegation.gate(str(b), t, cells, "", levels=("L1", "L2", "L3", "L4"))
    assert not gate["closable"] and any("배포 계획의 첫 승인" in w[0] for w in gate["wait"])


# ---------------------------------------------------------------- 측정

def test_measure_line_counts_items_and_reasons(workspace, repo):
    a = finished_run(workspace, repo)
    save(a)
    new = commit_file(repo, "docs/deploy.md", "2\n")
    b = next_run(workspace, repo, new)
    d = decide(b)
    assert compose_with(b, new, "## 다시 쓴 항목\n" + rewrite_block("C4", "근거: tools/deploy/run.sh", "그대로: 같음"))[0] == 0
    b.task("T030", "배포 계획: 운영", kind="deploy-plan", block="배포", status="진행", parent="T020",
           depends_on=["T020"], split_criterion="환경 운영", **NEW)
    decide(b, "T030")
    n = len(d["items"]) - 1
    assert deploy_reuse.measure_line(b.tasks()) == "- 배포 계획 재사용: 재사용 항목 {}, 다시 쓴 항목 1, 처음부터 1(절차서 없음 1)".format(n)


def test_collect_measure_prints_the_line_only_when_there_is_a_decision(workspace, repo):
    settings(workspace)
    b = next_run(workspace, repo)
    p = run_script("collect", str(b), "--measure")
    assert p.returncode == 0 and "배포 계획 재사용" not in p.stdout   # 옛 실행은 지금 그대로다
    decide(b)
    p = run_script("collect", str(b), "--measure")
    assert p.returncode == 0, p.stdout + p.stderr
    assert "- 배포 계획 재사용: 재사용 항목 0, 다시 쓴 항목 0, 처음부터 1(절차서 없음 1)" in p.stdout
