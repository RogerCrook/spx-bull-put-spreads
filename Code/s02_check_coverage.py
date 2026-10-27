import glob, pandas as pd

files = sorted(glob.glob("Data/02_clean/*.csv"))
days = set()

for i, f in enumerate(files, 1):
    d = pd.read_csv(f, usecols=["quote_datetime"])        # no parse_dates
    days.update(d["quote_datetime"].str[:10].unique())    # first 10 chars = the date
    print(i, "/", len(files), f, "->", len(days), "days so far")

days = pd.DatetimeIndex(sorted(days))
print()
print(len(days), "trading days,", days[0].date(), "to", days[-1].date())

missing = pd.bdate_range(days[0], days[-1]).difference(days)
print(len(missing), "weekdays with no data")
print(missing[:40])