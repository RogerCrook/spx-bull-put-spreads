# Every snapshot the rule skipped in the four "on" runs (action "skipped (broken)"
# or "not opened (broken)"), with both legs' quotes. Read-only.
import pandas as pd                 # pandas works with tables

HERE = "C:/Dokumente/Python/Masterarbeit/experiments/quote_filter/"
RUNS = ["base_mid", "base_cross", "p15_mid", "p15_cross"]

pd.set_option("display.width", 250)            # print wide tables on one line
for run in RUNS:
    q = pd.read_csv(HERE + "quotes_" + run + "_on_c8c9.csv")
    # an empty action is read back as a missing value; fillna("") makes it empty text
    q["action"] = q["action"].fillna("")
    # .str.contains("broken"): True where the action text contains "broken";
    # q[...] keeps those rows; .copy() makes it a table of its own, so the new
    # columns below are added to it and not to q
    hit = q[q["action"].str.contains("broken")].copy()
    # the vol before and now as text, e.g. "53.7 -> 46.3": .round(1) rounds to
    # 1 decimal, .astype(str) turns the numbers into text so they can be joined
    vol_before = (100 * hit["iv_before"]).round(1).astype(str)
    vol_now = (100 * hit["iv"]).round(1).astype(str)
    hit["vol"] = vol_before + " -> " + vol_now
    hit["ratio"] = hit["width_ratio"].round(1)
    print("\n" + run)
    # to_string(index=False): print the table without pandas' row numbers
    print(hit[["time", "kind", "leg", "root", "expiration", "strike", "bid_before", "ask_before",
               "bid", "ask", "vol", "ratio", "action"]].to_string(index=False))
