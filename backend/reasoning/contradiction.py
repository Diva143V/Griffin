class ContradictionResolver:
    def analyze(self, claims: list) -> list:
        conflicts = []
        for idx, a in enumerate(claims):
            for b in claims[idx+1:]:
                if a != b:
                    conflicts.append({
                        "claim_a": a,
                        "claim_b": b,
                        "possible_reason": "Different patient population or dosing methodology"
                    })
        return conflicts
