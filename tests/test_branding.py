"""Brand asset and planned Insights view must remain honest and accessible."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def test_official_colors_and_logo_asset():
    svg=(ROOT/"app/static/mehrad-kavir-logo.svg").read_text(encoding="utf8")
    css=(ROOT/"app/static/app.css").read_text(encoding="utf8")
    for color in ("#006FFE","#1E2B39"):
        assert color in svg
    for color in ("#006FFE","#1E2B39","#111A24","#F3F5F7","#AEB8C2"):
        assert color.lower() in css.lower()
    assert "viewBox" in svg

def test_brand_logo_used_in_app():
    html=(ROOT/"app/static/index.html").read_text(encoding="utf8")
    assert html.count('/static/mehrad-kavir-logo.svg') >= 2
    assert 'alt="لوگوی مهراد کویر"' in html
    assert 'id="page-insights"' in html

def test_insights_does_not_invent_numbers():
    html=(ROOT/"app/static/index.html").read_text(encoding="utf8")
    js=(ROOT/"app/static/app.js").read_text(encoding="utf8")
    assert "در انتظار داده واقعی" in html
    assert "در انتظار اتصال رسمی Insights" in html
    assert 'activePage === "insights"' in js
    assert "data.integration.meta" in js
