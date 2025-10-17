# # engines.py
# import numpy as np

# try:
#     from PyQt5.QtCore import QTimer, pyqtSignal
#     from PyQt5.QtWidgets import QWidget, QLabel, QGridLayout
# except Exception:
#     from PyQt6.QtCore import QTimer, pyqtSignal
#     from PyQt6.QtWidgets import QWidget, QLabel, QGridLayout

# from widgets import MatrixView, Compute3DCanvas


# # ----- 理论周期（硬件拍）估算：与 UI 动画无关，用于真实对比 -----
# def cycles_1d(M, N, K, vec_width=None):
#     # vec_width=None 表示单个 C[i,j] 的 K 路并行乘一次完成（1 拍）；否则分批
#     batches = 1 if (vec_width is None or vec_width >= K) else int(np.ceil(K / vec_width))
#     reduce_cost = int(np.ceil(np.log2(K))) if K > 1 else 0
#     return M * N * (batches + reduce_cost)

# def cycles_2d(M, N, K, Tm, Tn, vec_width=None):
#     tiles_m = int(np.ceil(M / Tm))
#     tiles_n = int(np.ceil(N / Tn))
#     batches = 1 if (vec_width is None or vec_width >= K) else int(np.ceil(K / vec_width))
#     reduce_cost = int(np.ceil(np.log2(K))) if K > 1 else 0
#     return tiles_m * tiles_n * (batches + reduce_cost)

# def cycles_3d(M, N, K, Tm, Tn, Tk):
#     # 外积：每个 k 层 1 拍；Tk 影响缓冲与流水，不改变层拍数
#     tiles_m = int(np.ceil(M / Tm))
#     tiles_n = int(np.ceil(N / Tn))
#     return tiles_m * tiles_n * K


# class BaseEngine(QWidget):
#     updated = pyqtSignal()

#     def __init__(self, name, A, B, parent=None):
#         super().__init__(parent)
#         # A: M×K, B: K×N, C: M×N
#         self.name, self.A, self.B = name, A.astype(float), B.astype(float)
#         self.M, self.K = self.A.shape
#         self.K2, self.N = self.B.shape
#         assert self.K2 == self.K, "Inner dims mismatch"

#         self.viewA = MatrixView("A"); self.viewB = MatrixView("B")
#         self.C = np.zeros((self.M, self.N), dtype=float)
#         self.viewC = MatrixView("C (Result)")
#         self.viewA.set_data(self.A); self.viewB.set_data(self.B); self.viewC.set_data(self.C, precision=0)

#         self.lbl_title  = QLabel(f"{name}"); self.lbl_title.setStyleSheet("font-size:14px;font-weight:700;")
#         self.lbl_status = QLabel("Idle")
#         self.lbl_stage  = QLabel("Stage: -")
#         self.lbl_stats  = QLabel("Loads: 0   MACs: 0")
#         self.lbl_theory = QLabel("")  # 理论周期

#         g = QGridLayout(self)
#         g.setContentsMargins(6, 6, 6, 6); g.setHorizontalSpacing(8); g.setVerticalSpacing(8)
#         g.addWidget(self.lbl_title, 0,0,1,2)
#         g.addWidget(self.viewA, 1,0); g.addWidget(self.viewB, 1,1)
#         g.addWidget(self.viewC, 2,0,1,2)
#         g.addWidget(self.lbl_status, 3,0); g.addWidget(self.lbl_stage, 3,1)
#         g.addWidget(self.lbl_stats, 4,0,1,2)
#         g.addWidget(self.lbl_theory, 5,0,1,2)

#         self.timer = QTimer(self); self.timer.timeout.connect(self.step)
#         self.interval_ms = 460; self.loads = 0; self.macs = 0; self.done = False

#     def set_speed(self, ms):
#         self.interval_ms = ms
#         if self.timer.isActive(): self.timer.start(self.interval_ms)

#     def start(self):
#         self.reset(); self.timer.start(self.interval_ms); self.lbl_status.setText("Running...")

#     def pause(self):
#         self.timer.stop(); self.lbl_status.setText("Paused")

#     def resume(self):
#         if not self.done: self.timer.start(self.interval_ms); self.lbl_status.setText("Running...")

#     def reset(self):
#         self.timer.stop()
#         self.C[:] = 0; self.viewC.set_data(self.C, precision=0)
#         self.viewA.set_data(self.A); self.viewB.set_data(self.B)
#         self.loads = 0; self.macs = 0; self.done = False; self._reset_state()
#         self.lbl_status.setText("Ready"); self.lbl_stage.setText("Stage: -"); self.lbl_stats.setText("Loads: 0   MACs: 0")

#     def _reset_state(self): pass
#     def step(self): pass


# # ===== 1D · Vector（GEMV 点积） + 3D：竖向 K 个点 =====
# class VectorDotEngine(BaseEngine):
#     def __init__(self, A, B, parent=None, vec_width=None):
#         super().__init__("1D · Vector（GEMV 点积）", A, B, parent)
#         self.canvas3d = Compute3DCanvas(self.M, self.N, self.K)
#         self.layout().addWidget(self.canvas3d, 2, 1)
#         self.vec_width = vec_width  # None = 满 K 宽并行

#         Cth = cycles_1d(self.M, self.N, self.K, vec_width=self.vec_width)
#         self.lbl_theory.setText(f"Theory cycles (1D vecW={self.vec_width or 'K'}): {Cth}")

#     def _reset_state(self):
#         self.i = 0; self.j = 0; self.phase = 0
#         self.row_loaded = False
#         self.prod_vec = np.zeros((self.K,), dtype=float)
#         self.canvas3d.reset_dims(self.M, self.N, self.K)

#     def step(self):
#         if self.done: self.timer.stop(); return
#         M,N,K = self.M, self.N, self.K
#         self.viewA.clear_highlights(); self.viewB.clear_highlights(); self.viewC.clear_highlights()

#         if not self.row_loaded:
#             self.loads += K  # 加载 A[i,:]
#             self.row_loaded = True

#         if self.phase == 0:
#             # 并行乘（K 路；此处简单化为一拍）
#             self.loads += K  # 加载 B[:,j]
#             arow = self.A[self.i, :]   # (K,)
#             bcol = self.B[:, self.j]   # (K,)
#             self.prod_vec = arow * bcol
#             self.macs += K

#             # 3D：蓝点（活跃）
#             self.canvas3d.show_points_1d(self.i, self.j, K, phase=0)

#             # 2D 高亮
#             self.viewA.highlight_row(self.i, self.viewA.cl_row)
#             self.viewB.highlight_col(self.j, self.viewB.cl_col)
#             for k in range(K):
#                 self.viewA.highlight_cell(self.i, k)
#                 self.viewB.highlight_cell(k, self.j)

#             self.lbl_stage.setText(f"Stage: 并行乘（K 路）→ Prod[i={self.i}, j={self.j}]")
#             self.lbl_stats.setText(f"Loads: {self.loads}   MACs: {self.macs}")
#             self.phase = 1

#         else:
#             # 归约
#             self.C[self.i, self.j] = float(self.prod_vec.sum())
#             self.viewC.set_data(self.C, precision=0)
#             self.viewC.highlight_cell(self.i, self.j, self.viewC.cl_out)
#             self.canvas3d.show_points_1d(self.i, self.j, self.K, phase=1)
#             self.lbl_stage.setText("Stage: 归约 sum(Prod) → C[i,j]")

#             self.phase = 0
#             self.j += 1
#             if self.j >= N:
#                 self.j = 0; self.i += 1; self.row_loaded = False
#                 if self.i >= M:
#                     self.done = True; self.timer.stop(); self.lbl_status.setText("Done")
#         self.updated.emit()


# # ===== 2D · Matrix（真正的 Tm×Tn 点积阵列） + 3D：tile 点云 =====
# class Matrix2DEngine(BaseEngine):
#     def __init__(self, A, B, tile_rows=2, tile_cols=2, parent=None, vec_width=None):
#         super().__init__("2D · Matrix（Tm×Tn 点积阵列）", A, B, parent)
#         self.Tm = max(1, min(tile_rows, self.M))
#         self.Tn = max(1, min(tile_cols, self.N))
#         self.vec_width = vec_width  # None=沿 k 一次完成
#         self.canvas3d = Compute3DCanvas(self.M, self.N, self.K)
#         self.layout().addWidget(self.canvas3d, 2, 1)

#         Cth = cycles_2d(self.M, self.N, self.K, Tm=self.Tm, Tn=self.Tn, vec_width=self.vec_width)
#         self.lbl_theory.setText(f"Theory cycles (2D Tm={self.Tm},Tn={self.Tn},vecW={self.vec_width or 'K'}): {Cth}")

#     def _reset_state(self):
#         self.i0 = 0; self.j0 = 0; self.k = 0; self.phase = 0
#         self.tile_acc = np.zeros((min(self.Tm, self.M), min(self.Tn, self.N)), dtype=float)
#         self.done_points = set()  # (i,j,k) 已算
#         self.canvas3d.reset_dims(self.M, self.N, self.K)

#     def _ranges(self):
#         rows = np.arange(self.i0, min(self.i0+self.Tm, self.M))
#         cols = np.arange(self.j0, min(self.j0+self.Tn, self.N))
#         return rows, cols

#     def _advance_tile(self):
#         self.j0 += self.Tn
#         if self.j0 >= self.N:
#             self.j0 = 0
#             self.i0 += self.Tm
#             if self.i0 >= self.M:
#                 return True
#         return False

#     def step(self):
#         if self.done: self.timer.stop(); return
#         self.viewA.clear_highlights(); self.viewB.clear_highlights(); self.viewC.clear_highlights()
#         rows, cols = self._ranges()
#         rm, rn = len(rows), len(cols)

#         if self.phase == 0:
#             # 并行乘（点积的按-k 乘法；这里一次用全部 k）
#             a_col = self.A[rows, self.k]        # rm
#             b_row = self.B[self.k, cols]        # rn
#             self.tile_acc[:rm, :rn] += np.outer(a_col, b_row)
#             self.loads += (rm + rn)
#             self.macs  += (rm * rn)

#             # 3D：当前 tile 的 (rows,cols) 在 z=k 的点（蓝）；历史点（绿）
#             self.canvas3d.show_tile_points(self.k, rows, cols, self.done_points)

#             # 2D 高亮
#             for ri in rows: self.viewA.highlight_cell(ri, self.k, self.viewA.cl_col)
#             for cj in cols: self.viewB.highlight_cell(self.k, cj, self.viewB.cl_row)
#             self.lbl_stage.setText(f"Stage: Tile 乘 k={self.k} （rm={rm}, rn={rn}）")
#             self.lbl_stats.setText(f"Loads: {self.loads}   MACs: {self.macs}")

#             self.k += 1
#             if self.k >= self.K:
#                 self.phase = 1  # 进入归约/写回
#         else:
#             # 写回 C 的子块
#             self.C[np.ix_(rows, cols)] = self.tile_acc[:rm, :rn]
#             self.viewC.set_data(self.C, precision=0)
#             for ri in rows:
#                 for cj in cols:
#                     self.viewC.highlight_cell(ri, cj, self.viewC.cl_out)
#                     # 标记该 tile 上所有 (ri,cj,k) 为 done
#                     for kk in range(self.K):
#                         self.done_points.add((ri, cj, kk))

#             self.lbl_stage.setText("Stage: Tile 归约完成 → 写回 C 子块")
#             # 重置 tile 累加器，推进到下一个 tile
#             self.tile_acc[:] = 0
#             self.k = 0
#             finished = self._advance_tile()
#             if finished:
#                 self.done = True; self.timer.stop(); self.lbl_status.setText("Done")
#             self.phase = 0
#         self.updated.emit()


# # ===== 3D · Cube（外积 · 三维分块） + 3D：子区域外积层 =====
# class Cube3DEngine(BaseEngine):
#     def __init__(self, A, B, Tm=16, Tn=16, Tk=16, parent=None):
#         super().__init__("3D · Cube（外积 · 三维分块）", A, B, parent)
#         self.Tm = max(1, min(Tm, self.M))
#         self.Tn = max(1, min(Tn, self.N))
#         self.Tk = max(1, min(Tk, self.K))
#         self.canvas3d = Compute3DCanvas(self.M, self.N, self.K)
#         self.layout().addWidget(self.canvas3d, 2, 1)

#         Cth = cycles_3d(self.M, self.N, self.K, Tm=self.Tm, Tn=self.Tn, Tk=self.Tk)
#         self.lbl_theory.setText(f"Theory cycles (3D Tm={self.Tm},Tn={self.Tn},Tk={self.Tk}): {Cth}")

#     def _reset_state(self):
#         self.m0 = 0; self.n0 = 0; self.k0 = 0; self.kk = 0
#         self.phase = 0  # 0=装载+外积一层子区域; 1=累加到 C 子块
#         self.done_layers_in_tile = set()
#         self.canvas3d.reset_dims(self.M, self.N, self.K)

#     def _tile_ranges(self):
#         rows = np.arange(self.m0, min(self.m0+self.Tm, self.M))
#         cols = np.arange(self.n0, min(self.n0+self.Tn, self.N))
#         rk = min(self.Tk, self.K - self.k0)
#         return rows, cols, rk

#     def _advance(self):
#         rows, cols, rk = self._tile_ranges()
#         self.kk += 1
#         if self.kk >= rk:
#             self.kk = 0
#             self.done_layers_in_tile.clear()
#             self.k0 += self.Tk
#             if self.k0 >= self.K:
#                 self.k0 = 0
#                 self.n0 += self.Tn
#                 if self.n0 >= self.N:
#                     self.n0 = 0
#                     self.m0 += self.Tm
#                     if self.m0 >= self.M:
#                         return True
#         return False

#     def step(self):
#         if self.done: self.timer.stop(); return
#         self.viewA.clear_highlights(); self.viewB.clear_highlights(); self.viewC.clear_highlights()
#         rows, cols, rk = self._tile_ranges()
#         rm, rn = len(rows), len(cols)
#         k = self.k0 + self.kk

#         if self.phase == 0:
#             a_col = self.A[rows, k]      # rm
#             b_row = self.B[k, cols]      # rn
#             self.tile = np.outer(a_col, b_row)   # rm×rn
#             self.loads += (rm + rn)
#             self.macs  += (rm * rn)

#             # 3D：在 z=k 层显示当前子区域（红），历史层（绿）
#             self.canvas3d.show_plane_3d(k, self.done_layers_in_tile, rows=rows, cols=cols)

#             # 2D 高亮
#             for ri in rows: self.viewA.highlight_cell(ri, k, self.viewA.cl_col)
#             for cj in cols: self.viewB.highlight_cell(k, cj, self.viewB.cl_row)

#             self.lbl_stage.setText(f"Stage: 外积层 k={k}，子区域 rm={rm}, rn={rn}")
#             self.lbl_stats.setText(f"Loads: {self.loads}   MACs: {self.macs}")
#             self.phase = 1

#         else:
#             self.C[np.ix_(rows, cols)] += self.tile
#             self.viewC.set_data(self.C, precision=0)
#             for ri in rows:
#                 for cj in cols:
#                     self.viewC.highlight_cell(ri, cj, self.viewC.cl_out)

#             self.done_layers_in_tile.add(k)
#             self.lbl_stage.setText("Stage: 子区域累加 C += Tile")
#             self.phase = 0

#             finished = self._advance()
#             if finished:
#                 self.done = True; self.timer.stop(); self.lbl_status.setText("Done")
#         self.updated.emit()
