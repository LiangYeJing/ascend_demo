# details.py
import random
import math

try:
    from PyQt5.QtCore import Qt, QTimer
    from PyQt5.QtWidgets import (
        QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QGridLayout, QTabWidget, QSpinBox, QTableWidget, QTableWidgetItem,
        QGroupBox, QDoubleSpinBox, QProgressBar
    )
    from PyQt5.QtGui import QColor
except Exception:
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtWidgets import (
        QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QGridLayout, QTabWidget, QSpinBox, QTableWidget, QTableWidgetItem,
        QGroupBox, QDoubleSpinBox, QProgressBar
    )
    from PyQt6.QtGui import QColor


# ---------- 小工具 ----------
def make_table(r, c, cell_sz=200):
    t = QTableWidget(r, c)
    t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    t.horizontalHeader().setVisible(False)
    t.verticalHeader().setVisible(False)
    t.setShowGrid(True)
    sz = max(26, int(cell_sz / max(1, max(r, c))))
    for j in range(c): t.setColumnWidth(j, sz)
    for i in range(r): t.setRowHeight(i, sz)
    return t

def set_cell(t: QTableWidget, i, j, val, bold=False):
    it = QTableWidgetItem(str(val))
    it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
    if bold:
        f = it.font(); f.setBold(True); it.setFont(f)
    t.setItem(i, j, it)

def clear_hl(t: QTableWidget):
    r = t.rowCount(); c = t.columnCount()
    for i in range(r):
        for j in range(c):
            it = t.item(i, j)
            if it: it.setBackground(QColor(255,255,255))

def hl_cell(t: QTableWidget, i, j, color=QColor(255,240,170)):
    it = t.item(i, j)
    if it: it.setBackground(color)

def hl_row(t: QTableWidget, i, color=QColor(190,235,255)):
    c = t.columnCount()
    for j in range(c):
        it = t.item(i, j)
        if it: it.setBackground(color)

def hl_col(t: QTableWidget, j, color=QColor(210,255,190)):
    r = t.rowCount()
    for i in range(r):
        it = t.item(i, j)
        if it: it.setBackground(color)

def clamp(x, a, b): return max(a, min(b, x))

# 简易色图：次数越大越红
def heat_color(cnt, mx):
    if mx <= 0: return QColor(255,255,255)
    ratio = clamp(cnt / mx, 0.0, 1.0)
    r = int(255 * ratio)
    g = int(255 * (1 - 0.5*ratio))
    b = int(255 * (1 - ratio))
    return QColor(r, g, b)


# =============== MTE 细化页 ===============
class MteDetailDialog(QDialog):
    """
    四个子页：
      1) Decompress：8bit→16bit（演示位宽扩展/查表）；
      2) Interleave/Pack：两通道交错打包（C0/C1）；
      3) Transpose：5×3 → 3×5；
      4) im2col：把 (H×W×C) 小块滑窗展平为 (HW)×(KhKwC)；并统计 L1->L0A/L1->L0B 的位数。
    """
    def __init__(self, parent=None, bits_in=8, bits_out=16, elem_bits=16, Tm=4, Tn=4):
        super().__init__(parent)
        self.setWindowTitle("MTE · 解压 / 拼接 / 转置 / im2col")
        self.resize(920, 720)
        self.elem_bits = elem_bits
        self.Tm = Tm; self.Tn = Tn

        root = QVBoxLayout(self)
        self.tabs = QTabWidget(); root.addWidget(self.tabs)

        self.page_decomp = self._build_decompress_tab(bits_in, bits_out)
        self.page_pack   = self._build_interleave_tab()
        self.page_trans  = self._build_transpose_tab()
        self.page_im2col = self._build_im2col_tab()

        self.tabs.addTab(self.page_decomp, "Decompress")
        self.tabs.addTab(self.page_pack,   "Interleave / Pack")
        self.tabs.addTab(self.page_trans,  "Transpose")
        self.tabs.addTab(self.page_im2col, "im2col + BW")

    # ---- Decompress ----
    def _build_decompress_tab(self, in_bits, out_bits):
        w = QWidget(); lay = QVBoxLayout(w)
        ctl = QHBoxLayout()
        self.dec_btn_start = QPushButton("Start")
        self.dec_btn_step  = QPushButton("Step")
        self.dec_btn_reset = QPushButton("Reset")
        self.dec_bits_in   = QSpinBox(); self.dec_bits_in.setRange(4,16); self.dec_bits_in.setValue(in_bits)
        self.dec_bits_out  = QSpinBox(); self.dec_bits_out.setRange(8,32); self.dec_bits_out.setValue(out_bits)
        ctl.addWidget(QLabel("in bits:"));  ctl.addWidget(self.dec_bits_in)
        ctl.addWidget(QLabel("out bits:")); ctl.addWidget(self.dec_bits_out)
        ctl.addStretch(1)
        for b in (self.dec_btn_start,self.dec_btn_step,self.dec_btn_reset): ctl.addWidget(b)
        lay.addLayout(ctl)

        grid = QGridLayout(); lay.addLayout(grid)
        self.dec_src = make_table(4, 6)
        self.dec_dst = make_table(4, 6)
        grid.addWidget(QLabel("Compressed (src)"), 0,0)
        grid.addWidget(QLabel("Decompressed (dst)"), 0,1)
        grid.addWidget(self.dec_src, 1,0)
        grid.addWidget(self.dec_dst, 1,1)

        self._dec_i = 0; self._dec_j = 0
        self._dec_timer = QTimer(self); self._dec_timer.timeout.connect(self._dec_tick)
        self._dec_fill()

        self.dec_btn_start.clicked.connect(lambda: self._dec_timer.start(180))
        self.dec_btn_step.clicked.connect(self._dec_tick)
        self.dec_btn_reset.clicked.connect(self._dec_reset)
        return w

    def _dec_fill(self):
        random.seed(0)
        for i in range(self.dec_src.rowCount()):
            for j in range(self.dec_src.columnCount()):
                v = random.randint(0, 255)
                set_cell(self.dec_src, i,j, v)
                set_cell(self.dec_dst, i,j, 0)

    def _dec_reset(self):
        self._dec_timer.stop()
        self._dec_i = self._dec_j = 0
        clear_hl(self.dec_src); clear_hl(self.dec_dst)
        self._dec_fill()

    def _dec_tick(self):
        r, c = self.dec_src.rowCount(), self.dec_src.columnCount()
        clear_hl(self.dec_src); clear_hl(self.dec_dst)
        it = self.dec_src.item(self._dec_i, self._dec_j)
        if it:
            v = int(it.text())
            out_bits = self.dec_bits_out.value()
            scale = max(1, (1 << out_bits) // 256)
            v2 = v * scale
            set_cell(self.dec_dst, self._dec_i, self._dec_j, v2, bold=True)
            hl_cell(self.dec_src, self._dec_i, self._dec_j, QColor(255,240,170))
            hl_cell(self.dec_dst, self._dec_i, self._dec_j, QColor(190,255,200))

        self._dec_j += 1
        if self._dec_j >= c:
            self._dec_j = 0
            self._dec_i += 1
            if self._dec_i >= r:
                self._dec_timer.stop()

    # ---- Interleave / Pack ----
    def _build_interleave_tab(self):
        w = QWidget(); lay = QVBoxLayout(w)
        ctl = QHBoxLayout()
        self.pack_btn_start = QPushButton("Start")
        self.pack_btn_step  = QPushButton("Step")
        self.pack_btn_reset = QPushButton("Reset")
        ctl.addStretch(1)
        for b in (self.pack_btn_start,self.pack_btn_step,self.pack_btn_reset): ctl.addWidget(b)
        lay.addLayout(ctl)

        grid = QGridLayout(); lay.addLayout(grid)
        self.pack_A = make_table(4, 4)
        self.pack_B = make_table(4, 4)
        self.pack_out = make_table(4, 8)
        grid.addWidget(QLabel("Plane C0"), 0,0)
        grid.addWidget(QLabel("Plane C1"), 0,1)
        grid.addWidget(QLabel("Interleave (C0,C1) → Packed"), 0,2)
        grid.addWidget(self.pack_A, 1,0)
        grid.addWidget(self.pack_B, 1,1)
        grid.addWidget(self.pack_out, 1,2)

        random.seed(1)
        for i in range(4):
            for j in range(4):
                set_cell(self.pack_A, i,j, random.randint(1,9))
                set_cell(self.pack_B, i,j, random.randint(1,9))
        for i in range(4):
            for j in range(8): set_cell(self.pack_out, i,j, 0)

        self._pk_i = 0; self._pk_j = 0; self._pk_timer = QTimer(self); self._pk_timer.timeout.connect(self._pk_tick)
        self.pack_btn_start.clicked.connect(lambda: self._pk_timer.start(160))
        self.pack_btn_step.clicked.connect(self._pk_tick)
        self.pack_btn_reset.clicked.connect(self._pk_reset)
        return w

    def _pk_reset(self):
        self._pk_timer.stop()
        self._pk_i = self._pk_j = 0
        clear_hl(self.pack_A); clear_hl(self.pack_B); clear_hl(self.pack_out)
        for i in range(4):
            for j in range(8): set_cell(self.pack_out, i,j, 0)

    def _pk_tick(self):
        i, j = self._pk_i, self._pk_j
        if i>=4: self._pk_timer.stop(); return
        clear_hl(self.pack_A); clear_hl(self.pack_B); clear_hl(self.pack_out)

        src_j = j//2
        val = int(self.pack_A.item(i, src_j).text()) if j%2==0 else int(self.pack_B.item(i, src_j).text())
        set_cell(self.pack_out, i, j, val, bold=True)
        if j%2==0: hl_cell(self.pack_A, i, src_j, QColor(255,240,170))
        else:       hl_cell(self.pack_B, i, src_j, QColor(255,240,170))
        hl_cell(self.pack_out, i, j, QColor(190,255,200))

        self._pk_j += 1
        if self._pk_j >= 8:
            self._pk_j = 0
            self._pk_i += 1

    # ---- Transpose ----
    def _build_transpose_tab(self):
        w = QWidget(); lay = QVBoxLayout(w)
        ctl = QHBoxLayout()
        self.tp_btn_start = QPushButton("Start")
        self.tp_btn_step  = QPushButton("Step")
        self.tp_btn_reset = QPushButton("Reset")
        ctl.addStretch(1)
        for b in (self.tp_btn_start,self.tp_btn_step,self.tp_btn_reset): ctl.addWidget(b)
        lay.addLayout(ctl)

        grid = QGridLayout(); lay.addLayout(grid)
        self.tp_src = make_table(5, 3)
        self.tp_dst = make_table(3, 5)
        grid.addWidget(QLabel("Src (5×3)"), 0,0)
        grid.addWidget(QLabel("Dst = Transpose (3×5)"), 0,1)
        grid.addWidget(self.tp_src, 1,0)
        grid.addWidget(self.tp_dst, 1,1)

        random.seed(2)
        for i in range(5):
            for j in range(3):
                set_cell(self.tp_src, i,j, random.randint(10,99))
        for i in range(3):
            for j in range(5):
                set_cell(self.tp_dst, i,j, 0)

        self._tp_i = 0; self._tp_j = 0; self._tp_timer = QTimer(self); self._tp_timer.timeout.connect(self._tp_tick)
        self.tp_btn_start.clicked.connect(lambda: self._tp_timer.start(120))
        self.tp_btn_step.clicked.connect(self._tp_tick)
        self.tp_btn_reset.clicked.connect(self._tp_reset)
        return w

    def _tp_reset(self):
        self._tp_timer.stop(); self._tp_i = self._tp_j = 0
        clear_hl(self.tp_src); clear_hl(self.tp_dst)
        for i in range(3):
            for j in range(5): set_cell(self.tp_dst, i,j, 0)

    def _tp_tick(self):
        R, C = 5, 3
        if self._tp_i>=R: self._tp_timer.stop(); return
        clear_hl(self.tp_src); clear_hl(self.tp_dst)
        v = int(self.tp_src.item(self._tp_i, self._tp_j).text())
        set_cell(self.tp_dst, self._tp_j, self._tp_i, v, bold=True)
        hl_cell(self.tp_src, self._tp_i, self._tp_j, QColor(255,240,170))
        hl_cell(self.tp_dst, self._tp_j, self._tp_i, QColor(190,255,200))

        self._tp_j += 1
        if self._tp_j >= C:
            self._tp_j = 0
            self._tp_i += 1

    # ---- im2col + BW ----
    def _build_im2col_tab(self):
        w = QWidget(); lay = QVBoxLayout(w)
        ctl = QHBoxLayout()
        self.im_btn_start = QPushButton("Start")
        self.im_btn_step  = QPushButton("Step")
        self.im_btn_reset = QPushButton("Reset")
        # 简化：H×W=4×4, Kh×Kw=3×3, C=2
        self.H,self.W,self.C = 4,4,2
        self.Kh,self.Kw = 3,3
        ctl.addWidget(QLabel("H×W=4×4, C=2, Kh×Kw=3×3（演示）")); ctl.addStretch(1)
        for b in (self.im_btn_start,self.im_btn_step,self.im_btn_reset): ctl.addWidget(b)
        lay.addLayout(ctl)

        grid = QGridLayout(); lay.addLayout(grid)
        self.im_src  = make_table(self.H*self.C, self.W)  # 展示为 8×4（两个通道堆叠）
        self.im_dst  = make_table(self.H*self.W, self.Kh*self.Kw*self.C)  # 16×18
        grid.addWidget(QLabel("Feature (C-stacked)"), 0,0)
        grid.addWidget(QLabel("im2col ((H·W)×(Kh·Kw·C))"), 0,1)
        grid.addWidget(self.im_src, 1,0)
        grid.addWidget(self.im_dst, 1,1)

        random.seed(3)
        # 填入两个 4×4 平面接在一起
        for ch in range(self.C):
            for i in range(self.H):
                for j in range(self.W):
                    set_cell(self.im_src, ch*self.H+i, j, random.randint(1,9))
        for i in range(self.H*self.W):
            for j in range(self.Kh*self.Kw*self.C):
                set_cell(self.im_dst, i, j, 0)

        self._im_idx = 0
        self._im_timer = QTimer(self); self._im_timer.timeout.connect(self._im_tick)
        self.im_btn_start.clicked.connect(lambda: self._im_timer.start(130))
        self.im_btn_step.clicked.connect(self._im_tick)
        self.im_btn_reset.clicked.connect(self._im_reset)

        # 带宽计数
        bw = QHBoxLayout(); lay.addLayout(bw)
        self.lb_bw_a = QLabel("L1→L0A bits: 0"); self.lb_bw_b = QLabel("L1→L0B bits: 0")
        bw.addWidget(self.lb_bw_a); bw.addSpacing(24); bw.addWidget(self.lb_bw_b); bw.addStretch(1)
        self._bw_a_bits = 0; self._bw_b_bits = 0
        return w

    def _im_reset(self):
        self._im_timer.stop(); self._im_idx = 0
        clear_hl(self.im_src); clear_hl(self.im_dst)
        for i in range(self.H*self.W):
            for j in range(self.Kh*self.Kw*self.C):
                set_cell(self.im_dst, i, j, 0)
        self._bw_a_bits = 0; self._bw_b_bits = 0
        self.lb_bw_a.setText("L1→L0A bits: 0"); self.lb_bw_b.setText("L1→L0B bits: 0")

    def _im_tick(self):
        # 逐像素展开一个 3×3×C 的 patch 到 im2col 行
        if self._im_idx >= self.H*self.W: self._im_timer.stop(); return
        clear_hl(self.im_src); clear_hl(self.im_dst)
        y = self._im_idx // self.W; x = self._im_idx % self.W
        out_row = self._im_idx

        # 采样 3×3×C（边界不够就跳过，作为演示）
        pos = 0
        klist = []
        for ch in range(self.C):
            for ky in range(self.Kh):
                for kx in range(self.Kw):
                    sy, sx = y+ky-1, x+kx-1
                    if 0<=sy<self.H and 0<=sx<self.W:
                        val = int(self.im_src.item(ch*self.H+sy, sx).text())
                        set_cell(self.im_dst, out_row, pos, val, bold=True)
                        hl_cell(self.im_src, ch*self.H+sy, sx, QColor(255,240,170))
                        hl_cell(self.im_dst, out_row, pos, QColor(190,255,200))
                        klist.append((ch,sy,sx))
                    pos += 1

        # 带宽估计：把这行写入 L0A（激活），同时假定本轮需要调 B 的 1 行 tile（Tn 元）：计入 L1→L0B
        elem_bits = max(8, self.elem_bits)
        written_elems = len(klist)  # 写到 L0A 的元素数（演示）
        self._bw_a_bits += written_elems * elem_bits
        self._bw_b_bits += self.Tn * elem_bits  # 对应一行权重 tile
        self.lb_bw_a.setText(f"L1→L0A bits: {self._bw_a_bits}")
        self.lb_bw_b.setText(f"L1→L0B bits: {self._bw_b_bits}")

        self._im_idx += 1


# =============== Cube 外积细化页 ===============
class CubeDetailDialog(QDialog):
    """
    演示外积：每个 k 层用 A[:,k] × B[k,:] → 产生 Tm×Tn 外积平面累加到 C。
    新增：访问热力图（C 的累计次数）、边界 tile 可视（Tm/Tn 不整除），参数联动。
    """
    def __init__(self, parent=None, Tm=4, Tn=4, K=4, bits=16, seed=0, M=None, N=None):
        super().__init__(parent)
        self.setWindowTitle("Cube · 外积累加（3D 层可视 / 热力图 / 边界tile）")
        self.resize(1040, 720)

        self.bits = bits
        self.Tm, self.Tn, self.K = Tm, Tn, K
        self.M = M or Tm
        self.N = N or Tn
        self.rm = min(self.Tm, self.M)  # 边界tile行数
        self.rn = min(self.Tn, self.N)  # 边界tile列数

        random.seed(seed)
        # A: rm×K, B: K×rn, C: rm×rn
        self.A = [[random.randint(1,9) for _ in range(self.K)] for __ in range(self.rm)]
        self.B = [[random.randint(1,9) for _ in range(self.rn)] for __ in range(self.K)]
        self.C = [[0 for _ in range(self.rn)] for __ in range(self.rm)]
        self.HC = [[0 for _ in range(self.rn)] for __ in range(self.rm)]  # heat count
        self.k = 0
        self.macs = 0

        root = QVBoxLayout(self)

        # 控制行
        ctl = QHBoxLayout()
        self.btnStart = QPushButton("Start"); self.btnStep = QPushButton("Step"); self.btnReset = QPushButton("Reset")
        self.spTm = QSpinBox(); self.spTm.setRange(2, 16); self.spTm.setValue(self.Tm)
        self.spTn = QSpinBox(); self.spTn.setRange(2, 16); self.spTn.setValue(self.Tn)
        self.spK  = QSpinBox(); self.spK.setRange(1, 32); self.spK.setValue(self.K)
        self.spM  = QSpinBox(); self.spM.setRange(1, 64); self.spM.setValue(self.M)
        self.spN  = QSpinBox(); self.spN.setRange(1, 64); self.spN.setValue(self.N)
        ctl.addWidget(QLabel("Tm:")); ctl.addWidget(self.spTm)
        ctl.addWidget(QLabel("Tn:")); ctl.addWidget(self.spTn)
        ctl.addWidget(QLabel("K:"));  ctl.addWidget(self.spK)
        ctl.addSpacing(16)
        ctl.addWidget(QLabel("M:"));  ctl.addWidget(self.spM)
        ctl.addWidget(QLabel("N:"));  ctl.addWidget(self.spN)
        ctl.addStretch(1)
        for b in (self.btnStart, self.btnStep, self.btnReset): ctl.addWidget(b)
        root.addLayout(ctl)

        # 三个表
        row = QHBoxLayout(); root.addLayout(row)

        gbA = QGroupBox("A tile  (rm×K)"); la = QVBoxLayout(gbA)
        self.tblA = make_table(self.rm, self.K) ; la.addWidget(self.tblA)

        gbB = QGroupBox("B tile  (K×rn)"); lb = QVBoxLayout(gbB)
        self.tblB = make_table(self.K,  self.rn) ; lb.addWidget(self.tblB)

        gbC = QGroupBox("C tile = Σ_k  A[:,k] ⊗ B[k,:]  (rm×rn)"); lc = QVBoxLayout(gbC)
        self.tblC = make_table(self.rm, self.rn); lc.addWidget(self.tblC)

        row.addWidget(gbA); row.addWidget(gbB); row.addWidget(gbC)

        # 状态栏：热力图开关
        st = QHBoxLayout(); root.addLayout(st)
        self.lblInfo = QLabel("k = 0 / MACs = 0 / Reuse: A-col×rn, B-row×rm / 边界tile: rm×rn")
        self.btnHeat = QPushButton("Heatmap ON"); self._heat_on = False
        st.addWidget(self.lblInfo); st.addStretch(1); st.addWidget(self.btnHeat)

        self._render_all()

        self.timer = QTimer(self); self.timer.timeout.connect(self._tick)

        self.btnStart.clicked.connect(lambda: self.timer.start(220))
        self.btnStep.clicked.connect(self._tick)
        self.btnReset.clicked.connect(self._reset)
        self.btnHeat.clicked.connect(self._toggle_heat)
        for sp in (self.spTm, self.spTn, self.spK, self.spM, self.spN): sp.valueChanged.connect(self._reinit)

    def _toggle_heat(self):
        self._heat_on = not self._heat_on
        self.btnHeat.setText("Heatmap ON" if self._heat_on else "Heatmap OFF")
        self._draw_heat()

    def _reinit(self):
        self.timer.stop()
        self.Tm, self.Tn, self.K = self.spTm.value(), self.spTn.value(), self.spK.value()
        self.M, self.N = self.spM.value(), self.spN.value()
        self.rm, self.rn = min(self.Tm, self.M), min(self.Tn, self.N)
        random.seed(0)
        self.A = [[random.randint(1,9) for _ in range(self.K)] for __ in range(self.rm)]
        self.B = [[random.randint(1,9) for _ in range(self.rn)] for __ in range(self.K)]
        self.C = [[0 for _ in range(self.rn)] for __ in range(self.rm)]
        self.HC = [[0 for _ in range(self.rn)] for __ in range(self.rm)]
        self.k = 0; self.macs = 0
        self._rebuild_tables()
        self._render_all()

    def _rebuild_tables(self):
        self.tblA.setRowCount(self.rm); self.tblA.setColumnCount(self.K)
        self.tblB.setRowCount(self.K);  self.tblB.setColumnCount(self.rn)
        self.tblC.setRowCount(self.rm); self.tblC.setColumnCount(self.rn)

    def _render_all(self):
        clear_hl(self.tblA); clear_hl(self.tblB); clear_hl(self.tblC)
        for i in range(self.rm):
            for k in range(self.K): set_cell(self.tblA, i,k, self.A[i][k])
        for k in range(self.K):
            for j in range(self.rn): set_cell(self.tblB, k,j, self.B[k][j])
        for i in range(self.rm):
            for j in range(self.rn): set_cell(self.tblC, i,j, self.C[i][j])
        self._draw_heat()
        self.lblInfo.setText(
            f"k = {self.k}/{self.K}   MACs = {self.macs}   Reuse: A-col×{self.rn}, B-row×{self.rm}   边界tile: {self.rm}×{self.rn}"
        )

    def _draw_heat(self):
        # 把热力图着色覆盖到 C 表格背景
        if not self._heat_on: 
            clear_hl(self.tblC); return
        mx = 0
        for i in range(self.rm):
            for j in range(self.rn):
                mx = max(mx, self.HC[i][j])
        for i in range(self.rm):
            for j in range(self.rn):
                col = heat_color(self.HC[i][j], mx)
                it = self.tblC.item(i,j)
                if it: it.setBackground(col)

    def _tick(self):
        if self.k >= self.K:
            self.timer.stop(); return
        clear_hl(self.tblA); clear_hl(self.tblB)
        hl_col(self.tblA, self.k, QColor(210,255,200))
        hl_row(self.tblB, self.k, QColor(190,235,255))
        for i in range(self.rm):
            a = self.A[i][self.k]
            for j in range(self.rn):
                b = self.B[self.k][j]
                self.C[i][j] += a * b
                self.HC[i][j] += 1
                self.macs += 1
                set_cell(self.tblC, i,j, self.C[i][j])
                if not self._heat_on:
                    hl_cell(self.tblC, i, j, QColor(255,235,210))
        self.k += 1
        self._draw_heat()
        self.lblInfo.setText(
            f"k = {self.k}/{self.K}   MACs = {self.macs}   Reuse: A-col×{self.rn}, B-row×{self.rm}   边界tile: {self.rm}×{self.rn}"
        )

    def _reset(self):
        self.timer.stop()
        self.k = 0; self.macs = 0
        self.C = [[0 for _ in range(self.rn)] for __ in range(self.rm)]
        self.HC = [[0 for _ in range(self.rn)] for __ in range(self.rm)]
        self._render_all()


# =============== Vector 细化页 ===============
class VectorDetailDialog(QDialog):
    """
    逐元素流水：Read→op1(ReLU)→op2(Scale)→op3(Cast)→Write
    展示：Wv（宽度）影响每拍能处理的元素数；理论拍数 vs 实测拍数。
    """
    def __init__(self, parent=None, Tm=8, Tn=8, Wv=32, gamma_out=1.0, elem_bits=16):
        super().__init__(parent)
        self.setWindowTitle("Vector · 逐元素流水（Wv/拍数对比）")
        self.resize(820, 600)
        self.Tm, self.Tn = Tm, Tn
        self.Wv = Wv
        self.gamma_out = gamma_out
        self.bits = elem_bits

        self.N = self.Tm * self.Tn  # 待处理元素数（例如一个 tile 的 C）
        self.idx = 0
        self.cycles = 0

        root = QVBoxLayout(self)
        ctl = QHBoxLayout()
        self.btnStart = QPushButton("Start"); self.btnStep = QPushButton("Step"); self.btnReset = QPushButton("Reset")
        self.spWv = QSpinBox(); self.spWv.setRange(1, 1024); self.spWv.setValue(self.Wv)
        self.spGo = QDoubleSpinBox(); self.spGo.setRange(0, 8); self.spGo.setSingleStep(0.5); self.spGo.setValue(self.gamma_out)
        ctl.addWidget(QLabel("Wv:")); ctl.addWidget(self.spWv)
        ctl.addWidget(QLabel("γ_out:")); ctl.addWidget(self.spGo)
        ctl.addStretch(1)
        for b in (self.btnStart,self.btnStep,self.btnReset): ctl.addWidget(b)
        root.addLayout(ctl)

        # 进度条：读/算/写（把一拍内的“批量元素”处理掉）
        bars = QHBoxLayout(); root.addLayout(bars)
        self.pb_read = QProgressBar(); self.pb_read.setFormat("Read %p%")
        self.pb_ops  = QProgressBar(); self.pb_ops.setFormat("Ops %p%")
        self.pb_write= QProgressBar(); self.pb_write.setFormat("Write %p%")
        for pb in (self.pb_read,self.pb_ops,self.pb_write):
            pb.setRange(0, 100); pb.setValue(0)
            pb.setStyleSheet("QProgressBar{height:12px;border:1px solid #c9d3ea;border-radius:6px;} QProgressBar::chunk{background:#2a7fff;}")
            bars.addWidget(pb)

        # 表格：一行元素的状态（简化显示 N 个元素的完成情况）
        self.tbl = make_table(1, self.N, cell_sz=520)
        for j in range(self.N): set_cell(self.tbl, 0, j, "·")
        root.addWidget(self.tbl)

        self.lblInfo = QLabel("elements=Tm×Tn  batch=Wv  Theoretical cycles ≈ ceil(γ_out·N / Wv)")
        root.addWidget(self.lblInfo)

        self.timer = QTimer(self); self.timer.timeout.connect(self._tick)
        self.btnStart.clicked.connect(lambda: self.timer.start(140))
        self.btnStep.clicked.connect(self._tick)
        self.btnReset.clicked.connect(self._reset)
        self.spWv.valueChanged.connect(self._on_param)
        self.spGo.valueChanged.connect(self._on_param)

        self._refresh_text()

    def _on_param(self):
        self.Wv = self.spWv.value()
        self.gamma_out = self.spGo.value()
        self._refresh_text()

    def _refresh_text(self):
        theo = math.ceil(max(1, self.gamma_out) * self.N / max(1, self.Wv))
        self.lblInfo.setText(
            f"elements={self.N}  Wv={self.Wv}  γ_out={self.gamma_out}  Theoretical cycles≈{theo}  (done {self.cycles})"
        )

    def _reset(self):
        self.timer.stop()
        self.idx = 0; self.cycles = 0
        clear_hl(self.tbl)
        for j in range(self.N): set_cell(self.tbl, 0, j, "·")
        self.pb_read.setValue(0); self.pb_ops.setValue(0); self.pb_write.setValue(0)
        self._refresh_text()

    def _tick(self):
        if self.idx >= self.N: self.timer.stop(); return
        batch = min(self.Wv, self.N - self.idx)
        # 一拍：读→算→写（用三个进度块体现）
        self.pb_read.setValue(100); self.pb_ops.setValue(100); self.pb_write.setValue(100)
        for j in range(self.idx, self.idx+batch):
            set_cell(self.tbl, 0, j, "✓", bold=True)
            hl_cell(self.tbl, 0, j, QColor(200,255,200))
        self.idx += batch
        self.cycles += 1
        self._refresh_text()
