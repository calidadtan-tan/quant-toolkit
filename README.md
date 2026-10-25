# Quant Toolkit：量化交易技能与策略集

本仓库收集了大神级开源量化交易项目的完整源码、可运行的经典策略示例，以及已安装的量化分析技能说明，用于学习、研究和二次开发。

## 目录结构

- `projects/`：七个知名开源量化项目的完整源码（当前版本快照）
- `strategies/`：零依赖、可直接运行的经典策略示例（教学用途）
- `README.md`：本说明

## 项目清单

Star 数据为 2026 年 10 月采集，以 GitHub 官方数据为准。

| 项目 | 定位 | Star |
| --- | --- | --- |
| freqtrade | 加密货币自动交易机器人 | 55.9k |
| microsoft/qlib | 微软 AI 量化投资平台 | 49.7k |
| vnpy | 基于 Python 的开源量化交易平台 | 46.0k |
| awesome-quant | 量化金融资源大全 | 30.3k |
| backtrader | 经典回测框架 | 23.6k |
| QuantConnect/Lean | 算法交易引擎（Python/C#） | 22.2k |
| freqtrade-strategies | Freqtrade 社区策略集合 | 5.6k |

## 快速开始

### 运行本仓库的策略示例

需要 Python 3.8 或更高版本，无第三方依赖：

```bash
python strategies/sma_cross.py
```

每个策略脚本都内置了模拟行情，直接运行即可看到信号与收益结果。

### 使用大神级项目

每个项目的安装与使用方法见其自带的 `README.md`，例如：

- Freqtrade：`projects/freqtrade/README.md`
- VN.PY：`projects/vnpy/README.md`
- Qlib：`projects/qlib/README.md`
- Lean：`projects/lean/README.md`

## 已安装的量化分析技能

本机 Skywork 技能库中已安装以下量化技能，可在对话中直接调用：

| 技能 | 用途 |
| --- | --- |
| stock-analysis | 股票与加密货币分析、投资组合管理、热门扫描 |
| fx-carry-trade | 外汇套息交易机会评估 |
| option-vol-analysis | 期权波动率面、Greeks 与隐含/已实现波动率分析 |

## 免责声明

本仓库全部内容仅供学习研究，不构成任何投资建议。历史回测不代表未来收益，实盘交易风险自负。

## 版权与许可

- `projects/` 下各项目版权归其原作者所有，许可见各项目内 `LICENSE` 文件。
- `strategies/` 示例代码与本说明文档以 MIT License 发布。
