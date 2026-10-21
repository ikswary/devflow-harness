"""검증 효율 shadow 실험의 고정·대조기.

운영 판정은 이 모듈의 결과를 읽지 않는다. 불완전하거나 달라진 실험은 ``excluded``로
고정하고, 기존 판정·전체 CI는 그대로 진행한다.
"""
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
from datetime import date, datetime, timezone

import devflow_lib
import kinds


MIN_VERSION = (1, 0, 2)
STAGES = ("candidate", "baseline", "current", "final")
HEX256 = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA = re.compile(r"^[0-9a-fA-F]{40}$")


class ShadowError(Exception):
    pass


def _now():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            value = json.load(f)
    except (OSError, UnicodeError, json.JSONDecodeError) as e:
        raise ShadowError("JSON을 읽지 못함: {} ({})".format(path, e))
    if not isinstance(value, dict):
        raise ShadowError("JSON 최상위는 객체여야 함: " + path)
    return value


def _write_json(path, value):
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
    devflow_lib.write_text(path, text)


def canonical_bytes(path):
    """UTF-8을 엄격히 읽고 줄바꿈만 LF로 바꾼다. 공백과 최종 개행 유무는 보존한다."""
    try:
        raw = open(path, "rb").read()
        text = raw.decode("utf-8")
    except (OSError, UnicodeError) as e:
        raise ShadowError("UTF-8 원본을 읽지 못함: {} ({})".format(path, e))
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def file_hash(path):
    return hashlib.sha256(canonical_bytes(path)).hexdigest()


def section_hash(path, section):
    text = canonical_bytes(path).decode("utf-8")
    lines = text.splitlines(keepends=True)
    start = None
    for i, line in enumerate(lines):
        if line.rstrip("\n") == "## " + section:
            start = i + 1
            break
    if start is None:
        raise ShadowError("{}에 `{}` 절이 없음".format(path, section))
    end = len(lines)
    for i in range(start, len(lines)):
        if lines[i].startswith("## "):
            end = i
            break
    return hashlib.sha256("".join(lines[start:end]).encode("utf-8")).hexdigest()


def entry_hash(path, section=""):
    return section_hash(path, section) if section else file_hash(path)


def raw_hash(path):
    try:
        return hashlib.sha256(open(path, "rb").read()).hexdigest()
    except OSError as e:
        raise ShadowError("파일을 읽지 못함: {} ({})".format(path, e))


def _finite_number(value, name, low=None, high=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ShadowError("{}는 유한한 숫자여야 함".format(name))
    if low is not None and value < low or high is not None and value > high:
        raise ShadowError("{} 범위는 {}~{}".format(name, low, high))
    return value


def _nonempty(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ShadowError("{}는 비어 있지 않은 문자열이어야 함".format(name))
    return value.strip()


def _version(value):
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)(?:\D.*)?$", str(value or "").strip())
    return tuple(map(int, m.groups())) if m else ()


def _experiment_set(value):
    if isinstance(value, str):
        parts = re.split(r"\s*[,/]\s*", value.strip())
    elif isinstance(value, list):
        parts = value
    else:
        raise ShadowError("experiments는 A/B 배열이어야 함")
    out = []
    for part in parts:
        p = str(part).strip().upper()
        if p and p not in out:
            out.append(p)
    if not out or any(p not in ("A", "B") for p in out):
        raise ShadowError("experiments는 A, B 또는 A와 B여야 함")
    return sorted(out)


def _run_choice(run_dir):
    text = devflow_lib.read_text(os.path.join(run_dir, "run.md"))
    for line in text.splitlines():
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if cells and cells[0] == "검증 효율 실험" and len(cells) >= 2:
                return _experiment_set(cells[1])
    raise ShadowError("run.md 이번 실행의 값에 `검증 효율 실험` 선택이 없음")


def _source_path(run_dir, path):
    p = path if os.path.isabs(path) else os.path.join(run_dir, path)
    return os.path.normcase(os.path.realpath(os.path.abspath(p)))


def _validate_money(obj, name):
    if not isinstance(obj, dict):
        raise ShadowError("{}는 value/unit 객체여야 함".format(name))
    return {"value": _finite_number(obj.get("value"), name + ".value"),
            "unit": _nonempty(obj.get("unit"), name + ".unit")}


def init_plan(run_dir, plan_path):
    out = os.path.join(run_dir, "shadow-plan.json")
    if os.path.exists(out):
        raise ShadowError("shadow-plan.json은 한 번만 만든다")
    if devflow_lib.load_tasks(run_dir):
        raise ShadowError("task가 이미 있는 실행에는 shadow 계획을 시작하지 않음")
    run_md = os.path.join(run_dir, "run.md")
    decisions = os.path.join(run_dir, "decisions.md")
    meta = devflow_lib.run_meta(run_dir)
    version = meta.get("harness_version", "")
    if _version(version) < MIN_VERSION:
        raise ShadowError("run.md 하네스 판본은 1.0.2 이상이어야 함")
    if not os.path.isfile(decisions):
        raise ShadowError("decisions.md가 없음")
    plan = _json(plan_path)
    experiments = _experiment_set(plan.get("experiments"))
    if experiments != _run_choice(run_dir):
        raise ShadowError("PLAN experiments와 run.md 검증 효율 실험 선택이 다름")
    approval = _nonempty(plan.get("approval_evidence"), "approval_evidence")
    decision_text = devflow_lib.read_text(decisions)
    if approval not in decision_text:
        raise ShadowError("decisions.md에서 approval_evidence를 찾지 못함")
    n = plan.get("N")
    if isinstance(n, bool) or not isinstance(n, int) or n <= 0:
        raise ShadowError("N은 0보다 큰 정수여야 함")
    counts = plan.get("counts_by_type")
    if not isinstance(counts, dict) or not counts:
        raise ShadowError("counts_by_type은 비어 있지 않은 객체여야 함")
    clean_counts = {}
    for key, value in counts.items():
        key = _nonempty(key, "counts_by_type key")
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ShadowError("counts_by_type 값은 0 이상의 정수여야 함")
        clean_counts[key] = value
    if sum(clean_counts.values()) < n:
        raise ShadowError("유형별 표본 수 합은 N 이상이어야 함")
    end = _nonempty(plan.get("end_date"), "end_date")
    try:
        date.fromisoformat(end)
    except ValueError:
        raise ShadowError("end_date는 YYYY-MM-DD여야 함")
    record = {
        "schema": "devflow-shadow-plan-v1", "created_at": _now(), "status": "active",
        "experiments": experiments, "repository": _nonempty(plan.get("repository"), "repository"),
        "work_type": _nonempty(plan.get("work_type"), "work_type"), "approval_evidence": approval,
        "N": n, "counts_by_type": clean_counts, "S": _validate_money(plan.get("S"), "S"),
        "H": _validate_money(plan.get("H"), "H"),
        "E": _finite_number(plan.get("E"), "E", 0, 1), "end_date": end,
        "sources": {"plan_path": os.path.abspath(plan_path), "plan_sha256": raw_hash(plan_path),
                    "run_version": version, "run_round": str(meta.get("round", "")),
                    "run_choice": experiments, "approval_evidence_sha256":
                    hashlib.sha256(approval.encode("utf-8")).hexdigest(),
                    "initial_run_md_sha256": file_hash(run_md), "initial_decisions_md_sha256": file_hash(decisions)},
    }
    if "A" in experiments:
        a = plan.get("A")
        if not isinstance(a, dict):
            raise ShadowError("A 선택에는 A 객체가 필요함")
        strata = a.get("strata")
        if not isinstance(strata, list) or not strata:
            raise ShadowError("A.strata는 비어 있지 않은 배열이어야 함")
        record["A"] = {
            "R": _finite_number(a.get("R"), "A.R", 0, 1), "Q": _finite_number(a.get("Q"), "A.Q", 0, 1),
            "strata": [_nonempty(x, "A.strata") for x in strata],
            "seed": _nonempty(str(a.get("seed", "")), "A.seed"),
            "ratio": _finite_number(a.get("ratio"), "A.ratio", 0, 1),
            "rotation": _nonempty(a.get("rotation"), "A.rotation"),
            "calculation": _nonempty(a.get("calculation"), "A.calculation"),
        }
    _write_json(out, record)
    return out


def _plan(run_dir, experiment):
    path = os.path.join(run_dir, "shadow-plan.json")
    plan = _json(path)
    if plan.get("status") != "active" or experiment not in plan.get("experiments", []):
        raise ShadowError("활성화된 {} shadow 계획이 아님".format(experiment))
    src = plan.get("sources", {})
    original = src.get("plan_path")
    if not original or not os.path.isfile(original) or raw_hash(original) != src.get("plan_sha256"):
        raise ShadowError("계획 원본 hash가 달라짐")
    meta = devflow_lib.run_meta(run_dir)
    if (str(meta.get("harness_version", "")) != str(src.get("run_version", "")) or
            str(meta.get("round", "")) != str(src.get("run_round", "")) or
            _run_choice(run_dir) != src.get("run_choice")):
        raise ShadowError("run 판본/round/실험 선택 고정값이 달라짐")
    approval = str(plan.get("approval_evidence", ""))
    if (approval not in devflow_lib.read_text(os.path.join(run_dir, "decisions.md")) or
            hashlib.sha256(approval.encode("utf-8")).hexdigest() != src.get("approval_evidence_sha256")):
        raise ShadowError("승인 근거 행이 삭제·변경됨")
    return plan


def _exclude(task_dir, reason):
    path = os.path.join(task_dir, "shadow", "excluded.json")
    if not os.path.exists(path):
        _write_json(path, {"status": "excluded", "reason": reason, "recorded_at": _now()})
    return reason


def _task(run_dir, tid):
    task = devflow_lib.load_tasks(run_dir).get(tid)
    if not task:
        raise ShadowError("task를 찾지 못함: " + tid)
    if _version(task.get("started_version")) < MIN_VERSION:
        raise ShadowError("started_version 1.0.2 미만 task는 실험하지 않음")
    if os.path.exists(os.path.join(task["_dir"], "shadow", "excluded.json")):
        raise ShadowError("이미 비교 제외된 task")
    return task


def _check_entries(run_dir, entries, name):
    if not isinstance(entries, list) or not entries:
        raise ShadowError("{}는 비어 있지 않은 배열이어야 함".format(name))
    clean = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ShadowError("{} 원소는 path/sha256 객체여야 함".format(name))
        p = _source_path(run_dir, _nonempty(entry.get("path"), name + ".path"))
        expected = str(entry.get("sha256", "")).lower()
        section = str(entry.get("section", "") or "").strip()
        if not HEX256.match(expected) or not os.path.isfile(p) or entry_hash(p, section) != expected:
            raise ShadowError("{} 고정 사본 hash 불일치: {}".format(name, p))
        clean.append({"path": p, "sha256": expected, "section": section})
    return clean


def _check_raw_entries(run_dir, entries, name):
    if not isinstance(entries, list) or not entries:
        raise ShadowError("{}는 비어 있지 않은 배열이어야 함".format(name))
    clean = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ShadowError("{} 원소는 role/path/sha256 객체여야 함".format(name))
        p = _source_path(run_dir, _nonempty(entry.get("path"), name + ".path"))
        expected = str(entry.get("sha256", "")).lower()
        role = _nonempty(entry.get("role"), name + ".role")
        if not HEX256.match(expected) or not os.path.isfile(p) or raw_hash(p) != expected:
            raise ShadowError("{} 원본 byte hash 불일치: {}".format(name, p))
        clean.append({"role": role, "path": p, "sha256": expected})
    return clean


def _review_citations(run_dir, task, state, output, citations, judge_text):
    if not isinstance(citations, list) or not citations:
        return False, []
    checked = []
    for item in citations:
        if not isinstance(item, dict):
            return False, []
        p = _source_path(run_dir, str(item.get("path", "")))
        digest = str(item.get("sha256", "")).lower()
        location = str(item.get("location", "")).strip()
        if (not HEX256.match(digest) or not location or not os.path.isfile(p) or raw_hash(p) != digest or
                "{}#{}".format(p, location) not in judge_text or p == output):
            return False, []
        checked.append({"path": p, "sha256": digest, "location": location})
    got = {x["path"] for x in checked}
    required = set()
    for stage in STAGES:
        data = state.get("stages", {}).get(stage, {})
        required.add(data.get("input_copy"))
        required.add(data.get("access_log_path"))
        if stage != "final":
            required.add(data.get("evidence_path"))
            required.add(data.get("snapshot") or data.get("output_path"))
    required = {_source_path(run_dir, x) for x in required if x}
    return required <= got, checked


def _git_snapshot(run_dir, inputs):
    code_dir = _source_path(run_dir, _nonempty(inputs.get("code_dir"), "code_dir"))
    declared = inputs.get("git_snapshot")
    if not isinstance(declared, dict) or not isinstance(declared.get("files"), list):
        raise ShadowError("git_snapshot은 head_sha/files 객체여야 함")
    try:
        head = subprocess.run(["git", "-C", code_dir, "rev-parse", "HEAD"], capture_output=True,
                              check=True, text=True, encoding="utf-8").stdout.strip()
        tracked_raw = subprocess.run(["git", "-C", code_dir, "ls-files", "-z"], capture_output=True,
                                     check=True).stdout
        status_raw = subprocess.run(["git", "-C", code_dir, "status", "--porcelain=v1", "-z", "--untracked-files=all"],
                                    capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError) as e:
        raise ShadowError("code_dir Git 상태를 읽지 못함: {} ({})".format(code_dir, e))
    tracked = {x.decode("utf-8") for x in tracked_raw.split(b"\0") if x}
    status = {}
    chunks = [x.decode("utf-8") for x in status_raw.split(b"\0") if x]
    i = 0
    while i < len(chunks):
        row = chunks[i]
        code, path = row[:2], row[3:]
        if code[0] in "RC" or code[1] in "RC":
            i += 1
            if i >= len(chunks):
                raise ShadowError("Git rename/copy 상태가 불완전함")
            path = path + " -> " + chunks[i]
        status[path] = code
        i += 1
    all_paths = tracked | {p for p in status if " -> " not in p and status[p] == "??"}
    actual = []
    for rel in sorted(all_paths):
        p = os.path.join(code_dir, rel)
        # Git 원천은 바이너리를 포함할 수 있으므로 byte hash다. LF canonical은 판정문서/고정 사본에만 적용한다.
        actual.append({"path": rel.replace("\\", "/"), "status": status.get(rel, "  "),
                       "sha256": raw_hash(p) if os.path.isfile(p) else None})
    clean_declared = sorted(declared["files"], key=lambda x: str(x.get("path", "")))
    if declared.get("head_sha") != head or clean_declared != actual:
        raise ShadowError("실제 Git HEAD/tracked+untracked/삭제·rename 스냅샷과 입력이 다름")
    return {"code_dir": code_dir, "head_sha": head, "files": actual}


def _state(task):
    path = os.path.join(task["_dir"], "shadow", "state.json")
    if not os.path.isfile(path):
        return {"schema": "devflow-shadow-a-v1", "stages": {}, "instances": []}
    return _json(path)


def _verify_frozen(task, state):
    for stage, data in state.get("stages", {}).items():
        if data.get("status") != "frozen":
            continue
        snap = data.get("snapshot")
        if snap and (not os.path.isfile(snap) or file_hash(snap) != data.get("output_sha256")):
            raise ShadowError("{} 고정 사본이 바뀌거나 삭제됨".format(stage))
        if not snap:
            output = data.get("output_path")
            if not output or not os.path.isfile(output) or file_hash(output) != data.get("output_sha256"):
                raise ShadowError("{} 정상 결과가 고정 뒤 바뀌거나 삭제됨".format(stage))
        inp = data.get("input_copy")
        if not inp or not os.path.isfile(inp) or raw_hash(inp) != data.get("input_copy_sha256"):
            raise ShadowError("{} 입력 고정 사본이 바뀌거나 삭제됨".format(stage))
        evidence_path = data.get("evidence_path")
        if (not evidence_path or not os.path.isfile(evidence_path) or
                raw_hash(evidence_path) != data.get("evidence_sha256")):
            raise ShadowError("{} evidence 원본이 바뀌거나 삭제됨".format(stage))
        access_path = data.get("access_log_path")
        if (not access_path or not os.path.isfile(access_path) or
                raw_hash(access_path) != data.get("access_log_sha256")):
            raise ShadowError("{} 접근 로그 원본이 바뀌거나 삭제됨".format(stage))
        for entry in data.get("fixed", []):
            if (not os.path.isfile(entry["path"]) or
                    entry_hash(entry["path"], entry.get("section", "")) != entry["sha256"]):
                raise ShadowError("{} 뒤 원천이 바뀌거나 삭제/rename됨: {}".format(stage, entry["path"]))
        git = data.get("git")
        if git:
            check = {"code_dir": git["code_dir"], "git_snapshot": {"head_sha": git["head_sha"], "files": git["files"]}}
            _git_snapshot(os.path.dirname(os.path.dirname(task["_dir"])), check)


def shadow_open(run_dir, tid, stage, instance, inputs_path):
    task = _task(run_dir, tid)
    if task.get("kind") != "flow-verify":
        raise ShadowError("A shadow 대상은 flow-verify task만")
    try:
        _plan(run_dir, "A")
    except ShadowError as e:
        _exclude(task["_dir"], str(e))
        raise
    if stage not in STAGES:
        raise ShadowError("stage는 " + "/".join(STAGES))
    state = _state(task)
    try:
        _verify_frozen(task, state)
    except ShadowError as e:
        _exclude(task["_dir"], str(e))
        raise
    idx = STAGES.index(stage)
    if any(state.get("stages", {}).get(s, {}).get("status") != "frozen" for s in STAGES[:idx]):
        raise ShadowError("이전 단계가 모두 고정되지 않음")
    if stage in state.get("stages", {}):
        raise ShadowError("이미 연 단계는 덮어쓰지 않음")
    instance = _nonempty(instance, "instance")
    if instance in state.get("instances", []):
        raise ShadowError("단계별 instance ID는 달라야 함")
    if stage in ("candidate", "baseline") and task.get("status") != "진행":
        raise ShadowError("candidate/baseline 동안 task 상태는 진행이어야 함")
    inputs = _json(inputs_path)
    sha = str(inputs.get("candidate_sha", ""))
    if not GIT_SHA.match(sha):
        raise ShadowError("candidate_sha는 40자리 Git SHA여야 함")
    pop = inputs.get("population")
    if not isinstance(pop, list) or not pop or any(not str(x).strip() for x in pop):
        raise ShadowError("population은 모집단 전체가 든 비어 있지 않은 배열이어야 함")
    population = [str(x).strip() for x in pop]
    if len(set(population)) != len(population):
        raise ShadowError("population에 중복 task가 있음")
    actual_population = sorted(
        x for x, candidate in devflow_lib.load_tasks(run_dir).items()
        if candidate.get("flow") == task.get("flow") and candidate.get("approval_mode") == "알림"
        and candidate.get("status") == kinds.DONE)
    if sorted(population) != actual_population:
        raise ShadowError("population이 같은 흐름의 실제 notified 완료 task 전체와 다름")
    context = inputs.get("context")
    allowed = inputs.get("allowed_paths")
    if not isinstance(context, list) or not isinstance(allowed, list):
        raise ShadowError("context와 allowed_paths는 배열이어야 함")
    criteria = _check_entries(run_dir, inputs.get("criteria"), "criteria")
    for entry in criteria:
        own = entry["path"] == _source_path(run_dir, task["_path"])
        if (own and entry.get("section") != "판정 기준") or (not own and entry.get("section")):
            raise ShadowError("task.md 자체는 판정 기준 절만, 다른 criteria 파일은 전체만 고정")
    copies = _check_entries(run_dir, inputs.get("copies"), "copies")
    fixed = criteria + copies
    git = _git_snapshot(run_dir, inputs)
    if sha.lower() != git["head_sha"].lower():
        raise ShadowError("candidate_sha와 code_dir HEAD가 다름")
    if idx:
        first = state.get("stages", {}).get("candidate", {})
        if (sha.lower() != str(first.get("candidate_sha", "")).lower() or
                sorted(population) != sorted(first.get("population", [])) or
                criteria != first.get("criteria", []) or git != first.get("git")):
            _exclude(task["_dir"], "단계 사이 candidate SHA/모집단/기준/Git 스냅샷이 다름")
            raise ShadowError("단계 사이 candidate SHA/모집단/기준/Git 스냅샷이 다름")
    shadow_dir = os.path.join(task["_dir"], "shadow")
    os.makedirs(shadow_dir, exist_ok=True)
    input_copy = os.path.join(shadow_dir, stage + "-inputs.json")
    shutil.copyfile(inputs_path, input_copy)
    state.setdefault("stages", {})[stage] = {
        "status": "open", "instance": instance, "opened_at": _now(), "candidate_sha": sha,
        "population": population, "context": [str(x) for x in context],
        "allowed_paths": [_source_path(run_dir, str(x)) for x in allowed], "criteria": criteria,
        "copies": copies, "fixed": fixed, "git": git,
        "input_sha256": raw_hash(inputs_path), "input_copy": input_copy, "input_copy_sha256": raw_hash(input_copy),
    }
    state.setdefault("instances", []).append(instance)
    _write_json(os.path.join(shadow_dir, "state.json"), state)


def make_inputs(run_dir, tid, spec_path, out_path):
    """메인이 hash 목록을 손으로 조립하지 않도록 실제 입력 manifest를 만든다."""
    task = _task(run_dir, tid)
    _plan(run_dir, "A")
    spec = _json(spec_path)
    code_dir = _source_path(run_dir, _nonempty(spec.get("code_dir"), "code_dir"))
    population = sorted(
        x for x, candidate in devflow_lib.load_tasks(run_dir).items()
        if candidate.get("flow") == task.get("flow") and candidate.get("approval_mode") == "알림"
        and candidate.get("status") == kinds.DONE)
    if not population:
        raise ShadowError("같은 흐름에 notified 완료 task가 없어 모집단을 만들 수 없음")
    def entries(key):
        paths = spec.get(key)
        if not isinstance(paths, list) or not paths:
            raise ShadowError("{}는 비어 있지 않은 경로 배열이어야 함".format(key))
        out = []
        for raw in paths:
            p = _source_path(run_dir, str(raw))
            section = "판정 기준" if os.path.normcase(p) == os.path.normcase(task["_path"]) else ""
            out.append({"path": os.path.abspath(p), "sha256": entry_hash(p, section), "section": section})
        return out
    context, allowed = spec.get("context"), spec.get("allowed_paths")
    if not isinstance(context, list) or not isinstance(allowed, list):
        raise ShadowError("context와 allowed_paths는 배열이어야 함")
    seed = {"code_dir": code_dir, "git_snapshot": {"head_sha": "", "files": []}}
    # 선언값을 비교하는 함수와 같은 Git 포맷을 만들기 위해 먼저 실제값을 계산한다.
    try:
        head = subprocess.run(["git", "-C", code_dir, "rev-parse", "HEAD"], capture_output=True,
                              check=True, text=True, encoding="utf-8").stdout.strip()
        tracked = {x.decode("utf-8") for x in subprocess.run(
            ["git", "-C", code_dir, "ls-files", "-z"], capture_output=True, check=True).stdout.split(b"\0") if x}
        status_raw = subprocess.run(["git", "-C", code_dir, "status", "--porcelain=v1", "-z", "--untracked-files=all"],
                                    capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError) as e:
        raise ShadowError("code_dir Git 상태를 읽지 못함: {}".format(e))
    statuses, chunks, i = {}, [x.decode("utf-8") for x in status_raw.split(b"\0") if x], 0
    while i < len(chunks):
        row, i = chunks[i], i + 1
        code, rel = row[:2], row[3:]
        if code[0] in "RC" or code[1] in "RC":
            if i >= len(chunks):
                raise ShadowError("Git rename/copy 상태가 불완전함")
            rel, i = rel + " -> " + chunks[i], i + 1
        statuses[rel] = code
    all_paths = tracked | {p for p, code in statuses.items() if " -> " not in p and code == "??"}
    files = [{"path": p.replace("\\", "/"), "status": statuses.get(p, "  "),
              "sha256": raw_hash(os.path.join(code_dir, p)) if os.path.isfile(os.path.join(code_dir, p)) else None}
             for p in sorted(all_paths)]
    value = {"candidate_sha": head, "code_dir": code_dir, "git_snapshot": {"head_sha": head, "files": files},
             "population": population, "criteria": entries("criteria_paths"), "copies": entries("copy_paths"),
             "context": [str(x) for x in context],
             "allowed_paths": [os.path.abspath(_source_path(run_dir, str(x))) for x in allowed]}
    _write_json(out_path, value)
    return out_path


def shadow_freeze(run_dir, tid, stage, evidence_path):
    task = _task(run_dir, tid)
    if task.get("kind") != "flow-verify":
        raise ShadowError("A shadow 대상은 flow-verify task만")
    try:
        _plan(run_dir, "A")
    except ShadowError as e:
        _exclude(task["_dir"], str(e))
        raise
    state = _state(task)
    try:
        _verify_frozen(task, state)
        data = state.get("stages", {}).get(stage)
        if not data or data.get("status") != "open":
            raise ShadowError("열린 단계가 아님: " + stage)
        evidence = _json(evidence_path)
        if evidence.get("input_sha256") != data.get("input_sha256"):
            raise ShadowError("open 때 입력 hash와 evidence가 다름")
        if evidence.get("context") != data.get("context"):
            raise ShadowError("open 때 context와 evidence가 다름")
        if not evidence.get("access_log_path"):
            raise ShadowError("실제 접근 기록 원본이 없음")
        log_path = _source_path(run_dir, _nonempty(evidence.get("access_log_path"), "access_log_path"))
        expected_log_hash = str(evidence.get("access_log_sha256", "")).lower()
        if not HEX256.match(expected_log_hash) or not os.path.isfile(log_path) or raw_hash(log_path) != expected_log_hash:
            raise ShadowError("접근 기록 원본이 없거나 hash가 다름")
        try:
            access_doc = _json(log_path)
            logged_paths = access_doc.get("paths")
        except ShadowError:
            logged_paths = None
        accessed = evidence.get("accessed_paths")
        if (not isinstance(accessed, list) or not accessed or
                not isinstance(logged_paths, list) or logged_paths != accessed or
                not _nonempty(evidence.get("isolation_provider"), "isolation_provider") or
                not _nonempty(evidence.get("isolation_session_id"), "isolation_session_id")):
            raise ShadowError("실제 접근 기록이나 격리 근거가 불명")
        normalized = {_source_path(run_dir, str(x)) for x in accessed}
        allowed = set(data.get("allowed_paths", [])) | {x["path"] for x in data.get("fixed", [])}
        peer = os.path.join(task["_dir"], "shadow", "candidate.md")
        if (not normalized <= allowed or evidence.get("peer_result_accessed") is not False or
                (stage == "baseline" and os.path.normcase(peer) in normalized)):
            raise ShadowError("상대 결과 선열람 또는 허용하지 않은 경로 접근")
        output = _source_path(run_dir, _nonempty(evidence.get("output_path"), "output_path"))
        if not os.path.isfile(output):
            raise ShadowError("고정할 결과 파일이 없음")
        expected_name = "result.md" if stage in ("candidate", "current") else "judge.md"
        expected_output = os.path.normcase(os.path.abspath(os.path.join(task["_dir"], expected_name)))
        if output != expected_output:
            raise ShadowError("{} 단계 결과는 {}여야 함".format(stage, expected_name))
        digest = file_hash(output)
        snapshot = None
        if stage in ("candidate", "baseline"):
            snapshot = os.path.join(task["_dir"], "shadow", stage + ".md")
            if os.path.exists(snapshot):
                raise ShadowError("고정 사본을 덮어쓰지 않음: " + snapshot)
            with open(snapshot, "wb") as f:
                f.write(canonical_bytes(output))
        data.update({"status": "frozen", "frozen_at": _now(), "output_path": output,
                     "output_sha256": digest, "snapshot": snapshot,
                     "evidence_path": os.path.abspath(evidence_path), "evidence_sha256": raw_hash(evidence_path),
                     "access_log_path": log_path,
                     "access_log_sha256": expected_log_hash, "accessed_path_claims": sorted(normalized),
                     "isolation_verified": False, "comparison_eligibility": "unproven"})
        if stage == "final":
            review = evidence.get("reviewer_conclusion")
            if isinstance(review, dict) and review.get("conclusion") in ("proven", "unproven", "indeterminate"):
                marker = "shadow-review-conclusion: " + review["conclusion"]
                citations = review.get("citations")
                judge_text = devflow_lib.read_text(output)
                who, _ = devflow_lib.judge_header(output)
                valid = marker in judge_text and who == data.get("instance") and who.startswith(
                    devflow_lib.JUDGE_PREFIX.get("judge.md", ""))
                valid, checked_review = _review_citations(
                    run_dir, task, state, output, citations, judge_text) if valid else (False, [])
                data["reviewer_conclusion"] = {"conclusion": review.get("conclusion"),
                                                 "citations": checked_review if valid else [], "valid": valid}
                if valid and review["conclusion"] == "proven":
                    data["comparison_eligibility"] = "proven-by-final-read-judge"
        _write_json(os.path.join(task["_dir"], "shadow", "state.json"), state)
    except ShadowError as e:
        _exclude(task["_dir"], str(e))
        raise


def b_freeze(run_dir, tid, observation_path):
    task = _task(run_dir, tid)
    try:
        _plan(run_dir, "B")
    except ShadowError as e:
        _exclude(task["_dir"], str(e))
        raise
    if task.get("kind") != "wrap-up" or task.get("status") != "진행":
        raise ShadowError("B 관측은 진행 중인 wrap-up task에서만 고정")
    path = os.path.join(task["_dir"], "shadow", "b-observation.json")
    if os.path.exists(path):
        raise ShadowError("B 관측은 덮어쓰거나 자동 재측정하지 않음")
    obs = _json(observation_path)
    for key in ("basis", "source_ci", "current", "candidate_pair"):
        if not isinstance(obs.get(key), dict) or not obs[key]:
            raise ShadowError("OBS.{}는 비어 있지 않은 객체여야 함".format(key))
    _nonempty(obs.get("observed_at"), "OBS.observed_at")
    if obs.get("full_ci_started_at"):
        raise ShadowError("새 전체 CI 시작 뒤 작성한 B 관측은 제외")
    source, current = obs["source_ci"], obs["current"]
    source_tid = str(obs.get("candidate_pair", {}).get("source_task", ""))
    if (obs.get("candidate_pair", {}).get("current_task") != tid or source_tid not in devflow_lib.load_tasks(run_dir) or
            devflow_lib.load_tasks(run_dir)[source_tid].get("status") != kinds.DONE):
        raise ShadowError("candidate_pair는 같은 run의 완료 source task와 현재 wrap-up task여야 함")
    source_task = devflow_lib.load_tasks(run_dir)[source_tid]
    source_judge = os.path.join(source_task["_dir"], "judge-run.md")
    source_judge_text = devflow_lib.read_text(source_judge) if os.path.isfile(source_judge) else ""
    first = source_judge_text.splitlines()[0] if source_judge_text.splitlines() else ""
    match = devflow_lib.JUDGE_LINE.match(first)
    prefix = devflow_lib.JUDGE_PREFIX.get("judge-run.md", "")
    source_ok, source_why = devflow_lib.judges_present(source_task)
    source_ci = _final_ci_values(source_judge_text)
    if (not match or not match.group(1).startswith(prefix) or not source_ok or source_ci is None):
        raise ShadowError("완료 source task의 독립 judge-run 원본이 없음")
    code_dir = _source_path(run_dir, _nonempty(current.get("code_dir"), "current.code_dir"))
    try:
        actual_head = subprocess.run(["git", "-C", code_dir, "rev-parse", "HEAD"], capture_output=True,
                                     check=True, text=True, encoding="utf-8").stdout.strip()
        dirty = subprocess.run(["git", "-C", code_dir, "status", "--porcelain"], capture_output=True,
                               check=True, text=True, encoding="utf-8").stdout.strip()
    except (OSError, subprocess.CalledProcessError) as e:
        raise ShadowError("B 현재 Git 후보를 읽지 못함: {}".format(e))
    exact = ("full_sha", "input_sha256", "artifact_digest", "db_state_sha256")
    conditions = {"exact_identity_values": all(source.get(k) and source.get(k) == current.get(k) for k in exact)}
    possible = conditions["exact_identity_values"]
    proof = ("commands_sha256", "environment_sha256", "complete", "independent")
    conditions["command_environment_values"] = all(source.get(k) and source.get(k) == current.get(k) for k in proof[:2])
    conditions["source_complete_independent"] = source.get("complete") is True and source.get("independent") is True
    possible = possible and conditions["command_environment_values"] and conditions["source_complete_independent"]
    evidence = obs.get("evidence_files")
    try:
        checked = _check_raw_entries(run_dir, evidence, "evidence_files")
    except ShadowError:
        checked, possible = [], False
    required_roles = {"source_ci_log", "artifact", "db_state", "installed_environment", "commands", "input_manifest"}
    roles = {str(x.get("role", "")) for x in evidence or [] if isinstance(x, dict)}
    conditions["required_evidence_roles"] = required_roles <= roles
    possible = possible and conditions["required_evidence_roles"]
    by_role = {str(x.get("role", "")): x for x in evidence or [] if isinstance(x, dict)}
    conditions.update({
        "source_log_path": _source_path(run_dir, str(by_role.get("source_ci_log", {}).get("path", ""))) ==
                           os.path.normcase(os.path.abspath(source_judge)),
        "source_log_hash": raw_hash(source_judge) == by_role.get("source_ci_log", {}).get("sha256"),
        "current_clean_head": not dirty and actual_head == current.get("full_sha"),
        "source_commit": str(source_task.get("commit", "")) == source.get("full_sha"),
        "artifact_hash": source.get("artifact_digest") == by_role.get("artifact", {}).get("sha256"),
        "db_hash": source.get("db_state_sha256") == by_role.get("db_state", {}).get("sha256"),
        "environment_hash": source.get("environment_sha256") == by_role.get("installed_environment", {}).get("sha256"),
        "commands_hash": source.get("commands_sha256") == by_role.get("commands", {}).get("sha256"),
        "input_hash": source.get("input_sha256") == by_role.get("input_manifest", {}).get("sha256"),
        "full_sha_format": GIT_SHA.match(str(source.get("full_sha", ""))) is not None,
        "digest_formats": all(HEX256.match(str(source.get(k, ""))) for k in
                              ("input_sha256", "artifact_digest", "db_state_sha256",
                               "commands_sha256", "environment_sha256")),
    })
    possible = possible and all(conditions.values())
    conditions["source_full_ci_contract"] = (source_ci.get("범위") == "전체 검증" and
                                               source_ci.get("검증 commit") == source.get("full_sha") and
                                               source_ci.get("검증 artifact") == source.get("artifact_digest"))
    possible = possible and conditions["source_full_ci_contract"]
    out = {"schema": "devflow-shadow-b-v1", "status": "indeterminate" if possible else "impossible",
           "recorded_at": _now(), "observation_sha256": raw_hash(observation_path), "observation": obs,
           "checked_evidence": checked, "necessary_conditions_match": bool(possible),
           "condition_checks": conditions, "identity_verified": False, "actual_reuse": False}
    _write_json(path, out)


def _final_ci_values(text):
    section = devflow_lib.sections(text, level=2).get("최종 배포 후보 CI")
    if section is None:
        return None
    values = {}
    for line in section.splitlines():
        m = re.match(r"^-\s*(범위|검증 commit|검증 artifact)\s*:\s*(.+?)\s*$", line.strip())
        if m:
            values[m.group(1)] = m.group(2)
    return values if all(values.get(k) for k in ("범위", "검증 commit", "검증 artifact")) else None


def _iso_utc(value, name):
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        raise ShadowError("{} 시각이 ISO-8601이 아님".format(name))
    if parsed.tzinfo is None:
        raise ShadowError("{} 시각에 timezone이 없음".format(name))
    return parsed.astimezone(timezone.utc)


def _refresh_b(run_dir, task, gate_complete=False):
    path = os.path.join(task["_dir"], "shadow", "b-observation.json")
    if not os.path.isfile(path):
        return "missing", "B 관측 없음"
    b = _json(path)

    def invalidate(reason, status="excluded"):
        b.pop("reviewer_conclusion", None)
        b.pop("reviewer_judge_path", None)
        b.pop("reviewer_judge_sha256", None)
        b["reviewer_invalidated"] = reason
        _write_json(path, b)
        return status, reason

    excluded_path = os.path.join(task["_dir"], "shadow", "excluded.json")
    if os.path.isfile(excluded_path):
        try:
            reason = _json(excluded_path).get("reason", "sticky excluded")
        except ShadowError:
            reason = "sticky excluded"
        return invalidate("이미 비교 제외됨: " + reason)
    try:
        _plan(run_dir, "B")
    except ShadowError as e:
        _exclude(task["_dir"], str(e))
        return invalidate("B 계획/승인 고정값 불일치: " + str(e))
    if b.get("status") != "indeterminate" or b.get("necessary_conditions_match") is not True:
        return invalidate("B 사전 관측 필요조건이 일치한 indeterminate 사례가 아님")
    current = b.get("observation", {}).get("current", {})
    try:
        code_dir = _source_path(run_dir, _nonempty(current.get("code_dir"), "current.code_dir"))
        actual_head = subprocess.run(["git", "-C", code_dir, "rev-parse", "HEAD"], capture_output=True,
                                     check=True, text=True, encoding="utf-8").stdout.strip()
        dirty = subprocess.run(["git", "-C", code_dir, "status", "--porcelain"], capture_output=True,
                               check=True, text=True, encoding="utf-8").stdout.strip()
    except (OSError, subprocess.CalledProcessError, ShadowError) as e:
        _exclude(task["_dir"], "B 현재 Git 후보 재검사 실패")
        return invalidate("B 현재 Git 후보 재검사 실패: " + str(e))
    if dirty or actual_head != current.get("full_sha"):
        _exclude(task["_dir"], "B 관측 뒤 current HEAD/작업 트리가 달라짐")
        return invalidate("B 관측 뒤 current HEAD/작업 트리가 달라짐")
    for entry in b.get("checked_evidence", []):
        if not os.path.isfile(entry.get("path", "")) or raw_hash(entry["path"]) != entry.get("sha256"):
            _exclude(task["_dir"], "B 원 evidence가 고정 뒤 바뀌거나 삭제됨")
            return invalidate("B 원 evidence 변조")
    judge_path = os.path.join(task["_dir"], "judge-run.md")
    if not os.path.isfile(judge_path):
        return invalidate("B 후속 독립 실행 판정 전", "pending")
    text = devflow_lib.read_text(judge_path)
    found = re.search(r"(?:full_ci_started_at|전체 CI 시작)\s*[:|]\s*([^\s|]+)", text)
    if not found:
        return invalidate("B 실제 전체 CI 시작 시각 불명")
    try:
        started = _iso_utc(found.group(1), "full_ci_started_at")
        observed = _iso_utc(b.get("observation", {}).get("observed_at", ""), "observed_at")
    except ShadowError as e:
        _exclude(task["_dir"], str(e))
        return invalidate(str(e))
    if started <= observed:
        _exclude(task["_dir"], "B 관측이 실제 전체 CI 시작 뒤 작성됨")
        return invalidate("B 사후작성")
    if not gate_complete:
        return invalidate("B 운영 gate 완료 전", "pending")
    ok, why = devflow_lib.judges_present(task)
    ci = _final_ci_values(text)
    conclusion = re.search(r"shadow-b-conclusion\s*:\s*(possible|impossible|indeterminate)", text)
    if (not ok or ci is None or ci.get("범위") != "전체 검증" or
            ci.get("검증 commit") != current.get("full_sha") or
            ci.get("검증 artifact") != current.get("artifact_digest") or not conclusion):
        return invalidate("B 운영 gate 판정/전체 CI 근거 불완전: " + (why or "필수 절/값"))
    b["reviewer_conclusion"] = conclusion.group(1)
    b.pop("reviewer_invalidated", None)
    b["reviewer_judge_path"], b["reviewer_judge_sha256"] = judge_path, file_hash(judge_path)
    _write_json(path, b)
    return "observed", "B 완료 gate의 독립 run-judge 결론과 원본 hash 고정"


def observe_transition(run_dir, task, old, new):
    """정상 전이 뒤 관측만 덧붙인다. 누락/불일치는 기존 gate 결과를 바꾸지 않는다."""
    plan_path = os.path.join(run_dir, "shadow-plan.json")
    if not os.path.isfile(plan_path) or new not in ("자체검증", "승인대기", kinds.DONE):
        return ""
    shadow_dir = os.path.join(task["_dir"], "shadow")
    os.makedirs(shadow_dir, exist_ok=True)
    status = "not-applicable"
    reason = "shadow 기록 없음"
    try:
        plan = _json(plan_path)
        if (_version(task.get("started_version")) >= MIN_VERSION and "A" in plan.get("experiments", [])
                and task.get("kind") == "flow-verify"):
            _plan(run_dir, "A")
            state = _state(task)
            _verify_frozen(task, state)
            complete = all(state.get("stages", {}).get(s, {}).get("status") == "frozen" for s in STAGES)
            eligible = state.get("stages", {}).get("final", {}).get("comparison_eligibility") == "proven-by-final-read-judge"
            status = "observed" if complete and eligible else ("excluded" if complete else "missing")
            reason = ("A 네 단계와 final 독립 판정 근거 고정·재검사 완료" if status == "observed" else
                      "A 네 단계는 고정됐으나 독립 격리 판정 미입증" if complete else "A 네 단계 고정 기록 불완전")
            if os.path.exists(os.path.join(shadow_dir, "excluded.json")):
                status, reason = "excluded", "sticky excluded"
        if (task.get("kind") == "wrap-up" and
                ("B" in plan.get("experiments", []) or os.path.isfile(os.path.join(shadow_dir, "b-observation.json")))):
            status, reason = _refresh_b(run_dir, task, gate_complete=(new == kinds.DONE))
    except Exception as e:
        if task.get("kind") == "wrap-up" and os.path.isfile(os.path.join(shadow_dir, "b-observation.json")):
            try:
                status, reason = _refresh_b(run_dir, task, gate_complete=(new == kinds.DONE))
            except Exception as nested:
                status, reason = "excluded", str(nested)
        else:
            status, reason = "excluded", str(e)
    path = os.path.join(shadow_dir, "transition-observations.jsonl")
    line = json.dumps({"at": _now(), "old": old, "new": new, "status": status, "reason": reason},
                      ensure_ascii=False, sort_keys=True, allow_nan=False)
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(line + "\n")
    return "shadow 관측: {} ({})".format(status, reason)


def notified_evidence(run_dir, task):
    """A opt-in 실행에서 collect가 전달할 원 판정의 기계적 사실만 만든다."""
    try:
        plan = _json(os.path.join(run_dir, "shadow-plan.json"))
    except ShadowError:
        return None
    if plan.get("status") != "active" or "A" not in plan.get("experiments", []):
        return None
    judges = []
    has_scope = True
    for name in ("judge.md", "judge-run.md"):
        path = os.path.join(task["_dir"], name)
        if not os.path.isfile(path):
            continue
        text = devflow_lib.read_text(path)
        scope = "## 판정 대상과 범위" in text
        has_scope = has_scope and scope
        judges.append({"path": os.path.abspath(path), "sha256": file_hash(path), "scope_section": scope})
    criteria = task.get("_sections", {}).get("판정 기준", "")
    criteria_sha = hashlib.sha256(criteria.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")).hexdigest()
    commit = str(task.get("commit", "") or "")
    snapshot_map = {"verified": False,
                    "reason": "텍스트에 적힌 SHA/commit만으로 원 Git snapshot 내용을 재구성·대조할 수 없음"}
    eligible = False
    return {"task": task.get("id"), "commit": commit, "criteria_sha256": criteria_sha,
            "judges": judges, "snapshot_to_commit": snapshot_map,
            "inheritance_candidate": eligible,
            "reason": "기계 근거 완전" if eligible else "scope 또는 snapshot→commit 근거 없음; 자동 상속 불가"}


def shadow_status(run_dir, tid):
    task = _task(run_dir, tid)
    try:
        plan = _plan(run_dir, "A")
    except ShadowError:
        try:
            plan = _plan(run_dir, "B")
        except ShadowError as e:
            b_path = os.path.join(task["_dir"], "shadow", "b-observation.json")
            if os.path.isfile(b_path):
                _refresh_b(run_dir, task, gate_complete=(task.get("status") == kinds.DONE))
            _exclude(task["_dir"], str(e))
            raise
    excluded = os.path.join(task["_dir"], "shadow", "excluded.json")
    if os.path.isfile(excluded):
        raise ShadowError("비교 제외: " + str(_json(excluded).get("reason", "이유 없음")))
    out = {"task": tid, "experiments": plan.get("experiments", []), "A": None, "B": None}
    applicable = False
    if "A" in out["experiments"] and task.get("kind") == "flow-verify":
        applicable = True
        state = _state(task)
        _verify_frozen(task, state)
        out["A"] = {s: state.get("stages", {}).get(s, {}).get("status", "missing") for s in STAGES}
        out["A_comparison_eligibility"] = state.get("stages", {}).get("final", {}).get(
            "comparison_eligibility", "unproven")
        if any(out["A"][s] != "frozen" for s in ("candidate", "baseline")):
            raise ShadowError("shadow-check는 candidate와 baseline 고정 뒤에만 성공")
    if "B" in out["experiments"] and task.get("kind") == "wrap-up":
        applicable = True
        path = os.path.join(task["_dir"], "shadow", "b-observation.json")
        status, reason = _refresh_b(run_dir, task, gate_complete=(task.get("status") == kinds.DONE))
        out["B"] = {"machine_status": _json(path).get("status") if os.path.isfile(path) else "missing",
                    "review_status": status, "reason": reason}
    if not applicable:
        raise ShadowError("task kind에 적용되는 활성 shadow 실험이 없음")
    print(json.dumps(out, ensure_ascii=False, sort_keys=True))


def main(argv):
    devflow_lib.utf8_stdout()
    if len(argv) < 3:
        print(__doc__)
        return 2
    run_dir, args = argv[1], argv[2:]
    try:
        if args[0] == "--shadow-inputs" and len(args) == 4:
            make_inputs(run_dir, args[1], args[2], args[3])
        elif args[0] == "--shadow-open" and len(args) == 7 and args[3] == "--instance" and args[5] == "--inputs":
            shadow_open(run_dir, args[1], args[2], args[4], args[6])
        elif args[0] == "--shadow-freeze" and len(args) == 5 and args[3] == "--evidence":
            shadow_freeze(run_dir, args[1], args[2], args[4])
        elif args[0] == "--shadow-b-freeze" and len(args) == 4 and args[2] == "--observation":
            b_freeze(run_dir, args[1], args[3])
        elif args[0] == "--shadow-check" and len(args) == 2:
            shadow_status(run_dir, args[1])
        else:
            print(__doc__)
            return 2
    except ShadowError as e:
        print("실험 조건 불충족: " + str(e))
        return 3
    print("shadow 기록 완료")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
