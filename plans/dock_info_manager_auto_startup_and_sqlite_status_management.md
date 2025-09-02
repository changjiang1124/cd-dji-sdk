---
创建时间: 02/09/2025
更新时间: 2025-09-02 13:48:42
功能名称: dock_info_manager开机自启动和SQLite状态管理
状态: 方案确认
优先级: 高
---

# DJI Edge SDK 媒体文件管理系统实施方案

## 概述

本方案旨在解决DJI Edge SDK项目中的两个核心需求：
1. 配置 `dock_info_manager` 程序开机自启动
2. 实现基于SQLite数据库的媒体文件传输状态管理，确保只传输完整下载的媒体文件

## 1. dock_info_manager开机自启动方案

### 1.1 systemd服务配置（推荐）

**服务文件位置：** `/etc/systemd/system/dock-info-manager.service`

```ini
[Unit]
Description=DJI Dock Info Manager Service
Documentation=https://developer.dji.com/doc/edge-sdk-tutorial/
After=network.target network-online.target
Wants=network-online.target
Requires=network.target

[Service]
Type=simple
User=celestial
Group=celestial
WorkingDirectory=/home/celestial/dev/esdk-test/Edge-SDK
ExecStart=/home/celestial/dev/esdk-test/Edge-SDK/build/dock_info_manager
Restart=always
RestartSec=10
KillMode=mixed
KillSignal=SIGTERM
TimeoutStopSec=30

# 环境变量
Environment=LD_LIBRARY_PATH=/home/celestial/dev/esdk-test/Edge-SDK/lib/aarch64
Environment=DJI_LOG_PATH=/home/celestial/dev/esdk-test/Edge-SDK/celestial_works/logs

# 日志配置
StandardOutput=append:/home/celestial/dev/esdk-test/Edge-SDK/celestial_works/logs/dock_manager.log
StandardError=append:/home/celestial/dev/esdk-test/Edge-SDK/celestial_works/logs/dock_manager_error.log

# 安全配置
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=/home/celestial/dev/esdk-test/Edge-SDK/celestial_works
ReadWritePaths=/data/temp/dji

[Install]
WantedBy=multi-user.target
```

**启用命令：**
```bash
sudo systemctl daemon-reload
sudo systemctl enable dock-info-manager.service
sudo systemctl start dock-info-manager.service
```

## 2. 媒体文件状态管理方案

### 2.1 配置文件统一管理

**重要说明：** 本方案严格遵循项目配置统一原则，所有配置信息统一使用现有的 `/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/unified_config.json` 文件，不创建额外的配置文件。

**SSH连接配置：** 使用 `/home/celestial/.ssh/config` 中的 `nas-edge` 主机配置进行NAS连接，确保无密码连接。

### 2.2 SQLite数据库设计（推荐方案）

基于通用性和可读性考虑，采用SQLite数据库来管理媒体文件传输状态：

**数据库文件位置：** `/data/temp/dji/media_status.db`

**数据库表结构：**
```sql
CREATE TABLE media_transfer_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT UNIQUE NOT NULL,           -- 文件完整路径
    file_name TEXT NOT NULL,                  -- 文件名
    file_size INTEGER,                        -- 文件大小（字节）
    file_hash TEXT,                           -- 文件MD5哈希值
    download_status TEXT DEFAULT 'downloading', -- 下载状态：downloading, completed, failed
    download_time DATETIME,                   -- 下载完成时间
    transfer_status TEXT DEFAULT 'pending',  -- 传输状态：pending, transferring, completed, failed
    transfer_time DATETIME,                   -- 传输完成时间
    retry_count INTEGER DEFAULT 0,           -- 重试次数
    error_message TEXT,                       -- 错误信息
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引提高查询性能
CREATE INDEX idx_file_path ON media_transfer_status(file_path);
CREATE INDEX idx_download_status ON media_transfer_status(download_status);
CREATE INDEX idx_transfer_status ON media_transfer_status(transfer_status);
```

### 2.2 状态流转机制

1. **下载阶段** (dock_info_manager):
   - `downloading` → `completed` (成功)
   - `downloading` → `failed` (失败)

2. **传输阶段** (NAS同步系统):
   - `pending` → `transferring` → `completed` (成功)
   - `pending` → `transferring` → `failed` (失败，可重试)

### 2.3 代码实现要点

**dock_info_manager.cc 修改：**
```cpp
#include <sqlite3.h>
#include <openssl/md5.h>

class MediaStatusDB {
public:
    bool InsertDownloadRecord(const std::string& filepath, const std::string& filename, int64_t filesize);
    bool UpdateDownloadStatus(const std::string& filepath, const std::string& status, const std::string& hash = "");
};

void SaveMediaFileToDirectory(const std::string& filename, const std::vector<uint8_t>& data) {
    std::string filepath = "/data/temp/dji/media/" + filename;
    
    // 1. 在数据库中插入下载记录
    MediaStatusDB db;
    db.InsertDownloadRecord(filepath, filename, data.size());
    
    // 2. 保存文件
    FILE* f = fopen(filepath.c_str(), "wb");
    if (f) {
        fwrite(data.data(), data.size(), 1, f);
        fclose(f);
        
        // 3. 计算文件哈希并更新状态
        std::string hash = CalculateMD5(filepath);
        db.UpdateDownloadStatus(filepath, "completed", hash);
    } else {
        db.UpdateDownloadStatus(filepath, "failed");
    }
}
```

**media_sync.py 修改：**
```python
import sqlite3
from typing import List, Dict

class MediaStatusDB:
    def __init__(self, db_path: str = "/data/temp/dji/media_status.db"):
        self.db_path = db_path
        self.init_database()
    
    def get_ready_files(self) -> List[Dict]:
        """获取已就绪待传输的媒体文件列表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT file_path, file_name, file_size, file_hash 
            FROM media_transfer_status 
            WHERE download_status = 'completed' 
            AND transfer_status = 'pending'
            ORDER BY created_at ASC
        """)
        
        files = [{
            'file_path': row[0],
            'file_name': row[1], 
            'file_size': row[2],
            'file_hash': row[3]
        } for row in cursor.fetchall()]
        
        conn.close()
        return files
    
    def update_transfer_status(self, file_path: str, status: str, error_msg: str = None):
        """更新传输状态"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if status == 'completed':
            cursor.execute("""
                UPDATE media_transfer_status 
                SET transfer_status = ?, transfer_time = CURRENT_TIMESTAMP
                WHERE file_path = ?
            """, (status, file_path))
        else:
            cursor.execute("""
                UPDATE media_transfer_status 
                SET transfer_status = ?, error_message = ?, retry_count = retry_count + 1
                WHERE file_path = ?
            """, (status, error_msg, file_path))
        
        conn.commit()
        conn.close()
```

## 3. 实施步骤

### 第一阶段：基础配置（1-2天）
1. 创建systemd服务文件
2. 设计和创建SQLite数据库表结构
3. 实现数据库连接和基础操作类
4. 配置日志轮转
5. 启用dock_info_manager自启动
6. 测试服务启动和重启

### 第二阶段：状态管理实施（3-4天）
1. 修改dock_info_manager代码（集成SQLite数据库操作）
2. 实现文件下载状态记录和MD5哈希计算
3. 修改NAS传输系统代码（基于数据库状态查询）
4. 实现传输状态更新和失败重试机制
5. 创建数据库维护和查询工具
6. 重新编译和部署
7. 测试完整流程和并发访问

### 第三阶段：监控优化（1-2天）
1. 部署健康检查脚本（包含数据库状态检查）
2. 实现传输统计和报告功能
3. 配置cron任务和告警机制
4. 优化数据库查询性能
5. 测试异常情况处理
6. 性能调优和连接池优化

## 4. 技术优势

### 4.1 可靠性
- systemd提供的自动重启和监控机制
- SQLite的ACID事务保证数据一致性
- 完善的错误处理和重试机制

### 4.2 可维护性
- 数据库结构清晰，便于理解和维护
- 支持SQL查询进行状态检查和统计
- 提供丰富的监控和报告能力

### 4.3 可扩展性
- 数据库结构易于扩展新字段
- 支持复杂查询和数据分析
- 为未来功能增强预留接口

### 4.4 向后兼容
- 保持现有API和接口不变
- 兼容现有的日志和监控系统
- 不破坏现有的文件组织结构

## 5. 风险评估

### 5.1 主要风险
1. **数据库文件损坏**：定期备份，实现自动修复机制
2. **并发访问冲突**：使用SQLite的WAL模式，实现连接池
3. **磁盘空间不足**：实现数据清理和归档机制
4. **服务启动失败**：完善依赖检查和错误处理

### 5.2 缓解措施
- 实现数据库健康检查和自动修复
- 设置合理的超时和重试策略
- 监控磁盘使用情况，自动清理过期数据
- 提供手动干预和状态重置工具

## 6. 监控和维护

### 6.1 关键指标
- 服务运行状态和重启次数
- 媒体文件下载成功率
- NAS传输成功率和延迟
- 数据库大小和查询性能
- 错误日志和异常统计

### 6.2 维护工具
- 数据库状态查询脚本
- 传输统计报告工具
- 数据清理和归档脚本
- 健康检查和告警脚本

## 7. 需求完成后的预期结果

### 7.1 系统运行状态
1. **自启动服务**：`dock_info_manager` 作为systemd服务在系统启动时自动运行
2. **状态管理**：SQLite数据库实时跟踪所有媒体文件的下载和传输状态
3. **配置统一**：所有配置信息集中在 `unified_config.json` 中管理
4. **无缝传输**：只有完全下载完成的媒体文件才会被传输到NAS

### 7.2 功能验收标准
1. **服务自启动验证**：
   - 系统重启后 `dock_info_manager` 服务自动启动
   - 服务异常退出后自动重启（10秒内）
   - 服务状态可通过 `systemctl status dock-info-manager` 查看

2. **状态管理验证**：
   - 媒体文件下载过程中状态为 `downloading`
   - 下载完成后状态更新为 `completed` 并计算MD5哈希
   - 只有状态为 `completed` 的文件才会被NAS传输系统处理
   - 传输过程中状态流转：`pending` → `transferring` → `completed`

3. **数据一致性验证**：
   - 数据库记录与实际文件状态保持一致
   - 支持并发访问不出现数据冲突
   - 异常情况下数据库状态可恢复

4. **配置管理验证**：
   - 所有配置参数从 `unified_config.json` 读取
   - SSH连接使用 `nas-edge` 配置实现无密码连接
   - 不存在重复或冗余的配置文件

### 7.3 交付成果
1. **代码修改**：
   - 修改后的 `dock_info_manager.cc`（集成SQLite状态管理）
   - 修改后的 `media_sync.py`（基于数据库状态查询）
   - 新增的数据库操作类和工具脚本

2. **配置文件**：
   - systemd服务配置文件 `/etc/systemd/system/dock-info-manager.service`
   - 更新的 `unified_config.json`（如需添加新配置项）

3. **数据库**：
   - SQLite数据库文件 `/data/temp/dji/media_status.db`
   - 数据库初始化和维护脚本

4. **监控工具**：
   - 服务健康检查脚本
   - 数据库状态查询工具
   - 传输统计报告工具

### 7.4 运维能力
1. **监控能力**：实时监控服务状态、传输进度和错误情况
2. **故障恢复**：自动重启机制和手动干预工具
3. **数据维护**：定期清理过期数据和数据库优化
4. **性能分析**：传输统计和性能报告

## 总结

本方案采用systemd服务管理dock_info_manager的自启动，使用SQLite数据库进行精细化状态管理，严格遵循配置文件统一原则，协调两个阶段的文件传输，确保数据一致性和可追溯性。该方案具有高可靠性、易维护性和良好的扩展性，推荐作为主要实施方案。