# 园区水量漏损排查 · 验证索引

AI/ML / 传统ML · 园区夜间水表异常聚类与巡检工单排序

## 功能模块

| 模块 | 业务职责 | 计算规则 | 核心位置 | 独立测试 |
|---|---|---|---|---|
| M1 | 抄表校验 | 累计读数转区间脉冲，区分寄存器翻转、更换、异常倒转与换区 | `src/meterloss/meter_ingress/register.py` `src/meterloss/meter_ingress/contracts.py` `src/meterloss/meter_ingress/service.py` | `tests/test_meter_ingress.py` |
| M2 | 隔离夜窗 | 用 Fraction 分摊跨夜脉冲，按覆盖率、冲洗及生产标记隔离不可比夜窗 | `src/meterloss/night_windows/integration.py` `src/meterloss/night_windows/contracts.py` `src/meterloss/night_windows/service.py` | `tests/test_night_windows.py` |
| M3 | 用水聚类 | 用冻结 MAD 尺度执行可重现 k-medoids，提供簇置换对齐与按表距离 | `src/meterloss/consumption_clusters/medoids.py` `src/meterloss/consumption_clusters/contracts.py` `src/meterloss/consumption_clusters/service.py` | `tests/test_consumption_clusters.py` |
| M4 | 漏损筛查 | 压力修正与经验尾概率校准，按持续夜数、关阀余流及簇外距离分级 | `src/meterloss/loss_screen/scoring.py` `src/meterloss/loss_screen/contracts.py` `src/meterloss/loss_screen/service.py` | `tests/test_loss_screen.py` |
| M5 | 巡检配次 | 显式优先队列和执勤区、听漏资质、阀门资质、步行和班内时间约束 | `src/meterloss/field_rounds/assignment.py` `src/meterloss/field_rounds/contracts.py` `src/meterloss/field_rounds/service.py` | `tests/test_field_rounds.py` |
| M6 | 水量追溯 | 配次独立核验与工单回执对账，量化已确认损耗、召回和净节水量 | `src/meterloss/water_balance/audit.py` `src/meterloss/water_balance/contracts.py` `src/meterloss/water_balance/service.py` | `tests/test_water_balance.py` |

## 边界案例

| 陷阱 | 触发 | 错误做法 | 实现 | 位置 | 测试 |
|---|---|---|---|---|---|
| TRAP-19 | 安全等级和耗水量同时触发 | 输入顺序排队 | 显式裁决优先级 | `src/meterloss/field_rounds/assignment.py` | `tests/test_field_rounds.py::test_explicit_priority_reproducible` |
| TRAP-23 | 夜窗相邻端点 | 双边计量 | 半开区间按分钟分摊 | `src/meterloss/night_windows/integration.py` | `tests/test_night_windows.py::test_half_open_no_double_count` |
| TRAP-25 | 同效累计读数冲突 | 直接覆盖 | 隔离异常版 | `src/meterloss/meter_ingress/register.py` | `tests/test_meter_ingress.py::test_conflicting_revisions_are_dropped` |
| TRAP-32 | 供压恒定导致 MAD 为零 | 除零 | 稳健尺度底限 | `src/meterloss/consumption_clusters/medoids.py` | `tests/test_consumption_clusters.py::test_constant_scale_no_zero` |
| TRAP-42 | 历史画像延迟入账 | 全部放入聚类 | 按档案时点切分 | `src/meterloss/consumption_clusters/medoids.py` | `tests/test_consumption_clusters.py::test_known_time_isolated` |
| TRAP-43 | 复核无确诊漏点 | 空桶召回按满分 | 明确缺正例 | `src/meterloss/water_balance/audit.py` | `tests/test_water_balance.py::test_empty_class_has_undefined_recall` |
| TRAP-44 | 基线校准样本少及画像越界 | 盲目压低概率触发 | 经验尾概率和簇外拦截 | `src/meterloss/loss_screen/scoring.py` | `tests/test_loss_screen.py::test_far_cohort_refuses_auto_decision` |
| TRAP-52 | 水表簇 id 任意编号 | 按标签直接比 | 组合矩阵全局最优一对一 | `src/meterloss/consumption_clusters/medoids.py` | `tests/test_consumption_clusters.py::test_assignment_after_permutation` |
| TRAP-53 | 请求同时带大流量表 | 重新计算批次尺度 | 冻结 medoid 和统计量 | `src/meterloss/consumption_clusters/medoids.py` | `tests/test_consumption_clusters.py::test_immutable_inference_score` |
| TRAP-54 | 抄表策略版本更新 | 沿用旧签发摘要 | 源版本加入签名 | `src/meterloss/water_balance/audit.py` | `tests/test_water_balance.py::test_upstream_changes_dispatch_stamp` |
