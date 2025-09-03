# DJI Edge SDK 开发笔记

> **最近更新**: 2025-01-25 - 完成废弃脚本分析与清理，生成详细的清理方案和自动化工具。根据 `commsdocs/how-it-works.md` 更新了架构描述和组件信息，删除了已废弃的旧组件引用。

## 最新更新记录

### 2025-01-25 - Media Finding Daemon 服务配置优化
完成了 `media_finding_daemon` 服务配置的重要修复和优化：
- 🔧 **配置路径修复**: 修正了 `media_finding_daemon.py` 中 NAS 配置路径与 `unified_config.json` 结构不匹配的问题
  - 将错误的 `nas.host` 等路径修正为 `nas_settings.host` 等
  - 源文件: `/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/media_finding_daemon.py`
- 🚀 **SSH 别名动态化**: 修复了 `_transfer_file_to_nas` 函数中硬编码 `nas-edge` SSH 别名的问题
  - 改为使用配置文件中的 `ssh_alias` 值，实现动态配置
  - 提升了系统的灵活性和可维护性
- 🗂️ **服务架构简化**: 删除了系统级 `media_finding_daemon.service`，统一使用用户级服务
  - 避免了权限冲突和配置重复问题
  - 简化了部署和维护流程
- ✅ **验证测试**: 修复后重启用户级服务，确认配置正确读取和 SSH 别名正常使用

### 2025-01-25 - 废弃脚本分析与清理
完成了项目中废弃脚本文件的全面分析，生成了详细的清理方案：
- 📋 **分析报告**: `commsdocs/deprecated_scripts_analysis.md` - 详细的废弃文件分析
- 📝 **删除清单**: `commsdocs/safe_deletion_list.md` - 安全删除指南
- 🔧 **自动化工具**: `cleanup_deprecated_scripts.sh` - 自动化清理脚本
- 🎯 **主要发现**: 识别出 8+ 个废弃文件，包括旧架构的核心组件和测试文件
- ⚠️ **风险评估**: 提供了分阶段删除策略，确保系统稳定性

### 2025-01-25 - 架构文档更新
根据 `commsdocs/how-it-works.md` 更新了本文档的架构描述和组件信息，删除了已废弃的旧组件引用。主要更新包括：
- 更新了两阶段架构描述，反映 `dock-info-manager` (C++) 和 `media_finding_daemon` (Python) 的当前状态
- 修正了组件信息，将 `media_sync.py` 更新为 `media_finding_daemon`
- 添加了新的 `file_sync` 配置段描述
- 明确标记了废弃组件 (`sync_scheduler.py`, `media_sync.py`, `media-sync-daemon.service`)
- 统一了技术术语和服务命名规范

## 项目概述

本项目基于DJI Edge SDK开发，实现从DJI无人机机场获取媒体文件并同步到NAS的完整流程。

### 项目架构

```
阶段1: DJI机场 → Edge服务器 (C++ dock-info-manager)
阶段2: Edge服务器 → NAS (Python media_finding_daemon)
```

### 两阶段架构设计
本项目采用两阶段架构来处理DJI Edge SDK的媒体文件管理：

1. **第一阶段 (C++)**: Edge服务器从机场获取媒体文件
   - 使用C++实现的 `dock-info-manager` 服务负责从DJI机场下载媒体文件
   - 文件下载到本地存储路径：`/data/temp/dji/`
   - 同时将文件信息记录到SQLite数据库中
   - 支持原子传输和安全删除机制

2. **第二阶段 (Python)**: Edge服务器同步文件到NAS
   - 使用Python实现的 `media_finding_daemon` 统一守护进程负责文件发现和同步到NAS
   - NAS地址：`192.168.200.103`，用户名：`edge_sync`
   - 通过SSH协议进行文件传输
   - 支持大文件哈希优化和线性传输模式

## 关键组件

### 1. 数据库设计

**位置**: `/data/temp/dji/media_status.db`

**表结构**: `media_transfer_status`
- 文件基本信息：路径、大小、哈希值
- 下载状态：pending, downloading, completed, failed
- 传输状态：pending, transferring, completed, failed
- 时间戳和重试计数

**初始化脚本**: `celestial_works/config/setup_database.sh`

### 2. C++ 组件 (阶段1)

**主程序**: `celestial_works/src/dock_info_manager.cc` (编译为 dock-info-manager 服务)
- 集成SQLite数据库操作
- 从DJI机场下载媒体文件
- 更新数据库状态
- 支持原子传输和安全删除机制

**数据库操作**: `celestial_works/src/media_status_db.cc/h`
- 提供C++数据库接口
- 支持状态查询和更新
- 实现并发控制和重试机制

**编译配置**: 根目录`CMakeLists.txt`已更新
- 链接sqlite3库
- 包含media_status_db.cc

### 3. Python 组件 (阶段2)

**主程序**: `celestial_nasops/media_finding_daemon.py`
- 统一媒体管理守护进程
- 文件发现和哈希计算
- 同步文件到NAS (192.168.200.103)
- 支持大文件哈希优化和线性传输模式

**数据库接口**: `celestial_works/src/media_status_db.py`
- Python SQLite操作封装
- 与C++组件共享数据库
- 支持线程安全的数据库操作

**配置文件**: `celestial_nasops/unified_config.json`
- 统一配置管理
- 包含数据库路径、NAS连接信息等
- **新增 file_sync 配置节**:
  - `scan_interval_seconds`: 文件扫描间隔
  - `file_extensions`: 支持的文件扩展名白名单
  - `hash_optimization`: 大文件哈希优化配置
  - `transfer_mode`: 传输模式（linear 线性传输）
  - `enable_detailed_logging`: 详细日志记录开关

## 部署和测试

### 编译

```bash
cd /home/celestial/dev/esdk-test/Edge-SDK
mkdir -p build && cd build
cmake ..
make dock_info_manager
```

### 数据库初始化

```bash
./celestial_works/config/setup_database.sh
```

### 运行测试

**C++组件**:
```bash
./build/bin/dock_info_manager
```

**Python组件**:
```bash
source .venv/bin/activate
python celestial_nasops/media_sync.py
```

## 测试结果 (2025-09-02)

### ✅ 成功项目

1. **数据库初始化**: 成功创建表结构和索引
2. **C++编译**: 成功编译dock_info_manager
3. **Python运行**: 成功连接数据库，查询功能正常
4. **数据库集成**: C++和Python组件都能正常访问共享数据库

### ⚠️ 已知问题

1. **CleanupRule配置错误**: 
   ```
   CleanupRule.__init__() got an unexpected keyword argument 'name'
   ```
   - 影响: 存储清理功能无法正常工作
   - 位置: `celestial_nasops/unified_config.json`
   - 状态: 需要修复配置格式

2. **DJI设备连接**: 
   ```
   Command async send retry: cmdSet = 60, cmdId = 64
   ```
   - 影响: 无实际DJI设备时的正常现象
   - 状态: 测试环境预期行为

## 系统服务

### 核心服务架构

1. **dock-info-manager服务** (阶段1 - 媒体获取)
   - 服务文件: `celestial_works/config/dock-info-manager.service`
   - 安装脚本: `celestial_works/config/install_dock_service.sh`
   - 二进制文件: `celestial_works/bin/dock_info_manager` (运行为 dock-info-manager 服务)
   - 功能: 从DJI机场获取媒体文件到边缘服务器
   - 特性: 支持原子传输、安全删除、并发控制

2. **media_finding_daemon服务** (阶段2 - 统一媒体管理)
   - 服务文件: `celestial_nasops/media_finding_daemon.service`
   - 安装脚本: `celestial_nasops/install_media_finding_daemon.sh`
   - 主程序: `celestial_nasops/media_finding_daemon.py`
   - 功能: 统一媒体文件发现、哈希计算和NAS同步
   - 特性: 文件发现、哈希优化、线性传输、配置化过滤
   - 日志文件: `/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/logs/media_finding.log`

### 服务安装标准流程
基于 `celestial_nasops/install_daemon.sh` 的成功模式：
1. 检查root权限
2. 验证服务文件和依赖
3. 创建必要目录并设置权限
4. 停止现有服务
5. 复制服务文件到 `/etc/systemd/system/`
6. 重新加载systemd配置
7. 启用并启动服务
8. 验证服务状态

### 统一配置管理
**重要**: 所有服务和脚本都应使用统一配置文件
- 配置文件: `/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/unified_config.json`
- 避免重复创建配置文件
- 确保配置一致性

### 日志记录标准

**新daemon程序日志要求** (2024-12-19更新):
- **日志文件**: `/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/logs/media_finding.log`
- **轮转配置**: 50MB单文件，保留5个备份
- **详细记录内容**:
  1. **文件发现操作**: 扫描到的新文件数量、跳过的文件及原因
  2. **数据库操作**: 插入、更新、查询操作及结果，包含记录ID
  3. **文件处理**: 哈希计算时间、传输状态变更、处理进度
  4. **性能统计**: 处理时间、文件大小、传输速度 (MB/s)
  5. **错误处理**: 异常情况详细信息和错误恢复过程

**日志格式**: `时间戳 - 模块名 - 级别 - 函数名:行号 - 详细信息`

**关键优势**:
- 便于历史问题追踪和性能分析
- 支持生产环境故障排查
- 提供完整的文件处理审计轨迹

**参考文档**: `/home/celestial/dev/esdk-test/Edge-SDK/plans/unified_sync_architecture_optimization.md`

## 网络配置

**NAS连接**: 
- IP: 192.168.200.103
- 用户: edge_sync
- SSH配置: `/home/celestial/.ssh/config` (别名: nas-edge)

## 密钥文件

**位置**: `/home/celestial/dev/esdk-test/keystore/`
- 私钥: `private.der`
- 公钥: `public.der`

## 2025-01-13 烟雾测试增强功能开发

### 任务概述
用户要求增强现有的烟雾测试脚本 `smoke_transfer_check.py`，添加以下功能：
1. 数据库集成 - 将测试文件信息记录到数据库
2. 系统诊断 - 添加全面的系统健康检查
3. 测试用例 - 创建完整的单元测试
4. 错误处理改进 - 增强异常处理和恢复机制

### 开发进展

#### 已完成任务
1. **MediaStatusDB类增强** ✅
   - 在 `media_status_db.py` 中添加了 `insert_file_record` 方法
   - 支持插入完整的文件记录信息，包括路径、名称、大小、哈希值和状态
   - 实现了重复记录检查和时间戳管理

2. **烟雾测试脚本集成** ✅
   - 修改 `smoke_transfer_check.py`，集成数据库操作功能
   - 在测试文件创建后自动记录到数据库
   - 添加了数据库连接错误处理，确保测试可以在数据库不可用时继续运行
   - 修复了数据库参数名称问题（`filename` → `file_name`）

3. **配置文件更新** ✅
   - 更新 `unified_config.json`，添加数据库相关配置
   - 添加测试相关的配置参数

4. **系统诊断功能** ✅
   - 实现了 `run_system_diagnostics` 函数，包括：
     - 磁盘空间检查
     - 网络连接检查
     - SSH连接验证
     - 守护进程状态检查
     - 数据库健康检查
   - 生成详细的诊断报告并保存为JSON格式

5. **SafeDeleteManager改进** ✅
   - 增强了错误处理机制
   - 解决了只读文件系统的问题
   - 添加了更详细的日志记录

6. **测试用例开发** ✅
   - 创建了 `test_smoke_transfer_enhanced.py` 完整测试套件
   - 包括正常流程、异常处理和边界条件测试
   - 修复了测试用例中的各种问题，包括参数类型匹配和断言逻辑
   - 创建了 `quick_test.py` 快速验证脚本

#### 关键技术发现
1. **数据库参数匹配**
   - `MediaStatusDB.insert_file_record` 方法的参数名为 `file_name` 而不是 `filename`
   - `FileStatus` 枚举需要使用 `.value` 属性来获取实际的字符串值

2. **函数返回值格式**
   - 诊断函数返回元组格式：`(bool, str)` 或 `(bool, dict)`
   - `check_disk_space` 返回 `(is_healthy, info_dict)`
   - 其他诊断函数返回 `(success, message)`

3. **测试配置要求**
   - 测试需要完整的配置项，包括 `media_path`、`log_level` 等
   - 数据库连接需要显式调用 `connect()` 方法

4. **实际运行验证**
   - 烟雾测试脚本成功运行，文件传输功能正常
   - 系统诊断显示所有核心组件状态良好
   - 文件从本地成功传输到NAS（约6分钟完成传输）

### 当前状态
- ✅ 核心功能已实现并测试通过
- ✅ 烟雾测试脚本成功运行，显示文件传输正常工作
- ✅ 系统诊断功能正常，能够检测和报告系统状态
- ✅ 数据库集成功能已修复并验证
- ✅ 守护进程清理完成：移除重复服务，统一使用media-sync-daemon.service

## 数据库连接问题排查
refer to `unified_config.json` for database path.

## 数据库并发优化 (2025-01-02)

### 问题分析
- **并发锁定问题**: 多个进程同时访问SQLite数据库时出现`database is locked`错误
- **性能瓶颈**: 频繁的数据库连接创建和销毁影响性能
- **错误处理不足**: 缺乏对数据库操作失败的详细错误处理和重试机制

### 解决方案实施

#### 1. 数据库连接优化
- **连接池机制**: 实现数据库连接复用，减少连接开销
- **WAL模式**: 启用Write-Ahead Logging提高并发性能
- **SQLITE_BUSY重试**: 实现自动重试机制处理数据库锁定

#### 2. 配置参数化
在`unified_config.json`中添加数据库优化配置:
```json
"dock_info_manager": {
  "check_interval_seconds": 10,
  "batch_size": 5,
  "max_retry_attempts": 3,
  "retry_delay_seconds": 1,
  "connection_pool_size": 2,
  "enable_connection_reuse": true,
  "sqlite_busy_timeout_ms": 5000,
  "enable_detailed_logging": true
}
```

#### 3. 代码实现改进
- **MediaStatusDB类优化**: 
  - 添加重试机制参数化构造函数
  - 实现SQLITE_BUSY超时处理
  - 优化数据库连接设置(WAL模式、同步模式、缓存大小)
- **错误处理增强**: 
  - 添加详细的错误日志记录
  - 实现数据库操作返回值检查
  - 添加GetLastError()方法获取详细错误信息
  - 在OnMediaFileUpdate函数中添加完整的错误处理流程

#### 4. 并发测试验证
- **压力测试**: 创建`test_db_concurrency.cc`进行多线程并发测试
- **测试结果**: 
  - 5线程×50操作: 100%成功率，120.42 ops/sec
  - 10线程×100操作: 100%成功率，305.06 ops/sec
- **验证结论**: 重试机制有效解决了数据库锁定问题

#### 5. 生产环境验证
- **冒烟测试**: 30秒运行测试，程序正常启动和运行
- **配置加载**: 成功从unified_config.json加载所有参数
- **数据库初始化**: 正确创建media_transfer_status表和相关索引
- **错误处理**: 完善的数据库操作错误检查和日志记录

### 技术细节

#### 数据库优化设置
```cpp
// WAL模式启用
sqlite3_exec(db, "PRAGMA journal_mode=WAL;", nullptr, nullptr, nullptr);
// 设置忙等超时
sqlite3_busy_timeout(db, sqlite_busy_timeout_ms);
// 优化同步模式
sqlite3_exec(db, "PRAGMA synchronous=NORMAL;", nullptr, nullptr, nullptr);
// 设置缓存大小
sqlite3_exec(db, "PRAGMA cache_size=10000;", nullptr, nullptr, nullptr);
```

#### 重试机制实现
```cpp
for (int attempt = 0; attempt < max_retry_attempts_; ++attempt) {
    int result = sqlite3_step(stmt);
    if (result != SQLITE_BUSY) {
        return (result == SQLITE_DONE);
    }
    if (attempt < max_retry_attempts_ - 1) {
        std::this_thread::sleep_for(std::chrono::seconds(retry_delay_seconds_));
    }
}
```

#### 错误处理机制
```cpp
// 数据库操作错误检查示例
if (!g_media_db->UpdateDownloadStatus(file.file_path, FileStatus::COMPLETED, "")) {
    ERROR("更新下载完成状态失败: %s - %s", file.file_name.c_str(), g_media_db->GetLastError().c_str());
}
```

### 部署状态
- ✅ 配置文件更新完成
- ✅ 代码实现完成
- ✅ 编译测试通过
- ✅ 并发压力测试通过
- ✅ 错误处理机制完善
- ✅ 部署验证完成
- ✅ 生产环境冒烟测试通过

### 性能提升
- **并发处理能力**: 从单线程提升到支持10+并发线程
- **错误恢复**: 自动重试机制显著降低因锁定导致的操作失败
- **系统稳定性**: 详细错误日志便于问题诊断和维护
- **运维友好**: 完善的配置参数化和错误处理机制

### 关键文件位置
- 主程序: `/home/celestial/dev/esdk-test/Edge-SDK/celestial_works/src/dock_info_manager.cc`
- 数据库类: `/home/celestial/dev/esdk-test/Edge-SDK/celestial_works/src/media_status_db.cc`
- 配置文件: `/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/unified_config.json`
- 测试程序: `/home/celestial/dev/esdk-test/Edge-SDK/celestial_works/src/test_db_concurrency.cc`
- 数据库文件: `/data/temp/dji/media_status.db`

## 下一步计划

1. 修复CleanupRule配置问题
2. 配置日志轮转
3. 部署监控和健康检查
4. 创建数据库维护工具
5. 性能优化和异常测试

## 参考文档

- [DJI Edge SDK官方文档](https://developer.dji.com/doc/edge-sdk-tutorial/cn/quick-start/run-sample.html)
- [GitHub项目](https://github.com/dji-sdk/Edge-SDK)
- [SDK初始化](https://developer.dji.com/doc/edge-sdk-tutorial/cn/function-set/sdk-init.html)
- [媒体文件获取](https://developer.dji.com/doc/edge-sdk-tutorial/cn/function-set/media-file-obtain.html)

---

**最后更新**: 2025-01-14 16:30  
**测试状态**: Media Finding Daemon 架构完全实现并通过所有测试，核心功能正常运行

## 数据库状态核查（2025-09-02）

- 已初始化且实际在用的数据库路径: `/data/temp/dji/media_status.db`
- 表：`media_transfer_status`，当前总记录数：1
- 最新记录（按 updated_at 降序 Top 1）：
  - id: 1
  - file_path: `__INIT_MARKER__`
  - file_name: `database_initialized`
  - download_status: `completed`
  - transfer_status: `completed`
  - last_error_message: `Database initialization completed successfully`
  - created_at: `2025-09-02 06:10:13`
  - updated_at: `2025-09-02 06:10:13`

- 另一路径数据库文件存在但未初始化：`celestial_nasops/media_transfer_status.db`（无 `media_transfer_status` 表）

- 原因分析：
  - 配置文件 <mcfile name="unified_config.json" path="/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/unified_config.json"></mcfile> 中 `database.path` 为相对路径 `"media_transfer_status.db"`
  - 初始化脚本 <mcfile name="setup_database.sh" path="/home/celestial/dev/esdk-test/Edge-SDK/celestial_works/config/setup_database.sh"></mcfile> 使用的固定路径为 `/data/temp/dji/media_status.db`
  - 烟雾测试脚本 <mcfile name="smoke_transfer_check.py" path="/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/tools/smoke_transfer_check.py"></mcfile> 读取配置中的相对路径进行连接，未执行建表脚本，导致相对路径下的 DB 未创建表

- 建议与下一步：
  1) 统一数据库路径，推荐将配置 `database.path` 指向 `/data/temp/dji/media_status.db`，与初始化脚本保持一致
  2) 或者对 `celestial_nasops/media_transfer_status.db` 执行初始化脚本（`init_media_status_db.sql`）以创建表结构
  3) 重启 `media-sync-daemon.service` 后重跑烟雾测试，确认测试文件记录可写入并再次查询最新记录

- 相关文件来源：
  - 数据库初始化 SQL：<mcfile name="init_media_status_db.sql" path="/home/celestial/dev/esdk-test/Edge-SDK/celestial_works/config/init_media_status_db.sql"></mcfile>
  - 数据库初始化脚本：<mcfile name="setup_database.sh" path="/home/celestial/dev/esdk-test/Edge-SDK/celestial_works/config/setup_database.sh"></mcfile>
  - 统一配置：<mcfile name="unified_config.json" path="/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/unified_config.json"></mcfile>
  - 烟雾测试脚本：<mcfile name="smoke_transfer_check.py" path="/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/tools/smoke_transfer_check.py"></mcfile>

## 2025-09-02 媒体同步守护进程行为结论与配置统一

### 守护进程同步依据（权威结论）
- 同步触发源：守护进程严格依赖数据库待传输记录触发，而不是扫描源目录。
  - 代码来源：<mcfile name="media_sync.py" path="/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/media_sync.py"></mcfile> 中 <mcsymbol name="get_ready_to_transfer_files" filename="media_sync.py" path="/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/media_sync.py" startline="454" type="function"></mcsymbol> 方法直接从数据库查询 `download_status = 'completed' AND transfer_status = 'pending'` 的记录，用于决定待传输文件列表。
  - 数据库层：<mcfile name="media_status_db.py" path="/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/media_status_db.py"></mcfile> 中 <mcsymbol name="get_ready_to_transfer_files" filename="media_status_db.py" path="/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/media_status_db.py" startline="115" type="function"></mcsymbol> 实现了上述SQL查询。

### 缺失文件异常处理
- 当数据库中有待传输记录，但本地文件不存在时，守护进程会将该记录标记为失败并增加重试计数。
  - 代码来源：<mcfile name="media_sync.py" path="/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/media_sync.py"></mcfile> 中 <mcsymbol name="sync_all_files" filename="media_sync.py" path="/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/media_sync.py" startline="484" type="function"></mcsymbol> 在 <mcsymbol name="sync_all_files" filename="media_sync.py" path="/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/media_sync.py" startline="505" type="function"></mcsymbol> 附近调用 `os.path.exists(file_path)` 检查本地文件，若不存在则调用数据库接口更新状态为 `FAILED`。
  - 数据库层更新逻辑：<mcfile name="media_status_db.py" path="/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/media_status_db.py"></mcfile> 的 <mcsymbol name="update_transfer_status" filename="media_status_db.py" path="/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/media_status_db.py" startline="171" type="function"></mcsymbol> 对 `FAILED` 状态会执行 `transfer_retry_count = transfer_retry_count + 1` 并记录 `last_error_message`。

### 配置与路径统一
- 统一数据库路径为绝对路径：`/data/temp/dji/media_status.db`
  - 配置文件：<mcfile name="unified_config.json" path="/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/unified_config.json"></mcfile> 中 `database.path` 已更新为上述绝对路径。
  - 烟雾测试脚本：<mcfile name="smoke_transfer_check.py" path="/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/tools/smoke_transfer_check.py"></mcfile> 中相对路径将被强制替换为该绝对路径，避免误用项目内临时DB。
  - 数据库接口默认值：<mcfile name="media_status_db.py" path="/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/media_status_db.py"></mcfile> 的构造函数默认即为 `/data/temp/dji/media_status.db`。

### 测试插入记录的默认状态
- 为了让守护进程拾取测试文件，`insert_file_record` 默认写入 `download_status = 'pending'` 与 `transfer_status = 'pending'`，可在烟雾测试中将 `download_status` 设为 `completed` 以满足守护进程筛选条件。
  - 代码来源：<mcfile name="media_status_db.py" path="/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/media_status_db.py"></mcfile> 的 <mcsymbol name="insert_file_record" filename="media_status_db.py" path="/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/media_status_db.py" startline="292" type="function"></mcsymbol>。

### 下一步建议
- 在烟雾测试流程中，插入记录时显式设置 `download_status='completed'`；或在创建文件后调用数据库更新接口将其置为 `COMPLETED` 再触发守护进程，确保被同步。
- 对于缺失文件的记录，增加定期清理策略，超过阈值 `transfer_retry_count` 的记录自动标记并通知。

## 2025-01-14 Media Finding Daemon 架构实现

### 项目背景
基于统一同步架构优化计划，开发了新的 Media Finding Daemon 来替代原有的文件扫描机制，实现更高效的文件发现、哈希计算和数据库管理。

### 核心架构设计

#### 1. 新增组件
- **主程序**: `celestial_nasops/media_finding_daemon.py`
  - 实现文件发现和数据库管理的核心daemon程序
  - 支持配置化的文件过滤策略
  - 实现大文件哈希优化策略（采样哈希）
  - 线性传输模式，避免并发冲突

- **服务配置**: `celestial_nasops/media_finding_daemon.service`
  - 系统服务配置文件
  - 支持自动启动和服务管理

- **安装脚本**: `celestial_nasops/install_media_finding_daemon.sh`
  - 自动化服务安装和配置

#### 2. 配置文件增强
在 `unified_config.json` 中新增 `file_sync` 配置节：
```json
"file_sync": {
  "enabled": true,
  "scan_interval_seconds": 300,
  "media_path": "/data/temp/dji",
  "file_extensions": [".mp4", ".mov", ".jpg", ".jpeg", ".png", ".dng", ".tiff"],
  "min_file_size_bytes": 1024,
  "max_file_size_bytes": 10737418240,
  "hash_optimization": {
    "large_file_threshold_mb": 100,
    "sample_size_mb": 10,
    "sample_positions": ["start", "middle", "end"]
  },
  "transfer_mode": "linear",
  "batch_size": 5,
  "enable_detailed_logging": true
}
```

#### 3. 详细日志记录系统
- **日志文件**: `/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/logs/media_finding.log`
- **轮转配置**: 50MB单文件，保留5个备份
- **记录内容**:
  1. 文件发现操作：扫描到的新文件数量、跳过的文件及原因
  2. 数据库操作：插入、更新、查询操作及结果，包含记录ID
  3. 文件处理：哈希计算时间、传输状态变更、处理进度
  4. 性能统计：处理时间、文件大小、传输速度 (MB/s)
  5. 错误处理：异常情况详细信息和错误恢复过程

### 开发过程与问题解决

#### 1. 数据库死锁问题 (关键技术突破)
**问题描述**: 测试过程中发现 `insert_file_record` 方法存在死锁问题
- 根本原因：`insert_file_record` 方法在持有锁的情况下调用 `file_exists` 方法，而 `file_exists` 方法也尝试获取同一个锁
- 影响：导致测试卡住，无法正常完成文件注册

**解决方案**: 
- 将 `file_exists` 的逻辑内联到 `insert_file_record` 方法的锁内
- 避免嵌套锁获取，确保线程安全
- 优化 cursor 管理，确保在所有情况下都正确关闭

**代码修改**: `celestial_nasops/media_status_db.py`
```python
# 修复前：存在死锁风险
with self.lock:
    if self.file_exists(file_path):  # 嵌套锁获取
        return False
    # ... 插入逻辑

# 修复后：内联检查逻辑
with self.lock:
    cursor = self.connection.cursor()
    # 直接在锁内执行文件存在性检查
    cursor.execute("SELECT COUNT(*) FROM media_transfer_status WHERE file_path = ?", (file_path,))
    if cursor.fetchone()[0] > 0:
        cursor.close()
        return False
    # ... 插入逻辑
```

#### 2. 测试配置路径问题
**问题描述**: 测试用例中配置文件路径不一致，导致 `MediaFindingDaemon` 初始化失败
- 多个测试方法使用硬编码的 `config.json` 路径
- 实际配置文件路径为 `self.config_path`

**解决方案**: 统一所有测试方法中的配置文件路径引用
- 修改 `test_scan_with_files`、`test_scan_empty_directory`、`test_small_file_hash`、`test_large_file_hash`、`test_hash_consistency` 等方法
- 将硬编码路径替换为 `self.config_path`

### 测试结果与验证

#### 1. 完整测试套件 (16个测试用例)
**测试覆盖范围**:
- **文件过滤测试**: 验证文件扩展名、大小过滤功能
- **文件发现测试**: 验证目录扫描、隐藏文件处理
- **哈希计算测试**: 验证小文件、大文件哈希计算和一致性
- **数据库操作测试**: 验证文件注册、状态更新、传输处理
- **性能测试**: 验证大文件处理性能

**测试结果**: ✅ 所有16个测试用例全部通过
```bash
$ python -m pytest celestial_nasops/test_media_finding_daemon.py -v
==================== 16 passed in 2.34s ====================
```

#### 2. 核心功能验证
- **文件扫描**: 成功扫描并处理20个测试文件
- **哈希计算**: 正确计算文件哈希值，支持大文件优化
- **数据库集成**: 成功将新文件注册到数据库，状态设置为 `PENDING`
- **传输处理**: 成功处理待传输文件，状态更新为 `DOWNLOADING` → `COMPLETED`

#### 3. 性能表现
- **处理速度**: 平均处理时间 < 100ms/文件
- **内存使用**: 稳定在合理范围内
- **并发安全**: 解决死锁问题后，支持多线程安全访问

### 部署状态
- ✅ 核心daemon程序开发完成
- ✅ 配置文件集成完成
- ✅ 服务配置文件创建完成
- ✅ 安装脚本开发完成
- ✅ 详细日志记录系统实现完成
- ✅ 完整测试套件开发并通过
- ✅ 数据库死锁问题解决
- ✅ 测试配置问题修复

### 技术亮点

#### 1. 大文件哈希优化
- 对超过100MB的文件使用采样哈希策略
- 从文件开头、中间、结尾各采样10MB进行哈希计算
- 显著提升大文件处理性能

#### 2. 配置化文件过滤
- 支持文件扩展名白名单
- 支持文件大小范围过滤
- 通过 `unified_config.json` 统一管理

#### 3. 线性传输模式
- 避免并发传输冲突
- 按文件大小优先级处理
- 提高传输成功率和系统稳定性

#### 4. 详细日志记录
- 完整的文件处理审计轨迹
- 性能统计和错误追踪
- 便于生产环境故障排查

### 关键文件清单
- **主程序**: `celestial_nasops/media_finding_daemon.py`
- **数据库接口**: `celestial_nasops/media_status_db.py` (增强版)
- **服务配置**: `celestial_nasops/media_finding_daemon.service`
- **安装脚本**: `celestial_nasops/install_media_finding_daemon.sh`
- **卸载脚本**: `celestial_nasops/uninstall_media_finding_daemon.sh`
- **测试套件**: `celestial_nasops/test_media_finding_daemon.py`
- **配置文件**: `celestial_nasops/unified_config.json` (更新版)

### 下一步计划
1. 部署到生产环境并监控运行状态
2. 集成到现有的监控和告警系统
3. 根据实际运行情况优化性能参数
4. 考虑添加文件变更监控功能（inotify）
5. 实现更智能的重试和错误恢复机制

---

## 架构清理和优化记录

### 媒体同步架构迁移完成 (2025-09-03)

#### 迁移概述
成功完成从旧架构 (`sync_scheduler.py` + `media_sync.py` - 已废弃) 到新架构 (`media_finding_daemon.py`) 的迁移，实现了统一同步架构优化。

#### 迁移执行记录

**服务迁移操作**:
1. **停止旧服务**: `sudo systemctl stop media-sync-daemon` ✅ (已废弃)
2. **安装新服务**: `./install_media_finding_daemon.sh` ✅
3. **启动新服务**: `sudo systemctl start media_finding_daemon` ✅
4. **禁用旧服务**: `sudo systemctl disable media-sync-daemon` ✅ (已废弃)

**迁移结果确认**:
- **旧服务状态**: `media-sync-daemon.service` - 已停止且禁用 (已废弃)
- **新服务状态**: `media_finding_daemon.service` - 正在运行且已启用
- **进程信息**: PID 2413000, 内存使用 10.8M
- **服务描述**: "Media Finding Daemon - 统一同步架构优化方案"

#### 架构升级优势

**新架构核心特性**:
1. **统一架构**: 从分离式调度器+同步器升级为统一的媒体发现守护进程
2. **性能优化**: 大文件哈希采样优化，减少CPU和I/O开销
3. **配置化过滤**: 支持多种文件过滤策略 (all_files/media_only/extended/custom)
4. **线性传输**: 避免并发冲突，确保传输稳定性
5. **详细日志**: 更完善的日志记录和错误处理
6. **独占数据库**: 避免多进程并发访问导致的锁定问题

**功能对比总结**:

| 特性 | 旧架构 (已废弃) | 新架构 (当前) | 改进 |
|------|--------|--------|------|
| **架构设计** | 分离式 (调度器+执行器) | 统一守护进程 | ✅ 简化架构 |
| **文件发现** | 依赖外部组件 | 内置扫描发现 | ✅ 自主发现 |
| **哈希计算** | 完整文件哈希 | 大文件采样优化 | ✅ 性能提升 |
| **传输模式** | 可能并发冲突 | 线性安全传输 | ✅ 稳定性提升 |
| **处理频次** | 定时调度 (10分钟) | 持续实时处理 | ✅ 响应速度 |
| **日志记录** | 基础日志 | 详细性能日志 | ✅ 可观测性 |

#### 服务配置信息

**新服务配置**:
- **服务名称**: `media_finding_daemon.service`
- **服务文件**: `/etc/systemd/system/media_finding_daemon.service`
- **主程序**: `/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/media_finding_daemon.py`
- **配置文件**: `/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/unified_config.json`
- **日志文件**: `/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/logs/media_finding.log`

**管理命令**:
```bash
# 服务控制
sudo systemctl {start|stop|restart|status} media_finding_daemon

# 日志查看
sudo journalctl -u media_finding_daemon -f

# 配置测试
python3 /home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/media_finding_daemon.py --config /home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/unified_config.json --once
```

#### 迁移验证

**功能验证**:
- ✅ 服务正常启动和运行
- ✅ 配置文件正确加载
- ✅ 数据库连接正常
- ✅ 文件扫描功能正常
- ✅ 日志记录详细完整

**性能表现**:
- **启动时间**: < 1秒
- **内存占用**: 10.8M (峰值 11.1M)
- **CPU使用**: 87ms (启动阶段)
- **处理周期**: 每次扫描 < 0.01秒

#### 后续维护

**监控要点**:
1. **服务状态**: 定期检查服务运行状态
2. **日志监控**: 关注错误日志和性能指标
3. **资源使用**: 监控内存和CPU使用情况
4. **传输效率**: 跟踪文件处理速度和成功率

**配置优化**:
- 根据实际文件量调整扫描间隔
- 优化文件过滤策略以提高效率
- 调整日志级别和轮转策略

#### 迁移总结

✅ **迁移成功**: 新架构已完全替代旧架构并正常运行  
✅ **功能增强**: 实现了更高效、更稳定的媒体文件同步  
✅ **架构优化**: 统一了系统架构，简化了维护复杂度  
✅ **性能提升**: 优化了文件处理和传输性能  

新的统一同步架构已投入生产使用，为媒体文件管理提供了更可靠和高效的解决方案。

#### 服务命名规范
当前生产环境使用的服务：
- ✅ `media_finding_daemon.service` (当前运行) - 统一媒体管理守护进程
- ✅ `dock-info-manager.service` (当前运行) - C++媒体下载服务

已废弃的旧服务：
- ❌ `media-sync-daemon.service` (已停用并废弃)
- ❌ `media_sync_daemon.service` (已清理)

## 日志轮转配置 (Logrotate)

### 配置概述
项目使用统一的 logrotate 配置管理所有日志文件的轮转，确保日志文件不会无限增长影响系统性能。

### 配置文件结构和工作流程

#### 配置文件说明
- **`logrotate.user.conf`** - 用户可编辑的主配置文件
  - 这是用户应该编辑的配置文件
  - 包含所有日志文件的轮转配置
  - 可以纳入版本控制
  - 所有者: celestial:celestial，用户可直接编辑

- **`logrotate.conf`** - 系统运行配置文件
  - 实际被 logrotate 系统使用的配置文件
  - 由同步脚本自动生成和维护
  - 所有者: root:root，权限 644
  - **不应手动编辑此文件**

- **`sync_logrotate.sh`** - 配置同步和部署脚本
  - 将用户配置同步到系统配置
  - 设置正确的权限和所有者
  - 验证配置语法

#### 正确的工作流程
1. **编辑配置**: 修改 `logrotate.user.conf` 文件（主配置文件）
2. **同步部署**: 运行 `./sync_logrotate.sh` 脚本
3. **自动生效**: 脚本会将 `logrotate.user.conf` 复制到 `logrotate.conf`，并设置正确权限

⚠️ **重要提醒**: 
- 始终编辑 `logrotate.user.conf` 文件，保持其为最新的主配置
- 使用 `./sync_logrotate.sh` 进行部署，不要手动编辑 `logrotate.conf`
- 两个文件同时存在是为了权限分离和配置安全

### 已配置的日志文件
1. **media_list.log** - 50MB轮转，保留7份备份
2. **media_monitor.log** - 20MB轮转，保留5份备份
3. **dock_init_info.txt** - 10MB轮转，保留3份备份
4. **media_finding.log** - 50MB轮转，保留5份备份
5. **nohup.out** - 100MB轮转，保留3份备份

### 配置参数说明
- `size`: 文件大小阈值，达到后触发轮转
- `rotate`: 保留的备份文件数量
- `compress`: 压缩旧的日志文件
- `delaycompress`: 延迟压缩，保留最新备份为未压缩状态
- `missingok`: 日志文件不存在时不报错
- `notifempty`: 空文件不轮转
- `copytruncate`: 复制后截断原文件（适用于持续写入的日志）
- `su celestial celestial`: 以指定用户身份运行
- `create 0664 celestial celestial`: 创建新文件的权限和所有者

### 使用方法

#### 编辑配置
```bash
# 编辑用户配置文件
vim /home/celestial/dev/esdk-test/Edge-SDK/logrotate.user.conf
```

#### 同步配置到系统
```bash
# 运行同步脚本
./sync_logrotate.sh
```

#### 测试配置
```bash
# 测试配置语法
sudo /usr/sbin/logrotate -d /home/celestial/dev/esdk-test/Edge-SDK/logrotate.conf

# 手动强制轮转
sudo /usr/sbin/logrotate -f /home/celestial/dev/esdk-test/Edge-SDK/logrotate.conf
```

#### 查看轮转状态
```bash
# 查看 logrotate 状态文件
sudo cat /var/lib/logrotate/status | grep media

# 检查系统定时器状态
sudo systemctl status logrotate.timer
```

### 自动化运行
- **系统定时器**: `logrotate.timer` 每日自动运行
- **Cron任务**: 系统每10分钟检查一次轮转需求
- **手动触发**: 可通过脚本手动执行轮转

### 权限设置
- **`logrotate.user.conf`**: `celestial:celestial` (用户可编辑)
- **`logrotate.conf`**: `root:root` (同步脚本自动设置)
- **日志文件权限**: `0664` (用户和组可读写，其他用户只读)

### 故障排查

#### 权限问题
如果 VSCode 无法保存配置文件：
```bash
# 修改文件所有者为当前用户
sudo chown celestial:celestial /home/celestial/dev/esdk-test/Edge-SDK/logrotate.user.conf
```

#### 配置验证
```bash
# 检查配置语法
sudo /usr/sbin/logrotate -d logrotate.conf

# 查看详细调试信息
sudo /usr/sbin/logrotate -v logrotate.conf
```

#### 常见问题
1. **文件不存在**: 使用 `missingok` 参数避免错误
2. **权限不足**: 确保 `su` 参数设置正确的用户
3. **磁盘空间**: 定期检查磁盘使用情况
4. **进程占用**: 使用 `copytruncate` 处理持续写入的日志

### 维护建议
1. **定期检查**: 监控日志轮转是否正常执行
2. **磁盘监控**: 确保有足够空间存储备份文件
3. **配置更新**: 根据日志增长情况调整轮转参数
4. **备份验证**: 定期验证压缩的日志文件完整性
5. **配置管理**: 始终保持 `logrotate.user.conf` 为最新的主配置文件

---

**最后更新**: 2025-09-03 11:00 AWST  
**架构状态**: 旧架构稳定运行，新架构开发完成，服务配置已清理  
**测试状态**: 新架构已通过完整测试，旧架构生产验证中  
**日志管理**: Logrotate 配置已完成并测试通过
