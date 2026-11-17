"""1.3.0 B: 판정 전 사실 검사 `judge_facts.py`(구현 설계 2절 B, 7판 규칙 5.2).

검사 다섯과 보안 신호를 `tasks\\{id}\\facts.md`에 쓴다. 판단은 하지 않고 줄만 낸다.
- ① 식별자의 생산처: 결과·정본이 언급한 식별자마다 정의·대입·반환·던짐 줄. 없으면 `생산처 없음`.
- ② 바뀐 동작의 기존 시험: 그 식별자나 지운 문구를 단언하는 시험 줄.
- ③ 배포 도구의 시간 제한·재시도·되돌림(배포 kind만).
- ④ 설정 값의 꼴(배포 kind만): 키의 있음과 길이·꼴 이름. 값의 글자는 한 자도 싣지 않는다.
- ⑤ 시험이 물려받는 환경.
kind마다 도는 검사는 등록표 `kinds.FACT_CHECKS`가 정하고, 돌지 않는 검사는 절에 `돌리지 않음`을 쓴다.
"""
import subprocess

import pytest

import devflow_lib as lib
import judge_facts
import kinds
from conftest import run_script, write

V130 = {"started_version": "1.3.0", "rules": "2"}
SECRET = "eyJhbGciOiJIUzI1NiJ9.c2VjcmV0LXZhbHVlLWhlcmU.abcdefghijklmnop"


def git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), "-c", "user.name=t", "-c", "user.email=t@t"] + list(args),
                   check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    folder = tmp_path / "code"
    folder.mkdir()
    git(folder, "init", "-q")
    return folder


def commit(repo, files):
    for path, text in files.items():
        write(repo / path, text)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "base")


def task(run_dir, kind, result_text, **meta):
    run_dir.task("T001", "일", kind=kind, block="설계", status="자체검증", **dict(V130, **meta))
    run_dir.result("T001", result_text)
    return run_dir.tasks()["T001"]


def facts(run_dir, t, repo):
    path = judge_facts.write_facts(str(run_dir.path), t, str(repo))
    return open(path, encoding="utf-8").read()


def section(text, name):
    return lib.sections(text, level=2).get(name, "")


# ---------------------------------------------------------------- 식별자

def test_identifiers_come_from_backticks_and_bare_error_codes():
    names = judge_facts.identifiers("`retryLimit`와 `fetch_order()`를 쓴다. 실패하면 ERR_TIMEOUT을 낸다. "
                                    "`src/a.ts`, `npm test`, `true`, `wrangler`는 식별자가 아니다. `api.client.send`")
    assert names == ["retryLimit", "fetch_order", "ERR_TIMEOUT", "send"]


def test_producer_lines_and_missing_producer(run_dir, repo):
    commit(repo, {"src/a.ts": "export const retryLimit = 3;\nfunction load() {\n  throw new Error(ERR_TIMEOUT);\n}\n",
                  "src/b.ts": "import { retryLimit } from './a';\nconsole.log(retryLimit);\n",
                  "tests/a.test.ts": "const retryLimit = 9;\n"})
    t = task(run_dir, "design", "# 결과\n이유: `retryLimit`는 3이다. 실패하면 ERR_TIMEOUT을 낸다. `E_GONE`도 쓴다.\n")
    body = section(facts(run_dir, t, repo), judge_facts.SECTIONS["producer"])
    rows = {line.split(" | ")[0]: line for line in body.splitlines() if line.startswith("- ")}
    assert "src/a.ts:1 정의" in rows["- `retryLimit`"] and "tests/a.test.ts" not in rows["- `retryLimit`"]
    assert "src/a.ts:3 던짐" in rows["- `ERR_TIMEOUT`"]
    assert "생산처 없음" in rows["- `E_GONE`"]


def test_canon_sections_are_read_too(run_dir, repo):
    commit(repo, {"src/a.ts": "export const quotaMax = 5;\n"})
    write(run_dir.path / "design" / "a.md", "# 설계\n한도는 `quotaMax`다.\n")
    run_dir.task("T001", "일", {"정본의 절": "- design/a.md"}, kind="design", block="설계", status="자체검증", **V130)
    run_dir.result("T001", "# 결과\n")
    body = section(facts(run_dir, run_dir.tasks()["T001"], repo), judge_facts.SECTIONS["producer"])
    assert "`quotaMax`" in body and "src/a.ts:1 정의" in body


# ---------------------------------------------------------------- 기존 시험

def test_asserting_tests_for_named_identifiers_and_removed_strings(run_dir, repo):
    commit(repo, {"src/a.ts": 'export function sendMail() {\n  return "메일을 보냈습니다";\n}\n',
                  "tests/a.test.ts": 'it("x", () => {\n  expect(sendMail()).toBe("메일을 보냈습니다");\n});\n'
                                     'it("y", () => {\n  sendMail();\n});\n'})
    write(repo / "src/a.ts", 'export function sendMail() {\n  return "보냄";\n}\n')
    t = task(run_dir, "implementation", "# 결과\n`sendMail`의 문구를 바꾼다.\n", flow="a")
    body = section(facts(run_dir, t, repo), judge_facts.SECTIONS["tests"])
    assert "tests/a.test.ts:2" in body
    assert "tests/a.test.ts:5" not in body   # 단언이 없는 호출은 세지 않는다
    assert '"메일을 보냈습니다"' in body


# ---------------------------------------------------------------- 배포 값

def test_deploy_values_only_for_deploy_kinds(run_dir, repo):
    commit(repo, {".github/workflows/deploy.yml": "jobs:\n  d:\n    timeout-minutes: 10\n    steps:\n      - run: x\n        retries: 2\n",
                  "scripts/deploy.sh": "wrangler deploy --rollback-on-failure\n"})
    plan = task(run_dir, "deploy-plan", "# 결과\n## 명령\n1. `wrangler deploy --timeout 60`\n")
    body = section(facts(run_dir, plan, repo), judge_facts.SECTIONS["deploy"])
    assert ".github/workflows/deploy.yml:3" in body and "timeout-minutes=10" in body
    assert "retries=2" in body
    assert "scripts/deploy.sh:1" in body and "되돌림" in body
    assert "result.md" in body and "timeout=60" in body
    design = task(run_dir, "design", "# 결과\n")
    assert judge_facts.NOT_RUN in section(facts(run_dir, design, repo), judge_facts.SECTIONS["deploy"])


# ---------------------------------------------------------------- 설정 값의 꼴

def test_config_shape_without_any_value(run_dir, repo):
    commit(repo, {"src/env.ts": 'const k = process.env.SUPABASE_KEY;\nif (!k.startsWith("eyJ")) throw 1;\n'
                                "const u = process.env.API_URL;\n",
                  ".gitignore": ".env.local\n"})
    write(repo / ".env.local", "SUPABASE_KEY={}\nUNUSED_TOKEN=abc123\n".format(SECRET))
    t = task(run_dir, "deploy-plan", "# 결과\n")
    text = facts(run_dir, t, repo)
    body = section(text, judge_facts.SECTIONS["config"])
    assert SECRET not in text and "abc123" not in text and SECRET[:12] not in text
    key = next(line for line in body.splitlines() if line.startswith("- SUPABASE_KEY"))
    assert "src/env.ts:1" in key and "길이 {}".format(len(SECRET)) in key and "JWT" in key
    assert "startsWith(리터럴 길이 3)" in key
    url = next(line for line in body.splitlines() if line.startswith("- API_URL"))
    assert "키 없음" in url
    unused = next(line for line in body.splitlines() if line.startswith("- UNUSED_TOKEN"))
    assert "코드에서 읽지 않음" in unused


# ---------------------------------------------------------------- 물려받는 환경

def test_inherited_environment(run_dir, repo):
    commit(repo, {"vitest.config.ts": "import 'dotenv/config';\nexport default { test: { env: { ...process.env } } };\n",
                  "tests/db.test.ts": "const url = process.env.DATABASE_URL;\n",
                  "src/a.ts": "const x = process.env.OTHER;\n"})
    t = task(run_dir, "implementation", "# 결과\n", flow="a")
    body = section(facts(run_dir, t, repo), judge_facts.SECTIONS["env"])
    assert "vitest.config.ts:1" in body and "vitest.config.ts:2" in body
    assert "tests/db.test.ts:1" in body and "DATABASE_URL" in body
    assert "src/a.ts" not in body   # 제품 코드의 환경 읽기는 시험의 물려받음이 아니다


# ---------------------------------------------------------------- 보안 신호, 상한, 종류

def test_security_signals_for_code_kinds(run_dir, repo):
    commit(repo, {"src/auth.ts": "export const a = 1;\n"})
    write(repo / "src/auth.ts", "export function authorize(user) { return true; }\n")
    t = task(run_dir, "implementation", "# 결과\n", flow="a")
    body = section(facts(run_dir, t, repo), judge_facts.SECTIONS["security"])
    assert "src/auth.ts:1 | authorize" in body


def test_each_section_is_capped(run_dir, repo, monkeypatch):
    monkeypatch.setattr(judge_facts, "LINE_CAP", 3)
    names = " ".join("`nameNo{}`".format(i) for i in range(6))
    commit(repo, {"src/a.ts": "x\n"})
    body = section(facts(run_dir, task(run_dir, "design", "# 결과\n" + names + "\n"), repo), judge_facts.SECTIONS["producer"])
    rows = [line for line in body.splitlines() if line.startswith("- ")]
    assert len(rows) == 4 and "외 3줄" in rows[-1]


def test_checks_follow_the_registry(run_dir, repo):
    commit(repo, {"src/a.ts": "x\n"})
    for kind, checks in kinds.FACT_CHECKS.items():
        text = facts(run_dir, task(run_dir, kind, "# 결과\n"), repo)
        for key, name in judge_facts.SECTIONS.items():
            assert (judge_facts.NOT_RUN in section(text, name)) == (key not in checks), (kind, key)


def test_registry_covers_the_designed_kinds():
    code = {k for k, v in kinds.KINDS.items() if v.auto_depends_in_flow}
    assert set(kinds.FACT_CHECKS) == code | {"design", "root-cause", "req-overview", "change", "infra-design", "deploy-plan"}
    assert all("producer" in v for v in kinds.FACT_CHECKS.values())
    assert {k for k, v in kinds.FACT_CHECKS.items() if "deploy" in v} == {"deploy-plan", "infra-design"}


def test_no_stage_kind_needs_facts():
    # 사실은 진행→자체검증 전이 때 뽑는다. 그 전이가 없는 단계 kind에 요구하면 판정 파일 점검이 영원히 막는다
    assert not set(kinds.FACT_CHECKS) & set(kinds.STAGE_KINDS)


def test_no_code_folder_still_writes_the_file(run_dir):
    t = task(run_dir, "design", "# 결과\n`a_b`\n")
    path = judge_facts.write_facts(str(run_dir.path), t, None)
    assert "뽑지 못함" in open(path, encoding="utf-8").read()


def test_command_line_falls_back_to_the_project_folder(run_dir, repo):
    commit(repo, {"src/a.ts": "export const quotaMax = 5;\n"})
    run_md = run_dir.path / "run.md"
    run_md.write_text(run_md.read_text(encoding="utf-8").replace("status: 진행", "status: 진행\nproject: {}".format(repo)),
                      encoding="utf-8")
    task(run_dir, "design", "# 결과\n`quotaMax`\n")
    p = run_script("judge_facts", run_dir.path, run_dir.task_dir("T001") / "task.md")
    assert p.returncode == 0, p.output
    assert "src/a.ts:1 정의" in (run_dir.task_dir("T001") / lib.FACTS_FILE).read_text(encoding="utf-8")


def test_selfcheck_transition_writes_facts_for_new_tasks_only(run_dir, repo):
    commit(repo, {"src/a.ts": "export const quotaMax = 5;\n"})
    run_md = run_dir.path / "run.md"
    run_md.write_text(run_md.read_text(encoding="utf-8").replace("status: 진행", "status: 진행\nproject: {}".format(repo)),
                      encoding="utf-8")
    for tid, meta in (("T001", V130), ("T002", {"started_version": "1.2.1", "rules": "2"})):
        run_dir.task(tid, "설계", kind="design", block="설계", status="진행", **meta)
        run_dir.result(tid, "# 결과\n`quotaMax`\n")
        p = run_script("task_set", run_dir.path, tid, "--status", "자체검증")
        assert p.returncode == 0, p.output
    assert (run_dir.task_dir("T001") / lib.FACTS_FILE).is_file()
    assert not (run_dir.task_dir("T002") / lib.FACTS_FILE).exists()


# ---------------------------------------------------------------- 리뷰가 보인 새는 길과 잘못 걸림

def test_removed_secret_strings_are_not_written(run_dir, repo):
    commit(repo, {"src/config.ts": 'export const cfg = { apiKey: "re_live_9f8a7b6c5d", hello: "안녕하세요 반갑습니다" };\n',
                  "tests/config.test.ts": 'it("x", () => {\n  expect(cfg.apiKey).toBe("re_live_9f8a7b6c5d");\n'
                                          '  expect(cfg.hello).toBe("안녕하세요 반갑습니다");\n});\n'})
    write(repo / "src/config.ts", "export const cfg = { apiKey: process.env.KEY, hello: \"다른 인사\" };\n")
    text = facts(run_dir, task(run_dir, "implementation", "# 결과\n", flow="a"), repo)
    assert "re_live_9f8a7b6c5d" not in text
    assert '"안녕하세요 반갑습니다" | tests/config.test.ts:3 단언' in text


def test_env_values_join_multiline_quotes_and_drop_comments(run_dir, repo):
    commit(repo, {"src/a.ts": "const a = process.env.PRIVATE_KEY;\nconst b = process.env.DB_PASSWORD;\n"
                              'if (!b.startsWith("AIzaSyD-abcdefghijklmnopqrstu")) throw 1;\n',
                  ".gitignore": ".env\n"})
    write(repo / ".env", 'PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\nQ29tcGxldGVseVNlY3JldFZhbHVlSGVyZQ==\n-----END PRIVATE KEY-----"\n'
                         "DB_PASSWORD = hunter2 # comment\n")
    text = facts(run_dir, task(run_dir, "deploy-plan", "# 결과\n"), repo)
    body = section(text, judge_facts.SECTIONS["config"])
    for secret in ("Q29tcGxldGVseVNlY3JldFZhbHVlSGVyZQ", "hunter2", "AIzaSyD"):
        assert secret not in text
    keys = [line.split(" | ")[0] for line in body.splitlines() if line.startswith("- ")]
    assert keys == ["- DB_PASSWORD", "- PRIVATE_KEY"]
    assert "길이 7, 꼴 그 밖" in body and "꼴 PEM" in body
    assert "startsWith(리터럴 길이 29)" in body


def test_deploy_lines_carry_no_line_text_and_skip_wrong_files(run_dir, repo):
    commit(repo, {"scripts/rollback.sh": "curl -u admin:hunter2 https://x/rollback\nvercel rollback --token abcdEFGH1234\n",
                  "deploy/.env.production": "WAITLIST_API_KEY=98234723984\nTIMEOUT=5\n",
                  "docs/deploy.md": "timeout: 99\n", "src/rollbackButton.tsx": "const timeout = 7;\n",
                  "playwright.config.ts": "export default { timeout: 30000 };\n",
                  "wrangler.toml": "[limits]\ncpu_ms = 50\n[triggers]\nretries = 3\n",
                  "netlify.toml": "[build]\n  command = 'x'\n  timeout = 120\n"})
    text = facts(run_dir, task(run_dir, "deploy-plan", "# 결과\n"), repo)
    body = section(text, judge_facts.SECTIONS["deploy"])
    for leak in ("hunter2", "abcdEFGH1234", "98234723984"):
        assert leak not in text
    assert "scripts/rollback.sh:1 | 되돌림을 말하는 줄" in body
    assert "wrangler.toml:4 | retries=3" in body and "netlify.toml:3 | timeout=120" in body
    for wrong in ("docs/deploy.md", "src/rollbackButton.tsx", "playwright.config.ts", ".env.production"):
        assert wrong not in body


def test_producer_kinds_are_narrow(run_dir, repo):
    commit(repo, {"src/a.py": "def archive_judge(x):\n    return 1\n\n    archive_judge(1)\nfoo(archive_judge=True)\n"
                              "# archive_judge = 옛 이름\nraise ValueError(\"archive_judge failed\")\nreturn archive_judge(2)\n",
                  "CHANGELOG.md": "return archive_judge\n", "cfg.yml": "API_URL: https://x\n"})
    t = task(run_dir, "design", "# 결과\n`archive_judge`와 `API_URL`\n")
    body = section(facts(run_dir, t, repo), judge_facts.SECTIONS["producer"])
    row = next(line for line in body.splitlines() if line.startswith("- `archive_judge`"))
    assert "생산: src/a.py:1 정의 |" in row and "그 밖 쓰임 4곳" in row
    assert "CHANGELOG" not in body
    assert "cfg.yml:1 대입" in body


def test_existing_tests_are_read_from_the_base_commit(run_dir, repo):
    commit(repo, {"src/a.ts": "export function sendMail() {}\n", "tests/a.test.ts": "x\n"})
    write(repo / "tests/new.test.ts", "expect(sendMail()).toBe(1);\n")
    t = task(run_dir, "implementation", "# 결과\n`sendMail`\n", flow="a")
    assert "new.test.ts" not in section(facts(run_dir, t, repo), judge_facts.SECTIONS["tests"])


def test_many_names_go_through_a_pattern_file(run_dir, repo):
    commit(repo, {"src/a.ts": "export const name_0 = 1;\n"})
    names = " ".join("`name_{}_{}`".format(i, "x" * 60) for i in range(800))   # 명령 줄이면 32K를 넘는다
    body = section(facts(run_dir, task(run_dir, "design", "# 결과\n`name_0` " + names + "\n"), repo), judge_facts.SECTIONS["producer"])
    assert "src/a.ts:1 정의" in body and "뽑지 못함" not in body


def test_a_failure_still_writes_the_file(run_dir, repo, monkeypatch):
    commit(repo, {"src/a.ts": "x\n"})
    t = task(run_dir, "design", "# 결과\n")

    def broken(*a):
        raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "bad")
    monkeypatch.setattr(judge_facts, "source_text", broken)
    text = facts(run_dir, t, repo)
    assert "뽑지 못함: 결과 파일·정본을 읽지 못함(UnicodeDecodeError" in text


def test_only_named_canon_sections_are_read(run_dir, repo):
    commit(repo, {"src/a.ts": "x\n"})
    write(run_dir.path / "spec" / "overview.md", "# 개요\n## 용어\n`termName`\n### 아래 절\n`deepName`\n## 범위 밖\n`outsideName`\n")
    run_dir.task("T001", "일", {"정본의 절": "spec\\overview.md 「용어」"}, kind="design", block="설계", status="자체검증", **V130)
    run_dir.result("T001", "# 결과\n")
    body = section(facts(run_dir, run_dir.tasks()["T001"], repo), judge_facts.SECTIONS["producer"])
    assert "`termName`" in body and "`deepName`" in body and "outsideName" not in body


def test_numbers_and_common_words_are_not_names():
    assert judge_facts.identifiers("`T001`, `JSON`, `HEAD`, `node_modules`, `AC7`, `URL` 그리고 `real_name`") == ["real_name"]


def test_sql_creates_are_producers(run_dir, repo):
    commit(repo, {"db/0006.sql": "create role bansel_mvp_app noinherit;\nCREATE OR REPLACE FUNCTION public.receipt_next() returns int as $$ select 1 $$;\n"
                                 "create table if not exists \"intake_log\" (id int);\ngrant select on t to bansel_mvp_app;\n"})
    body = section(facts(run_dir, task(run_dir, "design", "# 결과\n`bansel_mvp_app`, `receipt_next()`, `intake_log`\n"), repo),
                   judge_facts.SECTIONS["producer"])
    assert "db/0006.sql:1 정의" in body and "db/0006.sql:2 정의" in body and "db/0006.sql:3 정의" in body
    assert "생산처 없음" not in body


def test_string_literal_codes_are_producers(run_dir, repo):
    commit(repo, {"src/r.ts": "export function f() {\n  return { ok: false, code: 'db_insert' };\n}\n",
                  "tests/r.test.ts": "expect(x.code).toBe('db_insert');\n"})
    body = section(facts(run_dir, task(run_dir, "design", "# 결과\n`db_insert`\n"), repo), judge_facts.SECTIONS["producer"])
    assert "src/r.ts:2 문자열" in body and "tests/" not in body.split("|")[1]


def test_host_names_are_not_identifiers():
    """목적 시험 T004: `cdn.example.com`의 끝 마디 `com`이 식별자로 뽑혀 생산처 없음 256곳이 되었다."""
    names = judge_facts.identifiers("`cdn.example.com`, `img.gabia.co.kr`, `ctx.app`, `media.getUrl()`")
    assert "com" not in names and "kr" not in names and "app" in names and "getUrl" in names
