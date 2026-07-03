import argparse
import pandas as pd

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", default="")
    args = parser.parse_args()

    df = pd.read_csv("dataset/final_papers.csv")
    print("Before filtering:", len(df))

    # Convert to lowercase
    df["title_clean"] = df["title"].fillna("").str.lower()
    df["abstract_clean"] = df["abstract"].fillna("").str.lower()

    if args.query:
        # Extract keywords of length > 3, excluding common stop words
        stop_words = {"does", "what", "associated", "with", "from", "therapy", "disease", "treatment", "effect", "effects", "risk", "reduce", "improves", "improve", "levels", "level", "cancer"}
        words = [w.strip().replace("?", "").replace(".", "").replace(",", "").lower() for w in args.query.split()]
        keywords = [w for w in words if len(w) > 3 and w not in stop_words]
        
        if keywords:
            print("Filtering with keywords:", keywords)
            title_pat = "|".join(keywords)
            filtered_df = df[
                df["title_clean"].str.contains(title_pat, na=False) |
                df["abstract_clean"].str.contains(title_pat, na=False)
            ].copy()
        else:
            filtered_df = df.copy()
    else:
        filtered_df = df.copy()

    # Clean up temporary column
    filtered_df = filtered_df.drop(columns=["title_clean", "abstract_clean"], errors="ignore")

    print("After filtering:", len(filtered_df))
    filtered_df.to_csv("dataset/clean_papers.csv", index=False)
    print("Saved clean_papers.csv")

if __name__ == "__main__":
    main()