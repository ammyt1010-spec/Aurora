"""Theme matplotlib Colmena + gráfico de distribución (barra horizontal
apilada 100%). Nunca se usa el estilo default de matplotlib ni un gráfico
sin valores dentro de los segmentos."""

from __future__ import annotations

import io
import textwrap

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402  (después de matplotlib.use)

from .theme import COLMENA


def _c(name: str) -> str:
    return f"#{COLMENA[name]}"


TRICHOTOMY_COLORS = {
    "favorable_pct": _c("green"),
    "intermediate_pct": _c("yellow"),
    "unfavorable_pct": _c("red"),
}
TRICHOTOMY_LABELS = {
    "favorable_pct": "Favorable",
    "intermediate_pct": "Intermedio",
    "unfavorable_pct": "Desfavorable",
}

_MIN_LABEL_WIDTH = 8.0


def apply_colmena_plot_theme(ax) -> None:
    ax.set_facecolor("white")
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(colors=_c("muted"), labelsize=8, length=0)
    ax.xaxis.label.set_color(_c("muted"))
    ax.yaxis.label.set_color(_c("muted"))
    ax.title.set_color(_c("navy"))
    ax.grid(axis="x", color=_c("line"), linewidth=0.6, alpha=0.8)
    ax.set_axisbelow(True)


def build_trichotomy_chart(results: list[dict]) -> io.BytesIO | None:
    """Horizontal, apilada 100%, sin marco exterior, grid discreta, labels
    internos %, leyenda inferior, tipografía pequeña, alto compacto."""
    plot_results = [r for r in results if not r.get("suppressed") and r.get("unfavorable_pct") is not None]
    if not plot_results:
        return None

    labels = [
        f"{r.get('construct_code') or ''} · {textwrap.shorten(str(r.get('construct_name') or ''), width=25, placeholder='...')}"
        if r.get("construct_name") else str(r.get("construct_code") or "")
        for r in plot_results
    ]
    fig_height = max(1.8, 0.42 * len(plot_results) + 1.1)
    fig, ax = plt.subplots(figsize=(6.3, fig_height), dpi=150)
    apply_colmena_plot_theme(ax)

    y_pos = list(range(len(plot_results)))
    left = [0.0] * len(plot_results)
    for key in ("favorable_pct", "intermediate_pct", "unfavorable_pct"):
        widths = [r.get(key) or 0 for r in plot_results]
        bars = ax.barh(
            y_pos, widths, left=left, color=TRICHOTOMY_COLORS[key],
            label=TRICHOTOMY_LABELS[key], height=0.6,
        )
        for bar, width in zip(bars, widths):
            if width >= _MIN_LABEL_WIDTH:
                ax.text(
                    bar.get_x() + width / 2, bar.get_y() + bar.get_height() / 2,
                    f"{width:.0f}%", ha="center", va="center", fontsize=7,
                    color="white", fontweight="bold",
                )
        left = [total + width for total, width in zip(left, widths)]

    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=8.5, color=_c("text"))
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xticklabels(["0%", "25%", "50%", "75%", "100%"])
    ax.legend(
        loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=3, fontsize=7.5,
        frameon=False, labelcolor=_c("muted"),
    )
    fig.tight_layout()
    return _fig_to_png(fig)


def _fig_to_png(fig) -> io.BytesIO:
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", facecolor="white")
    plt.close(fig)
    buffer.seek(0)
    return buffer
