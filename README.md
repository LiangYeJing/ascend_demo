# Ascend Pipeline Simulator (PyQt)

一个用于学习/演示 **华为 Ascend 核心数据通路与指令通路** 的 PyQt 可视化小工具。支持 **GEMM/Conv-im2col/向量后处理/MTE 搬运** 等典型场景；将 **数据流（L1→MTE→L0A/L0B→Cube→Acc→L0C→Vector/Unified→L1）** 与 **控制流（I$→Dispatch→Queues→Event）** 分离展示；内置 **带宽计数、队列可视、MAC/VectorOps 计数** 与 **Cube/Vector/MTE 的细化页面**。

> 适合入门者理解 Ascend 的 1D/2D/3D（Vector/Matmul/Cube）计算风格、数据复用与存储层级的取/写策略。

---

## ✨ 主要特性

* **双通路可视**：数据路径与控制路径独立高亮，避免干扰。
* **三类带宽指示**：`L1→L0A`、`L1→L0B`、`L0C→L1` 以 bits/cycle 显示，峰值上限可设（默认 4096/2048/2048）。
* **队列可视**：`CubeQ / VectorQ / MTEQ` 令牌数随场景推进而变化。
* **算力计数**：累计 **MACs** 与 **VectorOps**。
* **参数化面板**：可设 `M,N,K`、`Tm,Tn,Tk`、元素位宽、`γ_out, γ_in`、`Wv`（向量宽度）、带宽上限等；自动推导 **Vector 建议宽度**与 **理论拍数（Cube/Vector）**。
* **细化页面（双击卡片）**：

  * **MTE**：Decompress / Interleave / Transpose / im2col（含 L1→L0A/L0B 位数累加）；
  * **Cube**：外积 3D 层可视 + 热力图 + 边界 tile（Tm/Tn 不整除）；
  * **Vector**：逐元素流水（Read→Ops→Write），对比 **理论/实测拍数**，直观看到 `Wv` 的影响。
* **场景切换**：`GEMM`、`Conv2D(im2col)`、`Vector-only`、`MTE-only` 一键切换。

---

## 📁 工程结构

```
.
├─ main.py          # 入口：创建 QApplication，启动主窗体
├─ panels.py        # 顶层 UI：数据/控制双通路、带宽/队列/统计栏、场景控制
├─ sim.py           # 轻量仿真器：指令/数据阶段推进、计数与带宽估计
├─ widgets.py       # 通用控件：卡片、队列条、带宽条、控制栏、日志、定时器
├─ details.py       # 细化页：MTE/Cube/Vector 的独立演示对话框
└─ README.md
```

---

## 🧰 环境与运行

### 1) 创建虚拟环境（Windows PowerShell）

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

### 2) 安装依赖

> 优先装 **PyQt5**；如果你更喜欢 PyQt6，也可以安装 PyQt6（本项目含有轻量兼容处理）。

```powershell
pip install PyQt5 numpy
# 仅当你想用 PyQt6：
# pip install PyQt6 numpy
```

> 备注：当前细化页不强依赖 numpy，但主程序后续扩展常会用到，建议安装。

### 3) 运行

```powershell
python main.py
```

---

## 🖥️ 使用说明

* 顶部 **Scenario** 下拉选择场景（默认 GEMM）。
* **参数面板** 调整矩阵/阵列尺寸、位宽、向量宽度与带宽上限，点击 **Apply Params** 应用。
* 点击 **Start/Pause/Step/Reset** 控制推进。
* **双击模块卡片** 打开细化页：

  * **MTE**：演示 Decompress / Interleave / Transpose / im2col（含 L1→L0A/L0B 累计位数）；
  * **Cube**：演示外积逐层累加，热力图显示 C 元素被累加次数；支持边界 tile；
  * **Vector**：演示向量流水，观察 `Wv` 对吞吐的影响与理论拍数对比。
* 界面底部 **日志** 会打印控制/数据阶段的推进与带宽即时值。

---

## 🧩 参数与符号（与 Ascend 术语对齐）

* **阵列尺寸**：

  * `Tm`：Cube 沿输出**行**方向一次并行的行数
  * `Tn`：Cube 沿输出**列**方向一次并行的列数
  * `Tk`：Cube 面向 **K 维**的喂数粒度（影响缓冲/流水；模型中通常 1 层记 1 拍）

* **矩阵大小**：

  * (A \in \mathbb{R}^{M\times K}), (B \in \mathbb{R}^{K\times N}), (C \in \mathbb{R}^{M\times N})

* **向量宽度**：

  * `Wv`：Vector 单元每拍能并行处理的元素数（越大越快）

* **逐元素开销系数**：

  * `γ_out`：每个输出元素的向量操作次数（如 ReLU≈1，FP16↔FP32 两次≈2）
  * `γ_in`：每个被喂入的 A/B 元素需要的向量操作次数（若搬运由专用 MTE 完成可≈0）

* **建议向量宽度**（让 Vector 时间可被 Cube 完全覆盖）：
  [
  W_v ;\ge; \frac{\gamma_{\text{out}}\cdot T_m T_n}{K_\text{tile}} ;+; \gamma_{\text{in}}\cdot(T_m+T_n)
  ]
  本项目会实时给出建议值并对比当前设置。

* **带宽条（bits/cycle）**：

  * `L1→L0A`：激活/输入 A 列段（通常更高；Figure 9 中典型上限 4096）
  * `L1→L0B`：权重/输入 B 行段（通常较低；Figure 9 中典型上限 2048）
  * `L0C→L1`：部分和/结果写回

---

## 🔗 与 Ascend 逻辑的映射

* **MTE**（Memory Transfer Engine）：负责 **Decompress/Pack/Transpose/搬运**，把 L1 数据整形成 **L0A/L0B** 所需布局；
* **Cube**（3D 单元 / 外积阵列）：每拍取 (A[:,k]) 与 (B[k,:]) 做 **外积**，在 **Acc/L0C** 内累加；
* **Vector 单元**：对 C（或中间张量）做 **逐元素**算子：激活、归一化、格式转换等；
* **队列与同步**：`CubeQ / VectorQ / MTEQ` 协调三条流水，`Event Sync` 在关键点做屏障；
* **带宽与复用**：通过 **复用 A 列 / B 行**（一次喂入复用 (T_n/T_m) 次），在 L0A/L0B 内高度重用，降低 L1/DDR 压力。

---

## 🔬 细化页面说明

* **MTE**

  * *Decompress*：模拟位宽扩展（如 8bit→16bit），逐格高亮源/目标；
  * *Interleave/Pack*：两通道交错打包，演示通道拼接；
  * *Transpose*：5×3→3×5 转置；
  * *im2col + BW*：把 H×W×C 滑窗展开为 (H·W)×(Kh·Kw·C)，并**累加 L1→L0A/L0B 的位数**（元素位宽来自主界面）；
* **Cube**

  * 外积逐层（按 k）累加，可开关 **热力图**（C 元素被累加次数）；
  * 支持 **边界 tile**（M/N 小于 Tm/Tn 时），展示阵列实际覆盖区域 rm×rn；
* **Vector**

  * 逐元素流水（Read→Ops→Write），一拍处理 `Wv` 个元素，直观对比 **理论/实测拍数**。

---

