import sys
import os
import logging

# Ensure root directory is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.neo4j_client import Neo4jClient
from src.agents.tog_agent import ThinkOnGraphAgent

logging.basicConfig(level=logging.INFO)

def main():
    print("Connecting to Neo4j Client...")
    client = Neo4jClient()
    if not client.connect():
        print("Error: Could not connect to Neo4j!")
        return

    try:
        agent = ThinkOnGraphAgent(client)
        # We query for SIRT1, which does not exist in the database yet.
        # This will trigger the Self-Healing collector mechanism!
        query = "Does metformin interact with SIRT1 in breast cancer?"
        print(f"Running Think-on-Graph loop with self-healing for query: '{query}'...\n")
        
        context, papers = agent.run_tog(query, max_hops=2, beam_width=1)
        
        print("\n=== TRAVERSAL HISTORY ===")
        print(context)
        
        print("\n=== VISITED PAPERS ===")
        if papers:
            for p in papers:
                print(f"- {p['title']} (Quality Score: {p['evidence_score']}/10)")
        else:
            print("No paper nodes visited.")
            
    finally:
        client.close()

if __name__ == "__main__":
    main()
