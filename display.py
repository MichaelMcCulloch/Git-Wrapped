import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.patches as mpatches
import seaborn as sns
from matplotlib.colors import to_rgb
import datetime

# --- CONFIGURATION ---
FILENAME = "repo_aware_history.json"
THEME_BG = "#0d1117"  # GitHub Dark Dimmed
THEME_FG = "#c9d1d9"
THEME_ACCENT = "#58a6ff"  # GitHub Blue
COLOR_OTHER = "#21262d"  # Dark gray for background elements
TOP_N = 114  # How many distinct colors to show in charts


def load_data():
    try:
        with open(FILENAME, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ '{FILENAME}' not found. Run read.py first!")
        exit()


def hex_to_rgb_norm(hex_col):
    return to_rgb(hex_col)


def create_dashboard():
    print("🎨 Generating Deep-Dive Dashboard...")
    data = load_data()

    # --- DATA PREP ---
    df = pd.DataFrame(data["detailed_commits"])
    df = df.rename(columns={"date": "iso_date", "repo": "repo_name"})

    # Date Conversions
    df["dt"] = pd.to_datetime(df["iso_date"], utc=True).dt.tz_convert(
        "America/Edmonton"
    )
    df["date"] = df["dt"].dt.date
    df["year"] = df["dt"].dt.year
    df["month_year"] = df["dt"].dt.to_period("M")
    df["hour"] = df["dt"].dt.hour
    df["weekday"] = df["dt"].dt.day_name()

    # --- PALETTE GENERATION ---
    # Identify top repos by "Impact" (Lines Changed), not just commit count
    # This highlights the projects where the real work happened.
    df["total_impact"] = df["additions"] + df["deletions"]
    impact_by_repo = (
        df.groupby("repo_name")["total_impact"].sum().sort_values(ascending=False)
    )

    top_repos_list = impact_by_repo.head(TOP_N).index.tolist()

    # Custom vibrant palette
    palette = sns.color_palette("husl", len(top_repos_list)).as_hex()
    repo_color_map = {repo: palette[i] for i, repo in enumerate(top_repos_list)}
    repo_color_map["Other"] = "#3d444d"  # Muted gray for others

    # --- FIGURE SETUP ---
    years = sorted(df["year"].unique(), reverse=True)
    n_years = len(years)

    # Layout Calculation
    # Row 0: Title (Fixed small)
    # Row 1: Heatmap (Dynamic height based on years)
    # Row 2: Charts (Punchcard & Languages)
    # Row 3: Timeline Streamgraph (The new Deep Metric)
    # Row 4: Legend

    fig_height = max(18, (n_years * 1.5) + 10)
    fig = plt.figure(figsize=(22, fig_height))
    fig.patch.set_facecolor(THEME_BG)

    gs = gridspec.GridSpec(
        4,
        4,
        height_ratios=[0.5, n_years, 3, 3],
        width_ratios=[0.6, 1, 1, 1],
        hspace=0.4,
        wspace=0.15,
    )

    # ==========================
    # 1. HEADER & METRICS
    # ==========================
    ax_title = fig.add_subplot(gs[0, :])
    ax_title.axis("off")

    total_commits = len(df)
    total_lines = df["total_impact"].sum()
    est_hours = data.get("total_hours_estimated", 0)

    ax_title.text(
        0.5,
        0.75,
        "ENGINEERING DNA SEQUENCE",
        ha="center",
        fontsize=38,
        color=THEME_FG,
        fontweight="bold",
        fontfamily="sans-serif",
    )

    stats_line = (
        f"{total_commits:,} COMMITS  |  "
        f"{int(est_hours):,} EST. HOURS  |  "
        f"{total_lines:,} LINES MOVED"
    )

    ax_title.text(
        0.5,
        0.25,
        stats_line,
        ha="center",
        fontsize=14,
        color=THEME_ACCENT,
        fontfamily="monospace",
    )

    # ==========================
    # 2. CALENDAR HEATMAP (Dominance)
    # ==========================
    ax_heat = fig.add_subplot(gs[1, 1:])

    # Logic: Identify the "Dominant" repo for each day to assign color
    daily_repo_counts = (
        df.groupby(["date", "repo_name"])["total_impact"].sum().reset_index()
    )
    daily_repo_counts = daily_repo_counts.sort_values(
        ["date", "total_impact"], ascending=[True, False]
    )
    daily_top = daily_repo_counts.drop_duplicates(subset="date")
    date_to_repo = dict(zip(daily_top["date"], daily_top["repo_name"]))

    bg_rgb = hex_to_rgb_norm(THEME_BG)
    # Grid: [Rows (Years * 9), Cols (53 weeks), RGB]
    total_rows = (n_years * 8) + ((n_years - 1) * 2)
    grid = np.full((total_rows, 53, 3), bg_rgb)

    for i, year in enumerate(years):
        y_offset = i * 9
        start_date = datetime.date(year, 1, 1)

        # Year Label
        ax_heat.text(
            -1.5,
            y_offset + 3.5,
            str(year),
            color=THEME_FG,
            fontsize=14,
            fontweight="bold",
            ha="right",
            va="center",
        )

        for d_ord in range(366):
            d = start_date + datetime.timedelta(days=d_ord)
            if d.year != year:
                continue

            week = int(d.strftime("%W"))
            day = d.weekday()  # 0=Mon, 6=Sun

            if week < 53:
                if d in date_to_repo:
                    r_name = date_to_repo[d]
                    if r_name not in top_repos_list:
                        r_name = "Other"
                    grid[y_offset + day, week] = hex_to_rgb_norm(repo_color_map[r_name])
                else:
                    # Subtle dot for empty days to keep structure
                    grid[y_offset + day, week] = hex_to_rgb_norm("#161b22")

    ax_heat.imshow(grid, aspect="equal", interpolation="nearest")
    ax_heat.axis("off")
    ax_heat.set_title(
        "DAILY DOMINANCE (Primary Project per Day)",
        color="#8b949e",
        fontsize=10,
        loc="left",
    )
    # ==========================
    # 3. PUNCH CARD (Focus)
    # ==========================
    ax_punch = fig.add_subplot(gs[2, 1:3])

    day_order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    df["short_day"] = df["dt"].dt.strftime("%a")
    df["short_day"] = pd.Categorical(
        df["short_day"], categories=day_order, ordered=True
    )

    # 1. Aggregate Impact
    punch_data = (
        df.groupby(["short_day", "hour"], observed=False)["total_impact"]
        .sum()
        .unstack(fill_value=0)
    )

    # 2. Log Transform (to handle 10 vs 10,000 lines)
    punch_data_log = np.log1p(punch_data)

    # 3. Calculate Contrast Cutoff (The Fix)
    # We clip the top 5% of heaviest hours so massive data dumps don't
    # wash out the rest of the chart.
    vmax = np.percentile(punch_data_log.values, 95)

    sns.heatmap(
        punch_data_log,
        cmap="mako",
        ax=ax_punch,
        cbar=False,
        square=True,
        linewidths=0.5,
        linecolor=THEME_BG,
        vmax=vmax,  # <--- Forces contrast into the visible range
    )

    ax_punch.set_title(
        "IMPACT RHYTHM (Log Scale + 95% Clip)", color=THEME_FG, fontsize=14, pad=10
    )
    ax_punch.set_xlabel("Hour of Day", color="#8b949e")
    ax_punch.set_ylabel("")
    ax_punch.tick_params(colors="#8b949e")

    # ==========================
    # 4. LANGUAGES (Breadth)
    # ==========================
    ax_lang = fig.add_subplot(gs[2, 3])
    langs = data["languages"]
    # Filter small langs
    sorted_langs = sorted(langs.items(), key=lambda x: x[1], reverse=True)
    top_langs = sorted_langs[:8]
    other_count = sum(x[1] for x in sorted_langs[8:])
    if other_count > 0:
        top_langs.append(("Others", other_count))

    labels, values = zip(*top_langs)

    # Donut Chart
    wedges, texts, autotexts = ax_lang.pie(
        values,
        labels=labels,
        autopct="%1.0f%%",
        startangle=140,
        pctdistance=0.85,
        colors=sns.color_palette("viridis", len(values)),
        textprops={"color": THEME_FG},
    )

    ax_lang.add_artist(plt.Circle((0, 0), 0.65, fc=THEME_BG))
    for w in wedges:
        w.set_edgecolor(THEME_BG)
        w.set_linewidth(2)
    ax_lang.set_title(
        "LANGUAGE DISTRIBUTION (File Volume)", color=THEME_FG, fontsize=14
    )

    # ==========================
    # 5. TIMELINE STREAMGRAPH (Evolution)
    # ==========================
    ax_stream = fig.add_subplot(gs[3, 1:])

    # Aggregation: Sum Impact by Month and Repo
    df_monthly = (
        df.groupby(["month_year", "repo_name"])["total_impact"]
        .sum()
        .unstack(fill_value=0)
    )

    # Filter to top N repos, sum others
    main_cols = [c for c in df_monthly.columns if c in top_repos_list]
    df_stream = df_monthly[main_cols].copy()
    df_stream["Others"] = df_monthly[
        [c for c in df_monthly.columns if c not in top_repos_list]
    ].sum(axis=1)

    # Smooth data for "Flow" look (Rolling average)
    df_stream = df_stream.rolling(window=2, min_periods=1).mean()

    # Prepare stackplot data
    x = df_stream.index.to_timestamp()
    y = [df_stream[col].values for col in df_stream.columns]
    labels = df_stream.columns
    colors = [repo_color_map.get(col, "#3d444d") for col in df_stream.columns]

    ax_stream.stackplot(x, y, labels=labels, colors=colors, alpha=0.9, baseline="zero")
    ax_stream.set_yscale("symlog", linthresh=100)

    ax_stream.set_title(
        "THE BUILDER'S ARC (Code Volume over Time)", color=THEME_FG, fontsize=14, pad=10
    )
    ax_stream.set_facecolor(THEME_BG)
    ax_stream.tick_params(colors="#8b949e")
    for spine in ax_stream.spines.values():
        spine.set_visible(False)
    ax_stream.grid(axis="x", color="#30363d", linestyle="--", alpha=0.5)

    # ==========================
    # 6. LEGEND
    # ==========================
    ax_legend = fig.add_subplot(gs[1:, 0])
    ax_legend.axis("off")

    patches = [mpatches.Patch(color=repo_color_map[r], label=r) for r in top_repos_list]
    patches.append(mpatches.Patch(color=repo_color_map["Other"], label="All Others"))

    ax_legend.legend(
        handles=patches,
        loc="center",
        ncol=1,
        frameon=False,
        labelcolor=THEME_FG,
        title="PROJECT KEY",
        title_fontsize=12,
        fontsize=9,
    )

    # --- SAVE ---
    output_filename = "engineering_dna_profile.svg"
    plt.savefig(output_filename, facecolor=THEME_BG, dpi=150, bbox_inches="tight")
    print(f"✅ DNA Profile Generated: '{output_filename}'")


if __name__ == "__main__":
    create_dashboard()
