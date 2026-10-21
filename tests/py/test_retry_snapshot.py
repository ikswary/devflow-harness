"""재시도의 수정 전 사본과 재시도 diff 도구 시험.

- `task_set.py --archive-judge`가 판정 파일을 옮긴 뒤 같은 n으로 `tasks/{id}/before.r{n}/`(MANIFEST.md, files/, 코드 kind면
  code.patch)을 뜨는지, 지금 동작(보관 이름·retry·「재시도 범위」)이 그대로인지, 코드 폴더를 바꾸지 않는지를 명령행으로 본다.
- `retry_diff.py`가 사본 뒤 바뀐 것만 `바뀜`·`새 파일`·`사본 밖 변경`·`--stat`으로 내는지를 같은 표본으로 본다.
- git 동작은 대역 없이 임시 폴더의 실제 git 저장소로 본다(7절 「tmp git 저장소」).
"""
import hashlib
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime

import pytest

from conftest import ROOT, run_script, write

import task_set

if shutil.which("git") is None:
    # 전제가 없으면 시작할 때 이유를 말하고 실패한다(test-rules ⑥)
    pytest.exit("git이 없음: 코드 task 사본 시험은 실제 git 저장소를 쓴다 — git을 설치하고 다시 돌린다", returncode=4)

ALT_SENTENCE = "판정자의 대안 문장은 그대로 옮기지 않고, 그 근거 줄과 원천을 열어 확인한 뒤 쓴다(어긋나면 원천을 따르고 「알릴 것」에 적는다)."
RETRY_SCOPE = ("- 회차 1 (보관한 판정: {}): 고칠 기준: 2. 그 기준 안에서는 판정자가 적지 않은 같은 종류의 결함도 고친다. "
               "다른 기준과 판정자의 권장은 고치지 않는다. " + ALT_SENTENCE)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def judge_text(prefix, tid):
    when = datetime.fromtimestamp(time.time() - 60).strftime("%Y-%m-%d %H:%M:%S")
    return "판정자: {}-{} {}\n\n## 통과 못 한 기준\n- 기준 2: 틀린 인용\n".format(prefix, tid, when)


def age(*paths):
    """표본 파일을 앞 판정보다 오래된 것으로 둔다(`사본 밖 변경`은 앞 판정 시각 뒤에 바뀐 파일만)."""
    old = time.time() - 3600
    for p in paths:
        os.utime(p, (old, old))


def front_value(task_md, key):
    for line in task_md.read_text(encoding="utf-8").splitlines()[1:]:
        if line.strip() == "---":
            return None
        if line.startswith(key + ":"):
            return line.split(":", 1)[1].strip()
    return None


def section(task_md, title):
    text = task_md.read_text(encoding="utf-8")
    body = text.split("## " + title + "\n", 1)[1]
    return body.split("\n## ", 1)[0].strip()


def manifest_section(snap, title):
    text = (snap / "MANIFEST.md").read_text(encoding="utf-8")
    body = text.split("## " + title + "\n", 1)[1]
    return [x for x in body.split("\n## ", 1)[0].splitlines() if x.strip()]


def block(output, start, stop=None):
    """출력에서 start 줄 다음부터 stop으로 시작하는 줄 앞까지."""
    lines = output.splitlines()
    i = lines.index(start) + 1
    out = []
    for line in lines[i:]:
        if stop and line.startswith(stop):
            break
        out.append(line)
    return out


# ---------------------------------------------------------------- 문서 task 표본

def doc_sample(run_dir):
    run = run_dir.path
    canon = write(run / "design" / "plan.md", "# 계획\n- 하나\n- 둘\n")
    other = write(run / "design" / "other.md", "밖 정본\n")
    untouched = write(run / "design" / "old.md", "그대로인 정본\n")
    task_md = run_dir.task("T001", "문서 표본", kind="design", status="자체검증",
                           sections={"건드릴 파일": "- design/plan.md"})
    result = run_dir.result("T001", "# T001 결과\n\n## 승인 화면\n### 알릴 것\n- 없음\n")
    revised = write(run_dir.task_dir("T001") / "revised" / "design" / "plan.md", "# 계획(고친 판)\n- 하나\n")
    judge = run_dir.judge("T001", judge_text("rjudge", "T001"))
    age(canon, other, untouched, result, revised)
    return {"task": task_md, "canon": canon, "other": other, "result": result, "revised": revised, "judge": judge}


def test_doc_snapshot_copies_result_canon_and_revised_and_keeps_archive_behaviour(run_dir):
    s = doc_sample(run_dir)
    judged = s["judge"].read_bytes()
    originals = {"tasks/T001/result.md": s["result"].read_bytes(), "design/plan.md": s["canon"].read_bytes(),
                 "tasks/T001/revised/design/plan.md": s["revised"].read_bytes()}

    r = run_script("task_set", run_dir, "T001", "--status", "진행", "--archive-judge")

    assert r.returncode == 0, r.output
    # 지금 동작 그대로: 보관 이름, retry, 「재시도 범위」 번호 줄
    tdir = run_dir.task_dir("T001")
    assert not (tdir / "judge.md").exists()
    assert (tdir / "judge.r1.md").read_bytes() == judged
    assert front_value(s["task"], "retry") == "1"
    assert section(s["task"], "재시도 범위") == RETRY_SCOPE.format("judge.r1.md")
    # 사본: 바이트가 같은 세 파일과 목록
    snap = tdir / "before.r1"
    for rel, data in originals.items():
        assert sha256((snap / "files" / rel).read_bytes()) == sha256(data), rel
    assert manifest_section(snap, "파일") == ["- {} | {} | {}".format(rel, len(data), sha256(data)[:16])
                                             for rel, data in originals.items()]
    assert manifest_section(snap, "코드") == ["- 없음(코드 폴더에 쓰지 않는 kind)"]
    assert not (snap / "code.patch").exists()
    lines = r.stdout.splitlines()
    total = sum(len(x) for x in originals.values())
    assert lines[lines.index("보관: judge.r1.md") + 1] == "사본: tasks\\T001\\before.r1 (파일 3, {}바이트)".format(total)


def test_archive_judge_retry_scope_line_tells_writer_to_verify_alternative_sentences_at_source(run_dir):
    doc_sample(run_dir)

    r = run_script("task_set", run_dir, "T001", "--status", "진행", "--archive-judge")

    assert r.returncode == 0, r.output
    assert ALT_SENTENCE in section(run_dir.task_dir("T001") / "task.md", "재시도 범위")


def test_retry_diff_on_doc_sample_reports_changed_same_new_and_outside(run_dir):
    s = doc_sample(run_dir)
    assert run_script("task_set", run_dir, "T001", "--status", "진행", "--archive-judge").returncode == 0
    # 사본 뒤에 더 고침: 정본 한 줄, 고친 판 폴더의 새 파일, 「건드릴 파일」 밖 design 파일
    write(s["canon"], "# 계획\n- 하나\n- 셋\n")
    write(run_dir.task_dir("T001") / "revised" / "design" / "new.md", "새 고친 판\n")
    write(s["other"], "밖 정본을 고침\n")

    r = run_script("retry_diff", run_dir, "T001")

    assert r.returncode == 0, r.output
    assert block(r.stdout, "파일:", "코드") == [
        "- tasks/T001/result.md | 같음",
        "- design/plan.md | 바뀜 +1 -1",
        "- tasks/T001/revised/design/plan.md | 같음",
        "- tasks/T001/revised/design/new.md | 새 파일",
        "- design/other.md | 사본 밖 변경",
    ]   # design/old.md(앞 판정 전에 바뀐 밖 정본)는 나오지 않는다
    full = run_script("retry_diff", run_dir, "T001", "--round", "1", "--full")
    assert full.returncode == 0, full.output
    assert "-- 둘" in full.stdout.splitlines() and "+- 셋" in full.stdout.splitlines()


# ---------------------------------------------------------------- 코드 task 표본(tmp git 저장소)

def git(repo, *args):
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")   # 상태를 재는 명령이 색인을 다시 쓰지 않게
    out = subprocess.run(["git", "-C", str(repo)] + list(args), capture_output=True, text=True, encoding="utf-8", env=env)
    assert out.returncode == 0, out.stderr
    return out.stdout


def repo_state(repo):
    """(git status --porcelain -uall, .git/index sha256, git count-objects -v)."""
    return (git(repo, "status", "--porcelain", "-uall"), sha256((repo / ".git" / "index").read_bytes()),
            git(repo, "count-objects", "-v"))


def code_sample(run_dir, tmp_path):
    repo = tmp_path / "code"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "t@example.com")
    git(repo, "config", "user.name", "t")
    write(repo / "a.txt", "하나\n둘\n셋\n")
    write(repo / "gone.txt", "지울 파일\n")
    (repo / "bin.dat").write_bytes(bytes(range(256)))
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "init")
    # 고치는 작성자 앞의 변경: 추적 파일 수정, 삭제, 추적 안 된 새 파일, 바이너리 파일 수정
    write(repo / "a.txt", "하나\n둘(고침)\n셋\n")
    (repo / "gone.txt").unlink()
    write(repo / "new.txt", "새 파일\n")
    (repo / "bin.dat").write_bytes(bytes(reversed(range(256))) + b"\0\1")
    run_dir.flow("s1", dir=str(repo), status="진행")
    run_dir.task("T002", "코드 표본", kind="implementation", block="구현", status="자체검증", flow="s1",
                 sections={"건드릴 파일": "- a.txt\n- new.txt"})
    run_dir.result("T002", "# T002 결과\n")
    run_dir.judge("T002", judge_text("rjudge", "T002"))
    write(run_dir.task_dir("T002") / "judge-run.md", judge_text("xjudge", "T002"))
    git(repo, "status", "--porcelain", "-uall")
    return repo


def test_code_snapshot_writes_patch_without_touching_code_folder(run_dir, tmp_path):
    repo = code_sample(run_dir, tmp_path)
    head = git(repo, "rev-parse", "HEAD").strip()
    before = repo_state(repo)

    r = run_script("task_set", run_dir, "T002", "--status", "진행", "--archive-judge")

    assert r.returncode == 0, r.output
    assert repo_state(repo) == before
    snap = run_dir.task_dir("T002") / "before.r1"
    patch = (snap / "code.patch").read_bytes()
    for path in ("a.txt", "gone.txt", "new.txt", "bin.dat"):
        assert "diff --git a/{0} b/{0}".format(path).encode() in patch, path
    assert b"GIT binary patch" in patch
    assert manifest_section(snap, "코드") == ["- 폴더: {} | HEAD: {} | patch: code.patch {} | 바뀐 파일 4".format(
        repo, head, len(patch))]
    assert [x.split(" | ")[0] for x in manifest_section(snap, "파일")] == ["- tasks/T002/result.md"]
    assert "보관: judge.r1.md, judge-run.r1.md" in r.stdout.splitlines()


def test_retry_diff_on_code_sample_shows_only_changes_after_snapshot(run_dir, tmp_path):
    repo = code_sample(run_dir, tmp_path)
    assert run_script("task_set", run_dir, "T002", "--status", "진행", "--archive-judge").returncode == 0
    # 사본 뒤에 더 고침: 추적 파일 한 줄, 새 파일 하나
    write(repo / "a.txt", "하나\n둘(고침)\n셋(또 고침)\n")
    write(repo / "new2.txt", "또 새 파일\n")
    git(repo, "status", "--porcelain", "-uall")
    before = repo_state(repo)

    r = run_script("retry_diff", run_dir, "T002")

    assert r.returncode == 0, r.output
    assert repo_state(repo) == before
    stat = [x.split("|")[0].strip() for x in block(r.stdout, "코드: {} (앞 판정 시점 → 지금 작업 트리)".format(repo))
            if "|" in x]
    assert stat == ["a.txt", "new2.txt"]
    assert "HEAD 바뀜" not in r.stdout
    assert "- tasks/T002/result.md | 같음" in r.stdout.splitlines()


def test_retry_diff_after_head_moved_builds_before_tree_from_snapshot_head(run_dir, tmp_path):
    repo = code_sample(run_dir, tmp_path)
    old_head = git(repo, "rev-parse", "HEAD").strip()
    assert run_script("task_set", run_dir, "T002", "--status", "진행", "--archive-judge").returncode == 0
    # 사본 뒤: 사본에 든 추적 파일 수정(a.txt)을 커밋해 HEAD를 바꾸고, 파일 하나(new.txt)를 더 고친다
    git(repo, "commit", "-q", "-m", "a.txt 반영", "--", "a.txt")
    new_head = git(repo, "rev-parse", "HEAD").strip()
    assert new_head != old_head
    write(repo / "new.txt", "새 파일\n더 고침\n")
    git(repo, "status", "--porcelain", "-uall")

    r = run_script("retry_diff", run_dir, "T002")

    assert r.returncode == 0, r.output
    assert r.stdout.splitlines()[0] == "HEAD 바뀜 {}→{}".format(old_head, new_head)
    stat = [x.split("|")[0].strip() for x in block(r.stdout, "코드: {} (앞 판정 시점 → 지금 작업 트리)".format(repo))
            if "|" in x]
    assert stat == ["new.txt"]   # 사본 뒤 더 고친 파일뿐. 커밋만 된 a.txt와 사본 때 이미 있던 변경은 나오지 않는다


# ---------------------------------------------------------------- 상한과 거부

def test_capped_file_is_listed_and_archive_still_succeeds(run_dir, monkeypatch, capsys):
    s = doc_sample(run_dir)
    big = "줄\n" * 2000
    write(s["canon"], big)
    monkeypatch.setattr(task_set, "SNAPSHOT_MAX_BYTES", 1000)

    code = task_set.main(["task_set.py", str(run_dir), "T001", "--status", "진행", "--archive-judge"])

    out = capsys.readouterr().out
    assert code == 0, out
    snap = run_dir.task_dir("T001") / "before.r1"
    size = len(big.encode("utf-8"))
    assert "- design/plan.md | 사본 없음(상한) | {}".format(size) in manifest_section(snap, "파일")
    assert not (snap / "files" / "design" / "plan.md").exists()
    assert (snap / "files" / "tasks" / "T001" / "result.md").is_file()   # 상한 안의 파일은 그대로 뜬다
    assert "빠진 것 1)" in out
    r = run_script("retry_diff", run_dir, "T001")
    assert r.returncode == 0, r.output
    assert "- design/plan.md | 사본 없음(상한)" in r.stdout.splitlines()


def test_capped_patch_is_replaced_by_changed_file_list(run_dir, tmp_path, monkeypatch, capsys):
    repo = code_sample(run_dir, tmp_path)
    monkeypatch.setattr(task_set, "SNAPSHOT_MAX_BYTES", 10)

    code = task_set.main(["task_set.py", str(run_dir), "T002", "--status", "진행", "--archive-judge"])

    out = capsys.readouterr().out
    assert code == 0, out
    snap = run_dir.task_dir("T002") / "before.r1"
    assert not (snap / "code.patch").exists()
    lines = manifest_section(snap, "코드")
    assert " | patch: 사본 없음(상한) " in lines[0]
    assert sorted(lines[1:]) == sorted("- 바뀐 파일: " + x for x in git(repo, "status", "--porcelain", "-uall").splitlines())
    r = run_script("retry_diff", run_dir, "T002")
    assert r.returncode == 0, r.output
    assert any(x.startswith("코드: patch 사본 없음(상한)") for x in r.stdout.splitlines())


def test_rejected_archive_leaves_no_snapshot(run_dir):
    run_dir.task("T001", "상한", kind="design", status="자체검증", retry="2")
    run_dir.judge("T001", judge_text("rjudge", "T001"))
    run_dir.task("T003", "판정 없음", kind="design", status="자체검증")

    capped = run_script("task_set", run_dir, "T001", "--status", "진행", "--archive-judge")
    missing = run_script("task_set", run_dir, "T003", "--status", "진행", "--archive-judge")

    assert capped.returncode == 3 and "재시도 상한 2" in capped.stdout, capped.output
    assert missing.returncode == 3 and "보관할 판정 파일(judge.md·judge-run.md)이 없음" in missing.stdout, missing.output
    for tid in ("T001", "T003"):
        assert [p.name for p in run_dir.task_dir(tid).iterdir() if p.name.startswith("before.r")] == []
    assert (run_dir.task_dir("T001") / "judge.md").is_file()


def test_retry_diff_without_snapshot_exits_2(run_dir):
    run_dir.task("T001", "사본 없음", kind="design", status="진행")

    r = run_script("retry_diff", run_dir, "T001")

    assert r.returncode == 2, r.output
    assert r.stdout.strip() == "사본 없음: tasks\\T001\\before.r*"


# ---------------------------------------------------------------- 재판정 흐름에 연결(T097)
# 메인이 재판정자에게 주는 사본 경로·명령·규칙 파일 경로(selfcheck.md)와, 재판정자가 그때만 읽는 규칙(rejudge.md)을 글로 보고,
# 문서의 명령을 그대로 돌려 사본 뒤 바뀐 파일과 같은 파일을 맞게 내는지 본다.

SNAPSHOT_PATH = "`tasks\\{id}\\before.r{n}\\`"
COMMAND = "python ${CLAUDE_PLUGIN_ROOT}/scripts/retry_diff.py {실행 폴더} {id}"
MARKERS = ("사본 없음", "사본 밖 변경", "새 파일", "HEAD 바뀜")
REJUDGE = "references/roles/rejudge.md"


def rejudge_sentence(path, start):
    """문서에서 start로 시작하는 문장이 든 줄(없으면 이유를 말하고 실패)."""
    lines = [x for x in (ROOT / path).read_text(encoding="utf-8").splitlines() if start in x]
    assert len(lines) == 1, "{}에 '{}' 줄이 하나가 아님: {}".format(path, start, len(lines))
    return lines[0]


def test_main_selfcheck_gives_rejudge_snapshot_path_and_retry_diff_command():
    line = rejudge_sentence("references/main/selfcheck.md", "재판정은 새 판정자가 하고")
    rest = line.split("재판정은 새 판정자가 하고", 1)[1]
    assert "범위는 실패 기준 + 수정이 닿은 제품 코드·시험·설정·의존성·공용 계약의 검사다." in rest
    assert "읽기 재판정자 프롬프트" in rest and SNAPSHOT_PATH in rest and "`" + COMMAND + "`" in rest
    assert "`${CLAUDE_PLUGIN_ROOT}/" + REJUDGE + "`" in rest and (ROOT / REJUDGE).is_file()
    assert "영향을 가릴 근거가 없으면 더 넓은 묶음 또는 전체 검사를 돌린다." in rest
    assert "상속" not in line and "물려받" not in line


def test_rejudge_rule_runs_retry_diff_and_rereads_sources_on_four_markers():
    assert (ROOT / REJUDGE).is_file(), "재판정 때만 읽는 규칙 파일 {}이 없음".format(REJUDGE)
    assert "읽는 때: 읽기 재판정자, 메인이 프롬프트로 경로를 줄 때." in (ROOT / REJUDGE).read_text(encoding="utf-8").splitlines()
    line = rejudge_sentence(REJUDGE, "**재판정**")
    assert "「재시도 범위」" in line and "`retry_diff.py`" in line
    assert "「확인 방법 요약」에 한 줄로 적고" in line
    assert "바뀐 파일·덩어리가 닿은 제품 코드·시험·설정·의존성·공용 계약의 기준을 다시 판정한다" in line
    tool = (ROOT / "scripts" / "retry_diff.py").read_text(encoding="utf-8")
    for marker in MARKERS:
        assert "`{}`".format(marker) in line, marker
        assert marker in tool, marker   # 도구가 실제로 내는 표지
    assert "영향 범위를 가릴 근거가 없으면 원천과 검사를 더 넓게 본다." in line
    assert line.endswith("같은 URL이나 같은 tree만으로 DB 상태가 같다고 보지 않는다.")
    text = (ROOT / REJUDGE).read_text(encoding="utf-8")
    assert "상속" not in text and "물려받" not in text and "판정 로그" not in text


def test_documented_rejudge_command_reports_changed_revision_and_same_files(run_dir):
    line = rejudge_sentence("references/main/selfcheck.md", "재판정은 새 판정자가 하고")
    assert "`" + COMMAND + "`" in line, "selfcheck.md에 재판정자에게 줄 retry_diff 명령이 없음"
    s = doc_sample(run_dir)
    assert run_script("task_set", run_dir, "T001", "--status", "진행", "--archive-judge").returncode == 0
    snap = run_dir.path / SNAPSHOT_PATH.strip("`").format(id="T001", n=1).replace("\\", "/")
    assert (snap / "MANIFEST.md").is_file()   # 문서가 가리키는 사본 경로에 사본이 있다
    # 고치는 작성자가 고친 판만 고친다(정본·결과는 그대로)
    write(s["revised"], "# 계획(고친 판)\n- 하나(고침)\n- 둘\n")
    argv = COMMAND.replace("{실행 폴더}", str(run_dir.path)).replace("{id}", "T001").split(" ")
    assert argv[:2] == ["python", "${CLAUDE_PLUGIN_ROOT}/scripts/retry_diff.py"]
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    r = subprocess.run([sys.executable, "-B", str(ROOT / "scripts" / "retry_diff.py")] + argv[2:],
                       capture_output=True, text=True, encoding="utf-8", env=env, timeout=120)

    assert r.returncode == 0, r.stdout + r.stderr
    assert block(r.stdout, "파일:", "코드") == [
        "- tasks/T001/result.md | 같음",
        "- design/plan.md | 같음",
        "- tasks/T001/revised/design/plan.md | 바뀜 +2 -1",
    ]
