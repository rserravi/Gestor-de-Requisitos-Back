import re
from typing import List, Tuple

# Acepta "1. ..." o "1) ..." y tolera que la IA preponga viñetas "- " o "* "
NUM_LINE = re.compile(r"^\s*(?:[-*]\s*)?(?P<n>\d+)[\.\)]\s+(?P<txt>.+?)\s*$")

def _split_sections(text: str) -> Tuple[str, str]:
    """
    Separa por marcadores COMENTARIOS: y PREGUNTAS: (case-insensitive).
    Devuelve (comments_block, questions_block) crudos (pueden estar vacíos).
    Si no encuentra marcadores, devuelve ("", text) como fallback.
    """
    t = text.replace("\r\n", "\n").strip()
    # Busca encabezados exactos (tolerando espacios y case)
    comments_pat = re.compile(r"^\s*COMENTARIOS\s*:\s*$", re.IGNORECASE | re.MULTILINE)
    questions_pat = re.compile(r"^\s*PREGUNTAS\s*:\s*$", re.IGNORECASE | re.MULTILINE)

    comments_iter = list(comments_pat.finditer(t))
    questions_iter = list(questions_pat.finditer(t))

    if not questions_iter:
        # Fallback bruto: no hay secciones bien formadas → todo a "preguntas"
        return "", t

    # Elegimos la PRIMERA ocurrencia de cada sección posterior a la otra
    c_pos = comments_iter[0].end() if comments_iter else None
    q_pos = questions_iter[0].end()

    if c_pos is not None and c_pos < q_pos:
        comments_block = t[c_pos : questions_iter[0].start()].strip()
        questions_block = t[q_pos :].strip()
    else:
        # No hay COMENTARIOS antes que PREGUNTAS → comentarios vacío
        comments_block = ""
        questions_block = t[q_pos :].strip()

    return comments_block, questions_block


def _parse_numbered_block(block: str) -> List[str]:
    """
    Extrae líneas numeradas del bloque (1./1) ...).
    Ignora líneas vacías y no numeradas.
    """
    out: List[str] = []
    for raw in block.splitlines():
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
    """
    Devuelve (comentarios, preguntas[])
    - comentarios: una cadena (puede contener \n) construida desde las líneas numeradas del bloque COMENTARIOS.
      Si la IA puso (ninguno), devolverá "".
    - preguntas: lista de preguntas (sin numeración)
    Fallbacks:
      * si faltan encabezados, intenta detectar el primer bloque numerado como preguntas,
        y trata lo anterior como comentarios "libres" (no numerados).
    """
    comments_block, questions_block = _split_sections(text)

    # Intento “by the book”
    comments_list = _parse_numbered_block(comments_block) if comments_block else []
    questions_list = _parse_numbered_block(questions_block) if questions_block else []

    # Fallback heurístico si no hay preguntas numeradas
    if not questions_list:
        # Busca el primer tramo numerado en todo el texto como preguntas
        lines = [l.strip() for l in text.replace("\r\n", "\n").splitlines()]
        first_q_ix = None
        for i, l in enumerate(lines):
            if NUM_LINE.match(l):
                first_q_ix = i
                break
        if first_q_ix is not None:
            q_block = "\n".join(lines[first_q_ix:])
            questions_list = _parse_numbered_block(q_block)
            # Comentarios: líneas anteriores no vacías que no sean viñetas
            pre = [x for x in lines[:first_q_ix] if x and not NUM_LINE.match(x)]
            comments_list = pre if not comments_list else comments_list

    comments = "\n".join(comments_list).strip()
    return comments, questions_list
