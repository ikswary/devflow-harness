"""머리 파일(task.md)을 쓰는 유일한 길. 메인은 키와 값만 넘기고 시각·형식·전이 검사는 이 스크립트가 한다.

사용:
  python task_set.py {실행 폴더} {id} [키=값 …] [--status S] [--record "지점|결정|원문"] [--reason "문장"]
                     [--unlisted "이유"] [--archive-judge] [--amend-criteria {파일} --source "출처"]
                     [--screen-snapshot] [--now 키,…]
  python task_set.py {실행 폴더} new --kind K --title "제목" --body-from {파일} [--parent T] [--depends-on T,…]
                     [--flow F] [--origin "근거"] [--from-answer T] [키=값 …]
  python task_set.py {실행 폴더} --check [id]

옵션
  키=값              머리 파일 키를 그 값으로(목록은 `[a, b]`). 없던 키는 머리 끝에 더한다.
                     스크립트가 채우는 키(started_version, rules, 시각, exported_commit, origin, fix_generation 등)는 받지 않는다.
                     `{id}` 호출(기존 task)의 키=값은 status·retry·kind를 받지 않는다(전용 옵션으로만: --status,
                     --archive-judge, new --kind). machine_check는 진행→자체검증 전이(--status 자체검증)와 함께 준 `{id}` 호출에서만 받는다.
                     new는 kind·status·id·title과 스크립트가 채우는 키를 받지 않는다. 거부는 종료 코드 3(파일 그대로).
  --status S         상태 전이. 아래 전이표로 검사하고 어긋나면 종료 코드 3과 이유(파일은 그대로).
                     대기→진행: started·started_version(지금 하네스 판본)·rules(규칙 판, kinds.RULES)를 채운다.
                       배포 실행이면 exec.py로 부모 계획의 명령(실행승인)과 되돌리기(되돌림)를 얼린다.
                     진행→자체검증(implementation·fix): machine_check.py를 돌려 종료 코드를 `machine_check`에
                       (코드 폴더는 flows\\{flow}\\flow.md `dir`. `machine_check=값`을 함께 주면 돌리지 않는다).
                     →승인대기: approval_requested. →완료: approved, (--record의 지점으로) approval_mode.
                     →완료·보류·백로그: waiting_user를 비운다.
                     묻는 단계(stage 실행승인·결과승인·넣기승인)를 --record로 떠나면 exec.py --freeze를 함께 부른다.
                     「정해 주실 것」에 ```cmd 울타리가 있는 다른 task는 승인으로 닫을 때 실행승인을 얼린다.
  stage=값           합치기·마무리·배포 실행의 단계(formats.md 3절). deploy_stage=값도 stage로 받는다.
  --record "지점|결정|원문"  「승인 기록」에 `- {시각} | 지점 | 결정 | 원문: "…"`. 지점이 `알림`이고 원문이 비면
                     `원문: (알림, 답 없음)`. `점검 확인|{코드}|원문`은 그 기록 점검 걸림을 다시 찍지 않게 한다.
  --reason "문장"     사람 답 없이 메인이 판단한 전이(흡수·규칙 바뀜 보류, 다른 곳에서 처리된 백로그). journal에 한 줄.
  --unlisted "이유"   전이표에 없는 짝만 실행한다. journal과 머리 파일 「표 밖 전이」에 남고, 다음 승인 화면 「알릴 것」에
                     "[표 밖 전이]"로 붙는다(점검 확인 전까지). CHANGELOG 후보. 표 안 전이의 조건 미충족(필요한 판정,
                     --record·--reason, --archive-judge, 알림, 판본, stage 좁힘)은 넘기지 못하고 종료 코드 3.
  --archive-judge    judge.md·judge-run.md를 judge.r{n}.md·judge-run.r{n}.md로 보관하고 retry를 올리고, 보관한 판정의
                     「통과 못 한 기준」 번호로 머리 파일 「재시도 범위」를 쓴다. 재시도 상한(run.md 「이번 실행의 값」
                     "자체 검증 재시도", 시작값 2)에 닿았으면 하지 않고 종료 코드 3. `자체검증→진행`은 이것과 함께만.
                     보관한 판정과 같은 n으로 수정 전 사본을 tasks\\{id}\\before.r{n}\\에 뜬다(MANIFEST.md, files\\,
                     코드 kind면 code.patch. 상한 SNAPSHOT_MAX_BYTES, 사본이 실패해도 보관은 하고 목록에 이유. retry_diff.py가 읽는다).
  --amend-criteria {파일} --source "출처"   판정 전(대기·진행)에 「판정 기준」을 바꾼다. 출처는
                     `작성자 {이상 신호 위치}` / `판정자 {대안 문장 위치}` / `사용자 답 {task id} {승인 기록 시각}`
                     (사용자 답은 그 승인 기록 줄에 원문이 있어야 받는다). criteria.amend{n}.md와 「판정 기준 정정」에 남는다.
  --add "절|줄"       본문 절(넘길 이상 신호, 영향받는 task와 처리, 범위 등)에 한 줄을 더한다. 판정 기준·승인 기록처럼
                     전용 옵션이 있는 절은 받지 않는다.
  --screen-snapshot  result.md를 result.pre-screen.md로 떠 둔다(「승인 화면」만 다시 쓰게 하기 전에. 기록 점검이 절 밖만 본다).
  --now 키,…          그 시각 키에 지금 시각.
  --check [id]       기록 점검 결과만 찍는다(쓰지 않음).
  new --from-answer T  사용자 답을 계기로 만드는 task. origin을 `사용자 {T} {답 시각}`(T의 승인 기록에서 원문이 있는 가장
                     늦은 줄)으로 채우고, kind는 「건드릴 파일」에 정본(spec/·design/, 고친 판 revised/) 밖 경로가 있으면 fix,
                     없으면 change로 정한다(비면 거부). --origin을 함께 주면 그 뒤에 붙인다.
  new --kind change  「건드릴 파일」에 정본 밖 경로가 있으면 거부(코드를 고치는 변경은 fix).

전이표(합치기·마무리·배포 실행은 kind로 열고, rules 2 이상으로 시작한 것은 stage로 좁힌다)
  대기→진행 / 진행→자체검증                         조건 없음
  자체검증→진행                                     --archive-judge(재시도)
  자체검증→승인대기                                 필요한 판정이 있음
  자체검증→완료                                     --record(알림·승인) + 필요한 판정. kind가 알림 가능 종류이거나
                                                     합치기·마무리·배포 실행이거나 이미 승인 기록이 있음. 새 task의
                                                     알림 가능 종류는 screen.py 알림 조건 충족
  승인대기→완료                                     --record + 필요한 판정
  승인대기→진행                                     --record(사람 답 뒤 다시 작업, 실행 승인) 또는 --screen-snapshot
  진행→승인대기                                     합치기·마무리·배포 실행만(실행 승인·결과 승인·문서 넣기 승인)
  진행→완료                                         합치기·마무리·배포 실행만, --record + 필요한 판정
  (배포 실행의 →완료는 늘 stage: 끝. 옛 deploy_stage는 stage로 읽는다)
  stage 좁힘(rules 2 이상의 합치기·마무리·배포 실행)
    →승인대기                                       묻는 단계(stage 실행승인·결과승인·넣기승인·직전확인)
    승인대기→진행                                   묻는 단계가 아닌 다음 단계(--screen-snapshot이면 그대로)
    →완료                                           stage 끝. 합치기는 exec.py --verify 통과와 실행 판정의 통과 못 한
                                                     기준 0(아니면 stage=결과승인으로 승인), 마무리는 결과승인에서
                                                     --record와 exec.py --verify 통과, 배포 실행은 유지면 --verify 통과
  *→보류                                            --record 또는 --reason
  보류→대기, 보류→백로그                            --record
  대기→백로그                                       제목이 [백로그]·[안 …] 행이거나 --record·--reason
  백로그→완료                                       --record 또는 --reason "다른 실행·회고에서 처리: {경로}"
  그 밖                                             --unlisted
필요한 판정: 새 task(started_version 있음)는 devflow_lib.required_judges의 파일이 모두 있고 첫 줄 판정자가 그 역할,
            옛 task는 판정 파일이 하나라도 있으면 된다.

종료 코드: 0 / 2 사용법 / 3 거부(이유 출력, 파일 그대로)
"""
import glob
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime

import devflow_lib
import kinds
import retry_diff


# devflow_lib.Reject와 같은 객체(Doc이 내는 거부를 아래 `except Reject`가 그대로 잡는다)
Reject = devflow_lib.Reject

# 키=값과 --unlisted의 거부 문구. 채우는 길은 등록표 kinds.TASK_KEYS
OPTION_ONLY = "{}는 전용 옵션으로만 바꾼다(status → --status, retry → --archive-judge, kind → new --kind)"
SELFCHECK_ONLY = "{}=값은 진행→자체검증 전이(--status 자체검증)와 함께서만"
UNLISTED_ONLY = " — --unlisted는 전이표에 없는 짝만 넘긴다"


class Unlisted(str):
    """check_transition이 전이표에 없는 짝에 돌려주는 거부 이유. --unlisted는 이 이유만 넘긴다."""


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# 판정 기준 뒤의 절 가운데 스크립트가 끼워 넣는 셋(정정·재시도·표 밖 전이)을 뺀 것(등록표 TASK_SECTIONS의 순서)
_SECTION_ORDER = [name for name, _ in kinds.TASK_SECTIONS]
AFTER_CRITERIA = [name for name in _SECTION_ORDER[_SECTION_ORDER.index("판정 기준") + 1:]
                  if name not in ("판정 기준 정정", "재시도 범위", "표 밖 전이")]


# ---------------------------------------------------------------- 전이 검사

def title_parked(t):
    return str(t.get("title", "")).lstrip().startswith(("[백로그]", "[안"))


def check_transition(run_dir, t, old, new, ctx):
    """허용이면 None, 전이표에 없는 짝이면 Unlisted, 아니면 거부 이유(str)."""
    kind = t.get("kind", "")
    rec, point = ctx["record"] is not None, (ctx["record"] or ("", "", ""))[0]
    reason = ctx["reason"]

    def judges():
        ok, why = devflow_lib.judges_present(t)
        return None if ok else "필요한 판정이 없음: " + why

    def stage_end():
        if kind == "deploy-exec" and devflow_lib.stage_of(t) != "끝":
            return "배포 실행은 stage: 끝이 된 뒤에 완료(references/kinds/deploy-exec.md 「단계와 기록」)"
        return None

    if old == new:
        return None
    if kind in kinds.STAGE_KINDS and devflow_lib.rules_level(t) >= 2 and new != "보류":
        why = stage_rule(run_dir, t, old, new, ctx)
        if why:
            return why
    if new == "보류":
        return None if (rec or reason) else "보류는 --record(사용자 답) 또는 --reason(메인 판단)과 함께"
    pair = (old, new)
    if pair == ("대기", "진행"):
        # 판본을 비교하지 않고 task를 띄우지 못하게(하네스가 바뀐 뒤 journal·run.md 갱신 없이 한 task를 띄움)
        now_v, rec_v = devflow_lib.harness_version(), devflow_lib.run_meta(run_dir).get("harness_version", "")
        if rec_v and not devflow_lib.same_version(now_v, rec_v):
            return "run.md 하네스 판본({})이 지금 판본({})과 다름 — SKILL.md 1절 「하네스가 바뀌었을 때」대로 journal에 적고 run.md 판본을 먼저 고친다".format(rec_v, now_v)
        defs = devflow_lib.agent_def_problems()
        if defs:
            return "판정자 정의 설치 불일치: {} — 두 판정자 정의와 DEF_VERSION_MIN을 함께 설치한 뒤 시작한다".format("; ".join(defs))
        return None
    if pair == ("진행", "자체검증"):
        return None
    if pair == ("자체검증", "진행"):
        return None if ctx["archived"] else "자체검증→진행(재시도)은 --archive-judge와 함께"
    if pair == ("자체검증", "승인대기"):
        return judges()
    if pair == ("자체검증", "완료"):
        if not rec or point not in ("알림", "승인"):
            return "자체검증→완료는 --record \"알림|…\"(또는 승인)와 함께"
        if kind not in kinds.NOTIFY_KINDS and kind not in kinds.STAGE_KINDS and not devflow_lib.prior_approval(t):
            return "{}는 알림으로 지나가지 않는다(승인대기로)".format(kind)
        why = judges() or stage_end()
        if why:
            return why
        if devflow_lib.is_new_task(t) and kind in kinds.NOTIFY_KINDS and kind not in kinds.STAGE_KINDS and not devflow_lib.prior_approval(t):
            import screen
            ok, msg = screen.notify_status(run_dir, t["id"])
            if not ok:
                return "알림 불가: " + msg
        return None
    if pair == ("승인대기", "완료"):
        if not rec:
            return "승인대기→완료는 --record(사용자 답)와 함께"
        return judges() or stage_end()
    if pair == ("승인대기", "진행"):
        return None if (rec or ctx["snapshot"]) else "승인대기→진행은 --record(사람 답) 또는 --screen-snapshot과 함께"
    if pair == ("진행", "승인대기"):
        return None if kind in kinds.STAGE_KINDS else "진행→승인대기는 합치기·마무리·배포 실행만(그 밖은 자체검증을 거침)"
    if pair == ("진행", "완료"):
        if kind not in kinds.STAGE_KINDS:
            return "진행→완료는 합치기·마무리·배포 실행만"
        if not rec:
            return "진행→완료는 --record와 함께"
        return judges() or stage_end()
    if pair in (("보류", "대기"), ("보류", "백로그")):
        return None if rec else "보류에서 나가는 전이는 --record(사용자 답)와 함께"
    if pair == ("대기", "백로그"):
        return None if (title_parked(t) or rec or reason) else "대기→백로그는 [백로그] 행이거나 --record·--reason과 함께"
    if pair == ("백로그", "완료"):
        return None if (rec or reason) else "백로그→완료는 --record 또는 --reason \"다른 실행·회고에서 처리: {경로}\""
    return Unlisted("전이표에 없는 전이 {}→{}(--unlisted \"이유\"로만)".format(old, new))


def stage_rule(run_dir, t, old, new, ctx):
    """rules 2 이상의 합치기·마무리·배포 실행: 상태와 stage가 맞는가. 맞으면 None."""
    kind, st, st_old = t.get("kind", ""), devflow_lib.stage_of(t), ctx.get("old_stage", "")
    if new == "승인대기" and st not in kinds.ASK_STAGES:
        return "{}의 승인대기는 묻는 단계와 함께(stage={})".format(kind, "/".join(sorted(kinds.ASK_STAGES)))
    if old == "승인대기" and new == "진행" and not ctx["snapshot"] and (st in kinds.ASK_STAGES or st == "끝"):
        return "승인대기→진행은 다음 실행 단계와 함께(stage={} 가운데 묻는 단계가 아닌 것)".format("/".join(kinds.stages_of(kind)))
    if new != kinds.DONE:
        return None
    if st != "끝":
        return "{}는 stage: 끝이 된 뒤에 완료".format(kind)
    import exec as execmod
    ok, lines = execmod.verify(run_dir, t)
    answered = old == "승인대기" and st_old == "결과승인" and ctx["record"] is not None
    if kind == "merge" and os.path.isfile(os.path.join(t["_dir"], "approved-cmds-결과승인.md")):
        # 결과승인 지점은 그 승인 답이 있어야 얼린다. 끝내기 명령을 돌린 뒤의 완료는 그 답으로 받는다
        answered = True
    if kind == "merge":
        if not ok:
            return "exec.py --verify 실패({}) — stage=결과승인으로 승인을 받는다".format("; ".join(lines))
        proof = final_candidate_ci_problem(run_dir, t)
        if proof:
            return proof
        failed = merge_failed(run_dir, t)
        if failed and not answered:
            # 결과승인에서 사람이 답했으면(위험을 받아들임 = 승인, SKILL.md 2절 「실패 처리」) 실패 수는 보지 않는다
            return "실행 판정에 통과 못 한 기준 {}개 — stage=결과승인으로 승인을 받는다".format(failed)
    if kind == "wrap-up":
        if not answered:
            return "마무리는 결과승인(승인대기)에서 --record와 함께 완료"
        if not ok:
            return "exec.py --verify 실패({})".format("; ".join(lines))
        proof = final_candidate_ci_problem(run_dir, t, always=True, expected_commit=t.get("exported_commit", ""))
        if proof:
            return proof
    if kind == "deploy-exec" and str(t.get("deploy_outcome", "")).strip() == "유지" and not ok \
            and any(n.startswith("approved-cmds-") for n in os.listdir(t["_dir"])):
        return "exec.py --verify 실패({})".format("; ".join(lines))
    if kind == "deploy-exec" and str(t.get("deploy_outcome", "")).strip() == "유지":
        proof = deploy_target_problem(run_dir, t)
        if proof:
            return proof
    return None


def final_merge_candidate(run_dir, t):
    """이번 회차의 다른 기능·수정 흐름이 모두 합쳐졌으면 현재 merge가 최종 배포 후보를 만든다."""
    current, rnd = str(t.get("flow", "") or ""), devflow_lib.run_round(run_dir)
    flows = []
    for path in glob.glob(os.path.join(run_dir, "flows", "*", "flow.md")):
        meta_lines, _ = devflow_lib.split_front_matter(devflow_lib.read_text(path))
        meta = devflow_lib.parse_meta(meta_lines)
        name = str(meta.get("flow", "") or os.path.basename(os.path.dirname(path)))
        if devflow_lib.as_round(meta.get("round", "")) != rnd or devflow_lib.flow_role(name, meta) not in ("feature", "fixes"):
            continue
        if str(meta.get("status", "")) == "폴더 없음":
            continue
        flows.append((name, str(meta.get("status", ""))))
    return len(flows) >= 2 and any(name == current for name, _ in flows) \
        and all(name == current or status in ("합쳐짐", "폴더 지움") for name, status in flows)


GIT_SHA = re.compile(r"^[0-9a-fA-F]{7,40}$")


def same_git_commit(a, b):
    a, b = str(a or "").strip(), str(b or "").strip()
    return bool(GIT_SHA.fullmatch(a) and GIT_SHA.fullmatch(b) and (a.startswith(b) or b.startswith(a)))


def final_candidate_ci_problem(run_dir, t, always=False, expected_commit=None):
    if not devflow_lib.uses_isolation_contract(t) or (not always and not final_merge_candidate(run_dir, t)):
        return None
    path = os.path.join(t["_dir"], "judge-run.md")
    sec = devflow_lib.sections(devflow_lib.read_text(path), level=2) if os.path.isfile(path) else {}
    text = sec.get("최종 배포 후보 CI")
    if text is None:
        return "최종 배포 후보 CI 근거 없음: judge-run.md 「최종 배포 후보 CI」"
    values = {}
    for line in text.splitlines():
        m = re.match(r"^-\s*(범위|검증 commit|검증 artifact)\s*:\s*(.+?)\s*$", line.strip())
        if m:
            values[m.group(1)] = m.group(2)
    missing = [k for k in ("범위", "검증 commit", "검증 artifact") if not values.get(k) or values.get(k) in ("없음", "(없음)")]
    if missing:
        return "최종 배포 후보 CI 필수 값 없음: {}".format(", ".join(missing))
    if values["범위"] != "전체 검증":
        return "최종 배포 후보 CI 범위가 전체 검증이 아님({})".format(values["범위"])
    commit = str(t.get("commit", "") if expected_commit is None else expected_commit or "").strip()
    checked = values["검증 commit"].strip()
    if not GIT_SHA.fullmatch(checked):
        return "최종 배포 후보 CI 검증 commit이 유효한 Git SHA가 아님({})".format(checked)
    if not GIT_SHA.fullmatch(commit):
        return "최종 배포 후보 commit이 유효한 Git SHA가 아님({})".format(commit or "없음")
    if not same_git_commit(checked, commit):
        return "최종 배포 후보 CI 검증 commit({})이 후보 commit({})과 다름".format(checked, commit)
    return None


def ci_proof_values(t):
    path = os.path.join(t["_dir"], "judge-run.md")
    sec = devflow_lib.sections(devflow_lib.read_text(path), level=2) if os.path.isfile(path) else {}
    text = sec.get("최종 배포 후보 CI", "")
    values = {}
    for line in text.splitlines():
        m = re.match(r"^-\s*(범위|검증 commit|검증 artifact)\s*:\s*(.+?)\s*$", line.strip())
        if m:
            values[m.group(1)] = m.group(2)
    return values


def canonical_final_ci(run_dir):
    """현재 실행의 권위 있는 최종 후보: 완료된 1.0.1 wrap-up 가운데 가장 늦게 승인된 것."""
    wraps = [o for o in devflow_lib.load_tasks(run_dir).values()
             if o.get("kind") == "wrap-up" and o.get("status") == kinds.DONE
             and devflow_lib.uses_isolation_contract(o)]
    if not wraps:
        return None, "완료된 1.0.1 wrap-up 최종 CI가 없음"
    wraps.sort(key=lambda o: (str(o.get("approved", "")), str(o.get("id", ""))))
    authority = wraps[-1]
    values = ci_proof_values(authority)
    missing = [k for k in ("범위", "검증 commit", "검증 artifact") if not values.get(k)]
    if missing:
        return None, "{}의 최종 CI 필수 값 없음: {}".format(authority.get("id"), ", ".join(missing))
    return values, ""


def deploy_target_problem(run_dir, t):
    """1.0.1 배포 유지 전에는 검증 대상과 실제 배포 대상의 commit·artifact가 각각 같아야 한다."""
    if not devflow_lib.uses_isolation_contract(t):
        return None
    canonical, why = canonical_final_ci(run_dir)
    if canonical is None:
        return "배포할 권위 있는 최종 CI 근거 없음: " + why
    path = os.path.join(t["_dir"], "judge-run.md")
    sec = devflow_lib.sections(devflow_lib.read_text(path), level=2) if os.path.isfile(path) else {}
    text = sec.get("배포 대상 동일성")
    if text is None:
        return "배포 대상 동일성 근거 없음: judge-run.md 「배포 대상 동일성」"
    keys = ("검증 commit", "검증 artifact", "배포 commit", "배포 artifact")
    values = {}
    for line in text.splitlines():
        m = re.match(r"^-\s*({})\s*:\s*(.+?)\s*$".format("|".join(keys)), line.strip())
        if m:
            values[m.group(1)] = m.group(2)
    missing = [k for k in keys if not values.get(k) or values.get(k) in ("없음", "(없음)")]
    if missing:
        return "배포 대상 동일성 필수 값 없음: {}".format(", ".join(missing))
    for key in ("검증 commit", "배포 commit"):
        if not GIT_SHA.fullmatch(values[key]):
            return "배포 대상 동일성 {}이 유효한 Git SHA가 아님({})".format(key, values[key])
    if not same_git_commit(values["검증 commit"], values["배포 commit"]):
        return "배포 commit이 검증 commit과 다름({} != {})".format(values["배포 commit"], values["검증 commit"])
    if values["검증 artifact"] != values["배포 artifact"]:
        return "배포 artifact가 검증 artifact와 다름({} != {})".format(values["배포 artifact"], values["검증 artifact"])
    if not same_git_commit(canonical["검증 commit"], values["검증 commit"]):
        return "배포 검증 commit이 최종 CI commit과 다름({} != {})".format(values["검증 commit"], canonical["검증 commit"])
    if canonical["검증 artifact"] != values["검증 artifact"]:
        return "배포 검증 artifact가 최종 CI artifact와 다름({} != {})".format(
            values["검증 artifact"], canonical["검증 artifact"])
    deployed = str(t.get("deployed_commit", "") or "").strip()
    if deployed and not same_git_commit(deployed, values["배포 commit"]):
        return "배포 commit 근거({})가 deployed_commit({})과 다름".format(values["배포 commit"], deployed)
    return None


def merge_failed(run_dir, t):
    """합치기의 실행 판정 「통과 못 한 기준」 수(main-run.md로 푼 판정불가·`대상:` 판정불가는 뺀다)."""
    import screen
    b = screen.build(run_dir, t["id"])
    if "error" not in b:
        return devflow_lib.item_count(b["failed"])
    p = os.path.join(t["_dir"], "judge-run.md")
    if not os.path.isfile(p):
        return 0
    return devflow_lib.item_count(devflow_lib.sections(devflow_lib.read_text(p), level=2).get("통과 못 한 기준", ""))


def auto_freeze(run_dir, t, old, new, rec, old_stage):
    """승인 기록과 함께 묻는 단계를 떠날 때, 배포 실행이 시작될 때 exec.py --freeze. 실패는 알리기만 한다."""
    if devflow_lib.rules_level(t) < 2 and not (old == "대기" and new == "진행"):
        return
    import exec as execmod
    kind = t.get("kind", "")
    points = []
    if kind == "deploy-exec" and old == "대기" and new == "진행":
        points = ["실행승인", "되돌림"]
    elif rec is not None and old == "승인대기" and kind in kinds.STAGE_KINDS and new == "진행":
        # 실행 단계로 갈 때만 얼린다. 결과승인·넣기승인에서 곧바로 완료(받아들임·넣지 않음)면 돌 명령이 없다
        if old_stage in {"merge": ("실행승인", "결과승인"), "wrap-up": ("실행승인",),
                         "deploy-exec": ("넣기승인",)}.get(kind, ()):
            points = [old_stage]
    elif rec is not None and old == "승인대기" and kind not in kinds.STAGE_KINDS and new == kinds.DONE \
            and devflow_lib.cmd_lines(devflow_lib.decide_cell(t["_dir"])):
        points = ["실행승인"]
    for p in points:
        rc, msg = execmod.freeze(run_dir, t["id"], p)
        if p == "되돌림" and rc == 3 and "울타리가 없다" in msg:
            continue
        print("exec.py --freeze --point {}: {}".format(p, msg))


# ---------------------------------------------------------------- 하위 작업

def journal(run_dir, kind, tid, line):
    p = os.path.join(run_dir, "journal.md")
    eol = "\n"
    if os.path.isfile(p):
        with open(p, "rb") as f:
            eol = "\r\n" if b"\r\n" in f.read() else "\n"   # 그 journal의 줄 끝 꼴을 따른다
    with open(p, "a", encoding="utf-8", newline="") as f:
        f.write("- {} | {} | {} | {}{}".format(now_str()[:16], kind, tid, line, eol))


def parse_record(raw):
    parts = [p.strip() for p in raw.split("|", 2)]
    while len(parts) < 3:
        parts.append("")
    return tuple(parts)


def record_line(rec):
    point, decision, text = rec
    if point == "알림" and not text:
        quoted = "(알림, 답 없음)"
    else:
        quoted = '"{}"'.format(text.replace('"', "'"))
    return "- {} | {} | {} | 원문: {}".format(now_str(), point, decision, quoted)


FAIL_NO = re.compile(r"기준\s*(\d+)")
LEAD_NO = re.compile(r"^-\s*(\d+)[.)\s]")


def failed_numbers(paths):
    nums, loose = set(), []
    for p in paths:
        if not os.path.isfile(p):
            continue
        text = devflow_lib.sections(devflow_lib.read_text(p), level=2).get("통과 못 한 기준", "")
        for line in text.splitlines():
            s = line.strip()
            if not s.startswith("- ") or devflow_lib.EMPTY_ITEM.match(s):
                continue
            found = FAIL_NO.findall(s) or LEAD_NO.findall(s)
            if found:
                nums.update(int(x) for x in found)
            else:
                loose.append(s[2:][:120])
    return sorted(nums), loose


def archive_check(run_dir, t):
    """보관할 수 있는지만 본다(파일을 바꾸지 않는다). (retry, 보관할 파일 목록)."""
    d = t["_dir"]
    cap = devflow_lib.run_value(run_dir, "자체 검증 재시도", kinds.RUN_DEFAULTS["자체 검증 재시도"])
    retry = int(str(t.get("retry", "0") or "0").strip() or 0)
    if retry >= cap:
        raise Reject("재시도 상한 {}: 다시 띄우지 않고 통과 못 한 채 승인으로 올린다(SKILL.md 2절 「실패 처리」)".format(cap))
    progress = devflow_lib.judge_run_contract_problems(t)
    if progress:
        raise Reject("판정 미완료라 재시도를 보관하지 않음: " + "; ".join(progress))
    present = [n for n in ("judge.md", "judge-run.md") if os.path.isfile(os.path.join(d, n))]
    if not present:
        raise Reject("보관할 판정 파일(judge.md·judge-run.md)이 없음")
    return retry, present


def archive_judge(run_dir, t, doc):
    d = t["_dir"]
    retry, present = archive_check(run_dir, t)
    n = retry + 1
    while any(os.path.exists(os.path.join(d, x)) for x in ("judge.r{}.md".format(n), "judge-run.r{}.md".format(n))):
        n += 1
    moved = []
    for name in present:
        dst = name.replace(".md", ".r{}.md".format(n))
        os.replace(os.path.join(d, name), os.path.join(d, dst))
        moved.append(dst)
    snap = make_snapshot(run_dir, t, n)   # 판정 파일을 옮긴 뒤, 「재시도 범위」를 쓰기 전
    nums, loose = failed_numbers([os.path.join(d, m) for m in moved])
    lines = ["- 회차 {} (보관한 판정: {}): 고칠 기준: {}. 그 기준 안에서는 판정자가 적지 않은 같은 종류의 결함도 고친다. 다른 기준과 판정자의 권장은 고치지 않는다. 판정자의 대안 문장은 그대로 옮기지 않고, 그 근거 줄과 원천을 열어 확인한 뒤 쓴다(어긋나면 원천을 따르고 「알릴 것」에 적는다).".format(
        retry + 1, ", ".join(moved), ", ".join(str(x) for x in nums) if nums else "(번호 없음 — 아래 항목)")]
    lines += ["  - 번호 없는 항목: " + x for x in loose]
    doc.set_section("재시도 범위", "\n".join(lines), before=AFTER_CRITERIA)
    doc.set("retry", str(retry + 1))
    return moved, snap


# 수정 전 사본 한 회차의 상한(files\ + code.patch). 넘으면 큰 파일부터 빼고, 그래도 넘으면 code.patch를 뺀다
SNAPSHOT_MAX_BYTES = 1_048_576


def make_snapshot(run_dir, t, n):
    """tasks\\{id}\\before.r{n}\\에 수정 전 사본을 뜨고 화면 줄을 돌려준다.
    실패해도 예외를 내지 않는다(보관을 막지 않는다). 코드 폴더는 임시 색인·임시 객체 폴더로만 읽는다."""
    tid = t.get("id", "")
    shown = "tasks\\{}\\before.r{}".format(tid, n)
    out_dir = os.path.join(t["_dir"], "before.r{}".format(n))
    if os.path.exists(out_dir):
        return ["! 사본: {}이 이미 있어 새로 뜨지 않음(보관은 그대로)".format(shown)]
    try:
        return _write_snapshot(run_dir, t, n, out_dir, shown)
    except (OSError, ValueError, retry_diff.GitError) as e:
        return ["! 사본 만들지 못함: {} — 보관은 그대로(재시도를 막지 않는다)".format(e)]


def _write_snapshot(run_dir, t, n, out_dir, shown):
    rels, missing = retry_diff.snapshot_sources(run_dir, t)
    datas = []
    for rel in rels:
        with open(os.path.join(run_dir, rel), "rb") as f:
            datas.append((rel, f.read()))
    extra, patch, code_lines = [], None, []
    if t.get("kind") in kinds.CODE_DIR_KINDS:
        folder = code_dir(run_dir, t)
        if not folder:
            code_lines = ["- 사본 없음: 코드 폴더를 찾지 못함(flows\\{}\\flow.md dir)".format(t.get("flow", ""))]
        else:
            try:
                with retry_diff.TempGit(folder) as g:
                    head = g.head()
                    g.now_tree()
                    patch, changed = g.patch(head)
                    status = g.status() if len(patch) > SNAPSHOT_MAX_BYTES else []
            except retry_diff.GitError as e:
                code_lines = ["- 사본 없음: {}".format(e)]
    else:
        code_lines = ["- 없음(코드 폴더에 쓰지 않는 kind)"]
    if code_lines and code_lines[0].startswith("- 사본 없음"):
        extra.append("! 사본: 코드 " + code_lines[0][2:] + " — 보관은 그대로")
    # 상한: 큰 파일부터 빼고(같은 크기면 경로 순), 그래도 넘으면 code.patch를 뺀다
    kept = dict(datas)
    total = sum(len(b) for b in kept.values()) + (len(patch) if patch is not None else 0)
    capped = []
    for rel, data in sorted(datas, key=lambda x: (-len(x[1]), x[0])):
        if total <= SNAPSHOT_MAX_BYTES:
            break
        del kept[rel]
        capped.append(rel)
        total -= len(data)
    patch_capped = patch is not None and total > SNAPSHOT_MAX_BYTES
    if patch is not None:
        if patch_capped:
            code_lines = ["- 폴더: {} | HEAD: {} | patch: {} {} | 바뀐 파일 {}".format(
                folder, head or "(커밋 없음)", retry_diff.CAPPED, len(patch), changed)]
            code_lines += ["- 바뀐 파일: " + x for x in status]
        else:
            code_lines = ["- 폴더: {} | HEAD: {} | patch: {} {} | 바뀐 파일 {}".format(
                folder, head or "(커밋 없음)", retry_diff.PATCH, len(patch), changed)]
    # 쓰기: 파일, patch, 끝으로 MANIFEST.md(MANIFEST.md가 있으면 사본이 다 쓰인 것)
    file_lines = []
    for rel, data in datas:
        if rel in kept:
            dst = os.path.join(out_dir, retry_diff.FILES_DIR, *rel.split("/"))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, "wb") as f:
                f.write(data)
            file_lines.append("- {} | {} | {}".format(rel, len(data), retry_diff.sha16(data)))
        else:
            file_lines.append("- {} | {} | {}".format(rel, retry_diff.CAPPED, len(data)))
    file_lines += ["- {} | {}".format(p, retry_diff.NO_MATCH) for p in missing]
    os.makedirs(out_dir, exist_ok=True)
    if patch is not None and not patch_capped:
        with open(os.path.join(out_dir, retry_diff.PATCH), "wb") as f:
            f.write(patch)
    d = t["_dir"]
    judged = [x.format(n) for x in ("judge.r{}.md", "judge-run.r{}.md") if os.path.isfile(os.path.join(d, x.format(n)))]
    when = None
    for name in judged:
        when = devflow_lib.judge_header(os.path.join(d, name))[1]
        if when is not None:
            break
    head_lines = ["# {} 재시도 {} 수정 전 사본".format(t.get("id", ""), n),
                  "- 시각: " + now_str(),
                  "- 보관한 판정: " + ", ".join(judged),
                  "- 앞 판정 시각: " + (datetime.fromtimestamp(when).strftime("%Y-%m-%d %H:%M:%S") if when else "(읽지 못함)"),
                  "- kind: " + str(t.get("kind", "")),
                  "## 파일"] + (file_lines or ["- 없음"]) + ["## 코드"] + code_lines
    devflow_lib.write_text(os.path.join(out_dir, retry_diff.MANIFEST), "\n".join(head_lines) + "\n")
    kept_bytes = sum(len(kept[r]) for r in kept)
    tail = ", patch {}".format(len(patch)) if patch is not None and not patch_capped else ""
    left = len(capped) + (1 if patch_capped else 0)
    tail += ", 빠진 것 {}".format(left) if left else ""
    return ["사본: {} (파일 {}, {}바이트{})".format(shown, len(kept), kept_bytes, tail)] + extra


def amend_check(t, path, source, tasks):
    """판정 기준 정정을 받을 수 있는지만 본다(파일을 바꾸지 않는다)."""
    if t.get("status") not in ("대기", "진행"):
        raise Reject("판정 기준 정정은 판정자가 뜨기 전(대기·진행)에만")
    src = (source or "").strip()
    if not src.startswith(("작성자 ", "판정자 ", "사용자 답 ")):
        raise Reject("출처는 `작성자 {이상 신호 위치}` / `판정자 {대안 문장 위치}` / `사용자 답 {task id} {승인 기록 시각}`")
    if src.startswith("사용자 답 "):
        parts = src.split()
        if len(parts) < 4 or parts[2] not in tasks:
            raise Reject("사용자 답 출처는 `사용자 답 {task id} {YYYY-MM-DD HH:MM}`")
        stamp = " ".join(parts[3:5])
        rows = [l for l in devflow_lib.record_lines(tasks[parts[2]]) if l[2:].startswith(stamp)]
        if not any(re.search(r'"[^"]+"', l) for l in rows):   # 원문(따옴표 안의 사용자 말)이 있는 줄
            raise Reject("{}의 승인 기록에 {} 원문 줄이 없음".format(parts[2], stamp))
    if not os.path.isfile(path) or not devflow_lib.read_text(path).strip():
        raise Reject("고친 문장 파일이 없거나 비었음: " + str(path))


def amend_criteria(run_dir, t, doc, path, source, tasks):
    src = source.strip()
    new_text = devflow_lib.read_text(path).strip()
    d = t["_dir"]
    orig, amends = devflow_lib.criteria_files(d)
    if not os.path.isfile(orig):
        devflow_lib.write_text(orig, (doc.section("판정 기준") or "(없음)") + "\n")
    n = len(amends) + 1
    prev = os.path.basename(amends[-1]) if amends else "criteria.orig.md"
    devflow_lib.write_text(os.path.join(d, "criteria.amend{}.md".format(n)), new_text + "\n")
    doc.set_section("판정 기준", new_text)
    doc.append_line("판정 기준 정정", "- {} | 정정 {} | 출처: {} | 원문: {} | 고친 문장: criteria.amend{}.md".format(
        now_str(), n, src, prev, n), before=AFTER_CRITERIA)
    doc.set("criteria_amended", now_str())


def code_dir(run_dir, t):
    flow = t.get("flow", "")
    p = os.path.join(run_dir, "flows", flow, "flow.md")
    if not flow or not os.path.isfile(p):
        return None
    meta_lines, _ = devflow_lib.split_front_matter(devflow_lib.read_text(p))
    d = devflow_lib.parse_meta(meta_lines).get("dir", "")
    return d if d and os.path.isdir(d) else None


def touch_path_warnings(run_dir, t, text=None):
    """「건드릴 파일」 경로를 기준 폴더에서 확인해 경고 줄을 돌려준다(거부하지 않음).
    기준 폴더: 등록표 `writes_code_dir` kind는 흐름의 코드 폴더, 그 밖은 실행 폴더. 코드 폴더를 못 찾으면 그 한 줄만.
    text가 없으면 t의 머리 파일에서 「건드릴 파일」 절을 읽고, 있으면 그 글(`--add`가 더한 줄)만 본다."""
    if text is None:
        text = devflow_lib.Doc(t["_path"]).section("건드릴 파일") or ""
    paths = devflow_lib.touch_paths(text)
    if not paths:
        return []
    if t.get("kind") in kinds.CODE_DIR_KINDS:
        base = code_dir(run_dir, t)
        if not base:
            return ["! 건드릴 파일: 코드 폴더를 찾지 못해 경로를 확인하지 않음(flows\\{}\\flow.md dir)".format(t.get("flow", ""))]
    else:
        base = run_dir
    out = []
    for path in paths:
        full = os.path.join(base, path.replace("\\", "/"))
        if base == run_dir:
            rel = retry_diff.run_rel(run_dir, path)
            if rel:
                full = os.path.join(run_dir, rel)
        if re.search(r"[*?\[]", path):
            if not glob.glob(full, recursive=True):
                out.append("! 건드릴 파일: {} — 맞는 파일 없음".format(path))
        elif not os.path.exists(full):
            out.append("! 건드릴 파일: {} — 없는 경로(새 파일이면 그대로)".format(path))
    return out


def run_machine_check(run_dir, t):
    folder = code_dir(run_dir, t)
    if not folder:
        print("machine_check: 코드 폴더를 찾지 못함(flows\\{}\\flow.md dir) — 메인이 따로 돌린다".format(t.get("flow", "")))
        return None
    here = os.path.dirname(os.path.abspath(__file__))
    out = subprocess.run([sys.executable, os.path.join(here, "machine_check.py"), folder, t["_path"]],
                         capture_output=True, text=True, encoding="utf-8")
    print(out.stdout.rstrip())
    return str(out.returncode)


# ---------------------------------------------------------------- 명령

def answer_time(t):
    """사용자 원문(따옴표 안의 말)이 있는 답 줄의 시각. 지점이 `답`인 줄을 먼저 보고(가장 늦은 것), 없으면 원문이 있는
    다른 줄(승인 줄, 칸 없는 옛 꼴)을 본다. 알림·점검 확인·되물음 줄은 세지 않는다."""
    answer, other = "", ""
    for line in devflow_lib.record_lines(t):
        f = devflow_lib.record_fields(line)
        if len(f) >= 2 and (f[1] in ("알림", "점검 확인") or f[1].startswith("되물음")):
            continue
        if not re.search(r'"[^"]+"', line):
            continue
        m = re.match(r"-\s*(\d{4}-\d{2}-\d{2} \d{2}:\d{2}(?::\d{2})?)", line)
        stamp = m.group(1) if m else (f[0] if len(f) >= 2 else "")
        if len(f) >= 2 and f[1] == "답":
            answer = stamp
        elif stamp:
            other = stamp
    return answer or other


# `사용자 …`로 시작하지 않으면서 task의 답을 가리키는 origin(알림 불가가 꺼진다). `사용자 …`로 시작하면 알림 불가가 걸려 받는다
USER_ORIGIN_HINT = re.compile(r"T\d+\s*(?:의\s*)?(?:사용자\s*)?답")


def cmd_new(run_dir, args, kv):
    import spawn_children

    def opt(name, default=""):
        return args[args.index(name) + 1] if name in args else default
    kind, title, body_from = opt("--kind"), opt("--title"), opt("--body-from")
    answer = opt("--from-answer")
    owned = sorted({k for k, _ in kv} & (kinds.SCRIPT_KEYS | {"kind", "id", "status", "title"}))
    if owned:
        # 키=값이 --from-answer가 정한 origin·kind를 덮으면 알림 불가·세대가 꺼진다
        print("거부: {}는 new의 키=값으로 받지 않는다(--kind·--title·--origin·--from-answer를 쓴다)".format(", ".join(owned)))
        return 3
    if not (kind or answer) or not title or not body_from:
        print("new에는 --kind(또는 --from-answer), --title, --body-from이 필요")
        return 2
    if kind and kind not in kinds.KINDS:
        print("모르는 kind: " + kind)
        return 3
    tasks = devflow_lib.load_tasks(run_dir)
    body = devflow_lib.sections(devflow_lib.read_text(body_from), level=2)
    if not body.get("범위") or not body.get("판정 기준"):
        print("--body-from 파일에 「범위」와 「판정 기준」 절이 있어야 함")
        return 3
    outside = devflow_lib.outside_canon(devflow_lib.touch_paths(body.get("건드릴 파일", "")), run_dir)
    origin = opt("--origin")
    if not answer and kind in kinds.AUTO_DEPEND_KINDS | {"change"} and USER_ORIGIN_HINT.search(origin or "") \
            and not devflow_lib.user_origin({"origin": origin}):
        print("거부: origin이 사용자 답을 가리킨다('{}') — `--from-answer {{답을 받은 task id}}`로 만든다(SKILL.md 3절)".format(origin))
        return 3
    if answer:
        # 사용자 답을 계기로 만드는 task: origin과 kind를 스크립트가 정한다. 코드를 고치면 fix, 정본만이면 change
        if answer not in tasks:
            print("답을 받은 task를 찾지 못함: " + answer)
            return 3
        stamp = answer_time(tasks[answer])
        if not stamp:
            print("{}의 승인 기록에 사용자 원문(따옴표) 줄이 없음 — 답을 --record로 먼저 적는다".format(answer))
            return 3
        if not devflow_lib.touch_paths(body.get("건드릴 파일", "")):
            print("--from-answer에는 「건드릴 파일」이 있어야 kind를 정한다(정본만 고치면 spec/·design/ 경로)")
            return 3
        bad = devflow_lib.touch_format_problems(body.get("건드릴 파일", ""))
        if bad:
            print("거부: 「건드릴 파일」은 한 줄에 한 경로를 `- `로(kind를 정하려고): {}".format(" / ".join(bad)))
            return 3
        decided = "fix" if outside else "change"
        if kind and kind != decided:
            print("거부: --from-answer의 kind는 「건드릴 파일」로 정한다({}: 정본 밖 경로 {}). --kind {}를 빼거나 파일을 고친다".format(
                decided, ", ".join(outside) or "없음", kind))
            return 3
        kind = decided
        origin = "사용자 {} {}".format(answer, stamp) + (" — " + origin if origin else "")
    if kind == "change" and devflow_lib.touch_format_problems(body.get("건드릴 파일", "")):
        print("거부: change의 「건드릴 파일」은 한 줄에 한 경로를 `- `로: {}".format(
            " / ".join(devflow_lib.touch_format_problems(body.get("건드릴 파일", "")))))
        return 3
    if kind == "change" and outside:
        print("거부: change의 「건드릴 파일」에 정본 밖 경로({}) — 코드를 고치는 변경은 kind: fix(SKILL.md 5절)".format(", ".join(outside)))
        return 3
    tid = "T{:03d}".format(devflow_lib.next_task_number(tasks))
    deps = [x.strip() for x in opt("--depends-on").split(",") if x.strip()]
    missing = [x for x in deps if x not in tasks]
    if missing:
        print("의존하는 task를 찾지 못함: " + ", ".join(missing))
        return 3
    if kind in kinds.AUTO_DEPEND_KINDS and devflow_lib.flow_name_problem(run_dir, opt("--flow")):
        print("거부: " + devflow_lib.flow_name_problem(run_dir, opt("--flow")))
        return 3
    child = {"title": title, "meta": {"kind": kind, "flow": opt("--flow"), "block": opt("--block")}, "body": body}
    path = os.path.join(run_dir, "tasks", tid, "task.md")
    devflow_lib.write_text(path, spawn_children.render(tid, opt("--parent"), child, deps, now_str()))
    devflow_lib.write_text(os.path.join(run_dir, "tasks", tid, "criteria.orig.md"), body["판정 기준"].strip() + "\n")
    if kind in kinds.AUTO_DEPEND_KINDS and devflow_lib.ensure_flow_md(run_dir, opt("--flow")):
        print("flow.md 만듦: flows/{}/flow.md(폴더 없음)".format(opt("--flow")))
    doc = devflow_lib.Doc(path)
    if origin:
        doc.set("origin", origin)
    for k, v in kv:
        doc.set(k, v)
    doc.save()
    for line in touch_path_warnings(run_dir, {"kind": kind, "flow": opt("--flow"), "_path": path}):
        print(line)
    print(tid)
    return 0


def cmd_check(run_dir, only):
    tasks = devflow_lib.load_tasks(run_dir)
    found = [f for f in devflow_lib.record_findings(tasks) if not only or f[0] == only]
    print("기록 점검 {}건".format(len(found)))
    for tid, code, msg, sub in found:
        print("- {} {}: {}".format(tid, code, msg))
        for s in sub:
            print("    " + s)
    return 0


def main(argv):
    devflow_lib.utf8_stdout()
    if len(argv) < 3 or argv[1] in ("-h", "--help"):
        print(__doc__)
        return 2
    run_dir = argv[1]
    args = argv[2:]
    if args[0] == "--check":
        return cmd_check(run_dir, args[1] if len(args) > 1 else "")
    flags_with_value = {"--add", "--status", "--record", "--reason", "--unlisted", "--amend-criteria", "--source", "--now",
                        "--kind", "--title", "--body-from", "--parent", "--depends-on", "--flow", "--origin", "--block",
                        "--from-answer"}
    kv, opts, i = [], {}, 1
    while i < len(args):
        a = args[i]
        if a in flags_with_value:
            if i + 1 >= len(args):
                print("값이 없는 옵션: " + a)
                return 2
            opts[a] = args[i + 1]
            i += 2
        elif a.startswith("--"):
            opts[a] = True
            i += 1
        elif "=" in a:
            k, v = a.split("=", 1)
            kv.append((k.strip(), v.strip()))
            i += 1
        else:
            print("모르는 인수: " + a)
            return 2
    if args[0] == "new":
        return cmd_new(run_dir, args, kv)

    tid = args[0]
    tasks = devflow_lib.load_tasks(run_dir)
    if tid not in tasks:
        print("task를 찾지 못함: " + tid)
        return 2
    t = tasks[tid]
    try:
        doc = devflow_lib.Doc(t["_path"])
        rec = parse_record(opts["--record"]) if "--record" in opts else None
        kv = [("stage" if k == "deploy_stage" else k, v) for k, v in kv]   # 옛 키 이름도 stage로 받는다
        ctx = {"record": rec, "reason": opts.get("--reason"), "archived": False,
               "snapshot": bool(opts.get("--screen-snapshot")), "old_stage": devflow_lib.stage_of(t)}
        old = str(t.get("status", "")).strip()
        new = opts.get("--status", old)

        owned = sorted({k for k, _ in kv} & kinds.SCRIPT_KEYS)
        if owned:
            # 스크립트가 채우는 키를 손으로 바꾸면 기록 점검·stage 강제를 끌 수 있다
            raise Reject("{}는 스크립트가 채우는 키다(키=값으로 바꾸지 않는다)".format(", ".join(owned)))
        optioned = sorted({k for k, _ in kv} & kinds.OPTION_KEYS)
        if optioned:
            # 상태·재시도·kind를 키=값으로 바꾸면 전이 검사·재시도 상한을 넘긴다
            raise Reject(OPTION_ONLY.format(", ".join(optioned)))
        selfchecked = sorted({k for k, _ in kv} & kinds.SELFCHECK_KEYS)
        if selfchecked and not (old == "진행" and opts.get("--status") == "자체검증"):
            # 이미 자체검증인 task에 주면 기계 조건 값을 덮어 읽기 판정을 건너뛴다
            raise Reject(SELFCHECK_ONLY.format(", ".join(selfchecked)))
        for k, v in kv:           # 같은 호출의 값(stage=끝, commit=…)을 전이 검사에 쓴다
            if k == "stage" and t.get("kind") in kinds.STAGE_KINDS and v and v not in kinds.stages_of(t.get("kind")):
                raise Reject("{}의 stage는 {}".format(t.get("kind"), "/".join(kinds.stages_of(t.get("kind")))))
            t[k] = devflow_lib.parse_value(k, v)
        if "--amend-criteria" in opts and opts.get("--archive-judge"):
            raise Reject("--amend-criteria와 --archive-judge는 따로 부른다")
        # 검사를 모두 마친 뒤에 파일을 바꾼다(거부되면 아무것도 바꾸지 않는다)
        why = check_transition(run_dir, t, old, new, dict(ctx, archived=bool(opts.get("--archive-judge"))))
        if why and not (opts.get("--unlisted") and isinstance(why, Unlisted)):
            raise Reject(why + UNLISTED_ONLY if opts.get("--unlisted") else why)
        # 검사를 모두 끝낸 뒤에 파일을 바꾼다(거부된 호출이 정정 파일 등을 남기지 않게)
        add_sec = add_line = None
        if "--add" in opts:
            add_sec, _, add_line = opts["--add"].partition("|")
            add_sec, add_line = add_sec.strip(), add_line.strip()
            if not add_sec or not add_line or add_sec in kinds.OWN_SECTIONS:
                raise Reject("--add는 '절|줄'이고 {}에는 쓰지 않는다(전용 옵션)".format("·".join(sorted(kinds.OWN_SECTIONS))))
        res = os.path.join(t["_dir"], "result.md")
        if opts.get("--screen-snapshot") and not os.path.isfile(res):
            raise Reject("result.md가 없음")
        if opts.get("--archive-judge"):
            archive_check(run_dir, t)
        if "--amend-criteria" in opts:
            amend_check(t, opts["--amend-criteria"], opts.get("--source") or "", tasks)
        # 여기부터 쓰기
        if "--amend-criteria" in opts:
            amend_criteria(run_dir, t, doc, opts["--amend-criteria"], opts.get("--source"), tasks)
        if opts.get("--screen-snapshot"):
            shutil.copyfile(res, os.path.join(t["_dir"], "result.pre-screen.md"))
        if add_sec:
            doc.append_line(add_sec, add_line if add_line.startswith("- ") else "- " + add_line, before=["승인 기록"])
            if add_sec == "건드릴 파일":
                for line in touch_path_warnings(run_dir, t, add_line):
                    print(line)
        if opts.get("--archive-judge"):
            moved, snap = archive_judge(run_dir, t, doc)
            print("보관: " + ", ".join(moved))
            for line in snap:
                print(line)

        stamp = now_str()
        if new != old:
            doc.set("status", new)
            if old == "대기" and new == "진행":
                if not (doc.get("started") or ""):
                    doc.set("started", stamp)
                if not (doc.get("started_version") or ""):
                    doc.set("started_version", devflow_lib.harness_version())
                    doc.set("rules", str(kinds.RULES))
                orig = os.path.join(t["_dir"], "criteria.orig.md")
                if not os.path.isfile(orig):
                    # 메인이 손으로 만든 머리 파일(받아오기 수정 등)도 시작 뒤 고친 판정 기준이 R2로 드러나게
                    devflow_lib.write_text(orig, (doc.section("판정 기준") or "(없음)") + "\n")
                if t.get("kind") in kinds.AUTO_DEPEND_KINDS and devflow_lib.ensure_flow_md(run_dir, t.get("flow", "")):
                    # [백로그]·[안 …] 행이 새 흐름을 시작하면 행을 만들 때 flow.md가 없다. 메인이 손으로 쓰지 않게
                    # 시작 때 run.md round로 만든다(메인은 폴더를 만들 때 키만 고친다)
                    print("flow.md 만듦: flows/{}/flow.md(폴더 없음, round {})".format(t.get("flow"), devflow_lib.run_round(run_dir)))
                for problem in devflow_lib.agent_def_problems():
                    print("! 에이전트 정의: {} — 이 task의 판정 뒤 전이가 거부될 수 있다(SKILL.md 0절 1)".format(problem))
            if new == "자체검증" and t.get("kind") in kinds.AUTO_DEPEND_KINDS and not any(k == "machine_check" for k, _ in kv):
                rc = run_machine_check(run_dir, t)
                if rc is not None:
                    doc.set("machine_check", rc)
            if new == "승인대기":
                doc.set("approval_requested", stamp)
            if new == kinds.DONE:
                doc.set("approved", stamp)
                if rec and rec[0] in ("알림", "승인"):
                    doc.set("approval_mode", rec[0])
                if old == "백로그":
                    doc.set("done_via", "백로그")
            if new in (kinds.DONE, "보류", "백로그"):
                doc.set("waiting_user", "")
            if opts.get("--reason"):
                journal(run_dir, "메모", tid, "{}→{}: {}".format(old, new, opts["--reason"]))
            if why and opts.get("--unlisted"):
                doc.append_line("표 밖 전이", "- {} | {}→{} | {}".format(stamp, old, new, opts["--unlisted"]),
                                before=["승인 기록"])
                journal(run_dir, "표 밖 전이", tid, "{}→{}: {} (거부 이유: {})".format(old, new, opts["--unlisted"], why))
        for k, v in kv:
            doc.set(k, v)
        for k in [x.strip() for x in str(opts.get("--now", "")).split(",") if x.strip()]:
            doc.set(k, stamp)
        if rec:
            doc.append_line("승인 기록", record_line(rec))
            if rec[0] == "점검 확인" and rec[1].split()[:1] == ["R2"]:
                # 확인한 「판정 기준」을 남긴다. 그 뒤 또 바뀌면 R2가 다시 걸린다
                devflow_lib.write_text(os.path.join(t["_dir"], "criteria.ack.md"), (doc.section("판정 기준") or "") + "\n")
        doc.save()
        if new != old:
            if old == "대기" and new == "진행":
                t["started_version"], t["rules"] = doc.get("started_version"), doc.get("rules")
            auto_freeze(run_dir, t, old, new, rec, ctx["old_stage"])
            if t.get("kind") == "wrap-up" and new == kinds.DONE and not str(t.get("exported_commit", "") or "").strip():
                import exec as execmod
                tip = execmod.target_tip(run_dir, t)
                if tip:   # 사용자가 직접 내보낸 마무리: 받는 브랜치의 끝을 적는다(배포 계획이 읽는다)
                    d2 = devflow_lib.Doc(t["_path"])
                    d2.set("exported_commit", tip)
                    d2.save()
                    print("exported_commit={}(개발 기준 브랜치의 지금 끝)".format(tip))
    except Reject as e:
        print("거부: {} — {} (머리 파일은 그대로)".format(tid, e))
        return 3
    print("{}: {}{}".format(tid, old, "→" + new if new != old else " (상태 그대로)"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
