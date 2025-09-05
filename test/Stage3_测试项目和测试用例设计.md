# Stage 3 — 测试项目和测试用例设计

## 测试项目 (Test Items)

### 核心模块测试项目

#### TI001: MediaFindingDaemon 媒体发现守护进程
- **模块路径**: `celestial_nasops/media_finding_daemon.py`
- **核心功能**: 文件扫描、哈希计算、传输管理、状态跟踪
- **依赖组件**: MediaStatusDB, StorageManager, SyncLockManager

#### TI002: MediaStatusDB 数据库管理
- **模块路径**: `celestial_nasops/media_status_db.py`
- **核心功能**: 文件状态管理、数据库操作、事务处理
- **依赖组件**: SQLite数据库

#### TI003: StorageManager 存储管理器
- **模块路径**: `celestial_nasops/storage_manager.py`
- **核心功能**: 存储监控、自动清理、空间管理
- **依赖组件**: NAS连接、清理规则配置

#### TI004: SyncLockManager 同步锁管理器
- **模块路径**: `celestial_nasops/sync_lock_manager.py`
- **核心功能**: 进程互斥、锁管理、超时处理
- **依赖组件**: 文件系统锁

#### TI005: 文件传输子系统
- **涉及模块**: rsync命令、SSH连接、网络传输
- **核心功能**: 文件传输、断点续传、传输验证
- **依赖组件**: SSH配置、网络连接

#### TI006: 配置管理系统
- **模块路径**: `celestial_nasops/unified_config.json`
- **核心功能**: 配置加载、参数验证、默认值处理
- **依赖组件**: JSON配置文件

## 测试用例设计

### 功能性测试用例

| ID | Title | Level | Pre-conditions & Data | Steps (Given/When/Then) | Expected Result / Oracle | Priority | Automation? | Notes |
|----|----|----|----|----|----|----|----|----|
| TC001 | 正常文件发现和注册 | Unit | 测试目录包含3个不同大小的媒体文件 | Given: 媒体目录有新文件<br>When: 执行discover_and_register_files()<br>Then: 验证文件被正确注册到数据库 | 数据库中有3条PENDING状态记录，哈希值正确 | High | Yes | 基础功能验证 |
| TC002 | 小文件传输流程 | API | 数据库中有PENDING状态的小文件(<10MB) | Given: 有待传输小文件<br>When: 执行process_pending_files()<br>Then: 文件成功传输到NAS | 文件状态变为COMPLETED，NAS上文件存在且完整 | High | Yes | 核心传输功能 |
| TC003 | 大文件哈希计算 | Unit | 创建100MB+的测试文件 | Given: 大文件存在<br>When: 调用_calculate_file_hash()<br>Then: 使用采样哈希策略 | 返回采样哈希值，计算时间<5秒 | High | Yes | 性能优化验证 |
| TC004 | 重复文件检测 | Unit | 数据库中已有相同哈希的文件记录 | Given: 文件哈希已存在<br>When: 尝试注册相同文件<br>Then: 跳过重复文件 | 不创建新记录，日志显示跳过信息 | High | Yes | 去重机制 |
| TC005 | 存储空间检查 | API | NAS存储使用率设置为85% | Given: 存储空间接近警告阈值<br>When: 执行存储检查<br>Then: 触发警告机制 | 发送警告通知，记录警告日志 | Medium | Yes | 存储监控 |

### 边界条件测试用例

| ID | Title | Level | Pre-conditions & Data | Steps (Given/When/Then) | Expected Result / Oracle | Priority | Automation? | Notes |
|----|----|----|----|----|----|----|----|----|
| TC006 | 超大文件传输(30GB) | API | 创建30GB测试文件 | Given: 30GB文件待传输<br>When: 执行传输流程<br>Then: 验证传输完整性 | 传输成功，文件大小一致，传输时间记录 | High | Partial | 需要大存储空间 |
| TC007 | 空文件处理 | Unit | 创建0字节文件 | Given: 空文件存在<br>When: 执行文件发现<br>Then: 正确处理空文件 | 空文件被跳过或正确处理，无异常 | Medium | Yes | 边界情况 |
| TC008 | 文件名特殊字符 | Unit | 文件名包含中文、空格、特殊符号 | Given: 特殊文件名<br>When: 执行传输<br>Then: 文件名正确处理 | 传输成功，远程文件名正确 | Medium | Yes | 字符编码处理 |
| TC009 | 存储空间满 | API | NAS存储空间设置为99% | Given: 存储空间几乎满<br>When: 尝试传输文件<br>Then: 传输被阻止 | 传输失败，状态保持PENDING，记录错误 | High | Yes | 存储保护 |
| TC010 | 最大并发传输 | API | 配置最大并发数为3 | Given: 4个文件同时传输<br>When: 启动传输<br>Then: 只有3个并发 | 同时传输3个文件，第4个等待 | Medium | Yes | 并发控制 |

### 异常情况测试用例

| ID | Title | Level | Pre-conditions & Data | Steps (Given/When/Then) | Expected Result / Oracle | Priority | Automation? | Notes |
|----|----|----|----|----|----|----|----|----|
| TC011 | 网络中断恢复 | API | 模拟网络中断环境 | Given: 传输进行中<br>When: 网络中断后恢复<br>Then: 传输自动恢复 | 传输继续或重新开始，最终成功 | High | Partial | 需要网络模拟 |
| TC012 | SSH连接失败 | API | SSH服务不可用 | Given: SSH连接失败<br>When: 尝试传输<br>Then: 优雅处理连接错误 | 传输失败，状态为FAILED，记录错误信息 | High | Yes | 连接异常处理 |
| TC013 | 数据库锁定 | Unit | 模拟数据库被锁定 | Given: 数据库被其他进程锁定<br>When: 尝试数据库操作<br>Then: 等待或报错 | 操作等待或失败，不崩溃 | Medium | Yes | 数据库并发 |
| TC014 | 源文件被删除 | API | 传输过程中删除源文件 | Given: 文件在传输队列中<br>When: 源文件被删除<br>Then: 优雅处理文件不存在 | 状态更新为FAILED，记录错误原因 | Medium | Yes | 文件状态变化 |
| TC015 | 磁盘空间不足 | API | 本地磁盘空间不足 | Given: 本地磁盘空间<1GB<br>When: 处理大文件<br>Then: 检测并处理空间不足 | 操作失败，记录空间不足错误 | Medium | Yes | 本地存储保护 |

### 并发和竞态条件测试用例

| ID | Title | Level | Pre-conditions & Data | Steps (Given/When/Then) | Expected Result / Oracle | Priority | Automation? | Notes |
|----|----|----|----|----|----|----|----|----|
| TC016 | 多进程启动冲突 | Job | 同时启动2个守护进程实例 | Given: 系统空闲<br>When: 同时启动2个进程<br>Then: 只有1个进程运行 | 第二个进程检测到锁并退出 | High | Yes | 进程互斥 |
| TC017 | 并发文件扫描 | Unit | 多线程同时扫描同一目录 | Given: 大量文件待扫描<br>When: 并发扫描<br>Then: 无重复处理 | 每个文件只被处理一次，无数据竞争 | Medium | Yes | 线程安全 |
| TC018 | 数据库并发写入 | Unit | 多个线程同时写入数据库 | Given: 多个文件同时注册<br>When: 并发数据库操作<br>Then: 数据一致性 | 所有记录正确写入，无数据损坏 | High | Yes | 数据库事务 |
| TC019 | 锁文件竞争 | Unit | 多进程同时获取锁 | Given: 多个进程启动<br>When: 竞争同一锁文件<br>Then: 只有一个获得锁 | 锁文件状态正确，无死锁 | Medium | Yes | 锁机制验证 |
| TC020 | 传输状态竞争 | API | 同一文件多次传输请求 | Given: 文件传输中<br>When: 再次请求传输<br>Then: 避免重复传输 | 文件只传输一次，状态正确 | Medium | Yes | 状态管理 |

### 恢复能力测试用例

| ID | Title | Level | Pre-conditions & Data | Steps (Given/When/Then) | Expected Result / Oracle | Priority | Automation? | Notes |
|----|----|----|----|----|----|----|----|----|
| TC021 | 系统断电重启恢复 | Job | 传输过程中模拟断电 | Given: 系统运行中<br>When: 模拟断电重启<br>Then: 系统状态恢复 | 重启后继续处理，无数据丢失 | High | Partial | 需要系统级测试 |
| TC022 | 数据库损坏恢复 | Unit | 模拟数据库文件损坏 | Given: 数据库文件损坏<br>When: 系统启动<br>Then: 数据库重建或修复 | 系统正常启动，数据库可用 | Medium | Yes | 数据恢复 |
| TC023 | 配置文件损坏 | Unit | 配置文件格式错误 | Given: 配置文件无效<br>When: 系统启动<br>Then: 使用默认配置 | 系统使用默认值启动，记录警告 | Medium | Yes | 配置容错 |
| TC024 | 日志文件满 | Job | 日志文件达到最大大小 | Given: 日志文件很大<br>When: 继续写入日志<br>Then: 日志轮转或清理 | 日志正常写入，旧日志被轮转 | Low | Yes | 日志管理 |
| TC025 | 传输中断恢复 | API | 大文件传输中断 | Given: 大文件传输50%<br>When: 传输中断<br>Then: 断点续传 | 从中断点继续传输，最终完成 | High | Partial | 断点续传验证 |

### 性能测试用例

| ID | Title | Level | Pre-conditions & Data | Steps (Given/When/Then) | Expected Result / Oracle | Priority | Automation? | Notes |
|----|----|----|----|----|----|----|----|----|
| TC026 | 大量小文件处理 | API | 1000个小文件(<1MB) | Given: 1000个小文件<br>When: 批量处理<br>Then: 性能满足要求 | 处理时间<10分钟，内存使用稳定 | Medium | Yes | 批处理性能 |
| TC027 | 哈希计算性能 | Unit | 不同大小文件(1MB-10GB) | Given: 各种大小文件<br>When: 计算哈希<br>Then: 性能基准 | 大文件采样哈希<5秒，小文件<1秒 | Medium | Yes | 算法性能 |
| TC028 | 内存使用监控 | Job | 长时间运行(24小时) | Given: 系统持续运行<br>When: 监控内存使用<br>Then: 无内存泄漏 | 内存使用稳定，无持续增长 | Medium | Partial | 长期稳定性 |
| TC029 | 数据库查询性能 | Unit | 10000条文件记录 | Given: 大量数据库记录<br>When: 执行查询操作<br>Then: 查询性能 | 查询时间<1秒，索引有效 | Low | Yes | 数据库性能 |
| TC030 | 网络传输效率 | API | 不同网络条件 | Given: 各种网络环境<br>When: 传输文件<br>Then: 传输效率 | 带宽利用率>80%，传输稳定 | Low | Partial | 网络性能 |

## 测试数据策略

### 测试文件生成
```python
# 测试文件生成脚本
def generate_test_files():
    sizes = [
        ("small", 1024 * 1024),      # 1MB
        ("medium", 50 * 1024 * 1024), # 50MB
        ("large", 1024 * 1024 * 1024), # 1GB
        ("xlarge", 30 * 1024 * 1024 * 1024) # 30GB
    ]
    
    for name, size in sizes:
        create_test_file(f"test_{name}.dat", size)
```

### 测试环境数据
- **小文件集**: 100个文件，每个1-10MB
- **中等文件集**: 10个文件，每个50-100MB
- **大文件集**: 3个文件，每个1-5GB
- **超大文件**: 1个文件，30GB
- **特殊文件**: 空文件、特殊字符文件名、损坏文件

### 数据库测试数据
```sql
-- 测试数据插入
INSERT INTO media_files VALUES 
('test1.mp4', '/path/test1.mp4', 'hash1', 1048576, 'PENDING', datetime('now')),
('test2.mp4', '/path/test2.mp4', 'hash2', 52428800, 'DOWNLOADING', datetime('now')),
('test3.mp4', '/path/test3.mp4', 'hash3', 1073741824, 'COMPLETED', datetime('now'));
```

## 测试优先级和执行顺序

### 第一阶段：核心功能验证
1. TC001-TC005: 基础功能测试
2. TC016-TC018: 关键并发测试
3. TC021, TC025: 核心恢复测试

### 第二阶段：边界和异常
1. TC006-TC010: 边界条件测试
2. TC011-TC015: 异常处理测试
3. TC022-TC024: 其他恢复测试

### 第三阶段：性能和稳定性
1. TC026-TC030: 性能测试
2. TC019-TC020: 其他并发测试
3. 长期稳定性测试

## 测试环境要求

### 硬件要求
- **存储**: 至少100GB可用空间（用于大文件测试）
- **内存**: 至少8GB RAM
- **网络**: 可控制的网络环境（支持中断模拟）

### 软件要求
- **操作系统**: Ubuntu 24.04 Server
- **Python**: 3.8+
- **数据库**: SQLite 3
- **网络工具**: rsync, ssh, tc (流量控制)
- **监控工具**: htop, iotop, nethogs

### 测试工具
- **单元测试**: pytest
- **模拟工具**: unittest.mock
- **网络模拟**: tc, iptables
- **性能监控**: psutil, memory_profiler
- **文件生成**: dd, fallocate

---

**下一步**：基于测试用例设计，制定自动化测试策略和环境配置（Stage 4）。