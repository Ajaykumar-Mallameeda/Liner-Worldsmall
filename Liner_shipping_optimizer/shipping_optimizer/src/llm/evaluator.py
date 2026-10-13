import re


class LLMEvaluator:

    # --------------------------------
    # 1. Structure check
    # --------------------------------
    def structure_score(self, text: str) -> float:

        required = ["Strategy", "Reason"]

        score = 0
        for r in required:
            if r.lower() in text.lower():
                score += 1

        return score / len(required)

    # --------------------------------
    # 2. Completeness
    # --------------------------------
    def completeness_score(self, text: str) -> float:

        lines = [l.strip() for l in text.split("\n") if l.strip()]

        if len(lines) >= 3:
            return 1.0
        elif len(lines) == 2:
            return 0.7
        else:
            return 0.3

    # --------------------------------
    # 3. Relevance (domain keywords)
    # --------------------------------
    def relevance_score(self, text: str) -> float:

        keywords = [
            "demand",
            "port",
            "hub",
            "capacity",
            "route"
        ]

        matches = sum(1 for k in keywords if k in text.lower())

        return matches / len(keywords)

    # --------------------------------
    # 4. Overall score
    # --------------------------------
    def evaluate(self, text: str) -> dict:

        s = self.structure_score(text)
        c = self.completeness_score(text)
        r = self.relevance_score(text)

        total = 0.4 * s + 0.3 * c + 0.3 * r

        return {
            "structure": round(s, 2),
            "completeness": round(c, 2),
            "relevance": round(r, 2),
            "total_score": round(total, 2)
        }