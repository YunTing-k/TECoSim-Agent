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

---

## 项目进度 | Project Progress

### IR Drop 神经网络代理模型 | IR Drop Neural Network Surrogate Model (Jan 2026)
- **数据集生成流水线** (`IRDropNN/src/gen_dataset.py`)：随机生成 PDN 案例，调用 TECoSim 仿真器批量产生原始数据
  **Dataset generation pipeline**: Randomly generates PDN cases and invokes the TECoSim simulator for batch raw data production
- **数据集打包** (`IRDropNN/src/pack_dataset.py`)：将原始数据（图像、电压场、距离场）打包为 HDF5 格式，含归一化、预随机化
  **Dataset packaging**: Packs raw data (images, voltage fields, distance fields) into HDF5 format with normalization and pre-shuffling
- **数据集验证** (`IRDropNN/src/dataset_test.py`)：读写正确性检查与分块读取性能测试
  **Dataset validation**: Read/write correctness checks and chunked reading performance tests
- **UNet 模型定义与实现** (`IRDropNN/src/nn_model.py`)：多层编码器-解码器结构，GroupNorm + ReLU 激活
  **UNet model definition & implementation**: Multi-layer encoder-decoder architecture with GroupNorm + ReLU activation
- **UNet 训练/推理流水线** (`IRDropNN/src/nn_pipeline.py`, `unet_model.py`)：CosineAnnealingLR 学习率调度，支持训练/测试/批量测试模式
  **UNet training/inference pipeline**: CosineAnnealingLR scheduler, supports train/test/batch-test modes
- **UnetLand 增强架构** (`IRDropNN/src/unetland_model.py`)：改进的 UNet 景观模型，含距离场约束，进一步优化预测精度
  **UnetLand enhanced architecture**: Improved UNet landscape model with distance field constraints for further prediction accuracy optimization
- **MATLAB 可视化脚本** (`IRDropNN/script/`)：PDN 布局绘制、UNet/UnetLand 预测结果对比
  **MATLAB visualization scripts**: PDN layout plotting and UNet/UnetLand prediction comparison

### TECoSim 智能体核心框架 | TECoSim Agent Core Framework (Apr.-May 2026)
- **当前版本**: 0.0.16
  **Current version**: 0.0.16
- **Agent 主循环** (`Agent/src/main.py`)：基于 LLM 的流式交互框架，支持快速中断、退出 TUI
  **Agent main loop**: LLM-based streaming interaction framework with fast interruption and TUI exit support
- **工具系统（17个工具） | Tool system (17 tools)** (`Agent/src/tool/`)：
  - 用户交互：`ask_user_question` | User interaction
  - 文件操作：`glob_file`, `grep_file`, `read_file`, `write_file`, `edit_file`（含 TUI diff 编辑视图，只读路径的编辑保护） | File operations (with TUI diff editing view)
  - Shell 执行：`bash`（含命令风险检测分级系统） | Shell execution (with risk-level detection system, and edit protection of readonly paths)
  - 网页获取：`web_fetch`（URL 安全校验、私有网络拦截、HTML-to-Markdown 转换、可配置缓存）、主agent-loop上下文隔离 | Web fetching (URL security check, private network interception, HTML-to-Markdown conversion, configurable cache, main agent-loop context isolation)
  - 网络搜索：`web_search`（Domain黑名单/白名单、可配置代理和搜索模式的四种不同的后端`Exa`/`Tavily`/`Linkup`（需要API key）与`DDGS`（不需要key），主agent-loop上下文隔离 | Web fetching (Domain blacklist/whitelist, four configurable backends: `Exa`/`Tavily`/`Linkup` (API key required) and `DDGS` (no key), with proxy and search mode, main agent-loop context isolation)
  - 技能调用：`skill`（标准技能接口） | Skill invocation (standard skill interface)
  - 仿真器接口：`check_simulator`, `init_design`, `copy_design`, `query_design_list`, `launch_simulator`, `query_run_num`, `read_log` | Simulator interface
- **会话管理** (`Agent/src/context/session.py`)：创建/恢复/删除会话，TUI 历史记录、自动补全、验证器
  **Session management**: Create/resume/remove sessions, TUI history, auto-completion, validators
- **提示词管理** (`Agent/src/context/prompt.py`)：系统提示词组装（角色、指南、环境边界、技能）、DeepSeek 推理支持、消息历史管理、LLM流式响应支持与实时显示（溢出区域自动折叠）
  **Prompt management**: System prompt assembly (role, guidelines, environment boundaries, skills), DeepSeek reasoning support, message history management, stream LLM response support and real-time display (auto folding for overflowed display area)
- **上下文管理** (`Agent/src/context/agent_context.py`)：完整状态序列化（save/load/resume），含 Token 用量统计、权限状态、设计列表
  **Context management**: Full state serialization (save/load/resume) with token usage stats, permission status, design list
- **内置命令系统** (`Agent/src/utility/command.py`)：
  - **仿真设计/运行管理：** 查询设计列表 (`/design_list`)、查询运行次数 (`/run_list`)
  - **信息查询：** 查看上下文用量 (`/context`)、查看已读文件 (`/fread_list`)、查看只读路径 (`/readonly_list`)、查看缓存URL (`/url_caches`)、查看会话列表 (`/session_list`)
  - **会话管理：** 删除会话 (`/session_remove`)
  - **只读路径管理：** 添加只读路径 (`/readonly_add`)、移除只读路径 (`/readonly_remove`)
  - **权限管理：** 查看权限配置 (`/permission_list`)、切换权限开关 (`/permission_toggle`)
  - **技能管理：** 列出可用技能 (`/skill_list`)、列出已加载技能 (`/skills_loaded`)、加载指定技能 (`/<skill_name>`)
  - **MCP管理：** 查看MCP信息 (`/mcp_list`)
  - **其他：** 更新会话标题 (`/update_title`)、查看帮助 (`/help`)
  
  **Built-in command system**:
  - **Simulation Design/Run Management:** Query design list (`/design_list`), query run count (`/run_list`)
  - **Information Queries:** View context usage (`/context`), view read files (`/fread_list`), view read-only paths (`/readonly_list`), view cached URLs (`/url_caches`), view session list (`/session_list`)
  - **Session Management:** Remove session (`/session_remove`)
  - **Read-only Path Management:** Add read-only paths (`/readonly_add`), remove read-only paths (`/readonly_remove`)
  - **Permission Management:** View permission configs (`/permission_list`), toggle permission switches (`/permission_toggle`)
  - **Skill Management:** List available skills (`/skill_list`), list loaded skills (`/skills_loaded`), load a skill (`/<skill_name>`)
  - **MCP Management:** View MCP information (`/mcp_list`)
  - **Others:** Update session title (`/update_title`), view help (`/help`)
- **权限控制** (`Agent/src/tool/ask_permission.py`)：所有敏感操作（文件修改、仿真启动、bash 命令）均需用户确认
  **Permission control**: All sensitive operations (file modification, simulation launch, bash commands) require user confirmation
- **模型分类** (`Agent/src/utility/client.py`)：主模型（复杂/模糊任务）+ 快速模型（简单/确定任务）双模型支持
  **Model classification**: Dual-model support — primary model (complex/ambiguous tasks) + fast model (simple/deterministic tasks)
- **Agent 技能** (`Agent/skills/`)：标准 Anthropic 式技能框架，支持渐进式披露与按需加载
  **Agent skills**: Standard Anthropic-style skill framework with progressive disclosure and on-demand loading
- **Agent MCP支持** (`Agent/mcps/`)：基于`FastMCP`库，支持 `stdio`，`http`，`sse`传输的MCP协议的添加，禁用与移除，内建命令查询MCP配置情况，支持规避同名工具以及多MCP下工具调用的正确路由
  **Agent MCP support**: Based on the `FastMCP` library, supporting `stdio`, `http`, and `sse` transports MCP protocol — adding, disabling, and removing, with built-in commands to query MCP configuration status, supporting avoidance of duplicate tool names and correct routing of tool calls under multiple MCPs
- **工具执行引擎** (`Agent/src/tool/tool_execute.py`)：统一调度与异常捕获
  **Tool execution engine**: Unified scheduling and exception handling
- **配置文件** (`Agent/config/`)：API 连接配置、Agent 运行参数配置、MCP 配置
  **Configuration files**: API connection configuration, Agent runtime parameter configuration, MCP configuration
