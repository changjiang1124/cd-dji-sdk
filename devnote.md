# DJI Edge SDK 开发笔记

## 项目概述

本项目基于DJI Edge SDK开发，实现从DJI无人机机场获取媒体文件并同步到NAS的完整流程。

### 项目架构

```
阶段1: DJI机场 → Edge服务器 (C++)
阶段2: Edge服务器 → NAS (Python)
```

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

**主程序**: `celestial_works/src/dock_info_manager.cc`
- 集成SQLite数据库操作
- 从DJI机场下载媒体文件
- 更新数据库状态

**数据库操作**: `celestial_works/src/media_status_db.cc/h`
- 提供C++数据库接口
- 支持状态查询和更新

**编译配置**: 根目录`CMakeLists.txt`已更新
- 链接sqlite3库
- 包含media_status_db.cc

### 3. Python 组件 (阶段2)

**主程序**: `celestial_nasops/media_sync.py`
- 基于数据库查询待传输文件
- 同步文件到NAS (192.168.200.103)
- 更新传输状态

**数据库接口**: `celestial_works/src/media_status_db.py`
- Python SQLite操作封装
- 与C++组件共享数据库

**配置文件**: `celestial_nasops/unified_config.json`

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
   - 二进制文件: `celestial_works/bin/dock_info_manager`
   - 功能: 从DJI机场获取媒体文件到边缘服务器

2. **media-sync-daemon服务** (阶段2 - NAS同步)
   - 服务文件: `celestial_nasops/media_sync_daemon.service`
   - 安装脚本: `celestial_nasops/install_daemon.sh`
   - 主程序: `celestial_nasops/sync_scheduler.py`
   - 功能: 将媒体文件从边缘服务器同步到NAS

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

## 网络配置

**NAS连接**: 
- IP: 192.168.200.103
- 用户: edge_sync
- SSH配置: `/home/celestial/.ssh/config` (别名: nas-edge)

## 密钥文件

**位置**: `/home/celestial/dev/esdk-test/keystore/`
- 私钥: `private.der`
- 公钥: `public.der`

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

**最后更新**: 2025-09-02 14:10  
**测试状态**: 核心功能正常，待修复配置问题
