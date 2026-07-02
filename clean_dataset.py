import pandas as pd

df = pd.read_csv(
    "dataset/final_papers.csv"
)

print("Before filtering:",
      len(df))

# Convert to lowercase
df["title"] = (
    df["title"]
    .fillna("")
    .str.lower()
)

df["abstract"] = (
    df["abstract"]
    .fillna("")
    .str.lower()
)

# Keep only breast cancer + metformin papers, and exclude papers primarily about other drugs (like GLP-1)
is_metformin = (
    df["title"].str.contains("metformin") |
    df["abstract"].str.contains("metformin")
)
is_breast_cancer = (
    df["title"].str.contains("breast cancer") |
    df["abstract"].str.contains("breast cancer")
)

# Exclude papers where title contains GLP-1 or other specific drug classes unless title also contains metformin
has_other_drug_in_title = df["title"].str.contains("glp-1|glp1|semaglutide|liraglutide|sglt2", regex=True)
has_metformin_in_title = df["title"].str.contains("metformin")
exclude_mask = has_other_drug_in_title & ~has_metformin_in_title

filtered_df = df[is_metformin & is_breast_cancer & ~exclude_mask]


print("After filtering:",
      len(filtered_df))

filtered_df.to_csv(
    "dataset/clean_papers.csv",
    index=False
)

print("Saved clean_papers.csv")