"""잘못 걸리던 카드 검사 (2026-11-19 100개 B4): M023 연결/별도 기준(FINANCIAL_BASIS), M027 예측(PREDICTION)."""

import unittest
from pathlib import Path

import yaml

from pipelines.updates import checks

ROOT = Path(__file__).resolve().parents[2]
EXP = {**checks.DEFAULTS, **yaml.safe_load((ROOT / "configs" / "updates_exp.yaml").read_text(encoding="utf-8"))["topic"]}


class EarningsFigureTest(unittest.TestCase):
    def test_product_name_number_is_not_an_earnings_figure(self):
        self.assertFalse(checks._earnings_figure("공시에서는 바이오의약품 매출을 ‘CT-P13 바이오시밀러 외’로 묶어 제시했어요."))

    def test_amounts_and_percents_still_need_basis(self):
        self.assertTrue(checks._earnings_figure("3분기 매출은 4,114,227백만원이에요."))
        self.assertTrue(checks._earnings_figure("영업이익은 1조 2,000억원이에요."))
        self.assertTrue(checks._earnings_figure("영업이익률은 79.7%예요."))


class DisclosureTermPredictionTest(unittest.TestCase):
    def test_disclosure_item_names_are_not_predictions(self):
        for t in ("공시에 적힌 취득예상기간은 2026년 10월 28일부터 2027년 01월 26일까지예요.",
                  "공시상 취득예정금액은 450,000,000,000원이에요.",
                  "처분예정일은 2026-12-01이에요."):
            self.assertIsNone(checks.prediction_text([t], EXP), t)

    def test_real_predictions_still_blocked(self):
        for t in ("주가는 다음 달 오를 것으로 예상돼요.", "매출은 1조원을 넘을 것으로 예상돼요.",
                  "취득 이후 주가가 오를 가능성이 있어요."):
            self.assertIsNotNone(checks.prediction_text([t], EXP), t)


if __name__ == "__main__":
    unittest.main()
