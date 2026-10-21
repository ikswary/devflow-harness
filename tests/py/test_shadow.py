import hashlib
import json
import os
import subprocess
from pathlib import Path

import shadow_check
from conftest import RunDir, front_matter, run_script, write


def dump(path, value):
    return write(path, json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n")


def sha(path, canonical=True):
    raw = Path(path).read_bytes()
    if canonical:
        raw = raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def section_sha(path, name):
    text = Path(path).read_bytes().decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    body = text.split("## " + name + "\n", 1)[1]
    body = body.split("## ", 1)[0]
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def run_version(run_dir, value="1.0.2", choice="A"):
    path = run_dir.path / "run.md"
    text = path.read_text(encoding="utf-8")
    text = text.replace("harness_version:\n", "harness_version: {}\n".format(value))
    text += "| 검증 효율 실험 | {} |\n".format(choice)
    write(path, text)
    write(run_dir.path / "decisions.md", "# 결정\n\n사용자 승인: shadow {}\n".format(choice))


def plan(run_dir, choice="A"):
    value = {"experiments": choice.split(","), "repository": "fixture", "work_type": "implementation",
             "approval_evidence": "사용자 승인: shadow {}".format(choice), "N": 2,
             "counts_by_type": {"implementation": 2}, "S": {"value": 1, "unit": "minute/run"},
             "H": {"value": 3, "unit": "minute/run"}, "E": 0.2, "end_date": "2026-12-31"}
    if "A" in choice:
        value["A"] = {"R": 0.05, "Q": 0.95, "strata": ["risk", "size"], "seed": "fixed-7",
                      "ratio": 0.25, "rotation": "round-robin by run", "calculation": "one-sided Wilson upper bound"}
    return dump(run_dir.path / "PLAN.json", value)


def init(run_dir, choice="A"):
    run_version(run_dir, choice=choice)
    p = plan(run_dir, choice)
    r = run_script("collect", run_dir, "--shadow-init", p)
    assert r.returncode == 0, r.output
    return p


def git_repo(path):
    path.mkdir()
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "fixture@example.com"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Fixture"], check=True)
    write(path / "tracked.txt", "tracked\n")
    subprocess.run(["git", "-C", str(path), "add", "tracked.txt"], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-qm", "fixture"], check=True)
    return path


def snapshot(repo):
    head = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], check=True,
                          capture_output=True, text=True).stdout.strip()
    return head, {"head_sha": head, "files": [{"path": "tracked.txt", "status": "  ",
                                                  "sha256": sha(repo / "tracked.txt")}]}


def inputs(run_dir, repo, tid="T001"):
    head, git = snapshot(repo)
    task_path = run_dir.task_dir(tid) / "task.md"
    output = run_dir.task_dir(tid) / "result.md"
    value = {"candidate_sha": head, "code_dir": str(repo), "git_snapshot": git,
             "population": ["T000"],
             "criteria": [{"path": str(task_path), "sha256": section_sha(task_path, "판정 기준"),
                            "section": "판정 기준"}],
             "copies": [{"path": str(repo / "tracked.txt"), "sha256": sha(repo / "tracked.txt")}],
             "context": ["candidate isolated context"],
             "allowed_paths": [str(task_path), str(repo / "tracked.txt"), str(output)]}
    return dump(run_dir.path / "inputs.json", value)


def open_candidate(run_dir, repo, instance="candidate-1"):
    inp = inputs(run_dir, repo)
    return run_script("shadow_check", run_dir, "--shadow-open", "T001", "candidate",
                      "--instance", instance, "--inputs", inp), inp


def freeze(run_dir, inp, text=b"candidate  \r\nwithout-final-newline"):
    out = run_dir.task_dir("T001") / "result.md"
    out.write_bytes(text)
    access = dump(run_dir.path / "access.json", {"paths": [str(out)]})
    evidence = dump(run_dir.path / "evidence.json",
                    {"output_path": str(out), "input_sha256": sha(inp, canonical=False),
                     "context": ["candidate isolated context"], "access_log_path": str(access),
                     "access_log_sha256": sha(access, canonical=False), "isolation_provider": "fixture",
                     "isolation_session_id": "session-candidate", "accessed_paths": [str(out)],
                     "peer_result_accessed": False})
    return run_script("shadow_check", run_dir, "--shadow-freeze", "T001", "candidate",
                      "--evidence", evidence)


def prepared(tmp_path):
    run_dir = RunDir(tmp_path / "run")
    init(run_dir)
    run_dir.task("T000", "notified source", kind="implementation", status="완료", flow="F",
                 approval_mode="알림", started_version="1.0.2")
    run_dir.task("T001", "shadow target", kind="flow-verify", status="진행", flow="F", started_version="1.0.2")
    repo = git_repo(tmp_path / "repo")
    return run_dir, repo


def test_shadow_init_rejects_old_upgraded_or_ambiguous_run(tmp_path):
    old = RunDir(tmp_path / "old")
    run_version(old, "1.0.1")
    p = plan(old)
    assert run_script("collect", old, "--shadow-init", p).returncode == 3

    upgraded = RunDir(tmp_path / "upgraded")
    run_version(upgraded)
    upgraded.task("T001", "already exists")
    p2 = plan(upgraded)
    assert run_script("collect", upgraded, "--shadow-init", p2).returncode == 3

    bad = RunDir(tmp_path / "bad")
    run_version(bad, choice="A")
    p3 = plan(bad, choice="B")
    assert run_script("collect", bad, "--shadow-init", p3).returncode == 3


def test_non_opt_in_collect_and_old_task_transition_remain_unchanged(tmp_path):
    run_dir = RunDir(tmp_path / "plain")
    run_dir.task("T001", "plain", kind="implementation", status="진행")
    out = tmp_path / "out"
    r = run_script("collect", run_dir, out)
    assert r.returncode == 0, r.output
    assert not (run_dir.path / "shadow-plan.json").exists()
    assert not (run_dir.task_dir("T001") / "shadow").exists()


def test_candidate_freeze_canonicalizes_lf_and_preserves_spaces_and_final_newline_state(tmp_path):
    run_dir, repo = prepared(tmp_path)
    opened, inp = open_candidate(run_dir, repo)
    assert opened.returncode == 0, opened.output
    frozen = freeze(run_dir, inp)
    assert frozen.returncode == 0, frozen.output
    assert (run_dir.task_dir("T001") / "shadow" / "candidate.md").read_bytes() == b"candidate  \nwithout-final-newline"


def test_stage_order_and_instance_id_are_enforced(tmp_path):
    run_dir, repo = prepared(tmp_path)
    inp = inputs(run_dir, repo)
    early = run_script("shadow_check", run_dir, "--shadow-open", "T001", "baseline",
                       "--instance", "same", "--inputs", inp)
    assert early.returncode == 3 and "이전 단계" in early.output
    opened, inp = open_candidate(run_dir, repo, "same")
    assert opened.returncode == 0
    assert freeze(run_dir, inp).returncode == 0
    again = inputs(run_dir, repo)
    duplicate = run_script("shadow_check", run_dir, "--shadow-open", "T001", "baseline",
                           "--instance", "same", "--inputs", again)
    assert duplicate.returncode == 3 and "instance ID" in duplicate.output


def test_fixed_source_deletion_or_new_git_file_stickily_excludes(tmp_path):
    run_dir, repo = prepared(tmp_path)
    opened, inp = open_candidate(run_dir, repo)
    assert opened.returncode == 0 and freeze(run_dir, inp).returncode == 0
    write(repo / "new.txt", "new\n")
    next_inputs = inputs(run_dir, repo)  # 선언은 옛 스냅샷이어도 실제 Git 집합이 우선이다
    result = run_script("shadow_check", run_dir, "--shadow-open", "T001", "baseline",
                        "--instance", "baseline-1", "--inputs", next_inputs)
    assert result.returncode == 3
    excluded = run_dir.task_dir("T001") / "shadow" / "excluded.json"
    assert excluded.is_file()
    first = excluded.read_bytes()
    (repo / "new.txt").unlink()
    retry = run_script("shadow_check", run_dir, "--shadow-open", "T001", "baseline",
                       "--instance", "baseline-2", "--inputs", next_inputs)
    assert retry.returncode == 3 and excluded.read_bytes() == first


def test_freeze_without_real_access_log_is_excluded(tmp_path):
    run_dir, repo = prepared(tmp_path)
    opened, inp = open_candidate(run_dir, repo)
    assert opened.returncode == 0
    out = run_dir.task_dir("T001") / "result.md"
    write(out, "candidate\n")
    evidence = dump(run_dir.path / "evidence.json",
                    {"output_path": str(out), "input_sha256": sha(inp, canonical=False),
                     "context": ["candidate isolated context"], "accessed_paths": [str(out)],
                     "isolation_known": True, "peer_result_accessed": False})
    r = run_script("shadow_check", run_dir, "--shadow-freeze", "T001", "candidate", "--evidence", evidence)
    assert r.returncode == 3 and "접근 기록" in r.output
    assert (run_dir.task_dir("T001") / "shadow" / "excluded.json").is_file()


def test_freeze_rejects_other_tasks_same_named_output(tmp_path):
    run_dir, repo = prepared(tmp_path)
    run_dir.task("T002", "other", kind="flow-verify", status="진행", flow="F", started_version="1.0.2")
    inp = inputs(run_dir, repo)
    value = json.loads(inp.read_text(encoding="utf-8"))
    other = run_dir.task_dir("T002") / "result.md"
    value["allowed_paths"].append(str(other))
    dump(inp, value)
    opened = run_script("collect", run_dir, "--shadow-open", "T001", "candidate",
                        "--instance", "candidate-x", "--inputs", inp)
    assert opened.returncode == 0, opened.output
    write(other, "forged\n")
    access = dump(run_dir.path / "access.json", {"paths": [str(other)]})
    evidence = dump(run_dir.path / "evidence.json",
                    {"output_path": str(other), "input_sha256": sha(inp, False),
                     "context": ["candidate isolated context"], "access_log_path": str(access),
                     "access_log_sha256": sha(access, False), "isolation_provider": "fixture",
                     "isolation_session_id": "x", "accessed_paths": [str(other)], "peer_result_accessed": False})
    frozen = run_script("collect", run_dir, "--shadow-freeze", "T001", "candidate", "--evidence", evidence)
    assert frozen.returncode == 3 and "result.md" in frozen.output


def test_access_log_paths_are_truth_and_must_equal_claims(tmp_path):
    run_dir, repo = prepared(tmp_path)
    opened, inp = open_candidate(run_dir, repo)
    assert opened.returncode == 0
    out = write(run_dir.task_dir("T001") / "result.md", "candidate\n")
    access = dump(run_dir.path / "access.json", {"paths": ["C:/forbidden-peer-result.md"]})
    evidence = dump(run_dir.path / "evidence.json",
                    {"output_path": str(out), "input_sha256": sha(inp, False),
                     "context": ["candidate isolated context"], "access_log_path": str(access),
                     "access_log_sha256": sha(access, False), "isolation_provider": "fixture",
                     "isolation_session_id": "x", "accessed_paths": [str(out)], "peer_result_accessed": False})
    frozen = run_script("collect", run_dir, "--shadow-freeze", "T001", "candidate", "--evidence", evidence)
    assert frozen.returncode == 3 and "격리 근거" in frozen.output


def test_b_observation_after_full_ci_start_is_rejected(tmp_path):
    run_dir = RunDir(tmp_path / "run")
    init(run_dir, "B")
    run_dir.task("T001", "wrap", kind="wrap-up", status="진행", started_version="1.0.2")
    obs = {"basis": {"why": "prospective"}, "source_ci": {"full_sha": "a" * 40},
           "current": {"full_sha": "a" * 40}, "candidate_pair": {"source": "T000", "current": "T001"},
           "observed_at": "2026-10-21T12:00:00+09:00", "full_ci_started_at": "2026-10-21T11:00:00+09:00"}
    r = run_script("shadow_check", run_dir, "--shadow-b-freeze", "T001", "--observation",
                   dump(run_dir.path / "obs.json", obs))
    assert r.returncode == 3 and "시작 뒤" in r.output


def test_shadow_observation_cannot_replace_existing_judge_gate(tmp_path):
    run_dir = RunDir(tmp_path / "run")
    init(run_dir)
    run_dir.task("T001", "needs judge", kind="design", status="자체검증", started_version="1.0.2")
    shadow = run_dir.task_dir("T001") / "shadow"
    dump(shadow / "state.json", {"schema": "devflow-shadow-a-v1", "stages": {"candidate": {"status": "frozen"}}})
    r = run_script("task_set", run_dir, "T001", "--status", "승인대기")
    assert r.returncode == 3 and "필요한 판정이 없음" in r.output
    assert not (shadow / "transition-observations.jsonl").exists()


def test_input_helper_and_four_stages_finish_then_transition_records_observation(tmp_path):
    run_dir, repo = prepared(tmp_path)
    spec = dump(run_dir.path / "spec.json",
                {"code_dir": str(repo), "criteria_paths": [str(run_dir.task_dir("T001") / "task.md")],
                 "copy_paths": [str(repo / "tracked.txt")], "context": ["isolated"],
                 "allowed_paths": [str(run_dir.task_dir("T001") / "task.md"), str(repo / "tracked.txt"),
                                   str(run_dir.task_dir("T001") / "result.md"),
                                   str(run_dir.task_dir("T001") / "judge.md")]})
    generated = run_dir.path / "generated-inputs.json"
    made = run_script("collect", run_dir, "--shadow-inputs", "T001", spec, generated)
    assert made.returncode == 0 and generated.is_file(), made.output
    for index, stage in enumerate(("candidate", "baseline", "current", "final"), 1):
        instance = "rjudge-T001" if stage == "final" else "instance-{}".format(index)
        opened = run_script("collect", run_dir, "--shadow-open", "T001", stage,
                            "--instance", instance, "--inputs", generated)
        assert opened.returncode == 0, opened.output
        output = run_dir.task_dir("T001") / ("judge.md" if stage in ("baseline", "final") else "result.md")
        access = dump(run_dir.path / (stage + "-access.json"), {"paths": [str(output)]})
        evidence_value = {"output_path": str(output), "input_sha256": sha(generated, canonical=False),
                          "context": ["isolated"], "access_log_path": str(access),
                          "access_log_sha256": sha(access, canonical=False), "isolation_provider": "fixture-runtime",
                          "isolation_session_id": "stage-{}".format(index), "accessed_paths": [str(output)],
                          "peer_result_accessed": False}
        if stage == "final":
            state = json.loads((run_dir.task_dir("T001") / "shadow" / "state.json").read_text(encoding="utf-8"))
            citations = []
            for name, data in state["stages"].items():
                paths = [data["input_copy"]]
                if name != "final":
                    paths.append(data["access_log_path"])
                if name != "final":
                    paths += [data["evidence_path"], data.get("snapshot") or data["output_path"]]
                for path in paths:
                    citations.append({"path": path, "sha256": sha(path, False), "location": name + "-evidence"})
            citations += [{"path": str(access), "sha256": sha(access, False), "location": "final-access"}]
            refs = "\n".join("{}#{}".format(x["path"].lower(), x["location"]) for x in citations)
            write(output, "판정자: rjudge-T001 2026-10-21 12:00:00\nshadow-review-conclusion: proven\n" + refs + "\n")
            evidence_value["reviewer_conclusion"] = {"conclusion": "proven", "citations": citations}
        else:
            write(output, stage + "\n")
        evidence = dump(run_dir.path / (stage + "-evidence.json"), evidence_value)
        frozen = run_script("collect", run_dir, "--shadow-freeze", "T001", stage, "--evidence", evidence)
        assert frozen.returncode == 0, frozen.output
    checked = run_script("collect", run_dir, "--shadow-check", "T001")
    assert checked.returncode == 0 and '"A_comparison_eligibility": "proven-by-final-read-judge"' in checked.output
    moved = run_script("task_set", run_dir, "T001", "--status", "자체검증")
    assert moved.returncode == 0, moved.output
    observation = (run_dir.task_dir("T001") / "shadow" / "transition-observations.jsonl").read_text(encoding="utf-8")
    assert '"status": "observed"' in observation


def test_resume_metadata_and_unrelated_decision_append_do_not_invalidate_plan(tmp_path):
    run_dir, repo = prepared(tmp_path)
    path = run_dir.path / "run.md"
    text = path.read_text(encoding="utf-8").replace("start_task: T001", "start_task: T001\nsession_id: resumed-2")
    write(path, text)
    with open(run_dir.path / "decisions.md", "a", encoding="utf-8", newline="\n") as f:
        f.write("\n- unrelated later decision\n")
    made = open_candidate(run_dir, repo)[0]
    assert made.returncode == 0, made.output


def test_shadow_record_failure_does_not_cancel_normal_transition(tmp_path):
    run_dir = RunDir(tmp_path / "run")
    init(run_dir)
    run_dir.task("T001", "normal", kind="implementation", status="진행", started_version="1.0.2")
    # 손상된 shadow state를 읽으면 관측은 excluded가 되지만 정상 전이는 유지된다.
    write(run_dir.task_dir("T001") / "shadow" / "state.json", "{broken")
    r = run_script("task_set", run_dir, "T001", "machine_check=0", "--status", "자체검증")
    assert r.returncode == 0, r.output
    assert "진행→자체검증" in r.output


def test_b_records_only_indeterminate_then_independent_run_judge_conclusion(tmp_path):
    run_dir = RunDir(tmp_path / "run")
    init(run_dir, "B")
    repo = git_repo(tmp_path / "repo")
    head = snapshot(repo)[0]
    run_dir.task("T000", "source full CI", kind="implementation", status="완료",
                 started_version="1.0.2", commit=head)
    def judge_text(tid, commit, artifact, marker=""):
        return ("판정자: xjudge-{} 2026-10-21 09:00:00\n\n".format(tid)
                + "## 통과 못 한 기준\n- 없음\n\n## 검사 입력과 독립 근거\n"
                + "- 제품: src\n- 시험: tests\n- 설정: config\n- lock: lock\n- 명령: pytest\n"
                + "- 환경: fixture\n- 판정자: xjudge\n- 시각: 2026-10-21\n- 종료 코드: 0\n- 로그: log\n\n"
                + "## 남은 검사와 자원 대기\n- 없음\n\n## 최종 배포 후보 CI\n"
                + "- 범위: 전체 검증\n- 검증 commit: {}\n- 검증 artifact: {}\n".format(commit, artifact)
                + marker)
    source_judge = run_dir.task_dir("T000") / "judge-run.md"
    run_dir.task("T001", "wrap", kind="wrap-up", status="진행", started_version="1.0.2")
    files = {}
    for role in ("artifact", "db_state", "installed_environment", "commands", "input_manifest"):
        files[role] = write(run_dir.path / (role + ".bin"), role + "\n")
    identity = {"full_sha": head, "input_sha256": sha(files["input_manifest"], False),
                "artifact_digest": sha(files["artifact"], False), "db_state_sha256": sha(files["db_state"], False),
                "commands_sha256": sha(files["commands"], False),
                "environment_sha256": sha(files["installed_environment"], False)}
    write(source_judge, judge_text("T000", head, identity["artifact_digest"]))
    evidence = [{"role": "source_ci_log", "path": str(source_judge), "sha256": sha(source_judge, False)}]
    evidence += [{"role": role, "path": str(path), "sha256": sha(path, False)} for role, path in files.items()]
    source = dict(identity, complete=True, independent=True)
    current = dict(identity, code_dir=str(repo))
    obs = dump(run_dir.path / "obs.json",
               {"basis": {"reason": "prospective"}, "source_ci": source, "current": current,
                "candidate_pair": {"source_task": "T000", "current_task": "T001"},
                "observed_at": "2026-10-21T10:00:00+09:00", "full_ci_started_at": None,
                "evidence_files": evidence})
    frozen = run_script("collect", run_dir, "--shadow-b-freeze", "T001", "--observation", obs)
    assert frozen.returncode == 0, frozen.output
    record_path = run_dir.task_dir("T001") / "shadow" / "b-observation.json"
    assert json.loads(record_path.read_text(encoding="utf-8"))["status"] == "indeterminate"
    write(run_dir.task_dir("T001") / "judge-run.md",
          judge_text("T001", head, identity["artifact_digest"],
                     "\nfull_ci_started_at: 2026-10-21T03:00:00+00:00\nshadow-b-conclusion: possible\n"))
    moved = run_script("task_set", run_dir, "T001", "machine_check=0", "--status", "자체검증")
    assert moved.returncode == 0, moved.output
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert record["status"] == "indeterminate" and "reviewer_conclusion" not in record
    task_path = run_dir.task_dir("T001") / "task.md"
    write(run_dir.task_dir("T001") / "judge.md",
          "판정자: rjudge-T001 2026-10-21 11:00:00\n\n## 통과 못 한 기준\n- 없음\n")
    write(task_path, task_path.read_text(encoding="utf-8").replace("status: 자체검증", "status: 완료"))
    checked = run_script("collect", run_dir, "--shadow-check", "T001")
    assert checked.returncode == 0, checked.output
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert record["reviewer_conclusion"] == "possible" and record["actual_reuse"] is False
    record["status"], record["necessary_conditions_match"] = "impossible", False
    dump(record_path, record)
    assert run_script("collect", run_dir, "--shadow-check", "T001").returncode == 0
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert "reviewer_conclusion" not in record and "필요조건" in record["reviewer_invalidated"]
    record["status"], record["necessary_conditions_match"] = "indeterminate", True
    dump(record_path, record)
    assert run_script("collect", run_dir, "--shadow-check", "T001").returncode == 0
    assert json.loads(record_path.read_text(encoding="utf-8"))["reviewer_conclusion"] == "possible"
    judge_path = run_dir.task_dir("T001") / "judge-run.md"
    write(judge_path, judge_path.read_text(encoding="utf-8").replace("shadow-b-conclusion: possible\n", ""))
    assert run_script("collect", run_dir, "--shadow-check", "T001").returncode == 0
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert "reviewer_conclusion" not in record and "불완전" in record["reviewer_invalidated"]
    text = judge_text("T001", head, identity["artifact_digest"],
                      "\nfull_ci_started_at: 2026-10-21T03:00:00\nshadow-b-conclusion: possible\n")
    write(judge_path, text)
    assert run_script("collect", run_dir, "--shadow-check", "T001").returncode == 0
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert "reviewer_conclusion" not in record and "timezone" in record["reviewer_invalidated"]


def test_b_plan_change_invalidates_stale_reviewer_conclusion(tmp_path):
    run_dir = RunDir(tmp_path / "run")
    init(run_dir, "B")
    run_dir.task("T001", "wrap", kind="wrap-up", status="완료", started_version="1.0.2")
    shadow = run_dir.task_dir("T001") / "shadow"
    dump(shadow / "b-observation.json",
         {"schema": "devflow-shadow-b-v1", "status": "indeterminate", "necessary_conditions_match": True,
          "reviewer_conclusion": "possible", "reviewer_judge_path": "stale", "reviewer_judge_sha256": "a" * 64,
          "checked_evidence": [], "observation": {"current": {"code_dir": str(tmp_path), "full_sha": "a" * 40}}})
    write(run_dir.path / "decisions.md", "# 승인 근거가 제거됨\n")
    checked = run_script("collect", run_dir, "--shadow-check", "T001")
    assert checked.returncode == 3
    record = json.loads((shadow / "b-observation.json").read_text(encoding="utf-8"))
    assert "reviewer_conclusion" not in record and "계획/승인" in record["reviewer_invalidated"]


def test_b_current_git_change_is_sticky_after_clean_done_observation(tmp_path, lib):
    run_dir = RunDir(tmp_path / "run")
    init(run_dir, "B")
    repo = git_repo(tmp_path / "repo")
    head = snapshot(repo)[0]
    run_dir.task("T001", "wrap", kind="wrap-up", status="완료", started_version="1.0.2")
    shadow = run_dir.task_dir("T001") / "shadow"
    dump(shadow / "b-observation.json",
         {"schema": "devflow-shadow-b-v1", "status": "indeterminate", "necessary_conditions_match": True,
          "reviewer_conclusion": "possible", "reviewer_judge_path": "stale", "reviewer_judge_sha256": "a" * 64,
          "checked_evidence": [], "observation": {"current": {"code_dir": str(repo), "full_sha": head}}})
    write(repo / "dirty.txt", "changed after observation\n")
    checked = run_script("collect", run_dir, "--shadow-check", "T001")
    assert checked.returncode == 0
    record = json.loads((shadow / "b-observation.json").read_text(encoding="utf-8"))
    assert "reviewer_conclusion" not in record and "HEAD/작업 트리" in record["reviewer_invalidated"]
    (repo / "dirty.txt").unlink()
    run_path = str(run_dir.path)
    shadow_check.observe_transition(run_path, lib.load_tasks(run_path)["T001"], "승인대기", "완료")
    record = json.loads((shadow / "b-observation.json").read_text(encoding="utf-8"))
    assert "reviewer_conclusion" not in record and "이미 비교 제외됨" in record["reviewer_invalidated"]
    observations = (shadow / "transition-observations.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(observations[-1])["status"] == "excluded"


def test_combined_plan_shadow_check_routes_by_task_kind(tmp_path):
    run_dir = RunDir(tmp_path / "run")
    init(run_dir, "A,B")
    run_dir.task("T001", "flow check", kind="flow-verify", status="진행", flow="F", started_version="1.0.2")
    run_dir.task("T002", "wrap check", kind="wrap-up", status="진행", started_version="1.0.2")
    flow = run_script("collect", run_dir, "--shadow-check", "T001")
    assert flow.returncode == 3 and "candidate와 baseline" in flow.output
    wrap = run_script("collect", run_dir, "--shadow-check", "T002")
    assert wrap.returncode == 0, wrap.output
    assert '"machine_status": "missing"' in wrap.output and '"A": null' in wrap.output
