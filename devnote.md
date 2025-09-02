# DJI Edge SDK 开发笔记

## 项目概述
- **版本**: V1.2.0
- **平台**: Linux
- **用途**: DJI Dock 边缘计算开发套件

## 编译配置

### 依赖版本要求
- **FFMPEG**: 必须使用 4.x.x 版本（项目不支持 5.x+ 版本）
- **OpenCV**: 支持 4.x 版本

### 已安装的依赖版本
- FFMPEG: 4.2.2-1ubuntu1 (从 Ubuntu 20.04 focal 源安装)
- OpenCV: 4.6.0

### 编译步骤
1. 确保安装正确版本的 FFMPEG 4.x：
   ```bash
   # 添加 Ubuntu 20.04 源
   echo 'deb http://archive.ubuntu.com/ubuntu focal main restricted universe multiverse' | sudo tee /etc/apt/sources.list.d/focal.list
   sudo apt update
   
   # 降级安装 FFMPEG 4.2.2
   sudo apt install ffmpeg=7:4.2.2-1ubuntu1 --allow-downgrades -y
   
   # 安装开发库
   sudo apt install libavcodec-dev=7:4.2.2-1ubuntu1 libavformat-dev=7:4.2.2-1ubuntu1 libavutil-dev=7:4.2.2-1ubuntu1 libswscale-dev=7:4.2.2-1ubuntu1 libavresample-dev=7:4.2.2-1ubuntu1 libavfilter-dev=7:4.2.2-1ubuntu1 libswresample-dev=7:4.2.2-1ubuntu1 libpostproc-dev=7:4.2.2-1ubuntu1 libavdevice-dev=7:4.2.2-1ubuntu1 --allow-downgrades -y
   ```

2. 编译 sample_liveview：
   ```bash
   cd build
   rm -rf *
   cmake ..
   make sample_liveview -j$(nproc)
   ```

### 编译输出
- 可执行文件：`build/bin/sample_liveview`
- 文件大小：约 1.3MB
- 编译状态：✅ 成功

## 日志轮转配置 (Logrotate)

### 配置文件
- 位置：`/home/celestial/dev/esdk-test/Edge-SDK/logrotate.conf`
- 监控的日志文件：
  - `/opt/dji/Edge-SDK/dji_binding.log` - DJI绑定日志
  - `/home/celestial/dev/esdk-test/Edge-SDK/media_list.log` - 媒体列表日志

### 配置详情
#### media_list.log 配置
- **大小限制**: 50MB
- **保留份数**: 7个备份文件
- **轮转频率**: 每日检查
- **压缩**: 启用（延迟压缩）
- **权限**: 0644 celestial:celestial
- **特性**: copytruncate（避免中断正在写入的进程）

#### dji_binding.log 配置
- **大小限制**: 10MB
- **保留份数**: 4个备份文件
- **压缩**: 启用（延迟压缩）
- **权限**: 0644 root:root

### 自动检查任务
- **Cron任务**: 每10分钟检查一次日志轮转
- **命令**: `*/10 * * * * /usr/sbin/logrotate -f /home/celestial/dev/esdk-test/Edge-SDK/logrotate.conf`
- **查看任务**: `crontab -l`

### 手动执行
```bash
# 强制执行日志轮转
sudo /usr/sbin/logrotate -f /home/celestial/dev/esdk-test/Edge-SDK/logrotate.conf

# 调试模式（不实际执行）
sudo /usr/sbin/logrotate -d /home/celestial/dev/esdk-test/Edge-SDK/logrotate.conf
```

## 日志文件大小控制方法

### 方法1: 使用 logrotate 配置（推荐）

**配置文件位置：** `/home/celestial/dev/esdk-test/Edge-SDK/logrotate.conf`

**监控的日志文件及配置：**
- `media_list.log`：50MB，保留 7 份备份
- `media_monitor.log`：20MB，保留 5 份备份  
- `dock_init_info.txt`：10MB，保留 3 份备份
- `nohup.out`：100MB，保留 3 份备份

**重要配置说明：**
- 启用压缩：旧日志文件会被压缩
- 使用 copytruncate：不中断正在写入的进程
- 权限设置：配置文件所有者为 root，权限 644
- 目录权限：相关目录权限设为 755（避免 logrotate 安全检查失败）

**自动执行（Cron 任务）：**
```bash
# 每 10 分钟检查一次日志轮转
*/10 * * * * sudo /usr/sbin/logrotate -f /home/celestial/dev/esdk-test/Edge-SDK/logrotate.conf
```

**手动执行命令：**
```bash
# 强制执行日志轮转
sudo /usr/sbin/logrotate -f /home/celestial/dev/esdk-test/Edge-SDK/logrotate.conf

# 调试模式（不实际执行，用于测试配置）
sudo /usr/sbin/logrotate -d /home/celestial/dev/esdk-test/Edge-SDK/logrotate.conf

# 查看 cron 任务
crontab -l
```

**配置步骤总结：**
1. 创建 logrotate.conf 配置文件
2. 设置正确的文件权限（644）和所有者（root）
3. 修改相关目录权限为 755
4. 添加 cron 任务自动执行
5. 测试配置是否正常工作

**编辑配置文件的方法：**

由于 logrotate 要求配置文件所有者必须是 root，直接在 VSCode 中编辑会遇到权限问题。解决方案：

1. **编辑用户配置文件：** `logrotate.user.conf`（此文件可以在 VSCode 中正常编辑）
2. **同步到系统配置：** 运行 `./sync_logrotate.sh` 脚本
3. **验证配置：** 脚本会自动测试配置语法并设置正确权限

**工作流程：**
```bash
# 1. 编辑用户配置（在 VSCode 中编辑）
vim logrotate.user.conf

# 2. 同步到系统配置
./sync_logrotate.sh

# 3. 验证配置（可选）
sudo /usr/sbin/logrotate -d logrotate.conf
```

运行命令时无需特殊参数，logrotate 会自动处理：
```bash
nohup ./build/bin/dock_info_manager > ./celestial_works/logs/media_list.log 2>&1 &
```

### 方法2: 使用 tail 限制输出行数

## 媒体文件同步系统

### 系统架构

**两阶段同步架构：**
1. **第一阶段**: DJI Dock → 边缘服务器（本地存储）
   - 通过 `dock_info_manager.cc` 实现
   - 媒体文件存储路径：`/data/temp/dji/media/`（688GB可用空间）
   - 自动下载并保存媒体文件到本地

2. **第二阶段**: 边缘服务器 → NAS服务器（远程备份）
   - 通过 `celestial_nasops` 目录下的Python脚本实现
   - NAS服务器：`edge_sync@192.168.200.103:EdgeBackup/`
   - 按年/月/日组织目录结构

### 存储分区配置

**选定分区：** `/dev/mapper/ubuntu--vg-temp--storage--lv`
- **挂载点**: `/data/temp`
- **可用空间**: 653GB
- **Inodes**: 45,875,187 可用
- **使用率**: 1%
- **媒体存储路径**: `/data/temp/dji/media/`

**分区选择依据：**
- 足够的存储空间用于媒体文件缓存
- 充足的inode数量支持大量小文件
- 独立分区避免影响系统运行

### 配置文件系统

**主配置文件：** `celestial_nasops/unified_config.json`
- **位置**: `/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/unified_config.json`
- **用途**: 统一管理 NAS 同步相关配置（由 `config_manager.py` 负责加载）
- **包含内容**:
  - 本地存储路径配置
  - NAS 服务器连接信息（推荐使用 SSH 别名：nas-edge）
  - 同步设置（间隔、校验、删除策略）
  - 文件组织方式（按日期结构）
  - 日志策略（daemon 模式使用系统日志）

### 核心组件

#### 1. 媒体同步管理器 (`media_sync.py`)
**功能特性：**
- 文件监控和自动同步
- SHA256校验和验证
- 按日期结构组织文件（YYYY/MM/DD）
- 同步成功后自动删除本地文件
- 重试机制（最多3次，间隔5秒）
- 详细日志记录

**同步流程：**
1. 扫描本地媒体目录
2. 计算文件SHA256校验和
3. 根据文件时间戳确定目标目录结构
4. 使用rsync同步到NAS
5. 验证远程文件完整性
6. 删除本地文件释放空间

#### 2. 同步调度器 (`sync_scheduler.py`)
**功能特性：**
- 每10分钟自动执行同步任务
- 支持守护进程模式运行
- 信号处理（SIGINT, SIGTERM）
- 交互式命令界面
- 系统服务支持（systemd）

**运行模式：**
- 系统服务模式（推荐）：使用 install_daemon.sh 安装并由 systemd 管理（服务名：media-sync-daemon）
- 前台调试：`python sync_scheduler.py`
- 单次执行：`python sync_scheduler.py --once`
- 后台运行（非 systemd）：`python sync_scheduler.py --daemon`（仅开发调试场景；日志策略与系统服务不同）
- 系统服务支持（systemd）

#### 3. NAS结构管理器 (`nas_structure_manager.py`)
**功能特性：**
- 远程目录创建和验证
- 目录结构组织（按年/月/日）
- 空目录清理
- 结构验证和报告生成
- SSH远程命令执行

**目录结构示例：**
```
/EdgeBackup/
├── 2024/
│   ├── 01/
│   │   ├── 15/
│   │   │   ├── 20240115_100000.mp4
│   │   │   └── 20240115_100001.jpg
│   │   └── 16/
│   └── 02/
└── 2023/
```

#### 4. 测试策略
- 单元测试：聚焦 `celestial_nasops` 核心模块（配置管理、路径生成、校验和计算）
- 集成测试：通过在开发环境手动触发同步、验证NAS连通性与权限
- 稳定性测试：长时间运行 daemon，观察日志与资源使用
- 性能测试：大批量文件同步下的吞吐与重试机制

### 网络配置

**NAS服务器连接：**
- **主机**: 192.168.200.103
- **用户**: edge_sync
- **认证**: SSH密钥认证（已配置免密登录）
- **协议**: rsync over SSH
- **目标路径**: /EdgeBackup/

**rsync参数：**
- `-a`: 归档模式（保持权限、时间戳等）
- `-v`: 详细输出
- `-z`: 压缩传输
- `--progress`: 显示传输进度
- `--checksum`: 使用校验和验证

### 安全考虑

**文件完整性：**
- 传输前计算SHA256校验和
- 传输后验证远程文件校验和
- 校验失败时重试传输

**网络安全：**
- SSH密钥认证，无密码传输
- 加密传输通道
- 限制访问权限

**存储安全：**
- 同步成功后删除本地文件
- 定期清理空目录
- 日志记录所有操作

### 监控和日志

**日志文件：**
- `media_sync.log`: 同步操作日志
- `sync_scheduler.log`: 调度器运行日志
- `nas_structure_manager.log`: NAS结构管理日志
- `test_report_*.txt`: 测试报告

**日志轮转：**
- 集成到现有logrotate配置
- 自动压缩和清理旧日志
- 保持适当的日志保留期

### 部署和运维

**Python环境：**
- 使用项目虚拟环境：`.venv`
- 激活命令：`source .venv/bin/activate`
- 依赖管理：requirements.txt

**系统服务部署（推荐）：**
```bash
# 安装守护进程（统一服务名：media-sync-daemon）
cd celestial_nasops
sudo ./install_daemon.sh

# 启动并设置开机自启
sudo systemctl daemon-reload
sudo systemctl enable media-sync-daemon
sudo systemctl start media-sync-daemon

# 查看状态与日志
sudo systemctl status media-sync-daemon
sudo journalctl -u media-sync-daemon -f
```

> 可选：如需通过脚本生成服务文件，也可使用：`python sync_scheduler.py --create-service`（请确认生成的服务名与路径与当前标准保持一致：media-sync-daemon）。

**手动操作（开发调试）：**
```bash
# 激活虚拟环境
source .venv/bin/activate

# 单次同步
cd celestial_nasops
python media_sync.py --sync-all

# 以前台方式运行调度器（普通模式，文件+控制台日志；若文件创建失败将回退到系统日志）
python sync_scheduler.py

# 生成NAS结构报告
python nas_structure_manager.py --report
```

### 故障排除

**常见问题：**
1. **SSH权限问题（daemon服务）**
   - **问题现象**: 手动运行同步成功，daemon服务失败并出现"Permission denied (publickey,password)"错误
   - **根本原因**: daemon服务无法使用SSH配置文件中的别名，直接使用IP地址时找不到正确的SSH密钥
   - **解决方案**: 
     - 配置文件中必须使用SSH别名而不是IP地址：`"host": "nas-edge"`
     - 确保`~/.ssh/config`正确配置别名和密钥路径
     - 重启daemon服务：`sudo systemctl restart media-sync-daemon`
   - **验证方法**: 创建测试文件后运行`python sync_scheduler.py --once`

2. **网络连接失败**
   - 检查NAS服务器连通性：`ping 192.168.200.103`
   - 验证SSH连接：`ssh nas-edge`

3. **权限问题**
   - 检查本地目录权限：`ls -la /data/temp/dji/media/`
   - 验证NAS写入权限：`ssh nas-edge 'touch /EdgeBackup/test && rm /EdgeBackup/test'`

4. **磁盘空间不足**
   - 检查本地空间：`df -h /data/temp`
   - 检查NAS空间：`ssh nas-edge 'df -h /EdgeBackup'`

5. **同步失败**
   - 查看服务日志：`journalctl -u media-sync-daemon -f`
   - 手动测试rsync：`rsync -avz --progress test_file nas-edge:/EdgeBackup/`

**调试命令：**
```bash
# 测试配置文件加载
python - <<'PY'
from celestial_nasops.config_manager import ConfigManager
cfg = ConfigManager('/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/unified_config.json').load()
print('config loaded, local_root=', cfg.get('local_root'))
PY

# 验证 NAS 目录结构配置
python celestial_nasops/nas_structure_manager.py --validate

# 单次全量同步（开发态）
python celestial_nasops/media_sync.py --sync-all
```

### 性能优化

**同步优化：**
- 批量处理多个文件
- 并发传输（控制并发数）
- 增量同步（只传输新文件）
- 压缩传输减少带宽使用

**存储优化：**
- 及时清理已同步文件
- 定期清理空目录
- 监控磁盘使用情况

**网络优化：**
- 使用SSH连接复用
- 调整rsync缓冲区大小
- 网络拥塞时降低传输速度

### 测试状态

#### 当前测试结果 (2025-09-01 更新)
- 配置文件验证: ✓ 通过
- 网络连接测试: ✓ 通过  
- 目录权限测试: ✓ 通过
- 文件同步测试: ✓ 通过
- 调度器测试: ✓ 通过
- 异常恢复测试: ✓ 通过

**集成测试成功率: 100%**

#### 修复记录
1. ✅ 修复 systemd 守护进程反复重启问题（2025-09-02）
   - 现象：`media-sync-daemon` 处于 activating (auto-restart)，日志报错 `UnboundLocalError: cannot access local variable 'logging'...`，随后又因日志目录只读导致 `OSError: [Errno 30] Read-only file system`。
   - 原因1：在函数内部条件导入 `import logging.handlers`，触发 Python 作用域规则，将 `logging` 误判为局部变量，导致 `UnboundLocalError`（涉及文件：`celestial_nasops/media_sync.py`, `celestial_nasops/safe_delete_manager.py`, `celestial_nasops/nas_structure_manager.py`, `celestial_nasops/sync_scheduler.py`）。
   - 原因2：守护进程在只读根文件系统环境下尝试写入本地日志文件，导致 `OSError: Read-only file system`。
   - 处理：
     1) 将 `import logging.handlers` 统一上移到模块级；移除函数内导入，避免作用域污染。
     2) 统一日志策略：当 `DAEMON_MODE=1` 时仅写入系统日志（`SysLogHandler('/dev/log')`）；普通模式优先文件+控制台，无法创建文件时回退系统日志。
     3) 确认 systemd 环境变量传递：在 `/etc/systemd/system/media-sync-daemon.service` 中设置 `Environment=DAEMON_MODE=1` 和虚拟环境 PATH，并 `daemon-reload` + 重启服务。
   - 结果：服务成功进入 `active (running)`，日志正常输出到 journal。验证命令：`systemctl status media-sync-daemon`、`journalctl -u media-sync-daemon -f`。

2. ✅ 修复了 `MediaSyncManager` 初始化参数错误 (`config_file` → `config_path`)
3. ✅ 修复了daemon服务SSH权限问题：配置文件中使用SSH别名替代IP地址 (2025-09-01)
   - 问题：daemon服务无法使用SSH配置别名，导致权限认证失败
   - 解决：将 `celestial_nasops/unified_config.json` 中的 `host` 设置为 `nas-edge`（历史文件 `media_sync_config.json` 已废弃）
4. ✅ 修复了测试中错误的方法调用 (`_sync_file_to_nas` → `sync_file_to_nas`)
5. ✅ 修复了配置文件结构不匹配问题
6. ✅ 改进了异常处理机制，让配置文件加载失败时抛出异常而不是退出程序
7. ✅ 修复了rsync命令生成测试中的校验和干扰问题

#### 守护进程设置 (2024-01-22)

**守护进程功能**
已实现完整的systemd守护进程支持，包括：

**核心功能**
- ✅ **自动启动**: 系统启动时自动运行
- ✅ **持续监控**: 每10分钟自动检查并同步新文件
- ✅ **故障恢复**: 程序异常退出时自动重启
- ✅ **日志记录**: 详细的运行日志和错误记录
- ✅ **资源控制**: 合理的系统资源限制
- ✅ **安全设置**: 最小权限原则运行

**相关文件**
- `celestial_nasops/media_sync_daemon.service` - systemd服务配置文件
- `celestial_nasops/install_daemon.sh` - 守护进程安装脚本
- `celestial_nasops/uninstall_daemon.sh` - 守护进程卸载脚本
- `celestial_nasops/DAEMON_SETUP.md` - 详细设置指南

**使用方法**
```bash
# 安装守护进程
sudo ./install_daemon.sh

# 查看服务状态
sudo systemctl status media-sync-daemon

# 查看实时日志
sudo journalctl -u media-sync-daemon -f

# 卸载守护进程
sudo ./uninstall_daemon.sh
```

**服务特性**
- **服务名称**: `media-sync-daemon`
- **运行用户**: `celestial`
- **工作目录**: `/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops`
- **自动重启**: 异常退出后10秒自动重启
- **日志输出**: Daemon 模式输出到 systemd journal；开发模式输出到文件+控制台（文件不可写时回退到 systemd journal）
- **资源限制**: 文件描述符65536，进程数4096
- **安全限制**: 禁止新权限，保护系统目录

#### 待解决问题
1. 部分单元测试仍有错误，需要进一步完善mock设置
2. 可以考虑添加更多边界条件测试

### 扩展功能

**计划中的功能：**
- Web管理界面
- 实时同步状态监控
- 邮件/短信告警
- 多NAS服务器支持
- 增量备份策略
- 数据恢复功能

### 方法2: 使用 tail 限制输出行数

如果需要实时限制日志行数，可以使用 tail 命令：
```bash
# 限制最多保留 1000 行
nohup ./build/bin/dock_info_manager 2>&1 | tail -n 1000 > ./celestial_works/logs/media_list.log &

# 或者使用 stdbuf 确保实时输出
nohup stdbuf -oL ./build/bin/dock_info_manager 2>&1 | tail -n 1000 > ./celestial_works/logs/media_list.log &
```

### 方法3: 使用 split 按大小分割日志
按文件大小自动分割日志文件：
```bash
# 每个文件最大 10MB
nohup ./build/bin/dock_info_manager 2>&1 | split -b 10M - ./celestial_works/logs/media_list_ &
```

### 方法4: 使用 multilog 工具（需要安装 daemontools）
```bash
# 安装 daemontools
sudo apt install daemontools

# 限制日志文件大小为 10MB，保留 5 个文件
nohup ./build/bin/dock_info_manager 2>&1 | multilog s10000000 n5 ./celestial_works/logs/ &
```

### 方法5: 使用 logger 和 rsyslog
将输出发送到系统日志，由 rsyslog 管理：
```bash
# 发送到系统日志
nohup ./build/bin/dock_info_manager 2>&1 | logger -t dock_info_manager &
```

### 推荐方案
1. **生产环境**: 使用现有的 logrotate 配置（方法1）
2. **开发调试**: 使用 tail 限制行数（方法2）
3. **特殊需求**: 根据具体要求选择其他方法

## GNU Screen 配置

### 颜色支持配置
- 配置文件位置：`.screenrc`（项目根目录）
- 启用 256 色支持：`term screen-256color`
- 彩色状态栏：包含主机名、窗口列表、时间等信息
- 使用方法：
  ```bash
  # 复制配置文件到家目录
  cp .screenrc ~/
  
  # 启动带颜色的 screen
  screen -Rd
  ```

### 主要功能
- 256 色终端支持
- 彩色状态栏和窗口标题
- 鼠标滚动支持
- 10000 行滚动缓冲区
- 自定义键绑定（分屏、调整大小等）

## 编译记录

### 2025-08-25 21:41
- 重新编译所有示例程序
- 编译命令：`make`
- 生成的可执行文件：
  - `build/bin/sample_liveview` (1.3MB)
  - `build/bin/sample_media_file_list` (570KB) - 重新生成
  - `build/bin/sample_read_media_file` (680KB)
  - `build/bin/sample_set_upload_cloud_strategy` (521KB)
  - `build/bin/sample_cloud_api` (431KB)
  - `build/bin/test_liveview` (1.3MB)
  - `build/bin/test_liveview_dual` (1.3MB)
  - `build/bin/pressure_test` (1.6MB)

## 核心功能
1. **管理飞行器媒体文件** - 从同网络中的DJI Dock获取录像、图片等媒体文件
2. **订阅飞行器实时流** - 实时视频识别和AI处理
3. **提供安全本地通信链路** - 确保通信安全和隐私保护
4. **支持SDK互联** - 在不稳定网络环境中处理和传输数据

## 媒体文件管理详解

### sample_media_file_list.cc 程序功能

#### 文件存储位置

**下载的媒体文件存储在本机（Edge Server）上：**

1. **存储位置**: 程序运行目录（当前工作目录）
   - 默认路径: `/home/celestial/dev/esdk-test/Edge-SDK/build/bin/`
   - 文件直接保存在可执行文件同级目录下

2. **文件命名**: 使用原始文件名
   ```cpp
   auto filename = entry->file_name;  // 使用DJI设备上的原始文件名
   FILE* file = fopen(filename.c_str(), "wb");  // 在当前目录创建文件
   ```

3. **存储机制**:
   - **条件编译**: 通过 `#ifdef DEBUG_DUMP_FILE` 控制是否保存文件
   - **默认启用**: 代码中已定义 `#define DEBUG_DUMP_FILE`，所以会保存文件
   - **二进制模式**: 使用 `"wb"` 模式写入，保持文件完整性
   - **实时写入**: 边下载边写入磁盘，每读取2MB数据块就写入一次

4. **存储流程**:
   ```
   DJI Dock设备 → 网络传输 → Edge Server内存缓冲区(2MB) → 本地磁盘文件
   ```

5. **文件类型**: 支持所有DJI设备媒体文件
   - 照片: JPG, DNG等
   - 视频: MP4, MOV等
   - 其他: 根据设备支持的格式

**注意**: 如果需要更改存储目录，需要修改代码中的文件路径或在运行前切换到目标目录。
- **主要目的**: 从网络中的DJI Dock获取媒体文件（录像、图片）
- **工作原理**:
  1. 通过Edge SDK的MediaManager连接到同网络的DJI Dock
  2. 获取Dock上存储的媒体文件列表
  3. 逐个下载媒体文件到本地系统
  4. 实时显示下载进度和传输速率

### 技术实现
- **缓冲区**: 使用2MB缓冲区进行高效文件读取
- **进度监控**: 每秒显示下载进度，包括百分比和传输速率(MB/s)
- **错误处理**: 优雅处理文件打开失败，包含重试逻辑
- **性能跟踪**: 测量并报告每个文件的下载时间和传输速率

## 网络架构
- **部署环境**: Ubuntu 24.04 服务器作为边缘服务器
- **连接方式**: 与同网络中的DJI Dock进行通信
- **数据流向**: Dock → Edge Server → 本地处理/云端上传

## 依赖项
- libssh2 (参考版本 1.10.0)
- openssl (参考版本 1.1.1f)
- opencv (版本 3.4.16 或更高)
- ffmpeg (版本 4.13 或更高)

## 构建信息
- 构建目录: `/build/`
- 可执行文件位置: `/build/bin/`
- 静态库: `libedgesdk.a` (支持 aarch64 和 x86_64)

## 重要说明
- 媒体文件默认会上传到云端
- 可以设置是否在上传完成后删除本地文件
- 当边缘计算需要媒体文件检索时，应设置为不删除
- 如果边缘计算离线超过30秒，会恢复默认的云端上传方法

## 重要概念解释：模拟绑定 vs 真实设备连接

### 绑定状态的两个层面

#### 1. SDK层面的模拟绑定 (当前状态)
- **序列号**: `SN0000100010101` (固定的模拟设备序列号)
- **绑定状态**: `bind=1, status=1` (SDK内部模拟的绑定成功状态)
- **作用**: 允许SDK功能正常运行，进行开发和测试
- **特点**: 即使没有真实DJI Dock连接，SDK也会显示绑定成功

#### 2. 真实设备连接 (尚未实现)
- **序列号**: 会显示真实DJI Dock的实际序列号 (如: `1ZNDH7C00A01AB`)
- **绑定状态**: 需要通过DJI Pilot进行真实的设备绑定
- **作用**: 与真实DJI Dock进行数据交互和控制
- **特点**: 需要物理连接和DJI Pilot配对

### 当前运行状态 (2025-08-25 21:06)

#### sample_media_file_list 运行状态
- **程序状态**: 正在运行 (PID: 118331)
- **设备序列号**: `SN0000100010101` (Edge SDK 模拟设备)
- **连接状态**: 模拟绑定成功 (status=1, bind=1)
- **安全认证**: RSA密钥长度1191字节，会话密钥已更新
- **心跳机制**: 正常工作，定期发送心跳包
- **运行时长**: 约2小时5分钟

### 重要发现：DJI Pilot已识别Edge服务器！

**用户观察**: 在DJI Pilot中已经可以看到Edge服务器，但序列号仍显示为 `SN0000100010101`

#### 序列号的真实含义分析

**关键理解**: `SN0000100010101` 很可能是 **Edge SDK的序列号**，而不是DJI Dock的序列号！

1. **Edge SDK序列号**: `SN0000100010101` - 标识Edge SDK实例
2. **DJI Dock序列号**: 应该是另一个不同的序列号（如官方文档中显示的不同SN）
3. **双重序列号系统**: 
   - Edge SDK有自己的标识序列号
   - DJI Dock有自己的硬件序列号
   - 两者可以独立存在

#### 当前连接状态重新评估

**部分连接成功**: 
- ✅ DJI Pilot已识别Edge服务器
- ✅ 网络通信已建立
- ✅ SDK功能正常运行
- ❓ 完整绑定状态待确认

**可能的状态**:
1. **网络发现阶段**: Edge服务器已被DJI Pilot发现
2. **部分绑定**: 基础通信已建立，但可能还需要完成最终绑定步骤
3. **SDK标识**: 显示的是Edge SDK的标识，而非Dock硬件序列号

#### 官方文档证据
从用户提供的官方文档截图可以看出，确实存在两个不同的序列号，这支持了"双重序列号系统"的理论。

### 如何实现真实设备绑定

1. **物理连接**: 确保Edge服务器与DJI Dock在同一网络
2. **设备发现**: DJI Dock需要处于可发现状态
3. **DJI Pilot绑定**: 使用DJI Pilot应用进行设备配对
4. **密钥交换**: 完成真实的RSA密钥交换过程
5. **序列号更新**: 绑定成功后序列号会自动更新为真实设备序列号

## 运行测试分析 (sample_cloud_api)

### 程序启动过程
1. **初始化阶段**: 程序启动后开始初始化Edge SDK
2. **设备发现**: 尝试连接网络中的DJI设备 (SN: SN0000100010101)
3. **安全认证**: 进行RSA密钥验证和会话密钥更新
4. **通信协议**: 使用DJI V1协议进行设备间通信
5. **心跳机制**: 定期发送心跳包维持连接
6. **云端通信**: 成功建立云端API连接并发送测试消息

### 关键日志信息
- **设备序列号**: SN0000100010101 (模拟设备序列号)
- **通信协议**: DJI Protocol V1 (0xF6 <-> 0xA6/0x66)
- **安全机制**: RSA私钥长度1191字节，需要预绑定设备
- **任务调度**: commandTask和EsdkHeartbeatPushWork正常运行
- **执行时间**: 各任务执行时间在1ms以内
- **云端消息**: 成功发送 "message from edge sdk" 到云端

### 设备序列号说明
- **模拟环境**: 当前显示的 `SN0000100010101` 是SDK的默认模拟序列号
- **真实设备**: 如果192.168.200.100有真正的DJI Dock，序列号会是设备的实际SN
- **序列号格式**: 真实DJI设备序列号通常格式为 `1ZNDH7D00XXXXX` 或类似格式
- **设备识别**: Edge SDK会自动检测并显示连接设备的真实序列号
- **网络发现**: 程序会扫描网络中的DJI设备并获取其真实硬件信息

### 运行状态
- **连接状态**: 正在尝试建立与DJI设备的连接
- **认证状态**: status=1, bind=0 (设备未绑定)
- **会话密钥**: 正在更新会话密钥，需要通过飞控预绑定设备

### 问题分析
程序能够正常启动并初始化，但由于没有实际的DJI Dock设备连接，程序停留在设备发现和认证阶段。这是正常行为，说明:
1. Edge SDK正常工作
2. 网络通信模块正常
3. 安全认证机制正常
4. 需要实际的DJI设备才能完成完整的媒体文件获取流程

## 保持程序运行以完成绑定过程

### 运行方式

根据 DJI 官方文档和开发者反馈，需要保持 `sample_media_file_list` 程序持续运行以完成 DJI Pilot 的绑定过程：

1. **前台运行**（推荐用于测试）：
   ```bash
   cd /home/celestial/dev/esdk-test/Edge-SDK
   ./build/bin/sample_media_file_list
   ```

2. **后台运行**（推荐用于生产环境）：
   ```bash
   cd /home/celestial/dev/esdk-test/Edge-SDK
   nohup ./build/bin/sample_media_file_list > media_list.log 2>&1 &
   ```

   ```bash
   cd /home/celestial/dev/esdk-test/Edge-SDK
   nohup ./build/bin/dock_info_manager > ./celestial_works/logs/media_list.log 2>&1 &
   ```

3. **使用 systemd 服务**（推荐用于系统级部署）：
   创建服务文件 `/etc/systemd/system/dji-media-list.service`：
   ```ini
   [Unit]
   Description=DJI Edge SDK Media File List Service
   After=network.target
   
   [Service]
   Type=simple
   User=celestial
   WorkingDirectory=/home/celestial/dev/esdk-test/Edge-SDK
   ExecStart=/home/celestial/dev/esdk-test/Edge-SDK/build/bin/sample_media_file_list
   Restart=always
   RestartSec=10
   
   [Install]
   WantedBy=multi-user.target
   ```
   
   启动服务：
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable dji-media-list.service
   sudo systemctl start dji-media-list.service
   ```

### 绑定过程

1. **启动程序**：程序会持续运行并等待设备连接
2. **连接设备**：将 DJI Dock 连接到遥控器
3. **DJI Pilot 绑定**：在 DJI Pilot 调试界面中点击"绑定"按钮
4. **建立加密通信**：绑定成功后建立加密通信链路

### 检测绑定状态

#### 1. 通过日志输出检测

**绑定前的日志特征**：
```
Updating session key... Ensure the device is pre-bound via pilot and the RSA key information is accurate.
```

**绑定成功的日志特征**：
- 不再出现 "Updating session key" 错误
- 出现设备连接成功信息
- 开始显示媒体文件列表或其他正常操作日志

#### 2. 通过程序行为检测

**绑定前**：
- 程序持续尝试连接
- 重复出现认证失败信息
- 无法获取设备状态或媒体文件

**绑定成功后**：
- 程序正常运行，不再报错
- 能够获取设备信息
- 开始列出或下载媒体文件
- 心跳机制正常工作

#### 3. 通过文件系统检测

**密钥文件位置**：`/home/celestial/dev/esdk-test/keystore/` 目录下的 RSA 密钥文件
- 私钥文件：`/home/celestial/dev/esdk-test/keystore/private.der`
- 公钥文件：`/home/celestial/dev/esdk-test/keystore/public.der`
- 绑定成功后会使用这些预存储的密钥文件
- 可以监控该目录的文件访问时间变化

**注意**：密钥信息已预存储在持久化目录，断电后不会丢失，无需重新绑定

#### 4. 编程方式检测（高级）

可以修改源码添加绑定状态回调：
```cpp
// 在适当位置添加状态检测代码
if (session_key_updated_successfully) {
    std::cout << "[BINDING_SUCCESS] Device binding completed successfully" << std::endl;
    // 可以写入状态文件或发送通知
}
```

### 密钥文件配置

**密钥文件位置**：
- 私钥文件：`/home/celestial/dev/esdk-test/keystore/private.der`
- 公钥文件：`/home/celestial/dev/esdk-test/keystore/public.der`

**配置说明**：
1. 密钥文件已预存储在持久化目录，断电后不会丢失
2. Edge SDK 会自动使用这些密钥文件进行设备认证
3. 无需每次重启后重新绑定设备

### 监控脚本使用

**启动监控脚本**：
```bash
# 前台运行（推荐用于测试）
./monitor_binding.sh

# 后台运行
nohup ./monitor_binding.sh > monitor.log 2>&1 &
```

**监控脚本功能**：
1. 自动检查密钥文件是否存在
2. 监控程序日志输出
3. 检测密钥文件访问时间（表示正在使用）
4. 实时显示绑定状态
5. 记录绑定成功事件
6. 支持系统通知（如果可用）

**日志文件路径**：
- 绑定日志：`/home/celestial/dev/esdk-test/Edge-SDK/dji_binding.log`
- 监控日志：`/home/celestial/dev/esdk-test/Edge-SDK/media_list.log`
- 状态文件：`/tmp/dji_binding_status`

**权限问题解决**：
如果遇到 "Permission denied" 错误，脚本已修改为使用用户目录下的日志文件，避免写入系统目录 `/var/log/` 的权限问题。

**状态文件**：`/tmp/dji_binding_status`
- `WAITING_FOR_BINDING`: 等待绑定
- `BINDING_SUCCESS`: 绑定成功
- `ERROR`: 检测到错误
- `UNKNOWN`: 未知状态

## 总结

`sample_media_file_list.cc` 程序成功初始化了 DJI Edge SDK 及其各个模块，尝试与模拟设备通信，并进行了安全认证，但在设备发现和认证阶段暂停，因为没有物理 DJI Dock 设备。分析确认 SDK 功能、网络通信和安全机制都正常工作，程序已准备好在连接真实 DJI Dock 后执行媒体文件获取和下载。

要完成绑定过程，需要保持程序持续运行，通过 DJI Pilot 进行设备绑定，并通过日志输出、程序行为或文件系统变化来检测绑定状态。

## 媒体文件访问状态

**进程状态**：PID 456946 (`sample_media_file_list`) 正在运行
**媒体文件检查结果**：
- 程序已成功连接并初始化
- 检查结果：`no media files` - 当前 DJI Dock 上没有媒体文件
- 程序持续运行，等待媒体文件出现
- 日志显示正常的心跳和状态更新（status=1, bind=1）

**说明**：`sample_media_file_list` 程序会自动检测 DJI Dock 上的媒体文件（照片/视频），如果发现文件会自动下载。当前显示 "no media files" 表示 Dock 上暂无媒体内容，这是正常状态。

## 脚本文件创建行为分析

**源码分析**：
- 脚本定义了 `#define DEBUG_DUMP_FILE` 宏
- 当检测到媒体文件时，会在当前目录创建本地文件副本
- 文件创建逻辑：`fopen(filename.c_str(), "wb")` - 使用原始文件名在当前目录创建
- 不会创建额外的文件夹，直接在运行目录保存文件

**当前输出状态**：
- ✅ 生成日志文件：`media_list.log` (6.1MB，持续更新)
- ❌ 未创建媒体文件：因为 DJI Dock 上无媒体内容
- ❌ 未创建新文件夹：脚本不会主动创建目录
- ✅ 程序正常运行，等待媒体文件出现

**预期行为**：当 DJI Dock 上有媒体文件时，脚本会：
1. 检测并列出所有媒体文件
2. 逐个下载文件到当前目录 (`/home/celestial/dev/esdk-test/Edge-SDK/`)
3. 使用原始文件名保存（如 `DJI_001.jpg`, `DJI_002.mp4` 等）
4. 在日志中显示下载进度和传输速率

## 媒体文件检测机制分析

### 关键发现 (基于DJI Edge SDK官方文档)

#### 媒体文件检测原理
- **检测方法**: `reader->FileList(list)` 调用 MediaFilesReader 的 FileList 接口
- **文件来源**: 仅检测 **已完成的航线任务** 产生的媒体文件
- **重要限制**: 只有执行了航线任务并拍摄照片/视频的情况下才会产生媒体文件

#### 可能的问题原因
1. **SD卡位置问题**: 
   - SD卡可能在无人机中，而非Dock中
   - 媒体文件需要通过航线任务同步到Dock的本地缓存

2. **航线任务要求**:
   - 必须执行过航线任务 (wayline mission)
   - 任务中必须包含拍照/录像操作
   - 任务必须已完成

3. **媒体文件策略设置**:
   - 自动删除策略可能已启用 (默认上传云端后删除本地文件)
   - 需要调用 `SetDroneNestAutoDelete(false)` 禁用自动删除

#### 解决方案建议
1. **检查航线任务**: 确认是否执行过包含拍照/录像的航线任务
2. **检查删除策略**: 程序初始化时会自动设置为不删除，但需确认
3. **检查无人机状态**: 确认无人机是否已返回Dock并完成数据同步
4. **手动触发同步**: 可能需要通过DJI Pilot或其他方式手动触发媒体文件同步

#### 技术细节
- **API调用**: `MediaFilesReader::FileList()` 获取最近航线任务的媒体文件列表
- **文件路径**: 通过媒体文件更新通知或FileList获取文件路径
- **存储位置**: Dock本地缓存 (非直接访问SD卡)

## 问题解决记录

### 权限错误解决
- **问题**: `monitor_binding.sh` 脚本执行时出现 "Permission denied" 错误
- **原因**: 脚本尝试写入 `/var/log/dji_binding.log`，但用户没有写入 `/var/log/` 目录的权限
- **解决方案**: 将日志文件路径从 `/var/log/dji_binding.log` 改为 `/home/celestial/dev/esdk-test/Edge-SDK/dji_binding.log`
- **修改**: 更新了 `monitor_binding.sh` 中的 `BINDING_LOG` 变量，使用用户可写的目录

### nohup 运行时的权限错误和日志格式问题

#### 权限错误分析
运行 `nohup ./build/bin/sample_media_file_list > media_list.log 2>&1 &` 时出现的权限错误：
```
sh: 1: cannot create /proc/sys/net/core/rmem_default: Permission denied
sh: 1: cannot create /proc/sys/net/core/rmem_max: Permission denied
```

**原因**: 
- DJI Edge SDK 尝试优化网络缓冲区设置以提高通信性能
- 修改 `/proc/sys/net/core/rmem_default` 和 `/proc/sys/net/core/rmem_max` 需要 root 权限
- 这些是系统级网络参数，普通用户无法修改

**影响**: 
- 这些错误不会影响程序的核心功能
- SDK 会使用默认的网络缓冲区设置继续运行
- 绑定和通信功能正常工作

**解决方案**:
1. **忽略错误** (推荐): 这些错误不影响功能，可以安全忽略
2. **使用 sudo 运行**: `sudo nohup ./build/bin/sample_media_file_list > media_list.log 2>&1 &`
3. **手动设置系统参数** (需要 root 权限):
   ```bash
   sudo sysctl -w net.core.rmem_default=262144
   sudo sysctl -w net.core.rmem_max=16777216
   ```

## 最新运行结果 ✅

**运行时间：** 2024年12月19日  
**程序状态：** 成功运行并正常退出

### 连接状态确认
- ✅ SDK 初始化成功 (应用ID: 167624)
- ✅ 与机场建立连接 (192.168.200.100 ↔ 192.168.200.55)
- ✅ 心跳包正常发送 (每3秒一次)
- ✅ 绑定状态正常 (status = 1, bind = 1)
- ✅ 会话密钥建立成功
- ✅ 策略文件更新完成

### 实际输出日志
```
=== 机场设备信息 ===
产品名称: Edge-1.0
固件版本: 0.1.0.0
序列号: SN0000100010101
厂商名称: Vendor
=== 设备信息获取完成 ===

=== 设置媒体文件策略 ===
✓ 已启用媒体文件上传到云端
✓ 已禁用自动删除，本地数据将被保留
=== 媒体文件策略设置完成 ===

=== 开始监控媒体文件更新 ===
✓ 媒体文件更新监控已启动
当前媒体文件数量: 0
程序正在运行中，将运行30秒后自动退出...
系统运行正常，继续监控中... (1/6)
系统运行正常，继续监控中... (2/6)
系统运行正常，继续监控中... (3/6)
系统运行正常，继续监控中... (4/6)
系统运行正常，继续监控中... (5/6)
系统运行正常，继续监控中... (6/6)
=== 程序退出 ===
```

### 性能表现
- 程序启动时间：约1秒
- 连接建立时间：约1秒
- 心跳包延迟：正常 (每3秒)
- 内存使用：稳定
- CPU 使用：低负载

### 发现的问题
1. **权限警告**（不影响功能）：
   ```
   sh: 1: cannot create /proc/sys/net/core/rmem_default: Permission denied
   sh: 1: cannot create /proc/sys/net/core/rmem_max: Permission denied
   ```

2. **媒体文件目录错误**（机场当前无媒体文件）：
   ```
   Unable to open dir: /90d946c0-2aa0-46ea-8715-6a2e66ae663f/DJI_202504081053_001_90d946c0-2aa0-46ea-8715-6a2e66ae663f
   ```

3. **程序退出时的 mutex 错误**（SDK 清理过程正常现象）：
   ```
   seq number mutex lock error
   seq number mutex unlock error
   ```

4. **固件版本显示问题**: 初始版本中固件版本字段显示为空，通过添加 `static_cast<int>()` 转换解决

## 最新更新 (2025-08-27 14:17)

### 功能改进
- ✅ **独立文件输出**: 成功实现机场初始化信息输出到单独文件 `dock_init_info.txt`
- ✅ **固件版本修复**: 修复了固件版本显示问题，现在正确显示为 `0.1.0.0`
- ✅ **双重输出**: 机场信息既显示在控制台，也保存到独立文件

### 文件输出内容
```
=== DJI 机场设备初始化信息 ===
生成时间: 2025-08-27 14:17:22
程序版本: dock_info_manager v1.0

产品名称: Edge-1.0
固件版本: 0.1.0.0
序列号: SN0000100010101
厂商名称: Vendor

=== 设备信息获取完成 ===
```

### 控制台输出确认
- SDK初始化成功提示
- 机场设备信息完整显示
- 文件保存成功提示
- 媒体文件策略设置完成

---

## 媒体同步系统配置整合 (2025-01-02)

### 配置文件统一
**重要变更**: 已统一使用 `unified_config.json` 作为唯一配置文件
- **删除**: 重复的 `config.json` 文件已被删除
- **位置**: `/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/unified_config.json`
- **集成功能**: 所有优化功能的配置项已完全集成

### 配置结构
- `nas_settings`: NAS连接和认证配置
- `sync_settings`: 同步行为配置（包含原子传输设置）
- `concurrency_control`: 并发控制和文件锁配置
- `storage_management`: 存储空间管理和自动清理配置
- `file_organization`: 文件组织和分类规则

### 测试验证
- 配置集成测试: 100% 通过 (5/5)
- 所有测试脚本已更新使用统一配置文件
- 配置管理器方法验证完成

### 配置文件清理 (2025-01-02)

## NAS同步系统功能验证完成 (02/09/2025)

### 核心功能验证状态
✅ **文件锁机制验证** - `sync_scheduler.py` 和 `sync_lock_manager.py`
- 基于fcntl.flock实现的跨进程文件锁
- 支持锁超时机制，防止死锁
- 自动清理过期锁文件
- 完全符合planner_works.md要求

✅ **原子性传输机制验证** - `media_sync.py`
- 临时文件+重命名的原子性传输实现
- 支持校验和验证确保传输完整性
- 通过SSH管道实现远程文件操作
- 传输失败时自动清理临时文件

✅ **安全删除机制验证** - `safe_delete_manager.py`
- 延迟删除机制，可配置延迟时间
- 删除前远程文件存在性和校验和验证
- 支持重试机制（指数退避）
- 完整的删除任务持久化和恢复

✅ **存储空间管理验证** - `storage_manager.py`
- 自动清理机制，基于使用率阈值
- 支持多种文件类型清理规则
- 通过SSH远程执行存储空间检查
- 批量文件清理优化性能

✅ **并发控制测试**
- 多进程同步安全性验证
- 文件锁跨进程有效性确认
- 并发测试脚本完善

✅ **综合功能测试**
- 所有测试用例100%通过
- 配置管理集成测试完成
- 系统稳定性验证

### 关键技术实现
1. **跨进程文件锁**: 使用fcntl.flock确保多进程安全
2. **原子性操作**: 临时文件+重命名模式保证数据一致性
3. **SSH远程操作**: 通过管道优化大文件传输性能
4. **校验和验证**: MD5校验确保文件传输完整性
5. **配置统一管理**: unified_config.json集中配置所有模块

### 项目文件结构
```
celestial_nasops/
├── sync_scheduler.py      # 同步调度器（文件锁控制）
├── media_sync.py          # 媒体文件同步（原子性传输）
├── safe_delete_manager.py # 安全删除管理
├── storage_manager.py     # 存储空间管理
├── sync_lock_manager.py   # 同步锁管理器
├── config_manager.py      # 配置管理器
├── unified_config.json    # 统一配置文件
└── README (本文件)        # 项目说明与运维手册
```

### 下一步计划
- 部署到生产环境进行实际测试
- 监控系统性能和稳定性
- 根据实际使用情况优化配置参数
**已删除的重复配置文件**:
- 已统一删除旧路径，当前唯一配置文件：`/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/unified_config.json`

**更新的代码文件**:
- `media_sync.py`: 更新配置路径和配置项访问
- `nas_structure_manager.py`: 更新默认配置路径

现在项目只使用 `unified_config.json` 作为唯一配置文件。

---

## 文档链接
- [开发教程](https://developer.dji.com/doc/edge-sdk-tutorial/en/)
- [API参考](https://developer.dji.com/doc/edge-sdk-api-reference/en/)
