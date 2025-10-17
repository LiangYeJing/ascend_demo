# # widgets.py
# import numpy as np

# try:
#     from PyQt5.QtCore import Qt
#     from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QSizePolicy
#     from PyQt5.QtGui import QColor
#     from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
# except Exception:
#     from PyQt6.QtCore import Qt
#     from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QSizePolicy
#     from PyQt6.QtGui import QColor
#     from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas  # PyQt6 也可用

# import matplotlib.pyplot as plt
# from mpl_toolkits.mplot3d import Axes3D  # noqa: F401


# class MatrixView(QWidget):
#     """自适应大小的矩阵表格视图（支持非方阵）。"""
#     def __init__(self, title="Matrix", parent=None):
#         super().__init__(parent)
#         self.title_lbl = QLabel(title)
#         self.title_lbl.setStyleSheet("font-weight:600;")
#         self.table = QTableWidget(0, 0)
#         self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
#         self.table.horizontalHeader().setVisible(False)
#         self.table.verticalHeader().setVisible(False)
#         self.table.setShowGrid(True)
#         self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
#         self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
#         lay = QVBoxLayout(self); lay.setContentsMargins(4, 4, 4, 4); lay.setSpacing(6)
#         lay.addWidget(self.title_lbl); lay.addWidget(self.table)
#         self.cl_cell = QColor(255, 230, 160)
#         self.cl_row  = QColor(180, 235, 255)
#         self.cl_col  = QColor(210, 255, 180)
#         self.cl_out  = QColor(255, 205, 205)

#     def set_title(self, text): self.title_lbl.setText(text)

#     def set_data(self, M: np.ndarray, precision=0):
#         r, c = M.shape
#         self.table.setRowCount(r); self.table.setColumnCount(c)
#         for i in range(r):
#             for j in range(c):
#                 txt = f"{M[i,j]:.{precision}f}" if precision>0 else f"{M[i,j]:.0f}"
#                 it = QTableWidgetItem(txt); it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
#                 self.table.setItem(i, j, it)
#         base = max(r, c, 1)
#         target = max(18, min(44, int(320 / base)))
#         for j in range(c): self.table.setColumnWidth(j, target)
#         for i in range(r): self.table.setRowHeight(i, target)
#         self.clear_highlights()

#     def clear_highlights(self):
#         r, c = self.table.rowCount(), self.table.columnCount()
#         for i in range(r):
#             for j in range(c):
#                 it = self.table.item(i, j)
#                 if it: it.setBackground(QColor(255,255,255))

#     def highlight_cell(self, i, j, color=None):
#         it = self.table.item(i, j)
#         if it: it.setBackground(color or self.cl_cell)

#     def highlight_row(self, i, color=None):
#         c = self.table.columnCount()
#         for j in range(c):
#             it = self.table.item(i, j)
#             if it: it.setBackground(color or self.cl_row)

#     def highlight_col(self, j, color=None):
#         r = self.table.rowCount()
#         for i in range(r):
#             it = self.table.item(i, j)
#             if it: it.setBackground(color or self.cl_col)


# class Compute3DCanvas(QWidget):
#     """
#     通用 3D 画布（x=j, y=i, z=k），用于 1D/2D/3D 的统一可视化。
#     - show_points_1d(i, j, K, phase):      固定 (i,j)，沿 k 的 K 个点；phase=0 蓝(活跃)，1 绿(已算)
#     - show_tile_points(k, rows, cols, done_points): 2D 点积 tile 在 z=k 的 (i,j,k) 点集
#     - show_plane_3d(k, done_layers, rows=None, cols=None): 3D 外积层（红=当前层/区域，绿=本 tile 历史层）
#     """
#     def __init__(self, M: int, N: int, K: int, parent=None):
#         super().__init__(parent)
#         self.M, self.N, self.K = M, N, K
#         self.fig = plt.Figure(figsize=(4.9, 4.3), tight_layout=True)
#         self.canvas = FigureCanvas(self.fig)
#         self.ax = self.fig.add_subplot(111, projection='3d')
#         lay = QVBoxLayout(self); lay.setContentsMargins(4,4,4,4); lay.addWidget(self.canvas)
#         self._init_axes()

#     def _init_axes(self):
#         ax = self.ax
#         ax.cla()
#         ax.set_xlim(-0.5, self.N-0.5)
#         ax.set_ylim(-0.5, self.M-0.5)
#         ax.set_zlim(-0.5, self.K-0.5)
#         ax.set_xlabel("j (B列 / C列)")
#         ax.set_ylabel("i (A行 / C行)")
#         ax.set_zlabel("k (K维 / 外积层)")
#         ax.view_init(elev=26, azim=-60)
#         self.canvas.draw_idle()

#     def reset_dims(self, M, N, K):
#         self.M, self.N, self.K = M, N, K
#         self._init_axes()

#     # ----- 1D：固定 (i,j) 的 K 个点 -----
#     def show_points_1d(self, i:int, j:int, K:int, phase:int):
#         self._init_axes()
#         ks = np.arange(K)
#         js = np.full_like(ks, j)
#         is_ = np.full_like(ks, i)
#         c = "g" if phase==1 else None  # None=默认蓝
#         self.ax.scatter(js, is_, ks, s=22, c=c)
#         self.canvas.draw_idle()

#     # ----- 2D：z=k 层的 rows×cols 点云 -----
#     def show_tile_points(self, k:int, rows:np.ndarray, cols:np.ndarray, done_points:set):
#         self._init_axes()
#         # 已算（绿）
#         if done_points:
#             arr = np.array(list(done_points), dtype=int)
#             self.ax.scatter(arr[:,1], arr[:,0], arr[:,2], s=12, c="g")
#         # 当前活跃（蓝）
#         if len(rows)>0 and len(cols)>0:
#             rr, cc = np.meshgrid(rows, cols, indexing="ij")
#             js = cc.flatten(); is_ = rr.flatten(); ks = np.full_like(js, k)
#             self.ax.scatter(js, is_, ks, s=18)  # 默认蓝
#         self.canvas.draw_idle()

#     # ----- 3D：整层（或子区域） -----
#     def show_plane_3d(self, k:int, done_layers:set, rows=None, cols=None):
#         self._init_axes()
#         M, N = self.M, self.N
#         r_idx = np.arange(M) if rows is None else rows
#         c_idx = np.arange(N) if cols is None else cols

#         # 历史层（绿）
#         for kk in sorted(list(done_layers)):
#             rr, cc = np.meshgrid(r_idx, c_idx, indexing="ij")
#             js = cc.flatten(); is_ = rr.flatten()
#             ks = np.full_like(js, kk)
#             self.ax.scatter(js, is_, ks, s=10, c="g")

#         # 当前层（红）
#         rr, cc = np.meshgrid(r_idx, c_idx, indexing="ij")
#         js = cc.flatten(); is_ = rr.flatten()
#         ks = np.full_like(js, k)
#         self.ax.scatter(js, is_, ks, s=12, c="r")
#         self.canvas.draw_idle()

# widgets.py
from typing import Optional
import time

try:
    from PyQt5.QtCore import Qt, QTimer, pyqtSignal
    from PyQt5.QtWidgets import (
        QWidget, QFrame, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QSlider,
        QComboBox, QTextEdit, QSizePolicy, QProgressBar, QSpinBox, QFormLayout,
        QDoubleSpinBox
    )
except Exception:
    from PyQt6.QtCore import Qt, QTimer, pyqtSignal
    from PyQt6.QtWidgets import (
        QWidget, QFrame, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QSlider,
        QComboBox, QTextEdit, QSizePolicy, QProgressBar, QSpinBox, QFormLayout,
        QDoubleSpinBox
    )


# ---------- 基础卡片（可点击/高亮） ----------
class ClickableCard(QFrame):
    clicked = pyqtSignal()
    doubleClicked = pyqtSignal()

    def __init__(self, title: str, subtitle: str = "", color="#f6f7fb", border="#c9d3ea", parent=None):
        super().__init__(parent)
        self._border = border
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(f"""
            QFrame {{
                background: {color};
                border-radius: 12px;
                border: 1px solid {border};
            }}
            QLabel[role='title'] {{ font-weight: 700; }}
            QLabel[role='sub'] {{ color: #333; }}
        """)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        lay = QVBoxLayout(self); lay.setContentsMargins(10, 8, 10, 8); lay.setSpacing(2)
        self.lblTitle = QLabel(title); self.lblTitle.setProperty("role", "title")
        self.lblSub = QLabel(subtitle); self.lblSub.setProperty("role", "sub"); self.lblSub.setWordWrap(True)
        lay.addWidget(self.lblTitle); lay.addWidget(self.lblSub)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton: self.clicked.emit()

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton: self.doubleClicked.emit()

    def set_active(self, on: bool, tint="#4f7cff"):
        self.setStyleSheet(self.styleSheet() + (f"""
            QFrame {{ border: 2px solid {tint}; }}
        """ if on else f"QFrame {{ border: 1px solid {self._border}; }}"))

    def set_badge(self, text: str):
        self.lblSub.setText(text)


# ---------- 队列视图 ----------
class QueueBar(QFrame):
    def __init__(self, title="Queue", parent=None):
        super().__init__(parent)
        self.setStyleSheet("QFrame{background:#eef3ff;border:1px solid #c9d3ea;border-radius:10px;}")
        lay = QHBoxLayout(self); lay.setContentsMargins(8,6,8,6); lay.setSpacing(8)
        self.lbl = QLabel(title); self.lbl.setStyleSheet("font-weight:600;")
        self.val = QLabel("0"); self.val.setStyleSheet("background:#2a7fff;color:white;padding:1px 8px;border-radius:8px;")
        lay.addWidget(self.lbl); lay.addStretch(1); lay.addWidget(self.val)

    def set_value(self, v: int): self.val.setText(str(v))


# ---------- 带宽条（bits/cycle） ----------
class BandwidthBar(QWidget):
    def __init__(self, title, max_bits_per_cycle=4096, color="#2a7fff", parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self); lay.setContentsMargins(0,0,0,0); lay.setSpacing(2)
        self.lbl = QLabel(title)
        self.prog = QProgressBar(); self.prog.setRange(0, max_bits_per_cycle)
        self.prog.setFormat("%v / %m bits/cycle")
        self.prog.setStyleSheet("QProgressBar{height:10px;border:1px solid #c9d3ea;border-radius:6px;} "
                                f"QProgressBar::chunk{{background:{color};}}")
        lay.addWidget(self.lbl); lay.addWidget(self.prog)
    def set_max(self, m: int): self.prog.setRange(0, m)
    def set_value(self, v: int): self.prog.setValue(max(0, v))


# ---------- 控制条 ----------
class ControlBar(QWidget):
    start = pyqtSignal()
    pause = pyqtSignal()
    step = pyqtSignal()
    reset = pyqtSignal()
    speedChanged = pyqtSignal(int)
    scenarioChanged = pyqtSignal(str)
    paramsApplied = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(8)

        # 第一行：按钮/场景/速度
        line1 = QHBoxLayout(); root.addLayout(line1)
        self.btnStart = QPushButton("Start"); self.btnPause = QPushButton("Pause")
        self.btnStep  = QPushButton("Step");  self.btnReset = QPushButton("Reset")
        self.cbxScenario = QComboBox(); self.cbxScenario.addItems(
            ["GEMM (Cube+Vector+MTE)", "Conv2D (im2col·MTE)", "Vector-only (PostOps)", "MTE-only (Move/Trans)"]
        )
        self.speed = QSlider(Qt.Orientation.Horizontal); self.speed.setRange(60, 1200); self.speed.setValue(380)
        self.lblSpeed = QLabel("Speed: 380 ms/tick")
        for b in (self.btnStart,self.btnPause,self.btnStep,self.btnReset): line1.addWidget(b)
        line1.addWidget(QLabel("Scenario:")); line1.addWidget(self.cbxScenario)
        line1.addStretch(1); line1.addWidget(self.lblSpeed); line1.addWidget(self.speed)

        self.btnStart.clicked.connect(self.start.emit)
        self.btnPause.clicked.connect(self.pause.emit)
        self.btnStep.clicked.connect(self.step.emit)
        self.btnReset.clicked.connect(self.reset.emit)
        self.speed.valueChanged.connect(lambda v: (self.lblSpeed.setText(f"Speed: {v} ms/tick"), self.speedChanged.emit(v)))
        self.cbxScenario.currentTextChanged.connect(self.scenarioChanged.emit)

        # 第二行：参数表
        box = QFrame(); box.setStyleSheet("QFrame{background:#f7fbff;border:1px solid #d7e3f4;border-radius:10px;}")
        root.addWidget(box)
        form = QFormLayout(box); form.setContentsMargins(8,6,8,6); form.setSpacing(6)

        self.spM = QSpinBox(); self.spM.setRange(1, 4096); self.spM.setValue(64)
        self.spN = QSpinBox(); self.spN.setRange(1, 4096); self.spN.setValue(64)
        self.spK = QSpinBox(); self.spK.setRange(1, 4096); self.spK.setValue(64)

        self.spTm = QSpinBox(); self.spTm.setRange(1, 128); self.spTm.setValue(16)
        self.spTn = QSpinBox(); self.spTn.setRange(1, 128); self.spTn.setValue(16)
        self.spTk = QSpinBox(); self.spTk.setRange(1, 128); self.spTk.setValue(16)

        self.spBits = QSpinBox(); self.spBits.setRange(4, 64); self.spBits.setValue(16)
        self.spWv = QSpinBox(); self.spWv.setRange(1, 2048); self.spWv.setValue(32)

        self.spGo = QDoubleSpinBox(); self.spGo.setRange(0, 8); self.spGo.setSingleStep(0.5); self.spGo.setValue(1.0)
        self.spGi = QDoubleSpinBox(); self.spGi.setRange(0, 8); self.spGi.setSingleStep(0.5); self.spGi.setValue(0.0)

        self.spBW_A = QSpinBox(); self.spBW_A.setRange(128, 16384); self.spBW_A.setValue(4096)  # L1->L0A
        self.spBW_B = QSpinBox(); self.spBW_B.setRange(128, 16384); self.spBW_B.setValue(2048)  # L1->L0B
        self.spBW_C = QSpinBox(); self.spBW_C.setRange(128, 16384); self.spBW_C.setValue(2048)  # L0C->L1

        self.btnApply = QPushButton("Apply Params")

        form.addRow("Matrix M×N×K:", self._row(self.spM, self.spN, self.spK))
        form.addRow("Cube Tile Tm×Tn×Tk:", self._row(self.spTm, self.spTn, self.spTk))
        form.addRow("Element Bits (FP16=16):", self.spBits)
        form.addRow("Vector Width Wv (elems/cycle):", self.spWv)
        form.addRow("γ_out (per C elem):", self.spGo)
        form.addRow("γ_in (per A/B elem):", self.spGi)
        form.addRow("Max BW (bits/cycle)  A/B/C:", self._row(self.spBW_A, self.spBW_B, self.spBW_C))
        form.addRow(self.btnApply)

        self.btnApply.clicked.connect(self.paramsApplied.emit)

    def _row(self, *widgets):
        w = QWidget(); h = QHBoxLayout(w); h.setContentsMargins(0,0,0,0); h.setSpacing(6)
        for x in widgets: h.addWidget(x)
        h.addStretch(1)
        return w


# ---------- 日志 ----------
class LogPane(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setStyleSheet("QTextEdit{background:#0b1220;color:#d6e3ff;border-radius:8px;padding:8px;}")
    def log(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        self.append(f"[{ts}] {msg}")
        self.moveCursor(self.textCursor().End)


# ---------- 定时器 ----------
class Ticker(QWidget):
    tick = pyqtSignal()
    def __init__(self, interval_ms=380, parent=None):
        super().__init__(parent)
        self.timer = QTimer(self); self.timer.timeout.connect(self.tick)
        self.interval = interval_ms
    def set_interval(self, ms): self.interval = ms
    def start(self): self.timer.start(self.interval)
    def stop(self): self.timer.stop()
    def single(self): self.tick.emit()
    def running(self): return self.timer.isActive()
