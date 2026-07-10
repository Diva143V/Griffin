class ResearchPlanner:
    def create_plan(self, objective: str) -> list:
        return [
            {
                "agent": "retrieval",
                "task": f"collect literature relevant to {objective}"
            },
            {
                "agent": "evidence",
                "task": "rank scientific evidence using Oxford scale"
            },
            {
                "agent": "reasoning",
                "task": "traverse relationships and map scientific contradictions"
            },
            {
                "agent": "hypothesis",
                "task": "generate novel targetable research directions"
            },
            {
                "agent": "writer",
                "task": "compile and generate LaTeX/PDF style executive report"
            }
        ]
