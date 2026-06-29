"""load_dotenv: local .env -> os.environ, without overriding preset vars."""
import os
from services.loader import load_dotenv


def test_sets_vars_and_respects_existing(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("# a comment\nSLACK_WEBHOOK_URL=https://hooks.slack.com/x\n"
                   "WEB_BASE_URL='http://pi:8765'\n\nNOEQUALS_LINE\n")
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    monkeypatch.setenv("WEB_BASE_URL", "preset")     # setdefault must NOT override
    load_dotenv(str(env))
    assert os.environ["SLACK_WEBHOOK_URL"] == "https://hooks.slack.com/x"
    assert os.environ["WEB_BASE_URL"] == "preset"    # already-set wins


def test_missing_file_is_noop(tmp_path):
    load_dotenv(str(tmp_path / "nope.env"))          # must not raise
