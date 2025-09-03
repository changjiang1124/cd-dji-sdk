

# 统一同步架构优化方案

## 背景

当前系统存在多个组件同时访问数据库的并发冲突问题：
- `dock_info_manager` (C++): 每15秒检查并记录媒体文件状态
- `sync_scheduler` (Python): 每10分钟批量同步文件到NAS，频繁更新传输状态
- `smoke_transfer_check` (Python): 诊断工具，偶尔访问数据库

## 优化方案概述

### 核心思路
1. **Dock -> Edge**: 仅使用日志记录，直接将文件保存到指定目录
2. **Edge -> NAS**: 直接监控文件夹发现新文件，通过数据库管理传输状态

### 架构变更
```
当前架构:
Dock -> Edge (dock_info_manager写DB) -> NAS (sync_scheduler读写DB)

新架构:
Dock -> Edge (dock_info_manager仅写日志+文件) -> NAS (sync_scheduler监控文件夹+独占DB)

关键变化:
- dock_info_manager: 不再写数据库，只写日志和文件
- sync_scheduler: 文件夹监控 + 独占数据库操作
- 彻底消除数据库并发访问冲突
```

## Edge -> NAS 数据库操作流程

### 日志记录要求

新的daemon程序需要详细记录所有操作到日志文件中，便于后续问题排查和历史追踪：

```python
# 日志配置
LOG_FILE_PATH = "/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/logs/media_finding.log"

# 需要记录的关键操作：
# 1. 文件发现操作 - 扫描后，是否发现新文件、跳过的文件 
# 2. 数据库操作 - 插入、更新、查询操作及结果
# 3. 文件处理 - 哈希计算、传输状态变更
# 4. 错误处理 - 异常情况和错误恢复
# 5. 性能统计 - 处理时间、文件大小、传输速度

def setup_logging():
    """配置详细的操作日志记录"""
    import logging
    from logging.handlers import RotatingFileHandler
    
    # 创建logger
    logger = logging.getLogger('media_finding')
    logger.setLevel(logging.INFO)
    
    # 创建文件处理器，支持日志轮转
    file_handler = RotatingFileHandler(
        LOG_FILE_PATH,
        maxBytes=50*1024*1024,  # 50MB
        backupCount=5
    )
    
    # 设置详细的日志格式
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger
```

### 核心流程设计

#### 阶段A: 文件发现和数据库检查
```python
def discover_and_register_files(self):
    """发现新文件并注册到数据库"""
    start_time = time.time()
    
    # 1. 扫描文件夹发现新文件
    self.logger.info("开始扫描媒体文件目录")
    new_files = self._scan_media_directory()
    self.logger.info(f"扫描完成，发现 {len(new_files)} 个文件")
    
    processed_count = 0
    skipped_count = 0
    registered_count = 0
    
    for file_path in new_files:
        try:
            processed_count += 1
            filename = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            
            self.logger.info(f"处理文件 [{processed_count}/{len(new_files)}]: {filename} ({file_size} bytes)")
            
            # 2. 计算文件哈希（用于去重）
            hash_start = time.time()
            file_hash = self._calculate_file_hash(file_path)
            hash_duration = time.time() - hash_start
            self.logger.info(f"文件哈希计算完成: {filename}, 哈希: {file_hash[:16]}..., 耗时: {hash_duration:.2f}秒")
            
            # 3. 检查数据库中是否已存在（通过文件名+哈希）
            existing_record = self.db.get_file_by_name_and_hash(filename, file_hash)
            
            if existing_record:
                skipped_count += 1
                self.logger.info(f"文件已存在数据库，跳过: {filename} (ID: {existing_record.get('id', 'N/A')})")
                continue
            
            # 4. 文件不存在，添加新记录并标记为 pending
            record_id = self.db.insert_media_file(
                file_path=file_path,
                filename=filename,
                file_hash=file_hash,
                status=FileStatus.PENDING,
                file_size=file_size
            )
            registered_count += 1
            self.logger.info(f"新文件已注册到数据库: {filename}, ID: {record_id}, 状态: PENDING")
            
        except Exception as e:
            self.logger.error(f"处理文件失败: {filename}, 错误: {str(e)}")
    
    total_duration = time.time() - start_time
    self.logger.info(f"文件发现和注册完成 - 总计: {processed_count}, 新注册: {registered_count}, 跳过: {skipped_count}, 总耗时: {total_duration:.2f}秒")
```

#### 阶段B: 处理待传输文件
```python
def process_pending_files(self):
    """处理数据库中 pending 状态的文件"""
    start_time = time.time()
    
    # 1. 查询所有 pending 状态的文件
    self.logger.info("开始查询待传输文件")
    pending_files = self.db.get_files_by_status(FileStatus.PENDING)
    self.logger.info(f"查询到 {len(pending_files)} 个待传输文件")
    
    if not pending_files:
        self.logger.info("没有待传输文件，跳过处理")
        return
    
    success_count = 0
    failed_count = 0
    
    for index, file_record in enumerate(pending_files, 1):
        file_id = file_record['id']
        filename = file_record['filename']
        file_size = file_record.get('file_size', 0)
        
        try:
            self.logger.info(f"开始处理文件 [{index}/{len(pending_files)}]: {filename} (ID: {file_id}, 大小: {file_size} bytes)")
            
            # 2. 开始传输前，更新状态为 transferring
            transfer_start = datetime.now()
            self.db.update_transfer_status(
                file_id, 
                FileStatus.TRANSFERRING,
                start_time=transfer_start
            )
            self.logger.info(f"文件状态已更新为 TRANSFERRING: {filename} (ID: {file_id})")
            
            # 3. 执行文件传输
            transfer_start_time = time.time()
            success = self._transfer_file_to_nas(file_record)
            transfer_duration = time.time() - transfer_start_time
            
            # 4. 根据传输结果更新状态
            transfer_end = datetime.now()
            
            if success:
                success_count += 1
                transfer_speed = file_size / transfer_duration if transfer_duration > 0 else 0
                self.db.update_transfer_status(
                    file_id,
                    FileStatus.TRANSFERRED,
                    end_time=transfer_end
                )
                self.logger.info(f"文件传输成功: {filename} (ID: {file_id}), 耗时: {transfer_duration:.2f}秒, 速度: {transfer_speed/1024/1024:.2f} MB/s")
            else:
                failed_count += 1
                self.db.update_transfer_status(
                    file_id,
                    FileStatus.FAILED,
                    end_time=transfer_end,
                    error_message="传输失败"
                )
                self.logger.error(f"文件传输失败: {filename} (ID: {file_id}), 耗时: {transfer_duration:.2f}秒")
                
        except Exception as e:
            failed_count += 1
            error_msg = str(e)
            self.db.update_transfer_status(
                file_id,
                FileStatus.FAILED,
                error_message=error_msg
            )
            self.logger.error(f"文件处理异常: {filename} (ID: {file_id}), 错误: {error_msg}")
    
    total_duration = time.time() - start_time
    self.logger.info(f"待传输文件处理完成 - 成功: {success_count}, 失败: {failed_count}, 总耗时: {total_duration:.2f}秒")
```

### 大文件哈希优化策略

#### 大文件哈希计算优化
```python
def _calculate_file_hash(self, file_path: str) -> str:
    """计算文件哈希值，针对大文件优化
    
    对于大文件（>1GB），使用采样哈希策略：
    - 文件头部 1MB + 文件中部 1MB + 文件尾部 1MB
    - 文件大小和修改时间
    """
    file_size = os.path.getsize(file_path)
    
    # 小文件直接计算完整哈希
    if file_size < 100 * 1024 * 1024:  # 100MB
        return self._calculate_full_hash(file_path)
    
    # 大文件使用采样哈希
    return self._calculate_sampled_hash(file_path, file_size)

def _calculate_sampled_hash(self, file_path: str, file_size: int) -> str:
    """大文件采样哈希计算 - 30GB文件约耗时1-2秒"""
    import hashlib
    
    hasher = hashlib.sha256()
    sample_size = 1024 * 1024  # 1MB
    
    with open(file_path, 'rb') as f:
        # 文件头部 1MB
        hasher.update(f.read(sample_size))
        
        # 文件中部 1MB
        if file_size > 2 * sample_size:
            f.seek(file_size // 2 - sample_size // 2)
            hasher.update(f.read(sample_size))
        
        # 文件尾部 1MB
        if file_size > sample_size:
            f.seek(-sample_size, 2)
            hasher.update(f.read(sample_size))
    
    # 添加文件元信息
    stat = os.stat(file_path)
    hasher.update(str(file_size).encode())
    hasher.update(str(int(stat.st_mtime)).encode())
    
    return hasher.hexdigest()
```

### 传输模式分析：线性 vs 异步

#### 线性传输模式（推荐）

**优势：**
1. **避免数据库并发冲突**: 单线程处理，无锁竞争
2. **带宽管理**: 避免多文件同时传输抢占带宽
3. **错误处理简单**: 单一传输流程，易于调试
4. **资源控制**: 内存和网络资源使用可控
5. **状态一致性**: 传输状态变更顺序可控

**异步传输的问题：**
1. **并发冲突**: 多线程访问数据库需要复杂的锁机制
2. **带宽抢占**: 多文件同时传输影响单个文件传输速度
3. **状态管理复杂**: 需要处理各种并发状态变更
4. **错误恢复困难**: 多个传输任务的错误处理复杂

**推荐实现：**
```python
def optimized_linear_transfer(self):
    """优化的线性传输策略"""
    # 1. 快速发现阶段（高频率）
    self.discover_and_register_files()
    
    # 2. 批量传输阶段（按优先级）
    pending_files = self.db.get_files_by_status(FileStatus.PENDING)
    
    # 按文件大小排序：小文件优先
    pending_files.sort(key=lambda x: x['file_size'])
    
    for file_record in pending_files:
        # 传输前再次检查文件状态（避免重复处理）
        current_status = self.db.get_file_status(file_record['id'])
        if current_status != FileStatus.PENDING:
            continue
            
        self._transfer_single_file(file_record)
```

## 关键技术实现

### 1. dock_info_manager 原子文件写入

```cpp
bool SaveMediaFileToDirectory(const std::string& file_data, 
                             const std::string& file_name,
                             const std::string& directory_path) {
    // 1. 生成临时文件名
    std::string temp_filename = ".tmp_" + file_name;
    std::string temp_file_path = directory_path + "/" + temp_filename;
    std::string final_file_path = directory_path + "/" + file_name;
    
    // 2. 写入临时文件
    std::ofstream temp_file(temp_file_path, std::ios::binary);
    if (!temp_file.is_open()) {
        ERROR("无法创建临时文件: %s", temp_file_path.c_str());
        return false;
    }
    
    temp_file.write(file_data.c_str(), file_data.size());
    temp_file.close();
    
    if (temp_file.fail()) {
        ERROR("写入临时文件失败: %s", temp_file_path.c_str());
        std::remove(temp_file_path.c_str());
        return false;
    }
    
    // 3. 原子重命名
    if (std::rename(temp_file_path.c_str(), final_file_path.c_str()) != 0) {
        ERROR("文件重命名失败");
        std::remove(temp_file_path.c_str());
        return false;
    }
    
    // 4. 记录日志（不写数据库）
    INFO("文件保存成功: %s", final_file_path.c_str());
    return true;
}
```

### 2. sync_scheduler 文件过滤逻辑

#### 文件过滤策略说明

本方案提供三种文件过滤策略，可根据实际需求选择：

**方案1：仅同步媒体文件（保守方案）**
- 优点：传输量小，专注核心媒体数据
- 缺点：可能遗漏重要的配置文件、日志文件等
- 适用场景：带宽受限，仅需要基本的媒体文件同步

**方案2：扩展文件类型支持（推荐方案）**
- 优点：覆盖大部分常用文件格式，包含文档、数据文件等
- 缺点：传输量适中，需要维护扩展名列表
- 适用场景：大部分生产环境，平衡了完整性和效率

**方案3：同步所有文件（完整方案）**
- 优点：确保所有数据完整同步，无遗漏风险
- 缺点：传输量大，可能包含不必要的系统文件
- 适用场景：数据完整性要求极高，带宽充足的环境

#### 实现代码

```python
def _should_process_file(self, filename: str) -> bool:
    """判断是否应该处理该文件 - 确保不处理传输中的隐藏文件"""
    # 过滤隐藏文件（以.开头的文件）
    if filename.startswith('.'):
        return False
    
    # 过滤临时文件
    if filename.startswith('.tmp_') or filename.endswith('.tmp'):
        return False
    
    # 过滤系统文件
    if filename in ['.DS_Store', 'Thumbs.db', 'desktop.ini']:
        return False
    
    # 文件扩展名过滤策略
    # 方案1：仅同步媒体文件（当前方案）
    # allowed_extensions = {'.mp4', '.mov', '.jpg', '.jpeg', '.png', '.dng'}
    
    # 方案2：扩展文件类型支持（推荐方案）
    allowed_extensions = {
        # 视频文件
        '.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.webm', '.m4v',
        # 图片文件
        '.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.gif', '.webp',
        # RAW格式
        '.dng', '.raw', '.cr2', '.nef', '.arw', '.orf', '.rw2',
        # 文档文件
        '.txt', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
        # 数据文件
        '.csv', '.json', '.xml', '.log', '.las', '.laz',
        # 压缩文件
        '.zip', '.rar', '.7z', '.tar', '.gz',
        # 其他常见格式
        '.kml', '.kmz', '.gpx', '.shp'
    }
    
    # 方案3：同步所有文件（除了已过滤的系统文件和临时文件）
    # 如果需要同步所有文件，可以注释掉下面的扩展名检查
    
    file_ext = os.path.splitext(filename)[1].lower()
    
    # 如果文件没有扩展名，也允许同步（如某些数据文件）
    if not file_ext:
        return True
        
    return file_ext in allowed_extensions
    
    # 方案3实现：同步所有文件（取消扩展名限制）
    # return True  # 取消注释此行并注释上面的扩展名检查代码
```

#### 配置管理

为了便于灵活配置文件过滤策略，需要在 `unified_config.json` 中添加相关配置项：

```json
{
  "file_sync": {
    "filter_strategy": "extended",  // "media_only", "extended", "all_files"
    "custom_extensions": [
      // 当 filter_strategy 为 "custom" 时使用
      ".mp4", ".jpg", ".txt", ".las"
    ],
    "exclude_patterns": [
      // 始终排除的文件模式
      ".*",           // 隐藏文件
      ".tmp_*",       // 临时文件
      "*.tmp",        // 临时文件
      ".DS_Store",    // 系统文件
      "Thumbs.db",    // 系统文件
      "desktop.ini"   // 系统文件
    ],
    "description": "文件同步过滤配置"
  }
}
```

**配置项说明：**
- `filter_strategy`: 过滤策略选择
  - `"media_only"`: 仅同步媒体文件（方案1）
  - `"extended"`: 扩展文件类型支持（方案2，推荐）
  - `"all_files"`: 同步所有文件（方案3）
  - `"custom"`: 自定义扩展名列表
- `custom_extensions`: 自定义文件扩展名列表
- `exclude_patterns`: 始终排除的文件模式

**代码实现示例：**

```python
def _load_filter_config(self):
    """从配置文件加载文件过滤策略"""
    config = self.config_manager.get_config()
    file_sync_config = config.get('file_sync', {})
    
    self.filter_strategy = file_sync_config.get('filter_strategy', 'extended')
    self.custom_extensions = set(file_sync_config.get('custom_extensions', []))
    self.exclude_patterns = file_sync_config.get('exclude_patterns', [
        '.*', '.tmp_*', '*.tmp', '.DS_Store', 'Thumbs.db', 'desktop.ini'
    ])
    
    self.logger.info(f"文件过滤策略: {self.filter_strategy}")

def _should_process_file(self, filename: str) -> bool:
    """根据配置的策略判断是否应该处理该文件"""
    import fnmatch
    
    # 检查排除模式
    for pattern in self.exclude_patterns:
        if fnmatch.fnmatch(filename, pattern) or filename.startswith(pattern.rstrip('*')):
            return False
    
    # 根据策略决定是否处理
    if self.filter_strategy == 'all_files':
        return True
    
    file_ext = os.path.splitext(filename)[1].lower()
    
    if self.filter_strategy == 'media_only':
        media_extensions = {'.mp4', '.mov', '.jpg', '.jpeg', '.png', '.dng'}
        return file_ext in media_extensions
    
    elif self.filter_strategy == 'extended':
        extended_extensions = {
            # 视频文件
            '.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.webm', '.m4v',
            # 图片文件
            '.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.gif', '.webp',
            # RAW格式
            '.dng', '.raw', '.cr2', '.nef', '.arw', '.orf', '.rw2',
            # 文档文件
            '.txt', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
            # 数据文件
            '.csv', '.json', '.xml', '.log', '.las', '.laz',
            # 压缩文件
            '.zip', '.rar', '.7z', '.tar', '.gz',
            # 其他常见格式
            '.kml', '.kmz', '.gpx', '.shp'
        }
        # 如果文件没有扩展名，也允许同步（如某些数据文件）
        return not file_ext or file_ext in extended_extensions
    
    elif self.filter_strategy == 'custom':
        return not file_ext or file_ext in self.custom_extensions
    
    # 默认使用扩展策略
    return True
```

### 3. 数据库架构设计

```sql
CREATE TABLE IF NOT EXISTS media_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,
    filename TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    status TEXT NOT NULL,  -- PENDING, TRANSFERRING, TRANSFERRED, FAILED
    created_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    UNIQUE(filename, file_hash)  -- 防止重复记录
);

CREATE INDEX idx_status ON media_files(status);
CREATE INDEX idx_filename_hash ON media_files(filename, file_hash);
```

## 测试验证方案

### 1. 原子写入机制测试
- 正常文件传输流程验证
- 写入中断情况处理
- 临时文件清理机制
- sync_scheduler不处理.tmp文件验证

### 2. 数据库操作流程测试
- 文件发现和注册流程
- 重复文件检测（文件名+哈希）
- 传输状态管理（PENDING->TRANSFERRING->TRANSFERRED）
- 错误处理和重试机制

### 3. 文件哈希性能测试
- 不同大小文件的哈希计算时间
- 30GB文件采样哈希vs完整哈希对比
- 哈希准确性验证
- 内存使用情况监控

### 4. 线性传输流程测试
- 传输顺序验证（小文件优先）
- 单文件传输确认
- 带宽使用监控
- 长时间运行稳定性

### 5. 文件过滤策略测试
- 不同过滤策略的文件识别准确性
- 配置文件热加载测试
- 自定义扩展名列表验证
- 排除模式匹配测试
- 边界情况处理（无扩展名文件、特殊字符文件名）

### 6. 系统集成测试
- 端到端传输测试（dock->edge->nas）
- 并发写入和扫描测试
- 异常恢复测试
- 性能基准测试
- 多种文件类型混合传输测试

## 风险评估和缓解措施

### 风险1: 大文件哈希计算
**风险**: 30GB文件哈希计算耗时
**缓解**: 采样哈希策略，3MB采样约1-2秒完成

### 风险2: 文件发现延迟
**风险**: 线性模式下新文件发现有延迟
**缓解**: 优化扫描频率，小文件优先传输

### 风险3: 临时文件清理
**风险**: 程序异常退出时临时文件残留
**缓解**: 启动时清理机制，定期清理任务

### 风险4: 数据库性能
**风险**: 大量文件时数据库查询性能
**缓解**: 索引优化，批量操作，连接池

## 实施建议

### 阶段1: dock_info_manager改造（1-2天）
- 实现原子文件写入
- 移除数据库操作
- 基础测试

### 阶段2: sync_scheduler重构（2-3天）
- 文件夹监控实现
- 数据库操作流程
- 哈希计算优化
- 文件过滤策略配置化实现
- 单元测试

### 阶段3: 集成测试（1-2天）
- 端到端测试
- 性能测试
- 错误处理完善

### 阶段4: 生产部署（1天）
- 更新 unified_config.json 配置文件
- 生产环境验证
- 监控部署
- 文档更新

## 总结

### 核心优势
1. **彻底消除数据库并发冲突**: 只有sync_scheduler访问数据库
2. **确保文件传输完整性**: 临时文件+原子重命名机制
3. **完整的传输状态管理**: 数据库记录完整传输过程
4. **高效的重复文件检测**: 文件名+哈希组合策略
5. **优化的大文件处理**: 采样哈希平衡性能和准确性
6. **线性传输避免资源竞争**: 避免带宽抢占和并发冲突
7. **灵活的文件过滤策略**: 支持媒体文件、扩展类型、全文件同步等多种策略

### 关键技术要点
- **原子文件操作**: 确保sync_scheduler不会处理传输中的.filename隐藏文件
- **采样哈希策略**: 30GB文件1-2秒完成哈希计算
- **线性传输模式**: 避免并发冲突，更适合生产环境
- **完整状态管理**: PENDING->TRANSFERRING->TRANSFERRED清晰流程
- **配置化文件过滤**: 通过unified_config.json灵活配置同步策略，支持txt、las等多种文件格式

**推荐采用线性传输模式**，在系统稳定性、资源管理和维护复杂度方面具有显著优势，更适合生产环境长期稳定运行。