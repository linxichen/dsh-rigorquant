# dsh-rigorquant

[English](README.md) | **简体中文**

面向 [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness) 的
**无人值守、长时运行的实证/计算数学研究**框架——覆盖经济学、金融、组合构建与
优化、模拟、计算经济/金融等领域。

RigorQuant 是一个 Agent preset + 内置技能，把一次 DSH 会话变成一个有隔离墙的
多智能体研究实验室：

- **并行探索者**提出候选方法（`subagent`，空白上下文）。
- **隔离的真值轨道**独立重推导简化情形下的解析闭式解、不变量与界——用两种
  不同手段各推一遍。
- **对抗者**只凭反例淘汰路线。
- **四重校验电池**（闭式解相等、精确不变量、解析界、统计强化）在数值实现
  **之前**运行。
- 随机工作采用**固定种子 + 大数定律**约定。
- **jacobian MCP 升级通道**（Lean 作为最后手段）在实现前解决证明关键性断言。
- **PASS → 自动实现并继续；BLOCKED → 同一缺口连续 3 轮 → 交付最强推导 + 精确
  缺口；BUDGET → 5 轮 → 存档 + 报告。**

运行范式改编自金山木医生攻克 Crouzeix 猜想的过程
（[提示词](https://github.com/jinshanmu/CrouzeixConjecture/blob/main/crouzeix_conjecture_prompt.txt)、
[Lean 审计](https://github.com/jinshanmu/CrouzeixConjecture/tree/main/Lean)）
与陶哲轩的 blueprint/等式理论项目，并落到数值工作。完整设计记录：
[docs/architecture.md](docs/architecture.md)。

## 安装

两种安装形态：

**Bundle（技能层）**——一条命令，让某个 profile 的所有会话都能使用
`rigorquant` 技能；仓库声明了 `dsh.bundle` manifest，生态的
`dsh plugin add` 安装路径可直接使用：

```sh
dsh plugin --profile web add github:linxichen/dsh-rigorquant
```

**Preset（完整框架）**——RigorQuant 智能体预设（persona + 编排 + 工具）及内置技能：

```sh
git clone https://github.com/linxichen/dsh-rigorquant
cd dsh-rigorquant
./install.sh                    # 将 RigorQuant preset 安装到 $DSH_HOME
# ./install.sh --skill-only     # 或只安装 rigorquant 技能，供任意 preset 使用
```

启动一个新的 DSH 会话并选择 **RigorQuant** preset，然后说：

> rigorquant：为 [问题] 推导并验证一个方法，先在简化情形上验证，
> 再做数值实现。

## 计算通道（一次性）

```sh
uv sync --project env            # 生成 env/uv.lock —— 请提交它
```

jacobian 升级通道已接好并可自供给（`npx -y jacobian mcp`）。缺失组件由框架
智能体**自动安装**——Python 运行时（`npx -y jacobian upgrade`）与完整 Lean
通道（`scripts/provision-lean.sh`：elan + 固定工具链 + Mathlib）——无需询问、
无需重启。详见 [mcp/jacobian.md](mcp/jacobian.md)。

## 仓库结构

```
package.json                dsh.bundle manifest（支持 dsh plugin add）
cordis.patch.yml            bundle patch：注册 rigorquant 技能
agent-presets/rigorquant/   preset 组合 + persona + 内置技能
env/                        固定的 uv 计算通道（sympy/cvxpy/hypothesis/…）
mcp/jacobian.md             升级通道接线说明
docs/architecture.md        逐项确认过的设计决策记录 + 资料来源
```

## 发布

本仓库是社区 DSH 插件发行物（bundle + preset + 技能形态）：`package.json`
声明 `dsh.bundle` manifest，已打上
[`dsh-plugin`](https://github.com/topics/dsh-plugin) 标签，可被生态内基于
topic 的索引发现——约定参见
[dsh-find-plugins](https://github.com/Nagi-ovo/dsh-find-plugins) 与
[awesome-deepseek-harness](https://github.com/0xsline/awesome-deepseek-harness)。

MIT License。
