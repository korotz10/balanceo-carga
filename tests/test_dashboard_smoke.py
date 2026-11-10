from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_dashboard_renders_and_runs_official_simulation():
    dashboard = Path(__file__).resolve().parents[1] / "src" / "dashboard.py"
    app = AppTest.from_file(str(dashboard), default_timeout=30).run()

    assert not app.exception
    assert len(app.tabs) == 4
    next(button for button in app.button if button.key == "ejecutar_oficial").click()
    app.run()

    assert not app.exception
    assert any("Resultados oficiales" in tab.label for tab in app.tabs)


def test_reproduction_play_button_enables_automatic_tick_updates():
    dashboard = Path(__file__).resolve().parents[1] / "src" / "dashboard.py"
    app = AppTest.from_file(str(dashboard), default_timeout=30).run()
    next(button for button in app.button if button.key == "preparar_reproduccion").click()
    app.run()

    next(button for button in app.button if button.key == "toggle_reproduccion").click()
    app.run()

    assert not app.exception
    assert app.session_state["reproduccion_activa"] is True
    assert app.session_state["tick_reproduccion"] > 0

    next(button for button in app.button if button.key == "toggle_reproduccion").click()
    app.run()
    assert app.session_state["reproduccion_activa"] is False
