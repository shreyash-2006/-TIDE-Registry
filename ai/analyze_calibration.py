import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

from sklearn.metrics import r2_score


# ============================================================
# 1. LOAD DATA
# ============================================================

df = pd.read_csv(
    "data/ndvi_agb_samples.csv"
)

print("Dataset shape:", df.shape)

print("\nMissing values:")
print(df.isnull().sum())


# ============================================================
# 2. BASIC STATISTICS
# ============================================================

print("\nNDVI:")
print(df["ndvi"].describe())

print("\nAGB:")
print(df["agb_t_per_ha"].describe())


# ============================================================
# 3. CORRELATION
# ============================================================

correlation = df[
    ["ndvi", "agb_t_per_ha"]
].corr().iloc[0, 1]

print("\nNDVI–AGB correlation:", correlation)


# ============================================================
# 4. SCATTER PLOT
# ============================================================

plt.figure(figsize=(8, 6))

plt.scatter(
    df["ndvi"],
    df["agb_t_per_ha"],
    alpha=0.6
)

plt.xlabel("NDVI")
plt.ylabel("AGB (t/ha)")
plt.title("Pichavaram NDVI vs NASA AGB")

plt.grid(True)

plt.tight_layout()

plt.savefig(
    "data/ndvi_agb_scatter.png",
    dpi=300
)

plt.show()


# ============================================================
# 5. IDENTIFY EXTREME NDVI VALUES
# ============================================================

print("\nNegative NDVI samples:")

print(
    df[df["ndvi"] < 0]
)


# ============================================================
# 6. CHECK AGB VALUE DISTRIBUTION
# ============================================================

print("\nMost common AGB values:")

print(
    df["agb_t_per_ha"]
    .value_counts()
    .head(15)
)