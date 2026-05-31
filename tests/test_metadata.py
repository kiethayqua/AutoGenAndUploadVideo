from auto_tiktok_orchestrator.metadata import parse_json_object


def test_parse_json_object_strict_json():
    assert parse_json_object('{"idea":"practice shadowing"}') == {"idea": "practice shadowing"}


def test_parse_json_object_fenced_json():
    assert parse_json_object('```json\n{"idea":"practice shadowing"}\n```') == {"idea": "practice shadowing"}


def test_parse_json_object_python_dict_output():
    assert parse_json_object("{'caption': 'Speak clearly', 'hashtags': ['#English', '#Tubeshad']}") == {
        "caption": "Speak clearly",
        "hashtags": ["#English", "#Tubeshad"],
    }


def test_parse_json_object_embedded_python_dict_output():
    assert parse_json_object("Here is the result: {'idea': 'repeat minimal pairs daily'}") == {
        "idea": "repeat minimal pairs daily"
    }
