"""
Server-side chart rendering for the Analytics page — every graph is a
matplotlib/seaborn PNG, never a client-side charting library.

Note on styling: seaborn's sns.set_style()/set_theme() calls internally
overwrite matplotlib's rcParams wholesale, so calling them *after* setting
a custom theme silently clobbers it — that was a real bug here (bars were
rendering on a washed-out light-gray background with barely-legible light
text on top of it). Fixed by applying the theme as a single rcParams.update()
and using sns.despine() per-axes for the clean seaborn look, instead of
sns.set_style(), which is what was fighting the custom theme.
"""
import os
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import seaborn as sns

# ---- report palette, aligned with the application’s new assessment studio ----
BG = '#fffef9'
PANEL = '#fffef9'
GRID = '#e1e7e2'
SPINE = '#c8d2cc'
TEXT = '#53625e'
TITLE = '#17201e'
MUTED = '#71817a'

BLUE = '#5471d8'
INDIGO = '#7657bb'
PURPLE = '#a161b2'
EMERALD = '#2c8370'
AMBER = '#d58a16'
ROSE = '#c8414f'
SLATE = '#71817a'

# Red -> amber -> green so a score-band chart reads at a glance, not just five
# identical bars.
BAND_COLORS = ['#c8414f', '#df7851', '#d58a16', '#94ae4f', '#2c8370']
VERDICT_COLORS = {'correct': EMERALD, 'partial': AMBER, 'incorrect': ROSE, 'pending': SLATE}

plt.rcParams.update({
    'figure.facecolor': BG,
    'savefig.facecolor': BG,
    'axes.facecolor': PANEL,
    'axes.edgecolor': SPINE,
    'axes.labelcolor': TEXT,
    'axes.titlecolor': TITLE,
    'text.color': TEXT,
    'xtick.color': MUTED,
    'ytick.color': MUTED,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'font.size': 11,
    'font.family': 'DejaVu Sans',
    'axes.titlesize': 15,
    'axes.titleweight': 'bold',
    'axes.labelsize': 11,
    'axes.labelweight': 'normal',
    'grid.color': GRID,
    'grid.alpha': 0.6,
    'grid.linewidth': 0.8,
    'legend.facecolor': '#fffef9',
    'legend.edgecolor': SPINE,
    'legend.labelcolor': TEXT,
    'axes.grid': True,
    'axes.axisbelow': True,
})

MEDIA_DIR = Path(__file__).resolve().parent.parent / 'media' / 'analytics'
MEDIA_DIR.mkdir(parents=True, exist_ok=True)


def _style_axes(ax, y_grid_only=True):
    sns.despine(ax=ax, left=False, bottom=False)
    if y_grid_only:
        ax.grid(axis='y')
        ax.grid(axis='x', visible=False)
    ax.tick_params(length=0)


def _save(fig, filename):
    path = MEDIA_DIR / filename
    tmp_path = path.with_suffix(f'.tmp-{os.getpid()}-{id(fig)}.png')
    fig.tight_layout()
    fig.savefig(str(tmp_path), bbox_inches='tight', dpi=170, facecolor=BG)
    plt.close(fig)
    os.replace(tmp_path, path)  # atomic on the same filesystem — no torn reads
    return path


def generate_score_distribution(data, exam_id):
    """Vertical bar: score bands, coloured red->green so it reads at a glance."""
    labels = [d['band'] for d in data]
    counts = [d['count'] for d in data]
    colors = [BAND_COLORS[i % len(BAND_COLORS)] for i in range(len(labels))]

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(labels, counts, color=colors, width=0.62, edgecolor=BG, linewidth=1.5, zorder=3)
    ax.set_title('Score Distribution', pad=14)
    ax.set_xlabel('Score Band')
    ax.set_ylabel('Number of Students')
    ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    for bar in bars:
        height = bar.get_height()
        if height > 0:
            ax.annotate(str(int(height)), xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 5), textcoords='offset points', ha='center', va='bottom',
                        fontsize=11, fontweight='bold', color=TITLE)
    _style_axes(ax)
    return _save(fig, f'{exam_id}_score_dist.png')


def generate_pass_fail(data, exam_id):
    """Donut chart: pass vs fail, with the pass rate written in the centre."""
    passed = data.get('passed_count', 0)
    failed = data.get('failed_count', 0)
    total = passed + failed
    values = [v for v in (passed, failed) if v > 0] or [1]
    labels = ([f'Passed\n{passed}'] if passed else []) + ([f'Failed\n{failed}'] if failed else [])
    colors = ([EMERALD] if passed else []) + ([ROSE] if failed else [])
    if not labels:
        labels, colors = ['No data'], [SLATE]

    fig, ax = plt.subplots(figsize=(6, 6))
    wedges, _ = ax.pie(
        values, colors=colors, startangle=90, counterclock=False,
        wedgeprops={'width': 0.42, 'edgecolor': BG, 'linewidth': 3},
    )
    import math
    for w, label in zip(wedges, labels):
        angle = (w.theta2 + w.theta1) / 2
        x, y = math.cos(math.radians(angle)) * 0.79, math.sin(math.radians(angle)) * 0.79
        ax.text(x, y, label, ha='center', va='center', fontsize=11, fontweight='bold', color=TITLE)

    pass_pct = round(passed / total * 100) if total else 0
    ax.text(0, 0.06, f'{pass_pct}%', ha='center', va='center', fontsize=26, fontweight='bold', color=TITLE)
    ax.text(0, -0.14, 'Pass Rate', ha='center', va='center', fontsize=10, color=MUTED)
    ax.set_title('Pass vs Fail', pad=14)
    ax.set_aspect('equal')
    return _save(fig, f'{exam_id}_pass_fail.png')


def generate_section_comparison(data, exam_id):
    """Vertical bar: MCQ vs Coding average as % of section max."""
    sections = [d['section'] for d in data]
    averages = [d['average_percent'] for d in data]
    colors = [BLUE, PURPLE][:len(sections)]

    fig, ax = plt.subplots(figsize=(7, 5))
    bars = ax.bar(sections, averages, color=colors, width=0.5, edgecolor=BG, linewidth=1.5, zorder=3)
    ax.set_title('Section Performance', pad=14)
    ax.set_ylabel('Average (% of max marks)')
    ax.set_ylim(0, 108)
    for bar in bars:
        height = bar.get_height()
        ax.annotate(f'{height:.0f}%', xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 5), textcoords='offset points', ha='center', va='bottom',
                    fontsize=12, fontweight='bold', color=TITLE)
    _style_axes(ax)
    return _save(fig, f'{exam_id}_section_comparison.png')


def generate_coding_breakdown(data, exam_id):
    """Donut chart: coding verdict mix."""
    verdicts = {d['status']: d['count'] for d in data if d['count'] > 0}
    if not verdicts:
        verdicts = {'No submissions': 1}
        colors = [SLATE]
    else:
        colors = [VERDICT_COLORS.get(k, SLATE) for k in verdicts]

    labels = [f'{k.capitalize()}\n{v}' for k, v in verdicts.items()]
    sizes = list(verdicts.values())

    fig, ax = plt.subplots(figsize=(6, 6))
    wedges, _ = ax.pie(
        sizes, colors=colors, startangle=90, counterclock=False,
        wedgeprops={'width': 0.42, 'edgecolor': BG, 'linewidth': 3},
    )
    import math
    for w, label in zip(wedges, labels):
        angle = (w.theta2 + w.theta1) / 2
        x, y = math.cos(math.radians(angle)) * 0.79, math.sin(math.radians(angle)) * 0.79
        ax.text(x, y, label, ha='center', va='center', fontsize=10.5, fontweight='bold', color=TITLE)
    ax.set_title('Coding Logic Verdicts', pad=14)
    ax.set_aspect('equal')
    return _save(fig, f'{exam_id}_coding_breakdown.png')


def generate_question_accuracy(data, exam_id):
    """Vertical bar: per-question accuracy, coloured by how well the cohort did."""
    labels = [d['label'] for d in data]
    accuracies = [d['accuracy_percent'] for d in data]

    def _tone(pct):
        if pct >= 70:
            return EMERALD
        if pct >= 40:
            return AMBER
        return ROSE

    colors = [_tone(a) for a in accuracies]
    fig, ax = plt.subplots(figsize=(max(8, len(labels) * 0.65), 5))
    bars = ax.bar(labels, accuracies, color=colors, width=0.6, edgecolor=BG, linewidth=1.2, zorder=3)
    ax.axhline(50, color=MUTED, linestyle='--', linewidth=1, alpha=0.6, zorder=2)
    ax.set_title('Per-Question Accuracy', pad=14)
    ax.set_ylabel('Accuracy %')
    ax.set_ylim(0, 108)
    for bar in bars:
        height = bar.get_height()
        ax.annotate(f'{height:.0f}%', xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 4), textcoords='offset points', ha='center', va='bottom',
                    fontsize=9, fontweight='bold', color=TITLE)
    plt.setp(ax.get_xticklabels(), rotation=20, ha='right')
    _style_axes(ax)
    return _save(fig, f'{exam_id}_question_accuracy.png')


def generate_problem_breakdown(data, exam_id):
    """Stacked vertical bar chart: per-problem verdict breakdown."""
    if not data:
        return None
    titles = [d['title'] for d in data]
    correct = [d.get('correct', 0) for d in data]
    partial = [d.get('partial', 0) for d in data]
    incorrect = [d.get('incorrect', 0) for d in data]

    fig, ax = plt.subplots(figsize=(max(7, len(titles) * 1.4), 5.5))
    x = np.arange(len(titles))
    width = 0.55
    ax.bar(x, correct, width, label='Correct', color=EMERALD, edgecolor=BG, linewidth=1.2, zorder=3)
    ax.bar(x, partial, width, bottom=correct, label='Partial', color=AMBER, edgecolor=BG, linewidth=1.2, zorder=3)
    bottoms = [c + p for c, p in zip(correct, partial)]
    ax.bar(x, incorrect, width, bottom=bottoms, label='Incorrect', color=ROSE, edgecolor=BG, linewidth=1.2, zorder=3)

    ax.set_xticks(x)
    ax.set_xticklabels(titles, fontsize=10, rotation=15, ha='right')
    ax.set_ylabel('Submissions')
    ax.set_title('Coding Problem Breakdown', pad=14)
    legend = ax.legend(loc='upper right', frameon=True)
    legend.get_frame().set_alpha(0.9)
    ax.set_ylim(0, max(sum(t) for t in zip(correct, partial, incorrect)) * 1.25 + 1)
    ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    _style_axes(ax)
    return _save(fig, f'{exam_id}_problem_breakdown.png')


def generate_analytics_charts(exam_id, analytics_data):
    """Generate all chart images and return a dict of relative URLs."""
    charts = {}
    # Score distribution
    charts['score_distribution'] = f'/media/analytics/{exam_id}_score_dist.png'
    generate_score_distribution(analytics_data.get('score_distribution', []), exam_id)

    # Pass/Fail
    charts['pass_fail'] = f'/media/analytics/{exam_id}_pass_fail.png'
    generate_pass_fail({
        'passed_count': analytics_data.get('passed_count', 0),
        'failed_count': analytics_data.get('failed_count', 0),
    }, exam_id)

    # Section comparison
    charts['section_comparison'] = f'/media/analytics/{exam_id}_section_comparison.png'
    generate_section_comparison(analytics_data.get('section_comparison', []), exam_id)

    # Coding breakdown
    charts['coding_breakdown'] = f'/media/analytics/{exam_id}_coding_breakdown.png'
    generate_coding_breakdown(analytics_data.get('coding_status_breakdown', []), exam_id)

    # Problem breakdown
    charts['problem_breakdown'] = f'/media/analytics/{exam_id}_problem_breakdown.png'
    res = generate_problem_breakdown(analytics_data.get('problem_stats', []), exam_id)
    if res is None:
        charts['problem_breakdown'] = None

    # Question accuracy
    charts['question_accuracy'] = f'/media/analytics/{exam_id}_question_accuracy.png'
    generate_question_accuracy(analytics_data.get('question_stats', []), exam_id)

    return charts


