from eval.memo_personas import preflight


def test_missing_env_fails_without_printing_values(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(preflight, "ENV_PATH", tmp_path / "no.env")
    monkeypatch.setenv("LLM_API_KEY", "SECRET-VALUE-123")
    monkeypatch.setenv("LLM_MODEL", "")
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.delenv("MEMO_CONFIG", raising=False)
    assert preflight.main() == 1
    out = capsys.readouterr().out
    assert "SECRET-VALUE-123" not in out
    assert "❌ .env LLM_MODEL" in out and "❌ .env DATABASE_URL" in out and "✅ .env LLM_API_KEY" in out
    assert "cp .env.example .env" in out
    assert "❌ 페르소나" not in out


def test_db_connection_failure_guidance(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(preflight, "ENV_PATH", tmp_path / "no.env")
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_MODEL", "m")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:topsecretpw@127.0.0.1:1/x")
    monkeypatch.setattr(preflight, "check_gemini", lambda r, cfg: r.ok("Gemini 테스트 호출", "건너뜀(테스트)"))
    assert preflight.main() == 1
    out = capsys.readouterr().out
    assert "❌ DB 연결" in out and "docker compose ps" in out and "topsecretpw" not in out
