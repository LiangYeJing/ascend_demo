# panels.py
try:
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import (
        QWidget, QMainWindow, QGridLayout, QVBoxLayout, QHBoxLayout, QLabel, QDialog
    )
except Exception:
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import (
        QWidget, QMainWindow, QGridLayout, QVBoxLayout, QHBoxLayout, QLabel, QDialog
    )

from widgets import ClickableCard, ControlBar, LogPane, Ticker, QueueBar, BandwidthBar
from sim import Simulator, scenario_gemm, scenario_conv_im2col, scenario_vector_only, scenario_mte_only
from details import MteDetailDialog, CubeDetailDialog, VectorDetailDialog



# # ---- 模块详情（占位，可扩展） ----
# class MteDetailDialog(QDialog):
#     def __init__(self, parent=None):
#         super().__init__(parent)
#         self.setWindowTitle("MTE Detail · 解压 / 拼接 / 转置（占位）")
#         self.resize(680, 380)
#         lay = QVBoxLayout(self)
#         lay.addWidget(QLabel(
#             "后续在此加入：\n"
#             "• Decompress：压缩→原始\n"
#             "• Interleave/Pack：通道拼接\n"
#             "• Transpose/Reshape：布局变换\n"
#             "• DMA/带宽计数器：L1<->L0A/L0B/L0C\n"
#         ))


class AscendTopWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ascend Pipeline · DataPath & ControlPath (扩展版)")
        self.resize(1360, 960)

        root = QWidget(); self.setCentralWidget(root)
        grid = QGridLayout(root); grid.setContentsMargins(10,10,10,10); grid.setHorizontalSpacing(10); grid.setVerticalSpacing(10)

        # 顶部控制 & 日志
        self.ctrl = ControlBar()
        self.log  = LogPane()
        grid.addWidget(self.ctrl, 0,0,1,2)
        grid.addWidget(self.log, 4,0,1,2)

        # ====== 数据路径（上排） ======
        data = QWidget(); grid.addWidget(data, 1,0,1,2)
        dg = QGridLayout(data); dg.setContentsMargins(0,0,0,0); dg.setHorizontalSpacing(10); dg.setVerticalSpacing(6)

        title_data = QLabel("Data Path  (L1 → MTE → L0A/L0B → Cube → Acc → L0C → Vector/Unified → L1)")
        title_data.setStyleSheet("font-weight:700;")
        dg.addWidget(title_data, 0,0,1,10)

        self.l1 = ClickableCard("L1 Buffer", "1 MB", "#dfffe9")
        self.mte = ClickableCard("MTE", "decomp/interleave/transpose", "#ece5ff")
        self.l0a = ClickableCard("L0A (A col)", "64 KB", "#fff5d8")
        self.l0b = ClickableCard("L0B (B row)", "64 KB", "#fff5d8")
        self.cube = ClickableCard("Cube 16×16×16", "outer-product array", "#ffd9c7")
        self.acc  = ClickableCard("Accumulator 16×16", "partial sums", "#ffc4d4")
        self.l0c  = ClickableCard("L0C (C buf)", "256 KB", "#fff5d8")
        self.vector = ClickableCard("Vector 8×16", "FPx/ReLU/Norm", "#ffe5fb")
        self.unified = ClickableCard("Unified Buffer", "256 KB", "#d7fffb")

        dg.addWidget(self.l1, 1,0,2,1)
        dg.addWidget(self.mte,1,1,2,1)
        dg.addWidget(self.l0a,1,2,1,1)
        dg.addWidget(self.l0b,2,2,1,1)
        dg.addWidget(self.cube,1,3,2,1)
        dg.addWidget(self.acc, 1,4,2,1)
        dg.addWidget(self.l0c, 1,5,2,1)
        dg.addWidget(self.vector,2,6,1,1)
        dg.addWidget(self.unified,1,6,1,1)

        # 三条带宽条
        self.bw_a = BandwidthBar("L1 → L0A  (bits/cycle)", max_bits_per_cycle=4096, color="#2a7fff")
        self.bw_b = BandwidthBar("L1 → L0B  (bits/cycle)", max_bits_per_cycle=2048, color="#5ac46d")
        self.bw_c = BandwidthBar("L0C → L1  (bits/cycle)", max_bits_per_cycle=2048, color="#ff8a3d")
        dg.addWidget(self.bw_a, 3,0,1,2)
        dg.addWidget(self.bw_b, 3,2,1,2)
        dg.addWidget(self.bw_c, 3,4,1,3)

        # ====== 控制路径（下排） ======
        ctrlp = QWidget(); grid.addWidget(ctrlp, 2,0,1,2)
        cg = QGridLayout(ctrlp); cg.setContentsMargins(0,0,0,0); cg.setHorizontalSpacing(10); cg.setVerticalSpacing(6)

        title_ctrl = QLabel("Control Path  (I$ → Dispatch → Queues → Event Sync)")
        title_ctrl.setStyleSheet("font-weight:700;")
        cg.addWidget(title_ctrl, 0,0,1,10)

        self.icache = ClickableCard("I-Cache", "32 KB", "#e8fff4")
        self.dispatch = ClickableCard("Dispatch", "decode/issue", "#e6ffed")
        self.q_cube = QueueBar("CubeQ")
        self.q_vec  = QueueBar("VectorQ")
        self.q_mte  = QueueBar("MTEQ")
        self.event  = ClickableCard("Event Sync", "barrier/signal", "#eeeeee")
        self.scalar = ClickableCard("Scalar/AGU/Mask", "SPR/GPR", "#f6ffd8")

        cg.addWidget(self.icache, 1,0,1,1)
        cg.addWidget(self.dispatch, 1,1,1,1)
        cg.addWidget(self.q_cube, 1,2,1,1)
        cg.addWidget(self.q_vec,  1,3,1,1)
        cg.addWidget(self.q_mte,  1,4,1,1)
        cg.addWidget(self.event,  1,5,1,1)
        cg.addWidget(self.scalar, 1,6,1,1)

        # 统计栏（理论拍数/建议 Wv）
        stats = QWidget(); grid.addWidget(stats, 3,0,1,2)
        sh = QHBoxLayout(stats); sh.setContentsMargins(6,6,6,6); sh.setSpacing(12)
        self.lblTheo = QLabel("Cycles (Cube/Vector): - / -")
        self.lblWvSg = QLabel("Suggested Wv ≥ -")
        self.lblMacV = QLabel("MACs: 0   VectorOps: 0")
        for L in (self.lblTheo, self.lblWvSg, self.lblMacV):
            L.setStyleSheet("background:#f7fbff;border:1px solid #d7e3f4;border-radius:8px;padding:6px;")
            sh.addWidget(L)
        sh.addStretch(1)

        # 交互
        # self.mte.doubleClicked.connect(lambda: MteDetailDialog(self).exec())
        # self.cube.doubleClicked.connect(lambda: CubeDetailDialog(self).exec())
        # 细化页：把主参数传入，保持一致性
        self.mte.doubleClicked.connect(self.open_mte)
        self.cube.doubleClicked.connect(self.open_cube)
        self.vector.doubleClicked.connect(self.open_vector)

        # ---- 仿真器 ----
        self.sim = Simulator()
        self.ticker = Ticker(interval_ms=self.ctrl.speed.value())
        self.ctrl.speedChanged.connect(self.ticker.set_interval)
        self.ctrl.start.connect(self.start)
        self.ctrl.pause.connect(self.pause)
        self.ctrl.step.connect(self.step_once)
        self.ctrl.reset.connect(self.reset)
        self.ctrl.scenarioChanged.connect(self.on_scenario)
        self.ctrl.paramsApplied.connect(self.apply_params)

        # 映射（控制/数据分别高亮）
        self.ctrl_map = {
            "IFetch": self.icache, "IDecode": self.dispatch, "Enqueue(": self.dispatch,
            "Vector exec": self.vector, "Cube exec": self.cube, "MTE": self.mte, "EventSync": self.event
        }
        self.data_map = {
            "MTE(L1->L0A)": self.l0a, "MTE(L1->L0B)": self.l0b,
            "MTE(im2col)": self.mte, "MTE(Transpose)": self.mte,
            "MTE(Decompress)": self.mte, "MTE(Interleave)": self.mte,
            "Cube@k": self.cube, "Accumulate(L0C)": self.acc,
            "Vector(Read L0C)": self.l0c, "Vector(Act": self.vector,
            "Vector(ReLU)": self.vector, "Vector(Read L1)": self.l1,
            "Vector(Scale+Bias)": self.vector, "Write C(L1)": self.l1, "Write L1": self.l1
        }

        self.reset()

    def open_mte(self):
        # 从控制面板读取当前参数
        elem_bits = self.ctrl.spBits.value()
        Tm = self.ctrl.spTm.value()
        Tn = self.ctrl.spTn.value()
        dlg = MteDetailDialog(self, bits_in=8, bits_out=max(8, elem_bits), elem_bits=elem_bits, Tm=Tm, Tn=Tn)
        dlg.exec()

    def open_cube(self):
        Tm = self.ctrl.spTm.value(); Tn = self.ctrl.spTn.value()
        K  = self.ctrl.spK.value();  bits = self.ctrl.spBits.value()
        M  = self.ctrl.spM.value();  N  = self.ctrl.spN.value()
        dlg = CubeDetailDialog(self, Tm=Tm, Tn=Tn, K=K, bits=bits, M=M, N=N)
        dlg.exec()

    def open_vector(self):
        Tm = self.ctrl.spTm.value(); Tn = self.ctrl.spTn.value()
        Wv = self.ctrl.spWv.value(); go = self.ctrl.spGo.value()
        bits = self.ctrl.spBits.value()
        dlg = VectorDetailDialog(self, Tm=Tm, Tn=Tn, Wv=Wv, gamma_out=go, elem_bits=bits)
        dlg.exec()


    # ==== 控制 ====
    def apply_params(self):
        # 从控件写回仿真器参数，并刷新上限
        s = self.sim; c = self.ctrl
        s.M, s.N, s.K = c.spM.value(), c.spN.value(), c.spK.value()
        s.Tm, s.Tn, s.Tk = c.spTm.value(), c.spTn.value(), c.spTk.value()
        s.bits, s.Wv = c.spBits.value(), c.spWv.value()
        s.gamma_out, s.gamma_in = c.spGo.value(), c.spGi.value()
        s.vmax_L1A, s.vmax_L1B, s.vmax_CW = c.spBW_A.value(), c.spBW_B.value(), c.spBW_C.value()

        self.bw_a.set_max(s.vmax_L1A); self.bw_b.set_max(s.vmax_L1B); self.bw_c.set_max(s.vmax_CW)

        # 更新建议与理论拍数
        wv_need = s.suggest_Wv()
        cube_cyc = s.cube_cycles_theory()
        vec_cyc  = s.vector_cycles_theory()
        self.lblWvSg.setText(f"Suggested Wv ≥ {wv_need:.1f}   (now {s.Wv})")
        self.lblTheo.setText(f"Cycles (Cube/Vector): {cube_cyc} / {vec_cyc}")
        self.log.log(f"[PARAM] Set M,N,K={s.M},{s.N},{s.K}; Tile={s.Tm}×{s.Tn}×{s.Tk}; bits={s.bits}; Wv={s.Wv}; γ_out={s.gamma_out}, γ_in={s.gamma_in}; BW_A/B/C={s.vmax_L1A}/{s.vmax_L1B}/{s.vmax_CW} bits/cycle.")

    def on_scenario(self, text): self.reset(text)

    def reset(self, scenario_text=None):
        text = scenario_text or self.ctrl.cbxScenario.currentText()
        if "GEMM" in text:     prog = scenario_gemm(K_layers=6)
        elif "Conv2D" in text: prog = scenario_conv_im2col(tiles=4)
        elif "Vector-only" in text: prog = scenario_vector_only()
        else:                  prog = scenario_mte_only()

        self.sim.reset(prog)
        self.sim.on_visit_ctrl = self.on_visit_ctrl
        self.sim.on_visit_data = self.on_visit_data
        self.sim.on_done = self.on_done

        self.clear_active()
        self.log.clear()
        self.log.log(f"Scenario ready: {text}. Set params then Start/Step.")

        self.bw_a.set_value(0); self.bw_b.set_value(0); self.bw_c.set_value(0)
        self.q_cube.set_value(0); self.q_vec.set_value(0); self.q_mte.set_value(0)
        self.lblMacV.setText("MACs: 0   VectorOps: 0")
        self.apply_params()  # 用当前控件值初始化

    def start(self):
        if not self.ticker.running():
            self.ticker.tick.connect(self.on_tick)
            self.ticker.start()
            self.log.log("Simulation started.")

    def pause(self):
        if self.ticker.running():
            self.ticker.stop()
            try: self.ticker.tick.disconnect(self.on_tick)
            except Exception: pass
            self.log.log("Paused.")

    def step_once(self): self.on_tick()
    def on_tick(self):   self.sim.step()

    def on_done(self):
        self.log.log("Program finished. (Event Sync)")
        self.pause()

    # ==== 可视反馈 ====
    def clear_active(self):
        for w in [self.l1,self.mte,self.l0a,self.l0b,self.cube,self.acc,self.l0c,self.vector,self.unified,
                  self.icache,self.dispatch,self.event,self.scalar]:
            w.set_active(False)

    def on_visit_ctrl(self, stage: str, name: str):
        self.clear_active()
        for key, card in self.ctrl_map.items():
            if key in stage:
                card.set_active(True, tint="#5ac46d")
                card.set_badge(stage)
                break
        self.q_cube.set_value(self.sim.q_cube)
        self.q_vec.set_value(self.sim.q_vec)
        self.q_mte.set_value(self.sim.q_mte)
        self.log.log(f"[CTRL] {name} → {stage}")

    def on_visit_data(self, stage: str, name: str, meta):
        self.clear_active()
        for key, card in self.data_map.items():
            if key in stage:
                card.set_active(True, tint="#2a7fff")
                card.set_badge(stage)
                break
        # 带宽条
        kind = meta.get("kind",""); val = meta.get("bits_per_cycle",0)
        if "L1->L0A" in kind: self.bw_a.set_value(val)
        if "L1->L0B" in kind: self.bw_b.set_value(val)
        if "L0C->L1" in kind: self.bw_c.set_value(val)

        # 显示 MAC/VectorOps
        self.lblMacV.setText(f"MACs: {self.sim.macs}   VectorOps: {self.sim.vecops}")
        self.log.log(f"[DATA] {name} → {stage}   ({kind} = {val} bits/cycle)")
