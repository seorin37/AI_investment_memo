from eval.memo_personas import typo


def test_rate_zero_keeps_text():
    t = "삼전 7만원 밑으로 오면 알림 받기"
    assert typo.inject(t, 0.0, "P001-01") == t


def test_protected_words_untouched_and_deterministic():
    t = "삼전 하닉 네이버 kb 10월 14일 7만원 HBM4 확인했습니다 체크하기 기다려보자"
    out = typo.inject(t, 1.0, "P001-02")
    assert out == typo.inject(t, 1.0, "P001-02")
    for w in ("삼전", "하닉", "네이버", "kb", "10월", "14일", "7만원", "HBM4"):
        assert w in out.split(" ")
    assert out != t


def test_mutations_change_word():
    assert all(m != "확인했습니다" for m in typo._mutations("확인했습니다"))
    assert "햇" in "".join(typo._mutations("했다"))
