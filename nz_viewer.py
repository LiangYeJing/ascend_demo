# -*- coding: utf-8 -*-
import sys, math, csv
import numpy as np
from PyQt5 import QtWidgets, QtCore, QtGui


# ---------------- 逻辑层：ND/NZ 辅助函数 ---------------- #

def pad_to_tiles(arr, h0, w0, pad_val=np.nan):
    H, W = arr.shape
    H1 = math.ceil(H / h0)
    W1 = math.ceil(W / w0)
    Hp, Wp = H1 * h0, W1 * w0
    out = np.full((Hp, Wp), pad_val, dtype=float)
    out[:H, :W] = arr
    return out, (H1, W1, Hp, Wp)

def nd_flatten(arr):
    """Row-major flatten ignoring NaN（跳过 padding）"""
    vals = arr.flatten(order="C")
    return [int(v) if not np.isnan(v) else None for v in vals if not np.isnan(v)]

def nz_order_indices(Hp, Wp, h0, w0):
    """按『列优先的分形块顺序 + 块内行优先』生成线性索引（行主序索引）"""
    H1, W1 = Hp // h0, Wp // w0
    order = []
    for tile_c in range(W1):          # 列优先（外层）
        for tile_r in range(H1):
            base_r = tile_r * h0
            base_c = tile_c * w0
            for i in range(h0):       # 块内行优先（内层）
                for j in range(w0):
                    r = base_r + i
                    c = base_c + j
                    order.append(r * Wp + c)
    return order

def nd_to_nz_flat(arr, h0, w0, pad_val=np.nan):
    """返回 NZ 线性序列（跳过 padding）"""
    padded, (H1, W1, Hp, Wp) = pad_to_tiles(arr, h0, w0, pad_val=pad_val)
    order = nz_order_indices(Hp, Wp, h0, w0)
    nz_seq = []
    for idx in order:
        v = padded.flat[idx]
        if not np.isnan(v):
            nz_seq.append(int(v))
    return padded, (H1, W1, Hp, Wp), nz_seq

def nz_to_nd_from_flat(nz_seq, H, W, h0, w0):
    """给定 NZ 序列，复原成 H×W 的 ND 布局（丢弃 padding）"""
    Hp = math.ceil(H / h0) * h0
    Wp = math.ceil(W / w0) * w0
    order = nz_order_indices(Hp, Wp, h0, w0)
    padded = np.full((Hp, Wp), np.nan, dtype=float)
    k = 0
    for idx in order:
        if k >= len(nz_seq):
            break
        r, c = divmod(idx, Wp)
        if r < H and c < W:
            padded[r, c] = nz_seq[k]
        k += 1
    return padded[:H, :W]


# ---------------- UI 层：表格与绘制代理 ---------------- #

class MatrixTable(QtWidgets.QTableWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.horizontalHeader().hide()
        self.verticalHeader().hide()
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)

    def set_matrix(self, arr):
        H, W = arr.shape
        self.setRowCount(H)
        self.setColumnCount(W)
        mn = np.nanmin(arr) if not np.all(np.isnan(arr)) else 0.0
        mx = np.nanmax(arr) if not np.all(np.isnan(arr)) else 1.0
        rng = (mx - mn) if (mx - mn) != 0 else 1.0

        for r in range(H):
            for c in range(W):
                val = arr[r, c]
                item = QtWidgets.QTableWidgetItem()
                if np.isnan(val):
                    item.setText("")
                    color = QtGui.QColor(200, 200, 200)  # padding: 灰
                else:
                    item.setText(str(int(val)))
                    # 简单热力着色
                    t = (val - mn) / rng
                    color = QtGui.QColor.fromHsvF(0.6 - 0.6 * t, 0.6, 1.0)
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                item.setBackground(color)
                self.setItem(r, c, item)

class TileDelegate(QtWidgets.QStyledItemDelegate):
    """在步骤2绘制 H0×W0 分形边界（粗线）"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.h0 = 0
        self.w0 = 0
        self.show_tiles = False

    def set_params(self, h0, w0, show_tiles):
        self.h0 = max(1, int(h0))
        self.w0 = max(1, int(w0))
        self.show_tiles = bool(show_tiles)

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        if not self.show_tiles:
            return

        row = index.row()
        col = index.column()
        rect = option.rect

        pen = QtGui.QPen(QtGui.QColor(30, 30, 30))
        pen.setWidth(2)
        painter.save()
        painter.setPen(pen)

        # 上边界
        if row % self.h0 == 0:
            painter.drawLine(rect.topLeft(), rect.topRight())
        # 左边界
        if col % self.w0 == 0:
            painter.drawLine(rect.topLeft(), rect.bottomLeft())
        # 右边界（tile 最后一列）
        if (col + 1) % self.w0 == 0:
            painter.drawLine(rect.topRight(), rect.bottomRight())
        # 下边界（tile 最后一行）
        if (row + 1) % self.h0 == 0:
            painter.drawLine(rect.bottomLeft(), rect.bottomRight())

        painter.restore()


# ---------------- 主窗口 ---------------- #

class NZDemo(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ND ↔ NZ 可视化演示（PyQt）")
        self.resize(1000, 700)

        # 控件
        self.h_spin = QtWidgets.QSpinBox(); self.h_spin.setRange(1, 512); self.h_spin.setValue(4)
        self.w_spin = QtWidgets.QSpinBox(); self.w_spin.setRange(1, 512); self.w_spin.setValue(4)
        self.h0_spin = QtWidgets.QSpinBox(); self.h0_spin.setRange(1, 64); self.h0_spin.setValue(2)
        self.w0_spin = QtWidgets.QSpinBox(); self.w0_spin.setRange(1, 64); self.w0_spin.setValue(2)

        self.btn_fill_inc = QtWidgets.QPushButton("递增填充")
        self.btn_fill_rand = QtWidgets.QPushButton("随机填充")
        self.btn_export = QtWidgets.QPushButton("导出当前为CSV")

        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItems(["ND→NZ（正向）", "NZ→ND（逆向）"])

        self.btn_prev = QtWidgets.QPushButton("⟵ 上一步")
        self.btn_next = QtWidgets.QPushButton("下一步 ⟶")
        self.btn_reset = QtWidgets.QPushButton("重置步骤")

        self.seq_nd = QtWidgets.QPlainTextEdit(); self.seq_nd.setReadOnly(True)
        self.seq_nz = QtWidgets.QPlainTextEdit(); self.seq_nz.setReadOnly(True)

        self.table = MatrixTable()
        self.tile_delegate = TileDelegate(self.table)
        self.table.setItemDelegate(self.tile_delegate)

        # 布局
        grid = QtWidgets.QGridLayout(self)
        row = 0
        grid.addWidget(QtWidgets.QLabel("H×W:"), row, 0)
        grid.addWidget(self.h_spin, row, 1)
        grid.addWidget(self.w_spin, row, 2)
        grid.addWidget(QtWidgets.QLabel("分形块 H0×W0:"), row, 3)
        grid.addWidget(self.h0_spin, row, 4)
        grid.addWidget(self.w0_spin, row, 5)
        grid.addWidget(self.mode_combo, row, 6, 1, 2)

        row += 1
        grid.addWidget(self.btn_fill_inc, row, 0, 1, 2)
        grid.addWidget(self.btn_fill_rand, row, 2, 1, 2)
        grid.addWidget(self.btn_export, row, 4, 1, 2)
        grid.addWidget(self.btn_prev, row, 6)
        grid.addWidget(self.btn_next, row, 7)

        row += 1
        grid.addWidget(self.btn_reset, row, 6, 1, 2)

        row += 1
        grid.addWidget(self.table, row, 0, 1, 8)

        row += 1
        grid.addWidget(QtWidgets.QLabel("ND（行主序）线性序列："), row, 0, 1, 8)
        row += 1
        grid.addWidget(self.seq_nd, row, 0, 1, 8)
        row += 1
        grid.addWidget(QtWidgets.QLabel("NZ（分形列优先 + 块内行优先）线性序列："), row, 0, 1, 8)
        row += 1
        grid.addWidget(self.seq_nz, row, 0, 1, 8)

        # 状态
        self.step = 0                 # 0: ND, 1: pad, 2: 分块示意, 3: NZ顺序（正向）/ 逆向 0: NZ序列, 1: 复原ND
        self.base = None              # 原始 H×W
        self.padded = None            # pad 后 Hp×Wp
        self.nz_seq = None
        self.update_base_incremental()

        # 信号
        self.btn_fill_inc.clicked.connect(self.update_base_incremental)
        self.btn_fill_rand.clicked.connect(self.update_base_random)
        self.btn_prev.clicked.connect(self.prev_step)
        self.btn_next.clicked.connect(self.next_step)
        self.btn_reset.clicked.connect(self.reset_steps)
        self.mode_combo.currentIndexChanged.connect(self.reset_steps)
        self.btn_export.clicked.connect(self.export_csv)

        self.h_spin.valueChanged.connect(self.reset_steps)
        self.w_spin.valueChanged.connect(self.reset_steps)
        self.h0_spin.valueChanged.connect(self.reset_steps)
        self.w0_spin.valueChanged.connect(self.reset_steps)

        self.render()

    # --- 数据准备 --- #
    def current_params(self):
        return self.h_spin.value(), self.w_spin.value(), self.h0_spin.value(), self.w0_spin.value()

    def update_base_incremental(self):
        H, W, *_ = self.current_params()
        self.base = np.arange(H * W, dtype=float).reshape(H, W)
        self.reset_steps()

    def update_base_random(self):
        H, W, *_ = self.current_params()
        rng = np.random.default_rng()
        self.base = rng.integers(0, 99, size=(H, W)).astype(float)
        self.reset_steps()

    def export_csv(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "导出 CSV", "matrix.csv", "CSV Files (*.csv)")
        if not path:
            return
        arr = self.get_matrix_for_current_step()
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            for r in range(arr.shape[0]):
                row = ["" if np.isnan(x) else int(x) for x in arr[r]]
                writer.writerow(row)
        QtWidgets.QMessageBox.information(self, "成功", f"已导出到：{path}")

    # --- 步骤控制 --- #
    def reset_steps(self):
        self.step = 0
        self.padded, _, self.nz_seq = nd_to_nz_flat(self.base, self.h0_spin.value(), self.w0_spin.value())
        self.render()

    def prev_step(self):
        if self.step > 0:
            self.step -= 1
            self.render()

    def next_step(self):
        # 正向：0 ND → 1 pad → 2 分块示意 → 3 NZ 线性
        # 逆向：0 NZ线性 → 1 复原ND
        mode = self.mode_combo.currentIndex()
        if mode == 0:
            self.step = min(self.step + 1, 3)
        else:
            self.step = min(self.step + 1, 1)
        self.render()

    def get_matrix_for_current_step(self):
        H, W, h0, w0 = self.current_params()
        mode = self.mode_combo.currentIndex()

        if mode == 0:  # ND→NZ
            if self.step == 0:
                return self.base
            elif self.step == 1:
                return self.padded
            elif self.step == 2:
                # 只返回 pad 后矩阵；块边界由 TileDelegate 绘制
                return self.padded
            else:
                # 显示 pad 后矩阵，便于对照 NZ 线性序列
                return self.padded
        else:          # NZ→ND
            if self.step == 0:
                # 直接展示 NZ 线性序列（单列矩阵显示）
                col = np.array(self.nz_seq, dtype=float).reshape(-1, 1)
                return col
            else:
                restored = nz_to_nd_from_flat(self.nz_seq, H, W, h0, w0)
                return restored

    # --- 渲染 --- #
    def render(self):
        arr = self.get_matrix_for_current_step()
        self.table.set_matrix(arr)

        # 文本框：ND/NZ 序列
        nd_seq = nd_flatten(self.base)
        self.seq_nd.setPlainText(str(nd_seq))
        _, _, nz_seq = nd_to_nz_flat(self.base, self.h0_spin.value(), self.w0_spin.value())
        self.seq_nz.setPlainText(str(nz_seq))

        # 在“步骤2/分块示意”时画 tile 边界；其他步骤关闭
        mode = self.mode_combo.currentIndex()
        show_tiles = (mode == 0 and self.step == 2)
        self.tile_delegate.set_params(self.h0_spin.value(), self.w0_spin.value(), show_tiles)
        self.table.viewport().update()

        # 状态提示
        hints = {
            (0,0): "步骤 0/3：ND 原始布局（行主序）。",
            (0,1): "步骤 1/3：pad 到分形整数倍（灰格为 padding，不参与序列）。",
            (0,2): "步骤 2/3：分块示意（已用粗线标出 H0×W0 分形块）。",
            (0,3): "步骤 3/3：NZ 线性序列已在下方展示；表格仍显示 pad 后物理布局用于对照。",
            (1,0): "步骤 0/1：NZ 线性序列（列优先块 + 块内行优先）。",
            (1,1): "步骤 1/1：根据 NZ 序列复原出的 ND（已裁去 padding）。",
        }
        self.setWindowTitle("ND ↔ NZ 可视化演示（PyQt） - " + hints[(mode, self.step)])


# ---------------- 入口 ---------------- #

def main():
    app = QtWidgets.QApplication(sys.argv)
    w = NZDemo()
    w.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
