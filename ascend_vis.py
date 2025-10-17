import sys, random
import numpy as np

# --- Try PyQt5 first, fallback to PyQt6 lightly ---
try:
    from PyQt5.QtCore import Qt, QTimer, pyqtSignal
    from PyQt5.QtWidgets import (
        QApplication, QWidget, QMainWindow, QLabel, QPushButton, QGridLayout,
        QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QSpinBox,
        QSlider, QGroupBox, QFormLayout
    )
    from PyQt5.QtGui import QColor
except Exception:
    from PyQt6.QtCore import Qt, QTimer, pyqtSignal
    from PyQt6.QtWidgets import (
        QApplication, QWidget, QMainWindow, QLabel, QPushButton, QGridLayout,
        QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QSpinBox,
        QSlider, QGroupBox, QFormLayout
    )
    from PyQt6.QtGui import QColor


# =============== MatrixView ===============
class MatrixView(QWidget):
    def __init__(self, title="Matrix", parent=None, fixed=210):
        super().__init__(parent)
        self.title_lbl = QLabel(title)
        self.title_lbl.setStyleSheet("font-weight:600;")
        self.table = QTableWidget(0, 0)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        if fixed:
            self.table.setFixedHeight(fixed)
            self.table.setFixedWidth(fixed)
        self.table.horizontalHeader().setVisible(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(True)
        lay = QVBoxLayout(self)
        lay.addWidget(self.title_lbl)
        lay.addWidget(self.table)
        # palette
        self.cl_cell = QColor(255, 230, 160)
        self.cl_row  = QColor(180, 235, 255)
        self.cl_col  = QColor(210, 255, 180)
        self.cl_out  = QColor(255, 205, 205)

    def set_title(self, text): self.title_lbl.setText(text)

    def set_data(self, M: np.ndarray, precision=0):
        r, c = M.shape
        self.table.setRowCount(r)
        self.table.setColumnCount(c)
        for i in range(r):
            for j in range(c):
                it = QTableWidgetItem(f"{M[i,j]:.{precision}f}" if precision>0 else f"{M[i,j]:.0f}")
                it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(i, j, it)
        sz = max(22, int(180 / max(r, c)))  # cell size
        for j in range(c): self.table.setColumnWidth(j, sz)
        for i in range(r): self.table.setRowHeight(i, sz)
        self.clear_highlights()

    def clear_highlights(self):
        r, c = self.table.rowCount(), self.table.columnCount()
        for i in range(r):
            for j in range(c):
                it = self.table.item(i, j)
                if it: it.setBackground(QColor(255,255,255))

    def highlight_cell(self, i, j, color=None):
        it = self.table.item(i, j)
        if it: it.setBackground(color or self.cl_cell)

    def highlight_row(self, i, color=None):
        c = self.table.columnCount()
        for j in range(c):
            it = self.table.item(i, j)
            if it: it.setBackground(color or self.cl_row)

    def highlight_col(self, j, color=None):
        r = self.table.rowCount()
        for i in range(r):
            it = self.table.item(i, j)
            if it: it.setBackground(color or self.cl_col)


# =============== BaseEngine ===============
class BaseEngine(QWidget):
    updated = pyqtSignal()  # UI refresh

    def __init__(self, name, A, B, parent=None):
        super().__init__(parent)
        self.name, self.A, self.B = name, A.astype(float), B.astype(float)
        self.N = A.shape[0]

        # views
        self.viewA = MatrixView("A")
        self.viewB = MatrixView("B")
        self.viewC = MatrixView("C (Result)")
        self.viewProd = MatrixView("Prod (中间乘积)", fixed=120)

        self.viewA.set_data(self.A)
        self.viewB.set_data(self.B)
        self.C = np.zeros_like(A, dtype=float)
        self.viewC.set_data(self.C, precision=0)

        # stats / layout
        self.lbl_status = QLabel("Idle")
        self.lbl_stage  = QLabel("Stage: -")
        self.lbl_loads  = QLabel("Loads: 0   MACs: 0")
        for l in (self.lbl_status, self.lbl_stage, self.lbl_loads):
            l.setStyleSheet("color:#333;")

        g = QGridLayout(self)
        title = QLabel(f"{name}")
        title.setStyleSheet("font-size:14px;font-weight:700;")
        g.addWidget(title, 0, 0, 1, 4)
        g.addWidget(self.viewA, 1, 0)
        g.addWidget(self.viewB, 1, 1)
        g.addWidget(self.viewC, 1, 2)
        g.addWidget(self.viewProd, 1, 3)
        g.addWidget(self.lbl_status, 2, 0, 1, 2)
        g.addWidget(self.lbl_stage,  2, 2, 1, 1)
        g.addWidget(self.lbl_loads,  2, 3, 1, 1)

        # state
        self.timer = QTimer(self); self.timer.timeout.connect(self.step)
        self.interval_ms = 600
        self.loads = 0; self.macs = 0; self.done = False

    def set_speed(self, ms):
        self.interval_ms = ms
        if self.timer.isActive(): self.timer.start(self.interval_ms)

    def start(self):
        self.reset(); self.timer.start(self.interval_ms); self.lbl_status.setText("Running...")

    def pause(self):
        self.timer.stop(); self.lbl_status.setText("Paused")

    def resume(self):
        if not self.done: self.timer.start(self.interval_ms); self.lbl_status.setText("Running...")

    def reset(self):
        self.timer.stop()
        self.C[:] = 0
        self.viewC.set_data(self.C, precision=0)
        self.viewA.set_data(self.A); self.viewB.set_data(self.B)
        # 清空 Prod
        self.viewProd.set_data(np.zeros((1,1)))
        self.loads = 0; self.macs = 0; self.done = False
        self._reset_state()
        self.lbl_status.setText("Ready")
        self.lbl_stage.setText("Stage: -")
        self.lbl_loads.setText(f"Loads: {self.loads}   MACs: {self.macs}")

    def _reset_state(self): pass
    def step(self): pass


# =============== Scalar ===============
class ScalarEngine(BaseEngine):
    """ i,j 固定时，k 逐个：每次 step 只做一次 a*b 并累加 """
    def __init__(self, A, B, parent=None):
        super().__init__("Scalar（逐元乘加：a*b → 累加）", A, B, parent)

    def _reset_state(self):
        self.i = self.j = self.k = 0

    def step(self):
        if self.done: self.timer.stop(); return
        N = self.N
        self.viewA.clear_highlights(); self.viewB.clear_highlights(); self.viewC.clear_highlights()

        # 每次 MAC 都需要两次数据加载
        self.loads += 2
        a = self.A[self.i, self.k]; b = self.B[self.k, self.j]
        prod = a * b
        self.macs += 1
        self.C[self.i, self.j] += prod

        # Prod 显示当前这一个乘积
        self.viewProd.set_data(np.array([[prod]]), precision=0)

        # UI 高亮
        self.viewA.highlight_cell(self.i, self.k)
        self.viewB.highlight_cell(self.k, self.j)
        self.viewC.set_data(self.C, precision=0)
        self.viewC.highlight_cell(self.i, self.j, self.viewC.cl_out)
        self.lbl_stage.setText(f"Stage: a({self.i},{self.k}) * b({self.k},{self.j}) → C({self.i},{self.j})")
        self.lbl_loads.setText(f"Loads: {self.loads}   MACs: {self.macs}")
        self.updated.emit()

        # 前进游标
        self.k += 1
        if self.k >= N:
            self.k = 0; self.j += 1
            if self.j >= N:
                self.j = 0; self.i += 1
                if self.i >= N:
                    self.done = True; self.timer.stop(); self.lbl_status.setText("Done")


# =============== Vector (1D dot) ===============
class VectorEngine(BaseEngine):
    """
    两拍：
    (1) 并行乘法：Prod[:] = A[i,:] * B[:,j]  （一次产生 N 个乘积，计 N 个 MAC）
        首次访问该 i 时加载 A 的整行；每个 j 首次时加载 B 的整列。
    (2) 归约加和：C[i,j] = sum(Prod)
    """
    def __init__(self, A, B, parent=None):
        super().__init__("Vector（1D 点积：行×列 并行乘 → 归约）", A, B, parent)

    def _reset_state(self):
        self.i = self.j = 0
        self.phase = 0  # 0=并行乘法, 1=归约
        self.row_loaded = False
        self.prod_vec = np.zeros((1, self.N))

    def step(self):
        if self.done: self.timer.stop(); return
        N = self.N
        self.viewA.clear_highlights(); self.viewB.clear_highlights(); self.viewC.clear_highlights()

        # 加载策略
        if not self.row_loaded:
            self.loads += N  # 加载 A 的整行
            self.row_loaded = True

        if self.phase == 0:
            # 每个 j 的第一拍：加载 B 的整列
            self.loads += N
            Arow = self.A[self.i, :]            # 1×N
            Bcol = self.B[:, self.j]            # N×1
            self.prod_vec = (Arow * Bcol).reshape(1, -1)   # N 个并行乘积
            self.macs += N  # 并行乘法产生 N 个 MAC
            # 显示 Prod 向量
            self.viewProd.set_data(self.prod_vec, precision=0)
            # 高亮行/列与全部元素
            self.viewA.highlight_row(self.i, self.viewA.cl_row)
            self.viewB.highlight_col(self.j, self.viewB.cl_col)
            for k in range(N):
                self.viewA.highlight_cell(self.i, k)
                self.viewB.highlight_cell(k, self.j)
            self.lbl_stage.setText(f"Stage: 并行乘法（{N} 路）→ Prod[k]=A[i,k]*B[k,j]")
            self.lbl_loads.setText(f"Loads: {self.loads}   MACs: {self.macs}")
            self.phase = 1  # 下一拍做归约
        else:
            # 归约加和写 C[i,j]
            val = float(self.prod_vec.sum())
            self.C[self.i, self.j] = val
            self.viewC.set_data(self.C, precision=0)
            self.viewC.highlight_cell(self.i, self.j, self.viewC.cl_out)
            self.lbl_stage.setText("Stage: 归约 sum(Prod) → 写入 C[i,j]")
            self.viewProd.set_data(self.prod_vec, precision=0)  # 仍显示上一拍的乘积
            self.phase = 0
            # 进位
            self.j += 1
            if self.j >= N:
                self.j = 0; self.i += 1; self.row_loaded = False
                if self.i >= N:
                    self.done = True; self.timer.stop(); self.lbl_status.setText("Done")
        self.updated.emit()


# =============== Cube (3D tile / outer-product) ===============
class CubeEngine(BaseEngine):
    """
    两拍（每个 k）：
    (1) 并行外积：Tile = A[:,k] * B[k,:]  （一次产生 N×N 个乘积，计 N*N 个 MAC；加载 2N）
    (2) 整块累加：C += Tile
    """
    def __init__(self, A, B, parent=None):
        super().__init__("Cube（3D 外积：列×行 并行外积 → 整块累加）", A, B, parent)

    def _reset_state(self):
        self.k = 0
        self.phase = 0  # 0=并行外积, 1=整块累加
        self.tile = np.zeros_like(self.A)

    def step(self):
        if self.done: self.timer.stop(); return
        N = self.N
        self.viewA.clear_highlights(); self.viewB.clear_highlights(); self.viewC.clear_highlights()

        if self.phase == 0:
            # 加载 A 的一列 + B 的一行（喂入 L0）
            self.loads += 2 * N
            a_col = self.A[:, self.k]   # N×1
            b_row = self.B[self.k, :]   # 1×N
            self.tile = np.outer(a_col, b_row)   # N×N 并行乘积
            self.macs += N * N
            # 展示 Tile
            self.viewProd.set_data(self.tile, precision=0)
            self.viewA.highlight_col(self.k, self.viewA.cl_col)
            self.viewB.highlight_row(self.k, self.viewB.cl_row)
            self.lbl_stage.setText(f"Stage: 并行外积（{N}×{N} 路）→ Tile = A[:,k]*B[k,:], k={self.k}")
            self.lbl_loads.setText(f"Loads: {self.loads}   MACs: {self.macs}")
            self.phase = 1
        else:
            # 整块累加
            self.C += self.tile
            self.viewC.set_data(self.C, precision=0)
            self.lbl_stage.setText("Stage: 累加 C += Tile")
            # 下一 k
            self.phase = 0; self.k += 1
            if self.k >= N:
                self.done = True; self.timer.stop(); self.lbl_status.setText("Done")
        self.updated.emit()


# =============== MainWindow ===============
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ascend 执行风格可视化（Scalar / Vector / Cube）")
        self.resize(1320, 860)

        # Controls
        ctrl = QGroupBox("Controls")
        form = QFormLayout()
        self.spinN = QSpinBox(); self.spinN.setRange(2, 8); self.spinN.setValue(4)
        self.spinSeed = QSpinBox(); self.spinSeed.setRange(0, 10000); self.spinSeed.setValue(0)
        self.btnRand = QPushButton("Generate A,B")
        self.btnStart = QPushButton("Start")
        self.btnPause = QPushButton("Pause")
        self.btnResume = QPushButton("Resume")
        self.btnReset = QPushButton("Reset")
        self.speed = QSlider(Qt.Orientation.Horizontal); self.speed.setRange(80, 1200); self.speed.setValue(600)
        self.lblSpeed = QLabel("Speed (ms): 600")
        form.addRow("Matrix N (2–8):", self.spinN)
        form.addRow("Random Seed:", self.spinSeed)
        form.addRow(self.btnRand)
        form.addRow(self.lblSpeed, self.speed)
        row = QHBoxLayout()
        for b in (self.btnStart, self.btnPause, self.btnResume, self.btnReset): row.addWidget(b)
        form.addRow(row)
        ctrl.setLayout(form)

        self.status_lbl = QLabel("点击 Generate 生成 A、B；Start 同时启动三种计算。Vector/Cube 现在分两拍显示：并行乘 → 归约/累加。")
        self.status_lbl.setStyleSheet("padding:6px;color:#333;")

        self.grid = QGridLayout()
        self.grid.addWidget(ctrl, 0, 0, 1, 3)
        self.grid.addWidget(self.status_lbl, 1, 0, 1, 3)

        central = QWidget(); central.setLayout(self.grid); self.setCentralWidget(central)

        # events
        self.btnRand.clicked.connect(self.generate_mats)
        self.btnStart.clicked.connect(self.start_all)
        self.btnPause.clicked.connect(self.pause_all)
        self.btnResume.clicked.connect(self.resume_all)
        self.btnReset.clicked.connect(self.reset_all)
        self.speed.valueChanged.connect(self.on_speed)

        # init
        self.A = self.B = None
        self.scalar = self.vector = self.cube = None
        self.generate_mats()

    def on_speed(self, val):
        self.lblSpeed.setText(f"Speed (ms): {val}")
        for e in self.engines(): e.set_speed(val)

    def engines(self): return [self.scalar, self.vector, self.cube]

    def generate_mats(self):
        N, seed = self.spinN.value(), self.spinSeed.value()
        random.seed(seed); np.random.seed(seed)
        self.A = np.random.randint(1, 9, size=(N, N))
        self.B = np.random.randint(1, 9, size=(N, N))

        # rebuild engines
        self.scalar = ScalarEngine(self.A, self.B)
        self.vector = VectorEngine(self.A, self.B)
        self.cube   = CubeEngine(self.A, self.B)

        # layout
        # 先清理原来的 widget（如果有）
        while self.grid.count() > 2:
            item = self.grid.itemAt(self.grid.count()-1)
            w = item.widget()
            if w: w.setParent(None)

        self.grid.addWidget(self.scalar, 2, 0)
        self.grid.addWidget(self.vector, 2, 1)
        self.grid.addWidget(self.cube,   2, 2)

        # --- 在 MainWindow.generate_mats() 末尾，统一设定速度之后 ---
        self.status_lbl.setText(
            f"A,B 生成（N={N}, seed={seed}）；Vector/Cube 拆解为“并行乘→归约/累加”的两拍展示，便于观察并行度。"
        )
        for e in self.engines():
            e.set_speed(self.speed.value())

    def start_all(self):
        if any(e.timer.isActive() for e in self.engines()):
            self.status_lbl.setText("已在运行。可 Pause → Reset。"); return
        for e in self.engines(): e.start()
        self.status_lbl.setText("三种计算已同时开始。")

    def pause_all(self):
        for e in self.engines(): e.pause()
        self.status_lbl.setText("已暂停。")

    def resume_all(self):
        for e in self.engines(): e.resume()
        self.status_lbl.setText("继续运行。")

    def reset_all(self):
        for e in self.engines(): e.reset()
        self.status_lbl.setText("已重置。可 Start 重新演示。")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())
