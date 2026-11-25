"""Sample project code for the Vee Check examples: each region's share of the portfolio."""
import pandas as pd


def region_shares(path="holdings.csv"):
    df = pd.read_csv(path)
    totals = df.groupby("region")["weight"].sum()
    return (totals / totals.sum() * 100).round(1)


if __name__ == "__main__":
    print(region_shares())
