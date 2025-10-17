# sim.py
from dataclasses import dataclass, field
from typing import List, Callable, Dict
import math

# ---- 抽象：指令 / 数据事件 ----
@dataclass
class Instr:
    name: str
    ctrl_stages: List[str]      # 控制路径阶段
    data_stages: List[str]      # 数据路径阶段
    ccur: int = 0
    dcur: int = 0

    def ctrl_done(self): return self.ccur >= len(self.ctrl_stages)
    def data_done(self): return self.dcur >= len(self.data_stages)
    def curr_ctrl(self) -> str: return "" if self.ctrl_done() else self.ctrl_stages[self.ccur]
    def curr_data(self) -> str: return "" if self.data_done() else self.data_stages[self.dcur]
    def step_ctrl(self): 
        if not self.ctrl_done(): self.ccur += 1
    def step_data(self):
        if not self.data_done(): self.dcur += 1
    def done(self): return self.ctrl_done() and self.data_done()


# ---- 场景 ----
def scenario_gemm(K_layers=6) -> List[Instr]:
    ins = [Instr("Fetch/Dispatch", ["IFetch","IDecode","Enqueue(CubeQ,MTEQ)"], [])]
    for k in range(K_layers):
        ins.append(Instr(f"Feed k={k}", ["(ctrl) wait MTE ready","(ctrl) signal Cube"], ["MTE(L1->L0A)","MTE(L1->L0B)"]))
        ins.append(Instr(f"Cube layer k={k}", ["(ctrl) Cube exec"], ["Cube@k","Accumulate(L0C)"]))
    ins.append(Instr("PostOps+Write", ["Enqueue(VectorQ)","(ctrl) Vector exec"], ["Vector(Read L0C)","Vector(Act/FPx)","Write C(L1)"]))
    ins.append(Instr("Finish",["EventSync"],[]))
    return ins


def scenario_conv_im2col(tiles=4) -> List[Instr]:
    ins = [Instr("Fetch/Dispatch", ["IFetch","IDecode","Enqueue(MTEQ)"], [])]
    for t in range(tiles):
        ins += [
            Instr(f"MTE im2col t{t}", ["(ctrl) MTE im2col"], ["MTE(im2col)","MTE(Transpose)"]),
            Instr(f"Cube GEMM t{t}",  ["(ctrl) Cube exec"],  ["Cube@k","Accumulate(L0C)"])
        ]
    ins += [Instr("Vector+Write",["Enqueue(VectorQ)","(ctrl) Vector"],["Vector(Read L0C)","Vector(ReLU)","Write C(L1)"]),
            Instr("Finish",["EventSync"],[])]
    return ins


def scenario_vector_only() -> List[Instr]:
    return [
        Instr("Fetch/Dispatch", ["IFetch","IDecode","Enqueue(VectorQ)"], []),
        Instr("VectorOps", ["(ctrl) Vector"], ["Vector(Read L1)","Vector(Scale+Bias)","Write L1"]),
        Instr("Finish",["EventSync"],[])
    ]


def scenario_mte_only() -> List[Instr]:
    return [
        Instr("Fetch/Dispatch", ["IFetch","IDecode","Enqueue(MTEQ)"], []),
        Instr("MTE move", ["(ctrl) MTE"], ["MTE(Decompress)","MTE(Interleave)","MTE(Transpose)","Write L1"]),
        Instr("Finish",["EventSync"],[])
    ]


# ---- 仿真器 ----
@dataclass
class Simulator:
    program: List[Instr] = field(default_factory=list)
    pc: int = 0

    on_visit_ctrl: Callable[[str, str], None] = lambda stage, name: None
    on_visit_data: Callable[[str, str, Dict], None] = lambda stage, name, meta: None
    on_done: Callable[[], None] = lambda: None

    # 参数（可由 UI 修改）
    M: int = 64
    N: int = 64
    K: int = 64
    Tm: int = 16
    Tn: int = 16
    Tk: int = 16
    bits: int = 16
    Wv: int = 32
    gamma_out: float = 1.0
    gamma_in: float = 0.0
    vmax_L1A: int = 4096
    vmax_L1B: int = 2048
    vmax_CW: int  = 2048

    # 统计
    macs: int = 0
    vecops: int = 0
    q_cube: int = 0
    q_vec: int = 0
    q_mte: int = 0

    def reset(self, program: List[Instr]):
        self.program = program
        self.pc = 0
        self.macs = self.vecops = 0
        self.q_cube = self.q_vec = self.q_mte = 0

    # ====== 模型：Vector 下限与理论拍数 ======
    def suggest_Wv(self, K_tile: int = None) -> float:
        Kt = K_tile if K_tile is not None else self.K
        # Wv >= (gamma_out*Tm*Tn)/K + gamma_in*(Tm+Tn)
        return (self.gamma_out * self.Tm * self.Tn) / max(1, Kt) + self.gamma_in * (self.Tm + self.Tn)

    def cube_cycles_theory(self) -> int:
        tiles_m = math.ceil(self.M / self.Tm)
        tiles_n = math.ceil(self.N / self.Tn)
        return tiles_m * tiles_n * self.K  # 每层1拍

    def vector_cycles_theory(self, K_tile: int = None) -> int:
        Kt = K_tile if K_tile is not None else self.K
        ops = self.gamma_out * self.Tm * self.Tn + self.gamma_in * Kt * (self.Tm + self.Tn)
        return math.ceil(ops / max(1, self.Wv))

    # ====== 带宽估算（简洁每拍峰值） ======
    def _bandwidth_for_stage(self, stage: str) -> Dict:
        if "MTE(L1->L0A)" in stage:
            need = self.Tm * self.bits
            return {"kind":"L1->L0A", "bits_per_cycle": min(self.vmax_L1A, need)}
        if "MTE(L1->L0B)" in stage:
            need = self.Tn * self.bits
            return {"kind":"L1->L0B", "bits_per_cycle": min(self.vmax_L1B, need)}
        if "Write C(L1)" in stage or "Write L1" in stage:
            # 简化：按每层产生的C增量估计写流量（通常会缓存在L0C后批量写出）
            need = self.Tm * self.Tn * max(1, self.bits // max(1, self.Tk))
            return {"kind":"L0C->L1", "bits_per_cycle": min(self.vmax_CW, need)}
        return {"kind": "", "bits_per_cycle": 0}

    # ====== 时钟推进 ======
    def step(self):
        if self.pc >= len(self.program):
            self.on_done(); return
        ins = self.program[self.pc]

        cs = ins.curr_ctrl()
        if cs:
            self.on_visit_ctrl(cs, ins.name)
            if "Enqueue(CubeQ" in cs: self.q_cube += 1; self.q_mte += 1
            if "Enqueue(VectorQ" in cs: self.q_vec += 1
            ins.step_ctrl()

        ds = ins.curr_data()
        if ds:
            meta = self._bandwidth_for_stage(ds)
            if "Cube@k" in ds:
                self.macs += self.Tm * self.Tn
                if self.q_cube>0: self.q_cube -= 1
            if "Vector(" in ds and "Read" not in ds:
                self.vecops += self.Tm * self.Tn
                if self.q_vec>0: self.q_vec -= 1
            if "MTE(" in ds and self.q_mte>0: self.q_mte -= 1

            self.on_visit_data(ds, ins.name, meta)
            ins.step_data()

        if ins.done(): self.pc += 1
