# Stage 5 — 可观测性和运维手册

## 系统监控指标

### 核心业务指标

#### 文件传输指标
```python
# 关键指标定义
FILE_TRANSFER_METRICS = {
    'transfer_success_rate': {
        'description': '文件传输成功率',
        'formula': 'completed_files / total_files * 100',
        'threshold': {
            'warning': '< 95%',
            'critical': '< 90%'
        },
        'collection_interval': '1m'
    },
    'transfer_throughput': {
        'description': '传输吞吐量 (MB/s)',
        'formula': 'sum(file_size) / sum(transfer_time)',
        'threshold': {
            'warning': '< 10 MB/s',
            'critical': '< 5 MB/s'
        },
        'collection_interval': '1m'
    },
    'queue_length': {
        'description': '待传输队列长度',
        'formula': 'count(status=PENDING)',
        'threshold': {
            'warning': '> 100',
            'critical': '> 500'
        },
        'collection_interval': '30s'
    },
    'average_transfer_time': {
        'description': '平均传输时间 (秒)',
        'formula': 'avg(transfer_duration)',
        'threshold': {
            'warning': '> 300s (5min)',
            'critical': '> 600s (10min)'
        },
        'collection_interval': '5m'
    }
}
```

#### 系统健康指标
```python
SYSTEM_HEALTH_METRICS = {
    'daemon_uptime': {
        'description': '守护进程运行时间',
        'unit': 'seconds',
        'threshold': {
            'critical': '< 60s (频繁重启)'
        }
    },
    'database_connection_pool': {
        'description': '数据库连接池状态',
        'metrics': ['active_connections', 'idle_connections', 'failed_connections'],
        'threshold': {
            'warning': 'failed_connections > 5',
            'critical': 'active_connections = 0'
        }
    },
    'ssh_connection_health': {
        'description': 'SSH连接健康状态',
        'metrics': ['connection_success_rate', 'connection_latency'],
        'threshold': {
            'warning': 'success_rate < 95% OR latency > 5s',
            'critical': 'success_rate < 80% OR latency > 10s'
        }
    },
    'lock_contention': {
        'description': '锁竞争情况',
        'metrics': ['lock_wait_time', 'lock_timeout_count'],
        'threshold': {
            'warning': 'avg_wait_time > 5s',
            'critical': 'timeout_count > 10/hour'
        }
    }
}
```

### 资源使用指标

#### 存储指标
```python
STORAGE_METRICS = {
    'local_disk_usage': {
        'description': '本地磁盘使用率',
        'paths': ['/home/celestial/dev/esdk-test/Edge-SDK/celestial_works/media'],
        'threshold': {
            'warning': '> 80%',
            'critical': '> 90%'
        }
    },
    'nas_storage_usage': {
        'description': 'NAS存储使用率',
        'host': '192.168.200.103',
        'threshold': {
            'warning': '> 80%',
            'critical': '> 90%'
        }
    },
    'database_size': {
        'description': '数据库文件大小',
        'path': '/path/to/media_status.db',
        'threshold': {
            'warning': '> 1GB',
            'critical': '> 5GB'
        }
    },
    'log_file_size': {
        'description': '日志文件大小',
        'paths': ['/path/to/logs/*.log'],
        'threshold': {
            'warning': '> 100MB',
            'critical': '> 500MB'
        }
    }
}
```

#### 系统资源指标
```python
SYSTEM_RESOURCE_METRICS = {
    'cpu_usage': {
        'description': 'CPU使用率',
        'threshold': {
            'warning': '> 70%',
            'critical': '> 90%'
        }
    },
    'memory_usage': {
        'description': '内存使用率',
        'threshold': {
            'warning': '> 80%',
            'critical': '> 95%'
        }
    },
    'network_bandwidth': {
        'description': '网络带宽使用',
        'metrics': ['upload_speed', 'download_speed'],
        'threshold': {
            'warning': 'upload_speed < 10MB/s',
            'critical': 'upload_speed < 1MB/s'
        }
    },
    'file_descriptor_usage': {
        'description': '文件描述符使用',
        'threshold': {
            'warning': '> 80% of limit',
            'critical': '> 95% of limit'
        }
    }
}
```

## 日志管理策略

### 日志分级和格式

```python
# 日志配置示例
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'detailed': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
        'simple': {
            'format': '%(asctime)s - %(levelname)s - %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
        'json': {
            'format': '%(message)s',
            'class': 'pythonjsonlogger.jsonlogger.JsonFormatter'
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'INFO',
            'formatter': 'simple',
            'stream': 'ext://sys.stdout'
        },
        'file_debug': {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': 'DEBUG',
            'formatter': 'detailed',
            'filename': '/var/log/celestial_nasops/debug.log',
            'maxBytes': 50 * 1024 * 1024,  # 50MB
            'backupCount': 5
        },
        'file_error': {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': 'ERROR',
            'formatter': 'detailed',
            'filename': '/var/log/celestial_nasops/error.log',
            'maxBytes': 10 * 1024 * 1024,  # 10MB
            'backupCount': 10
        },
        'file_audit': {
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'level': 'INFO',
            'formatter': 'json',
            'filename': '/var/log/celestial_nasops/audit.log',
            'when': 'midnight',
            'interval': 1,
            'backupCount': 30
        }
    },
    'loggers': {
        'celestial_nasops': {
            'level': 'DEBUG',
            'handlers': ['console', 'file_debug', 'file_error'],
            'propagate': False
        },
        'celestial_nasops.audit': {
            'level': 'INFO',
            'handlers': ['file_audit'],
            'propagate': False
        }
    }
}
```

### 关键日志事件

```python
# 审计日志事件定义
AUDIT_EVENTS = {
    'FILE_DISCOVERED': {
        'level': 'INFO',
        'message': 'File discovered and registered',
        'fields': ['filename', 'filepath', 'file_size', 'file_hash']
    },
    'TRANSFER_STARTED': {
        'level': 'INFO',
        'message': 'File transfer started',
        'fields': ['filename', 'file_size', 'destination']
    },
    'TRANSFER_COMPLETED': {
        'level': 'INFO',
        'message': 'File transfer completed successfully',
        'fields': ['filename', 'file_size', 'transfer_time', 'transfer_speed']
    },
    'TRANSFER_FAILED': {
        'level': 'ERROR',
        'message': 'File transfer failed',
        'fields': ['filename', 'error_code', 'error_message', 'retry_count']
    },
    'STORAGE_WARNING': {
        'level': 'WARNING',
        'message': 'Storage usage warning threshold reached',
        'fields': ['storage_type', 'usage_percentage', 'available_space']
    },
    'SYSTEM_ERROR': {
        'level': 'ERROR',
        'message': 'System error occurred',
        'fields': ['component', 'error_type', 'error_details', 'stack_trace']
    }
}
```

### 日志轮转配置

```bash
# /etc/logrotate.d/celestial_nasops
/var/log/celestial_nasops/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 celestial celestial
    postrotate
        /bin/kill -HUP `cat /var/run/celestial_nasops.pid 2> /dev/null` 2> /dev/null || true
    endscript
}

/var/log/celestial_nasops/audit.log {
    daily
    missingok
    rotate 365
    compress
    delaycompress
    notifempty
    create 644 celestial celestial
    # 审计日志不发送信号，避免中断
}
```

## 分布式追踪

### 追踪实现

```python
# 分布式追踪装饰器
import uuid
import time
from functools import wraps
from typing import Dict, Any

class TraceContext:
    def __init__(self, trace_id: str = None, span_id: str = None, parent_span_id: str = None):
        self.trace_id = trace_id or str(uuid.uuid4())
        self.span_id = span_id or str(uuid.uuid4())
        self.parent_span_id = parent_span_id
        self.start_time = time.time()
        self.tags = {}
        self.logs = []
    
    def add_tag(self, key: str, value: Any):
        self.tags[key] = value
    
    def add_log(self, message: str, level: str = 'INFO'):
        self.logs.append({
            'timestamp': time.time(),
            'level': level,
            'message': message
        })
    
    def finish(self):
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time

def trace_operation(operation_name: str):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 创建新的span
            trace_ctx = TraceContext()
            trace_ctx.add_tag('operation', operation_name)
            trace_ctx.add_tag('function', func.__name__)
            
            try:
                trace_ctx.add_log(f'Starting {operation_name}')
                result = func(*args, **kwargs)
                trace_ctx.add_tag('status', 'success')
                trace_ctx.add_log(f'Completed {operation_name}')
                return result
            except Exception as e:
                trace_ctx.add_tag('status', 'error')
                trace_ctx.add_tag('error', str(e))
                trace_ctx.add_log(f'Error in {operation_name}: {str(e)}', 'ERROR')
                raise
            finally:
                trace_ctx.finish()
                # 发送追踪数据到收集器
                send_trace_data(trace_ctx)
        
        return wrapper
    return decorator

# 使用示例
@trace_operation('file_transfer')
def transfer_file(self, file_info):
    # 文件传输逻辑
    pass
```

### 追踪数据收集

```python
# 追踪数据收集器
import json
from datetime import datetime

class TraceCollector:
    def __init__(self, output_file: str = '/var/log/celestial_nasops/traces.jsonl'):
        self.output_file = output_file
    
    def collect_trace(self, trace_ctx: TraceContext):
        trace_data = {
            'trace_id': trace_ctx.trace_id,
            'span_id': trace_ctx.span_id,
            'parent_span_id': trace_ctx.parent_span_id,
            'start_time': trace_ctx.start_time,
            'end_time': trace_ctx.end_time,
            'duration': trace_ctx.duration,
            'tags': trace_ctx.tags,
            'logs': trace_ctx.logs,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        with open(self.output_file, 'a') as f:
            f.write(json.dumps(trace_data) + '\n')

def send_trace_data(trace_ctx: TraceContext):
    collector = TraceCollector()
    collector.collect_trace(trace_ctx)
```

## 告警系统

### 告警规则定义

```python
# 告警规则配置
ALERT_RULES = {
    'high_transfer_failure_rate': {
        'condition': 'transfer_failure_rate > 10% for 5 minutes',
        'severity': 'critical',
        'description': '文件传输失败率过高',
        'actions': ['email', 'sms', 'webhook'],
        'recipients': ['admin@company.com', 'ops-team@company.com']
    },
    'storage_space_critical': {
        'condition': 'storage_usage > 90%',
        'severity': 'critical',
        'description': '存储空间严重不足',
        'actions': ['email', 'sms', 'auto_cleanup'],
        'recipients': ['admin@company.com']
    },
    'daemon_process_down': {
        'condition': 'daemon_uptime < 60 seconds',
        'severity': 'critical',
        'description': '守护进程异常重启',
        'actions': ['email', 'restart_service'],
        'recipients': ['ops-team@company.com']
    },
    'network_connectivity_issue': {
        'condition': 'ssh_connection_success_rate < 80% for 3 minutes',
        'severity': 'warning',
        'description': 'NAS网络连接不稳定',
        'actions': ['email'],
        'recipients': ['network-team@company.com']
    },
    'large_file_transfer_timeout': {
        'condition': 'transfer_time > 1800 seconds for files > 10GB',
        'severity': 'warning',
        'description': '大文件传输超时',
        'actions': ['email', 'log_analysis'],
        'recipients': ['dev-team@company.com']
    }
}
```

### 告警实现

```python
# 告警管理器
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

class AlertManager:
    def __init__(self, config: dict):
        self.config = config
        self.alert_history = {}
    
    def check_alert_conditions(self, metrics: dict):
        """检查告警条件"""
        for rule_name, rule in ALERT_RULES.items():
            if self._evaluate_condition(rule['condition'], metrics):
                if not self._is_alert_suppressed(rule_name):
                    self._trigger_alert(rule_name, rule, metrics)
    
    def _evaluate_condition(self, condition: str, metrics: dict) -> bool:
        """评估告警条件"""
        # 简化的条件评估逻辑
        # 实际实现需要更复杂的表达式解析
        if 'transfer_failure_rate > 10%' in condition:
            return metrics.get('transfer_failure_rate', 0) > 10
        elif 'storage_usage > 90%' in condition:
            return metrics.get('storage_usage', 0) > 90
        # ... 其他条件
        return False
    
    def _is_alert_suppressed(self, rule_name: str) -> bool:
        """检查告警是否被抑制"""
        # 实现告警抑制逻辑，避免重复告警
        last_alert_time = self.alert_history.get(rule_name, 0)
        current_time = time.time()
        suppression_period = 300  # 5分钟抑制期
        
        return (current_time - last_alert_time) < suppression_period
    
    def _trigger_alert(self, rule_name: str, rule: dict, metrics: dict):
        """触发告警"""
        alert_data = {
            'rule_name': rule_name,
            'severity': rule['severity'],
            'description': rule['description'],
            'metrics': metrics,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        for action in rule['actions']:
            if action == 'email':
                self._send_email_alert(alert_data, rule['recipients'])
            elif action == 'webhook':
                self._send_webhook_alert(alert_data)
            elif action == 'auto_cleanup':
                self._trigger_auto_cleanup()
        
        self.alert_history[rule_name] = time.time()
    
    def _send_email_alert(self, alert_data: dict, recipients: list):
        """发送邮件告警"""
        msg = MIMEMultipart()
        msg['From'] = self.config['smtp']['from']
        msg['To'] = ', '.join(recipients)
        msg['Subject'] = f"[{alert_data['severity'].upper()}] {alert_data['description']}"
        
        body = f"""
        告警详情：
        规则名称: {alert_data['rule_name']}
        严重程度: {alert_data['severity']}
        描述: {alert_data['description']}
        时间: {alert_data['timestamp']}
        
        相关指标:
        {json.dumps(alert_data['metrics'], indent=2)}
        """
        
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        try:
            server = smtplib.SMTP(self.config['smtp']['host'], self.config['smtp']['port'])
            server.starttls()
            server.login(self.config['smtp']['username'], self.config['smtp']['password'])
            server.send_message(msg)
            server.quit()
        except Exception as e:
            print(f"Failed to send email alert: {e}")
    
    def _send_webhook_alert(self, alert_data: dict):
        """发送Webhook告警"""
        webhook_url = self.config.get('webhook_url')
        if webhook_url:
            try:
                response = requests.post(webhook_url, json=alert_data, timeout=10)
                response.raise_for_status()
            except Exception as e:
                print(f"Failed to send webhook alert: {e}")
```

## 金丝雀部署和回滚策略

### 金丝雀部署流程

```python
# 金丝雀部署管理器
class CanaryDeployment:
    def __init__(self, config: dict):
        self.config = config
        self.canary_percentage = 0
        self.health_checks = []
        self.rollback_triggers = []
    
    def start_canary_deployment(self, new_version: str):
        """开始金丝雀部署"""
        deployment_plan = {
            'phases': [
                {'percentage': 5, 'duration': 300},   # 5% 流量，5分钟
                {'percentage': 25, 'duration': 600},  # 25% 流量，10分钟
                {'percentage': 50, 'duration': 900},  # 50% 流量，15分钟
                {'percentage': 100, 'duration': 0}    # 100% 流量
            ]
        }
        
        for phase in deployment_plan['phases']:
            if not self._execute_canary_phase(new_version, phase):
                self._rollback_deployment()
                return False
        
        return True
    
    def _execute_canary_phase(self, version: str, phase: dict) -> bool:
        """执行金丝雀部署阶段"""
        percentage = phase['percentage']
        duration = phase['duration']
        
        # 更新流量分配
        self._update_traffic_split(percentage)
        
        # 等待指定时间
        time.sleep(duration)
        
        # 检查健康状态
        return self._check_canary_health()
    
    def _check_canary_health(self) -> bool:
        """检查金丝雀版本健康状态"""
        health_metrics = {
            'error_rate': self._get_error_rate(),
            'response_time': self._get_response_time(),
            'throughput': self._get_throughput()
        }
        
        # 健康检查阈值
        thresholds = {
            'error_rate': 5.0,      # 错误率 < 5%
            'response_time': 2000,   # 响应时间 < 2秒
            'throughput': 0.8        # 吞吐量 > 80% 基线
        }
        
        for metric, value in health_metrics.items():
            if metric == 'error_rate' and value > thresholds[metric]:
                return False
            elif metric == 'response_time' and value > thresholds[metric]:
                return False
            elif metric == 'throughput' and value < thresholds[metric]:
                return False
        
        return True
    
    def _rollback_deployment(self):
        """回滚部署"""
        # 立即将流量切回到稳定版本
        self._update_traffic_split(0)
        
        # 发送回滚告警
        alert_data = {
            'type': 'deployment_rollback',
            'reason': 'Health check failed during canary deployment',
            'timestamp': datetime.utcnow().isoformat()
        }
        
        self._send_rollback_alert(alert_data)
```

### 自动回滚触发器

```python
# 回滚触发器配置
ROLLBACK_TRIGGERS = {
    'high_error_rate': {
        'condition': 'error_rate > 5% for 2 minutes',
        'action': 'immediate_rollback'
    },
    'performance_degradation': {
        'condition': 'avg_response_time > 200% baseline for 3 minutes',
        'action': 'immediate_rollback'
    },
    'memory_leak': {
        'condition': 'memory_usage increases > 50% in 10 minutes',
        'action': 'gradual_rollback'
    },
    'database_errors': {
        'condition': 'database_connection_errors > 10 in 1 minute',
        'action': 'immediate_rollback'
    }
}
```

## 容量规划和性能预算

### 性能预算定义

```python
# 性能预算配置
PERFORMANCE_BUDGETS = {
    'file_transfer': {
        'small_files': {
            'size_range': '< 10MB',
            'max_transfer_time': 30,      # 秒
            'min_throughput': 5,          # MB/s
            'max_queue_time': 60          # 秒
        },
        'medium_files': {
            'size_range': '10MB - 1GB',
            'max_transfer_time': 300,     # 5分钟
            'min_throughput': 20,         # MB/s
            'max_queue_time': 300         # 5分钟
        },
        'large_files': {
            'size_range': '> 1GB',
            'max_transfer_time': 3600,    # 1小时
            'min_throughput': 50,         # MB/s
            'max_queue_time': 1800        # 30分钟
        }
    },
    'system_resources': {
        'cpu_usage': {
            'normal_load': 30,            # 正常负载 < 30%
            'peak_load': 70,              # 峰值负载 < 70%
            'critical_load': 90           # 临界负载 < 90%
        },
        'memory_usage': {
            'normal_load': 50,            # 正常负载 < 50%
            'peak_load': 80,              # 峰值负载 < 80%
            'critical_load': 95           # 临界负载 < 95%
        },
        'disk_io': {
            'max_iops': 1000,             # 最大IOPS
            'max_bandwidth': 100          # 最大带宽 MB/s
        }
    },
    'scalability': {
        'concurrent_transfers': {
            'current_limit': 10,
            'target_limit': 50,
            'max_limit': 100
        },
        'file_queue_size': {
            'normal_size': 100,
            'warning_size': 500,
            'critical_size': 1000
        }
    }
}
```

### 容量规划模型

```python
# 容量规划计算器
class CapacityPlanner:
    def __init__(self, historical_data: dict):
        self.historical_data = historical_data
    
    def predict_storage_needs(self, days_ahead: int = 30) -> dict:
        """预测存储需求"""
        daily_growth = self._calculate_daily_growth()
        current_usage = self._get_current_storage_usage()
        
        predicted_usage = current_usage + (daily_growth * days_ahead)
        
        return {
            'current_usage_gb': current_usage,
            'daily_growth_gb': daily_growth,
            'predicted_usage_gb': predicted_usage,
            'days_until_full': self._calculate_days_until_full(current_usage, daily_growth),
            'recommended_cleanup_gb': max(0, predicted_usage - (self._get_total_capacity() * 0.8))
        }
    
    def predict_transfer_load(self, days_ahead: int = 7) -> dict:
        """预测传输负载"""
        historical_transfers = self.historical_data['daily_transfers']
        avg_daily_transfers = sum(historical_transfers) / len(historical_transfers)
        
        # 考虑增长趋势
        growth_rate = self._calculate_growth_rate(historical_transfers)
        predicted_daily_transfers = avg_daily_transfers * (1 + growth_rate) ** days_ahead
        
        return {
            'current_avg_daily_transfers': avg_daily_transfers,
            'predicted_daily_transfers': predicted_daily_transfers,
            'peak_hour_multiplier': 3.0,  # 峰值时段是平均值的3倍
            'recommended_concurrent_limit': min(50, int(predicted_daily_transfers / 24 * 3))
        }
    
    def _calculate_daily_growth(self) -> float:
        """计算日均存储增长"""
        storage_history = self.historical_data['daily_storage_usage']
        if len(storage_history) < 2:
            return 0
        
        growth_rates = []
        for i in range(1, len(storage_history)):
            growth = storage_history[i] - storage_history[i-1]
            growth_rates.append(growth)
        
        return sum(growth_rates) / len(growth_rates)
```

## 运维手册和故障排除

### 常见故障排除指南

#### 1. 文件传输失败

**症状**：
- 文件状态长时间停留在DOWNLOADING
- 传输错误日志增多
- 传输成功率下降

**排查步骤**：
```bash
# 1. 检查网络连接
ssh nas-edge 'echo "Connection OK"'

# 2. 检查NAS存储空间
ssh nas-edge 'df -h'

# 3. 检查传输日志
tail -f /var/log/celestial_nasops/transfer.log

# 4. 检查进程状态
ps aux | grep media_finding_daemon

# 5. 检查数据库状态
sqlite3 /path/to/media_status.db "SELECT status, COUNT(*) FROM media_files GROUP BY status;"
```

**解决方案**：
- 网络问题：重启网络服务或联系网络管理员
- 存储满：执行清理脚本或扩容
- 进程异常：重启守护进程
- 数据库锁：重启服务或手动解锁

#### 2. 系统性能问题

**症状**：
- CPU或内存使用率持续高企
- 传输速度明显下降
- 系统响应缓慢

**排查步骤**：
```bash
# 1. 检查系统资源
htop
iotop
netstat -i

# 2. 检查进程资源使用
ps aux --sort=-%cpu | head -10
ps aux --sort=-%mem | head -10

# 3. 检查磁盘IO
iostat -x 1 5

# 4. 检查网络状态
ss -tuln
ping 192.168.200.103
```

**解决方案**：
- CPU高：优化算法或增加并发限制
- 内存高：检查内存泄漏或重启服务
- 磁盘IO高：优化文件操作或使用SSD
- 网络问题：检查网络配置或带宽

#### 3. 数据库问题

**症状**：
- 数据库操作超时
- 数据不一致
- 数据库文件损坏

**排查步骤**：
```bash
# 1. 检查数据库文件
ls -la /path/to/media_status.db
file /path/to/media_status.db

# 2. 检查数据库完整性
sqlite3 /path/to/media_status.db "PRAGMA integrity_check;"

# 3. 检查数据库锁
lsof /path/to/media_status.db

# 4. 备份和恢复测试
cp /path/to/media_status.db /tmp/backup.db
sqlite3 /tmp/backup.db ".dump" > /tmp/dump.sql
```

**解决方案**：
- 锁死：重启相关进程
- 损坏：从备份恢复或重建
- 性能问题：优化查询或重建索引

### 维护脚本

```bash
#!/bin/bash
# maintenance.sh - 系统维护脚本

set -e

LOG_FILE="/var/log/celestial_nasops/maintenance.log"
DATE=$(date '+%Y-%m-%d %H:%M:%S')

log() {
    echo "[$DATE] $1" | tee -a "$LOG_FILE"
}

# 1. 检查系统健康状态
check_system_health() {
    log "开始系统健康检查"
    
    # 检查磁盘空间
    DISK_USAGE=$(df /home/celestial/dev/esdk-test/Edge-SDK | tail -1 | awk '{print $5}' | sed 's/%//')
    if [ "$DISK_USAGE" -gt 80 ]; then
        log "警告：磁盘使用率 ${DISK_USAGE}%"
    fi
    
    # 检查内存使用
    MEM_USAGE=$(free | grep Mem | awk '{printf "%.0f", $3/$2 * 100.0}')
    if [ "$MEM_USAGE" -gt 80 ]; then
        log "警告：内存使用率 ${MEM_USAGE}%"
    fi
    
    # 检查进程状态
    if ! pgrep -f "media_finding_daemon" > /dev/null; then
        log "错误：守护进程未运行"
        return 1
    fi
    
    log "系统健康检查完成"
}

# 2. 清理临时文件
cleanup_temp_files() {
    log "开始清理临时文件"
    
    # 清理7天前的日志文件
    find /var/log/celestial_nasops -name "*.log.*" -mtime +7 -delete
    
    # 清理临时传输文件
    find /tmp -name "transfer_*" -mtime +1 -delete
    
    # 清理数据库临时文件
    find /path/to/db -name "*.db-*" -mtime +1 -delete
    
    log "临时文件清理完成"
}

# 3. 数据库维护
maintain_database() {
    log "开始数据库维护"
    
    DB_PATH="/path/to/media_status.db"
    
    # 数据库完整性检查
    if ! sqlite3 "$DB_PATH" "PRAGMA integrity_check;" | grep -q "ok"; then
        log "错误：数据库完整性检查失败"
        return 1
    fi
    
    # 数据库优化
    sqlite3 "$DB_PATH" "VACUUM;"
    sqlite3 "$DB_PATH" "ANALYZE;"
    
    # 清理30天前的已完成记录
    sqlite3 "$DB_PATH" "DELETE FROM media_files WHERE status='COMPLETED' AND created_at < datetime('now', '-30 days');"
    
    log "数据库维护完成"
}

# 4. 性能监控
performance_monitoring() {
    log "开始性能监控"
    
    # 记录系统指标
    {
        echo "=== $(date) ==="
        echo "CPU使用率: $(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | sed 's/%us,//')"
        echo "内存使用率: $(free | grep Mem | awk '{printf "%.1f%%", $3/$2 * 100.0}')"
        echo "磁盘使用率: $(df /home/celestial/dev/esdk-test/Edge-SDK | tail -1 | awk '{print $5}')"
        echo "网络连接数: $(ss -t | wc -l)"
    } >> /var/log/celestial_nasops/performance.log
    
    log "性能监控完成"
}

# 主函数
main() {
    log "开始系统维护"
    
    check_system_health || exit 1
    cleanup_temp_files
    maintain_database || exit 1
    performance_monitoring
    
    log "系统维护完成"
}

# 执行维护
main "$@"
```

### 监控仪表板配置

```yaml
# grafana-dashboard.json (简化版)
{
  "dashboard": {
    "title": "Celestial NAS Operations Dashboard",
    "panels": [
      {
        "title": "文件传输成功率",
        "type": "stat",
        "targets": [
          {
            "expr": "rate(transfer_success_total[5m]) / rate(transfer_total[5m]) * 100"
          }
        ],
        "thresholds": [
          {"color": "red", "value": 90},
          {"color": "yellow", "value": 95},
          {"color": "green", "value": 98}
        ]
      },
      {
        "title": "传输队列长度",
        "type": "graph",
        "targets": [
          {
            "expr": "transfer_queue_length"
          }
        ]
      },
      {
        "title": "存储使用率",
        "type": "gauge",
        "targets": [
          {
            "expr": "storage_usage_percentage"
          }
        ],
        "thresholds": [
          {"color": "green", "value": 0},
          {"color": "yellow", "value": 80},
          {"color": "red", "value": 90}
        ]
      },
      {
        "title": "系统资源使用",
        "type": "graph",
        "targets": [
          {"expr": "cpu_usage_percentage", "legendFormat": "CPU"},
          {"expr": "memory_usage_percentage", "legendFormat": "Memory"}
        ]
      }
    ]
  }
}
```

---

## 总结

本可观测性和运维手册提供了完整的系统监控、告警、部署和维护策略。关键要点包括：

1. **全面监控**：覆盖业务指标、系统资源和网络状态
2. **智能告警**：基于阈值的多级告警机制
3. **安全部署**：金丝雀部署和自动回滚保障
4. **容量规划**：基于历史数据的预测性维护
5. **故障排除**：标准化的问题诊断和解决流程

通过实施这些策略，可以确保媒体文件同步系统的高可用性、高性能和可维护性。