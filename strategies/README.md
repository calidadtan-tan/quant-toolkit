# 经典策略示例

本目录提供零第三方依赖的经典策略参考实现，全部自带模拟行情，可直接运行，用于理解策略思想后再替换为真实行情与专业框架。

## 策略列表

| 文件 | 策略 | 思想 |
| --- | --- | --- |
| sma_cross.py | 双均线交叉 | 快线升穿慢线买入，跌穿卖出 |
| momentum.py | 动量轮动 | 每月持有过去 N 日涨幅最强的资产 |
| grid_trading.py | 网格交易 | 价格区间内高抛低吸 |
| rsi_reversion.py | RSI 均值回归 | 超卖买入、超买卖出 |

## 运行方式

```bash
python sma_cross.py
python momentum.py
python grid_trading.py
python rsi_reversion.py
```

输出包含模拟价格、交易信号、策略收益与基准收益对比。

## 使用真实行情

将模拟数据换成真实行情时，建议：

1. 数据格式统一为 `日期, 收盘价`（多资产则每列一个资产）。
2. 先在回测框架（如本仓库 `projects/backtrader` 或 `projects/qlib`）中验证。
3. 加上手续费与滑点后再评估策略价值。

所有示例均未包含交易成本、滑点与止损逻辑，请勿直接用于实盘。
