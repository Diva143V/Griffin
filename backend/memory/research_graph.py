class ResearchMemory:
    def __init__(self):
        self.graph = {}

    def add_node(self, node_type: str, value: Any):
        if node_type not in self.graph:
            self.graph[node_type] = []
        self.graph[node_type].append(value)

    def search(self, node_type: str) -> list:
        return self.graph.get(node_type, [])
