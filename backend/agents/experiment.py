class ExperimentAgent:
    def create_plan(self, hypothesis: str) -> dict:
        return {
            "model": "In-vitro human breast cancer line (MCF7) / In-vivo mouse model",
            "intervention": f"Metformin treatment + AMPK Pathway Inhibitor: {hypothesis}",
            "measurements": [
                "AMPK phosphorylation levels",
                "Tumor proliferation rates",
                "Immune marker expression (PD-L1, CD8+ T-cells)"
            ],
            "controls": "Untreated group & Monotherapy group"
        }
