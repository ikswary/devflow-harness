"""메인이 머리 파일(task.md)을 쓰는 유일한 길(engine 키는 그 키를 소유한 스크립트가 쓴다). 메인은 키와 값만 넘기고 시각·형식·전이 검사는 이 스크립트가 한다.

사용:
  python task_set.py {실행 폴더} {id} [키=값 …] [--status S] [--record "지점|결정|원문"] [--reason "문장"]
                     [--reuse-answer "이유"] [--message "한 메시지 전체"] [--unlisted "이유"] [--archive-judge [--undecided]] [--amend-criteria {파일} --source "출처"]
                     [--judge-start 이름,…] [--judge-clear] [--screen-snapshot] [--now 키,…]
  python task_set.py {실행 폴더} {id} --park | --unpark | --park-cancel | --park-drop --record "지점|결정|원문"
  python task_set.py {실행 폴더} new --kind K --title "제목" --body-from {파일} [--parent T] [--depends-on T,…]
                     [--flow F] [--origin "근거"] [--from-answer T] [키=값 …]
  python task_set.py {실행 폴더} {id} --card-open {곳 키}     흐름별 검증의 코드 확인 카드를 연다(머리 파일 card_open)
  python task_set.py {실행 폴더} --check [id]
  python task_set.py {실행 폴더} {id} --identity     배포 실행 결과 승인에 옮길 줄(소스 시험의 한계, 배포 대상 동일성 관문의 지금 판정과 이유)

옵션
  키=값              머리 파일 키를 그 값으로(목록은 `[a, b]`). 없던 키는 머리 끝에 더한다.
                     스크립트가 채우는 키(started_version, rules, 시각, exported_commit, origin, fix_generation 등)는 받지 않는다.
                     `{id}` 호출(기존 task)의 키=값은 status·retry·kind를 받지 않는다(전용 옵션으로만: --status,
                     --archive-judge, new --kind). machine_check는 진행→자체검증 전이(--status 자체검증)와 함께 준 `{id}` 호출에서만 받는다.
                     new는 kind·status·id·title과 스크립트가 채우는 키를 받지 않는다. 거부는 종료 코드 3(파일 그대로).
                     1.2.0부터 시작한 코드 task의 값이 있는 commit은 비우지 못한다.
  --status S         상태 전이. 아래 전이표로 검사하고 어긋나면 종료 코드 3과 이유(파일은 그대로).
                     대기→진행: started·started_version(지금 하네스 판본)·rules(규칙 판, kinds.RULES)를 채운다.
                       배포 계획이면 deploy_reuse.py가 항목마다 재사용을 가른다.
                       배포 실행이면 exec.py로 부모 계획의 명령(실행승인)과 되돌리기(되돌림)를 얼린다.
                     진행→자체검증(implementation·fix): machine_check.py를 돌려 종료 코드를 `machine_check`에
                       (코드 폴더는 flows\\{flow}\\flow.md `dir`. `machine_check=값`을 함께 주면 돌리지 않는다).
                     →승인대기: approval_requested. →완료: approved, (--record의 지점으로) approval_mode.
                     →완료·보류·백로그: waiting_user를 비운다.
                     묻는 단계(stage 실행승인·결과승인·넣기승인)를 --record로 떠나면 exec.py --freeze를 함께 부른다.
                     「정해 주실 것」에 ```cmd 울타리가 있는 다른 task는 승인으로 닫을 때 실행승인을 얼린다.
  stage=값           합치기·마무리·배포 실행·탐침의 단계(formats.md 3절). deploy_stage=값도 stage로 받는다.
                     탐침에 stage=기록을 주면 judge.md(계획 판정)를 judge.plan.md로 옮긴다(이미 있으면 거부).
  --record "지점|결정|원문"  「승인 기록」에 `- {시각} | 지점 | 결정 | 원문: "…"`. 지점이 `알림`이고 원문이 비면
                     `원문: (알림, 답 없음)`. `점검 확인|{코드}|원문`은 그 기록 점검 걸림을 다시 찍지 않게 한다.
  --reuse-answer "이유"  (--record와 함께만) 1.1.0 이상으로 시작한 task의 승인 원문이 한 마디 답이 아니고, 이 task의
                     승인 요청 전에 다른 task의 승인 줄과 같으면 --record는 종료 코드 3이다. 그 답을 다시 쓰는 것이 맞을 때
                     이것을 붙이면 승인 줄 끝에 `| 재사용 답: {이유}`, 「표 밖 전이」와 journal에 한 줄(그 답으로는 얼리지 않음).
  --message "전체"   (--record와 함께만) 한 메시지에 여러 task의 답이 있을 때 메시지 전체. 승인 줄 끝에 `| 원문 메시지: "…"`.
                     사람이 읽는 칸이고 승인 판별과 얼림은 이 칸을 읽지 않는다.
  --reason "문장"     사람 답 없이 메인이 판단한 전이(흡수·규칙 바뀜 보류, 다른 곳에서 처리된 백로그). journal에 한 줄.
  --unlisted "이유"   전이표에 없는 짝만 실행한다. journal과 머리 파일 「표 밖 전이」에 남고, 다음 승인 화면 「알릴 것」에
                     "[표 밖 전이]"로 붙는다(점검 확인 전까지). CHANGELOG 후보. 표 안 전이의 조건 미충족(필요한 판정,
                     --record·--reason, --archive-judge, 알림, 판본, stage 좁힘)은 넘기지 못하고 종료 코드 3.
  --archive-judge    judge.md·judge-run.md를 judge.r{n}.md·judge-run.r{n}.md로 보관하고 retry를 올리고, 보관한 판정의
                     「통과 못 한 기준」 번호로 머리 파일 「재시도 범위」를 쓴다. 재시도 상한(run.md 「이번 실행의 값」
                     "자체 검증 재시도", 시작값 2)에 닿았으면 하지 않고 종료 코드 3. `자체검증→진행`은 이것과 함께만.
                     보관한 판정과 같은 n으로 수정 전 사본을 tasks\\{id}\\before.r{n}\\에 뜬다(MANIFEST.md, files\\,
                     코드 kind면 code.patch. 상한 SNAPSHOT_MAX_BYTES, 사본이 실패해도 보관은 하고 목록에 이유. retry_diff.py가 읽는다).
                     판정 표지 judge_started도 비운다.
  --undecided        (--archive-judge와 함께) 판정불가 보관. 보관할 판정의 「통과 못 한 기준」 항목이 모두 판정불가
                     꼬리표(judge.md는 환경, judge-run.md는 환경·대상)이고 하나 이상일 때만 받는다. 재시도 상한·판정 미완료를
                     보지 않고 retry와 「재시도 범위」를 그대로 둔다(보관·사본·표지 비움은 같다). external_progress가
                     `자원 대기:`이면 종료 코드 3.
  --returned 이름     에이전트 반환 직후. 그 에이전트의 결과 파일(판정자면 그 판정 파일)이 없으면 `returned_empty`와 journal을 남기고 `!` 줄을 낸다.
                     다음 `running_agent=`가 표지를 지우고 멈춘 시간을 journal에 남긴다(references/main/errors.md).
  {실행 폴더} resume --session ID --said "원문"  재개의 맨 앞. 재개 줄과 session_id를 쓴다. 진행 중 실행이 여럿인데 원문에 이 실행 폴더 이름이 없으면
                     아무것도 쓰지 않고 종료 3이다. 다른 세션의 흔적은 `!` 줄이다(references/main/resume.md).
  --judge-start 이름[,이름…]  판정자를 띄우기 전에 표지 `judge_started: {시각} {이름} …`을 쓴다(진행·자체검증에서만. 같은 호출의 --status가 있으면 전이 뒤 상태로 본다).
                     다시 부르면 없던 이름만 덧붙이고 시각은 첫 값을 둔다. 표지가 있으면 --amend-criteria를 받지 않는다.
  --judge-clear      judge.md·judge-run.md가 둘 다 없을 때만 표지를 비우고 journal에 메모(있으면 종료 코드 3).
                     표지가 이미 비었으면 `표지 없음`(종료 코드 0, 파일 그대로).
                     --undecided·--judge-start·--judge-clear는 --amend-criteria와 같은 호출에서 받지 않는다.
  --amend-criteria {파일} --source "출처"   판정자가 뜨기 전(대기·진행, 1.1.0부터 시작한 task는 자체검증도.
                     표지 judge_started가 있으면 상태와 상관없이 거부)에 「판정 기준」을 바꾼다. 출처는
                     `작성자 {이상 신호 위치}` / `판정자 {대안 문장 위치}` / `사용자 답 {task id} {승인 기록 시각}`
                     (사용자 답은 그 승인 기록 줄에 원문이 있어야 받는다). criteria.amend{n}.md와 「판정 기준 정정」에 남는다.
  --add "절|줄"       본문 절(넘길 이상 신호, 영향받는 task와 처리, 범위 등)에 한 줄을 더한다. 판정 기준·승인 기록처럼
                     전용 옵션이 있는 절은 받지 않는다.
  --screen-snapshot  result.md를 result.pre-screen.md로 떠 둔다(「승인 화면」만 다시 쓰게 하기 전에. 기록 점검이 절 밖만 본다).
  --now 키,…          그 시각 키에 지금 시각.
  --check [id]       기록 점검 결과만 찍는다(쓰지 않음).
  --park             (따로 부른다) 1.2.0부터 시작하고 커밋 전인 코드 task의 커밋 안 된 변경을 패치로 뜨고(새 파일 포함) 뜬 파일만
                     되돌린다. 패치 쓰기 → `parked_pending` → 되돌리기 → 표지 차례이고, 끊기면 다시 부른다. 표지는 `보류`면 `parked`,
                     판정을 모두 통과한 원인 분석(등록표 REPRO_PATCH_KINDS, 자체검증·승인대기)이면 `repro_patch`(tasks\\{id}\\repro.patch).
                     그 밖과, 패치에 담기지 않거나 패치에 없는 내용이 있거나, `.gitignore`를 바꿨거나, 같은 폴더에 쓰는 다른 task가 돌거나
                     변경을 쥐고 있으면 종료 코드 3(코드 폴더 그대로). 끊긴 치우기는 상태와 상관없이 잇는다.
  --unpark           치운 변경을 그 task의 코드 폴더에 다시 붙이고 표지를 비운다. 자기 표지, 없으면 부모를 따라 올라가 만난 재현 패치를 본다.
                     →진행 전이도 같은 일을 먼저 한다(원인 분석 자손의 코드 task는 대기→진행 때). 충돌, 패치 전체 실패, 어긋남은
                     종료 코드 3(표지와 상태 그대로). 충돌을 푼 뒤(`git add`) 다시 부르면 표지를 비운다. `park_applying`이 그 근거다.
  --park-cancel      `parked_pending`을 취소한다. 남은 변경이 패치 안의 것뿐이면 되돌리지 않고 HEAD로 돌아간 패치 파일만 붙이고 표지를 비운다.
  --park-drop        (--record와 함께) 사람 답으로 표지만 비운다. 패치와 코드 폴더는 그대로 둔다.
  new --from-answer T  사용자 답을 계기로 만드는 task. origin을 `사용자 {T} {답 시각}`(T의 승인 기록에서 원문이 있는 가장
                     늦은 줄)으로 채우고, kind는 「건드릴 파일」에 정본(spec/·design/, 고친 판 revised/) 밖 경로가 있으면 fix,
                     없으면 change로 정한다(비면 거부). --origin을 함께 주면 그 뒤에 붙인다.
  new --kind change  「건드릴 파일」에 정본 밖 경로가 있으면 거부(코드를 고치는 변경은 fix).
  new --from-answer T --place {곳 키}  코드 확인의 `이 코드만 고침` 답으로 수정 task를 만든다. 제목과 본문은 스크립트가 쓰고,
                     origin은 `사용자 {T} {답 시각} 코드 확인 {키}`, 부모는 T다.
  --record "코드 확인 재지 못함 {T}|합쳐도 됨|원문"  다시 재도 못 잰 코드 task를 보지 않고 합치는 답. 보안 신호와 시험 변화를 함께 푼다. 빈 답과 위임의 말은 받지 않는다.
  --record "코드 확인 {곳 키}|{결정}|원문"  곳 하나의 답(`b1,b2=문제 없음 b3=판단 안 됨 …`, 판단이 하나면 값만, 일괄은 `나머지 남김`).
                     places.md의 `처리:`를 적고 그 키가 열려 있으면 card_open을 비운다. 답이 빠진 판단이 있으면 거부.

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
  탐침: →승인대기는 자체검증에서만(stage 실행승인·결과승인), stage=기록에서 judge.md → judge.plan.md,
        알림은 승인 기록이 있어도 screen.py 알림 조건, →완료는 exec.py --verify 통과(아니면 stage=결과승인으로 승인)
  stage 좁힘(rules 2 이상의 합치기·마무리·배포 실행)
    →승인대기                                       묻는 단계(stage 실행승인·결과승인·넣기승인·직전확인)
    승인대기→진행                                   묻는 단계가 아닌 다음 단계(--screen-snapshot이면 그대로)
    →완료                                           stage 끝. 합치기는 exec.py --verify 통과와 실행 판정의 통과 못 한
                                                     기준 0(아니면 stage=결과승인으로 승인), 1.2.0부터는 얼린 고정 꼴대로 돈 것만 알림(notice_block). 마무리는 결과승인에서
                                                     --record와 exec.py --verify 통과(1.2.0부터 얼린 줄대로 돌았으면 알림), 배포 실행은 유지면 --verify 통과
  *→보류                                            --record 또는 --reason
  (1.2.0부터 시작한 코드 task의 완료→보류·백로그는 커밋이 있거나 no_change일 때만. --unlisted로도 넘지 못한다)
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
import posixpath
import re
import shutil
import subprocess
import sys
from datetime import datetime

import board
import delegation
import deploy_reuse
import devflow_lib
import kinds
import places
import project_docs
import retry_diff
import shadow_check
import slots


# devflow_lib.Reject와 같은 객체(Doc이 내는 거부를 아래 `except Reject`가 그대로 잡는다)
Reject = devflow_lib.Reject

# 키=값과 --unlisted의 거부 문구. 채우는 길은 등록표 kinds.TASK_KEYS
OPTION_ONLY = "{}는 전용 옵션으로만 바꾼다(status → --status, retry → --archive-judge, kind → new --kind)"
SELFCHECK_ONLY = "{}=값은 진행→자체검증 전이(--status 자체검증)와 함께서만"
UNLISTED_ONLY = " — --unlisted는 전이표에 없는 짝만 넘긴다"
SCRIPT_OWNED = "{}는 스크립트가 채우는 키다(키=값으로 바꾸지 않는다)"
# 판정 기준 정정의 거부 문구(D-C7). 옛 task(1.1.0 전에 시작)는 AMEND_STATUS_OLD
AMEND_MARKED = ("판정자가 뜬 뒤에는 판정 기준을 고치지 않는다(judge_started: {}). "
                "재시도(--archive-judge)·판정불가 보관(--archive-judge --undecided)·--judge-clear 뒤에 고친다")
AMEND_STATUS_NEW = "판정 기준 정정은 판정자가 뜨기 전(대기·진행·자체검증)에만"
AMEND_STATUS_OLD = "판정 기준 정정은 판정자가 뜨기 전(대기·진행)에만"
# 판정 표지(--judge-start·--judge-clear)의 거부 문구와 출력·journal 메모
JUDGE_START_NOW = "--judge-start는 진행·자체검증에서만(지금 {})"
JUDGE_START_AFTER = "--judge-start는 진행·자체검증에서만(전이 뒤 {})"   # 같은 호출의 --status 전이 뒤 상태
JUDGE_FILES_PRESENT = "판정 파일이 있음({}): 표지를 지우지 않는다(--archive-judge로 보관하면 함께 비운다)"
JUDGE_CLEARED = "판정 표지 지움: {}"
NO_MARK = "표지 없음"
# 판정불가 보관(--archive-judge --undecided)의 거부 문구
UNDECIDED_WAIT = "자원 대기라 판정불가로 보관하지 않음: {}"
UNDECIDED_MIXED = "판정불가가 아닌 항목이 있음: --undecided 없이 보관한다(재시도)"
UNDECIDED_NONE = "판정불가 항목이 없음: --undecided 없이 보관한다"
# 「재시도 범위」 회차 줄. 회차, 보관한 판정, 사본, 고칠 기준
RETRY_SCOPE_LINE = ("- 회차 {} (보관한 판정: {}, 사본: {}): 고칠 기준: {}. 그 기준 안에서는 판정자가 적지 않은 같은 종류의 결함도 고친다. "
                    "다른 기준과 판정자의 권장은 고치지 않는다. 판정자의 대안 문장은 그대로 옮기지 않고, 그 근거 줄과 원천을 열어 확인한 뒤 쓴다"
                    "(어긋나면 원천을 따르고 「알릴 것」에 적는다).")


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

    def judges(stage=None):
        ok, why = devflow_lib.judges_present(t, stage)
        return None if ok else "필요한 판정이 없음: " + why

    def ask_judges():
        """승인대기로 갈 때: 1.1.1부터 시작한 STAGE kind는 묻는 stage 앞의 판정(kinds.STAGE_JUDGES)."""
        stage = devflow_lib.stage_of(t)
        why = judges(stage)
        return why + " (stage={} 앞, kinds.STAGE_JUDGES)".format(stage) \
            if why and devflow_lib.stage_judges(t, stage) is not None else why

    def stage_end():
        if kind == "deploy-exec" and devflow_lib.stage_of(t) != "끝":
            return "배포 실행은 stage: 끝이 된 뒤에 완료(references/kinds/deploy-exec.md 「단계와 기록」)"
        return None

    if old == new:
        return None
    if new == kinds.DONE:
        why = places.completion_block(run_dir, t)   # 코드 확인의 답이 빠졌으면 닫지 않는다. 보류는 받는다(설계 6.16절)
        if why:
            return why
    if kind == "probe" and old == "진행" and new in ("승인대기", kinds.DONE):
        # 탐침은 계획·기록 모두 읽기 판정 뒤에 묻는다(설계 A-17)
        return "탐침은 읽기 판정을 거친다(자체검증)"
    if kind in kinds.STAGE_KINDS and devflow_lib.rules_level(t) >= 2 and new != "보류":
        why = stage_rule(run_dir, t, old, new, ctx)
        if why:
            return why
    if old == kinds.DONE and new in devflow_lib.HELD_STATUSES and devflow_lib.needs_judgment_record(t) \
            and not str(t.get("commit", "") or "").strip() and not devflow_lib.no_change(t):
        # 커밋 없는 보류·백로그는 합치지 않는 코드로 보므로, 끝난 코드 task가 내려가면 흐름 브랜치의 코드를 아무도 보지 않는다
        return "끝났고 커밋이 빈 코드 task는 {}로 내리지 않는다: 커밋을 찾아 commit={{해시}}를 함께 적거나, 코드를 바꾸지 않았으면 no_change=true를 먼저 적는다".format(new)
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
        problems = devflow_lib.judgment_problems(t)
        return "판단 기록을 고친 뒤 자체검증으로(판정 뒤에 고치면 R3가 걸린다): " + " / ".join(problems) if problems else None
    if pair == ("자체검증", "진행"):
        return None if ctx["archived"] else "자체검증→진행(재시도)은 --archive-judge와 함께"
    if pair == ("자체검증", "승인대기"):
        return ask_judges()
    if pair == ("자체검증", "완료"):
        if not rec or point not in ("알림", "승인"):
            return "자체검증→완료는 --record \"알림|…\"(또는 승인)와 함께"
        if kind not in kinds.NOTIFY_KINDS and kind not in kinds.STAGE_KINDS and not devflow_lib.prior_approval(t):
            return "{}는 알림으로 지나가지 않는다(승인대기로)".format(kind)
        if kinds.notify_policy(kind) == "findings" and not devflow_lib.prior_approval(t) \
                and not devflow_lib.version_at_least(t.get("started_version"), devflow_lib.RULES_V120):
            return "{}는 알림으로 지나가지 않는다(승인대기로)".format(kind)
        why = judges() or stage_end()
        if why:
            return why
        if kind not in kinds.STAGE_KINDS and devflow_lib.prior_approval(t) \
                and devflow_lib.version_at_least(t.get("started_version"), devflow_lib.RULES_V120):
            # 앞 승인 뒤에 다시 쓴 결과도 사람 몫이 있으면 지나가지 않는다(설계 5.1절 공통 조건)
            import screen
            b = screen.build(run_dir, t["id"])
            if "error" not in b and (b["risky"] or b["counts"]["n_decide"] or b["counts"]["n_todo"]):
                return "알림 불가: 앞 승인 뒤의 결과에 사람 몫이 있다(정해 주실 것, 하실 일, 성질 `위험`)"
        # 탐침은 실행승인 답이 승인 기록에 있어도 기록 단계의 알림 조건(탐침 기록 표)을 본다
        if kind == "probe" or (devflow_lib.is_new_task(t) and kind in kinds.NOTIFY_KINDS
                               and kind not in kinds.STAGE_KINDS and not devflow_lib.prior_approval(t)):
            import screen
            ok, msg = screen.notify_status(run_dir, t["id"])
            if not ok:
                return "알림 불가: " + msg
        return None
    if pair == ("승인대기", "완료"):
        if not rec:
            return "승인대기→완료는 --record(사용자 답)와 함께"
        if point.startswith(devflow_lib.PARTIAL_POINTS):
            return "지점 `{}`의 답은 상태를 옮기지 않는다. 답을 먼저 남기고 전체 답으로 닫는다".format(point)
        import board
        held = board.summary_wait(devflow_lib.load_tasks(run_dir), t)
        if held:
            return "요구사항 종합을 기다린다({}): 상세가 닫힌 뒤에 묻는다".format(", ".join(held))
        return judges() or stage_end()
    if pair == ("승인대기", "진행"):
        return None if (rec or ctx["snapshot"]) else "승인대기→진행은 --record(사람 답) 또는 --screen-snapshot과 함께"
    if pair == ("진행", "승인대기"):
        if kind not in kinds.STAGE_KINDS:
            return "진행→승인대기는 합치기·마무리·배포 실행만(그 밖은 자체검증을 거침)"
        # 1.1.1부터: 자체검증을 건너뛰어 판정 없이 묻는 길을 막는다(옛 task는 그대로)
        return ask_judges() if devflow_lib.stage_judges(t, devflow_lib.stage_of(t)) is not None else None
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


def review_stale(t):
    """마무리 실행 승인 앞에 그 판정 뒤의 마무리 리뷰가 있는가(설계 7.3절). 없으면 사람이 전체를 보지 못한 채 넣는다."""
    path = os.path.join(t["_dir"], devflow_lib.WRAP_REVIEW)
    later = [os.path.join(t["_dir"], name) for name in tuple(kinds.JUDGE_FILES.values()) + ("result.md",)] \
        + [os.path.join(os.path.dirname(os.path.dirname(t["_dir"])), "decisions.md")]
    if not os.path.isfile(path) or any(os.path.isfile(p) and os.path.getmtime(path) < os.path.getmtime(p) for p in later):
        return "마무리 리뷰가 없거나 판정, 결과, 결정 기록보다 오래됨: `visual.py {{실행 폴더}} {} --wrap-review`를 돌린 뒤 묻는다".format(t["id"])
    return ""


def notice_block(run_dir, t, point, problems):
    """단계 kind를 사람 답 없이 닫는 관문(설계 5.1절 공통 조건, 5.3절 6): 얼린 줄대로 돌았고, 판정이 통과했고, 성질 `위험`과 인프라 경로가 없다.
    합치기는 「정해 주실 것」, 「하실 일」도 본다. 마무리의 그 칸은 내보낼 명령과 정리 목록이고 실행 승인에서 이미 답했다. 막히면 묻는 길을 말한다."""
    import screen
    why = list(problems)
    if point != "알림":
        why.append("사람 답 없이 닫으려면 --record \"알림|…\"")
    b = screen.build(run_dir, t["id"])
    if "error" in b:
        why.append(b["error"])
    else:
        if b["risky"]:
            why.append("성질 `위험` 항목이 있다")
        if b["infra_paths"]:
            why.append("인프라 경로: " + ", ".join(b["infra_paths"]))
        if devflow_lib.item_count(b["failed"]):
            why.append("통과 못 한 기준 {}개".format(devflow_lib.item_count(b["failed"])))
        if t.get("kind") == "merge" and (b["counts"]["n_decide"] or b["counts"]["n_todo"]):
            why.append("사람 몫이 있다(정해 주실 것, 하실 일)")
        if t.get("kind") == "merge" and (b["missing"] or b["unparsed"]):
            why.append("결과 파일의 칸 문제: " + ", ".join(b["missing"] + b["unparsed"]))
    return "알림으로 닫지 못함: {} — stage=결과승인으로 승인을 받는다".format("; ".join(why)) if why else ""


def stage_rule(run_dir, t, old, new, ctx):
    """rules 2 이상의 합치기·마무리·배포 실행: 상태와 stage가 맞는가. 맞으면 None."""
    kind, st, st_old = t.get("kind", ""), devflow_lib.stage_of(t), ctx.get("old_stage", "")
    if new == "승인대기" and st not in kinds.ASK_STAGES:
        return "{}의 승인대기는 묻는 단계와 함께(stage={})".format(kind, "/".join(sorted(kinds.ASK_STAGES)))
    if new == "승인대기" and kind == "wrap-up" and st == "실행승인" \
            and devflow_lib.version_at_least(t.get("started_version"), devflow_lib.RULES_V120):
        why = review_stale(t)
        if why:
            return why
    if old == "승인대기" and new == "진행" and kind == "wrap-up" and st == "실행":
        left = project_docs.unresolved(run_dir, t)
        if left:
            return "같은 절 두 곳이 풀리지 않아 내보내지 않는다: {} — 답을 `project_docs.py … --insert {{폴더}} --take`로 반영한다(그 문서를 빼려면 `#(파일 전체)=뺌`)".format(", ".join(left))
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
    v120 = devflow_lib.version_at_least(t.get("started_version"), devflow_lib.RULES_V120)
    point = (ctx["record"] or ("", "", ""))[0]
    if kind == "deploy-exec" and v120 and point == "알림":
        return "배포 실행의 결과는 알림으로 지나가지 않는다(설계 5.1절)"
    if kind == "merge" and v120 and not answered:
        why = notice_block(run_dir, t, point, execmod.merge_notice_problems(run_dir, t))
        if why:
            return why
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
        if not answered and not v120:
            return "마무리는 결과승인(승인대기)에서 --record와 함께 완료"
        if not answered:
            why = notice_block(run_dir, t, point, execmod.wrap_notice_problems(run_dir, t))
            if why:
                return why
        if not ok:
            return "exec.py --verify 실패({})".format("; ".join(lines))
        proof = final_candidate_ci_problem(run_dir, t, always=True, expected_commit=t.get("exported_commit", ""))
        if proof:
            return proof
        if devflow_lib.uses_isolation_contract(t) and devflow_lib.final_ci_failed(t) and not devflow_lib.risk_accepted(t):
            # 사용자 결정 U1(2026-10-31): 실패한 최종 CI는 위험 수용 답이 있을 때만 내보낸 채 완료
            return "최종 CI에 통과 못 한 기준 {}개이고 승인 기록에 위험 수용 답이 없음 — {}".format(
                devflow_lib.final_ci_failed(t), devflow_lib.RISK_SENTENCE)
    if kind == "probe" and not ok and not answered:
        return "exec.py --verify 실패({}) — stage=결과승인으로 승인을 받는다".format("; ".join(lines))
    if kind == "deploy-exec" and str(t.get("deploy_outcome", "")).strip() == "유지" and not ok \
            and any(n.startswith("approved-cmds-") for n in os.listdir(t["_dir"])):
        return "exec.py --verify 실패({})".format("; ".join(lines))
    if kind == "deploy-exec" and str(t.get("deploy_outcome", "")).strip() == "유지":
        proof = deploy_target_problem(run_dir, t, record=ctx.get("record"))
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
FULL_SHA = re.compile(r"[0-9a-fA-F]{40}")
BUILD_ID = re.compile(r"([0-9a-fA-F]{7,40})(?:[-+._:/][!-~]*)?")   # 해시로 시작하고 해시가 경계에서 끝난다


def same_git_commit(a, b):
    a, b = str(a or "").strip(), str(b or "").strip()
    return bool(GIT_SHA.fullmatch(a) and GIT_SHA.fullmatch(b) and (a.startswith(b) or b.startswith(a)))


def final_candidate_ci_problem(run_dir, t, always=False, expected_commit=None):
    if not devflow_lib.uses_isolation_contract(t) or (not always and not final_merge_candidate(run_dir, t)):
        return None
    path = os.path.join(t["_dir"], "judge-run.md")
    sec = devflow_lib.sections(devflow_lib.read_text(path), level=2) if os.path.isfile(path) else {}
    if sec.get("최종 배포 후보 CI") is None:
        return "최종 배포 후보 CI 근거 없음: judge-run.md 「최종 배포 후보 CI」"
    values = devflow_lib.final_ci_values(t)
    missing = [k for k in ("범위", "검증 commit", "검증 artifact") if not values.get(k) or values.get(k) in ("없음", "(없음)")]
    if missing:
        return "최종 배포 후보 CI 필수 값 없음: {}".format(", ".join(missing))
    if values["범위"] != "전체 검증":
        return "최종 배포 후보 CI 범위가 전체 검증이 아님({})".format(values["범위"])
    commit = str(t.get("commit", "") if expected_commit is None else expected_commit or "").strip()
    checked = values["검증 commit"].strip()
    if devflow_lib.run_from_v120(run_dir):
        why = devflow_lib.final_ci_artifact_problem(values["검증 artifact"])
        if why:
            return why
        if values["검증 artifact"] == devflow_lib.SOURCE_TESTED and not FULL_SHA.fullmatch(checked):
            return "소스 시험의 검증 commit이 전체 해시(40자)가 아님({})".format(checked)
    if not GIT_SHA.fullmatch(checked):
        return "최종 배포 후보 CI 검증 commit이 유효한 Git SHA가 아님({})".format(checked)
    if not GIT_SHA.fullmatch(commit):
        return "최종 배포 후보 commit이 유효한 Git SHA가 아님({})".format(commit or "없음")
    if not same_git_commit(checked, commit):
        return "최종 배포 후보 CI 검증 commit({})이 후보 commit({})과 다름".format(checked, commit)
    return None


def build_id_problem(build, commit):
    """소스 시험의 빌드 식별자(값이 있는 칸의 글자)를 배포 commit에 대조한다. 다른 커밋의 해시는 위험 수용으로 닫는 길을 알리지 않는다."""
    if "dirty" in build.lower():
        return "빌드 식별자가 커밋 안 된 변경을 담은 빌드임({})".format(build)
    m = BUILD_ID.fullmatch(build)
    if m and commit.startswith(m.group(1).lower()):
        return None
    if m and not m.group(1).isdigit():
        return "빌드 식별자({})가 배포 commit({})이 아닌 다른 커밋임".format(build, commit[:12])
    return "빌드 식별자({})가 커밋으로 시작하지 않음: 그런 꼴을 쓰는 프로젝트면 칸을 `없음`으로 적고 원래 값은 확인 줄에 남긴다(위험 수용 답으로 닫는다)".format(build)


def risk_answered(t, item, record):
    """그 이유를 적은 위험 수용 답이 승인 기록에 있거나, 이번 호출의 --record가 그 답인가."""
    return devflow_lib.risk_accepted(t, item=item) or bool(record and devflow_lib.risk_answer(record_line(record), item))


def unmeasured_problem(t, build_missing, record):
    """기계로 재지 못한 것 가운데 사람이 그 이유를 적어 받아들이지 않은 것의 이유 글. 없으면 None."""
    import exec as execmod
    labels = execmod.deploy_tree_unmeasured(t)
    open_build = build_missing and not risk_answered(t, devflow_lib.BUILD_ID_RISK, record)
    open_tree = bool(labels) and not risk_answered(t, devflow_lib.TREE_RISK, record)
    if not (open_build or open_tree):
        return None
    reasons = ["빌드 식별자 없음: 빌드가 이 커밋인지 기계로 확인하지 못했습니다"] if open_build else []
    if open_tree:
        reasons.append("{}은 사용자나 메인이 다른 방법으로 실행해 그 순간의 HEAD·작업 트리를 재지 못했습니다".format(", ".join(labels)))
    items = " ".join(([devflow_lib.BUILD_ID_RISK] if open_build else []) + ([devflow_lib.TREE_RISK] if open_tree else []))
    return "{}. 받아들이면 답을 `--record \"승인|위험 수용 {}|{{원문}}\"`으로 적고 `decisions.md`에 `[위험 수용 T0xx] {{항목}}` 한 줄을 쓴다".format(
        ". ".join(reasons), items)


def deploy_side_has(t, sec, value):
    """값이 배포 쪽 근거(`judge-run.md`의 동일성 절 밖, `logs\\`의 로그)에 나오는가."""
    if any(value in body for title, body in sec.items() if title != "배포 대상 동일성"):
        return True
    logs = os.path.join(t["_dir"], "logs")
    for name in os.listdir(logs) if os.path.isdir(logs) else []:
        path = os.path.join(logs, name)
        if os.path.isfile(path):
            with open(path, "rb") as f:
                if value.encode("utf-8") in f.read():
                    return True
    return False


def source_tested_problem(t, canonical, values, record=None, before_answer=False):
    """최종 CI가 소스를 시험한 경우: artifact 글자 비교 대신 전체 해시, 배포 폴더 상태(exec.py 기록), 빌드 식별자를 본다.
    before_answer는 결과 승인 화면(`--identity`)이다: 답 뒤에 적는 `deployed_commit`이 비어 있어도 그 비교만 건너뛴다."""
    if values.get("검증 artifact") != devflow_lib.SOURCE_TESTED:
        return "배포 대상 동일성 검증 artifact가 최종 CI의 `{}`가 아님({})".format(
            devflow_lib.SOURCE_TESTED, values.get("검증 artifact", "없음"))
    for key in ("검증 commit", "배포 commit"):
        if not FULL_SHA.fullmatch(values.get(key, "")):
            return "소스 시험의 {}이 전체 해시(40자)가 아님({})".format(key, values.get(key, "없음"))
    commit = values["배포 commit"].lower()
    if values["검증 commit"].lower() != commit:
        return "배포 commit이 검증 commit과 다름({} != {})".format(values["배포 commit"], values["검증 commit"])
    if canonical["검증 commit"].lower() != commit:
        return "배포 검증 commit이 최종 CI commit과 다름({} != {})".format(values["검증 commit"], canonical["검증 commit"])
    return deploy_side_problem(t, commit, values, record, before_answer)


def identity_lines(run_dir, t):
    """`--identity`: 결과 승인 화면(screen.py를 쓰지 않는다)에 옮길 줄. 1.2.0 앞에 시작한 실행은 빈 목록."""
    if not devflow_lib.run_from_v120(run_dir):
        return []
    why = deploy_target_problem(run_dir, t, before_answer=True)
    result = "닫지 못함 — " + why if why else "통과"
    label = "위험 수용(최종 CI 없음). 배포 쪽 대조: " if devflow_lib.no_ci_accepted(run_dir, t) else ""
    return devflow_lib.source_tested_lines(run_dir, t) + ["- 배포 대상 동일성: " + label + result]


RESUME_QUIET_MIN = 30   # 다른 세션의 기록이 이보다 가까우면 돌고 있을 수 있다고 본다
def deploy_side_problem(t, commit, values, record, before_answer):
    """최종 CI와 상관없이 배포 쪽에서 잴 수 있는 것: `deployed_commit`, 배포 폴더 상태, 빌드 식별자."""
    import exec as execmod
    deployed = str(t.get("deployed_commit", "") or "").strip()
    if (deployed or not before_answer) and not same_git_commit(deployed, commit):
        return "배포 commit 근거({})가 deployed_commit({})과 다름".format(commit, deployed or "없음")
    build = values.get("빌드 식별자", "")
    build_missing = build in ("", "없음", "(없음)")
    return execmod.deploy_tree_problem(t, commit) or (None if build_missing else build_id_problem(build, commit)) \
        or unmeasured_problem(t, build_missing, record)


NO_FINAL_CI = ("마무리 task가 없어 이 실행에서 돌린 최종 CI가 없습니다. 올라간 커밋을 이 실행이 시험했는지 기계로 확인하지 못했습니다. "
               "받아들이면 답을 `--record \"승인|위험 수용 {}|{{원문}}\"`으로 적고 `decisions.md`에 `[위험 수용 T0xx] {{항목}}` 한 줄을 쓴다")


def deploy_target_problem(run_dir, t, record=None, before_answer=False):
    """1.0.1 배포 유지 전에는 검증 대상과 실제 배포 대상의 commit·artifact가 각각 같아야 한다.
    1.2.0부터 시작한 실행에서 최종 CI가 소스를 시험했으면 artifact 대신 source_tested_problem을 본다."""
    if not devflow_lib.uses_isolation_contract(t):
        return None
    canonical, why = devflow_lib.canonical_final_ci(run_dir)
    if canonical is None:
        if not devflow_lib.deploy_only_run(run_dir):
            return "배포할 권위 있는 최종 CI 근거 없음: " + why
        if not risk_answered(t, devflow_lib.NO_CI_RISK, record):
            return NO_FINAL_CI.format(devflow_lib.NO_CI_RISK)
    new_rules = devflow_lib.run_from_v120(run_dir)
    if new_rules and canonical is not None:
        why = devflow_lib.final_ci_artifact_problem(canonical["검증 artifact"])
        if why:
            return why
    path = os.path.join(t["_dir"], "judge-run.md")
    sec = devflow_lib.sections(devflow_lib.read_text(path), level=2) if os.path.isfile(path) else {}
    text = sec.get("배포 대상 동일성")
    if text is None:
        return "배포 대상 동일성 근거 없음: judge-run.md 「배포 대상 동일성」"
    keys = ("검증 commit", "검증 artifact", "배포 commit", "배포 artifact")
    values = {}
    for line in text.splitlines():
        m = re.match(r"^-\s*({}|빌드 식별자)\s*:\s*(.+?)\s*$".format("|".join(keys)), line.strip())
        if m:
            values[m.group(1)] = m.group(2)
    if canonical is None:   # 사람은 "이 실행이 시험하지 않았다"만 받아들였다. CI 대조만 빠지고 배포 쪽은 그대로 잰다
        if not FULL_SHA.fullmatch(values.get("배포 commit", "")):
            return "최종 CI 없는 배포의 배포 commit이 전체 해시(40자)가 아님({})".format(values.get("배포 commit", "없음"))
        return deploy_side_problem(t, values["배포 commit"].lower(), values, record, before_answer)
    if new_rules and canonical["검증 artifact"] == devflow_lib.SOURCE_TESTED:
        return source_tested_problem(t, canonical, values, record, before_answer)
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
    if new_rules and not deploy_side_has(t, sec, values["배포 artifact"]):
        return ("배포 artifact({})가 배포 근거(`judge-run.md`의 확인 줄, 로그)에 없음: 올라간 것에서 읽은 값을 적는다. "
                "소스를 시험했으면 최종 CI의 값은 `{}`다").format(values["배포 artifact"], devflow_lib.SOURCE_TESTED)
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
                         "deploy-exec": ("넣기승인",), "probe": ("실행승인",)}.get(kind, ()):
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
    devflow_lib.journal_append(run_dir, kind, tid, line)


def stall_note(run_dir, tid, asked_at):
    """질문을 띄운 뒤 반환은 왔으나 처리되지 못한 task의 수와 시간(설계 8.1절). 머리 파일을 고치는 쪽이 없으므로 수정 시각으로 센다.
    아직 도는 에이전트의 쓰기도 반환으로 세므로 넘치게 세는 값이다."""
    try:
        asked = datetime.strptime(asked_at, "%Y-%m-%d %H:%M:%S").timestamp()
    except ValueError:
        return None
    late = {}
    for oid, o in devflow_lib.load_tasks(run_dir).items():
        if oid == tid or o.get("status") not in kinds.BUSY_STATUSES:
            continue
        marks = [os.path.getmtime(os.path.join(o["_dir"], n)) for n in os.listdir(o["_dir"])
                 if n == "result.md" or (n.startswith("judge") and n.endswith(".md"))]
        fresh = [m for m in marks if m > asked + 1]   # asked_at은 초까지다. 같은 초에 쓴 파일을 세지 않는다
        if fresh:
            late[oid] = min(fresh)
    if not late:
        return "멈춤 측정: 처리 못 한 반환 0개"
    minutes = int((datetime.now().timestamp() - min(late.values())) / 60)
    return "멈춤 측정: 처리 못 한 반환 {}개, {}분({})".format(len(late), minutes, ", ".join(sorted(late)))


def place_answer_key(rec):
    """`--record`의 지점이 곳 답(`코드 확인 {키}`)이면 그 키."""
    prefix = devflow_lib.CODE_CHECK_ORIGIN + " "
    return rec[0][len(prefix):].strip() if rec and rec[0].startswith(prefix) and not rec[0].startswith(devflow_lib.UNMEASURED_POINT) else ""


def unmeasured_answer_task(rec):
    """`--record`의 지점이 재지 못한 task의 답(`코드 확인 재지 못함 {T}`)이면 그 task."""
    return rec[0][len(devflow_lib.UNMEASURED_POINT):].split("@", 1)[0].strip() if rec and rec[0].startswith(devflow_lib.UNMEASURED_POINT) else ""


def card_check(run_dir, tid, status, key):
    if status != "승인대기":
        raise Reject("--card-open은 승인대기에서만(지금 {})".format(status))
    place = places.find(places.read(run_dir, tid), key)
    if place is None:
        raise Reject("곳을 찾지 못함: {} (`screen.py … --places`의 키)".format(key))
    if place.get("처리") != places.WAITING:
        raise Reject("이 곳은 답을 기다리지 않음: {} {}".format(key, place.get("처리")))


def place_answer_check(run_dir, tid, status, key, decision):
    if status != "승인대기":
        raise Reject("곳 답은 승인대기에서만(지금 {})".format(status))
    place = places.find(places.read(run_dir, tid), key)
    if place is None:
        raise Reject("곳을 찾지 못함: " + key)
    problem = places.decision_problem(place, decision, places.code_shown(run_dir, place))
    if problem:
        raise Reject(problem)


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


def delegation_check(run_dir, tasks, t, rec):
    """위임으로 닫는 답을 관문으로 거른다(설계 9절). 위임의 말을 위임 표지 없이 승인으로 적는 것도 받지 않는다. 옛 task는 그대로다."""
    line = record_line(rec)
    new_task = devflow_lib.version_at_least(t.get("started_version"), devflow_lib.RULES_V120)
    if new_task and rec[0] == devflow_lib.HANDED_POINT:
        return delegation.handed_answer_problem(t, rec[1]) or None
    if not devflow_lib.approval_line(line):
        return None
    if new_task and devflow_lib.HANDED_MARK.search(rec[1]):
        return "넘김 표지는 승인 줄에 적지 않는다: `--record \"{}|[하실 일 넘김 {}] {{항목}}|{{원문}}\"`".format(devflow_lib.HANDED_POINT, t.get("id"))
    if delegation.is_delegated_line(line):
        if not new_task:
            return "1.2.0 앞에 시작한 task는 위임으로 닫지 않는다 — 사람에게 묻고 답을 그대로 적는다"
        import screen
        return delegation.answer_problem(run_dir, line, screen.delegation_status(run_dir, t["id"], tasks)) or None
    if not new_task:
        return None
    return delegation.plain_answer_problem(rec[2], bool(devflow_lib.cmd_lines(devflow_lib.decide_cell(t["_dir"])))) or None


def reuse_check(tasks, t, rec, now):
    """적을 승인 줄의 원문이 다른 task의 더 이른 승인 줄 원문과 같으면 (그 task id, 그 줄 시각), 아니면 None.
    기준 시각은 이 task의 approval_requested(없으면 now). 한 마디 답(devflow_lib.short_answer)은 견주지 않는다.
    위임으로 닫는 답은 같은 원문이 정상이고 관문이 따로 거른다."""
    if not devflow_lib.version_at_least(t.get("started_version"), devflow_lib.RULES_V110):
        return None
    line = record_line(rec)
    if delegation.is_delegated_line(line) and devflow_lib.version_at_least(t.get("started_version"), devflow_lib.RULES_V120):
        return None
    text = devflow_lib.record_quote(line)
    if not devflow_lib.approval_line(line) or not rec[2].strip() or text is None or devflow_lib.short_answer(rec[2]):
        return None
    key = devflow_lib.answer_key(text)

    def when(value):
        for fmt, n in (("%Y-%m-%d %H:%M:%S", 19), ("%Y-%m-%d %H:%M", 16)):
            try:
                return datetime.strptime(str(value or "").strip()[:n], fmt)
            except ValueError:
                pass
        return None

    base = when(t.get("approval_requested")) or when(now)
    found = None
    for oid, o in tasks.items():
        if oid == t.get("id"):
            continue
        for other in devflow_lib.record_lines(o):
            stamp = devflow_lib.record_fields(other)[0]
            at = when(stamp)
            if at is None or base is None or not at < base or not devflow_lib.approval_line(other):
                continue
            if devflow_lib.answer_key(devflow_lib.record_quote(other)) == key and (found is None or at < found[2]):
                found = (oid, stamp, at)
    return found[:2] if found else None


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


def archive_check(run_dir, t, undecided=False):
    """보관할 수 있는지만 본다(파일을 바꾸지 않는다). (retry, 보관할 파일 목록).
    undecided(판정불가 보관)면 재시도 상한과 판정 미완료 대신 꼬리표 조건과 자원 대기를 본다."""
    d = t["_dir"]
    retry = int(str(t.get("retry", "0") or "0").strip() or 0)
    if undecided:
        wait = devflow_lib.resource_wait(t)
        if wait:
            raise Reject(UNDECIDED_WAIT.format(wait))
    else:
        cap = devflow_lib.run_value(run_dir, "자체 검증 재시도", kinds.RUN_DEFAULTS["자체 검증 재시도"])
        if retry >= cap:
            raise Reject("재시도 상한 {}: 다시 띄우지 않고 통과 못 한 채 승인으로 올린다(SKILL.md 2절 「실패 처리」)".format(cap))
        progress = devflow_lib.judge_run_contract_problems(t)
        if progress:
            raise Reject("판정 미완료라 재시도를 보관하지 않음: " + "; ".join(progress))
        if t.get("kind") == "wrap-up" and devflow_lib.final_ci_cause(t) == "코드":
            # 사용자 결정 U1·U2(2026-10-31): 코드 때문에 실패한 최종 CI는 문서 작성자에게 보내지 않는다
            raise Reject("최종 CI 실패 원인이 코드(judge-run.md 「최종 CI 실패 원인」): 작성자 재시도로 세지 않고 통과 못 한 채 "
                         "승인대기 stage=실행승인으로 묻는다(위험 수용 / 고침 / 보류, references/kinds/wrap-up/main-order.md)")
    present = [n for n in ("judge.md", "judge-run.md") if os.path.isfile(os.path.join(d, n))]
    if not present:
        raise Reject("보관할 판정 파일(judge.md·judge-run.md)이 없음")
    if undecided:
        undecided_check(d, present)
    return retry, present


def undecided_check(d, present):
    """보관할 판정의 「통과 못 한 기준」 항목이 모두 판정불가 꼬리표이고 하나 이상인지 본다. `대상`은 실행 판정의
    항목에서만 꼬리표로 읽는다(screen.split_tagged와 같은 규칙)."""
    import screen
    tagged = other = 0
    for name in present:
        text = devflow_lib.sections(devflow_lib.read_text(os.path.join(d, name)), level=2).get("통과 못 한 기준", "")
        keep, target, env = screen.split_tagged(text, allow_target=(name == kinds.JUDGE_FILES["run"]))
        tagged += env + len(target)
        other += devflow_lib.item_count(keep) - env   # 남긴 글에서 `환경`이 아닌 항목(실패, 지시, 읽기 판정의 대상)
    if other:
        raise Reject(UNDECIDED_MIXED)
    if not tagged:
        raise Reject(UNDECIDED_NONE)


def archive_judge(run_dir, t, doc, undecided=False):
    d = t["_dir"]
    retry, present = archive_check(run_dir, t, undecided)
    n = retry + 1
    while any(os.path.exists(os.path.join(d, x)) for x in ("judge.r{}.md".format(n), "judge-run.r{}.md".format(n))):
        n += 1
    moved = []
    for name in present:
        dst = name.replace(".md", ".r{}.md".format(n))
        os.replace(os.path.join(d, name), os.path.join(d, dst))
        moved.append(dst)
    snap = make_snapshot(run_dir, t, n)   # 판정 파일을 옮긴 뒤, 「재시도 범위」를 쓰기 전
    if doc.get("judge_started"):
        doc.set("judge_started", "")   # 보관한 판정의 판정자는 끝났다. 다음 판정자를 띄울 때 다시 찍는다
    if undecided:
        return moved, snap   # 판정불가 보관은 재시도로 세지 않는다(retry·「재시도 범위」 그대로)
    nums, loose = failed_numbers([os.path.join(d, m) for m in moved])
    # 판정불가 보관이 앞서면 사본 번호 n이 회차(retry + 1)와 달라지므로 사본 경로를 함께 적는다
    copy = "tasks\\{}\\before.r{}".format(t.get("id", ""), n) if os.path.isdir(os.path.join(d, "before.r{}".format(n))) else "(사본 없음)"
    lines = [RETRY_SCOPE_LINE.format(
        retry + 1, ", ".join(moved), copy, ", ".join(str(x) for x in nums) if nums else "(번호 없음 — 아래 항목)")]
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
                    head, _, patch, changed = g.capture()
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


# ---------------------------------------------------------------- 치워 두기(설계 8.2절. git 동작은 retry_diff.py)

PARK_KEYS = ("parked", "repro_patch")
PARK_OPTIONS = ("--park", "--unpark", "--park-cancel", "--park-drop")
PARK_PENDING = "치우기가 끊긴 채임({} parked_pending: {}): task_set.py {} --park로 잇거나 --park-cancel로 취소한다"
PARK_BACKLOG = "치운 변경이 있어 백로그로 닫지 않는다({}): 표지가 끝남을 막는다. 사람 답으로 --park-drop --record 뒤 닫는다"
PARK_NO_FOLDER = "코드 폴더를 찾지 못함(flows\\{}\\flow.md dir)"
PATCH_STEMS = {"repro_patch": "repro", "parked": "parked"}


def park_key(t):
    """`--park`가 적을 표지 키. 치울 수 없는 task면 거부한다(통과하지 못하고 승인을 기다리는 task는 치우지 않는다, 설계 3절)."""
    kind, status = t.get("kind", ""), t.get("status", "")
    if not devflow_lib.version_at_least(t.get("started_version"), devflow_lib.RULES_V120):
        raise Reject("치워 두기는 1.2.0부터 시작한 task만(이 task: {})".format(t.get("started_version") or "판본 없음"))
    if kind in kinds.STAGE_KINDS:
        raise Reject("{}는 치우지 않는다(병합 중인 폴더는 그 kind의 순서를 따른다)".format(kind))
    if not board.writes(t):
        raise Reject("코드 폴더에 쓰는 task만 치운다({})".format(kind))
    if str(t.get("commit", "") or "").strip():
        raise Reject("이미 커밋한 task는 치우지 않는다(커밋 전의 변경만)")
    if status == "보류":
        return "parked"
    if kind in kinds.REPRO_PATCH_KINDS and status in ("자체검증", "승인대기"):
        ok, why = devflow_lib.judges_present(t)
        if not ok:
            raise Reject("판정을 통과하기 전에는 치우지 않는다: " + why)
        for name in kinds.JUDGE_FILES.values():
            p = os.path.join(t["_dir"], name)
            if os.path.isfile(p) and devflow_lib.item_count(
                    devflow_lib.sections(devflow_lib.read_text(p), level=2).get("통과 못 한 기준", "")):
                raise Reject("{}에 통과 못 한 기준이 있어 치우지 않는다".format(name))
        return "repro_patch"
    raise Reject("치우는 때가 아님: 보류된 코드 task와 판정을 통과한 원인 분석만(지금 {} {})".format(kind, status))


def same_flow_writers(tasks, t):
    flow = t.get("flow", "")
    return [o for o in tasks.values() if flow and o is not t and o.get("id") != t.get("id")
            and o.get("flow") == flow and board.writes(o) and slots.slot_of(o) == slots.slot_of(t)]


def busy_check(tasks, t):
    """같은 폴더에 쓰는 다른 task가 도는 동안에는 폴더의 변경을 뜨거나 되돌리거나 붙이지 않는다."""
    busy = [o["id"] for o in same_flow_writers(tasks, t) if o.get("status") in kinds.BUSY_STATUSES]
    if busy:
        raise Reject("같은 폴더에 쓰는 task가 도는 중: {} — 끝난 뒤 다시 부른다".format(", ".join(busy)))


def holds_folder(tasks, o):
    """시작했고 커밋 전이고 치운 표지와 `holds_nothing`이 없는 보류·승인대기(단계 kind는 폴더를 묶는 순서가 따로 있다),
    또는 그런 `완료` 재현 task(치우기가 거부되어 재현 시험을 폴더에 둔 것)로 아래 코드 task가 아직 시작하지 않은 것."""
    if not str(o.get("started", "") or "").strip() or str(o.get("commit", "") or "").strip() or devflow_lib.no_change(o) \
            or any(str(o.get(k, "") or "").strip() for k in PARK_KEYS + ("holds_nothing",)):
        return False
    if o.get("status") in ("보류", "승인대기"):
        return o.get("kind") not in kinds.STAGE_KINDS
    if o.get("status") == kinds.DONE and o.get("kind") in kinds.REPRO_PATCH_KINDS:
        return not any(c.get("kind") in kinds.AUTO_DEPEND_KINDS and str(c.get("started", "") or "").strip()
                       and any(a.get("id") == o.get("id") for a in ancestors(tasks, c)) for c in tasks.values())
    return False


def holder_check(tasks, t):
    """폴더의 변경을 쥐고 있을 수 있는 다른 task가 있으면 치우지 않는다. 치우면 그 변경이 이 패치로 쓸려 들어간다."""
    held = [o["id"] for o in same_flow_writers(tasks, t) if holds_folder(tasks, o)]
    if held:
        raise Reject("같은 폴더의 변경을 쥔 task가 있어 치우지 않음: {} — 폴더를 잡은 채 다음으로 간다".format(", ".join(held)))


def write_park_patch(t, key, data):
    """패치를 task 폴더에 쓰고 실행 폴더 기준 경로를 돌려준다. 앞 패치를 덮어쓰지 않는다(그것이 변경의 유일한 사본일 수 있다)."""
    stem, n = PATCH_STEMS[key], 1
    while True:
        name = "{}.patch".format(stem) if n == 1 else "{}.{}.patch".format(stem, n)
        path = os.path.join(t["_dir"], name)
        if not os.path.isfile(path):
            with open(path + ".tmp", "wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.replace(path + ".tmp", path)
            break
        with open(path, "rb") as f:
            if f.read() == data:
                break
        n += 1
    return "tasks/{}/{}".format(t["id"], name)


def park(run_dir, t, doc, tasks):
    """패치 쓰기 → `parked_pending` → 되돌리기 → 표지. 어디서 끊겨도 변경은 코드 폴더나 패치에 있고, 다시 부르면 잇는다.
    끊긴 치우기는 상태와 상관없이 잇는다(표지 키는 패치 이름으로 정한다)."""
    mark = (doc.get("parked_pending") or "").strip()
    if mark:
        stem = posixpath.basename(retry_diff.parse_mark(mark)[0]).split(".")[0]
        key = next(k for k, v in PATCH_STEMS.items() if v == stem)
    else:
        key = park_key(t)
        if (doc.get(key) or "").strip():
            print("이미 치움: {}".format(doc.get(key)))
            return
    folder = code_dir(run_dir, t)
    if not folder:
        raise Reject(PARK_NO_FOLDER.format(t.get("flow", "")))
    busy_check(tasks, t)
    if not mark:
        head, data, names = retry_diff.park_capture(folder)
        if not data:
            doc.set("holds_nothing", now_str())   # 쥔 변경이 없다. 다른 task의 치우기를 막지 않는다
            doc.save()
            print("치울 변경 없음")
            return
        holder_check(tasks, t)
        mark = retry_diff.park_mark(write_park_patch(t, key, data), head, names)
        doc.set("parked_pending", mark)
        doc.save()
    patch = retry_diff.parse_mark(mark)[0]
    retry_diff.revert_parked(folder, mark, os.path.join(run_dir, patch))
    doc.set(key, mark)
    doc.set("parked_pending", "")
    if doc.get("slot"):   # 칸이 비었다. 다시 시작하면 다시 연다(그사이 다른 task가 그 칸을 쓴다)
        doc.set("slot", "")
        doc.set("slot_base", "")
    doc.save()
    journal(run_dir, "치움", t["id"], patch)
    print("치움: {} {} → {}".format(t["id"], key, patch))


def park_cancel(run_dir, t, doc, tasks):
    """끊겼거나 멈춘 치우기를 취소해 변경을 폴더로 되돌린다. 남은 변경이 패치 안의 것뿐일 때만 하고, 패치는 task 폴더에 남긴다."""
    mark = (doc.get("parked_pending") or "").strip()
    if not mark:
        raise Reject("취소할 치우기가 없음(parked_pending이 빔)")
    folder = code_dir(run_dir, t)
    if not folder:
        raise Reject(PARK_NO_FOLDER.format(t.get("flow", "")))
    busy_check(tasks, t)
    patch = retry_diff.parse_mark(mark)[0]
    retry_diff.cancel_parked(folder, mark, os.path.join(run_dir, patch))
    doc.set("parked_pending", "")
    doc.save()
    journal(run_dir, "메모", t["id"], "치우기 취소: " + patch)
    print("치우기 취소: {} → 변경을 폴더로 되돌림".format(patch))


def ancestors(tasks, t):
    """부모를 따라 올라간 task들(가까운 쪽부터)."""
    seen, cur = {t.get("id")}, t
    while True:
        ref = str(cur.get("parent", "") or "").strip()
        if not ref or ref in seen or ref not in tasks:
            return
        seen.add(ref)
        cur = tasks[ref]
        yield cur


def park_owner(tasks, t):
    """(표지가 있는 task, 키) 또는 None. 자기 표지를 먼저 보고, 코드 task면 부모를 따라 올라가 재현 패치를 찾는다
    (원인 분석의 자식이 설계이면 그 아래 구현이 첫 코드 task다)."""
    for key in PARK_KEYS:
        if str(t.get(key, "") or "").strip():
            return t, key
    if t.get("kind") in kinds.AUTO_DEPEND_KINDS:
        for cur in ancestors(tasks, t):
            if str(cur.get("repro_patch", "") or "").strip():
                return cur, "repro_patch"
    return None


def unpark(run_dir, t, doc, tasks):
    """t의 코드 폴더에 치운 변경을 붙이고 표지를 비운다(자기 표지면 비우는 저장은 부른 쪽이 한다). 붙일 것이 없으면 False.
    `park_applying`을 먼저 적으므로, 붙인 뒤 표지를 비우기 전에 끊겨도 다음 부름이 붙은 뒤를 알아보고 다시 붙이지 않는다."""
    if t.get("kind") in kinds.AUTO_DEPEND_KINDS:
        for cur in ancestors(tasks, t):
            pending = str(cur.get("parked_pending", "") or "").strip()
            if pending:
                raise Reject(PARK_PENDING.format(cur["id"], pending, cur["id"]))
    found = park_owner(tasks, t)
    if not found:
        return False
    owner, key = found
    busy_check(tasks, t)
    own = owner.get("id") == t.get("id")
    owner_doc = doc if own else devflow_lib.Doc(owner["_path"])
    mark = str(owner.get(key, "")).strip()
    patch, head, _ = retry_diff.parse_mark(mark)
    full = os.path.join(run_dir, patch)
    folder = code_dir(run_dir, t)
    if not folder:
        raise Reject(PARK_NO_FOLDER.format(t.get("flow", "")) + ": 폴더를 만든 뒤 붙인다")
    if not os.path.isfile(full):
        raise Reject("패치가 없음: {}".format(patch))
    applying = (owner_doc.get("park_applying") or "").strip()

    def mark_applying(value):
        owner_doc.set("park_applying", value)
        owner_doc.save()

    state, paths = retry_diff.park_state(folder, mark, full, applying)
    if state == retry_diff.PARK_BEFORE:
        mark_applying(retry_diff.APPLYING)
        ok, err = retry_diff.apply_parked(folder, head, full)
        if ok:
            state = retry_diff.PARK_AFTER
        else:
            state, paths = retry_diff.park_state(folder, mark, full, retry_diff.APPLYING)
            if state == retry_diff.PARK_BEFORE:
                mark_applying("")
                raise Reject("패치 전체가 붙지 않음: {} ({}) — 상태를 그대로 두고 사람에게 묻는다(「치워 두기」)".format(patch, err))
    conflict_list = full + ".conflict"
    if state == retry_diff.PARK_CONFLICT:
        if applying != retry_diff.APPLY_CONFLICT:
            devflow_lib.write_text(conflict_list, "\n".join(paths) + "\n")
            mark_applying(retry_diff.APPLY_CONFLICT)
        raise Reject("붙이다 충돌: {} ({}) — 그 파일을 충돌 해결 경로로 풀고 `git add` 뒤 --unpark(「치워 두기」)".format(", ".join(paths), patch))
    if state == retry_diff.PARK_PARTIAL:
        raise Reject("{}: 폴더의 변경이 패치 파일의 일부뿐({}) — 붙이다 끊겼는지 사람에게 묻는다({}, 「치워 두기」)".format(state, ", ".join(paths), patch))
    if state != retry_diff.PARK_AFTER:
        raise Reject("{}: 폴더의 변경이 패치와 다름({}) — 붙이지 않고 사람에게 묻는다({})".format(state, ", ".join(paths), patch))
    if applying == retry_diff.APPLY_CONFLICT:
        solved = devflow_lib.read_text(conflict_list).splitlines() if os.path.isfile(conflict_list) else []
        left = retry_diff.markers_left(folder, solved)
        if left:
            raise Reject("충돌 표시가 남음: {} — 풀고 `git add` 뒤 --unpark(「치워 두기」)".format(", ".join(left)))
        lost = retry_diff.missing_new_files(folder, mark, full)
        if lost:
            print("! 패치의 새 파일이 폴더에 없음: {} (패치는 남는다: {})".format(", ".join(lost), patch))
        if os.path.isfile(conflict_list):
            os.remove(conflict_list)
    owner_doc.set(key, "")
    owner_doc.set("park_applying", "")
    if not own:
        owner_doc.save()
    journal(run_dir, "붙임", owner["id"], patch)
    print("붙임: {} {} → {}".format(owner["id"], patch, folder))
    return True


def park_drop(run_dir, t, doc, tasks, opts):
    """사람 답으로 표지만 뗀다. 패치와 코드 폴더는 그대로 둔다. 받는 코드 task의 id로 불러도 그 재현 패치의 표지를 뗀다."""
    rec = parse_record(opts["--record"]) if "--record" in opts else None
    if rec is None or not rec[2]:
        raise Reject("--park-drop은 원문이 있는 --record와 함께(사람 답으로만 표지를 뗀다)")
    names = PARK_KEYS + ("parked_pending", "park_applying")
    owner, owner_doc = t, doc
    if not any((doc.get(k) or "").strip() for k in names):
        found = park_owner(tasks, t)
        if not found:
            raise Reject("뗄 표지가 없음")
        owner, owner_doc = found[0], devflow_lib.Doc(found[0]["_path"])
    keys = [k for k in names if (owner_doc.get(k) or "").strip()]
    for k in keys:
        owner_doc.set(k, "")
    # 폴더가 깨끗해야 변경이 패치에만 있다. 충돌을 풀던 중이면 폴더의 변경을 그대로 쥔다
    folder = code_dir(run_dir, t)
    owner_doc.set("holds_nothing", "" if folder and retry_diff.status_entries(folder) else now_str())
    owner_doc.append_line("승인 기록", record_line(rec))
    owner_doc.save()
    journal(run_dir, "메모", owner["id"], "치움 표지 뗌: " + ", ".join(keys))
    print("표지 뗌: {} {}".format(owner["id"], ", ".join(keys)))


def cmd_parking(run_dir, t, doc, tasks, opts, kv):
    used = [o for o in PARK_OPTIONS if o in opts]
    if len(used) > 1 or kv or set(opts) - set(used) - {"--record"}:
        raise Reject("{}는 따로 부른다".format("·".join(PARK_OPTIONS)))
    if "--park" in opts:
        park(run_dir, t, doc, tasks)
    elif "--park-cancel" in opts:
        park_cancel(run_dir, t, doc, tasks)
    elif "--unpark" in opts:
        if (doc.get("parked_pending") or "").strip():
            raise Reject(PARK_PENDING.format(t["id"], doc.get("parked_pending"), t["id"]))
        if unpark(run_dir, t, doc, tasks):
            doc.save()
        else:
            print("붙일 치운 변경 없음")
    else:
        park_drop(run_dir, t, doc, tasks, opts)
    return 0


def amend_check(t, path, source, tasks):
    """판정 기준 정정을 받을 수 있는지만 본다(파일을 바꾸지 않는다)."""
    mark = str(t.get("judge_started", "") or "").strip()
    if mark:
        raise Reject(AMEND_MARKED.format(mark))   # 옛 task도 표지가 찍히면 거부한다. 표지가 찍히는 자체검증에서는 옛 규칙도 거부하므로 진행 단계에서 판정자를 띄우는 task(배포 실행의 확인 등)만 달라진다
    if devflow_lib.version_at_least(t.get("started_version"), devflow_lib.RULES_V110):
        if t.get("status") not in ("대기", "진행", "자체검증"):
            raise Reject(AMEND_STATUS_NEW)
    elif t.get("status") not in ("대기", "진행"):
        raise Reject(AMEND_STATUS_OLD)
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


def judge_start(t, doc, names, new_status=None):
    """판정자를 띄우기 전의 표지. 없던 이름만 덧붙이고 시각은 첫 값을 둔다.
    같은 호출의 --status가 있으면 전이 뒤 상태로 검사한다(전이 검사는 이미 통과했다)."""
    now = new_status or t.get("status")
    if now not in ("진행", "자체검증"):
        raise Reject((JUDGE_START_AFTER if now != t.get("status") else JUDGE_START_NOW).format(now))
    parts = (doc.get("judge_started") or "").split()
    stamp, have = (parts[:2], parts[2:]) if len(parts) >= 2 else (now_str().split(), [])
    added = [x for x in dict.fromkeys(names) if x not in have]
    doc.set("judge_started", " ".join(stamp + have + added))


def judge_clear(run_dir, t, doc):
    """판정 파일이 없을 때 표지를 비우고 journal에 남긴다. 표지가 이미 비었으면 False(파일 그대로)."""
    present = [n for n in ("judge.md", "judge-run.md") if os.path.isfile(os.path.join(t["_dir"], n))]
    if present:
        raise Reject(JUDGE_FILES_PRESENT.format(", ".join(present)))
    old = (doc.get("judge_started") or "").strip()
    if not old:
        return False
    doc.set("judge_started", "")
    journal(run_dir, "메모", t["id"], JUDGE_CLEARED.format(old))
    return True


def after_docs_transition(run_dir, tid, new, rec):
    """프로젝트 산출물 표지(설계 7.5절). 측정과 같이 전이보다 권위가 낮다. 못 찍은 문서는 넣을 때 `승인 없이 들어감`으로 보인다."""
    try:
        t = devflow_lib.load_task(os.path.join(run_dir, "tasks", tid, "task.md"))
        if new == "승인대기":
            project_docs.snapshot_asked(run_dir, t)
        elif new == kinds.DONE:
            project_docs.stamp_task(run_dir, t)
        elif t.get("kind") == "wrap-up" and devflow_lib.stage_of(t) == "실행" and rec and devflow_lib.approval_line(record_line(rec)) \
                and not delegation.is_delegated_line(record_line(rec)):   # 등록한 명령은 셸로 돈다. 사람이 본 답만 받는다
            for name in project_docs.register_proposed(run_dir, t):
                print("생성 명령을 등록함: " + name)
    except (OSError, UnicodeError, ValueError, shadow_check.ShadowError) as e:
        print("! 승인 해시 실패(전이는 유지): {}".format(e))


def code_dir(run_dir, t):
    flow = t.get("flow", "")
    p = os.path.join(run_dir, "flows", flow, "flow.md")
    if not flow or not os.path.isfile(p):
        return None
    meta_lines, _ = devflow_lib.split_front_matter(devflow_lib.read_text(p))
    d = slots.folder_of(devflow_lib.parse_meta(meta_lines).get("dir", ""), t)
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


def run_machine_check(run_dir, t, *extra):
    folder = code_dir(run_dir, t)
    if not folder:
        print("machine_check: 코드 폴더를 찾지 못함(flows\\{}\\flow.md dir) — 메인이 따로 돌린다".format(t.get("flow", "")))
        return None
    here = os.path.dirname(os.path.abspath(__file__))
    out = subprocess.run([sys.executable, os.path.join(here, "machine_check.py"), folder, t["_path"]] + list(extra),
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
        if len(f) >= 2 and (f[1] in ("알림", "점검 확인") or f[1].startswith(("되물음",) + devflow_lib.PARTIAL_POINTS)) \
                and f[1] != devflow_lib.REVIEW_OBJECTION:   # 이의는 그 답에서 고치는 task를 만든다
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


def cmd_returned(run_dir, t, doc, name):
    """에이전트 반환 직후(설계 A-R 문제 3). 그 에이전트의 결과 파일이 없으면 끝난 것이 아니므로 표지와 journal을 남긴다."""
    if not devflow_lib.version_at_least(t.get("started_version"), devflow_lib.RULES_V120):
        raise Reject("--returned는 1.2.0부터 시작한 task만(이 task: {})".format(t.get("started_version") or "판본 없음"))
    file_name = next((f for f, prefix in devflow_lib.JUDGE_PREFIX.items() if name.startswith(prefix)), "result.md")
    if str(t.get("running_agent", "") or "").strip() == name:
        doc.set("running_agent", "")
    if os.path.isfile(os.path.join(t["_dir"], file_name)):
        doc.set("returned_empty", "")
        doc.save()
        return 0
    doc.set("returned_empty", "{} {}".format(now_str(), name))
    doc.save()
    journal(run_dir, devflow_lib.EMPTY_RETURN, t["id"], name)
    print(devflow_lib.EMPTY_RETURN_LINE.format(t["id"], name))
    return 0


def other_open_runs(run_dir):
    """같은 작업 공간에서 `status: 진행`인 다른 실행 폴더 이름."""
    base, name = os.path.split(os.path.abspath(run_dir))
    out = []
    for other in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        run_md = os.path.join(base, other, "run.md")
        if other != name and os.path.isfile(run_md) and not os.path.isfile(os.path.join(base, other, "state.md"))                 and devflow_lib.run_meta(os.path.join(base, other)).get("status") == "진행":
            out.append(other)
    return out


def names_run(name, said, others):
    """사람 말이 이 실행을 가리키는가: 이름 전체가 맞아야 한다. 뒤에 조사가 붙는 것은 받고, 이 이름을 품은 다른 실행의 이름은 먼저 지운다."""
    for other in others:
        said = said.replace(other, " ") if name in other else said
    return bool(re.search(r"(?<![A-Za-z0-9_-])" + re.escape(name) + r"(?![A-Za-z0-9_-])", said))


def another_session_note(run_dir, session):
    """run.md의 세션과 지금 세션이 다르고 그 실행이 돌고 있는 표가 있으면 그 문장. 표는 머리 파일의 에이전트 이름과 파일의 수정 시각이다."""
    before = str(devflow_lib.run_meta(run_dir).get("session_id", "") or "").strip()
    if not before or before == session:
        return ""
    names = []
    for t in devflow_lib.load_tasks(run_dir).values():
        names += [str(t.get("running_agent", "") or "").strip()] if t.get("status") in kinds.BUSY_STATUSES else []
        names += str(t.get("judge_started", "") or "").split()[2:] if t.get("status") in kinds.BUSY_STATUSES else []
    names = [n for n in names if n]
    stamps = [os.path.getmtime(os.path.join(root, f)) for root, _dirs, files in os.walk(run_dir) for f in files]
    recent = max(stamps, default=0) > datetime.now().timestamp() - RESUME_QUIET_MIN * 60
    if not names and not recent:
        return ""
    last = datetime.fromtimestamp(max(stamps)).strftime("%Y-%m-%d %H:%M:%S") if stamps else "없음"
    return "다른 세션({})이 이 실행을 돌리고 있을 수 있음: 에이전트 {}, 마지막 기록 {}".format(before[:8], ", ".join(names) or "없음", last)


def cmd_resume(run_dir, opts):
    """재개의 맨 앞(설계 A-R 문제 4). 진행 중 실행이 여럿인데 사람 말이 대상을 가리지 못할 때만 아무것도 쓰지 않고 거부한다.
    다른 세션의 흔적은 경고 한 줄이다. `/clear`로 세션 값이 바뀐 것과 가릴 수 없어서 묻지 않는다."""
    session, said = str(opts.get("--session", "") or "").strip(), str(opts.get("--said", "") or "")
    name = os.path.basename(os.path.abspath(run_dir))
    if devflow_lib.run_from_v120(run_dir):
        others = other_open_runs(run_dir)
        if others and not names_run(name, said, others):
            print("거부: 진행 중인 실행이 여럿이고 사람 말이 이 실행을 가리키지 않음: {} — 어느 실행인지 폴더 이름으로 묻고, 그 답을 --said로 다시 부른다".format(
                ", ".join([name] + others)))
            return 3
        note = another_session_note(run_dir, session)
        if note:
            print("! " + note)
    doc = devflow_lib.Doc(os.path.join(run_dir, "run.md"))
    doc.set("session_id", session)
    doc.save()
    with open(os.path.join(run_dir, "journal.md"), "a", encoding="utf-8") as f:
        f.write("- {} | 재개 | - | 시작\n".format(now_str()))
    return 0


def cmd_new(run_dir, args, kv):
    import spawn_children

    def opt(name, default=""):
        return args[args.index(name) + 1] if name in args else default
    place_key = opt("--place")
    place_body = None
    if place_key:
        if not opt("--from-answer"):
            print("--place는 --from-answer와 함께")
            return 2
        made = next((o["id"] for o in devflow_lib.load_tasks(run_dir).values()
                     if str(o.get("origin", "")).endswith("{} {}".format(devflow_lib.CODE_CHECK_ORIGIN, place_key))), None)
        if made:
            print("이미 있음: 이 곳의 수정 task")   # 끊긴 뒤 다시 돌려도 수정이 둘이 되지 않는다
            print(made)
            return 0
        place_body = places.fix_body(run_dir, opt("--from-answer"), place_key)
        if isinstance(place_body, str):
            print("거부: " + place_body)
            return 3
        args = args + ["--title", place_body[1], "--flow", place_body[2], "--parent", opt("--from-answer")]
    kind, title, body_from = opt("--kind"), opt("--title"), opt("--body-from")
    answer = opt("--from-answer")
    owned = sorted({k for k, _ in kv} & (kinds.SCRIPT_KEYS | {"kind", "id", "status", "title"}))
    if owned:
        # 키=값이 --from-answer가 정한 origin·kind를 덮으면 알림 불가·세대가 꺼진다
        print("거부: {}는 new의 키=값으로 받지 않는다(--kind·--title·--origin·--from-answer를 쓴다)".format(", ".join(owned)))
        return 3
    if not (kind or answer) or not title or not (body_from or place_key):
        print("new에는 --kind(또는 --from-answer), --title, --body-from이 필요")
        return 2
    if kind and kind not in kinds.KINDS:
        print("모르는 kind: " + kind)
        return 3
    tasks = devflow_lib.load_tasks(run_dir)
    body = place_body[0] if place_key else devflow_lib.sections(devflow_lib.read_text(body_from), level=2)
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
        stamp = places.answer_record(tasks, answer, place_key)[0] if place_key else answer_time(tasks[answer])
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
        origin = "사용자 {} {}".format(answer, stamp) + (" {} {}".format(devflow_lib.CODE_CHECK_ORIGIN, place_key) if place_key else "") \
            + (" — " + origin if origin else "")
        moved_answer = kind == "fix" or devflow_lib.is_design_revision({"kind": kind, "_sections": body})
        if moved_answer and devflow_lib.version_at_least(devflow_lib.harness_version(), devflow_lib.RULES_V120):
            # 알림으로 지나가므로 판정이 그 옮김을 본다(설계 5.3절 2, 7.2절). 판정자가 다른 task 폴더를 읽지 않아도 되게 원문을 옮겨 적는다
            quoted = [re.search(r'"([^"]+)"', l).group(1) for l in devflow_lib.record_lines(tasks[answer])
                      if l[2:].startswith(stamp) and re.search(r'"[^"]+"', l) and place_key in l]
            sentence = '{}: "{}"'.format(devflow_lib.ANSWER_CRITERION, " ".join((quoted or [""])[-1].split()))
            body["판정 기준"] = body["판정 기준"].rstrip() + "\n" + devflow_lib.next_criterion(body["판정 기준"], sentence) + "\n"
    source = devflow_lib.JUDGE_ORIGIN.match(origin or "")
    if kind == "change" and source and source.group(1) in tasks \
            and devflow_lib.version_at_least(devflow_lib.harness_version(), devflow_lib.RULES_V120):
        # 뜻이 그대로인 정정도 알림으로 지나가므로 판정이 그 옮김을 본다(설계 5.3절 4). 정본이 같은 대안 문장만 잇는다
        judge = os.path.join(tasks[source.group(1)]["_dir"], "judge.md")
        paths = devflow_lib.change_paths({"_sections": body})
        lines = devflow_lib.unchanged_corrections(devflow_lib.read_text(judge), paths) if paths and os.path.isfile(judge) else []
        if lines:
            sentence = "{}: {}".format(devflow_lib.CORRECTION_CRITERION, " / ".join(l[2:].strip() for l in lines))
            body["판정 기준"] = body["판정 기준"].rstrip() + "\n" + devflow_lib.next_criterion(body["판정 기준"], sentence) + "\n"
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
                        "--from-answer", "--judge-start", "--reuse-answer", "--message", "--card-open", "--place", "--returned", "--session", "--said"}
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
    if args[0] == "resume":
        return cmd_resume(run_dir, opts)
    if args[0] == "new":
        return cmd_new(run_dir, args, kv)
    judge_names = [x.strip() for x in str(opts.get("--judge-start", "")).split(",") if x.strip()]
    if "--judge-start" in opts and not judge_names:
        print("--judge-start에는 판정자 이름(쉼표로 여럿)이 필요")
        return 2

    tid = args[0]
    tasks = devflow_lib.load_tasks(run_dir)
    if tid not in tasks:
        print("task를 찾지 못함: " + tid)
        return 2
    t = tasks[tid]
    if "--identity" in opts:
        print("\n".join(identity_lines(run_dir, t)))
        return 0
    try:
        doc = devflow_lib.Doc(t["_path"])
        if "--returned" in opts:
            return cmd_returned(run_dir, t, doc, opts["--returned"])
        if any(o in opts for o in PARK_OPTIONS):
            return cmd_parking(run_dir, t, doc, tasks, opts, kv)
        rec = parse_record(opts["--record"]) if "--record" in opts else None
        if rec:
            delegation.clear_pending(run_dir)   # 어떤 답이든 받으면 그 뒤의 답은 위임 확인의 답이 아니다
        if rec and rec[0].startswith(devflow_lib.PARTIAL_POINTS) and not rec[2]:
            raise Reject("지점 `{}`의 답에는 사람의 원문이 있어야 한다".format(rec[0]))
        if "--message" in opts and (rec is None or not rec[2]):
            raise Reject("--message는 원문이 있는 --record와 함께")
        kv = [("stage" if k == "deploy_stage" else k, v) for k, v in kv]   # 옛 키 이름도 stage로 받는다
        ctx = {"record": rec, "reason": opts.get("--reason"), "archived": False,
               "snapshot": bool(opts.get("--screen-snapshot")), "old_stage": devflow_lib.stage_of(t)}
        old = str(t.get("status", "")).strip()
        new = opts.get("--status", old)

        owned = sorted({k for k, _ in kv} & kinds.SCRIPT_KEYS)
        if owned:
            # 스크립트가 채우는 키를 손으로 바꾸면 기록 점검·stage 강제를 끌 수 있다
            raise Reject(SCRIPT_OWNED.format(", ".join(owned)))
        optioned = sorted({k for k, _ in kv} & kinds.OPTION_KEYS)
        if optioned:
            # 상태·재시도·kind를 키=값으로 바꾸면 전이 검사·재시도 상한을 넘긴다
            raise Reject(OPTION_ONLY.format(", ".join(optioned)))
        if slots.slot_of(t) and any(k == "commit" for k, _ in kv):
            # commit에는 흐름 브랜치에 들어간 해시만 적는다(설계 8.3절). 칸의 커밋을 적으면 수집과 shadow가 없는 해시를 본다
            raise Reject("칸에서 돈 task의 commit은 slots.py가 적는다: --pending {칸 커밋} 뒤 --insert")
        selfchecked = sorted({k for k, _ in kv} & kinds.SELFCHECK_KEYS)
        if selfchecked and not (old == "진행" and opts.get("--status") == "자체검증"):
            # 이미 자체검증인 task에 주면 기계 조건 값을 덮어 읽기 판정을 건너뛴다
            raise Reject(SELFCHECK_ONLY.format(", ".join(selfchecked)))
        if devflow_lib.needs_judgment_record(t) and str(t.get("commit", "") or "").strip() \
                and any(k == "commit" and not devflow_lib.parse_value(k, v) for k, v in kv):
            # 비우고 no_change를 적으면 코드가 있던 task가 메인의 말로 풀린다. 재시도와 치우기는 커밋을 비우지 않는다
            raise Reject("값이 있는 commit을 비우지 않는다. 커밋이 틀렸으면 맞는 값으로 고치고, 맞는 값을 찾지 못하면 `screen.py … --places --remeasure` 뒤에 사람에게 묻는다")
        for k, v in kv:           # 같은 호출의 값(stage=끝, commit=…)을 전이 검사에 쓴다
            if k == "stage" and t.get("kind") in kinds.STAGE_KINDS and v and v not in kinds.stages_of(t.get("kind")) \
                    and (v not in kinds.OLD_STAGES.get(t.get("kind"), ())
                         or devflow_lib.version_at_least(t.get("started_version"), devflow_lib.RULES_V120)):
                raise Reject("{}의 stage는 {}".format(t.get("kind"), "/".join(kinds.stages_of(t.get("kind")))))
            t[k] = devflow_lib.parse_value(k, v)
        if any(k == "no_change" for k, _ in kv) and devflow_lib.needs_judgment_record(t) and devflow_lib.no_change(t) and str(t.get("commit", "") or "").strip():
            raise Reject("커밋이 있는 task에 no_change를 적지 않는다(코드가 있다). 커밋이 틀렸으면 commit=을 고치고 `screen.py … --places --remeasure`로 다시 잰다")
        if "--amend-criteria" in opts and opts.get("--archive-judge"):
            raise Reject("--amend-criteria와 --archive-judge는 따로 부른다")
        # 탐침의 기록 단계: 계획 판정(judge.md)을 judge.plan.md로 옮겨 기록 단계의 판정으로 세지 않게 한다(설계 A-17)
        plan_move = t.get("kind") == "probe" and ("stage", "기록") in kv
        if plan_move and os.path.isfile(os.path.join(t["_dir"], "judge.plan.md")):
            raise Reject("judge.plan.md가 이미 있음(계획 판정을 이미 옮김) — 탐침의 stage=기록은 한 번만")
        marks = [o for o in ("--undecided", "--judge-start", "--judge-clear") if o in opts]
        if "--amend-criteria" in opts and marks:
            raise Reject("--amend-criteria와 {}는 따로 부른다".format("·".join(marks)))
        if opts.get("--undecided") and not opts.get("--archive-judge"):
            raise Reject("--undecided는 --archive-judge와 함께")
        if opts.get("--archive-judge") and ("--judge-start" in opts or "--judge-clear" in opts):
            raise Reject("--archive-judge는 표지를 비운다. --judge-start·--judge-clear는 따로 부른다")
        filled_tip = ""
        if t.get("kind") == "wrap-up" and new == kinds.DONE and not str(t.get("exported_commit", "") or "").strip():
            # 사용자가 직접 넣은 마무리: 넣는 브랜치의 끝이 개발 기준 브랜치에 들어 있으면 그 끝(배포 계획이 읽는다).
            # 완료 관문(최종 CI 대조)이 이 값을 보므로 관문 앞에서 채운다. 쓰기는 검사를 모두 마친 뒤
            import exec as execmod
            filled_tip = execmod.target_tip(run_dir, t)
            if filled_tip:
                t["exported_commit"] = filled_tip
        # 검사를 모두 마친 뒤에 파일을 바꾼다(거부되면 아무것도 바꾸지 않는다)
        why = check_transition(run_dir, t, old, new, dict(ctx, archived=bool(opts.get("--archive-judge"))))
        if why and not (opts.get("--unlisted") and isinstance(why, Unlisted)):
            raise Reject(why + UNLISTED_ONLY if opts.get("--unlisted") else why)
        if "--reuse-answer" in opts and rec is None:
            raise Reject("--reuse-answer는 --record와 함께")
        if rec and rec[0] == devflow_lib.HANDED_POINT and "--status" in opts:
            raise Reject("넘김 답은 상태를 바꾸지 않는다: `--status` 없이 적고 화면의 승인은 따로 묻는다")
        refused = delegation_check(run_dir, tasks, t, rec) if rec else None
        if refused:
            raise Reject(refused)
        reused = reuse_check(tasks, t, rec, now_str()) if rec else None
        if reused and "--reuse-answer" not in opts:
            raise Reject("같은 원문 재사용: {} {}의 승인 줄과 원문이 같다 — 이 승인 요청 뒤에 받은 답이 아니면 답을 새로 받고, "
                         "앞 답을 다시 쓰는 것이 맞으면 --reuse-answer \"{{이유}}\"(그 답으로는 명령 지점을 얼리지 않는다)"
                         .format(*reused))
        # 코드 확인: 카드를 여는 것과 곳 답의 꼴은 쓰기 전에 본다
        card_key = opts.get("--card-open")
        if card_key:
            card_check(run_dir, tid, new, card_key)
        place_key = place_answer_key(rec)
        if place_key:
            place_answer_check(run_dir, tid, new, place_key, rec[1])
        gap_task = unmeasured_answer_task(rec)
        if gap_task:
            if new != "승인대기":
                raise Reject("재지 못한 task의 답은 승인대기에서만(지금 {})".format(new))
            problem = places.unmeasured_answer_problem(run_dir, t, gap_task, rec[1], rec[2])
            if problem:
                raise Reject(problem)
            stamped = devflow_lib.UNMEASURED_POINT + gap_task + "@" + devflow_lib.commit_mark(tasks[gap_task])
            if "@" in rec[0] and rec[0] != stamped:
                raise Reject("답의 커밋이 지금 커밋과 다르다: {} (지금 {})".format(rec[0], stamped))
            rec = (stamped, rec[1], rec[2])   # 답은 받을 때의 코드에 묶인다
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
        undecided = bool(opts.get("--undecided"))
        if opts.get("--archive-judge"):
            archive_check(run_dir, t, undecided)
        if "--amend-criteria" in opts:
            amend_check(t, opts["--amend-criteria"], opts.get("--source") or "", tasks)
        if new in ("진행", "승인대기", kinds.DONE, "백로그") and new != old and str(t.get("parked_pending", "") or "").strip():
            raise Reject(PARK_PENDING.format(tid, t.get("parked_pending"), tid))
        if new == "백로그" and new != old and str(t.get("parked", "") or "").strip():
            raise Reject(PARK_BACKLOG.format(retry_diff.parse_mark(t.get("parked"))[0]))
        if new == "진행" and new != old:
            if slots.slot_of(t) and not board.in_slot(t):
                doc.set("slot", "")   # 칸 수를 1로 되돌린 뒤 다시 시작한다. 코드 폴더를 찾기 전에 뗀다
                doc.set("slot_base", "")
                t["slot"] = ""
            if board.in_slot(t) and not slots.slot_of(t):
                raise Reject("칸을 쓰는 실행이다: `slots.py {{실행 폴더}} {} --open {{칸}}`으로 칸을 먼저 연다(board.py --ready의 [칸 n])".format(tid))
            if slots.slot_taken(tasks, t):
                raise Reject("칸 {}을 {}가 차지함: `slots.py {{실행 폴더}} {} --open {{칸}}`으로 다른 칸을 연다".format(
                    slots.slot_of(t), ", ".join(slots.slot_taken(tasks, t)), tid))
            if board.writes(t):
                for cut in board.park_cut(tasks, t):
                    raise Reject(PARK_PENDING.format(cut["id"], cut.get("parked_pending"), cut["id"]))
                conflict = board.park_conflict(tasks, code_dir(run_dir, t))
                if conflict:
                    raise Reject("폴더에 치운 변경의 충돌이 남음: {} — 풀고 `git add` 뒤 --unpark(「치워 두기」)".format(", ".join(conflict)))
            # 맨 앞의 쓰기. 붙지 않으면 거부하므로 상태는 그대로다(설계 8.2절 「다시 붙일 때」)
            unpark(run_dir, t, doc, tasks)
            if doc.get("holds_nothing"):
                doc.set("holds_nothing", "")   # 다시 작업하면 쥘 수 있다
        # 여기부터 쓰기(표지 둘은 거부할 수 있어 맨 앞에. --amend-criteria·--archive-judge와는 함께 오지 않는다)
        if judge_names:
            judge_start(t, doc, judge_names, new)
            print("judge_started: " + doc.get("judge_started"))
        if opts.get("--judge-clear") and not judge_clear(run_dir, t, doc):
            print(NO_MARK)
        if plan_move and os.path.isfile(os.path.join(t["_dir"], "judge.md")):
            os.replace(os.path.join(t["_dir"], "judge.md"), os.path.join(t["_dir"], "judge.plan.md"))
            print("judge.md → judge.plan.md(계획 판정을 옮김. 기록 단계의 읽기 판정이 judge.md를 새로 쓴다)")
            old_mark = (doc.get("judge_started") or "").strip()
            if old_mark:
                doc.set("judge_started", "")   # 계획 판정의 판정자는 끝났다. 기록 단계의 판정자를 띄울 때 다시 찍는다
                journal(run_dir, "메모", t["id"], JUDGE_CLEARED.format(old_mark))
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
            moved, snap = archive_judge(run_dir, t, doc, undecided)
            print("보관: " + ", ".join(moved) + (" (판정불가 보관: retry·「재시도 범위」 그대로)" if undecided else ""))
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
                if devflow_lib.needs_judgment_record(dict(t, started_version=doc.get("started_version"))):
                    try:
                        devflow_lib.copy_canon_sections(run_dir, t["_dir"], doc.section("정본의 절"))
                    except OSError as e:
                        print("! 설계 사본을 뜨지 못함: {} (판정자는 [설계:] 줄을 지금 정본으로 대조하고 그 사실을 적는다)".format(e))
                if t.get("kind") in kinds.AUTO_DEPEND_KINDS and devflow_lib.ensure_flow_md(run_dir, t.get("flow", "")):
                    # [백로그]·[안 …] 행이 새 흐름을 시작하면 행을 만들 때 flow.md가 없다. 메인이 손으로 쓰지 않게
                    # 시작 때 run.md round로 만든다(메인은 폴더를 만들 때 키만 고친다)
                    print("flow.md 만듦: flows/{}/flow.md(폴더 없음, round {})".format(t.get("flow"), devflow_lib.run_round(run_dir)))
                for problem in devflow_lib.agent_def_problems():
                    print("! 에이전트 정의: {} — 이 task의 판정 뒤 전이가 거부될 수 있다(SKILL.md 0절 1)".format(problem))
            if new == "자체검증" and t.get("kind") in kinds.AUTO_DEPEND_KINDS:
                measured = devflow_lib.needs_judgment_record(t)
                if measured:
                    devflow_lib.clear_test_changes(t)
                if not any(k == "machine_check" for k, _ in kv):
                    rc = run_machine_check(run_dir, t)
                    if rc is not None:
                        doc.set("machine_check", rc)
                elif measured:   # 값은 기계 조건의 결과만 덮는다. 시험 변화는 그래도 잰다
                    run_machine_check(run_dir, t, "--measure-only")
            if new == "승인대기":
                doc.set("approval_requested", stamp)
            if new == kinds.DONE:
                doc.set("approved", stamp)
                if t.get("kind") == "flow-verify" and devflow_lib.version_at_least(t.get("started_version"), devflow_lib.RULES_V120):
                    import exec as execmod
                    doc.set("reviewed_tip", execmod.flow_tip(run_dir, t))   # 합치기가 그 뒤의 커밋을 대조한다
                if rec and rec[0] in ("알림", "승인"):
                    doc.set("approval_mode", rec[0])
                if old == "백로그":
                    doc.set("done_via", "백로그")
            if new in (kinds.DONE, "보류", "백로그"):
                doc.set("waiting_user", "")
            if old == "승인대기" and doc.get("card_open"):
                doc.set("card_open", "")   # 승인대기를 떠나면 그 카드를 기다리지 않는다
            if opts.get("--reason"):
                journal(run_dir, "메모", tid, "{}→{}: {}".format(old, new, opts["--reason"]))
            if why and opts.get("--unlisted"):
                doc.append_line("표 밖 전이", "- {} | {}→{} | {}".format(stamp, old, new, opts["--unlisted"]),
                                before=["승인 기록"])
                journal(run_dir, "표 밖 전이", tid, "{}→{}: {} (거부 이유: {})".format(old, new, opts["--unlisted"], why))
        for k, v in kv:
            doc.set(k, v)
            if k == "running_agent" and v and doc.get("returned_empty"):
                doc.set("returned_empty", "")
                journal(run_dir, devflow_lib.EMPTY_RESUMED, tid, v)
        if (new != old and new in devflow_lib.HELD_STATUSES) or any(k == "no_change" and devflow_lib.parse_value(k, v) for k, v in kv):
            slots.fix_closed(run_dir, tid)
        if filled_tip:
            doc.set("exported_commit", filled_tip)
            print("exported_commit={}(넣는 브랜치의 끝, 개발 기준 브랜치에 들어 있음)".format(filled_tip))
        for k in [x.strip() for x in str(opts.get("--now", "")).split(",") if x.strip()]:
            doc.set(k, stamp)
        if card_key:
            doc.set("card_open", card_key)
        if rec:
            message = opts.get("--message")
            # 한 메시지에 여러 task의 답이 있을 때 그 전체(설계 8.1절). 맨 끝 칸이고 record_core가 떼므로 판별의 재료가 되지 않는다
            tail = devflow_lib.RECORD_MESSAGE + " ".join(message.replace('"', "'").split()) + '"' if message else ""
            if reused:
                why_reuse = opts["--reuse-answer"]
                doc.append_line("승인 기록", record_line(rec) + " | 재사용 답: " + why_reuse + tail)
                doc.append_line("표 밖 전이", "- {} | 재사용 답 | {} (같은 원문: {} {})".format(stamp, why_reuse, *reused),
                                before=["승인 기록"])
                journal(run_dir, "재사용 답", tid, "{} (같은 원문: {} {})".format(why_reuse, *reused))
            else:
                doc.append_line("승인 기록", record_line(rec) + tail)
            if place_key and str(doc.get("card_open") or "").strip() == place_key:
                doc.set("card_open", "")
            asked_at = str(t.get("asked_at", "") or "").strip()
            if asked_at and rec[0] not in ("알림", "점검 확인") and not place_key and not gap_task:   # 사람이 답하기 전에 메인이 적는 줄은 답이 아니다
                try:
                    note = stall_note(run_dir, tid, asked_at)
                    if note:
                        journal(run_dir, "메모", tid, note)
                except OSError as e:
                    # 측정은 답 기록보다 권위가 낮다. 실패해도 답은 남긴다.
                    print("! 멈춤 측정 실패(답 기록은 유지): {}".format(e))
                doc.set("asked_at", "")
            if rec[0] == "점검 확인" and rec[1].split()[:1] == ["R2"]:
                # 확인한 「판정 기준」을 남긴다. 그 뒤 또 바뀌면 R2가 다시 걸린다
                devflow_lib.write_text(os.path.join(t["_dir"], "criteria.ack.md"), (doc.section("판정 기준") or "") + "\n")
        doc.save()
        if place_key:
            print(places.next_card_line(places.apply_answer(run_dir, tid, place_key, rec[1])))
        if new != old:
            if old == "대기" and new == "진행":
                t["started_version"], t["rules"] = doc.get("started_version"), doc.get("rules")
            auto_freeze(run_dir, t, old, new, rec, ctx["old_stage"])
            after_docs_transition(run_dir, tid, new, rec)
            deploy_reuse.after_transition(run_dir, t, old, new)
            try:
                observed = shadow_check.observe_transition(run_dir, t, old, new)
                if observed:
                    print(observed)
            except Exception as e:
                # shadow 관측은 기존 gate보다 권위가 낮다. 기록 실패는 비교 제외 경고일 뿐 전이를 되돌리지 않는다.
                print("! shadow 관측 기록 실패(기존 전이는 유지): {}".format(e))
    except Reject as e:
        print("거부: {} — {} (머리 파일은 그대로)".format(tid, e))
        return 3
    except retry_diff.GitError as e:
        print("거부: {} — {} (치운 변경은 패치나 코드 폴더에 있다)".format(tid, e))
        return 3
    print("{}: {}{}".format(tid, old, "→" + new if new != old else " (상태 그대로)"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
