# 业务模块与回归证据

AI/ML / 传统ML · 中型

## 功能模块

| 编号 | 业务模块 | 交付内容 | 核心文件 | 测试文件 |
| --- | --- | --- | --- | --- |
| M1 | `stack_cards` | 验签、换版与隔离 | `src/kilnboard/stack_cards/contracts.py` `src/kilnboard/stack_cards/parsing.py` `src/kilnboard/stack_cards/service.py` | `tests/test_stack_cards.py` |
| M2 | `cycle_anchors` | 按可见时点冻结样本和结果 | `src/kilnboard/cycle_anchors/contracts.py` `src/kilnboard/cycle_anchors/revisions.py` `src/kilnboard/cycle_anchors/service.py` | `tests/test_cycle_anchors.py` |
| M3 | `drying_features` | 形成训练与当班共用的领域特征 | `src/kilnboard/drying_features/contracts.py` `src/kilnboard/drying_features/indicators.py` `src/kilnboard/drying_features/service.py` | `tests/test_drying_features.py` |
| M4 | `moisture_tree` | 估计业务结果并输出本地归因 | `src/kilnboard/moisture_tree/contracts.py` `src/kilnboard/moisture_tree/estimator.py` `src/kilnboard/moisture_tree/service.py` | `tests/test_moisture_tree.py` |
| M5 | `stack_backcheck` | 逐窗校准并与历史基线比较 | `src/kilnboard/stack_backcheck/contracts.py` `src/kilnboard/stack_backcheck/calibration.py` `src/kilnboard/stack_backcheck/service.py` | `tests/test_stack_backcheck.py` |
| M6 | `fiber_shift` | 识别缺测、未建档与分布变动 | `src/kilnboard/fiber_shift/contracts.py` `src/kilnboard/fiber_shift/distribution.py` `src/kilnboard/fiber_shift/service.py` | `tests/test_fiber_shift.py` |
| M7 | `probe_windows` | 按业务规则锁定和分派资源 | `src/kilnboard/probe_windows/contracts.py` `src/kilnboard/probe_windows/domain.py` `src/kilnboard/probe_windows/service.py` | `tests/test_probe_windows.py` |
| M8 | `stack_disposition` | 按版本发布、导出、回查与对账 | `src/kilnboard/stack_disposition/contracts.py` `src/kilnboard/stack_disposition/storage.py` `src/kilnboard/stack_disposition/service.py` | `tests/test_stack_disposition.py` |

## 高风险边界

| 编号 | 可观察后果 | 处理位置 | 回归用例 |
| --- | --- | --- | --- |
| TRAP-14 | 同版互斥读数隔离后继续处理其他单据 | `src/kilnboard/cycle_anchors/service.py` | `tests/test_cycle_anchors.py::test_exact_resends_and_conflicts` |
| TRAP-19 | 单据锁定优先于排队和默认动作 | `src/kilnboard/probe_windows/service.py` | `tests/test_probe_windows.py::test_locked_cannot_book` |
| TRAP-23 | 可见日等于截止的单据属于下一个窗口 | `src/kilnboard/cycle_anchors/service.py` | `tests/test_cycle_anchors.py::test_at_cut_is_future` |
| TRAP-26 | 陈旧发布请求保留已生效的派工版 | `src/kilnboard/stack_disposition/service.py` | `tests/test_stack_disposition.py::test_stale_leaves_head` |
| TRAP-32 | 恒定训练轴避免除零和新偏移误放 | `src/kilnboard/drying_features/service.py` | `tests/test_drying_features.py::test_constant_axis` |
| TRAP-42 | 未来修订绝不替换前序训练证据 | `src/kilnboard/cycle_anchors/service.py` | `tests/test_cycle_anchors.py::test_late_revision_cannot_revise_past` |
| TRAP-43 | 回放没有正例时说明指标不可定义 | `src/kilnboard/stack_backcheck/service.py` | `tests/test_stack_backcheck.py::test_no_positive_average_precision` |
| TRAP-44 | 未建档片区会拒识，异常流量高时禁止发布 | `src/kilnboard/fiber_shift/service.py` | `tests/test_fiber_shift.py::test_unseen_blocks_when_majority` |
| TRAP-53 | 批中相邻样本不改变单条评分 | `src/kilnboard/moisture_tree/service.py` | `tests/test_moisture_tree.py::test_point_invariance` |
| TRAP-54 | 账簿参数变化会改变模型摘要并重算 | `src/kilnboard/moisture_tree/service.py` | `tests/test_moisture_tree.py::test_fitted_signature_tracks_source` |
