# DJI媒体文件同步守护进程设置指南

## 概述

本指南介绍如何将DJI媒体文件同步程序设置为系统守护进程，实现自动监控和同步功能。

## 功能特性

- **自动启动**: 系统启动时自动运行
- **持续监控**: 每10分钟自动检查并同步新文件
- **故障恢复**: 程序异常退出时自动重启
- **日志记录**: 详细的运行日志和错误记录
- **资源控制**: 合理的系统资源限制
- **安全设置**: 最小权限原则运行

## 安装步骤

### 1. 准备工作

确保以下条件已满足：

```bash
# 检查Python虚拟环境
ls -la /home/celestial/dev/esdk-test/Edge-SDK/.venv/bin/python

# 检查同步脚本
ls -la /home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/sync_scheduler.py

# 检查配置文件
ls -la /home/celestial/dev/esdk-test/Edge-SDK/media_sync_config.json

# 测试SSH连接到NAS
ssh edge_sync@192.168.200.103 "echo 'SSH连接正常'"
```

### 2. 安装守护进程

使用提供的安装脚本：

```bash
cd /home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops
sudo ./install_daemon.sh
```

安装脚本会自动：
- 创建必要的目录
- 复制systemd服务文件
- 启用并启动服务
- 显示服务状态

### 3. 验证安装

检查服务状态：

```bash
# 查看服务状态
sudo systemctl status media-sync-daemon

# 查看实时日志
sudo journalctl -u media-sync-daemon -f

# 查看服务是否开机自启
sudo systemctl is-enabled media-sync-daemon
```

## 服务管理

### 基本命令

```bash
# 启动服务
sudo systemctl start media-sync-daemon

# 停止服务
sudo systemctl stop media-sync-daemon

# 重启服务
sudo systemctl restart media-sync-daemon

# 查看状态
sudo systemctl status media-sync-daemon

# 启用开机自启
sudo systemctl enable media-sync-daemon

# 禁用开机自启
sudo systemctl disable media-sync-daemon
```

### 日志查看

```bash
# 查看系统日志
sudo journalctl -u media-sync-daemon

# 查看实时日志
sudo journalctl -u media-sync-daemon -f

# 查看最近的日志
sudo journalctl -u media-sync-daemon --since "1 hour ago"

# 查看应用程序日志文件
tail -f /home/celestial/dev/esdk-test/Edge-SDK/celestial_works/logs/sync_scheduler.log
```

## 配置调整

### 修改同步间隔

编辑服务文件：

```bash
sudo systemctl edit media-sync-daemon
```

添加以下内容来修改同步间隔（例如改为5分钟）：

```ini
[Service]
ExecStart=
ExecStart=/home/celestial/dev/esdk-test/Edge-SDK/.venv/bin/python /home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/sync_scheduler.py --daemon --interval 5
```

然后重启服务：

```bash
sudo systemctl daemon-reload
sudo systemctl restart media-sync-daemon
```

### 修改资源限制

编辑服务文件来调整资源限制：

```bash
sudo systemctl edit media-sync-daemon
```

添加资源限制配置：

```ini
[Service]
# 限制内存使用（例如512MB）
MemoryMax=512M
# 限制CPU使用（例如50%）
CPUQuota=50%
```

## 测试功能

### 手动测试同步

```bash
# 停止守护进程
sudo systemctl stop media-sync-daemon

# 手动执行一次同步
cd /home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops
../.venv/bin/python sync_scheduler.py --once

# 重新启动守护进程
sudo systemctl start media-sync-daemon
```

### 测试文件同步

1. 在媒体目录中放置测试文件：

```bash
# 创建测试文件
echo "测试内容" > /data/temp/dji/media/test_$(date +%Y%m%d_%H%M%S).txt
```

2. 等待下一个同步周期（最多10分钟）或手动触发同步

3. 检查NAS上是否有对应文件：

```bash
ssh nas-edge "find ~/EdgeBackup -name 'test*' -type f"
```

## 故障排除

### SSH权限问题

**问题现象：**
- 手动运行 `sync_scheduler.py --once` 成功
- daemon服务运行时出现 "Permission denied (publickey,password)" 错误
- rsync返回错误码255或12

**根本原因：**
daemon服务无法使用SSH配置文件中的别名，直接使用IP地址连接时无法找到正确的SSH密钥。

**解决方案：**
1. 确保配置文件中使用SSH别名而不是IP地址：
   ```json
   "nas_config": {
     "host": "nas-edge",  // 使用SSH别名，不是IP地址
     "username": "edge_sync"
   }
   ```

2. 确认SSH配置文件 `/home/celestial/.ssh/config` 正确设置：
   ```
   Host nas-edge
       HostName 192.168.200.103
       User edge_sync
       IdentityFile ~/.ssh/id_ed25519_edge_sync
       IdentitiesOnly yes
   ```

3. 重启daemon服务使配置生效：
   ```bash
   sudo systemctl restart media-sync-daemon
   ```

**验证方法：**
```bash
# 创建测试文件
echo "test" > /data/temp/dji/media/test_$(date +%Y%m%d_%H%M%S).txt

# 手动触发同步
python sync_scheduler.py --once

# 检查daemon日志
journalctl -u media-sync-daemon --since "5 minutes ago"
```

### 常见问题

1. **服务启动失败**
   ```bash
   # 查看详细错误信息
   sudo journalctl -u media-sync-daemon --no-pager
   
   # 检查配置文件
   python3 -c "import json; json.load(open('/home/celestial/dev/esdk-test/Edge-SDK/media_sync_config.json'))"
   ```

2. **SSH连接失败**
   ```bash
   # 测试SSH连接
   ssh -v edge_sync@192.168.200.103
   
   # 检查SSH密钥
   ls -la ~/.ssh/
   ```

3. **权限问题**
   ```bash
   # 检查目录权限
   ls -la /data/temp/dji/media/
   ls -la /home/celestial/dev/esdk-test/Edge-SDK/celestial_works/logs/
   
   # 修复权限
   sudo chown -R celestial:celestial /home/celestial/dev/esdk-test/Edge-SDK/celestial_works/logs/
   ```

4. **Python环境问题**
   ```bash
   # 检查虚拟环境
   /home/celestial/dev/esdk-test/Edge-SDK/.venv/bin/python --version
   
   # 检查依赖包
   /home/celestial/dev/esdk-test/Edge-SDK/.venv/bin/pip list
   ```

### 重置服务

如果服务出现问题，可以完全重置：

```bash
# 卸载服务
sudo ./uninstall_daemon.sh

# 清理日志（可选）
rm -rf /home/celestial/dev/esdk-test/Edge-SDK/celestial_works/logs/*

# 重新安装
sudo ./install_daemon.sh
```

## 卸载

使用提供的卸载脚本：

```bash
cd /home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops
sudo ./uninstall_daemon.sh
```

## 监控建议

1. **定期检查日志**：建议每周检查一次同步日志
2. **磁盘空间监控**：确保本地和NAS有足够存储空间
3. **网络连接监控**：确保到NAS的网络连接稳定
4. **性能监控**：监控CPU和内存使用情况

## 安全注意事项

1. **SSH密钥安全**：定期轮换SSH密钥
2. **网络安全**：确保NAS网络访问安全
3. **文件权限**：定期检查文件和目录权限
4. **日志审计**：定期审查同步日志

---

**注意**: 本文档基于Ubuntu 24.04系统编写，其他Linux发行版可能需要适当调整。