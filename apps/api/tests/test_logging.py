"""The app's INFO lines reach a handler -- the grounding-check detail lives there."""

import logging

from app.core.logging import _AppHandler, configure_logging


def test_app_info_lines_are_emitted(caplog):
    configure_logging()
    with caplog.at_level(logging.INFO):
        logging.getLogger("app.routers.rag").info("dropped quotes: probe")
    assert "dropped quotes: probe" in caplog.text
    assert logging.getLogger("app").isEnabledFor(logging.INFO)


def test_configuring_twice_adds_one_handler():
    configure_logging()
    configure_logging()
    ours = [h for h in logging.getLogger("app").handlers if isinstance(h, _AppHandler)]
    assert len(ours) == 1
