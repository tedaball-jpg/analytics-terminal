import copy

import pytest

import learn_loader
from command_parser import FUNCTION_CODES
from learn_loader import ALL_FIELDS, LearnFileError, load_learn, validate_learn_data

VALID = {
    "mnemonic": "GP",
    "full_name": "Graph Price",
    "what_it_does": "Draws a price chart.",
    "why_analysts_use_it": "Quick look at trend and swings.",
    "key_concepts": [{"term": "Log scale", "explanation": "Equal distances are equal percentage moves."}],
    "how_to_read_the_output": ["Check the axes first."],
    "common_mistakes": ["Reading pence as pounds."],
    "interview_questions": [{"question": "Log or linear?", "model_answer": "Log for long histories."}],
    "terminal_checklist": ["Run GP on AAPL US Equity."],
    "related_functions": ["HP"],
}


def make_data(**overrides):
    data = copy.deepcopy(VALID)
    data.update(overrides)
    return data


# The real check: every function registered in the app must have a complete, valid learn file.
@pytest.mark.parametrize("code", sorted(FUNCTION_CODES))
def test_every_function_has_a_valid_learn_file(code):
    load_learn(code)


def test_valid_data_has_no_errors():
    assert validate_learn_data(make_data(), "GP") == []


def test_related_functions_may_be_empty():
    assert validate_learn_data(make_data(related_functions=[]), "GP") == []


@pytest.mark.parametrize("field", ALL_FIELDS)
def test_missing_field_is_reported(field):
    data = make_data()
    del data[field]
    errors = validate_learn_data(data, "GP")
    assert any(f"missing required field '{field}'" in error for error in errors)


@pytest.mark.parametrize("field", ["mnemonic", "full_name", "what_it_does", "why_analysts_use_it"])
def test_blank_text_field_is_reported(field):
    errors = validate_learn_data(make_data(**{field: "   "}), "GP")
    assert any(field in error for error in errors)


@pytest.mark.parametrize(
    "field",
    ["key_concepts", "how_to_read_the_output", "common_mistakes", "interview_questions", "terminal_checklist"],
)
def test_empty_list_is_reported(field):
    errors = validate_learn_data(make_data(**{field: []}), "GP")
    assert any(field in error for error in errors)


def test_unknown_field_is_reported():
    errors = validate_learn_data(make_data(common_mistake=["typo in the key"]), "GP")
    assert any("unknown field 'common_mistake'" in error for error in errors)


def test_mnemonic_must_match_function_code():
    errors = validate_learn_data(make_data(mnemonic="HP"), "GP")
    assert any("mnemonic" in error for error in errors)


def test_yaml_boolean_mnemonic_is_reported():
    # Unquoted NO or ON in YAML becomes a boolean, not text.
    errors = validate_learn_data(make_data(mnemonic=False), "GP")
    assert any("mnemonic" in error for error in errors)


def test_concept_missing_explanation_is_reported():
    errors = validate_learn_data(make_data(key_concepts=[{"term": "Log scale"}]), "GP")
    assert any("key_concepts" in error for error in errors)


def test_question_with_blank_answer_is_reported():
    bad = [{"question": "Log or linear?", "model_answer": ""}]
    errors = validate_learn_data(make_data(interview_questions=bad), "GP")
    assert any("interview_questions" in error for error in errors)


@pytest.mark.parametrize("bad_entry", ["hp", "H P", 5])
def test_malformed_related_mnemonic_is_reported(bad_entry):
    errors = validate_learn_data(make_data(related_functions=[bad_entry]), "GP")
    assert any("related_functions" in error for error in errors)


def test_related_functions_must_not_list_itself():
    errors = validate_learn_data(make_data(related_functions=["GP"]), "GP")
    assert any("itself" in error for error in errors)


def test_non_mapping_file_is_reported():
    assert validate_learn_data(["just", "a", "list"], "GP") != []


def test_missing_file_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(learn_loader, "LEARN_DIR", tmp_path)
    with pytest.raises(LearnFileError, match="No learn file for GP"):
        load_learn("GP")


def test_incomplete_file_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(learn_loader, "LEARN_DIR", tmp_path)
    (tmp_path / "GP.yaml").write_text("mnemonic: GP\nfull_name: Graph Price\n", encoding="utf-8")
    with pytest.raises(LearnFileError, match="missing required field"):
        load_learn("GP")


def test_broken_yaml_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(learn_loader, "LEARN_DIR", tmp_path)
    (tmp_path / "GP.yaml").write_text("mnemonic: [unclosed", encoding="utf-8")
    with pytest.raises(LearnFileError, match="not valid YAML"):
        load_learn("GP")
