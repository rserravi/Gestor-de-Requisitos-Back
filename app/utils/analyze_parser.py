import re
from typing import List, Tuple

QUESTION_RE = re.compile(r"^\s*\d+[\.\)]\s+(.+)$")  # 1. ó 1) Pregunta...

def parse_analyze_output(text: str) -> Tuple[str, List[str]]:
    """
    Devuelve (comentarios, preguntas[])
    - comentarios: bloque previo a la primera línea numerada tipo '1. ...' o '1) ...'
    - preguntas: cada línea numerada sin el prefijo '1. ' / '1) '
    """
    lines = [l.strip() for l in text.splitlines()]
    comments_lines: List[str] = []
    questions: List[str] = []

    reached_questions = False
    for l in lines:
        if not l:
            # preserva separación visual en comentarios, ignora en preguntas
            if not reached_questions:
                comments_lines.append("")
            continue

        m = QUESTION_RE.match(l)
        if m:
            reached_questions = True
            q = m.group(1).strip()
            if q:
                questions.append(q)
        else:
            # línea no numerada
            if not reached_questions:
                # filtra encabezados tipo 'Preguntas para ...'
                if not l.lower().startswith("preguntas"):
                    comments_lines.append(l)

    comments = "\n".join([cl for cl in comments_lines]).strip()
    return comments, questions
