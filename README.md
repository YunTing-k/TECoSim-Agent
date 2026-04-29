# TECoSim Agent: 从跨层次建模到智能体设计
# TECoSim Agent: From Cross-level Modeling to Intelligent Design

<div align="center" style="margin-top: 50px;">
  <img src="./doc/img/logo.png" width="75%" />
</div>

## 简介 | Introduction
### 背景 | Background
现代显示系统一个是典型的具有**多个层次的耦合嵌套的复杂系统**，并可按照设计层次大致划分为物理层、器件层、电路层、面板/宏电路层、驱动/应用层与系统性能层等六个层次。
The modern display systems represent a **complex multi-level coupled hierarchical system**, which can be fundamentally categorized into six design layers: Physical layer, Device layer, Circuit layer, Panel/macro-circuit layer, Driver/application layer, System performance layer.

<div align="center">
  <img src="./doc/img/hierarchy_of_displays.png" width="100%" />
</div>

之前的个人项目[TECoSim仿真器](https://github.com/YunTing-k/TECoSim) （暂未开源），采用**自底向上逐层抽象** + **系统级端到端仿真** 的**跨层次协同的仿真方法**对显示系统进行建模与仿真。
With my previous project [TECoSim Simulator](https://github.com/YunTing-k/TECoSim) (not open yet), we can modeling the display system with a **cross-level co-simulation methodology** that combines **bottom-up hierarchical abstraction** with **system-level end-to-end simulation**.

建模的层级包括 | The modeling levels includes:
1. - **物理层（Material/Interface）**：底层物理材料、界面的光、电学特性
   - **Material/Interface**: The optoelectronic properties of physical materials and interfaces
2. - **器件层（Semiconductor Device）**：驱动晶体管的电流电压、温敏、迟滞特性
   - **Semiconductor Device**: I-V characteristics, thermal sensitivity, and hysteresis behaviors of semiconductor devices
3. - **电路层（Pixel Circuit）**：多个半导体器件组成的像素电路
   - **Pixel Circuit**: Pixel circuits integrate multiple semiconductor devices
4. - **面板/宏电路层（Display Panel）**：由规模化集成的像素电路，考虑寄生电阻/电容的电源网络，以及宏观材质构成的显示面板
   - **Display Panel**: Display panel consisting of a large-scale integrated pixel circuits, power supply network considering parasitic resistance/capacitance, and macro-scale material property
5. - **驱动/应用层（Driving Scheme）**：显示面板的刷新率、灰阶映射算法、颜色抖动算法、亮度控制算法等
   - **Driving Scheme**: Refresh rate, gray-scale mapping algorithms, color dithering, and brightness control schemes, etc.
6. - **系统性能层（Display Quality）**：由以上所有嵌套耦合层次所共同决定的系统最终性能,如显示面板的显示不均一性、色偏、伪影
   - **Display Quality**: The final system performance co-determined by all the above nested coupled hierarchies, such as display non-uniformity, color shift, and artifacts in the display panel

### 敏捷设计的困境 | Dilemma of Agile Design
TECoSim仿真器的提出是为了对多层次耦合的复杂显示系统进行建模与仿真，以便为显示面板设计提供量化的指导，加快前期设计、验证等流程的迭代收敛。
The TECoSim simulator was proposed to model and simulate complex multi-level coupled display systems, aiming to provide quantitative guidance for display panel design and accelerate the iterative convergence of early-stage design, verification, and related processes.

1. 然而TECoSim的跨层级的建模范式使得其使用**门槛较高**，使用者既需要理解从底层到顶层多个不同的设计领域，还需要对数值计算方法也需要有基本的了解，才能针对性地进行参数调优，开展设计与仿真工作。
However, the cross-level modeling paradigm of TECoSim results in a **high barrier to entry**. Users need to understand multiple different design domains ranging from the bottom level to the top level, as well as have a basic understanding of numerical computation methods, in order to perform targeted parameter tuning and carry out design and simulation work effectively.

2. 此外，TECoSim只提供了“设计输入-结果输出”范式的仿真，对于显示系统的优化只能**依赖专家调优**，缺乏高效的自动化调优方法以实现“指标输入-设计输出”的高效设计范式。
Furthermore, TECoSim only provides a "design input → result output" simulation paradigm. Optimization of the display system can only **rely on expert tuning**, lacking efficient automated optimization methods to achieve an efficient "specification input → design output" design paradigm.

---

以上问题限制了TECoSim及其背后的跨层次建模思想在真实场景下的能力，因此诞生了**TECoSim Agent**项目。
These issues limit the capability of TECoSim and the underlying cross-layer modeling philosophy in real-world scenarios, which led to the creation of the **TECoSim Agent** project.


### 项目贡献 | Contribution of this Project
本项目还在开发中，以下是本项目想要完成的基本目标：
This project is still under development. The basic goals are as follows:

**核心目标 | Core Goal**
- 基于TECoSim仿真器，实现一个基于大语言模型的智能体。只用自然语言交互与极少专家干预，根据用户预期的显示面板指标完成整体面板的设计、仿真、验证等工作
- Based on the TECoSim simulator, implement an intelligent agent powered by large language model. Using only natural language interaction and minimal expert intervention, the agent is able to complete the overall panel design, simulation, verification, and related tasks according to the user's expected display panel specifications.

**主要特性 | Main Features**
1. 智能体能够调用TECoSim，自动配置最优仿真参数，解析仿真器输出结果并给出优化建议
    The agent is able to invoke TECoSim, automatically configure the optimal simulation parameters, parse the simulator's output results, and provide optimization suggestions.
2. 智能体能够调用基于神经网络的代理模型，进一步加速耗时的物理场、电路的求解
    The agent is able to invoke neural network-based agent models to further accelerate the solution of time-consuming physical field and circuit simulations.
3. 智能体能基于BO等方法，实现高效的设计空间探索以及多目标的设计优化
    The agent is capable of efficient design space exploration and multi-objective design optimization using methods such as Bayesian Optimization (BO).
