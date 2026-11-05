from eval.memo_personas import preflight
from eval.memo_personas.common import read_database_url


def test_read_database_url_prefers_readonly():
    env = {"READONLY_DATABASE_URL": " postgresql://readonly/db ", "DATABASE_URL": "postgresql://writer/db"}
    assert read_database_url(env) == "postgresql://readonly/db"


def test_read_database_url_falls_back_to_database_url():
    env = {"READONLY_DATABASE_URL": "  ", "DATABASE_URL": " postgresql://writer/db "}
    assert read_database_url(env) == "postgresql://writer/db"


def test_read_database_url_missing_is_safe():
    assert read_database_url({}) is None


def test_missing_env_fails_without_printing_values(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(preflight, "ENV_PATH", tmp_path / "no.env")
    monkeypatch.setenv("LLM_API_KEY", "SECRET-VALUE-123")
    monkeypatch.setenv("LLM_MODEL", "")
    monkeypatch.setenv("READONLY_DATABASE_URL", "")
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.delenv("MEMO_CONFIG", raising=False)
    assert preflight.main() == 1
    out = capsys.readouterr().out
    assert "SECRET-VALUE-123" not in out
    assert "❌ .env LLM_MODEL" in out
    assert "❌ .env READONLY_DATABASE_URL 또는 DATABASE_URL" in out
    assert "✅ .env LLM_API_KEY" in out
    assert "cp .env.example .env" in out
    assert "❌ 페르소나" not in out


def test_db_connection_failure_guidance(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(preflight, "ENV_PATH", tmp_path / "no.env")
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_MODEL", "m")
    monkeypatch.setenv("READONLY_DATABASE_URL", "")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:topsecretpw@127.0.0.1:1/x")
    monkeypatch.setattr(preflight, "check_gemini", lambda r, cfg: r.ok("Gemini 테스트 호출", "건너뜀(테스트)"))
    assert preflight.main() == 1
    out = capsys.readouterr().out
    assert "❌ DB 연결" in out and "DB 상태" in out and "topsecretpw" not in out
