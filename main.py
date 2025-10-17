# # main.py
# import sys, random, numpy as np

# try:
#     from PyQt5.QtCore import Qt
#     from PyQt5.QtWidgets import (
#         QApplication, QMainWindow, QWidget, QLabel, QPushButton,
#         QGridLayout, QHBoxLayout, QVBoxLayout, QGroupBox, QFormLayout,
#         QSpinBox, QSlider, QTabWidget, QSizePolicy
#     )
# except Exception:
#     from PyQt6.QtCore import Qt
#     from PyQt6.QtWidgets import (
#         QApplication, QMainWindow, QWidget, QLabel, QPushButton,
#         QGridLayout, QHBoxLayout, QVBoxLayout, QGroupBox, QFormLayout,
#         QSpinBox, QSlider, QTabWidget, QSizePolicy
#     )

# from engines import VectorDotEngine, Matrix2DEngine, Cube3DEngine


# class MainWindow(QMainWindow):
#     def __init__(self):
#         super().__init__()
#         self.setWindowTitle("Ascend 执行风格（1D / 2D / 3D · 理论周期对比 & 3D可视）")
#         self.resize(1260, 860)

#         # 左侧控制
#         ctrl = QGroupBox("Controls"); form = QFormLayout()
#         self.spinM = QSpinBox(); self.spinM.setRange(2, 64); self.spinM.setValue(8)
#         self.spinK = QSpinBox(); self.spinK.setRange(2, 64); self.spinK.setValue(8)
#         self.spinN = QSpinBox(); self.spinN.setRange(2, 64); self.spinN.setValue(8)

#         # 2D tile 尺寸
#         self.spinTm2d = QSpinBox(); self.spinTm2d.setRange(1, 32); self.spinTm2d.setValue(4)
#         self.spinTn2d = QSpinBox(); self.spinTn2d.setRange(1, 32); self.spinTn2d.setValue(4)

#         # 3D Cube 规格
#         self.spinTm = QSpinBox(); self.spinTm.setRange(1, 32); self.spinTm.setValue(16)
#         self.spinTn = QSpinBox(); self.spinTn.setRange(1, 32); self.spinTn.setValue(16)
#         self.spinTk = QSpinBox(); self.spinTk.setRange(1, 32); self.spinTk.setValue(16)

#         self.spinSeed = QSpinBox(); self.spinSeed.setRange(0, 10000); self.spinSeed.setValue(0)
#         self.btnGen = QPushButton("Generate A(M×K), B(K×N)")
#         self.btnStart = QPushButton("Start All")
#         self.btnPause = QPushButton("Pause All")
#         self.btnResume = QPushButton("Resume All")
#         self.btnReset = QPushButton("Reset All")

#         self.speed = QSlider(Qt.Orientation.Horizontal); self.speed.setRange(60, 1200); self.speed.setValue(460)
#         self.lblSpeed = QLabel("Speed (ms): 460")

#         form.addRow("M (rows of A/C):", self.spinM)
#         form.addRow("K (cols of A / rows of B):", self.spinK)
#         form.addRow("N (cols of B/C):", self.spinN)
#         form.addRow("2D Tm:", self.spinTm2d)
#         form.addRow("2D Tn:", self.spinTn2d)
#         form.addRow("3D Tm:", self.spinTm)
#         form.addRow("3D Tn:", self.spinTn)
#         form.addRow("3D Tk:", self.spinTk)
#         form.addRow("Random Seed:", self.spinSeed)
#         form.addRow(self.btnGen)
#         form.addRow(self.lblSpeed, self.speed)

#         preset_row = QHBoxLayout()
#         self.btnCaseA = QPushButton("Case A: Cube≥Matrix (8,8,8 | 16³)")
#         self.btnCaseB = QPushButton("Case B: Cube≈Matrix (32,16,24 | 16³)")
#         self.btnCaseC = QPushButton("Case C: Cube≪Matrix (64,32,64 | 8³)")
#         preset_row.addWidget(self.btnCaseA); preset_row.addWidget(self.btnCaseB); preset_row.addWidget(self.btnCaseC)
#         form.addRow(preset_row)

#         row = QHBoxLayout()
#         row.addWidget(self.btnStart); row.addWidget(self.btnPause)
#         row.addWidget(self.btnResume); row.addWidget(self.btnReset)
#         form.addRow(row)
#         ctrl.setLayout(form); ctrl.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

#         # 右侧 Tab
#         self.tabs = QTabWidget()
#         self.status_lbl = QLabel(
#             "3D·Cube：固定阵列 (Tm,Tn,Tk)，当 M,N,K 超出时按三维分块覆盖；每个 k 层 1 拍，"
#             "2D 为 Tm×Tn 点积阵列（每 tile 需要并行乘 + 归约）。蓝=活跃，绿=已算，红=3D 当前层区域。"
#         )
#         self.status_lbl.setStyleSheet("padding:6px;color:#333;")

#         central = QWidget(); grid = QGridLayout(central)
#         grid.setContentsMargins(8,8,8,8); grid.setHorizontalSpacing(10); grid.setVerticalSpacing(10)
#         grid.addWidget(ctrl, 0,0, 2,1); grid.addWidget(self.status_lbl, 0,1); grid.addWidget(self.tabs, 1,1)
#         self.setCentralWidget(central)

#         # 事件
#         self.speed.valueChanged.connect(self.on_speed)
#         self.btnGen.clicked.connect(self.generate_mats)
#         self.btnStart.clicked.connect(self.start_all)
#         self.btnPause.clicked.connect(self.pause_all)
#         self.btnResume.clicked.connect(self.resume_all)
#         self.btnReset.clicked.connect(self.reset_all)

#         self.btnCaseA.clicked.connect(lambda: self.apply_case(8,8,8, 16,16,16))
#         self.btnCaseB.clicked.connect(lambda: self.apply_case(32,16,24, 16,16,16))
#         self.btnCaseC.clicked.connect(lambda: self.apply_case(64,32,64, 8,8,8))

#         for s in (self.spinM, self.spinK, self.spinN):
#             s.valueChanged.connect(self._cap_tiles)

#         # init
#         self.A = self.B = None
#         self.eng_1d = self.eng_2d = self.eng_3d = None
#         self.generate_mats()

#     def _cap_tiles(self):
#         # 不让 tile 超过维度
#         self.spinTm2d.setMaximum(max(1, self.spinM.value()))
#         self.spinTn2d.setMaximum(max(1, self.spinN.value()))
#         self.spinTm.setMaximum(max(1, self.spinM.value()))
#         self.spinTn.setMaximum(max(1, self.spinN.value()))
#         self.spinTk.setMaximum(max(1, self.spinK.value()))

#     def on_speed(self, val):
#         self.lblSpeed.setText(f"Speed (ms): {val}")
#         for e in self.engines(): e.set_speed(val)

#     def engines(self):
#         return [self.eng_1d, self.eng_2d, self.eng_3d]

#     def apply_case(self, M, K, N, TmT, TnT, TkT):
#         self.spinM.setValue(M); self.spinK.setValue(K); self.spinN.setValue(N)
#         self.spinTm.setValue(TmT); self.spinTn.setValue(TnT); self.spinTk.setValue(TkT)
#         self.spinTm2d.setValue(min(4, M)); self.spinTn2d.setValue(min(4, N))
#         self.generate_mats()

#     def generate_mats(self):
#         M, K, N = self.spinM.value(), self.spinK.value(), self.spinN.value()
#         seed = self.spinSeed.value()
#         random.seed(seed); np.random.seed(seed)
#         self.A = np.random.randint(1, 9, size=(M, K))
#         self.B = np.random.randint(1, 9, size=(K, N))

#         # 清空标签
#         while self.tabs.count() > 0:
#             w = self.tabs.widget(0); self.tabs.removeTab(0); w.setParent(None)

#         # 引擎
#         self.eng_1d = VectorDotEngine(self.A, self.B, vec_width=None)
#         self.eng_2d = Matrix2DEngine(self.A, self.B, tile_rows=self.spinTm2d.value(), tile_cols=self.spinTn2d.value(), vec_width=None)
#         self.eng_3d = Cube3DEngine(self.A, self.B, Tm=self.spinTm.value(), Tn=self.spinTn.value(), Tk=self.spinTk.value())

#         self.tabs.addTab(self.eng_1d, "1D · Vector")
#         self.tabs.addTab(self.eng_2d, f"2D · Matrix (Tm={self.spinTm2d.value()},Tn={self.spinTn2d.value()})")
#         self.tabs.addTab(self.eng_3d, f"3D · Cube (Tm={self.spinTm.value()},Tn={self.spinTn.value()},Tk={self.spinTk.value()})")

#         for e in self.engines(): e.set_speed(self.speed.value())

#         self.status_lbl.setText(
#             f"A(M×K),B(K×N) 生成（M={M},K={K},N={N}, seed={seed}）。"
#             f"2D 为 Tm×Tn 点积阵列；3D 为外积阵列（每层 1 拍）并按 (Tm,Tn,Tk)=({self.spinTm.value()},{self.spinTn.value()},{self.spinTk.value()}) 分块。"
#         )

#     def start_all(self):
#         if any(e and e.timer.isActive() for e in self.engines()):
#             self.status_lbl.setText("已在运行。可先 Pause / Reset。"); return
#         for e in self.engines(): e.start()
#         self.status_lbl.setText("全部引擎已启动。")

#     def pause_all(self):
#         for e in self.engines(): e.pause()
#         self.status_lbl.setText("已暂停。")

#     def resume_all(self):
#         for e in self.engines(): e.resume()
#         self.status_lbl.setText("继续运行。")

#     def reset_all(self):
#         for e in self.engines(): e.reset()
#         self.status_lbl.setText("已重置。可 Start 重新演示。")


# if __name__ == "__main__":
#     app = QApplication(sys.argv)
#     w = MainWindow()
#     w.show()
#     sys.exit(app.exec())


# main.py
import sys
try:
    from PyQt5.QtWidgets import QApplication
except Exception:
    from PyQt6.QtWidgets import QApplication

from panels import AscendTopWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = AscendTopWindow()
    w.show()
    sys.exit(app.exec())

