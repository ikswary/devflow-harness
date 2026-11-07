"""위임의 층과 성질의 기계 끌어내기(설계 9절, 5.2절). 1.2.0부터 시작한 task에만 쓴다.

- `read_levels`: 위임 원문을 층으로 옮긴다. 읽지 못하면 맡긴 것으로 보지 않고 되묻는다. 좁은 쪽으로 틀린다.
- 대기 파일: 층을 넓히는 말은 읽은 범위를 사람에게 보이고 확인받은 뒤에 행을 쓴다. 줄이는 말은 바로 쓴다.
- `item_derived`, `task_derived`: 결정 줄과 task에서 성질을 끌어낸다. 올리는 쪽으로만 틀린다.
- `command_level`: 명령 줄의 층. 어느 명령이 운영인지는 프로젝트 설정 `운영 표지`로 가른다. 표지가 비면 밖으로 나가는 명령을 운영으로 본다.
- `gate`: 이 화면을 위임으로 닫을 수 있는지와 기다리는 이유. `screen.py`가 칸을 주고, `task_set.py`가 `승인|위임 …` 답을 이 값으로 거른다.
"""
import os
import re
from datetime import datetime

import devflow_lib
import kinds

WAITING_PROPERTIES = ("범위", "비용", "위험")   # 위임으로도 닫지 않는다(설계 9절). `밖`은 명령의 층이 맡는다
QUESTION_PROPERTIES = {"1": {"밖"}, "3": {"비용"}, "4": {"범위"}, "5": {"범위"}}   # 설계 5.2절. 2와 6은 성질이 아니다
INFRA_PROPERTIES = {"비용", "밖"}
SPEC_PREFIX = "spec/"
FACT_MARK = "[사실]"
LAST_CHECK_STAGE = "직전확인"
FOUR_CELLS = ("정해 주실 것", "하실 일·허용 요청", "알릴 것", "확인 안 된 것")
SCRIPT_ITEMS = ("[기록 점검]", "[판정 기준 정정]", "[기준선 질문]")   # 스크립트가 더한 질문은 사람의 일이다

QUESTION_NUMBERS = re.compile(r"질문\s*([1-6](?:\s*[·,/]\s*[1-6])*)(?!\s*[~\d])")
BRACKET_NUMBERS = re.compile(r"\[Q[1-6](?:\s*[·,/]\s*Q?[1-6])*\]")
ACCEPT_CHOICE = re.compile(r"위험\s*수용|위험을?\s*받아들|받아들임|백로그로\s*미루|되돌릴\s*수\s*없")
SECURITY_MARK = "[보안]"
SECURITY_WORDS = re.compile(r"권한|인증|개인정보|비밀값")
RECOMMENDED = re.compile(r"추천안?\s*[(（]?[가-힣]?[)）]?\s*[:：]\s*\S|[(（](?:추천|Recommended)[)）]")
NO_RECOMMENDATION = re.compile(r"추천안?\s*(?:없|하지|못|불가|할\s*근거)|추천\s+안\s|추천안?\s*[:：]\s*(?:없|해당)")
CHOICE = re.compile(r"[(（][가-힣][)）]")

# 층 읽기는 허용 목록이다. 절마다 전체가 아래 꼴 가운데 하나여야 하고, 어느 꼴도 아니면 층을 주지 않고 되묻는다(부정어를 찾지 않는다)
#   맡김: {대상과 조사}* + 맡기는 끝말 / 뺌: {대상과 조사}+ + 빼는 끝말 / 취소: {위임의 말} + 취소하는 끝말
TOKEN = r"l[1-4](?:\s*[~\-–—～〜]\s*l?[1-4])?"
TARGETS = (("L4", r"운영\s*배포|운영\s*환경|운영|prod\s*배포|production|prod|main"),
           ("L3", r"dev\s*배포|dev\s*환경|dev|개발\s*환경|개발\s*서버|배포|push|푸시"),
           ("L2", r"로컬|커밋|합치기|병합|머지|merge|통합|내보내기"),
           ("L1", r"결정|추천대로|추천|선택지"))
AUTO_TOKEN = "⟦자동⟧"
ITEM = re.compile(r"(?:(?P<token>" + TOKEN + r")|" + "|".join("(?P<{}>{})".format(l, w) for l, w in TARGETS)
                  + r"|(?P<all>전부|모두|전체)|(?P<rest>이번\s*실행의?|나머지|남은\s*승인|남은\s*것|이후)|(?P<alone>알아서)|(?P<auto>" + AUTO_TOKEN + r"))(?![a-z0-9])"
                  + r"\s*(?P<part>(?:까지만|까지|은|는|을|를|도|만|으로|로|이랑|랑|하고|과|와|및|포함해서|포함하고|포함)*)[\s·]*")
HAND_END = re.compile(r"맡(?:아(?:\s*(?:줘|주세요|요|도\s*돼|도\s*됩니다))?|겨(?:\s*(?:줘|주세요))?|길게요?|깁니다)|위임(?:\s*(?:할게요?|합니다|해|해\s*줘))?")
AUTO_END = re.compile(r"자동\s*승인(?:\s*(?:해|해\s*줘|해\s*주세요|합니다|할게요?|으로(?:\s*해)?|부탁(?:해요?|합니다|드립니다)))?|자동으로(?:\s*(?:해|해\s*줘|진행해?|승인))?|자동")
GO_END = re.compile(r"진행(?:해요?|해\s*줘|해\s*주세요|합니다|하세요)?|해(?:\s*줘|요|\s*주세요)?|돌려(?:\s*줘)?")
PICK_END = re.compile(r"정해(?:\s*줘|요)?|골라(?:\s*줘)?")
TAKE_END = re.compile(r"(?:맡기지|하지)\s*(?:마(?:세요)?|말고|말아(?:\s*줘)?|말\s*것)|빼고|빼(?:\s*줘)?|제외(?:하고|해(?:\s*줘)?)?|말고|안\s*(?:돼|됨|해|함|할게)|안돼|안해|못\s*해|금지|보류|아직|나중에"
                      r"|(?:이번\s*)?범위\s*밖|(?:내가|제가)\s*(?:직접\s*)?(?:할게요?|합니다|볼게요?|정할게요?)|직접\s*할게요?|물어\s*봐(?:요|\s*주세요)?|묻고|안\s*맡겨요?")
CANCEL = re.compile(r"(?:자동\s*승인|자동|위임|알아서)(?:은|는|을|를)?\s*(?:하지\s*(?:마(?:세요)?|말아(?:\s*줘)?)|말고|안\s*(?:해|함|돼|됨|할게)|안해|안함|안돼|못\s*해|못해"
                    r"|아니(?:야|에요|다)?|아님|그만(?:\s*해)?|해제(?:\s*해\s*줘|해)?|철회(?:해)?|풀어(?:\s*줘)?|꺼(?:\s*줘|요)?|끄고|끝(?:내)?|멈춰|취소(?:해)?|중단(?:해)?|필요\s*없어요?|금지)"
                    r"|맡기지\s*(?:마(?:세요)?|말아(?:\s*줘)?)|안\s*맡겨요?|(?:하나씩\s*|직접\s*|그대로\s*|계속\s*)?물어\s*봐(?:요|\s*주세요)?")
FILLER = re.compile(r"^(?:ㅇㅋ|ㅇㅇ|오케이|ok|okay|네|넵|예|응|그래|좋아|좋습니다|이제)[\s,.]+")
CORRECTION = re.compile(r"^(?:아니[요오다]?|아냐|아\s*잠깐|잠깐|정정)[\s,]*")
LEAD_AUTO = re.compile(r"승인\s*없이|확인\s*없이|(?:묻|물어\s*보)지\s*(?:말고|마(?:세요)?)")
AFTER_ALL = re.compile(r"이후\s*전체(?:\s*자동)?")
CLAUSE = re.compile(r"[,，.。;；\n]+|(?<=말고)\s+|(?<=빼고)\s+|(?<=제외하고)\s+|\s그리고\s")
LEVEL_TOKEN = re.compile(r"(?<![a-z0-9])l([1-4])(?:\s*[~\-–—～〜]\s*l?([1-4]))?")
ORDER = ("L1", "L2", "L3", "L4")
COMMANDS = ("L2", "L3", "L4")
ASK_AGAIN = "어디까지 맡기시는지 읽지 못했습니다"
PROD_WORD = re.compile(r"운영|(?<![a-z0-9_])(?:prod|production|prd|live)(?![a-z0-9_])")
DELEGATION_WORDS = re.compile(devflow_lib.DELEGATED_ANSWER.pattern + r"|자동으로|위임|(?:묻|물어\s*보)지\s*(?:말|마)|승인\s*없이|확인\s*없이|맡[기길겨아]|알아서|안\s*물어")
ONE_SCREEN = re.compile(r"추천대로|알아서\s*(?:정해|골라)")   # 그 화면에 대한 답이다. 범위 낱말이 없으면 층을 주지 않는다
LEAVES_OUT = re.compile(r"빼고|제외|말고|하지\s*마")


def _with_commands_below(named):
    """명령의 층은 아래 층을 함께 준다(운영까지 맡기면 dev 명령도 맡긴 것이다). 결정(L1)은 말해야 준다."""
    out = set(named)
    top = max((ORDER.index(level) for level in named if level in COMMANDS), default=-1)
    out.update(level for level in COMMANDS if ORDER.index(level) <= top)
    return out


def _read_clause(clause):
    """절을 앞에서부터 읽는다. (말한 층, 대상과 조사의 표시들, 남은 끝말). 대상을 읽지 못하면 그 자리부터가 끝말이다."""
    named, flags, at = set(), set(), 0
    while at < len(clause):
        m = ITEM.match(clause, at)
        if not m:
            break
        kind = m.lastgroup if m.lastgroup != "part" else next(k for k in m.groupdict() if k != "part" and m.group(k))
        if kind == "token":
            low, high = LEVEL_TOKEN.search(m.group("token")).groups()
            ends = sorted((int(low), int(high or low)))
            named.update("L{}".format(n) for n in range(ends[0], ends[1] + 1))
            flags.add("token")
        elif kind in ORDER:
            named.add(kind)
            if m.group(kind).startswith("추천"):
                flags.add("recommend")
        else:
            flags.add(kind)
        part = m.group("part")
        if "까지" in part:
            flags.add("reach")
        if "도" in part:
            flags.add("adds")
        if "포함" in part:
            flags.add("reach")
        if "만" in part.replace("까지만", ""):
            flags.add("only")
        at = m.end()
    return named, flags, clause[at:].strip()


def read_levels(text, current=()):
    """(층 튜플, 되묻는 이유). 이유가 비지 않으면 층은 None이고 메인은 한 번 되묻는다. current는 지금 적힌 층이다."""
    source = FILLER.sub("", " ".join((text or "").lower().replace("\n", ", ").split()).strip())
    if not source:
        return None, ASK_AGAIN
    source = AFTER_ALL.sub("전체 " + AUTO_TOKEN, source)
    source = LEAD_AUTO.sub(AUTO_TOKEN + " ", source)
    given, taken, cleared, adds, handed, elliptic, corrected = set(), set(), False, False, False, False, False
    for clause in filter(str.strip, CLAUSE.split(source)):
        clause = clause.strip()
        correction = CORRECTION.match(clause)
        if correction:
            given, taken, adds, corrected = set(), set(), False, True   # 자기 정정: 앞 절의 층을 지우고 새로 읽는다
            clause = clause[correction.end():].strip()
            if not clause:
                continue
        if CANCEL.fullmatch(clause):
            cleared = True
            continue
        named, flags, end = _read_clause(clause)
        if end and TAKE_END.fullmatch(end):
            if not named:
                return None, ASK_AGAIN
            taken |= named
            continue
        hand, auto, go, pick = (bool(pat.fullmatch(end)) for pat in (HAND_END, AUTO_END, GO_END, PICK_END))
        if end and not (hand or auto or go or pick):   # 자동 표시(승인 없이, 묻지 말고)도 끝말을 건너뛰지 못한다
            return None, "맡기시는지 읽지 못한 말이 있습니다: " + clause
        auto = auto or "auto" in flags
        alone = "alone" in flags
        scope = flags & {"all", "rest"}
        if "only" in flags:
            return None, "그 층만인지 아래 층까지인지 읽지 못했습니다: " + clause
        if auto and not (named or scope) or (auto and corrected and not named):
            return None, "무엇을 맡기시는지 말이 모자랍니다: " + clause
        if (pick or "recommend" in flags) and not scope:
            return None, "이 화면의 답인지 실행 전체인지 읽지 못했습니다: " + clause
        if not end and not (auto or "token" in flags):
            if not named or not flags & {"reach", "adds"}:
                return None, "맡기시는지 읽지 못한 말이 있습니다: " + clause
            elliptic = True
        if not end and "token" in flags and not auto and len(named) == 1:
            return None, "그 층만인지 아래 층까지인지 읽지 못했습니다: " + clause
        if hand and not (named or "all" in flags):
            return None, ASK_AGAIN
        if alone and not (named or pick or "all" in flags):
            return None, ASK_AGAIN
        if pick and not (alone or named):
            return None, ASK_AGAIN
        if go and not (flags & {"reach", "token"} or auto or alone or scope):
            return None, "한 번의 지시인지 맡기신 것인지 읽지 못했습니다: " + clause
        if "all" in flags and not (auto or hand or alone):
            return None, ASK_AGAIN
        handed = handed or hand or auto or alone or go or "token" in flags
        if pick or (alone and named & set(COMMANDS)):
            named.add("L1")
        if auto:
            named |= {"L1", "L2"}
        if "all" in flags:
            named |= {"L1", "L2", "L3"}
        adds = adds or "adds" in flags
        given |= _with_commands_below(named)
    if elliptic and not handed:
        return None, ASK_AGAIN
    if cleared:
        return (None, ASK_AGAIN) if given else ((), "")
    if not given:
        if taken:
            return tuple(l for l in ORDER if l in set(current) - taken), ""
        return None, ASK_AGAIN
    levels = given - taken
    if adds:
        levels |= set(current) - taken
    return tuple(l for l in ORDER if l in levels), ""


def levels_text(levels):
    """("L1","L2","L3") → `L1~L3`. 끊긴 층은 쉼표로 잇는다."""
    numbers, parts, start = [int(l[1]) for l in levels], [], None
    for i, n in enumerate(numbers):
        start = n if start is None else start
        if i + 1 == len(numbers) or numbers[i + 1] != n + 1:
            parts.append("L{}".format(start) if start == n else "L{}~L{}".format(start, n))
            start = None
    return ", ".join(parts)


def sentence(run_dir, levels):
    """메인이 사용자에게 한 줄로 보이는 문장(설계 9절의 1.2.0 문장)."""
    if not levels:
        return "위임: 없음으로 적었습니다. 모두 그대로 여쭙니다"
    name = levels_text(levels)
    head = "위임: {}{} 적었습니다. ".format(name, "으로" if name.endswith("3") else "로")
    if "L1" in levels:
        out = head + "이 실행의 코드 확인은 남긴 곳으로 건수와 위치만 남고 다시 오지 않습니다. 보안과 시험 끄기·삭제는 기다립니다"
    else:
        out = head + "결정과 코드 확인은 그대로 여쭙니다. 맡기시려면 말씀해 주세요"
    empty_marks = not devflow_lib.production_marks(run_dir)[0]
    if "L4" in levels:
        out += ". 운영 명령은 실행 직전에 환경 이름을 적어 한 번 더 여쭙니다"
        if empty_marks:
            out += ". 프로젝트 설정 `운영 표지`가 비어 밖으로 나가는 명령마다 환경을 적어 한 번 더 여쭙니다"
    elif "L3" in levels and empty_marks:
        out += ". 프로젝트 설정 `운영 표지`가 비어 dev와 운영을 가르지 못하므로 밖으로 나가는 명령은 그대로 여쭙니다"
    return out


PENDING_FILE = "delegation-pending.md"
EASY_WORDS = {"L1": "결정", "L2": "로컬 명령", "L3": "dev 배포", "L4": "운영"}
CONFIRM = re.compile(r"ㅇ+|ㅇㅋ|네+|넵|예|응|맞아요?|맞습니다|맞음|좋아요?|좋습니다|그래요?|오케이|ok|okay|yes|y")


def _final_consonant(word):
    """낱말 끝 글자에 받침이 있는가."""
    code = ord(word[-1]) - 0xAC00
    return 0 <= code < 11172 and code % 28 != 0


def _joined(levels):
    """층을 쉬운 말로 잇는다: `결정, 로컬 명령과 운영`."""
    names = [EASY_WORDS[level] for level in levels]
    if len(names) < 2:
        return "".join(names)
    return "{}{} {}".format(", ".join(names[:-1]), "과" if _final_consonant(names[-2]) else "와", names[-1])


def pending_sentence(levels):
    """사람이 확인할 문장. 층 이름을 쓰지 않는다."""
    rest = [level for level in ORDER if level not in levels]
    out = "이렇게 맡기는 것으로 읽었습니다: {}.".format(_joined(levels))
    if rest:
        out += " {}{} 계속 여쭙니다.".format(_joined(rest), "은" if _final_consonant(EASY_WORDS[rest[-1]]) else "는")
    if "L1" in levels:
        out += " 결정을 맡기면 코드 확인도 건수와 위치만 남습니다."
    return out + " 맞으면 ㅇ, 아니면 고쳐 말씀해 주세요."


def write_pending(run_dir, levels, text, now=None):
    """읽은 층과 원문을 대기 파일에 쓴다. 이 파일은 위임이 아니다(행을 읽는 곳은 이 파일을 보지 않는다)."""
    stamp = now or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    devflow_lib.write_text(os.path.join(run_dir, PENDING_FILE), "층: {}\n시각: {}\n원문: {}\n".format(
        levels_text(levels), stamp, " ".join((text or "").split())))


def read_pending(run_dir):
    """{"levels", "at", "text"}, 없거나 읽지 못하면 None."""
    path = os.path.join(run_dir, PENDING_FILE)
    if not os.path.isfile(path):
        return None
    fields = dict(line.split(": ", 1) for line in devflow_lib.read_text(path).splitlines() if ": " in line)
    levels = devflow_lib.levels_in(fields.get("층", ""))
    return {"levels": levels, "text": fields.get("원문", "")} if levels else None


def clear_pending(run_dir):
    path = os.path.join(run_dir, PENDING_FILE)
    if os.path.isfile(path):
        os.remove(path)


def is_yes(answer):
    """확인의 긍정 답인가. 짧은 답의 허용 목록만 받는다. 마침표 하나까지는 받고 말줄임표는 머뭇거리는 답으로 본다."""
    return bool(CONFIRM.fullmatch(re.sub(r"(?<=[^.…])[.!~]$", "", (answer or "").strip()).lower()))


def write_levels(run_dir, levels, text, now=None, reason="", confirm=None):
    """「이번 실행의 값」 `위임` 행과 `decisions.md`의 원문 한 줄을 쓴다. text가 None이면 사용자의 말이 아니라 메인의 기록이다(reason).
    confirm은 읽은 범위를 확인한 사람의 답이다."""
    value = levels_text(levels) or "없음"
    path = os.path.join(run_dir, "run.md")
    lines = devflow_lib.read_text(path).splitlines()
    row = "| 위임 | {} |".format(value)
    at = next((i for i, l in enumerate(lines) if l.strip() == "## 이번 실행의 값"), None)
    if at is None:
        lines += ["", "## 이번 실행의 값", "| 값 | 이번 실행 |", "|---|---|", row]
    else:
        end = at + 1
        while end < len(lines) and not lines[end].startswith("## "):
            end += 1
        rows = [i for i in range(at + 1, end) if lines[i].startswith("|")]
        same = [i for i in rows if re.fullmatch(r"위임(?:\s*층)?", lines[i].strip().strip("|").split("|")[0].strip())]
        if same:
            lines[same[0]] = row
        elif rows:
            lines.insert(rows[-1] + 1, row)
        else:
            lines[at + 1:at + 1] = ["| 값 | 이번 실행 |", "|---|---|", row]
    devflow_lib.write_text(path, "\n".join(lines) + "\n")
    stamp = now or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if text is None:
        line = "- {} | [메인] 위임 {}: {} | 메인 판단\n".format(stamp, value, " ".join(reason.split()))
    else:
        answered = ' | 확인: "{}"'.format(" ".join(confirm.replace('"', "'").split())) if confirm is not None else ""
        line = '- {} | 위임 {} | 원문: "{}"{} | 실행 전체\n'.format(stamp, value, " ".join(text.replace('"', "'").split()), answered)
    log = os.path.join(run_dir, "decisions.md")
    devflow_lib.write_text(log, (devflow_lib.read_text(log) if os.path.isfile(log) else "") + line)
    return value


DELEGATION_LINE = re.compile(r'^- [^|]*\| (?:\[메인\] )?위임 ([^|:]+?)(?::[^|]*)? \|(?: 원문: "([^"]*)")?')


def current_original(run_dir):
    """`decisions.md`에서 지금 위임 행을 적은 원문. 행이 내려갔으면 빈 글이다."""
    path = os.path.join(run_dir, "decisions.md")
    found = ""
    for line in (devflow_lib.read_text(path) if os.path.isfile(path) else "").splitlines():
        m = DELEGATION_LINE.match(line)
        if m:
            found = m.group(2) or "" if m.group(1) != "없음" else ""
    return found


def answer_problem(run_dir, line, status):
    """`승인|위임 {층}|{원문}` 줄을 받지 못하는 이유(없으면 빈 글): 관문, 원문, 칸의 층을 차례로 본다."""
    if not status["closable"]:
        return "위임으로 닫지 못함: {} — 사람에게 묻고 답을 그대로 적는다".format(status["why"])
    original = current_original(run_dir)
    if not original or devflow_lib.answer_key(devflow_lib.record_quote(line)) != devflow_lib.answer_key(original):
        return "위임 원문이 아니다: 원문 칸에는 `decisions.md`의 지금 `위임` 줄 원문을 그대로 적는다(앞 task의 사람 답을 다시 쓰지 않는다)"
    written = devflow_lib.levels_in(devflow_lib.record_fields(line)[2])
    missing = [level for level in status["need"] if level not in written]
    if missing:
        return "칸의 층이 모자란다: {}이 필요하다 — `승인|위임 {}|{{원문}}`으로 적는다".format(", ".join(missing), levels_text(status["need"]))
    return ""


def handed_answer_problem(t, decision):
    """넘김 답(`하실 일 넘김|[하실 일 넘김 T0xx] {항목}|{원문}`)을 받지 못하는 이유. 표지의 id가 이 task이고 「하실 일」 칸에 그 항목이 있어야 한다."""
    mark = devflow_lib.HANDED_MARK.search(decision or "")
    if not mark or mark.group(1) != t.get("id"):
        return "넘김 답의 표지는 이 task의 `[하실 일 넘김 {}] {{항목}}`이어야 한다".format(t.get("id"))
    item = (decision or "")[mark.end():].strip()
    cells = devflow_lib.result_cells(t) or {}
    if not item or not any(item in todo for todo in split_items(cells.get("하실 일·허용 요청", ""))):
        return "넘김 답의 항목이 이 task의 「하실 일」에 없다"
    return ""


def confirmed_levels(run_dir):
    """사람이 확인해 적힌 층. `decisions.md`에 지금 위임 원문이 없는 행(손으로 쓴 행)은 층으로 보지 않는다."""
    return devflow_lib.delegation_levels(run_dir) if current_original(run_dir) else ()


def plain_answer_problem(text, has_commands=False):
    """평범한 승인으로 받지 못하는 말이면 그 이유. 층이 `()`로 읽힌 말(맡기지 않는다는 말)과 한 화면의 답은 평소 답이다.
    명령이 있는 화면에서 뺀다는 말은 어느 줄을 돌릴지 모르므로 되묻는다(승인하면 모든 줄이 언다)."""
    levels, _ = read_levels(text)
    if levels:
        return ("위임의 말이다: `screen.py {실행 폴더} --delegate \"원문\"`으로 읽은 범위를 확인받아 층을 적은 뒤 "
                "`--record \"승인|위임 {층}|원문\"`으로 적는다(관문이 거르면 사람에게 묻는다)")
    if has_commands and LEAVES_OUT.search(text or ""):
        return "명령 일부를 뺀다는 말로 보인다: 어느 줄을 돌릴지 되묻는다"
    if levels == () or ONE_SCREEN.search(text or "") or not DELEGATION_WORDS.search(text or ""):
        return ""
    return "맡기는 말로 보인다: 이 화면의 답인지 되묻는다. 실행 전체를 맡기는 말이면 `--delegate`, 사람이 할 일을 넘기는 말이면 넘김 절차를 따른다"


# ---------------------------------------------------------------- 성질


def item_derived(text, decide=False):
    """결정 줄 하나(하위 줄 포함)에서 끌어낸 성질. `[사실]` 줄은 결정이 아니다. 위험 선택지와 보안 낱말은 선택지가 있는 칸에서만 본다."""
    if text.lstrip("- ").startswith("[사실]"):
        return set()
    found = {"범위"} if SECURITY_MARK in text else set()
    for numbers in QUESTION_NUMBERS.findall(text):
        for n in re.findall(r"\d", numbers):
            found |= QUESTION_PROPERTIES.get(n, set())
    for mark in BRACKET_NUMBERS.findall(text):
        for n in re.findall(r"\d", mark):
            found |= QUESTION_PROPERTIES.get(n, set())
    if decide:
        if ACCEPT_CHOICE.search(text):
            found.add("위험")
        if SECURITY_WORDS.search(text):
            found.add("범위")
    return found


def task_derived(t):
    """task의 산출물이 닿는 곳에서 끌어낸 성질(설계 5.2절): 인프라 경로면 `비용`·`밖`, 이 실행에서 승인된 요구사항·기획을 고치면 `범위`."""
    found = set()
    if devflow_lib.touched_in_paths(t, "인프라", devflow_lib.DEFAULT_INFRA_PATTERNS):
        found |= INFRA_PROPERTIES
    if t.get("kind") == "change":
        paths = devflow_lib.touch_paths(t.get("_sections", {}).get("건드릴 파일", ""))
        if any(p.replace("\\", "/").startswith(SPEC_PREFIX) for p in paths):
            found.add("범위")
    return found


def split_items(text):
    """칸 글을 항목 글 목록으로. `- 없음`은 뺀다."""
    out = []
    for line in (text or "").splitlines():
        if line.startswith("- "):
            out.append([line])
        elif out:
            out[-1].append(line)
    return ["\n".join(it) for it in out if not devflow_lib.EMPTY_ITEM.match(it[0].strip())]


def mark_derived(text, decide=False):
    """옮겨 오지 않은 항목의 첫 줄 끝에 끌어낸 성질을 `[성질: …]`로 더한다. 이미 적힌 것은 더하지 않는다."""
    blocks, head = [], []
    for line in (text or "").splitlines():
        if line.startswith("- "):
            blocks.append([line])
        elif blocks:
            blocks[-1].append(line)
        else:
            head.append(line)
    for block in blocks:
        if devflow_lib.EMPTY_ITEM.match(block[0].strip()) or devflow_lib.MOVED_ITEM.match(block[0]):
            continue
        body = "\n".join(block)
        extra = sorted(item_derived(body, decide) - devflow_lib.item_properties(body))
        if extra:
            block[0] += " [성질: {}]".format(", ".join(extra))
    return "\n".join(head + [line for block in blocks for line in block])


# ---------------------------------------------------------------- 명령의 층


def _mark_hits(text, marks):
    low = (text or "").lower()
    for mark in marks:
        if re.search(".*".join(re.escape(part) for part in mark.lower().split("*")), low):
            return True
    return False


LOCAL_COMMAND = re.compile(r"^(?:\[[^\]]*\]\s*)?git\s+(?:merge|commit|add|checkout|switch|rebase|update-ref|branch|status|log|diff|rev-parse|tag)\b")
CHAINED = re.compile(r"&|\||;|`|\$\(|>|\n|\brebase\b.*\s(?:-x|--exec)\b")
DEFAULT_BRANCHES = ("main", "master")


def _judge_text(t):
    out = []
    for name in kinds.JUDGE_FILES.values():
        path = os.path.join(t.get("_dir", ""), name)
        if os.path.isfile(path):
            out.append(devflow_lib.read_text(path))
    return "\n".join(out)


def is_production(run_dir, t, lines):
    """명령 줄이나 판정 파일이나 task 제목이 운영을 가리키는가(설계 9절, 리뷰 F)."""
    marks, branch = devflow_lib.production_marks(run_dir)
    joined = "\n".join(lines)
    if _mark_hits(joined + "\n" + _judge_text(t), marks) or PROD_WORD.search(joined.lower()):
        return True
    if any(re.search(r"(?<![\w.-])" + re.escape(name) + r"(?![\w.-])", joined) for name in ((branch,) if branch else DEFAULT_BRANCHES)):
        return True
    return bool(PROD_WORD.search(str(t.get("title", "")).lower()))


def command_level(run_dir, t, lines):
    """명령 줄의 층. 올리는 쪽으로 틀린다: 표지가 비면 밖으로 나가는 명령은 운영으로 본다."""
    if is_production(run_dir, t, lines):
        return "L4"
    # 내보내기와 넣기의 병합은 원래 폴더에 닿는다(설계 5.3절 6)
    outside = t.get("kind") == "wrap-up" or t.get("kind") == "deploy-exec"
    if not outside and all(LOCAL_COMMAND.match(line) and not CHAINED.search(line) for line in lines):
        return "L2"
    return "L3" if devflow_lib.production_marks(run_dir)[0] else "L4"


# ---------------------------------------------------------------- 관문


def _text_before_items(text):
    """첫 `- ` 항목 앞에 글이 있는가(항목으로 세지 못하므로 관문이 읽지 못한다)."""
    lines = (text or "").splitlines()
    first = next((i for i, line in enumerate(lines) if line.startswith("- ")), None)
    return first is not None and any(line.strip() for line in lines[:first])


def gate(run_dir, t, screen_cells, failed, levels=None, held="", unread=()):
    """{"levels", "need", "wait": [(글, 이유)], "close": [글], "closable", "why"}. 기다림이 하나라도 있으면 task를 위임으로 닫지 않는다."""
    levels = devflow_lib.delegation_levels(run_dir) if levels is None else levels
    out = {"levels": levels, "need": (), "wait": [], "close": [], "closable": False, "why": ""}
    if not devflow_lib.version_at_least(t.get("started_version"), devflow_lib.RULES_V120):
        out["why"] = "1.2.0 앞에 시작한 task는 위임 관문이 없다"
        return out
    if not levels:
        out["why"] = "「이번 실행의 값」에 맡긴 층이 없다"
        return out
    wait, need = [], set()
    if t.get("kind") == "deploy-plan":
        wait.append(("배포 계획의 첫 승인", "위임이 있어도 사람이 명령 목록을 본다"))
    all_cells = "\n".join(screen_cells.get(cell, "") for cell in FOUR_CELLS)
    handed_answer = any(len(devflow_lib.record_fields(line)) > 1 and devflow_lib.record_fields(line)[1] == devflow_lib.HANDED_POINT
                        for line in devflow_lib.record_lines(t))
    if devflow_lib.HANDED_ORIGIN in str(t.get("origin", "") or "") or devflow_lib.HANDED_MARK.search(all_cells) or handed_answer:
        wait.append(("넘긴 「하실 일」", "위임 층과 별개로 명령마다 묻는다"))
    if t.get("kind") == "probe" and devflow_lib.probe_remains(t) != devflow_lib.PROBE_NOTHING:
        wait.append(("탐침이 남기는 것", "저장소 밖에 남으므로 사람에게 묻는다"))
    if devflow_lib.stage_of(t) == LAST_CHECK_STAGE:
        wait.append(("L4 직전 확인", "위임으로 닫지 않는다"))
    if held:
        wait.append((held, "완료 관문"))
    if devflow_lib.item_count(failed):
        wait.append(("통과 못 한 기준", "성질 위험"))
    for cell in FOUR_CELLS:
        if devflow_lib.unparsed_cell(screen_cells.get(cell, "")) or _text_before_items(screen_cells.get(cell, "")):
            wait.append((cell, "칸 꼴을 읽지 못함"))
    for line in unread:
        wait.append((line, "판정자 줄을 읽지 못함"))
    for item in split_items(screen_cells.get("하실 일·허용 요청", "")):
        wait.append((_head(item), "하실 일"))
    for cell in devflow_lib.DERIVED_CELLS:
        for item in split_items(devflow_lib.without_moved_items(screen_cells.get(cell, ""))):
            hit = (devflow_lib.item_properties(item) | item_derived(item, cell == "정해 주실 것")) & set(WAITING_PROPERTIES)
            if hit:
                wait.append((_head(item), "성질 " + ", ".join(sorted(hit))))
    task_hit = task_derived(t) & set(WAITING_PROPERTIES)
    if task_hit:
        wait.append(("건드릴 파일", "성질 " + ", ".join(sorted(task_hit))))
    decide = screen_cells.get("정해 주실 것", "")
    commands = devflow_lib.cmd_lines(decide)
    close = []
    for item in split_items(decide):
        if item[2:].lstrip().startswith(FACT_MARK):
            continue
        is_command = bool(devflow_lib.cmd_lines(item))
        if is_command and not CHOICE.search(item):
            if not devflow_lib.item_properties(item):
                wait.append((_head(item), "성질 표시 없음"))
            continue
        need.add("L1")
        if any(item[2:].lstrip().startswith(mark) for mark in SCRIPT_ITEMS):
            wait.append((_head(item), "스크립트가 더한 질문"))
        elif not devflow_lib.item_properties(item):
            wait.append((_head(item), "성질 표시 없음"))
        elif NO_RECOMMENDATION.search(item) or not RECOMMENDED.search(item):
            wait.append((_head(item), "추천 없음"))
        elif "L1" in levels:
            close.append(_head(item))
    if commands or t.get("kind") in kinds.STAGE_KINDS:
        # 명령 없는 단계 화면: 합치기 결과만 로컬이고 탐침, 마무리, 배포의 결과는 저장소 밖이다(설계 5.3절 6)
        need.add(command_level(run_dir, t, commands) if commands else ("L2" if t.get("kind") == "merge" else "L3"))
    elif not need:
        need.add("L1")
    missing = sorted(need - set(levels))
    if missing:
        wait.append(("맡기지 않은 층", ", ".join(missing)))
    waiting = {w for w, _ in wait}
    out.update(need=tuple(sorted(need)), wait=wait, close=[c for c in close if c not in waiting], closable=not wait)
    out["why"] = "; ".join("{} ({})".format(what, reason) for what, reason in wait)
    return out


def _head(item):
    first = item.splitlines()[0][2:].strip()
    return first if len(first) <= 60 else first[:60] + "…"


def gate_lines(g):
    """화면에 낼 줄. 항목 번호와 부딪치지 않게 `- `로 시작하지 않는다."""
    head = "■ 위임 {}: 이 화면을 {}".format(levels_text(g["levels"]), "위임으로 닫을 수 있습니다" if g["closable"] else "사람에게 묻습니다")
    lines = [head]
    lines += ["  기다림: {} ({})".format(what, reason) for what, reason in g["wait"]]
    lines += ["  추천으로 닫음: " + what for what in g["close"]]
    return lines


def is_delegated_line(line):
    fields = devflow_lib.record_fields(line)
    return len(fields) > 2 and fields[2].startswith("위임")
