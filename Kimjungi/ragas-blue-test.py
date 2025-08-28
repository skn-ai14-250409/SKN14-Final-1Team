from ragas import SingleTurnSample
from ragas.metrics import BleuScore

# 한국어 예시 문장
test_data = {
    "user_input": "다음 텍스트를 요약해줘\n이 회사는 2024년 3분기에 아시아 시장에서의 강력한 실적에 힘입어 8%의 성장을 기록했습니다. 이 지역의 판매 증가가 전체 성장에 크게 기여했으며, 이는 전략적인 마케팅과 제품 현지화 덕분이라는 분석입니다. 이러한 긍정적인 흐름은 다음 분기에도 계속될 것으로 예상됩니다.",
    "response": "이 회사는 2024년 3분기에 아시아 시장의 강력한 실적 덕분에 8% 성장했으며, 다음 분기에도 성장세가 기대됩니다.",
    "reference": "이 회사는 전략적 마케팅과 제품 현지화를 통해 아시아 시장에서 높은 실적을 내며 2024년 3분기에 8% 성장을 기록했고, 이 추세는 계속될 전망입니다."
}

metric = BleuScore()
sample = SingleTurnSample(**test_data)
score = metric.single_turn_score(sample)

print("BLEU 점수:", score)