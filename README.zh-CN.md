# dsh-rigorquant

[English](README.md) | **简体中文**

<p align="center">
  <img src="docs/figs/edgesworth-box.png" alt="Edgeworth box with contract curve and Pareto optimum" width="70%">

</p>
<p align="center"><sub>
  <a href="docs/figs/edgesworth-box.png">埃奇沃思盒</a> —
  由 <a href="https://en.wikibooks.org/wiki/LaTeX/PGF/TikZ">TikZ</a> 手绘，非 AI 生成图
</sub></p>

面向 [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness) 的
**会话内无人值守、长时运行的实证/计算数学研究**框架——覆盖经济学、金融、组合
构建与优化、模拟、计算经济/金融等领域。

RigorQuant 是一个 Agent preset + 内置技能，把一次 DSH 会话变成一个上下文隔离的
多智能体研究实验室：

- **并行探索者**提出候选方法（`explorer-<n>`，空白上下文）。
- **离网思考者（OffGridThinker）**（`offgrid-<n>`）在路线需要隔离时上
  场：只凭模型自身的推理加上计算工具（sympy、numpy、mpmath、Lean 校验器）
  ——无网络、无文献、不使用他人的结果。
- **真值轨道**独立重推导简化情形下的解析闭式解、不变量与界——用两种不同手段
  各推一遍（两个独立的全新 `doublechecker-<n>` 队友）。
- **对抗者**只凭反例淘汰路线。
- **四项检验**（闭式解相等、精确不变量、解析界、统计强化）在数值实现
  **之前**运行。
- **元校验器**（`rq_check.py`）会拒绝证据缺失的 PASS：阶段产物为空、
  `derivations/` 为空、registry 中没有带审计引用的 passed 路线、交付物无法
  编译等。其证据检查只读审计记录，不读 `study.json`——研究不能为自己作证。
- 随机工作采用**固定种子 + 大数定律**约定。
- **jacobian MCP 升级通道**（opt-in；Lean 作为手动外部通道）在实现前解决证明
  关键性断言。
- **PASS → 自动实现并继续；BLOCKED → 同一缺口连续 3 轮 → 交付最强推导 + 精确
  缺口；BUDGET → 5 轮 → 存档 + 报告。**

运行范式改编自金山木医生攻克 Crouzeix 猜想的过程
（[提示词](https://github.com/jinshanmu/CrouzeixConjecture/blob/main/crouzeix_conjecture_prompt.txt)、
[Lean 审计](https://github.com/jinshanmu/CrouzeixConjecture/tree/main/Lean)）
与陶哲轩的 blueprint/等式理论项目，并落到数值工作。完整设计记录：
[docs/architecture.md](docs/architecture.md)。

**"无人值守"的准确含义：**框架在**单个会话内**无人值守运行；跨会话边界会解除
goal，需要一次人工回合（"continue"）重新武装；它不会跨重启自主续跑。

## 研究团队——以及它如何运作

一个枢纽周围的八个角色，每个都是编排者按角色创建、带自己 persona 与工具预算的队友。编排者是唯一能看到所有汇报的角色——队友之间无法互发消息、无法列出花名册、也读不到整个看板——因此这种分离是被强制的，而不是靠约定，**生产者绝不自查自己的成果**：一个想法只会死于具体反例，绝不因风格或感觉而死。

<img src="docs/figs/avatar-orchestrator.png" align="left" width="200" alt="Orchestrator">

**编排者** · `root persona`——扇出工作、综合结果并写状态。受四条铁律约束：生产者≠检查者、只凭反例淘汰、随机运行必记种子、承重命题不许空谈。

<br clear="left">


<img src="docs/figs/avatar-explorer.png" align="left" width="200" alt="Explorer">

**探索者** · `explorer-<n>`——白纸上下文、刻意发散。给出引理、方程、构造与带精确陈述的候选方法；拒绝状态汇报式输出。

<br clear="left">


<img src="docs/figs/avatar-offgrid.png" align="left" width="200" alt="OffGridThinker">

**离网思考者（OffGridThinker）** · `offgrid-<n>`——离网通道。只凭模型自身的推理加上固定的计算通道（sympy、numpy、mpmath、cvxpy、hypothesis、jax；已配置时还有 Lean 校验器）——除此之外什么都没有：无联网、无技能、无委派、不使用他人的结果。它是独立的智能体，不是探索者的变体：隔离即身份。

<br clear="left">


<img src="docs/figs/avatar-doublechecker.png" align="left" width="200" alt="DoubleChecker">

**双重复核（DoubleChecker）** · `doublechecker-<n>`——盲态（无联网、无技能、无委派、无草稿）。从第一性原理把关键命题重推两遍，方法各异。

<br clear="left">


<img src="docs/figs/avatar-adversary.png" align="left" width="200" alt="Adversary">

**对抗者** · `adversary-<n>`——执行检验组、专找反例。以裁决收尾：`PASS` 或 `NEEDS-EDITS`。

<br clear="left">


<img src="docs/figs/avatar-literature.png" align="left" width="200" alt="Literature">

**文献线** · `lit-line-<n>` · `lit-adversary-<n>`——封闭式引文图遍历，再由独立对抗者重取每条主张，确认其真实**且**不过时。

<br clear="left">


<img src="docs/figs/avatar-validator.png" align="left" width="200" alt="Validator">

**校验器** · `rq_check.py` + schemas——证据缺失即拒绝 `PASS`。只读审计记录，绝不读研究自称的主张——研究无法为自己作保。

<br clear="left">


<img src="docs/figs/avatar-document-adversary.png" align="left" width="200" alt="Document adversary">

**文档对抗** · `doc-adversary-<n>`——一个独立智能体，逐一审计每份交付物的**自足性**（约九成 AI 生成内容恰恰会省略这点）：文档用到的每个专业术语、符号与缩写，都必须在文档自身或受众规范的符号表中有定义。返回 `VERDICT: PASS` / `VERDICT: NEEDS-EDITS`；`NEEDS-EDITS` 是阻塞性缺陷，校验器在缺失时会拒绝 `PASS`。

<br clear="left">

### 团队实时视图——原生团队视图

一项 study 跑在 Harness 自带的 Agent Teams 界面上，没有自定义面板要学：
RigorQuant 会话运行期间，点开会话头部的团队动作，就能看到**花名册**（名字、
角色、状态）和本轮的**任务看板**及其阻塞边——要盯的就是这两样。花名册的模型列
显示的是该成员的模型选择，而不是 `rq-model-router` 实际把其请求路由到的模型
（决策 16），因此某个角色的路由要去 **插件 → dsh-rigorquant** 卡片上看，
不要在花名册上读。花名册里每位队友占一行：**点开任意一位**，打开的就是它自己的
会话，于是你可以在它运行的同时读它的推导或审计（直接对话就是普通会话，会打断
该队友的空白上下文——这一点会被记录，但不被阻止）。

拓扑是**枢纽-辐条（hub-and-spoke）**，而且由守卫**强制**成事实而非约定：
队友的消息要么到编排者、要么发不出去；队友无法列出花名册或整个看板；只能读取或
更新没有被其他队友占有的任务（也就是它简报指定的那一条，由它 claim）。下图就是
这一拓扑——编排者居中，它创建的角色为辐条，本轮的任务在下方：

<p align="center">
  <img src="docs/figs/agent-team-activity.svg" width="52%" alt="RigorQuant 团队拓扑——枢纽-辐条式角色与其下方本轮的任务依赖图">
</p>

上图是该视图的读者友好静态渲染，由
[`docs/figs/agent-team-activity.js`](docs/figs/agent-team-activity.js) 生成——
实时花名册与看板只在运行中的 web 会话里可见。它改绘自
[dsh-agent-teams](https://github.com/NanmiCoder/dsh-agent-teams)
的活动面板——[其 README 中的那张图](https://github.com/NanmiCoder/dsh-agent-teams/blob/main/assets/ui.png)——这里展示 RigorQuant 自身八个角色在"扇出"时刻的状态。

> **署名。** 本图改编自
> [dsh-agent-teams](https://github.com/NanmiCoder/dsh-agent-teams) 的活动面板设计，作者
> [NanmiCoder](https://github.com/NanmiCoder)（程序员阿江 / Relakkes）——
> Copyright (c) 2026，MIT 许可证。角色头像为本仓库 `docs/figs/` 自有资源；
> hero 横幅（`docs/figs/agent-team-hero.svg`）同样改自上游 hero 图。

**五步循环。** 每轮＝扇出 → 求真 → 对抗 → 综合。

1. **承诺**——逐字记录原始问题，拆成带明确判据的子问题，挑手算可验的简化情形，钉死种子、容差与 schema／校验器摘要。
2. **扇出**——白纸上下文的探索者与文献线并行运行；大多数不会被告知偏好的路线。
3. **求真**——盲态的 DoubleChecker 不看草稿地重推承重命题；凡研究赖以立足之处，必须有两份独立推导。
4. **攻击**——对抗者先跑四关检验，再找反例；分歧的轨道先排成一份裁定案卷。
5. **认证并交付**——校验器确认无遗漏；论文与幻灯由已验证记录装配，绝不现写。

**检验组**，任何数值实现之前运行：**A** 闭式等价 · **B** 精确不变量 · **C** 解析界 · **D** 统计加固（固定种子 + LLN 按 ≈ C/√N 收缩）。

**有据可查：**一次硬核运行中，21 个错误全部被特定机制捕获、无一靠运气（其中 11 个出自编排者自己）；81 条文献主张中仅 35% 通过独立验证；诚实闸门本身也经测试——一份伪造研究*必须*失败。

## 安装

需要 DSH `>=0.1.7-rc.2 <0.1.8`（决策 25，
`docs/adr/0002-declared-preset-on-dsh-0.1.7.md`）。preset 是一个声明式的
`@deepseek-ai/dsh-agent-preset` 行，路由是路由器那一行自己的 profile 配置，卡片
通过插件页的配置表单编辑它们——更早的宿主上这些都不存在，安装脚本会直接拒绝。
**0.5.0 是支持 0.1.6 alpha 宿主的最后一个版本**：不做任何回移，暂时无法升级宿主
的话，请留在 0.5.0。

这个版本范围是预发布版，团队层还是**实验性**的：本版本只跑在宿主以 **Beta**
卡片形式提供的 **Agent Teams** bundle 上——即 **插件 → 官方** 下带 **Beta**
标记的 *智能体团队（Agent Teams）* 卡片。你可以在那里自行开启，也可以交给完整
安装去做（见下）。

**从 0.5.0 升级**是一次性切换，要在 0.1.7 第一次启动之前完成。先把进行中的
RigorQuant 研究完成或归档：在 0.1.6 宿主上开始的会话，不保证能在新版上恢复。然后：

1. 停止 dsh（所有正在运行的进程，包括 web 应用）。
2. 安装钉在本版本范围所测试版本上的宿主：

   ```sh
   npm i -g @deepseek-ai/dsh@0.1.7-rc.2   # 或 @deepseek-ai/dsh@next
   ```

   不要执行不带版本的 `npm i -g`：npm 的 `latest` 仍是 `0.1.5-rc.3`。
3. 在启动 dsh 之前运行 `./install.sh`（或 `npx dsh-rigorquant`）。它会把你在旧
   `settings.yaml` 里保存的路由，以及保存过的 RigorQuant 默认 preset 迁移过来。
   若 dsh 已经启动过一次，重新运行它会从 `settings.yaml.imported` 中找回它们。
4. 启动 web 应用，在新会话选择器里选 **RigorQuant**。若选择器不见了，请在通用
   设置中重新打开 **代码工作工具**（Coding Tools）：它是选择器唯一的开关，默认
   开启，只有你自己或桌面端引导把它关掉时才会关闭。

扇出受宿主限制：每个 root 同时最多 8 个存活子代理（`maxActiveSubagents`，
**插件 → Subagent**）。文献密集的研究若要让 4 条文献线与探索者并行，可在那里调高。

完整安装会打开那张 **Beta** bundle——即插件页 **官方** 分组下的
*智能体团队（Agent Teams）* 卡片——条件是目标 profile 尚未启用它，且会钉到
core 自身的版本上（若 profile 记录的是别的版本，则改钉回 core 的版本；你自己
启用、没有记录版本号的 bundle 不会被碰）。它总会移除 0.5.0 的 profile 里那个
独立的 *智能体团队 Web UI* bundle，并用一行说明原因：DSH 0.1.7 已把该面板并入
唯一的 bundle，也没有为这个 core 发布 web bundle；移除失败则安装中止。它还会在
profile 的用户补丁（`$DSH_HOME/profiles/<profile>/cordis.patch.yml`）中追加一段
带 `dsh-rigorquant` 标记的配置块，把团队服务的成员数量上限提高到 64，并打印它
写入的每一行。装好之后重复运行不会再有变化；`--uninstall` 只会移除该标记块，
并且只在该标记块记录了"是安装脚本启用的"时才关闭该 bundle——你自己手动启用的
bundle 不受影响。若 PATH 上没有 `dsh`，这一步会打印警告后跳过，其余安装步骤
照常进行——那张 Beta 卡片就留给你在插件页自行开关（参见
docs/adr/0001-rigorquant-on-agent-teams.md）。

两种安装形态：

**Bundle（一条命令）**——仓库声明了 `dsh.bundle` manifest，它自己声明
`rigorquant` preset，其中的 `rq-lane-sync` 行会在 profile 下次启动时，把计算通道
落盘到 `$DSH_HOME/share/rigorquant/`，因此生态的 `dsh plugin add` 安装路径即可获得
完整框架（设计记录：docs/architecture.md 决策 22 与 25）。这条路径既不开启
Agent Teams，也不迁移保存过的路由；这两件事由安装脚本完成：

```sh
dsh --version                 # 必须 >= 0.1.7-rc.2 且 < 0.1.8
dsh plugin --profile web add github:linxichen/dsh-rigorquant
```

启动同步是幂等的（字节一致的目录不动；`.venv` 等派生状态既不复制也不清除）。
它还会删除 0.6.0 之前的版本复制到 `$DSH_HOME` 下的目录式 preset，但仅当该目录
的 `.rq-sync.json` 表明是本包放置的。DSH 的插件 CLI 没有卸载钩子，因此计算通道
的移除始终是显式操作（`./install.sh --uninstall`）。

**安装脚本（完整框架）**——计算通道，以及插件（声明式 preset、角色模型路由器及其
插件页卡片）：

```sh
git clone https://github.com/linxichen/dsh-rigorquant
cd dsh-rigorquant
./install.sh                    # 安装计算通道 + 插件，开启 Agent Teams，迁移保存的路由
# ./install.sh --skill-only     # 或只安装技能（rigorquant、arxiv、academic-paper-search）
# ./install.sh --uninstall      # 移除技能、共享通道与插件
```

启动一个新的 DSH 会话并选择 **RigorQuant** preset，然后说：

> rigorquant：为 [问题] 推导并验证一个方法，先在简化情形上验证，再做数值实现。

## 部署须知

四件需要研究型部署自行决定的事。它们都不是 RigorQuant 自己的机器，安装
RigorQuant 也不会改变其中任何一件：

- **DeepSeek 会话日志默认开启。** base bundle 以 `enabled: true` 挂载
  `session-log-deepseek`：每个会话的规范事件日志都会作为请求元数据上传到
  DeepSeek 官方 API——不占模型输入 token，但整个运行会离开本机。要关掉它，
  在 profile 的用户补丁
  （`$DSH_HOME/profiles/<profile>/cordis.patch.yml`）中覆盖该行，然后重启
  profile——改动在下次启动生效：

  ```yaml
  - id: session-log-deepseek
    config:
      enabled: false
  ```

- **目标轮驱动器（goal-round-driver）是宿主的，而且已经挂好。** goal 服务与
  `goal-round-driver` 是随附 base bundle 的宿主平面行
  （`@deepseek-ai/dsh-base`）；preset 只重新挂载人工的 `/goal` 命令与面向模型的
  goal 工具——这两个在 host 平面上被 web bundle 关掉。本仓库不发布、不挂载、
  也不武装这个轮驱动器："无人值守"是原生契约，跨会话边界仍会解除 goal，直到
  一次人工回合重新武装它（决策 10）。

- **workspace-changes 卡片是"编辑"这件事人类可见的见证。** web bundle 的
  `workspace-changes` 行按 git 工作区快照记录每个顶层回合改动的文件，并在该回合
  下方渲染变更卡片——于是判决之后才落地的编辑，就在它发生的地方、发生的时间被
  看见，这正是决策 19 的冻结写入规则需要人类能看到的东西。认证本身只读研究记录，
  从不读会话（docs/architecture.md 决策 19）。

- **定时任务既不使用，也不受守卫约束。** DSH 0.1.7 发布时定时任务（及其时间
  上下文）是关闭的。RigorQuant 不使用它们，它的逐次调用守卫也不覆盖它们：你自己
  开启的定时任务会跑在团队的枢纽-辐条规则之外。

## 计算通道（一次性）

固定的 uv 通道位于 `$DSH_HOME/share/rigorquant/env`，由 `install.sh` 或插件的
boot-sync 行落盘——两者写入的字节一致，最后运行者持有该锚点（见
[env/README.md](env/README.md)）。venv 本身**从不随包安装**：它是派生状态，
由第一次 `uv run --frozen --project <env_lane>` 在锚点内**惰性创建**（后续
调用即时；`--frozen` 严格遵守已提交的 lockfile）。jacobian 升级通道已**固定版本**
（`jacobian@0.12.0`），它不再是 preset 的一行，而是在运行时挂载：当某个论断需要时，
编排者无需询问就调用 `rq_escalate`，挂载到自己或它点名的某个队友身上，jacobian
工具从下一次请求起出现，直到会话结束。框架在一次性配置前仍会**请求批准**
（`npx -y jacobian@0.12.0 upgrade`，或通过技能内的 `scripts/provision-lean.sh`
安装 Lean 工具链）。详见
[mcp/jacobian.md](mcp/jacobian.md)。

## 角色模型路由（rq-model-router）

内置插件为每个 RigorQuant 角色制定模型与推理强度策略，每个角色各有一个
回退模型。角色身份来自 Team 成员的名字（`<role>-<n>`；Lead 即编排者）——
路由器自身携带已发布的层级矩阵（DoubleChecker 与 adversary 默认使用
`deepseek-v4-pro` @ `high`），并把保存过的路由覆盖在上层。
配置入口：**插件 → dsh-rigorquant**
（该 bundle 自己的页面，位于其描述之下）：只有“保存”才会写入，保存的路由就是
路由器那一行在 profile 的 `cordis.patch.yml` 里的配置，从下一次请求起生效；
离开页面会丢弃未保存的修改。默认配置：

| 角色 | 主选 | 回退 |
| --- | --- | --- |
| 双重复核（DoubleChecker） | `deepseek-v4-pro` @ high | `deepseek-flash` @ low |
| 对抗审计 | `deepseek-v4-pro` @ high | `deepseek-flash` @ low |
| 根编排者、探索者、离网思考者、文献/文档角色 | 继承（root 跟随聊天框选择器） | — |

主选路由遇到终止性失败（无适配器 / HTTP 4xx；包括官方额度响应
`1308` / “Usage limit reached”）时，该角色降级到自己的回退模型并强制重试一次；下一次成功或 10 分钟后恢复主选。不属于 RigorQuant 团队的智能体
（其他 preset，或完全没有 Team 成员身份）一律不受影响。

**只用 DeepSeek 账号登录？** DSH 0.1.7 把 DeepSeek 拆成 `deepseek-official`
（API key）与 `deepseek-account`（账号登录）。当官方路由不可路由（没有 API key）
而账号路由可路由时，上表的默认配置会改用 `deepseek-account` 上同名的模型，这些
请求计入你的账号额度，而不是某个 API key。你自己保存的路由永远不会被改动。
设计记录见 [docs/architecture.md](docs/architecture.md) 决策 16 与 25。

## 仓库结构

```
package.json                dsh.bundle manifest（支持 dsh plugin add）
cordis.patch.yml            bundle patch：技能层 + rq-model-router +
                            rq-team + rq-lane-sync 行
dsh/                        宿主半（角色路由、团队组合与逐调用守卫、
                            启动同步）+ 每角色一个 persona 文件，与 web 客户端包
                            （路由卡片）
agent-presets/
  rigorquant.patch.yml      声明式 `rigorquant` preset（persona + 子行）
  rigorquant/skills/        内置技能
    rigorquant/             SKILL.md + references/ + scripts/ + schemas/
  .../scripts/rq_check.py   元校验器（唯一正式副本）
  .../schemas/              study.json 与 registry.json 的 JSON Schema；
                            校验器直接加载它们，因此二者不会漂移
env/                        固定的 uv 计算通道（sympy/cvxpy/hypothesis/…）
mcp/jacobian.md             升级通道接线说明
docs/architecture.md        逐项确认过的设计决策记录 + 资料来源
docs/figs/agent-team-activity.svg  读者友好的枢纽-辐条拓扑静态图
docs/figs/agent-team-activity.js   其生成脚本（测试锁定不漂移）
docs/figs/agent-team-hero.svg       hero 横幅，改自 dsh-agent-teams
                            的 hero 图（见上方署名）
tests/                      校验器测试套件（见下方"测试"）
studies/                    每项研究一个文件夹（Mode B；各 checkout 自己的
                            活跃研究，不随 bundle 发布）
```

## 测试

校验器自带测试套件，核心是一个**伪造的 study**：空的 derivations、空的阶段
产物、一行字的对抗者报告，以及正文写着"This paper says nothing."的论文。
它必须 FAIL。诚实性闸门若自身没有测试，就会为递给它的任何东西背书。

```sh
uv sync --frozen --project env
uv run --frozen --project env python -m pytest tests/ -q
```

### 提交前覆盖率闸门（校验器 ≥95%）

仓库内的 [`.githooks/pre-commit`](.githooks/pre-commit) 会在覆盖率模式下运行同一
整套测试；已发布的校验器（`rq_check.py`）低于**95% 行覆盖率**时拒绝提交。`./install.sh`
在 git checkout 中自动启用；已有 checkout 可显式执行：

```sh
git config core.hooksPath .githooks
```

校验器以子进程形式运行，因此覆盖率采用显式接线而非插件魔法：`RQ_COVERAGE=1` 让
`tests/conftest.py::run_check` 调用 `coverage run --parallel`；hook 合并子进程数据并
执行 `coverage report --fail-under=95`。CI 运行完全相同的闸门。单次绕过可使用
Git 的标准 `git commit --no-verify`。


`tests/test_repo_consistency.py` 负责另一半：唯一的校验器、唯一的 schema、
文档中可解析的命令、与文件系统一致的目录说明。

**校验器通过意味着什么：**声明的证据齐备、交付物可编译；它**不**意味着数学
是对的——那仍然由检验组、独立真值轨道与对抗者负责。

## 研究（Study）

一项 **study** 即用户的委托：一个自包含的工作单元，各处内部结构完全一致。
持久化成果位于 study 根目录（`study.json`、`STUDY.md`、`registry.json`、
`journal.md`、`derivations/`、`audits/`、`artifacts/`），应当提交；所有草稿
都在被 git 忽略的 `interim/` 中。两种模式，由位置决定：

- **一仓库一研究** — `study.json` 在仓库根目录。
- **一仓库多研究** — `studies/<slug>/study.json`；清单即 `studies/*/study.json`。

启动时检测到已有 study 则静默续跑；新 study 只问一次（模式 + slug），之后不再
询问。详见 [docs/architecture.md](docs/architecture.md) 第 12 条。

## 发布

本仓库是社区 DSH 插件发行物（bundle + preset + 技能形态）：`package.json` 声明
`dsh.bundle` manifest，已打上
[`dsh-plugin`](https://github.com/topics/dsh-plugin) 标签，可被生态内基于
topic 的索引发现——约定参见
[dsh-find-plugins](https://github.com/Nagi-ovo/dsh-find-plugins) 与
[awesome-deepseek-harness](https://github.com/0xsline/awesome-deepseek-harness)。

MIT License。
