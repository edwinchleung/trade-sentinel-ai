
from trade_sentinel_api.services.llm import _extract_json_from_text, _normalize_content


def test_extract_json_plain():
    data = _extract_json_from_text(
        '{"bullets": ["a", "b", "c"], "data_gaps": []}'
    )
    assert len(data["bullets"]) == 3


def test_extract_json_markdown_fence():
    text = """```json
{"bullets": ["one", "two", "three"], "data_gaps": ["earnings"]}
```"""
    data = _extract_json_from_text(text)
    assert data["bullets"][0] == "one"
    assert data["data_gaps"] == ["earnings"]


def test_extract_json_with_leading_prose():
    text = """Here is the analysis:

{"bullets": ["x", "y", "z"], "data_gaps": []}
"""
    data = _extract_json_from_text(text)
    assert data["bullets"] == ["x", "y", "z"]


def test_normalize_content_block_list():
    content = [{"type": "text", "text": '{"bullets": ["a","b","c"], "data_gaps": []}'}]
    assert "bullets" in _normalize_content(content)


def test_extract_json_bullets_only_fragment():
    text = 'Some intro\n"bullets": ["a", "b", "c"],\n"data_gaps": []\n}'
    data = _extract_json_from_text(text)
    assert data["bullets"] == ["a", "b", "c"]
    assert data["data_gaps"] == []
