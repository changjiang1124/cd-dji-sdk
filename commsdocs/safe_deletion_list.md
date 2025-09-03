# 安全删除文件清单

> **生成时间**: 2025-01-25  
> **目的**: 提供经过验证的可安全删除的废弃脚本文件列表

## 立即可删除的文件 (无依赖风险)

### 1. 废弃的服务配置文件
```bash
# 项目内的服务文件 (已被替代)
rm /home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/media_sync_daemon.service

# 系统中的废弃服务文件 (需要root权限)
sudo rm /etc/systemd/system/media-sync-daemon.service
sudo systemctl daemon-reload
```

### 2. 废弃的安装/卸载脚本
```bash
# 旧版本的安装脚本 (已被新版本替代)
rm /home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/install_daemon.sh
rm /home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/uninstall_daemon.sh
```

## 需要谨慎处理的文件 (有依赖关系)

### 3. 核心废弃组件 (需要先处理依赖)

**注意**: 以下文件被其他文件引用，需要先处理依赖关系后再删除

#### 3.1 sync_scheduler.py
- **文件**: `celestial_nasops/sync_scheduler.py`
- **状态**: 已被 `media_finding_daemon.py` 替代
- **依赖**: 被 `test_sync.py` 引用
- **建议**: 先删除或更新测试文件，再删除此文件

#### 3.2 media_sync.py
- **文件**: `celestial_nasops/media_sync.py`
- **状态**: 已被 `media_finding_daemon.py` 替代
- **依赖**: 被多个测试文件引用
- **建议**: 先处理所有测试文件依赖

### 4. 废弃的测试文件

以下测试文件测试的是旧架构组件，可以删除:

```bash
# 测试旧架构的文件
rm /home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/test_sync.py
rm /home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/test_concurrency.py
rm /home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/test_storage_manager.py
rm /home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/test_safe_delete.py
```

## 推荐的删除顺序

### 阶段 1: 无风险删除
```bash
#!/bin/bash
# 删除废弃的服务配置文件
echo "删除废弃的服务配置文件..."
rm -f celestial_nasops/media_sync_daemon.service
echo "✅ 删除 media_sync_daemon.service"

# 删除废弃的安装脚本
echo "删除废弃的安装脚本..."
rm -f celestial_nasops/install_daemon.sh
rm -f celestial_nasops/uninstall_daemon.sh
echo "✅ 删除旧版安装/卸载脚本"

# 删除系统中的废弃服务 (需要root权限)
echo "删除系统中的废弃服务文件..."
sudo rm -f /etc/systemd/system/media-sync-daemon.service
sudo systemctl daemon-reload
echo "✅ 清理系统服务文件"
```

### 阶段 2: 删除废弃测试文件
```bash
#!/bin/bash
# 删除测试旧架构的文件
echo "删除废弃的测试文件..."
rm -f celestial_nasops/test_sync.py
rm -f celestial_nasops/test_concurrency.py
rm -f celestial_nasops/test_storage_manager.py
rm -f celestial_nasops/test_safe_delete.py
echo "✅ 删除废弃测试文件"
```

### 阶段 3: 删除核心废弃组件
```bash
#!/bin/bash
# 删除核心废弃文件 (确保没有依赖后执行)
echo "删除核心废弃组件..."
rm -f celestial_nasops/sync_scheduler.py
rm -f celestial_nasops/media_sync.py
echo "✅ 删除核心废弃组件"
```

## 验证清单

删除后需要验证以下内容:

### 1. 服务状态检查
```bash
# 确认当前活跃的服务
systemctl list-units --type=service --state=active | grep -E '(media|dock)'
# 预期结果: 只显示 dock-info-manager.service 和 media_finding_daemon.service
```

### 2. 功能验证
```bash
# 验证新架构服务正常运行
sudo systemctl status dock-info-manager
sudo systemctl status media_finding_daemon

# 检查日志无错误
sudo journalctl -u dock-info-manager --since "1 hour ago" --no-pager
sudo journalctl -u media_finding_daemon --since "1 hour ago" --no-pager
```

### 3. 文件系统检查
```bash
# 确认废弃文件已删除
find . -name "sync_scheduler.py" -o -name "media_sync.py" -o -name "*daemon.sh"
# 预期结果: 无输出或只显示新版本文件
```

## 回滚计划

如果删除后出现问题，可以通过以下方式回滚:

1. **Git回滚**: `git checkout HEAD~1 -- <deleted_files>`
2. **服务恢复**: 重新安装必要的服务文件
3. **功能测试**: 运行完整的系统测试

## 预期收益

删除这些废弃文件后:
- ✅ 减少代码库大小约 1000+ 行
- ✅ 消除架构混淆
- ✅ 简化维护工作
- ✅ 提高部署一致性
- ✅ 减少潜在的配置错误

---

**重要提醒**: 执行删除操作前，请确保:
1. 已创建完整的代码备份
2. 当前系统运行正常
3. 有回滚计划
4. 在测试环境中验证过删除操作