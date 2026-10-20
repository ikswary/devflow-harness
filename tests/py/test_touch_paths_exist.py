"""「건드릴 파일」 경로 확인 경고 시험.

- `task_set.py --add "건드릴 파일|…"`와 `new`가 줄의 경로를 기준 폴더에서 확인해 `! 건드릴 파일:` 경고를 내는지를 명령행으로 본다.
  기준 폴더는 코드를 쓰는 kind면 flow.md의 `dir`, 그 밖은 실행 폴더다.
- 경고는 거부가 아니다: 종료 코드와 머리 파일의 더한 줄은 검사가 없던 때와 같다.
"""
from conftest import run_script, write

WARN = "! 건드릴 파일:"
NOT_FOUND = "! 건드릴 파일: {} — 없는 경로(새 파일이면 그대로)"
NO_MATCH = "! 건드릴 파일: {} — 맞는 파일 없음"


def warnings(r):
    return [x for x in r.stdout.splitlines() if x.startswith(WARN)]


def touch_section(task_md):
    text = task_md.read_text(encoding="utf-8")
    return text.split("## 건드릴 파일\n", 1)[1].split("\n## ", 1)[0].strip().splitlines()


def code_sample(run_dir, tmp_path):
    repo = tmp_path / "code"
    write(repo / "scripts" / "kinds.py", "# kinds\n")
    write(repo / "references" / "main" / "a.md", "# a\n")
    run_dir.flow("s1", dir=str(repo), status="진행")
    return run_dir.task("T002", "코드 표본", kind="implementation", block="구현", status="대기", flow="s1",
                        sections={"건드릴 파일": "- scripts/task_set.py"})


def add(run_dir, line):
    return run_script("task_set", run_dir, "T002", "--add", "건드릴 파일|" + line)


def test_add_warns_once_for_wrong_path_and_for_pattern_with_no_match_without_changing_result(run_dir, tmp_path):
    task = code_sample(run_dir, tmp_path)

    wrong = add(run_dir, "- scripts/devflow/kinds.py — 설명")
    pattern = add(run_dir, "- skills/devflow-harness/references/main/*.md")

    assert wrong.returncode == 0 and pattern.returncode == 0, wrong.output + pattern.output
    assert warnings(wrong) == [NOT_FOUND.format("scripts/devflow/kinds.py")]
    assert warnings(pattern) == [NO_MATCH.format("skills/devflow-harness/references/main/*.md")]
    # 머리 파일: 검사가 없던 때와 같이 줄이 그대로 더해진다
    assert touch_section(task) == ["- scripts/task_set.py", "- scripts/devflow/kinds.py — 설명",
                                   "- skills/devflow-harness/references/main/*.md"]
    assert wrong.stdout.splitlines()[-1] == "T002: 대기 (상태 그대로)"


def test_add_prints_no_warning_for_existing_path_and_matching_pattern(run_dir, tmp_path):
    task = code_sample(run_dir, tmp_path)

    path = add(run_dir, "- scripts/kinds.py")
    pattern = add(run_dir, "- references/main/*.md")

    assert path.returncode == 0 and pattern.returncode == 0, path.output + pattern.output
    assert warnings(path) == [] and warnings(pattern) == []
    assert touch_section(task) == ["- scripts/task_set.py", "- scripts/kinds.py", "- references/main/*.md"]


def test_add_to_other_section_does_not_check_paths(run_dir, tmp_path):
    code_sample(run_dir, tmp_path)

    r = run_script("task_set", run_dir, "T002", "--add", "범위|- scripts/devflow/kinds.py를 고친다")

    assert r.returncode == 0, r.output
    assert warnings(r) == []


def new_task(run_dir, tmp_path, kind, touch, flow=None):
    body = write(tmp_path / "body-{}.md".format(kind), "## 범위\n- 표본\n\n## 판정 기준\n1. 표본\n\n## 건드릴 파일\n{}\n".format(touch))
    args = ["new", "--kind", kind, "--title", "표본", "--body-from", body]
    if flow:
        args += ["--flow", flow, "--block", "구현"]
    return run_script("task_set", run_dir, *args)


def test_new_change_checks_paths_against_run_folder(run_dir, tmp_path):
    write(run_dir.path / "design" / "real.md", "# 정본\n")

    r = new_task(run_dir, tmp_path, "change", "- design\\x.md\n- design\\real.md")

    assert r.returncode == 0, r.output
    assert warnings(r) == [NOT_FOUND.format("design\\x.md")]
    assert r.stdout.splitlines()[-1] == "T001"
    # 머리 파일의 「건드릴 파일」은 적은 그대로다
    assert touch_section(run_dir.task_dir("T001") / "task.md") == ["- design\\x.md", "- design\\real.md"]


def test_new_code_kind_without_flow_md_dir_says_so_once_and_does_not_check(run_dir, tmp_path):
    r = new_task(run_dir, tmp_path, "implementation", "- scripts/devflow/kinds.py", flow="s9")

    assert r.returncode == 0, r.output
    assert warnings(r) == ["! 건드릴 파일: 코드 폴더를 찾지 못해 경로를 확인하지 않음(flows\\s9\\flow.md dir)"]
    assert r.stdout.splitlines()[-1] == "T001"


def test_new_change_reads_workspace_relative_forms_against_run_folder(run_dir, tmp_path):
    write(run_dir.path / "design" / "real.md", "# 정본\n")
    name = run_dir.path.name

    r = new_task(run_dir, tmp_path, "change",
                 "- _workspace/{0}/design/real.md\n- {0}/design/real.md\n- _workspace/{0}/design/x.md".format(name))

    assert r.returncode == 0, r.output
    assert warnings(r) == [NOT_FOUND.format("_workspace/{}/design/x.md".format(name))]
    assert r.stdout.splitlines()[-1] == "T001"
    assert touch_section(run_dir.task_dir("T001") / "task.md") == [
        "- _workspace/{0}/design/real.md".format(name), "- {0}/design/real.md".format(name),
        "- _workspace/{0}/design/x.md".format(name)]


def test_new_change_run_folder_absolute_path_has_no_warning(run_dir, tmp_path):
    write(run_dir.path / "design" / "real.md", "# 정본\n")

    r = new_task(run_dir, tmp_path, "change", "- {}\n- {}".format(run_dir.path / "design" / "real.md",
                                                                  run_dir.path / "design" / "x.md"))

    assert r.returncode == 0, r.output
    # 있는 파일은 경고 0, 없는 파일(양성 대조)은 적은 절대 경로 그대로 한 줄: 확인을 건너뛰면 둘째가 사라진다
    assert warnings(r) == [NOT_FOUND.format(str(run_dir.path / "design" / "x.md"))]
