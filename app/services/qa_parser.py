import re
from typing import List, Tuple

NUM_LINE = re.compile(r"^\s*(?:[-*]\s*)?(?P<n>\d+)[\.\)]\s+(?P<txt>.+?)\s*$")

def _split_sections(text: str) -> Tuple[str, str]:
    t = text.replace("\r\n", "\n").strip()
    comments_pat = re.compile(r"^\s*COMENTARIOS\s*:\s*$", re.IGNORECASE | re.MULTILINE)
    questions_pat = re.compile(r"^\s*PREGUNTAS\s*:\s*$", re.IGNORECASE | re.MULTILINE)

    comments_iter = list(comments_pat.finditer(t))
    questions_iter = list(questions_pat.finditer(t))

    if not questions_iter:
        return "", t

    c_pos = comments_iter[0].end() if comments_iter else None
    q_pos = questions_iter[0].end()

    if c_pos is not None and c_pos < q_pos:
        comments_block = t[c_pos:questions_iter[0].start()].strip()
        questions_block = t[q_pos:].strip()
    else:
        comments_block = ""
        questions_block = t[q_pos:].strip()

    return comments_block, questions_block

def _parse_numbered_block(block: str) -> List[str]:
    out: List[str] = []
    for raw in (block or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        m = NUM_LINE.match(line)
        if m:
            txt = m.group("txt").strip()
            if txt and txt.lower() != "(ninguno)":
                out.append(txt)
    return out

def parse_analyze_output(text: str) -> Tuple[str, List[str]]:
    comments_block, questions_block = _split_sections(text)
    comments_list = _parse_numbered_block(comments_block) if comments_block else []
    questions_list = _parse_numbered_block(questions_block) if questions_block else []

    # Fallback si no hay preguntas numeradas
    if not questions_list:
        lines = [l.strip() for l in text.replace("\r\n", "\n").splitlines()]
        first_q_ix = None
        for i, l in enumerate(lines):
            if NUM_LINE.match(l):
                first_q_ix = i
                break
        if first_q_ix is not None:
            q_block = "\n".join(lines[first_q_ix:])
            questions_list = _parse_numbered_block(q_block)
            pre = [x for x in lines[:first_q_ix] if x and not NUM_LINE.match(x)]
            if not comments_list:
                comments_list = pre

    comments = "\n".join(comments_list).strip()
    return comments, questions_list
