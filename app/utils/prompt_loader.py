import os

BASE_PATH = os.path.join(os.path.dirname(__file__), "..", "static", "prompts")

def load_prompt(filename: str, **kwargs):
    path = os.path.join(BASE_PATH, filename)
    with open(path, encoding="utf-8") as f:
        text = f.read()
    return text.format(**kwargs)
