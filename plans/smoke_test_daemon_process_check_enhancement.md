---
**Meta信息**
- 创建时间: 2025-01-23
- 更新时间: 2025-01-23
- 功能名称: 烟雾测试守护进程检查增强
- 负责人: Celestial
- 优先级: 高
---

# 烟雾测试守护进程检查增强计划

## 背景与问题分析

### 当前实现状态

根据代码分析，当前的烟雾测试脚本 `smoke_transfer_check.py` 已经具备了以下功能：

1. **数据库集成已完成**：
   - 已集成 `MediaStatusDB` 类
   - 支持插入测试文件记录到数据库
   - 正确设置 `download_status='completed'` 和 `transfer_status='pending'`
   - 计算并存储文件哈希值

2. **系统诊断功能已实现**：
   - 磁盘空间检查
   - 网络连接检查
   - SSH连接验证
   - 守护进程状态检查
   - 数据库健康检查

3. **配置驱动设计**：
   - 使用统一配置文件 `unified_config.json`
   - 支持灵活的参数配置
   - 完整的错误处理机制

### 用户提出的新需求

用户希望在生成测试文件之前检查守护进程状态，并询问关于数据库锁定风险和SQLite替代方案的问题。

### 核心问题识别

1. **守护进程状态预检查**：在创建测试文件前确保 `media-sync-daemon` 正在运行
2. **数据库并发锁定风险**：两个守护进程同时访问SQLite可能导致锁定
3. **数据库架构评估**：是否需要考虑SQLite的替代方案

## 增强方案设计

### 1. 守护进程预检查增强

#### 实现目标
- 在生成测试文件前强制检查守护进程状态
- 提供守护进程启动建议和故障排除指导
- 支持可选的自动启动功能（需要sudo权限）

#### 技术实现

```python
def check_daemon_prerequisites() -> Tuple[bool, List[str]]:
    """检查守护进程运行的前置条件
    
    Returns:
        (是否满足条件, 问题列表)
    """
    issues = []
    
    # 1. 检查守护进程状态
    daemon_running, daemon_msg = check_daemon_status("media-sync-daemon")
    if not daemon_running:
        issues.append(f"守护进程未运行: {daemon_msg}")
    
    # 2. 检查守护进程配置文件
    service_file = "/etc/systemd/system/media-sync-daemon.service"
    if not os.path.exists(service_file):
        issues.append(f"守护进程服务文件不存在: {service_file}")
    
    # 3. 检查守护进程日志是否有错误
    recent_errors = check_daemon_logs("media-sync-daemon", minutes=10)
    if recent_errors:
        issues.append(f"守护进程最近有错误日志: {len(recent_errors)} 条")
    
    return len(issues) == 0, issues

def provide_daemon_guidance(issues: List[str]) -> None:
    """提供守护进程问题的解决指导"""
    print("\n🔧 守护进程问题解决指导:")
    
    for issue in issues:
        print(f"  ❌ {issue}")
    
    print("\n建议的解决步骤:")
    print("  1. 检查服务状态: sudo systemctl status media-sync-daemon")
    print("  2. 查看服务日志: journalctl -u media-sync-daemon --since '10 min ago'")
    print("  3. 重启服务: sudo systemctl restart media-sync-daemon")
    print("  4. 如果服务未安装，运行: cd celestial_nasops && sudo ./install_daemon.sh")
```

#### 用户交互增强

```python
def interactive_daemon_check(args) -> bool:
    """交互式守护进程检查
    
    Returns:
        是否继续执行测试
    """
    print("正在检查守护进程状态...")
    
    prerequisites_ok, issues = check_daemon_prerequisites()
    
    if prerequisites_ok:
        print("✅ 守护进程状态正常，可以继续执行烟雾测试")
        return True
    
    print("\n⚠️  发现守护进程问题:")
    provide_daemon_guidance(issues)
    
    if args.force:
        print("\n--force 参数已指定，强制继续执行测试")
        return True
    
    # 交互式询问
    while True:
        choice = input("\n是否继续执行测试? (y/n/r) [y=继续, n=退出, r=重新检查]: ").lower().strip()
        if choice in ['y', 'yes']:
            return True
        elif choice in ['n', 'no']:
            return False
        elif choice in ['r', 'recheck']:
            return interactive_daemon_check(args)  # 递归重新检查
        else:
            print("请输入 y, n 或 r")
```

### 2. 数据库并发优化方案

#### 问题分析

当前系统中有两个组件同时访问SQLite数据库：

1. **dock_info_manager** (C++组件)
   - 频率：每5秒检查一次
   - 操作：INSERT新文件记录，UPDATE下载状态

2. **media-sync-daemon** (Python组件)
   - 频率：每10分钟执行一次
   - 操作：SELECT待传输文件，UPDATE传输状态

#### 并发风险评估

**风险等级：中等**

- **锁定概率**：相对较低，因为操作频率不高且持续时间短
- **影响范围**：主要影响烟雾测试和实时同步
- **恢复能力**：SQLite的WAL模式和重试机制可以缓解大部分问题

#### 优化建议

**短期方案（推荐）**：

1. **优化现有SQLite配置**：
   ```json
   {
     "database": {
       "enable_wal_mode": true,
       "connection_timeout_seconds": 30,
       "max_retries": 5,
       "retry_delay_ms": 100,
       "busy_timeout_ms": 10000
     }
   }
   ```

2. **实现连接池管理**：
   ```python
   class DatabaseConnectionPool:
       def __init__(self, db_path: str, pool_size: int = 3):
           self.db_path = db_path
           self.pool = queue.Queue(maxsize=pool_size)
           self._initialize_pool()
       
       def get_connection(self, timeout: int = 30):
           return self.pool.get(timeout=timeout)
       
       def return_connection(self, conn):
           self.pool.put(conn)
   ```

3. **增强错误处理和重试机制**：
   ```python
   def execute_with_retry(self, operation, max_retries=5):
       for attempt in range(max_retries):
           try:
               return operation()
           except sqlite3.OperationalError as e:
               if "database is locked" in str(e) and attempt < max_retries - 1:
                   time.sleep(0.1 * (2 ** attempt))  # 指数退避
                   continue
               raise
   ```

**长期方案（可选）**：

如果并发问题严重，可考虑以下替代方案：

1. **PostgreSQL**：
   - 优点：真正的并发支持，ACID事务，丰富的功能
   - 缺点：需要额外的服务器进程，配置复杂
   - 适用场景：高并发，复杂查询需求

2. **Redis + SQLite混合**：
   - Redis：缓存热数据，队列管理
   - SQLite：持久化存储
   - 适用场景：需要高性能缓存的场景

3. **文件锁 + JSON**：
   - 简单的文件锁机制
   - JSON格式存储
   - 适用场景：数据量小，查询简单

#### 推荐方案

**保持SQLite + 优化配置**，理由：

1. **当前负载适中**：两个进程的访问频率不高
2. **SQLite性能足够**：WAL模式下支持并发读写
3. **部署简单**：无需额外服务，维护成本低
4. **风险可控**：通过重试机制可以处理偶发的锁定问题

### 3. 烟雾测试流程优化

#### 增强的测试流程

```python
def enhanced_smoke_test_flow(args, cfg) -> int:
    """增强的烟雾测试流程"""
    
    # 阶段1：系统预检查
    print("=== 阶段1：系统预检查 ===")
    
    # 1.1 守护进程检查
    if not interactive_daemon_check(args):
        return 1
    
    # 1.2 系统诊断（如果启用）
    if not args.skip_diagnostics:
        diagnostic_results = run_system_diagnostics(cfg)
        if not diagnostic_results["overall_health"] and not args.force:
            print("系统诊断发现问题，使用 --force 强制继续")
            return 1
    
    # 阶段2：测试文件准备
    print("\n=== 阶段2：测试文件准备 ===")
    
    # 2.1 生成测试文件
    filename = generate_test_filename(args.prefix, args.ext)
    local_path, file_size = write_local_file(cfg["local_settings"]["media_path"], filename, args.size_bytes)
    
    # 2.2 计算文件哈希
    file_hash = calculate_file_hash(local_path)
    
    # 2.3 插入数据库记录
    db_success = insert_database_record(cfg, local_path, filename, file_size, file_hash)
    if not db_success and not args.force:
        print("数据库记录插入失败，使用 --force 强制继续")
        return 1
    
    # 阶段3：守护进程监控
    print("\n=== 阶段3：守护进程监控 ===")
    
    # 3.1 等待守护进程处理
    success = monitor_daemon_processing(args, cfg, local_path, filename)
    
    # 阶段4：结果验证和清理
    print("\n=== 阶段4：结果验证和清理 ===")
    
    # 4.1 生成测试报告
    generate_test_report(success, filename, local_path, cfg)
    
    # 4.2 清理测试数据（如果配置启用）
    if cfg.get("smoke_test", {}).get("cleanup_test_files", True):
        cleanup_test_data(local_path, filename, cfg)
    
    return 0 if success else 2
```

### 4. 测试用例和验收标准

#### 功能测试用例

1. **守护进程状态检查测试**
   - 测试场景：守护进程运行时的正常流程
   - 预期结果：检查通过，继续执行测试
   - 验证方法：`systemctl is-active media-sync-daemon` 返回 "active"

2. **守护进程未运行测试**
   - 测试场景：守护进程停止时的处理
   - 预期结果：显示错误信息和解决建议
   - 验证方法：停止守护进程后运行测试

3. **数据库并发测试**
   - 测试场景：同时运行多个烟雾测试实例
   - 预期结果：所有实例都能成功完成，无数据库锁定错误
   - 验证方法：并行执行3个测试实例

4. **网络中断恢复测试**
   - 测试场景：测试过程中网络临时中断
   - 预期结果：网络恢复后测试继续进行
   - 验证方法：测试期间临时断开网络连接

#### 性能测试用例

1. **大文件传输测试**
   - 测试文件大小：1MB, 10MB, 100MB
   - 预期结果：所有文件都能在超时时间内完成传输
   - 验证标准：传输时间 < `sync_timeout_seconds`

2. **批量文件测试**
   - 测试场景：同时创建5个测试文件
   - 预期结果：所有文件都能被正确处理
   - 验证方法：检查所有文件的数据库状态更新

#### 可靠性测试用例

1. **磁盘空间不足测试**
   - 测试场景：本地或远程磁盘空间不足
   - 预期结果：优雅处理错误，提供清晰的错误信息
   - 验证方法：模拟磁盘空间不足的情况

2. **权限问题测试**
   - 测试场景：数据库文件或媒体目录权限不足
   - 预期结果：显示权限错误和解决建议
   - 验证方法：临时修改文件权限

### 5. 实施计划

#### 第一阶段：守护进程检查增强（优先级：高）

**时间估计**：2-3天

**任务清单**：
- [ ] 实现 `check_daemon_prerequisites()` 函数
- [ ] 添加 `interactive_daemon_check()` 交互式检查
- [ ] 实现 `check_daemon_logs()` 日志检查功能
- [ ] 添加 `--force` 参数支持
- [ ] 更新命令行参数解析
- [ ] 编写单元测试

#### 第二阶段：数据库并发优化（优先级：中）

**时间估计**：3-4天

**任务清单**：
- [ ] 优化SQLite配置参数
- [ ] 实现连接池管理（可选）
- [ ] 增强错误处理和重试机制
- [ ] 添加数据库性能监控
- [ ] 编写并发测试用例
- [ ] 性能基准测试

#### 第三阶段：测试流程完善（优先级：中）

**时间估计**：2-3天

**任务清单**：
- [ ] 重构测试流程为阶段化执行
- [ ] 实现详细的测试报告生成
- [ ] 添加测试数据清理功能
- [ ] 完善错误处理和用户指导
- [ ] 编写集成测试

#### 第四阶段：文档和部署（优先级：低）

**时间估计**：1-2天

**任务清单**：
- [ ] 更新用户文档
- [ ] 编写故障排除指南
- [ ] 更新配置文件示例
- [ ] 准备部署脚本

## 验收标准

### 功能验收

- [ ] 烟雾测试在守护进程未运行时能正确检测并提供指导
- [ ] 数据库并发访问不会导致测试失败
- [ ] 所有测试用例都能通过
- [ ] 错误处理机制完善，用户体验良好

### 性能验收

- [ ] 守护进程检查时间 < 5秒
- [ ] 数据库操作响应时间 < 2秒
- [ ] 并发测试成功率 > 95%

### 可靠性验收

- [ ] 异常情况下能优雅退出
- [ ] 提供清晰的错误信息和解决建议
- [ ] 不会留下垃圾文件或数据库记录

## 风险评估与缓解

### 主要风险

1. **数据库锁定风险**
   - 概率：中等
   - 影响：测试失败，用户体验差
   - 缓解措施：重试机制，连接池，优化配置

2. **守护进程依赖风险**
   - 概率：低
   - 影响：测试无法进行
   - 缓解措施：预检查，用户指导，强制模式

3. **网络连接风险**
   - 概率：中等
   - 影响：远程检查失败
   - 缓解措施：重试机制，超时设置，离线模式

### 回滚计划

如果新功能出现问题，可以：
1. 通过配置开关禁用新功能
2. 回退到简化的检查流程
3. 提供兼容模式支持旧版本行为

## 总结

本增强计划旨在解决用户提出的守护进程检查需求，同时优化数据库并发处理，提升烟雾测试的可靠性和用户体验。通过分阶段实施，可以逐步改进系统功能，降低实施风险。

重点改进：
1. **守护进程预检查**：确保测试环境就绪
2. **数据库并发优化**：提升系统稳定性
3. **用户体验改进**：提供清晰的指导和反馈
4. **测试流程完善**：分阶段执行，便于问题定位

建议优先实施第一阶段的守护进程检查增强，这是用户最关心的功能，也是风险最低的改进。