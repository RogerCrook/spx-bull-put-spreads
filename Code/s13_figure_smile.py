"""
FIGURE - the implied volatility smile on two days (thesis Figure fig:smile, in sec:greeks)

What this file does:
    It READS the stage-2 output (Data/04_greeks/ folder) for two snapshots, keeps the
    out-of-the-money quotes of one expiry, and plots implied volatility against
    strike / forward. It changes no data file. It writes one picture:
        Masterarbeit_Tex_file/figures/smile.pdf
    (the folder was called "Masterarbeit Tex File from claude" until 2026-10-29)

    The two snapshots (10:00, expiry near 30 days):
        8 June 2021   (calm)    root SPXW, expiry 2021-07-07, 29 days
        16 March 2020 (stress)  root SPX,  expiry 2020-04-17, 32 days
    On 16 March 2020 the expiry nearest to 30 days was SPXW 2020-04-15, but it had
    no strikes listed below K/F = 0.70, so the monthly SPX contract is used.

    On each curve it marks
        a circle: the at-the-money volatility, fitted as in thesis Definition def:atm
                  (quadratic in x = log(K/F), out-of-the-money quotes, |x| < 0.05)
        squares:  the strategy's strike targets K = F * exp(-k * sigma_atm * sqrt(tau))
                  for k = 1 (short leg) and k = 2.3 (long leg), thesis Definition def:entry

HOW TO RUN IT
    In PowerShell, from the project folder:   python Code/s13_figure_smile.py
    It reads two monthly files of about 0.3-0.6 GB each, so it takes a minute.
"""

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")                   # draw into a file, no window on screen
import matplotlib.pyplot as plt


# ----------------------------------------------------------------------
# SETTINGS
# ----------------------------------------------------------------------

GREEKS_FOLDER = "Data/04_greeks"
OUT_FILE = os.path.join("Masterarbeit_Tex_file", "figures", "smile.pdf")

# one entry per curve: (snapshot time, monthly file, root, expiry, legend text, colour)
DAYS = [
    ("2021-06-08 10:00:00", "spx_2021-06.csv", "SPXW", "2021-07-07", "8 June 2021", "#1f5aa6"),
    ("2020-03-16 10:00:00", "spx_2020-03.csv", "SPX",  "2020-04-17", "16 March 2020", "#b8462e"),
]

K_SHORT = 1.0                           # strike offsets of the strategy, thesis Definition def:entry
K_LONG = 2.3
BAND = 0.05                             # ATM fitting band, thesis Definition def:atm

# only these columns are needed; reading fewer columns is much faster
COLUMNS = ["quote_datetime", "root", "expiration", "dte", "strike",
           "option_type", "forward", "iv"]


# ----------------------------------------------------------------------
# Read one snapshot of one expiry
# ----------------------------------------------------------------------

def read_slice(time_text, file_name, root, expiry):
    """Return the rows of one (time, root, expiry) slice from a monthly Greeks file."""
    path = os.path.join(GREEKS_FOLDER, file_name)

    # The monthly file is large, so read it in pieces ("chunks") of 2 million rows.
    # chunksize makes read_csv hand back one piece at a time instead of the whole file.
    pieces = []
    for chunk in pd.read_csv(path, usecols=COLUMNS, chunksize=2_000_000):
        # boolean mask: True on the rows of the wanted slice; & means "and"
        wanted = ((chunk["quote_datetime"] == time_text)
                  & (chunk["root"] == root)
                  & (chunk["expiration"] == expiry))
        pieces.append(chunk[wanted])

    slice_rows = pd.concat(pieces)                              # glue the pieces together
    slice_rows = slice_rows[slice_rows["iv"].notna()].copy()    # drop quotes with no volatility
    return slice_rows


# ----------------------------------------------------------------------
# Draw the figure
# ----------------------------------------------------------------------

def main():
    # fonts close to the thesis (serif, Computer-Modern-style maths)
    plt.rcParams["font.family"] = "serif"
    plt.rcParams["mathtext.fontset"] = "cm"
    plt.rcParams["font.size"] = 9

    fig, ax = plt.subplots(figsize=(6.3, 3.5))     # width, height in inches

    for time_text, file_name, root, expiry, label, colour in DAYS:
        s = read_slice(time_text, file_name, root, expiry)

        F = s["forward"].iloc[0]                    # one forward per slice; .iloc[0] = first row
        days_left = int(s["dte"].iloc[0])
        tau = days_left / 365.0
        s["m"] = s["strike"] / F                    # strike / forward

        # out-of-the-money only: puts below the forward, calls at or above it
        is_otm_put = (s["option_type"] == "P") & (s["m"] < 1)
        is_otm_call = (s["option_type"] == "C") & (s["m"] >= 1)
        otm = s[is_otm_put | is_otm_call].sort_values("strike")   # | means "or"

        # ATM volatility as in Definition def:atm: quadratic fit in x = log(K/F) on |x| < BAND.
        # np.polyfit(x, y, 2) returns [c, b, a] for c*x^2 + b*x + a; the last one is sigma(0).
        x = np.log(otm["m"])
        in_band = np.abs(x) < BAND
        coefficients = np.polyfit(x[in_band], otm["iv"][in_band], 2)
        sigma_atm = coefficients[-1]

        # strike targets of the two legs, as fractions of the forward
        m_short = np.exp(-K_SHORT * sigma_atm * np.sqrt(tau))
        m_long = np.exp(-K_LONG * sigma_atm * np.sqrt(tau))

        # implied vol at a target: read off the curve by straight-line interpolation
        # between the two neighbouring quotes (np.interp needs the x values sorted)
        iv_short = np.interp(m_short, otm["m"], otm["iv"])
        iv_long = np.interp(m_long, otm["m"], otm["iv"])

        print(label, root, expiry, days_left, "days | F =", round(F, 1),
              "| quotes", len(otm), "| ATM %.2f%%" % (100 * sigma_atm),
              "| short K/F %.3f at %.2f%%" % (m_short, 100 * iv_short),
              "| long K/F %.3f at %.2f%%" % (m_long, 100 * iv_long))

        # the curve: "-" draws a solid line, lw is its width, and label is the
        # text this curve gets in the legend
        ax.plot(otm["m"], 100 * otm["iv"], "-", lw=1.1, color=colour,
                label=label + ", " + str(days_left) + " days")
        # the ATM circle at K/F = 1: "o" draws a circle, mfc="white" fills it
        # white (marker face colour), ms is its size, and zorder=3 draws it on
        # top of the line (things with a higher zorder are drawn later)
        ax.plot([1.0], [100 * sigma_atm], "o", color=colour, mfc="white", ms=5, zorder=3)
        # the two legs: the list holds (K/F, implied vol, name) for each leg, and
        # the loop takes one leg at a time
        for m_leg, iv_leg, name in [(m_short, iv_short, "short"), (m_long, iv_long, "long")]:
            # "s" draws a square marker at the leg
            ax.plot([m_leg], [100 * iv_leg], "s", color=colour, ms=4.5, zorder=3)
            # annotate writes the word "short" or "long" next to the square;
            # textcoords="offset points" and xytext=(4, 6) put the text 4 points
            # to the right of and 6 points above the square
            ax.annotate(name, (m_leg, 100 * iv_leg), textcoords="offset points",
                        xytext=(4, 6), fontsize=8, color=colour)

    ax.axvline(1.0, color="grey", lw=0.6)          # the forward
    ax.set_xlim(0.5, 1.04)
    ax.set_ylim(0, 100)
    ax.set_xlabel(r"strike / forward  $K/F_t$")
    ax.set_ylabel("implied volatility (%)")
    ax.legend(frameon=False, loc="lower left")    # lower left is empty space in this plot
    fig.tight_layout()                            # shrink the margins to fit the axis labels

    os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)   # make figures/ if missing
    fig.savefig(OUT_FILE)
    print("saved", OUT_FILE)


if __name__ == "__main__":
    main()
