-- DJI Edge SDK 媒体文件传输状态数据库初始化脚本
-- 创建时间: 2025-01-22
-- 作者: Celestial
-- 描述: 用于跟踪媒体文件从DJI Dock下载到本地，再传输到NAS的完整状态

-- 创建媒体文件传输状态表
CREATE TABLE IF NOT EXISTS media_transfer_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL UNIQUE,           -- 文件完整路径
    file_name TEXT NOT NULL,                  -- 文件名
    file_size INTEGER DEFAULT 0,              -- 文件大小(字节)
    file_hash TEXT DEFAULT '',                -- 文件哈希值(用于完整性验证)
    
    -- 下载状态字段
    download_status TEXT NOT NULL DEFAULT 'pending',  -- pending, downloading, completed, failed
    download_start_time DATETIME,             -- 下载开始时间
    download_end_time DATETIME,               -- 下载完成时间
    download_retry_count INTEGER DEFAULT 0,   -- 下载重试次数
    
    -- 传输状态字段
    transfer_status TEXT NOT NULL DEFAULT 'pending',  -- pending, transferring, completed, failed
    transfer_start_time DATETIME,             -- 传输开始时间
    transfer_end_time DATETIME,               -- 传输完成时间
    transfer_retry_count INTEGER DEFAULT 0,   -- 传输重试次数
    
    -- 错误信息
    last_error_message TEXT DEFAULT '',       -- 最后一次错误信息
    
    -- 时间戳
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引以提高查询性能
CREATE INDEX IF NOT EXISTS idx_file_path ON media_transfer_status(file_path);
CREATE INDEX IF NOT EXISTS idx_download_status ON media_transfer_status(download_status);
CREATE INDEX IF NOT EXISTS idx_transfer_status ON media_transfer_status(transfer_status);
CREATE INDEX IF NOT EXISTS idx_created_at ON media_transfer_status(created_at);
CREATE INDEX IF NOT EXISTS idx_updated_at ON media_transfer_status(updated_at);

-- 创建复合索引用于常见查询
CREATE INDEX IF NOT EXISTS idx_status_combo ON media_transfer_status(download_status, transfer_status);

-- 创建触发器自动更新updated_at字段
CREATE TRIGGER IF NOT EXISTS update_media_transfer_status_updated_at
    AFTER UPDATE ON media_transfer_status
    FOR EACH ROW
BEGIN
    UPDATE media_transfer_status 
    SET updated_at = CURRENT_TIMESTAMP 
    WHERE id = NEW.id;
END;

-- 插入初始化完成标记
INSERT OR IGNORE INTO media_transfer_status 
(file_path, file_name, download_status, transfer_status, last_error_message) 
VALUES 
('__INIT_MARKER__', 'database_initialized', 'completed', 'completed', 'Database initialization completed successfully');

-- 显示表结构信息
.schema media_transfer_status

-- 显示初始化完成信息
SELECT 'Database initialization completed at: ' || datetime('now', 'localtime') as message;
SELECT COUNT(*) as total_records FROM media_transfer_status;