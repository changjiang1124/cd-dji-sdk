---
**Meta信息**
- 创建时间: 2025-01-22
- 更新时间: 2025-01-22
- 功能名称: smoke_transfer_check 烟雾测试脚本增强
- 负责人: Celestial
---

# smoke_transfer_check 烟雾测试脚本增强计划

## 当前状态分析

### 现有功能回顾

当前的 `smoke_transfer_check.py` 脚本具备以下功能：

1. **文件创建**: 在本地媒体目录 `/data/temp/dji/media/` 创建测试文件
2. **远程检查**: 通过SSH检查文件是否传输到NAS的目标路径
3. **本地清理检查**: 验证本地文件是否在传输后被删除
4. **配置驱动**: 使用统一配置文件 `unified_config.json`

### 目标路径确认

根据配置文件分析：
- **NAS基础路径**: `/volume1/homes/edge_sync/drone_media`
- **备份子路径**: `EdgeBackup`
- **完整目标路径**: `/volume1/homes/edge_sync/drone_media/EdgeBackup/YYYY/MM/DD/`

**回答用户问题**: 是的，程序当前使用的是 `~/drone_media/EdgeBackup` 作为目标文件夹，这与配置一致，无需更改。

### 关键问题识别

**核心问题**: 当前脚本存在重大缺陷 - 仅在文件系统中创建文件，但**未在数据库中创建相应记录**。

根据系统架构分析：
- `media-sync-daemon` 通过查询数据库 `media_transfer_status` 表来获取待传输文件
- 查询条件: `download_status = 'completed' AND transfer_status = 'pending'`
- 如果文件不在数据库中，daemon将完全忽略该文件

## 增强方案设计

### 方案概述

增强 `smoke_transfer_check.py` 脚本，使其能够：
1. 创建测试文件到本地媒体目录
2. **在数据库中插入相应的文件记录**（关键增强）
3. 等待并验证daemon的完整工作流程
4. 提供更详细的测试报告和诊断信息

### 技术实现方案

#### 1. 数据库集成

**新增功能**:
- 导入 `media_status_db.py` 模块
- 在创建测试文件后，向数据库插入记录
- 设置正确的初始状态：`download_status='completed'`, `transfer_status='pending'`

**实现细节**:
```python
# 伪代码示例
from celestial_nasops.media_status_db import MediaStatusDB

def insert_test_file_record(db: MediaStatusDB, file_path: str, file_size: int):
    """向数据库插入测试文件记录"""
    # 需要添加insert_file_record方法到MediaStatusDB类
    db.insert_file_record(
        file_path=file_path,
        file_name=os.path.basename(file_path),
        file_size=file_size,
        download_status='completed',  # 模拟已下载完成
        transfer_status='pending'     # 等待传输
    )
```

#### 2. 数据库操作类扩展

**需要在 `MediaStatusDB` 类中添加的方法**:

```python
def insert_file_record(self, file_path: str, file_name: str, file_size: int, 
                       file_hash: str = "", download_status: str = "pending", 
                       transfer_status: str = "pending") -> bool:
    """插入新的文件记录到数据库"""
    # 实现插入逻辑
    pass
```

#### 3. 测试流程优化

**增强的测试步骤**:
1. 生成测试文件名（带时间戳）
2. 创建本地测试文件
3. 计算文件哈希值（可选，用于完整性验证）
4. **向数据库插入文件记录**
5. 等待daemon处理（轮询检查）
6. 验证远程文件存在
7. 验证本地文件删除（如果配置启用）
8. 生成详细测试报告

#### 4. 诊断和报告增强

**新增诊断功能**:
- 数据库连接状态检查
- Daemon服务状态检查（通过systemctl）
- 网络连接测试（ping NAS）
- 详细的时间线报告
- 失败原因分析

### 配置文件更新

**需要在 `unified_config.json` 中添加**:
```json
{
  "database_settings": {
    "db_path": "/data/temp/dji/media_status.db",
    "connection_timeout": 30,
    "description": "数据库连接配置"
  },
  "testing": {
    "smoke_test_prefix": "smoketest",
    "test_file_size_bytes": 1024,
    "max_wait_minutes": 15,
    "poll_interval_seconds": 30,
    "description": "烟雾测试配置"
  }
}
```

## 测试用例设计

### 基础功能测试

1. **正常流程测试**
   - 创建测试文件和数据库记录
   - 验证daemon在配置的时间间隔内处理文件
   - 确认文件成功传输到NAS
   - 验证本地文件按配置删除

2. **数据库集成测试**
   - 验证数据库记录正确插入
   - 确认状态更新正确（pending → transferring → completed）
   - 测试数据库连接异常处理

3. **网络异常测试**
   - 模拟NAS不可达情况
   - 验证重试机制
   - 测试超时处理

### 边界条件测试

1. **并发测试**
   - 多个测试文件同时处理
   - 验证文件锁机制

2. **存储空间测试**
   - 本地存储空间不足
   - NAS存储空间不足

3. **权限测试**
   - 数据库文件权限问题
   - SSH连接权限问题

### 性能测试

1. **大文件测试**
   - 测试不同大小的文件传输
   - 验证传输超时设置

2. **批量文件测试**
   - 同时处理多个文件
   - 验证系统负载

## 验收标准

### 功能验收

- [ ] 脚本能够正确创建测试文件和数据库记录
- [ ] Daemon能够检测并处理测试文件
- [ ] 文件成功传输到NAS的正确路径
- [ ] 本地文件按配置策略删除
- [ ] 数据库状态正确更新

### 性能验收

- [ ] 测试完成时间不超过配置的最大等待时间
- [ ] 数据库操作响应时间 < 1秒
- [ ] 网络检查响应时间 < 5秒

### 可靠性验收

- [ ] 异常情况下脚本能够优雅退出
- [ ] 提供清晰的错误信息和诊断建议
- [ ] 不会留下垃圾文件或数据库记录

## 实施计划

### 第一阶段：数据库集成（优先级：高）

1. 在 `MediaStatusDB` 类中添加 `insert_file_record` 方法
2. 修改 `smoke_transfer_check.py` 集成数据库操作
3. 基础功能测试

### 第二阶段：功能增强（优先级：中）

1. 添加系统状态检查功能
2. 增强错误诊断和报告
3. 优化用户界面和输出格式

### 第三阶段：测试完善（优先级：中）

1. 添加边界条件测试
2. 性能测试和优化
3. 文档更新

## 风险评估

### 技术风险

1. **数据库并发访问**
   - 风险：测试脚本与daemon同时访问数据库可能导致锁定
   - 缓解：使用适当的事务和超时设置

2. **测试文件清理**
   - 风险：测试失败时可能留下垃圾文件
   - 缓解：实现清理机制和异常处理

### 运维风险

1. **生产环境影响**
   - 风险：测试可能影响正常的媒体文件处理
   - 缓解：使用明确的测试文件标识，避免与真实文件冲突

## 守护进程重启要求

### 为什么需要重启

在实施本增强计划后，**必须重启媒体同步守护进程**，原因如下：

1. **数据库连接更新**
   - `MediaStatusDB` 类新增 `insert_file_record` 方法
   - 守护进程需要重新加载更新后的代码

2. **配置文件变更**
   - `unified_config.json` 可能新增数据库和测试相关配置
   - 守护进程启动时加载配置，需要重启生效

3. **代码模块更新**
   - Python进程需要重启才能加载新的模块和方法

### 重启步骤

```bash
# 1. 停止守护进程
sudo systemctl stop media-sync-daemon

# 2. 验证服务已停止
sudo systemctl status media-sync-daemon

# 3. 启动守护进程
sudo systemctl start media-sync-daemon

# 4. 检查服务状态
sudo systemctl status media-sync-daemon

# 5. 监控启动日志
journalctl -u media-sync-daemon -f --since "1 minute ago"
```

### 当前发现的问题

**错误信息分析**：
```
ERROR - 保存待删除任务失败: [Errno 30] Read-only file system
```

**问题原因**：
- 守护进程尝试写入 `/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/pending_deletes.json`
- 出现只读文件系统错误（临时性问题）

**解决方案**：
1. **立即修复**：重启守护进程通常可以解决临时的文件系统问题
2. **预防措施**：在 `SafeDeleteManager` 中添加更好的错误处理和重试机制
3. **监控改进**：增加文件系统状态检查

**修复验证**：
- 目录权限正常：`drwxrwxr-x celestial celestial`
- 文件系统可写：测试创建文件成功
- 问题可能是守护进程运行时的临时状态

### 重启后验证清单

- [ ] 守护进程成功启动
- [ ] 日志中无错误信息
- [ ] 数据库连接正常
- [ ] 配置文件加载成功
- [ ] 运行增强的烟雾测试验证功能
- [ ] 检查 `pending_deletes.json` 文件创建和写入正常

## 总结

当前的 `smoke_transfer_check.py` 脚本虽然能够验证文件系统层面的操作，但**缺少关键的数据库集成**，导致无法真正测试daemon的完整工作流程。

通过本增强计划，我们将：
1. 修复核心缺陷，确保测试文件能被daemon正确处理
2. 提供更全面的系统健康检查
3. 建立完整的测试验收标准
4. 为系统维护提供可靠的验证工具
5. **解决当前发现的文件系统写入问题**

**重要提醒**：实施增强计划后必须重启守护进程，并验证所有功能正常工作。

这个增强后的烟雾测试脚本将成为验证整个媒体同步系统正常工作的重要工具。