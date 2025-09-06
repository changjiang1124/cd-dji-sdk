# 存储空间管理服务（Space Manager）方案 — 方案B（独立进程）

日期：2025-09-06（AWST）
作者：Celestial

## 1. 背景与目标
- 背景：当前“删除与空间回收”能力内聚在同步进程中，存在职责耦合、资源争用与失败域过大的问题。
- 目标：将“空间监测 + 删除策略 + 安全回收”拆出为独立进程，周期性运行，基于“同步完成度 + 空间水位 + 保留策略”做出可回滚、可审计的删除决策，并通过邮件与日志实现可观测与告警。
- 范围：
  - 监测：本地与 NAS 的可用空间、使用率；
  - 决策：基于统一配置与数据库状态，选择可回收集合；
  - 执行：两阶段删除（回收站/隔离区 → 延迟期 → 永久删除）；
  - 通知：水位、批量删除、失败重试、阈值触发等事件的邮件告警；
  - 幂等：重复执行无副作用，失败可重试。

参考文件：
- 统一配置：celestial_nasops/unified_config.json
- 现有删除/存储模块：celestial_nasops/safe_delete_manager.py, celestial_nasops/storage_manager.py
- 锁管理：celestial_nasops/sync_lock_manager.py
- 邮件通知：celestial_nasops/email_notifier.py
- 现有服务单元：
  - /home/celestial/dev/esdk-test/Edge-SDK/celestial_works/config/dock-info-manager.service
  - /home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/media_finding_daemon_user.service

## 2. 现状盘点（磁盘基线）
采集时间：2025-09-06（AWST）
- 本地媒体卷 /data/temp（含 /data/temp/dji/media/）
  - 总量：738,673,549,312 B（≈ 688 GiB），已用：≈ 5.6 MiB，可用：≈ 652.8 GiB+（df 实测显示 1% 使用率）
- 本地根分区 /
  - 总量：105,089,261,568 B（≈ 98 GiB），已用：≈ 18.3 GiB，可用：≈ 74.5 GiB（20% 使用率）
- NAS 目标路径 /volume1/homes/edge_sync/drone_media
  - 总量：7,670,124,396,544 B（≈ 6.98 TiB），已用：≈ 1.54 GiB，可用：≈ 6.97 TiB（1% 使用率）

结论：当前空间极为充裕；但需建立“最小可用空间（Hard Floor）+ 目标清理水位（Target）+ 阈值告警（Warn/Crit）”的长期策略。

## 3. 架构设计
- 进程：独立 Python 服务 space_manager（常驻）或 CLI（被 systemd timer 周期拉起执行 --once）。
- 单一事实来源：沿用本地媒体状态数据库（media_status.db），记录远端路径/大小/校验与 last_verified_at。
- 远端空间测量：通过 SSH（~/.ssh/config Alias=nas-edge）执行 df -P -B1 获取 NAS 路径水位；失败重试与降级。
- 模块复用：
  - 安全删除/回收：safe_delete_manager（两阶段删除 + 延迟期 + pending_deletes.json）
  - 存储检查：storage_manager（扩展为“本地+NAS”双端水位汇总）
  - 锁：sync_lock_manager（跨进程互斥，防止与同步与自身并发冲突）
  - 通知：email_notifier（关键事件邮件）

## 4. 与现有同步进程的解耦策略
- 配置开关迁移：
  - unified_config.json 中 sync_settings.delete_after_sync = true（现状）。建议改为默认 false，将“删除权”移交给 Space Manager；
  - verify_remote_before_delete 由 Space Manager 负责最终裁决（远端存在性/校验通过）。
- 渐进迁移：
  1) 第一阶段：在同步进程中保留删除逻辑但默认关闭，通过配置显式禁用；
  2) 第二阶段：当 Space Manager 稳定后，删除同步进程路径中的删除分支，只保留最小保障的“异常清理”能力；
  3) 回滚预案：若 Space Manager 异常，可临时将 delete_after_sync 打开作为应急（同时严格限制删除范围和批量）。

## 5. 运行与调度（防重入）
- 推荐方式：systemd --user 服务 + timer（celestial 用户会话），避免 root 依赖；
- 防重策略：
  - 外部：systemd timer 触发的 space_manager@.service，默认不会并发重入；
  - 内部：sync_lock_manager + 文件锁/DB 锁；当检测到已有执行中则立即退出，记录“跳过”日志；
  - 超时控制：单轮最大运行时长（如 15 分钟）以避免长时间占用；
- 频率建议：每 10~15 分钟一次；夜间可加大批量与频率。

## 6. 删除策略（安全优先）
- 总体原则：仅删除“已远端校验可用 + 满足保留策略 + 达到清理目标”的文件；所有删除先进入回收站，延迟期后永久删除。
- 候选集：媒体状态为 remote_verified（大小/mtime/可选 checksum 一致）；非 pinned；不在传输中；非黑名单目录。
- 排序规则：优先回收“更老、体积更大、最近未访问”的对象，逐批次处理至达到目标空间。
- 批次与速率：限制每轮最大回收体量（如 50~100 GiB）与 I/O 并发，错峰执行以减少对同步干扰。
- 两阶段删除：
  1) move → 回收站（本地与 NAS 各自独立 Quarantine 目录）；
  2) 延迟期（grace period，如 7 天）后永久删除；
  期间提供“恢复”与“清单审计”能力。
- 干跑：提供 --dry-run 输出候选与将释放空间估算，不执行。

## 7. 阈值与水位（初稿，待确认）
- 本地（/data/temp/dji/media/ 所在卷）：
  - 最小可用空间（Hard Floor）：≥ 100 GiB（满足“一次完整任务”冗余的保守值）；
  - 告警阈值：
    - warning：使用率 ≥ 85% 或 可用 < 150 GiB（任一触发）
    - critical：使用率 ≥ 90% 或 可用 < 100 GiB（任一触发）
  - 清理目标：清理后期望使用率 ≤ 70% 且 可用 ≥ 200 GiB（二者择优达成）。
- NAS（/volume1/homes/edge_sync/drone_media）：
  - 最小可用空间（Hard Floor）：≥ 500 GiB（初稿，可根据飞行频率与保留期再调高至 1 TiB）；
  - 告警阈值：warning ≥ 85% 或 可用 < 1 TiB；critical ≥ 90% 或 可用 < 500 GiB；
  - 清理目标：期望使用率 ≤ 75%。
- 邮件与日志：触发阈值→即时告警；每日 1 次汇总报表（含本地/NAS 水位、回收与失败统计）。

说明：以上阈值与 unified_config.storage_management 的百分比字段需要统一语义（使用率/可用率），建议以“使用率百分比 + 可用空间下限（GiB）”双轨约束，降低极端容量差异的误判。

## 8. 配置项扩展（统一配置 unified_config.json）
新增/对齐建议：
- storage_management：
  - mode: "local_only" | "remote_only" | "both" | "none"
  - local: { warn_percent, crit_percent, min_free_gib, cleanup_target_percent, cleanup_target_min_free_gib }
  - nas:   { warn_percent, crit_percent, min_free_gib, cleanup_target_percent }
  - quarantine: { enabled: true, grace_period_days: 7, local_path, nas_path }
  - dry_run: true|false
  - max_cleanup_bytes_per_round: e.g. 100GiB
  - blacklist_paths / whitelist_paths / pinned_tags
- sync_settings：
  - delete_after_sync: 默认 false（由 Space Manager 接管）

## 9. 服务与部署（示意）
- 推荐：systemd --user
  - space_manager.service：常驻（内部 loop）或一次性工作（ExecStart 调用 --once）。
  - space_manager.timer：OnUnitActiveSec=10min，Persistent=true（补跑 missed 窗口），不与已有任务并发。
- 日志：journald + 结构化文件日志（对齐 logrotate 流程：编辑 logrotate.user.conf → ./sync_logrotate.sh）。
- 权限：不需要 root；使用 celestial 用户执行（与现有 media_finding_daemon_user.service 一致）。

## 10. 失败与回滚
- Space Manager 异常：
  - 自动暂停清理，仅保留监测与告警；
  - 可临时切回 sync_settings.delete_after_sync=true 的同步侧“最小删除功能”（受限批量与黑白名单保护）；
- 远端不可达：
  - 暂停任何依赖“远端校验”的删除，保留本地空间预警；
- 数据一致性：
  - 始终以本地数据库为真，通过 SSH 抽样刷新远端存在性；极端场景可触发全量核对任务（低优先级）。

## 11. 验证与发布计划
- 开发阶段：
  - 单元测试：候选选择、排序、批量边界、幂等；
  - 集成测试：与 media_finding_daemon 并行运行，验证锁与 I/O 限速；
  - 冒烟测试：构造本地空间紧张 → dry-run → 回收站移动 → 延迟后删除 → 邮件告警链路；
- 发布阶段：
  - 第 1 周：同步侧删除禁用，Space Manager 干跑 + 报告；
  - 第 2 周：开启“回收站移动”，不做永久删除；
  - 第 3 周：启用延迟到期的永久删除；

## 12. 与现有进程的代码处理建议
- dock-info-manager.service（C++ 侧）：若含与媒体删除相关的逻辑，建议迁出至 Space Manager，或用配置显式关闭，仅保留日志/告警；
- media_finding_daemon_user.service（Python 侧）：
  - 使用 unified_config.sync_settings.delete_after_sync=false；
  - 保留“异常清理”最小能力（如 tmp 失败文件清扫），避免与 Space Manager 功能重叠；
- 这样既降低职责耦合，又保留在 Space Manager 异常时的应急路径（受控启用）。

## 13. 邮件与运维
- 事件型告警：
  - 阈值越界、批量删除、远端不可达、删除失败重试；
- 每日报告：
  - 本地/NAS 水位、回收站占用、候选/已删除/失败统计、近 24h 失败 TopN；
- 对齐 next.md 的目标：在 dock→edge、edge→NAS 两阶段的“开始/过程/结束/异常”均可发邮件，并新增“磁盘每日汇总与阈值事件告警”。

## 14. 开放问题（待确认）
1) 本地最小可用空间 100 GiB 是否确认？是否需要同时设置“清理后目标可用 200 GiB”？
2) NAS 最小可用空间建议 500 GiB 或 1 TiB，哪个更符合你们的上限规划？
3) 回收站延迟期默认 7 天是否合适？是否需要区分媒体类型（视频/图片）或任务类型？
4) 是否允许在 NAS 侧执行删除？若允许，限定仅移动到 NAS 上的隔离目录（不直接永久删除）。
5) 是否采用 systemd --user（推荐）还是系统级服务？（系统级需要考虑最小权限与读写路径白名单）

——
如认可本方案，我将：
- 起草 unified_config.json 的字段扩展建议清单；
- 产出最小可用 CLI（支持 --once / --dry-run）与 systemd service/timer 示例；
- 编写冒烟测试用例与邮件模板；
- 制定迁移步骤 PR（同步侧默认关闭删除、Space Manager 接管）。