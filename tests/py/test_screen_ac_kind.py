"""영역 규칙의 자식 행 쪽(설계 domain 3.3): `spawn_children.py`의 화면 id 대조(fe 강제), 영역 판정 기준 주입,
문서 행의 자동 의존 제외. 경로 대조 함수 `path_in_list`의 예 패턴 표(설계 문서 5.1)도 여기서 본다.

가짜 실행 폴더(`RunDir`)에 상세 정본 `spec\\*.md`, 프로젝트 설정(실행 폴더의 부모 폴더), 부모 결과를 두고 명령행으로 돌린다.
규칙은 부모의 `started_version`이 1.1.0 이상일 때만 켜진다.
"""
import os

import pytest

from conftest import run_script, write

NOW = "2026-10-30 12:00:00"

SPEC_ORDERS = ("# 주문 상세 요구사항\n\n## 인수 기준\n"
               "- AC-01 [화면: S-01] 주문 목록에 최근 주문이 보인다\n"
               "- AC-02: 주문 합계를 계산한다\n"
               "### AC-03-1 [화면: S-03, S-02] 상세에서 취소한다\n"
               "- AC-01 다시 [화면: S-09]: 처음 나온 줄만 본다\n")


def parent(run_dir, version, spec=SPEC_ORDERS, paths=None, rows=()):
    """완료된 설계 부모 T001(시작 판본 version)과 그 자식 목록, 상세 정본, 프로젝트 설정의 「경로 목록」을 둔다."""
    run_dir.task("T001", "주문 설계", status="완료", started_version=version)
    if spec is not None:
        write(run_dir.path / "spec" / "orders.md", spec)
    if paths is not None:
        write(run_dir.path.parent / "devflow-harness.project.md",
              "# 프로젝트 설정\n\n- 개발 기준 브랜치: main\n\n## 경로 목록\n- 감지한 실행: dryrun\n"
              + "".join("- {} 경로: {}\n".format(k, paths.get(k, "없음")) for k in ("화면", "인프라", "문서")))
    run_dir.result("T001", "# T001 결과\n\n## 승인 화면\n### 정해 주실 것\n- 없음\n\n## 자식 목록\n나눈 기준: 마른 시험\n\n"
                   + "".join(rows) + "## 규약 추가\n없음\n")


def row(title, kind="implementation", flow="orders", closes="", partial="", scope=None, sig="", touch="- src/orders.py"):
    lines = ["### 자식: " + title, "- kind: " + kind, "- flow: " + flow, "- depends_on: ", "- difficulty: 일반",
             "- closes_ac: " + closes, "- partial_ac: " + partial, "- 한 줄: " + title,
             "#### 범위", scope or "- " + title, "#### 판정 기준", "1. " + title + "이 있다",
             "#### 건드릴 파일", touch, "#### 시그니처와 결정 번호", sig or "(없음)"]
    return "\n".join(lines) + "\n\n"


def spawn(run_dir, *extra):
    return run_script("spawn_children", run_dir, "T001", "--now", NOW, *extra)


def made(run_dir):
    return sorted(os.listdir(run_dir.path / "tasks"))


# --- (가)(나) 화면 id가 붙은 인수 기준을 닫는 행은 fe-implementation ---------------------------------------------

def test_screen_ac_row_must_be_fe_implementation(run_dir):
    parent(run_dir, "1.1.0", rows=[row("목록 화면", closes="AC-01, AC-02")])

    r = spawn(run_dir)

    assert r.returncode == 3, r.output
    assert "- 화면 id가 붙은 인수 기준 AC-01(S-01)을 닫는 행은 fe-implementation: 목록 화면" in r.stdout.splitlines()
    assert made(run_dir) == ["T001"]


def test_screen_ac_row_as_fe_implementation_is_made(run_dir):
    # 양성 대조: 같은 행을 fe-implementation으로 쓰면 만든다
    parent(run_dir, "1.1.0", rows=[row("목록 화면", kind="fe-implementation", closes="AC-01, AC-02")])

    r = spawn(run_dir)

    assert r.returncode == 0, r.output
    assert made(run_dir) == ["T001", "T002"]
    assert run_dir.tasks()["T002"]["kind"] == "fe-implementation"


def test_screen_ac_check_lists_every_screen_ac_and_ignores_partial(run_dir):
    parent(run_dir, "1.1.0", rows=[row("상세 취소", kind="be-implementation", closes="AC-03-1, AC-01"),
                                   row("합계", closes="AC-02", partial="AC-01")])

    r = spawn(run_dir)

    assert r.returncode == 3, r.output
    lines = r.stdout.splitlines()
    assert "- 화면 id가 붙은 인수 기준 AC-03-1(S-02, S-03), AC-01(S-01)을 닫는 행은 fe-implementation: 상세 취소" in lines
    assert "자식 목록의 형식 문제 1건. 머리 파일을 만들지 않았다." in lines   # partial_ac만 화면 인수 기준인 행은 막지 않는다


def test_screen_ac_check_is_off_for_parent_started_before_1_1_0(run_dir):
    parent(run_dir, "1.0.4", rows=[row("목록 화면", closes="AC-01, AC-02")])

    r = spawn(run_dir)

    assert r.returncode == 0, r.output
    assert made(run_dir) == ["T001", "T002"]
    assert run_dir.tasks()["T002"]["kind"] == "implementation"


# --- (다) 영역 판정 기준 주입 ------------------------------------------------------------------------------------

def criteria(lib, key, **fill):
    return lib.DOMAIN_CRITERIA[key].format(**fill)


def test_fix_row_gets_domain_criteria_from_each_source(run_dir, lib):
    parent(run_dir, "1.1.0", paths={"화면": "client/**, src/routes/**"}, rows=[
        row("목록 수정", kind="fix", closes="AC-01", scope="- V-01: 상세 취소(AC-03-1)가 두 번 돈다",
            sig="- `cancel(id)` [계약]", touch="- client/list.tsx\n- src/orders.py"),
        row("합계 수정", kind="fix", closes="AC-02", touch="- src/total.py"),
    ])

    r = spawn(run_dir)

    assert r.returncode == 0, r.output
    expected = "\n".join([
        "1. 목록 수정이 있다",
        lib.DOMAIN_CRITERIA_HEAD,
        "2. " + criteria(lib, "화면", **{"묶음": "orders", "화면 id": "S-01", "번호": "AC-01"}),
        "3. " + criteria(lib, "화면", **{"묶음": "orders", "화면 id": "S-02, S-03", "번호": "AC-03-1"}),
        "4. " + lib.DOMAIN_CRITERIA["계약"],
        "5. " + criteria(lib, "화면 경로", 경로="client/list.tsx"),
    ])
    assert "(스크립트 주입: 영역 판정)" == lib.DOMAIN_CRITERIA_HEAD
    tasks = run_dir.tasks()
    assert tasks["T002"]["_sections"]["판정 기준"] == expected
    assert (run_dir.task_dir("T002") / "criteria.orig.md").read_text(encoding="utf-8") == expected + "\n"
    assert any(l.startswith("T002 목록 수정 [fix]") and l.endswith(" 영역 판정 4줄") for l in r.stdout.splitlines()), r.stdout
    # 원천(화면 id가 붙은 인수 기준, [계약], 화면 경로)이 없는 수정 행에는 주입 줄이 없다
    assert tasks["T003"]["_sections"]["판정 기준"] == "1. 합계 수정이 있다"
    assert (run_dir.task_dir("T003") / "criteria.orig.md").read_text(encoding="utf-8") == "1. 합계 수정이 있다\n"


def test_implementation_row_gets_only_screen_path_criterion(run_dir, lib):
    parent(run_dir, "1.1.0", paths={"화면": "client/**"}, rows=[
        row("합계 화면", closes="AC-02", partial="AC-01", sig="[계약]", touch="- client/total.tsx\n- src/total.py")])

    r = spawn(run_dir)

    assert r.returncode == 0, r.output
    assert run_dir.tasks()["T002"]["_sections"]["판정 기준"] == "\n".join([
        "1. 합계 화면이 있다", lib.DOMAIN_CRITERIA_HEAD, "2. " + criteria(lib, "화면 경로", 경로="client/total.tsx")])


def test_fix_row_gets_no_criteria_for_parent_started_before_1_1_0(run_dir):
    parent(run_dir, "1.0.4", paths={"화면": "client/**"}, rows=[
        row("목록 수정", kind="fix", closes="AC-01", sig="[계약]", touch="- client/list.tsx")])

    r = spawn(run_dir)

    assert r.returncode == 0, r.output
    assert run_dir.tasks()["T002"]["_sections"]["판정 기준"] == "1. 목록 수정이 있다"


# --- (라) 문서 행의 자동 의존 제외 --------------------------------------------------------------------------------

DOC_ROWS = [row("코드 앞", touch="- src/a.py"),
            row("안내 문서", touch="- docs/guide.md (사용 안내)\n- README.md"),
            row("코드 뒤", touch="- src/c.py")]


def test_docs_row_skips_flow_auto_dependency(run_dir):
    parent(run_dir, "1.1.0", paths={"문서": "docs/**, README.md"}, rows=DOC_ROWS)

    r = spawn(run_dir, "--dry-run")

    assert r.returncode == 0, r.output
    lines = r.stdout.splitlines()
    assert "T002 코드 앞 [implementation] 흐름=orders 의존=- (dry-run)" in lines
    assert "T003 안내 문서 [implementation] 흐름=orders 의존=- 문서 행(자동 의존 없음) (dry-run)" in lines
    assert "T004 코드 뒤 [implementation] 흐름=orders 의존=T002 (dry-run)" in lines   # 문서 행이 아닌 앞 코드 행


def test_docs_rule_is_off_for_parent_started_before_1_1_0(run_dir):
    # 대조: 같은 행을 옛 규칙으로 만들면 차례대로 잇는다
    parent(run_dir, "1.0.4", paths={"문서": "docs/**, README.md"}, rows=DOC_ROWS)

    r = spawn(run_dir, "--dry-run")

    assert r.returncode == 0, r.output
    lines = r.stdout.splitlines()
    assert "T003 안내 문서 [implementation] 흐름=orders 의존=T002 (dry-run)" in lines
    assert "T004 코드 뒤 [implementation] 흐름=orders 의존=T003 (dry-run)" in lines


def test_row_with_a_code_path_is_not_docs_row(run_dir):
    parent(run_dir, "1.1.0", paths={"문서": "docs/**"}, rows=[
        row("코드 앞", touch="- src/a.py"), row("섞인 행", touch="- docs/guide.md\n- src/b.py")])

    r = spawn(run_dir, "--dry-run")

    assert r.returncode == 0, r.output
    assert "T003 섞인 행 [implementation] 흐름=orders 의존=T002 (dry-run)" in r.stdout.splitlines()


# --- (마) 두 상세 정본에 같은 인수 기준 번호 -----------------------------------------------------------------------

def test_duplicate_ac_number_warns_and_does_not_reject(run_dir):
    parent(run_dir, "1.1.0", rows=[row("배송 화면", closes="AC-05")])
    write(run_dir.path / "spec" / "delivery.md", "## 인수 기준\n- AC-05 [화면: S-05] 배송 상태가 보인다\n")
    write(run_dir.path / "spec" / "returns.md", "## 인수 기준\n- AC-05: 반품을 받는다\n")
    write(run_dir.path / "spec" / "overview.md", "- AC-01: 개요의 번호는 상세가 아니다\n")

    r = spawn(run_dir)

    assert r.returncode == 0, r.output
    lines = r.stdout.splitlines()
    assert "! 인수 기준 중복: AC-05 (delivery.md, returns.md)" in lines
    assert not any(l.startswith("! 인수 기준 중복: AC-01") for l in lines), r.stdout   # overview.md는 읽지 않는다
    assert made(run_dir) == ["T001", "T002"]


def test_ac_screen_map_reads_first_head_line_per_number(run_dir, lib):
    write(run_dir.path / "spec" / "orders.md", SPEC_ORDERS)
    write(run_dir.path / "spec" / "brief.md", "- AC-02 [화면: S-99] 기획은 상세가 아니다\n")

    screens, warnings = lib.ac_screen_map(str(run_dir.path))

    assert screens == {"AC-01": {"S-01"}, "AC-02": set(), "AC-03-1": {"S-02", "S-03"}}
    assert warnings == []


# --- (바) 경로 대조: 설계 문서 5.1 표의 예 패턴 -------------------------------------------------------------------

@pytest.mark.parametrize("pattern, inside, outside", [
    ("client/**", "client/src/App.tsx", "server/client.ts"),
    ("src/routes/**", "src/routes/orders/+page.svelte", "src/lib/routes.ts"),
    ("db/migrations/**", "db/migrations/0001_init.sql", "db/seed.sql"),
    ("db/install.sql", "db/install.sql", "db/install.sql.bak"),
    ("wrangler.jsonc", "wrangler.jsonc", "tools/wrangler.jsonc"),
    ("tools/deploy/**", "tools/deploy/run.sh", "tools/build/deploy.sh"),
    (".github/workflows/**", ".github/workflows/ci.yml", ".github/dependabot.yml"),
    ("docs/**", "docs/guide/start.md", "src/docs.md"),
    ("README.md", "README.md", "docs/README.md"),
])
def test_path_in_list_example_patterns(lib, pattern, inside, outside):
    assert lib.path_in_list(inside, [pattern]) is True
    assert lib.path_in_list(outside, [pattern]) is False


def test_path_in_list_normalizes_and_keeps_single_star_in_one_level(lib):
    assert lib.path_in_list(".\\docs\\a.md", ["docs/**"]) is True
    assert lib.path_in_list("db/migrations/*.sql", ["db/migrations/**"]) is True   # 「건드릴 파일」의 와일드카드는 글자 그대로
    assert lib.path_in_list("src/a.py", ["src/*.py"]) is True
    assert lib.path_in_list("src/x/a.py", ["src/*.py"]) is False
    assert lib.path_in_list("src/a.py", []) is False


def test_project_paths_reads_lists_and_empty_values(run_dir, lib):
    write(run_dir.path.parent / "devflow-harness.project.md",
          "## 경로 목록\n- 감지한 실행: dryrun\n- 화면 경로: `client/**`, src/routes/**\n- 인프라 경로: 없음\n- 문서 경로: docs/**\n")

    got = lib.project_paths(str(run_dir.path))

    assert got == {"실행": "dryrun", "화면": ["client/**", "src/routes/**"], "인프라": [], "문서": ["docs/**"]}
    os.remove(run_dir.path.parent / "devflow-harness.project.md")
    assert lib.project_paths(str(run_dir.path)) == {"실행": "", "화면": [], "인프라": [], "문서": []}
