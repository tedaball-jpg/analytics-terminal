import re
from pathlib import Path

import yaml

LEARN_DIR = Path(__file__).parent / "learn"

# Field groups. Every field is required; unknown fields are rejected so typos are caught.
TEXT_FIELDS = ["mnemonic", "full_name", "what_it_does", "why_analysts_use_it"]
STRING_LIST_FIELDS = ["how_to_read_the_output", "common_mistakes", "terminal_checklist"]
RECORD_LIST_FIELDS = {
    "key_concepts": ("term", "explanation"),
    "interview_questions": ("question", "model_answer"),
}
RELATED_FIELD = "related_functions"

ALL_FIELDS = TEXT_FIELDS + STRING_LIST_FIELDS + list(RECORD_LIST_FIELDS) + [RELATED_FIELD]

MNEMONIC_PATTERN = re.compile(r"[A-Z][A-Z0-9]*")


class LearnFileError(Exception):
    pass


def _is_text(value):
    # YAML turns unquoted words like NO or ON into booleans, so check the type, not just truthiness.
    return isinstance(value, str) and value.strip() != ""


def validate_learn_data(data, code):
    """Return a list of human-readable problems; an empty list means the data is valid."""
    if not isinstance(data, dict):
        return [f"file must contain a mapping of fields, got {type(data).__name__}"]

    errors = []

    for field in ALL_FIELDS:
        if field not in data:
            errors.append(f"missing required field '{field}'")
    for field in data:
        if field not in ALL_FIELDS:
            errors.append(f"unknown field '{field}' (typo?)")

    for field in TEXT_FIELDS:
        if field in data and not _is_text(data[field]):
            errors.append(f"'{field}' must be non-empty text")

    if _is_text(data.get("mnemonic")) and data["mnemonic"] != code:
        errors.append(f"'mnemonic' is {data['mnemonic']!r} but the function code is {code!r}")

    for field in STRING_LIST_FIELDS:
        if field not in data:
            continue
        items = data[field]
        if not isinstance(items, list) or not items:
            errors.append(f"'{field}' must be a non-empty list")
        elif not all(_is_text(item) for item in items):
            errors.append(f"every item in '{field}' must be non-empty text")

    for field, keys in RECORD_LIST_FIELDS.items():
        if field not in data:
            continue
        items = data[field]
        if not isinstance(items, list) or not items:
            errors.append(f"'{field}' must be a non-empty list")
            continue
        for position, item in enumerate(items, start=1):
            if not isinstance(item, dict) or set(item) != set(keys):
                errors.append(f"'{field}' item {position} must have exactly the keys {list(keys)}")
            elif not all(_is_text(item[key]) for key in keys):
                errors.append(f"'{field}' item {position} has an empty {list(keys)} value")

    if RELATED_FIELD in data:
        related = data[RELATED_FIELD]
        if not isinstance(related, list):
            errors.append(f"'{RELATED_FIELD}' must be a list (it may be empty)")
        else:
            for item in related:
                if not isinstance(item, str) or not MNEMONIC_PATTERN.fullmatch(item):
                    errors.append(f"'{RELATED_FIELD}' entry {item!r} is not an uppercase mnemonic")
                elif item == code:
                    errors.append(f"'{RELATED_FIELD}' must not list the function itself")

    return errors


def load_learn(code):
    path = LEARN_DIR / f"{code}.yaml"

    if not path.exists():
        raise LearnFileError(f"No learn file for {code}: expected {path}")

    try:
        # Explicit utf-8: Windows would otherwise default to cp1252 and garble characters like em dashes.
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise LearnFileError(f"{path.name} is not valid YAML: {e}") from e

    errors = validate_learn_data(data, code)
    if errors:
        raise LearnFileError(f"{path.name} is invalid:\n- " + "\n- ".join(errors))

    return data
