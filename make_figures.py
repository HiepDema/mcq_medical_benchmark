#!/usr/bin/env python3
"""Sinh biểu đồ cho REPORT_GEMMA_V2.md.

  python make_figures.py            # -> figures/*.png

Số liệu đọc thẳng từ processed_data_v2/ và results_v2/, không nhập tay con số nào,
nên biểu đồ và bảng trong report không thể lệch nhau.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from analyze_results import DIFF_NAME, difficulty  # noqa: E402
from eval_qwen3vl import load_items  # noqa: E402

P, R, FIG = ROOT / "processed_data_v2", ROOT / "results_v2", ROOT / "figures"

# Bảng màu tham chiếu của skill dataviz, chế độ sáng, 4 khe đầu.
# Đã chạy validate_palette.js: mọi kiểm tra PASS; riêng aqua và vàng dưới 3:1 so
# với nền nên bắt buộc có nhãn trực tiếp (đã thêm) hoặc bảng đi kèm (report có).
SURFACE = "#fcfcfb"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#d8d7d2"
# 7 khe dau cua bang mau tham chieu. Da chay validate_palette.js voi ca 7:
# moi kiem tra PASS; ba mau aqua/vang/hong duoi 3:1 nen bat buoc co nhan truc tiep
# hoac bang so di kem (report co ca hai).
MODELS = {
    "Qwen3-0.6B": ("0.6b", "#2a78d6"),
    "Qwen3-4B": ("4b", "#eb6834"),
    "Gemma3-1B": ("gemma1b", "#1baf7a"),
    "Gemma3-4B": ("gemma4b", "#eda100"),
    "GPT-4o-mini": ("gpt-4o-mini", "#e87ba4"),
    "DeepSeek-v4-Flash": ("deepseek-v4-flash-0731", "#008300"),
    "Gemini-2.5-Flash": ("gemini-25-flash", "#4a3aa7"),
}
NEUTRAL = "#9a998f"          # dùng cho "đáp án chuẩn" — mốc tham chiếu, không phải một series

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "font.size": 10.5, "font.family": "DejaVu Sans",
    "text.color": INK, "axes.labelcolor": INK2, "axes.edgecolor": GRID,
    "xtick.color": INK2, "ytick.color": INK2,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "grid.alpha": 0.7,
    "axes.axisbelow": True, "legend.frameon": False,
})
PCT = FuncFormatter(lambda v, _: f"{v:.0f}%")


def titles(ax, title, sub, size=13):
    """Phụ đề đặt bằng set_title, tiêu đề đẩy lên trên nó — nếu đặt cả hai cùng
    một mốc y thì chúng chồng lên nhau."""
    ax.set_title(sub, loc="left", fontsize=9.5, color=INK2, pad=10)
    ax.text(0, 1.085, title, transform=ax.transAxes, fontsize=size,
            fontweight="bold", color=INK, va="bottom")


def spread(vals, gap):
    """Đẩy các nhãn quá sát nhau ra xa theo trục dọc, giữ nguyên thứ tự."""
    order = sorted(range(len(vals)), key=lambda k: vals[k])
    out = list(vals)
    for a, b in zip(order, order[1:]):
        if out[b] - out[a] < gap:
            out[b] = out[a] + gap
    return out


def preds(tag: str, dtag: str) -> dict[int, set]:
    d = json.loads((R / f"eval_{dtag}_{tag}.json").read_text(encoding="utf-8"))
    return {x["index"]: set(x["pred"]) for x in d["per_item"]}


def save(fig, name: str):
    FIG.mkdir(exist_ok=True)
    fig.savefig(FIG / name, dpi=200, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)
    print(f"  -> figures/{name}")


# --------------------------------------------------------------- dữ liệu chung
items = {it["index"]: it for it in load_items(P / "final_benchmark_mixed.json")}
raw = json.loads((P / "final_benchmark_mixed.json").read_text(encoding="utf-8"))
prov = json.loads((P / "final_benchmark_mixed_provenance.json").read_text(encoding="utf-8"))
diff = {i: difficulty(raw[i].get("difficultLevel")) for i in range(len(raw))}
subset = {p["index"]: p["subset"] for p in prov}
PM = {n: preds(t, "mixed") for n, (t, _) in MODELS.items()}


# ============================================================ 1. bảng điểm chung
def fig_scores():
    DS = [("Bộ A — nhiều đáp án", "final_benchmark_9368.json", "multi"),
          ("Bộ B — hỗn hợp", "final_benchmark_mixed.json", "mixed"),
          ("Đối chứng của A", "final_benchmark_9368_single.json", "single"),
          ("Đối chứng của B", "final_benchmark_mixed_single.json", "mixedsingle")]
    data = []
    for lbl, f, dtag in DS:
        its = load_items(P / f)
        row = []
        for n, (t, _) in MODELS.items():
            p = preds(t, dtag)
            row.append(100 * sum(1 for it in its if p[it["index"]] == it["gold"]) / len(its))
        data.append((lbl, row))

    fig, ax = plt.subplots(figsize=(9.5, 6.4))
    h, gap = 0.115, 0.012
    for k, (name, (_, color)) in enumerate(MODELS.items()):
        ys = [i + (k - 3) * (h + gap) for i in range(len(DS))]
        vals = [row[k] for _, row in data]
        ax.barh(ys, vals, height=h, color=color, label=name, linewidth=0)
        for y, v in zip(ys, vals):
            ax.text(v + 0.7, y, f"{v:.1f}%".replace(".", ","), va="center",
                    fontsize=9, color=INK2)
    ax.set_yticks(range(len(DS)))
    ax.set_yticklabels([lbl for lbl, _ in data])
    ax.invert_yaxis()
    ax.set_xlim(0, 86)
    ax.xaxis.set_major_formatter(PCT)
    ax.set_xlabel("exact match")
    ax.grid(axis="y", visible=False)
    titles(ax, "Điểm bảy model trên bốn bộ dữ liệu",
           "Ba model API bỏ xa bốn model mở; xếp hạng giữ nguyên trên cả bốn bộ.")
    ax.legend(loc="upper left", bbox_to_anchor=(0, -0.11), ncols=4, fontsize=9)
    save(fig, "01_bang_diem.png")


# ============================================================ 2. theo độ khó
def fig_difficulty():
    lv = [1, 2, 3, 4]
    ns = [sum(1 for i in items if diff[i] == l) for l in lv]
    fig, ax = plt.subplots(figsize=(8.4, 5.2))
    for name, (_, color) in MODELS.items():
        ys = []
        for l in lv:
            idx = [i for i in items if diff[i] == l]
            ys.append(100 * sum(1 for i in idx if PM[name][i] == items[i]["gold"]) / len(idx))
        ax.plot(lv[:3], ys[:3], color=color, linewidth=2, marker="o",
                markersize=8, label=name, zorder=3)
        # bậc 4 chỉ 39 câu -> vẽ đứt để không đọc như một xu hướng
        ax.plot(lv[2:], ys[2:], color=color, linewidth=2, marker="o",
                markersize=8, linestyle=(0, (2, 2)), zorder=3)
        ax.annotate(f"{ys[0]:.1f}%".replace(".", ","), (lv[0], ys[0]),
                    xytext=(-8, 0), textcoords="offset points",
                    ha="right", va="center", fontsize=9, color=INK2)
    ax.set_xticks(lv)
    ax.set_xticklabels([f"{DIFF_NAME[l].split(' — ')[1]}\nn = {n:,}".replace(",", ".")
                        for l, n in zip(lv, ns)])
    ax.set_xlim(0.45, 4.35)
    ax.set_ylim(0, 62)
    ax.yaxis.set_major_formatter(PCT)
    ax.set_ylabel("exact match")
    ax.grid(axis="x", visible=False)
    titles(ax, "Điểm theo độ khó do người ra đề gán — Bộ B",
           "Mọi model đủ mạnh đều giảm đều khi độ khó tăng; hai model nhỏ đi ngang. "
           "Đoạn đứt: bậc 4 chỉ có 39 câu.")
    ax.legend(loc="upper right", fontsize=9.5)
    save(fig, "02_do_kho.png")


# ============================================= 3. phân bố số ô model chọn
def fig_counts():
    buckets = [1, 2, 3, 4, 5]
    gold = Counter(len(items[i]["gold"]) for i in items)
    panels = [("Đáp án chuẩn", NEUTRAL, [gold[b] for b in buckets])]
    for name in MODELS:
        c = Counter(len(PM[name][i]) for i in items)
        panels.append((name, MODELS[name][1], [c[b] for b in buckets]))

    fig, axes = plt.subplots(1, 8, figsize=(19, 3.9), sharey=True)
    for ax, (name, color, vals) in zip(axes, panels):
        ax.bar(buckets, vals, width=0.68, color=color, linewidth=0)
        for b, v in zip(buckets, vals):
            if v:
                ax.text(b, v + 230, f"{v:,}".replace(",", "."), ha="center",
                        fontsize=8, color=INK2, rotation=90 if v > 3000 else 0)
        ax.set_title(name, fontsize=9, color=INK, pad=8)
        ax.set_xticks(buckets)
        ax.set_xlabel("số ô chọn")
        ax.grid(axis="x", visible=False)
        ax.set_ylim(0, 13200)
    axes[0].set_ylabel("số câu")
    axes[0].yaxis.set_major_formatter(FuncFormatter(
        lambda v, _: f"{v:,.0f}".replace(",", ".")))
    fig.suptitle("Model chọn bao nhiêu ô mỗi câu — Bộ B (11.368 câu)",
                 x=0.005, ha="left", fontsize=13, fontweight="bold", y=1.06)
    fig.text(0.005, 0.99, "Model càng mạnh, hình dạng càng bám sát đáp án chuẩn. Hai model nhỏ "
                          "dồn gần như toàn bộ vào 2 ô, bất kể câu hỏi có mấy đáp án.", ha="left", fontsize=9.5, color=INK2)
    save(fig, "03_so_o_chon.png")


# ============================== 4. được báo vs không được báo (2.000 câu)
def fig_told():
    idx1 = [i for i in items if subset[i] == "single_1_dap_an"]
    its = {it["index"]: it for it in load_items(P / "final_benchmark_mixed_single.json")}
    fig, ax = plt.subplots(figsize=(8.2, 5.2))
    names, A, B = [], [], []
    for name, (t, color) in MODELS.items():
        ps, pm = preds(t, "mixedsingle"), PM[name]
        names.append(name)
        A.append(100 * sum(1 for i in idx1 if ps[i] == its[i]["gold"]) / len(idx1))
        B.append(100 * sum(1 for i in idx1 if pm[i] == items[i]["gold"]) / len(idx1))
    Ay, By = spread(A, 2.4), spread(B, 2.4)
    for name, a, b, ay, by in zip(names, A, B, Ay, By):
        color = MODELS[name][1]
        ax.plot([0, 1], [a, b], color=color, linewidth=2, marker="o",
                markersize=9, label=name, zorder=3)
        ax.text(-0.05, ay, f"{a:.1f}%".replace(".", ","), ha="right", va="center",
                fontsize=9.5, color=INK2)
        ax.text(1.05, by, f"{b:.1f}%".replace(".", ","), ha="left", va="center",
                fontsize=9.5, color=INK2)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(['Được báo trước\n"đúng 1 đáp án"', "Không được báo\n(bộ hỗn hợp)"])
    ax.set_xlim(-0.42, 1.42)
    ax.set_ylim(-2, 82)
    ax.yaxis.set_major_formatter(PCT)
    ax.set_ylabel("exact match")
    ax.grid(axis="x", visible=False)
    titles(ax, "Cùng 2.000 câu một đáp án — chỉ khác việc có báo trước số đáp án",
           "Bỏ manh mối về số đáp án đi thì mọi model đều tụt — nhưng mức tụt rất khác nhau.", size=12)
    ax.legend(loc="center", fontsize=9.5)
    save(fig, "04_bao_truoc.png")


# ==================================== 5. tran bo de: cong don tung model
def fig_ceiling():
    """Them dan tung model, con bao nhieu cau KHONG AI lam duoc."""
    order = list(MODELS)                       # yeu -> manh, dung thu tu trong report
    order.sort(key=lambda n: sum(1 for i in items if PM[n][i] == items[i]["gold"]))
    ys, solved = [], set()
    for n in order:
        solved |= {i for i in items if PM[n][i] == items[i]["gold"]}
        ys.append(100 * (len(items) - len(solved)) / len(items))

    fig, ax = plt.subplots(figsize=(9, 5.4))
    xs = range(1, len(order) + 1)
    ax.plot(xs, ys, color="#2a78d6", linewidth=2, marker="o", markersize=9, zorder=3)
    for x, y in zip(xs, ys):
        ax.annotate(f"{y:.1f}%".replace(".", ","), (x, y), xytext=(0, 11),
                    textcoords="offset points", ha="center", fontsize=9.5, color=INK2)
    # hai moc duoc noi trong report
    ax.axvline(4, color=GRID, linewidth=1.2, zorder=1)
    ax.annotate("4 model mở", (4, 20), xytext=(-8, 0), textcoords="offset points",
                ha="right", fontsize=9.5, color=INK2)
    ax.annotate("+ 3 model API", (4, 20), xytext=(8, 0), textcoords="offset points",
                ha="left", fontsize=9.5, color=INK2)
    ax.set_xticks(list(xs))
    ax.set_xticklabels([f"+{n}" if k else n for k, n in enumerate(order)],
                       rotation=30, ha="right", fontsize=9)
    ax.set_ylim(0, 113)
    ax.yaxis.set_major_formatter(PCT)
    ax.set_yticks([0, 20, 40, 60, 80, 100])
    ax.set_ylabel("% câu KHÔNG model nào làm được")
    ax.grid(axis="x", visible=False)
    titles(ax, "Trần bộ đề — cộng dồn từng model",
           "Thêm ba model API cắt hơn một nửa vùng \"không ai làm được\": 69,8% → 33,3%.")
    save(fig, "05_tran_bo_de.png")


# ============================ 6. kien thuc vs hieu chinh (2.000 cau 1 dap an)
def fig_knowledge():
    idx1 = [i for i in items if subset[i] == "single_1_dap_an"]
    n = len(idx1)
    fig, ax = plt.subplots(figsize=(8.2, 6.2))
    ax.plot([0, 100], [0, 100], color=GRID, linewidth=1.5, zorder=1)
    ax.annotate("biết bao nhiêu, đúng bấy nhiêu", (74, 74), rotation=39,
                fontsize=9, color=INK2, ha="center", va="bottom")
    for name, (t, color) in MODELS.items():
        x = 100 * sum(1 for i in idx1 if items[i]["gold"] <= PM[name][i]) / n
        y = 100 * sum(1 for i in idx1 if PM[name][i] == items[i]["gold"]) / n
        ax.plot([x, x], [y, x], color=GRID, linewidth=1.2, zorder=2)   # khoang hut
        ax.scatter([x], [y], s=140, color=color, zorder=4, linewidth=0)
        # lech nhan rieng cho tung diem: goc duoi trai bon diem rat sat nhau
        OFF = {"Gemma3-1B": (-14, -20, "right"), "Qwen3-0.6B": (14, 10, "left"),
               "Gemma3-4B": (0, -22, "center"), "Qwen3-4B": (0, 13, "center"),
               "GPT-4o-mini": (0, -22, "center"), "DeepSeek-v4-Flash": (-12, 12, "right"),
               "Gemini-2.5-Flash": (-12, 12, "right")}
        dx, dy, ha = OFF[name]
        ax.annotate(name, (x, y), xytext=(dx, dy), textcoords="offset points",
                    ha=ha, fontsize=9.5, color=INK)
    ax.set_xlim(45, 100); ax.set_ylim(-4, 100)
    ax.xaxis.set_major_formatter(PCT); ax.yaxis.set_major_formatter(PCT)
    ax.set_xlabel("BIẾT đáp án — đáp án đúng nằm trong tập model chọn")
    ax.set_ylabel("TRẢ LỜI ĐÚNG — chọn khít đúng một ô")
    titles(ax, "Biết đáp án không có nghĩa là trả lời đúng",
           "2.000 câu một đáp án. Càng xa đường chéo, model càng không biết dừng lại.",
           size=12.5)
    save(fig, "06_kien_thuc_vs_hieu_chinh.png")


if __name__ == "__main__":
    fig_scores()
    fig_difficulty()
    fig_counts()
    fig_told()
    fig_ceiling()
    fig_knowledge()
