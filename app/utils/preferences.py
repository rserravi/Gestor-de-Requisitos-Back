import json
from app.schemas.user import UserPreferences

def parse_user_preferences(prefs) -> UserPreferences:
    if isinstance(prefs, UserPreferences):
        return prefs
    if isinstance(prefs, str):
        try:
            prefs = json.loads(prefs)
        except json.JSONDecodeError:
            prefs = {}
    return UserPreferences(**prefs) if prefs else UserPreferences()
