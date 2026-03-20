# Tool Selection Benchmark

离线测试「给定 prompt → agent 选择正确工具」的准确率。不执行真实工具，不需要 Discord，不写文件，不跑 shell。

## 运行

```bash
cd pyagent

# 运行全部用例
uv run python benchmarks/run_bench.py

# 只跑某个标签的用例
uv run python benchmarks/run_bench.py --tag search

# 只跑第 N 条用例（按 id）
uv run python benchmarks/run_bench.py --case 3

# 显示每条用例的实际 vs 期望工具调用
uv run python benchmarks/run_bench.py --verbose
```

## 文件说明

| 文件 | 说明 |
|------|------|
| `cases.json` | 测试用例（21 条，覆盖所有主要工具） |
| `run_bench.py` | 主运行器 |
| `results/YYYY-MM-DD.json` | 每次运行的结果（自动保存） |

## 用例覆盖范围

| 工具 | 用例数 | match_mode |
|------|--------|------------|
| `web_search` | 4 | first_tool |
| `shell_exec` | 4 | first_tool |
| `file_read` | 3 | first_tool |
| `file_write` | 2 | first_tool |
| `memory_append` | 3 | first_tool |
| 不调用工具 | 3 | none |
| 工具链（多工具） | 2 | any |

## match_mode 说明

- **first_tool**：第一个被调用的工具必须在 `expected_tools` 中
- **any**：`expected_tools` 中的每个工具至少被调用过一次
- **none**：不应调用任何工具（纯对话）

## 典型输出

```
PyAgent Tool Selection Benchmark
=================================================================
[PASS]  搜一下今天北京的天气怎么样                          →  ['web_search']
[PASS]  查看一下磁盘使用情况                                →  ['shell_exec']
[FAIL]  读一下 workspace/SOUL.md 的内容                     →  ['file_read']
       期望第一个工具为 ['file_read']，实际为 shell_exec
...
=================================================================
结果: 18/21 通过 (85.7%)
失败用例: 3
结果已保存: benchmarks/results/2026-03-16.json
```

## 使用场景

每次修改 `SOUL.md`、工具 `description` 或提示词后，运行 benchmark 对比准确率变化，量化影响。
