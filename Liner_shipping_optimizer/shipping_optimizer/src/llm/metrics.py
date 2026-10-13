class LLMMetrics:

    def __init__(self):
        self.records = []

    def log(self, agent, scores):
        self.records.append({
            "agent": agent,
            **scores
        })

    def summary(self):

        if not self.records:
            return {}

        avg_score = sum(r["total_score"] for r in self.records) / len(self.records)

        return {
            "calls": len(self.records),
            "avg_score": round(avg_score, 2)
        }


llm_metrics = LLMMetrics()