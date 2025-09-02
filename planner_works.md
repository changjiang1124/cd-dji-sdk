# DJI Edge SDK 媒体文件管理系统实施方案

## 项目概述

本方案旨在实现DJI Edge SDK媒体文件的完整管理流程：
1. **第一阶段**：dock_info_manager程序从DJI Dock获取媒体文件并保存到本地
2. **第二阶段**：NAS传输系统将本地媒体文件同步到NAS存储
3. **状态管理**：确保两个阶段之间的协调，避免传输未完成的文件

## 当前系统分析

### dock_info_manager程序功能
- **位置**：`/home/celestial/dev/esdk-test/Edge-SDK/build/bin/dock_info_manager`
- **功能**：
  - 初始化DJI Edge SDK
  - 获取机场设备信息
  - 设置媒体文件策略（上传云端后保留本地数据）
  - 监控媒体文件更新通知
  - 自动下载媒体文件到 `/data/temp/dji/media/` 目录
  - 每5秒检查一次媒体文件并记录日志

### NAS传输系统现状
- **位置**：`/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/`
- **功能**：
  - 监控本地媒体目录 `/data/temp/dji/media/`
  - 按日期结构同步到NAS `edge_sync@192.168.200.103:EdgeBackup/`
  - 支持校验和验证、重试机制、安全删除
  - 已配置为systemd守护进程

## 实施方案

### 1. dock_info_manager开机自启动配置

#### 方案选择：systemd服务（推荐）

**优势**：
- 系统级管理，开机自动启动
- 自动重启机制，提高可靠性
- 标准化的日志管理
- 易于监控和控制

**实施步骤**：

1. **创建systemd服务文件**：`/etc/systemd/system/dji-dock-manager.service`
```ini
[Unit]
Description=DJI Dock Info Manager Service
Documentation=https://developer.dji.com/doc/edge-sdk-tutorial/
After=network.target
Wants=network.target

[Service]
Type=simple
User=celestial
Group=celestial
WorkingDirectory=/home/celestial/dev/esdk-test/Edge-SDK
ExecStart=/home/celestial/dev/esdk-test/Edge-SDK/build/bin/dock_info_manager
Restart=always
RestartSec=10
KillMode=mixed
KillSignal=SIGTERM
TimeoutStopSec=30

# 环境变量
Environment=HOME=/home/celestial
Environment=USER=celestial

# 日志配置
StandardOutput=append:/home/celestial/dev/esdk-test/Edge-SDK/celestial_works/logs/dock_manager.log
StandardError=append:/home/celestial/dev/esdk-test/Edge-SDK/celestial_works/logs/dock_manager_error.log

# 安全配置
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

2. **启用服务**：
```bash
sudo systemctl daemon-reload
sudo systemctl enable dji-dock-manager.service
sudo systemctl start dji-dock-manager.service
```

3. **服务管理命令**：
```bash
# 查看状态
sudo systemctl status dji-dock-manager.service

# 查看日志
journalctl -u dji-dock-manager.service -f

# 重启服务
sudo systemctl restart dji-dock-manager.service

# 停止服务
sudo systemctl stop dji-dock-manager.service
```

### 2. 媒体文件状态管理方案

#### 问题分析
当前系统存在潜在的竞态条件：
- dock_info_manager正在下载文件时，NAS传输系统可能尝试传输未完成的文件
- 需要确保只传输完整下载的文件

#### 解决方案：SQLite数据库状态管理（推荐）

**方案特点**：
- 状态管理更加精细和可控
- 支持复杂查询和统计分析
- 易于扩展和维护
- 提供完整的传输历史记录
- 支持并发访问和事务处理
- 便于监控和故障排查

**数据库设计**：

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

**实施机制**：

1. **dock_info_manager修改**：
   - 开始下载时在数据库中插入记录，状态为 'downloading'
   - 下载完成后更新状态为 'completed'，记录下载时间和文件哈希
   - 下载失败时更新状态为 'failed'，记录错误信息

2. **NAS传输系统修改**：
   - 查询数据库中 download_status='completed' 且 transfer_status='pending' 的文件
   - 传输前更新状态为 'transferring'
   - 传输成功后更新状态为 'completed'，删除本地文件
   - 传输失败时更新状态为 'failed'，增加重试计数

**代码修改点**：

```cpp
// dock_info_manager.cc 中的 SaveMediaFileToDirectory 函数
#include <sqlite3.h>
#include <openssl/md5.h>

class MediaStatusDB {
public:
    bool InsertDownloadRecord(const std::string& filepath, const std::string& filename, int64_t filesize);
    bool UpdateDownloadStatus(const std::string& filepath, const std::string& status, const std::string& hash = "");
    bool UpdateTransferStatus(const std::string& filepath, const std::string& status);
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
        
        // 3. 计算文件哈希
        std::string hash = CalculateMD5(filepath);
        
        // 4. 更新数据库状态为已完成
        db.UpdateDownloadStatus(filepath, "completed", hash);
        INFO("媒体文件已保存: %s", filepath.c_str());
    } else {
        // 5. 更新数据库状态为失败
        db.UpdateDownloadStatus(filepath, "failed");
        ERROR("保存媒体文件失败: %s", filepath.c_str());
    }
}
```

```python
# media_sync.py 中的数据库查询逻辑
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

def sync_file(self, file_info: Dict) -> bool:
    """同步单个文件"""
    file_path = file_info['file_path']
    
    # 检查文件是否存在
    if not os.path.exists(file_path):
        self.db.update_transfer_status(file_path, "failed", "本地文件不存在")
        return False
    
    # 更新状态为传输中
    self.db.update_transfer_status(file_path, "transferring")
    
    # 执行同步
    try:
        success = self._do_sync(file_path)
        if success:
            # 同步成功后删除本地文件并更新数据库
            os.remove(file_path)
            self.db.update_transfer_status(file_path, "completed")
            return True
        else:
            self.db.update_transfer_status(file_path, "failed", "传输失败")
            return False
    except Exception as e:
        self.db.update_transfer_status(file_path, "failed", str(e))
        return False
```

#### 备选方案：基于文件系统的状态标记

**适用场景**：
- 系统规模较小，文件数量不多
- 追求最简实现
- 不需要详细的历史记录和统计

**实现原理**：
- 在媒体文件下载完成后，创建对应的 `.ready` 标记文件
- NAS传输系统只处理有 `.ready` 标记的媒体文件
- 传输完成后删除 `.ready` 文件，避免重复传输

**优势**：
- 实现简单，无需额外依赖
- 原子性操作，避免并发问题
- 与现有系统兼容性好

**文件结构示例**：
```
/data/temp/dji/media/
├── 20240115_flight_001.mp4
├── 20240115_flight_001.mp4.ready    # 标记文件已准备好传输
├── 20240115_flight_002.jpg
└── 20240115_flight_002.jpg.ready
```

### 3. 系统集成和监控

#### 日志轮转配置
更新现有的 `logrotate.conf`，添加dock_info_manager日志：

```
/home/celestial/dev/esdk-test/Edge-SDK/celestial_works/logs/dock_manager.log {
    size 50M
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
    create 0644 celestial celestial
}

/home/celestial/dev/esdk-test/Edge-SDK/celestial_works/logs/dock_manager_error.log {
    size 20M
    rotate 5
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
    create 0644 celestial celestial
}
```

#### 监控脚本
创建系统健康检查脚本：

```bash
#!/bin/bash
# /home/celestial/dev/esdk-test/Edge-SDK/celestial_works/scripts/health_check.sh

# 检查dock_info_manager服务状态
if ! systemctl is-active --quiet dji-dock-manager.service; then
    echo "[ERROR] dock_info_manager服务未运行"
    exit 1
fi

# 检查NAS传输服务状态
if ! systemctl is-active --quiet media-sync-daemon.service; then
    echo "[ERROR] NAS传输服务未运行"
    exit 1
fi

# 检查磁盘空间
USAGE=$(df /data/temp/dji/media/ | awk 'NR==2 {print $5}' | sed 's/%//')
if [ $USAGE -gt 80 ]; then
    echo "[WARNING] 媒体目录磁盘使用率过高: ${USAGE}%"
fi

echo "[OK] 系统运行正常"
```

## 实施时间表

### 第一阶段：基础配置（1-2天）
1. 创建systemd服务文件
2. 设计和创建SQLite数据库表结构
3. 实现数据库连接和基础操作类
4. 配置日志轮转
5. 启用dock_info_manager自启动
6. 测试服务启动和重启

### 第二阶段：状态管理实现（3-4天）
1. 修改dock_info_manager代码（集成SQLite数据库操作）
2. 实现文件下载状态记录和MD5哈希计算
3. 修改NAS传输系统代码（基于数据库状态查询）
4. 实现传输状态更新和失败重试机制
5. 创建数据库维护和查询工具
6. 重新编译和部署
7. 测试完整流程和并发访问

### 第三阶段：监控和优化（1-2天）
1. 部署健康检查脚本（包含数据库状态检查）
2. 实现传输统计和报告功能
3. 配置cron任务和告警机制
4. 优化数据库查询性能
5. 测试异常情况处理
6. 性能调优和连接池优化

## 风险评估和缓解措施

### 风险1：服务启动失败
**缓解措施**：
- 详细的错误日志记录
- 自动重启机制
- 健康检查脚本监控

### 风险2：文件传输中断
**缓解措施**：
- 原子性文件操作
- 重试机制
- 校验和验证

### 风险3：磁盘空间不足
**缓解措施**：
- 磁盘使用率监控
- 及时清理已同步文件
- 告警机制

### 风险4：网络连接问题
**缓解措施**：
- NAS连接重试机制
- 离线模式支持
- 网络恢复后自动同步

## 总结

本方案采用systemd服务管理dock_info_manager的自启动，使用SQLite数据库进行精细化状态管理，协调两个阶段的文件传输，确保数据一致性和可追溯性。该方案具有以下优势：

1. **可靠性**：systemd提供的自动重启和监控机制，SQLite的ACID事务保证
2. **精确性**：数据库级别的状态管理，支持复杂查询和统计
3. **原子性**：利用数据库事务保证操作的原子性和一致性
4. **可维护性**：标准化的服务管理、详细的状态记录和日志
5. **可扩展性**：数据库结构易于扩展，支持未来功能增强
6. **可监控性**：提供丰富的状态查询和报告功能
7. **容错性**：完善的错误处理、重试机制和故障恢复

推荐采用SQLite数据库状态管理方案作为主要实施方案，为系统提供更强的可靠性和可维护性。