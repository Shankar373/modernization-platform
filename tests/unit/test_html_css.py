"""Unit tests for HTML and CSS modernization adapters."""
import tempfile
from pathlib import Path

from backend.app.adapters.html.adapter import HtmlModernizationAdapter
from backend.app.adapters.css.adapter import CssModernizationAdapter
from backend.app.core.domain.models import MigrationProfile, TechnologyProfile, DetectedLanguage


def _html_profile():
    p = TechnologyProfile()
    p.languages = [DetectedLanguage(name="HTML", confidence=0.9)]
    return p


def _css_profile():
    p = TechnologyProfile()
    p.languages = [DetectedLanguage(name="CSS", confidence=0.9)]
    return p


# ── HTML tests ────────────────────────────────────────────────────────────────

def test_html_adapter_detect():
    adapter = HtmlModernizationAdapter()
    with tempfile.TemporaryDirectory() as tmpdir:
        Path(tmpdir, "index.html").write_text("<html><body>Hello</body></html>")
        assert adapter.detect(tmpdir) is True


def test_html_adapter_capabilities():
    caps = HtmlModernizationAdapter().get_capabilities()
    assert len(caps) >= 2
    names = {c.name for c in caps}
    assert "html-modernization" in names
    assert "html-formatting"    in names


def test_html_adapter_create_plan_has_targets():
    adapter = HtmlModernizationAdapter()
    with tempfile.TemporaryDirectory() as tmpdir:
        plan = adapter.create_plan(tmpdir, _html_profile(), "5", MigrationProfile.STANDARD)
        # Must have targets so orchestrator can route
        assert len(plan.targets) > 0
        assert plan.targets[0].language == "html"


def test_html_adapter_dry_run():
    adapter = HtmlModernizationAdapter()
    with tempfile.TemporaryDirectory() as tmpdir:
        Path(tmpdir, "index.html").write_text(
            "<center><font color='red'>Hello</font></center>"
        )
        plan = adapter.create_plan(tmpdir, _html_profile(), "5", MigrationProfile.STANDARD)
        result = adapter.dry_run(tmpdir, plan)
        assert result.success is True
        assert result.files_would_change >= 1


def test_html_adapter_migrate_modernizes_tags():
    adapter = HtmlModernizationAdapter()
    with tempfile.TemporaryDirectory() as tmpdir:
        f = Path(tmpdir, "index.html")
        f.write_text("<center><font color='red'>Hello</font></center>")
        plan = adapter.create_plan(tmpdir, _html_profile(), "5", MigrationProfile.STANDARD)
        result = adapter.migrate(tmpdir, plan)

        assert result.statistics.files_modified >= 1
        content = f.read_text(encoding="utf-8")
        # <center> should be replaced with <div style="text-align: center;">
        assert "text-align: center" in content
        # <font color="red"> → <span style="color: red;">
        assert "color: red" in content


def test_html_adapter_skips_node_modules():
    adapter = HtmlModernizationAdapter()
    with tempfile.TemporaryDirectory() as tmpdir:
        nm = Path(tmpdir, "node_modules", "lib")
        nm.mkdir(parents=True)
        (nm / "index.html").write_text("<center>Skip me</center>")
        # No actual HTML outside node_modules
        assert adapter.detect(tmpdir) is False


# ── CSS tests ─────────────────────────────────────────────────────────────────

def test_css_adapter_detect():
    adapter = CssModernizationAdapter()
    with tempfile.TemporaryDirectory() as tmpdir:
        Path(tmpdir, "style.css").write_text("body { color: red; }")
        assert adapter.detect(tmpdir) is True


def test_css_adapter_capabilities():
    caps = CssModernizationAdapter().get_capabilities()
    names = {c.name for c in caps}
    assert "css-modernization" in names
    assert "css-formatting"    in names


def test_css_adapter_create_plan_has_targets():
    adapter = CssModernizationAdapter()
    with tempfile.TemporaryDirectory() as tmpdir:
        plan = adapter.create_plan(tmpdir, _css_profile(), "3", MigrationProfile.STANDARD)
        assert len(plan.targets) > 0
        assert plan.targets[0].language == "css"


def test_css_adapter_dry_run():
    adapter = CssModernizationAdapter()
    with tempfile.TemporaryDirectory() as tmpdir:
        Path(tmpdir, "style.css").write_text("body{color:red;background:blue;}")
        plan = adapter.create_plan(tmpdir, _css_profile(), "3", MigrationProfile.STANDARD)
        result = adapter.dry_run(tmpdir, plan)
        assert result.success is True
        assert result.files_would_change >= 1


def test_css_adapter_migrate_maps_colors():
    adapter = CssModernizationAdapter()
    with tempfile.TemporaryDirectory() as tmpdir:
        f = Path(tmpdir, "style.css")
        f.write_text("body { color: red; background: blue; }")
        plan = adapter.create_plan(tmpdir, _css_profile(), "3", MigrationProfile.STANDARD)
        result = adapter.migrate(tmpdir, plan)

        assert result.statistics.files_modified >= 1
        content = f.read_text(encoding="utf-8")
        assert "var(--color-danger)"  in content   # red → danger
        assert "var(--color-accent)"  in content   # blue → accent


def test_css_adapter_skips_node_modules():
    adapter = CssModernizationAdapter()
    with tempfile.TemporaryDirectory() as tmpdir:
        nm = Path(tmpdir, "node_modules", "bootstrap")
        nm.mkdir(parents=True)
        (nm / "bootstrap.css").write_text("body { color: red; }")
        assert adapter.detect(tmpdir) is False
