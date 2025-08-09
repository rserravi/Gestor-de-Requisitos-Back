from typing import Optional
from app.models.state_machine import StateMachine

def resolve_lang(message_lang: Optional[str], state_machine: Optional[StateMachine]) -> str:
    if message_lang and message_lang.strip():
        return message_lang.strip()
    if state_machine and state_machine.extra and state_machine.extra.get("lang"):
        return str(state_machine.extra.get("lang"))
    return "es"

def is_es(lang: str) -> bool:
    return str(lang).lower().startswith("es")
