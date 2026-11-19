"""같은 흐름 코드 행의 자동 의존 좁힘(설계 harness-defects 5절 S, AC-28, D-36~D-40): `spawn_children.py`.

부모 `started_version`이 1.3.1 이상이면 같은 흐름 코드 행은 이 자식 목록의 앞 코드 행 가운데 「건드릴 파일」이 겹치는 행 모두와
「시그니처와 결정 번호」에 `[계약]`이 든 행 모두에만 자동으로 의존한다. `recon.md` `- 덧붙이기 파일:` 줄의 파일은 겹침으로 세지 않고,
의존성 목록 파일은 겹침으로 센다. 부모가 1.3.1 앞이면 바로 앞 코드 행에 의존한다(옛 대조는 test_scenarios s05·test_screen_ac_kind·golden).
"""
import pytest

from conftest import run_script, write

NOW = "2026-11-19 12:00:00"
APPEND = "# 프로젝트 정찰\n\n## 저장소 제약\n- 덧붙이기 파일: `CHANGELOG.md`\n"


def row(title, touch, sig="(없음)", depends="", kind="implementation", flow="orders"):
    lines = ["### 자식: " + title, "- kind: " + kind, "- flow: " + flow, "- depends_on: " + depends, "- difficulty: 일반",
             "- closes_ac: ", "- partial_ac: ", "- 한 줄: " + title,
             "#### 범위", "- " + title, "#### 판정 기준", "1. " + title + "이 있다",
             "#### 건드릴 파일", "\n".join("- " + p for p in touch), "#### 시그니처와 결정 번호", sig]
    return "\n".join(lines) + "\n\n"


def parent(run_dir, version, rows, recon=None, kind="design", docs=None):
    """완료된 부모 T001(시작 판본 version)과 그 자식 목록. recon이 있으면 recon.md, docs가 있으면 프로젝트 설정의 문서 경로."""
    run_dir.task("T001", "주문 설계", kind=kind, status="완료", started_version=version)
    if recon is not None:
        write(run_dir.path / "recon.md", recon)
    if docs is not None:
        write(run_dir.path.parent / "devflow-harness.project.md",
              "# 프로젝트 설정\n\n- 개발 기준 브랜치: main\n\n## 경로 목록\n- 감지한 실행: dryrun\n"
              "- 화면 경로: 없음\n- 인프라 경로: 없음\n- 문서 경로: {}\n".format(docs))
    run_dir.result("T001", "# T001 결과\n\n## 승인 화면\n### 정해 주실 것\n- 없음\n\n## 자식 목록\n나눈 기준: 마른 시험\n\n"
                   + "".join(rows) + "## 규약 추가\n없음\n")


def spawn(run_dir, *extra):
    return run_script("spawn_children", run_dir, "T001", "--now", NOW, *extra)


def depends_by_title(stdout):
    """dry-run 출력 줄 `{id} {제목} [{kind}] 흐름={흐름} 의존={id,…}…` → {제목: (id, [의존])}."""
    out = {}
    for line in stdout.splitlines():
        if " 흐름=" not in line or " 의존=" not in line:
            continue
        tid, rest = line.split(" ", 1)
        title = rest.split(" [", 1)[0]
        dep = line.split(" 의존=", 1)[1].split(" ", 1)[0]
        out[title] = (tid, [] if dep == "-" else dep.split(","))
    return out


ABCD = [row("A", ["src/a.py", "CHANGELOG.md"]), row("B", ["src/b.py", "CHANGELOG.md"]),
        row("C", ["src/a.py", "src/b.py", "CHANGELOG.md"]), row("D", ["src/d.py", "CHANGELOG.md"])]


# --- 판정 기준 1·2·6: 덧붙이기 줄 있음/없음, 옛 부모 ---------------------------------------------------------------

def test_rows_depend_only_on_earlier_rows_touching_the_same_files_besides_append_files(run_dir):
    parent(run_dir, "1.3.1", ABCD, recon=APPEND)

    r = spawn(run_dir, "--dry-run")

    assert r.returncode == 0, r.output
    got = depends_by_title(r.stdout)
    assert [got[t][0] for t in "ABCD"] == ["T002", "T003", "T004", "T005"]
    assert got["B"][1] == [] and got["D"][1] == []
    assert got["C"][1] == ["T002", "T003"]   # 겹치는 앞 행 모두(가장 가까운 하나가 아니라)
    assert "T005 D [implementation] 흐름=orders 의존=- (dry-run)" in r.stdout.splitlines()   # 출력 줄 꼴은 그대로


def test_without_append_line_the_changelog_overlaps_every_earlier_row(run_dir):
    parent(run_dir, "1.3.1", ABCD, recon="# 프로젝트 정찰\n\n## 저장소 제약\n- 없음\n")

    r = spawn(run_dir, "--dry-run")

    assert r.returncode == 0, r.output
    got = depends_by_title(r.stdout)
    assert got["A"][1] == []
    assert got["B"][1] == ["T002"]
    assert got["C"][1] == ["T002", "T003"]
    assert got["D"][1] == ["T002", "T003", "T004"]


def test_parent_started_before_1_3_1_keeps_the_chain_to_the_previous_code_row(run_dir):
    parent(run_dir, "1.3.0", ABCD, recon=APPEND)

    r = spawn(run_dir, "--dry-run")

    assert r.returncode == 0, r.output
    got = depends_by_title(r.stdout)
    assert [got[t][1] for t in "ABCD"] == [[], ["T002"], ["T003"], ["T004"]]


# --- 판정 기준 3: [계약] 앞 행 ---------------------------------------------------------------------------------

def test_contract_row_is_waited_for_even_without_file_overlap_but_decision_numbers_alone_are_not(run_dir):
    parent(run_dir, "1.3.1", [row("계약 행", ["src/api.py"], sig="- `[계약]` 주문 응답 형식, D-1"),
                              row("결정 행", ["src/rule.py"], sig="- D-2"),
                              row("뒤 행", ["src/view.py"])], recon=APPEND)

    r = spawn(run_dir, "--dry-run")

    assert r.returncode == 0, r.output
    got = depends_by_title(r.stdout)
    assert got["결정 행"][1] == ["T002"]
    assert got["뒤 행"][1] == ["T002"]   # [계약] 행에만. 결정 번호만 적은 T003에는 의존하지 않는다


# --- 판정 기준 4: 의존성 목록 파일, 덧붙이기 파일뿐인 행 ------------------------------------------------------------

def test_dependency_list_file_overlaps_any_row_and_append_only_row_waits_for_none(run_dir):
    parent(run_dir, "1.3.1", [row("앞 행", ["src/a.py", "CHANGELOG.md"]),
                              row("의존성 행", ["requirements.txt", "CHANGELOG.md"]),
                              row("이력 행", ["CHANGELOG.md"])], recon=APPEND)

    r = spawn(run_dir, "--dry-run")

    assert r.returncode == 0, r.output
    got = depends_by_title(r.stdout)
    assert got["의존성 행"][1] == ["T002"]
    assert got["이력 행"][1] == []


# --- 판정 기준 5: 적은 depends_on, 문서 행, [백로그] 행 ------------------------------------------------------------

def test_written_depends_stay_and_docs_and_backlog_rows_are_outside_the_order(run_dir):
    run_dir.task("T002", "앞 실행 task", kind="implementation", block="구현", flow="other", status="완료")
    parent(run_dir, "1.3.1", [row("앞 행", ["src/a.py", "docs/guide.md"]),
                              row("문서 행", ["docs/guide.md"]),
                              row("[백로그] 미룬 행", ["src/a.py"]),
                              row("뒤 행", ["docs/guide.md", "src/c.py"], depends="앞 행, T002"),
                              row("끝 행", ["src/a.py", "src/c.py"])],
           recon=APPEND, docs="docs/**")

    r = spawn(run_dir, "--dry-run")

    assert r.returncode == 0, r.output
    got = depends_by_title(r.stdout)
    assert [got[t][0] for t in ("앞 행", "문서 행", "[백로그] 미룬 행", "뒤 행", "끝 행")] == ["T003", "T004", "T005", "T006", "T007"]
    assert got["문서 행"][1] == [] and "문서 행(자동 의존 없음)" in r.stdout   # 앞 행과 겹쳐도 받지 않음
    assert got["[백로그] 미룬 행"][1] == []
    assert got["뒤 행"][1] == ["T003", "T002"]   # 적은 의존 그대로. 겹치는 문서 행 T004는 앞 코드 행이 아님
    assert got["끝 행"][1] == ["T003", "T006"]   # 겹치는 [백로그] 행 T005는 앞 코드 행이 아님


# --- 판정 기준 7: --replace로 바꾸는 행이 그 흐름의 첫 코드 행 -------------------------------------------------------

def test_replaced_first_code_row_keeps_its_old_same_flow_code_dependency(run_dir):
    run_dir.task("T002", "앞 코드", kind="implementation", block="구현", flow="orders", status="진행")
    run_dir.task("T003", "B", kind="implementation", block="구현", flow="orders", status="대기", depends_on=["T002"])
    parent(run_dir, "1.3.1", [row("B", ["src/b.py", "CHANGELOG.md"]), row("D", ["src/d.py", "CHANGELOG.md"])],
           recon=APPEND, kind="change")

    r = run_script("spawn_children", run_dir, "T001", "--replace", "--now", NOW)

    assert r.returncode == 0, r.output
    tasks = run_dir.tasks()
    assert tasks["T003"]["depends_on"] == ["T002"]   # 원래 의존(같은 흐름 코드 task)이 남음
    assert tasks["T004"]["depends_on"] == []          # 목록 밖 T002와는 겹침을 보지 않음


# --- 판정 기준 8: 머리 파일의 depends_on이 dry-run 출력과 같다 -----------------------------------------------------

def test_head_files_get_the_dry_run_dependencies(run_dir):
    parent(run_dir, "1.3.1", ABCD, recon=APPEND)
    dry = depends_by_title(spawn(run_dir, "--dry-run").stdout)

    r = spawn(run_dir)

    assert r.returncode == 0, r.output
    tasks = run_dir.tasks()
    assert {t: tasks[dry[t][0]]["depends_on"] for t in "ABCD"} == {t: dry[t][1] for t in "ABCD"}
    assert tasks["T004"]["depends_on"] == ["T002", "T003"]


@pytest.mark.parametrize("line", ["- 덧붙이기 파일: CHANGELOG.md, docs/HISTORY.md", "* 덧붙이기 파일 : `CHANGELOG.md`, `./docs/HISTORY.md`"])
def test_append_files_reads_the_recon_line(run_dir, line):
    import slots
    write(run_dir.path / "recon.md", "# 정찰\n\n" + line + "\n")
    assert slots.append_files(str(run_dir.path)) == {"CHANGELOG.md", "docs/HISTORY.md"}


def test_append_files_is_empty_without_the_line(run_dir):
    import slots
    assert slots.append_files(str(run_dir.path)) == set()
    write(run_dir.path / "recon.md", "# 정찰\n\n- 의존성 목록: deps.txt\n")
    assert slots.append_files(str(run_dir.path)) == set()
