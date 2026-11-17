"""목적 시험 폴더 준비: 자료 폴더의 task 하나를 그 task가 시작할 때의 상태로 되돌린 시험 폴더를 만든다.

사용:
  python tests/purpose/setup_task.py --data DIR --task TID --out DIR --source-run-md PATH --run-name NAME --prior-name NAME

- `--data`: `{TID}/code`(대상 프로젝트 코드 사본), `{TID}/run`(실행 폴더 사본), `{TID}/prior-run/decisions.md`
  (앞 실행의 결정)를 가진 폴더. 자료는 저장소에 두지 않는다(tests/purpose/README.md).
- 만드는 것: `{out}/{TID}/code`(코드 사본, 시험용 git 커밋 하나), 실행 폴더 `code/_workspace/{run-name}`,
  앞 실행 결정 `code/_workspace/{prior-name}/decisions.md`. 실행 폴더를 실제 실행처럼 코드 사본 아래에 두어
  머리 파일이 가리키는 상대 경로가 풀리게 한다. `_workspace/`는 시험용 git에서 뺀다(`.git/info/exclude`).
- 되돌리는 것: 대상 task보다 늦게 만든 task 폴더(머리 파일 없는 폴더 포함), 대상 task의 묻기·승인 흔적
  (`approved/`·`asked/` 아래 `{TID}`로 시작하는 것), 대상 task 폴더의 결과·판정·사본·사실·화면·정정·main-run 파일.
  머리 파일은 「판정 기준 정정」·「재시도 범위」를 빼고 판정 기준을 `criteria.orig.md`로, 이상 신호·승인 기록을 비우고,
  상태 키를 시작 때 값으로(`started_version`은 이 저장소 판본). 흐름 `dir`은 코드 사본. run.md는 `--source-run-md`의
  「요청 원문」·「이번 실행의 값」만 옮긴다.
- 지우는 것: `{out}/{TID}`가 이미 있으면 이 스크립트가 남긴 표지 파일 `.purpose-sandbox`가 있을 때만 지우고 다시 만든다.
- 종료 코드: 0 준비됨, 3 거부(표지 없는 출력 폴더, 이 저장소 안 `_workspace/` 밖의 `--out`, 자료 꼴이 아님).
"""
import argparse
import json
import os
import re
import shutil
import stat
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(ROOT, "scripts")
MARKER = ".purpose-sandbox"
REFUSED = 3

sys.dont_write_bytecode = True   # scripts/ 아래에 __pycache__를 남기지 않는다
sys.path.insert(0, SCRIPTS)
import devflow_lib  # noqa: E402

# 대상 task 폴더에서 지우는 파일·폴더의 이름 머리(결과·판정·사본·사실·화면·정정·main-run)
DROP_PREFIXES = ("result", "judge", "before.r", "facts", "screen-", "criteria.amend", "main-run")
DROP_NAMES = ("design-copy",)
# 머리 파일에서 빼는 절(판정 기준 정정, 재시도 범위)
DROP_SECTIONS = ("판정 기준 정정", "재시도 범위")
# 시작 때 값으로 되돌리는 상태 키. started_version은 이 저장소 판본으로 따로 쓴다
RESET_KEYS = (("status", "진행"), ("retry", "0"), ("judge_started", ""), ("approval_requested", ""), ("approved", ""),
              ("approval_mode", ""), ("machine_check", ""), ("waiting_user", ""), ("running_agent", ""),
              ("n_decide", "0"), ("n_todo", "0"), ("n_notify", "0"), ("n_unverified", "0"), ("n_children", "0"),
              ("asked_at", ""), ("card_open", ""))
RUN_SECTIONS = ("요청 원문", "이번 실행의 값")


class Refuse(Exception):
    """거부(종료 3). 메시지는 무엇이 안 되는지 한 줄."""


def _clear_readonly(func, path, _exc):
    # Windows에서 git 객체 파일은 읽기 전용이라 지우기 전에 쓰기 권한을 준다
    os.chmod(path, stat.S_IWRITE)
    func(path)


def remove(path):
    if os.path.isdir(path):
        if sys.version_info >= (3, 12):
            shutil.rmtree(path, onexc=_clear_readonly)
        else:  # pragma: no cover
            shutil.rmtree(path, onerror=_clear_readonly)
    else:
        os.remove(path)


def harness_version():
    with open(os.path.join(ROOT, ".claude-plugin", "plugin.json"), encoding="utf-8") as f:
        return json.load(f)["version"]


def out_refusal(out, root=ROOT):
    """`--out`을 거부할 까닭(없으면 None). 이 저장소 안이면 `_workspace/` 아래만 받는다."""
    # realpath로 연결점·심볼릭 링크·8.3 짧은 이름을 풀어 저장소 안 판단이 표기에 흔들리지 않게 한다
    out = os.path.normcase(os.path.realpath(out))
    root = os.path.normcase(os.path.realpath(root))
    try:
        inside = os.path.commonpath([out, root]) == root
    except ValueError:   # 드라이브가 다름
        inside = False
    if not inside:
        return None
    workspace = os.path.join(root, "_workspace")
    if os.path.commonpath([out, workspace]) == workspace:
        return None
    return "--out이 이 저장소 안이면서 _workspace/ 밖임: {}".format(out)


def check_inputs(data, task, source_run_md):
    src = os.path.join(data, task)
    need = [os.path.join(src, "code"), os.path.join(src, "run", "tasks", task, "task.md"),
            os.path.join(src, "prior-run", "decisions.md"), source_run_md]
    missing = [p for p in need if not os.path.exists(p)]
    if missing:
        raise Refuse("자료 꼴이 아님(없음: {}). --data는 {{TID}}/code·run·prior-run/decisions.md를 가진 폴더".format(
            ", ".join(missing)))
    secs = devflow_lib.sections(devflow_lib.read_text(source_run_md), level=2)
    lost = [s for s in RUN_SECTIONS if s not in secs]
    if lost:
        raise Refuse("--source-run-md에 절이 없음: {}".format(", ".join(lost)))
    return src


def prepare_out(dst):
    """출력 폴더를 비우고 표지를 남긴다. 표지 없는 폴더는 건드리지 않고 거부한다."""
    if os.path.exists(dst):
        if not os.path.isfile(os.path.join(dst, MARKER)):
            raise Refuse("출력 폴더가 이미 있고 표지 {}가 없음(이 스크립트가 만든 폴더가 아님): {}".format(MARKER, dst))
        remove(dst)
    os.makedirs(dst)
    with open(os.path.join(dst, MARKER), "w", encoding="utf-8") as f:
        f.write("tests/purpose/setup_task.py가 만든 목적 시험 폴더. 다시 돌리면 지우고 새로 만든다.\n")


def drop_later_tasks(tasks_dir, task, born):
    for name in sorted(os.listdir(tasks_dir)):
        if name == task:
            continue
        d = os.path.join(tasks_dir, name)
        f = os.path.join(d, "task.md")
        if not os.path.isfile(f) or (devflow_lib.Doc(f).get("created") or "") > born:
            remove(d)
            print("뺌", name)


def drop_asked_marks(run, task):
    for sub in ("approved", "asked"):
        base = os.path.join(run, sub)
        for top, dirs, files in os.walk(base):
            for name in sorted(dirs + files):
                if name.startswith(task):
                    p = os.path.join(top, name)
                    remove(p)
                    print("뺌", os.path.relpath(p, run))
            dirs[:] = [d for d in dirs if not d.startswith(task)]


def reset_task(tdir, version):
    for name in sorted(os.listdir(tdir)):
        if name.startswith(DROP_PREFIXES) or name in DROP_NAMES:
            remove(os.path.join(tdir, name))
    path = os.path.join(tdir, "task.md")
    text = devflow_lib.read_text(path)
    for sec in DROP_SECTIONS:
        text = re.sub(r"(?ms)^## {}\n.*?(?=^## |\Z)".format(re.escape(sec)), "", text)
    devflow_lib.write_text(path, text)
    doc = devflow_lib.Doc(path)
    orig = os.path.join(tdir, "criteria.orig.md")
    if os.path.isfile(orig):
        doc.set_section("판정 기준", devflow_lib.read_text(orig).strip())
    doc.set_section("넘길 이상 신호", "(없음)")
    doc.set_section("승인 기록", "")
    doc.set("started_version", version)
    for key, value in RESET_KEYS:
        doc.set(key, value)
    doc.save()


def write_run_md(run, source_run_md, code, version):
    text = devflow_lib.read_text(source_run_md)
    meta_lines, body = devflow_lib.split_front_matter(text)
    base_branch = devflow_lib.parse_meta(meta_lines).get("base_branch", "")
    secs = devflow_lib.sections(body, level=2)
    devflow_lib.write_text(os.path.join(run, "run.md"), (
        "---\nkind: devflow-harness\nstatus: 진행\nproject: {}\nbase_branch: {}\nround: 1\nintegration_branch:\n"
        "integration_dir:\nharness_version: {}\nstart_task: T001\nprevious_run:\nsession_id:\n---\n"
        "## 요청 원문\n{}\n\n## 이번 실행의 값\n{}\n").format(
            code, base_branch, version, secs["요청 원문"].strip(), secs["이번 실행의 값"].strip()))


def snapshot(code):
    git = ["git", "-C", code, "-c", "user.name=purpose", "-c", "user.email=purpose@test", "-c", "core.autocrlf=false",
           "-c", "commit.gpgsign=false"]
    subprocess.run(git + ["init", "-q"], check=True)
    with open(os.path.join(code, ".git", "info", "exclude"), "a", encoding="utf-8") as f:
        f.write("\n_workspace/\n")
    subprocess.run(git + ["add", "-A"], check=True, capture_output=True)
    # 자료의 코드 사본이 비어 있어도 커밋 하나를 만든다(실행 폴더는 _workspace/라 빠짐)
    subprocess.run(git + ["commit", "-q", "--allow-empty", "-m", "sandbox snapshot"], check=True)


def setup(args):
    reason = out_refusal(args.out)
    if reason:
        raise Refuse(reason)
    src = check_inputs(args.data, args.task, args.source_run_md)
    version = harness_version()
    dst = os.path.join(os.path.abspath(args.out), args.task)
    born = devflow_lib.Doc(os.path.join(src, "run", "tasks", args.task, "task.md")).get("created")
    if not born:
        raise Refuse("대상 task 머리 파일에 created가 없음: {}".format(args.task))
    prepare_out(dst)

    code = os.path.join(dst, "code")
    shutil.copytree(os.path.join(src, "code"), code)
    if not os.listdir(code):
        print("! 코드 사본이 비었음: {}".format(os.path.join(src, "code")))
    run = os.path.join(code, "_workspace", args.run_name)
    shutil.copytree(os.path.join(src, "run"), run)
    prior = os.path.join(code, "_workspace", args.prior_name)
    os.makedirs(prior)
    shutil.copyfile(os.path.join(src, "prior-run", "decisions.md"), os.path.join(prior, "decisions.md"))

    drop_later_tasks(os.path.join(run, "tasks"), args.task, born)
    drop_asked_marks(run, args.task)
    reset_task(os.path.join(run, "tasks", args.task), version)
    flows = os.path.join(run, "flows")
    for flow in sorted(os.listdir(flows)) if os.path.isdir(flows) else []:
        path = os.path.join(flows, flow, "flow.md")
        if os.path.isfile(path):
            doc = devflow_lib.Doc(path)
            doc.set("dir", code)
            doc.save()
    write_run_md(run, args.source_run_md, code, version)
    snapshot(code)
    print("준비됨:", run)


def main(argv=None):
    devflow_lib.utf8_stdout()
    p = argparse.ArgumentParser(description="목적 시험 폴더 준비(tests/purpose/README.md)")
    p.add_argument("--data", required=True, help="{TID}/code·run·prior-run/decisions.md를 가진 자료 폴더")
    p.add_argument("--task", required=True, help="대상 task id")
    p.add_argument("--out", required=True, help="시험 폴더를 만들 곳({out}/{TID})")
    p.add_argument("--source-run-md", required=True, help="원래 실행의 run.md(요청 원문·이번 실행의 값을 옮김)")
    p.add_argument("--run-name", required=True, help="코드 사본 _workspace/ 아래 실행 폴더 이름")
    p.add_argument("--prior-name", required=True, help="앞 실행 결정을 둘 _workspace/ 아래 폴더 이름")
    args = p.parse_args(argv)
    try:
        setup(args)
    except Refuse as e:
        print("거부:", e, file=sys.stderr)
        return REFUSED
    return 0


if __name__ == "__main__":
    sys.exit(main())
