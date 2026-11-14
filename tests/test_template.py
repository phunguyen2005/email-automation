import pytest

from services.template_service import render_template


def test_personalization():
    assert render_template("Chào {{ name }}: {{ score }}", {"name": "An", "score": "95"}, ["name", "score"]) == "Chào An: 95"
    assert render_template('{{ row["Họ tên"] }}', {"Họ tên": "An"}, ["Họ tên"]) == "An"


@pytest.mark.parametrize("row,template", [
    ({"name": "An"}, "{{ missing }}"),
    ({"name": ""}, "{{ name }}"),
])
def test_missing_value_or_column(row, template):
    with pytest.raises(ValueError):
        render_template(template, row, ["name"])
