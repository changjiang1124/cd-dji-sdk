---
**Meta Information**
- 创建时间: 2025-01-25
- 更新时间: 2025-01-25
- 版本: 1.0
- 作者: AI Assistant
- 目标: 增强烟雾测试系统实施计划
---

# 增强烟雾测试系统实施计划

## 项目概述

基于现有的 `smoke_transfer_check.py` 脚本，开发一个增强的烟雾测试系统，用于全面测试 `media_finding_daemon` 的文件传输功能。该系统将提供详细的日志记录、实时监控、性能分析和自动化报告生成。

## 当前系统分析

### 现有 smoke_transfer_check.py 的优势
1. **完整的系统诊断**: 包含磁盘空间、网络连接、SSH连接、守护进程状态检查
2. **数据库集成**: 直接操作 SQLite 数据库，插入测试记录
3. **配置管理**: 使用统一配置文件 `unified_config.json`
4. **基础监控**: 轮询检查文件传输状态
5. **错误处理**: 基本的异常处理和故障排除提示

### 需要增强的方面
1. **实时监控**: 当前是轮询方式，需要实时状态变更监控
2. **详细日志**: 需要更结构化、更详细的日志记录
3. **性能监控**: 缺少传输速度、系统资源监控
4. **测试覆盖**: 需要更多测试场景和边界条件
5. **报告生成**: 需要更丰富的测试报告和分析

## 实施计划

### 阶段一: 核心架构重构 (预计 2-3 天)

#### 1.1 模块化重构
**目标**: 将现有代码重构为模块化架构

**任务清单**:
- [ ] 创建 `EnhancedSmokeTestManager` 主控制器类
- [ ] 提取 `DatabaseMonitor` 数据库监控模块
- [ ] 提取 `TestFileManager` 文件管理模块
- [ ] 提取 `SystemDiagnostics` 系统诊断模块
- [ ] 创建 `ConfigManager` 配置管理模块

**验收标准**:
- 所有现有功能保持不变
- 代码结构清晰，职责分离明确
- 单元测试覆盖率 > 80%
- 向后兼容现有命令行参数

#### 1.2 配置系统增强
**目标**: 扩展配置系统支持新功能

**配置增强项**:
```json
{
  "smoke_test": {
    "enabled": true,
    "log_level": "INFO",
    "log_file": "/var/log/celestial_nasops/smoke_test.log",
    "report_output_dir": "/var/log/celestial_nasops/reports",
    "test_scenarios": {
      "basic": {
        "file_sizes": [1024, 10240, 102400],
        "file_types": [".txt", ".jpg", ".mp4"],
        "max_wait_minutes": 10
      },
      "performance": {
        "file_sizes": [1048576, 10485760, 104857600],
        "concurrent_files": 3,
        "max_wait_minutes": 30
      }
    },
    "monitoring": {
      "status_check_interval": 1,
      "performance_sample_interval": 5,
      "timeout_minutes": 15
    },
    "cleanup": {
      "auto_cleanup": true,
      "keep_test_files_on_failure": true,
      "cleanup_delay_seconds": 30
    }
  }
}
```

**验收标准**:
- 配置文件向后兼容
- 新配置项有合理默认值
- 配置验证和错误提示完善

### 阶段二: 实时监控系统 (预计 2-3 天)

#### 2.1 数据库状态监控
**目标**: 实现实时数据库状态变更监控

**核心功能**:
- 实时监控 `media_transfer_status` 表变更
- 记录状态变更时间戳和详细信息
- 支持多文件并发监控
- 状态变更事件回调机制

**实现要点**:
```python
class DatabaseStatusMonitor:
    def start_monitoring(self, file_id: int, callback=None)
    def wait_for_status_change(self, file_id: int, target_status: str, timeout: int) -> bool
    def get_status_timeline(self, file_id: int) -> List[StatusChange]
    def stop_monitoring(self, file_id: int)
```

**验收标准**:
- 状态变更检测延迟 < 2秒
- 支持同时监控至少10个文件
- 内存使用稳定，无内存泄漏
- 异常情况下能正确恢复监控

#### 2.2 文件系统监控
**目标**: 监控本地和远程文件系统变化

**核心功能**:
- 监控本地媒体目录文件创建/删除
- 监控远程NAS目录文件出现
- 文件完整性验证 (SHA256)
- 传输进度跟踪

**验收标准**:
- 文件变化检测延迟 < 5秒
- 哈希验证准确率 100%
- 支持大文件 (>100MB) 监控
- 网络中断时能正确处理

### 阶段三: 性能监控系统 (预计 2 天)

#### 3.1 传输性能监控
**目标**: 详细监控文件传输性能指标

**监控指标**:
- 传输速度 (实时/平均/峰值)
- 传输延迟 (发现延迟/传输延迟)
- 传输成功率
- 错误重试次数

**实现要点**:
```python
class TransferPerformanceMonitor:
    def start_transfer_monitoring(self, file_id: int, file_size: int)
    def update_transfer_progress(self, file_id: int, bytes_transferred: int)
    def complete_transfer_monitoring(self, file_id: int)
    def get_performance_summary(self, file_id: int) -> PerformanceMetrics
```

**验收标准**:
- 性能数据采集精度 ±5%
- 支持并发传输性能监控
- 性能数据持久化存储
- 生成性能趋势图表

#### 3.2 系统资源监控
**目标**: 监控测试期间系统资源使用情况

**监控指标**:
- CPU使用率
- 内存使用率
- 磁盘I/O
- 网络I/O

**验收标准**:
- 资源监控开销 < 5% CPU
- 数据采样间隔可配置
- 异常资源使用告警
- 资源使用趋势分析

### 阶段四: 日志和报告系统 (预计 2 天)

#### 4.1 结构化日志系统
**目标**: 实现详细的结构化日志记录

**日志类型**:
- 测试事件日志 (开始/结束/阶段切换)
- 文件操作日志 (创建/传输/删除)
- 数据库操作日志 (插入/更新/查询)
- 守护进程事件日志 (发现/处理/完成)
- 性能指标日志 (速度/延迟/资源)
- 错误和异常日志

**日志格式**:
```json
{
  "timestamp": "2025-01-25T10:30:45.123Z",
  "level": "INFO",
  "event_type": "file_transfer_started",
  "file_id": 12345,
  "details": {
    "file_path": "/data/media/20250125_103045_test.mp4",
    "file_size": 1048576,
    "file_hash": "abc123...",
    "remote_path": "/nas/backup/20250125/103045_test.mp4"
  }
}
```

**验收标准**:
- 日志格式统一，易于解析
- 支持日志级别过滤
- 日志轮转和压缩
- 日志查询和分析工具

#### 4.2 测试报告生成
**目标**: 生成详细的测试报告和分析

**报告内容**:
- 测试摘要 (成功率/失败原因/耗时)
- 时间线分析 (关键事件时序图)
- 性能分析 (传输速度/资源使用)
- 错误分析 (错误分类/频率/解决建议)
- 系统健康状态
- 改进建议

**报告格式**:
- JSON格式 (机器可读)
- HTML格式 (人类可读，包含图表)
- 简化文本格式 (控制台输出)

**验收标准**:
- 报告生成时间 < 10秒
- 报告内容完整准确
- 支持历史报告对比
- 报告可视化效果良好

### 阶段五: 测试用例扩展 (预计 2 天)

#### 5.1 基础功能测试用例
**测试场景**:
- 单文件传输 (小/中/大文件)
- 多文件并发传输
- 不同文件类型传输
- 文件名特殊字符处理
- 目录结构创建

#### 5.2 异常处理测试用例
**测试场景**:
- 网络中断恢复
- 磁盘空间不足
- 权限问题
- 数据库锁定
- 守护进程重启
- 配置文件错误

#### 5.3 性能基准测试用例
**测试场景**:
- 传输速度基准测试
- 并发传输性能测试
- 大文件传输稳定性测试
- 长时间运行稳定性测试

**验收标准**:
- 测试用例覆盖率 > 90%
- 所有测试用例可自动化执行
- 测试结果可重现
- 性能基准数据建立

### 阶段六: 集成和优化 (预计 1-2 天)

#### 6.1 系统集成测试
**目标**: 确保所有模块协同工作

**集成测试项**:
- 端到端测试流程
- 模块间接口测试
- 配置兼容性测试
- 性能回归测试

#### 6.2 性能优化
**优化目标**:
- 减少系统资源占用
- 提高监控精度
- 优化报告生成速度
- 改善用户体验

**验收标准**:
- 系统整体稳定性 > 99%
- 性能指标达到预期
- 用户界面友好
- 文档完整准确

## 技术实现细节

### 1. 核心类设计

```python
# 主控制器
class EnhancedSmokeTestManager:
    def __init__(self, config_path: str)
    def run_smoke_test(self, scenario: str = 'basic') -> TestResult
    def run_custom_test(self, test_config: dict) -> TestResult
    def get_test_history(self) -> List[TestResult]

# 数据库监控
class DatabaseStatusMonitor:
    def start_monitoring(self, file_ids: List[int])
    def wait_for_status(self, file_id: int, status: str, timeout: int) -> bool
    def get_status_timeline(self, file_id: int) -> Timeline
    def stop_monitoring(self)

# 文件管理
class TestFileManager:
    def create_test_files(self, file_configs: List[dict]) -> List[TestFile]
    def insert_database_records(self, test_files: List[TestFile]) -> List[int]
    def verify_remote_files(self, file_ids: List[int]) -> List[bool]
    def cleanup_test_files(self, file_ids: List[int])

# 性能监控
class PerformanceMonitor:
    def start_monitoring(self, file_ids: List[int])
    def get_real_time_metrics(self) -> PerformanceMetrics
    def get_performance_summary(self) -> PerformanceSummary
    def stop_monitoring()

# 报告生成
class TestReportGenerator:
    def generate_json_report(self, test_result: TestResult) -> str
    def generate_html_report(self, test_result: TestResult) -> str
    def generate_console_summary(self, test_result: TestResult) -> str
```

### 2. 数据结构设计

```python
@dataclass
class TestFile:
    path: str
    size: int
    hash: str
    file_type: str
    created_at: datetime

@dataclass
class StatusChange:
    timestamp: datetime
    old_status: str
    new_status: str
    details: dict

@dataclass
class PerformanceMetrics:
    transfer_speed_mbps: float
    discovery_latency_seconds: float
    transfer_latency_seconds: float
    cpu_usage_percent: float
    memory_usage_percent: float

@dataclass
class TestResult:
    test_id: str
    start_time: datetime
    end_time: datetime
    scenario: str
    success: bool
    files_tested: int
    files_successful: int
    performance_metrics: PerformanceMetrics
    error_details: List[dict]
    timeline: List[StatusChange]
```

### 3. 配置文件扩展

在现有 `unified_config.json` 基础上添加:

```json
{
  "smoke_test": {
    "enabled": true,
    "scenarios": {
      "basic": {
        "description": "基础功能测试",
        "files": [
          {"size": 1024, "type": ".txt"},
          {"size": 10240, "type": ".jpg"},
          {"size": 102400, "type": ".mp4"}
        ],
        "timeout_minutes": 10
      },
      "performance": {
        "description": "性能基准测试",
        "files": [
          {"size": 1048576, "type": ".mp4"},
          {"size": 10485760, "type": ".mp4"},
          {"size": 104857600, "type": ".mp4"}
        ],
        "timeout_minutes": 30,
        "concurrent": true
      },
      "stress": {
        "description": "压力测试",
        "files": [
          {"size": 1048576, "type": ".mp4", "count": 10}
        ],
        "timeout_minutes": 60
      }
    },
    "monitoring": {
      "status_check_interval_seconds": 1,
      "performance_sample_interval_seconds": 5,
      "resource_monitoring_enabled": true
    },
    "logging": {
      "level": "INFO",
      "file": "/var/log/celestial_nasops/smoke_test.log",
      "max_size_mb": 100,
      "backup_count": 5,
      "structured_format": true
    },
    "reporting": {
      "output_directory": "/var/log/celestial_nasops/reports",
      "formats": ["json", "html", "console"],
      "include_charts": true,
      "auto_open_html": false
    },
    "cleanup": {
      "auto_cleanup_on_success": true,
      "keep_files_on_failure": true,
      "cleanup_delay_seconds": 30,
      "max_test_files_to_keep": 100
    }
  }
}
```

## 测试验收标准

### 功能验收标准

1. **基础功能**
   - [ ] 能够创建指定大小和类型的测试文件
   - [ ] 能够正确插入数据库记录
   - [ ] 能够监控守护进程处理过程
   - [ ] 能够验证远程文件传输结果
   - [ ] 能够自动清理测试文件

2. **监控功能**
   - [ ] 实时监控数据库状态变更 (延迟 < 2秒)
   - [ ] 准确记录状态变更时间线
   - [ ] 监控文件传输性能指标
   - [ ] 监控系统资源使用情况

3. **日志功能**
   - [ ] 生成结构化日志记录
   - [ ] 支持多种日志级别
   - [ ] 日志轮转和压缩正常
   - [ ] 日志内容完整准确

4. **报告功能**
   - [ ] 生成JSON格式测试报告
   - [ ] 生成HTML格式可视化报告
   - [ ] 控制台输出简洁摘要
   - [ ] 报告内容完整准确

### 性能验收标准

1. **响应性能**
   - 测试启动时间 < 5秒
   - 状态检查延迟 < 2秒
   - 报告生成时间 < 10秒

2. **资源使用**
   - CPU使用率 < 10% (空闲时)
   - 内存使用 < 100MB
   - 磁盘I/O合理

3. **稳定性**
   - 连续运行24小时无崩溃
   - 内存泄漏 < 1MB/小时
   - 异常恢复能力良好

### 兼容性验收标准

1. **向后兼容**
   - [ ] 现有命令行参数完全兼容
   - [ ] 现有配置文件格式兼容
   - [ ] 现有日志格式兼容

2. **系统兼容**
   - [ ] Ubuntu 20.04+ 系统支持
   - [ ] Python 3.8+ 版本支持
   - [ ] 现有依赖库兼容

## 风险评估和缓解措施

### 技术风险

1. **数据库并发访问风险**
   - **风险**: 多进程同时访问SQLite可能导致锁定
   - **缓解**: 实现连接池和重试机制
   - **监控**: 数据库锁定超时告警

2. **网络连接不稳定风险**
   - **风险**: SSH连接中断影响测试结果
   - **缓解**: 实现连接重试和状态恢复
   - **监控**: 网络连接质量监控

3. **大文件处理风险**
   - **风险**: 大文件传输可能导致内存不足
   - **缓解**: 流式处理和内存监控
   - **监控**: 内存使用告警

### 运维风险

1. **磁盘空间风险**
   - **风险**: 测试文件占用过多磁盘空间
   - **缓解**: 自动清理和空间监控
   - **监控**: 磁盘使用率告警

2. **日志文件过大风险**
   - **风险**: 详细日志可能快速增长
   - **缓解**: 日志轮转和压缩
   - **监控**: 日志文件大小监控

### 业务风险

1. **测试干扰生产风险**
   - **风险**: 测试可能影响生产环境
   - **缓解**: 独立测试环境和资源限制
   - **监控**: 生产系统性能监控

## 后续优化方向

### 短期优化 (1-2周)

1. **用户体验优化**
   - 添加进度条显示
   - 改善错误提示信息
   - 支持交互式配置

2. **监控精度提升**
   - 更精确的时间戳记录
   - 更详细的性能指标
   - 异常检测和告警

### 中期优化 (1-2月)

1. **智能化测试**
   - 自适应测试参数
   - 基于历史数据的预测
   - 异常模式识别

2. **集成化部署**
   - CI/CD集成
   - 自动化测试调度
   - 测试结果通知

### 长期优化 (3-6月)

1. **分布式测试**
   - 多节点协同测试
   - 负载均衡测试
   - 大规模性能测试

2. **机器学习优化**
   - 性能预测模型
   - 异常检测算法
   - 自动调优建议

## 总结

本实施计划提供了一个全面、系统的烟雾测试系统开发方案。通过分阶段实施，可以逐步构建一个功能完善、性能优异、易于维护的测试系统。

**关键成功因素**:
1. 严格按照阶段计划执行
2. 每个阶段都有明确的验收标准
3. 持续的测试和质量保证
4. 充分的文档和培训
5. 积极的用户反馈和迭代改进

通过这个增强的烟雾测试系统，可以显著提高 `media_finding_daemon` 的质量保证水平，确保媒体文件传输系统的稳定可靠运行。