# Stage 4 — 自动化和环境策略

## 测试自动化策略

### 测试金字塔分层

```
           E2E Tests (10%)
         ┌─────────────────┐
        │  端到端集成测试    │
       └─────────────────┘
      
        API Tests (30%)
    ┌─────────────────────┐
   │   API/服务层测试      │
  └─────────────────────┘
  
     Unit Tests (60%)
 ┌─────────────────────────┐
│      单元测试层          │
└─────────────────────────┘
```

### 单元测试 (Unit Tests) - 60%

**覆盖范围**：
- 核心业务逻辑
- 数据处理算法
- 工具函数
- 配置解析
- 错误处理

**自动化工具**：
- **框架**: pytest
- **覆盖率**: pytest-cov
- **模拟**: unittest.mock
- **参数化**: pytest.mark.parametrize

**实施策略**：
```python
# 单元测试示例结构
test/unit/
├── test_media_finding_daemon.py
├── test_media_status_db.py
├── test_storage_manager.py
├── test_sync_lock_manager.py
├── test_config_manager.py
└── test_utils.py
```

**关键测试用例**：
- TC003: 大文件哈希计算
- TC004: 重复文件检测
- TC007: 空文件处理
- TC013: 数据库锁定
- TC017: 并发文件扫描
- TC018: 数据库并发写入
- TC022: 数据库损坏恢复
- TC023: 配置文件损坏
- TC027: 哈希计算性能
- TC029: 数据库查询性能

### API/服务层测试 (API Tests) - 30%

**覆盖范围**：
- 服务间集成
- 数据库操作
- 文件系统操作
- 网络通信
- 外部依赖

**自动化工具**：
- **框架**: pytest + requests
- **数据库**: pytest-postgresql (测试数据库)
- **文件系统**: tempfile, shutil
- **网络模拟**: responses, httpretty

**实施策略**：
```python
# API测试示例结构
test/api/
├── test_file_discovery_api.py
├── test_transfer_api.py
├── test_storage_api.py
├── test_lock_api.py
└── conftest.py  # 共享fixtures
```

**关键测试用例**：
- TC001: 正常文件发现和注册
- TC002: 小文件传输流程
- TC005: 存储空间检查
- TC008: 文件名特殊字符
- TC009: 存储空间满
- TC010: 最大并发传输
- TC012: SSH连接失败
- TC014: 源文件被删除
- TC015: 磁盘空间不足
- TC020: 传输状态竞争
- TC025: 传输中断恢复
- TC026: 大量小文件处理

### 端到端测试 (E2E Tests) - 10%

**覆盖范围**：
- 完整业务流程
- 系统集成
- 用户场景
- 关键路径

**自动化工具**：
- **框架**: pytest + docker-compose
- **容器化**: Docker
- **编排**: docker-compose
- **监控**: pytest-html (报告)

**实施策略**：
```python
# E2E测试示例结构
test/e2e/
├── test_full_sync_workflow.py
├── test_disaster_recovery.py
├── test_performance_scenarios.py
├── docker-compose.test.yml
└── fixtures/
    ├── test_files/
    └── test_configs/
```

**关键测试用例**：
- TC006: 超大文件传输(30GB)
- TC011: 网络中断恢复
- TC016: 多进程启动冲突
- TC021: 系统断电重启恢复
- TC028: 内存使用监控
- TC030: 网络传输效率

## CI/CD 集成策略

### GitHub Actions 工作流

```yaml
# .github/workflows/test.yml
name: Automated Testing

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements-test.txt
      - name: Run unit tests
        run: |
          pytest test/unit/ -v --cov=celestial_nasops --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v3

  api-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:13
        env:
          POSTGRES_PASSWORD: test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements-test.txt
      - name: Run API tests
        run: |
          pytest test/api/ -v

  e2e-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v2
      - name: Run E2E tests
        run: |
          docker-compose -f test/e2e/docker-compose.test.yml up --build --abort-on-container-exit
      - name: Cleanup
        run: |
          docker-compose -f test/e2e/docker-compose.test.yml down -v
```

### 测试门禁策略

**提交前检查**：
- 单元测试覆盖率 ≥ 80%
- 所有单元测试通过
- 代码风格检查通过 (flake8, black)
- 类型检查通过 (mypy)

**合并前检查**：
- 所有单元测试通过
- 关键API测试通过
- 代码审查完成
- 文档更新完成

**发布前检查**：
- 所有测试层级通过
- 性能基准测试通过
- 安全扫描通过
- 集成测试通过

## 测试环境配置

### 开发环境 (Development)

**目的**：开发人员本地测试

**配置**：
```yaml
# docker-compose.dev.yml
version: '3.8'
services:
  app:
    build: .
    volumes:
      - .:/app
      - ./test/fixtures:/test_data
    environment:
      - ENV=development
      - LOG_LEVEL=DEBUG
    ports:
      - "8000:8000"
  
  test-db:
    image: sqlite:latest
    volumes:
      - ./test/data:/data
  
  mock-nas:
    image: atmoz/sftp
    ports:
      - "2222:22"
    command: edge_sync:password:1001
```

**特点**：
- 快速启动
- 实时代码重载
- 详细日志输出
- 模拟外部依赖

### 测试环境 (Testing)

**目的**：自动化测试执行

**配置**：
```yaml
# docker-compose.test.yml
version: '3.8'
services:
  test-runner:
    build:
      context: .
      dockerfile: Dockerfile.test
    volumes:
      - ./test:/app/test
      - test-data:/test_data
    environment:
      - ENV=testing
      - PYTHONPATH=/app
    depends_on:
      - test-db
      - mock-nas
    command: pytest test/ -v --junitxml=test-results.xml
  
  test-db:
    image: postgres:13
    environment:
      POSTGRES_DB: test_db
      POSTGRES_USER: test_user
      POSTGRES_PASSWORD: test_pass
    tmpfs:
      - /var/lib/postgresql/data
  
  mock-nas:
    image: atmoz/sftp
    command: edge_sync:password:1001
    tmpfs:
      - /home/edge_sync/upload

volumes:
  test-data:
```

**特点**：
- 隔离环境
- 可重复执行
- 并行测试支持
- 临时数据存储

### 集成环境 (Integration)

**目的**：集成测试和性能测试

**配置**：
```yaml
# docker-compose.integration.yml
version: '3.8'
services:
  app:
    build: .
    environment:
      - ENV=integration
      - NAS_HOST=real-nas
      - DB_HOST=integration-db
    depends_on:
      - integration-db
      - monitoring
  
  integration-db:
    image: postgres:13
    environment:
      POSTGRES_DB: integration_db
      POSTGRES_USER: integration_user
      POSTGRES_PASSWORD: integration_pass
    volumes:
      - integration-db-data:/var/lib/postgresql/data
  
  monitoring:
    image: prom/prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
  
  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin

volumes:
  integration-db-data:
```

**特点**：
- 真实环境模拟
- 性能监控
- 持久化数据
- 完整功能测试

## 测试数据管理策略

### 测试数据生成

```python
# test/fixtures/data_generator.py
import os
import hashlib
from pathlib import Path

class TestDataGenerator:
    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def generate_file(self, name: str, size: int, content_type: str = 'random'):
        """生成指定大小的测试文件"""
        file_path = self.base_path / name
        
        if content_type == 'random':
            # 生成随机内容
            with open(file_path, 'wb') as f:
                remaining = size
                while remaining > 0:
                    chunk_size = min(1024 * 1024, remaining)  # 1MB chunks
                    chunk = os.urandom(chunk_size)
                    f.write(chunk)
                    remaining -= chunk_size
        elif content_type == 'pattern':
            # 生成模式内容（便于验证）
            pattern = b'TESTDATA' * 128  # 1KB pattern
            with open(file_path, 'wb') as f:
                for i in range(size // len(pattern)):
                    f.write(pattern)
                f.write(pattern[:size % len(pattern)])
        
        return file_path
    
    def generate_test_suite(self):
        """生成完整测试数据集"""
        files = {
            'small_files': [],
            'medium_files': [],
            'large_files': [],
            'special_files': []
        }
        
        # 小文件 (1KB - 10MB)
        for i in range(10):
            size = 1024 * (2 ** i)  # 1KB, 2KB, 4KB, ..., 512KB
            file_path = self.generate_file(f'small_{i}.dat', size)
            files['small_files'].append(file_path)
        
        # 中等文件 (10MB - 100MB)
        for i in range(5):
            size = 10 * 1024 * 1024 * (i + 1)  # 10MB, 20MB, ..., 50MB
            file_path = self.generate_file(f'medium_{i}.dat', size)
            files['medium_files'].append(file_path)
        
        # 大文件 (1GB+)
        large_sizes = [1024**3, 5*1024**3]  # 1GB, 5GB
        for i, size in enumerate(large_sizes):
            file_path = self.generate_file(f'large_{i}.dat', size)
            files['large_files'].append(file_path)
        
        # 特殊文件
        special_cases = [
            ('empty.dat', 0),
            ('中文文件名.dat', 1024),
            ('file with spaces.dat', 1024),
            ('file-with-symbols!@#$.dat', 1024)
        ]
        
        for name, size in special_cases:
            file_path = self.generate_file(name, size)
            files['special_files'].append(file_path)
        
        return files
```

### 测试数据清理

```python
# test/fixtures/data_cleanup.py
import shutil
from pathlib import Path

class TestDataCleanup:
    @staticmethod
    def cleanup_test_data(base_path: str):
        """清理测试数据"""
        path = Path(base_path)
        if path.exists():
            shutil.rmtree(path)
    
    @staticmethod
    def cleanup_database(db_path: str):
        """清理测试数据库"""
        db_file = Path(db_path)
        if db_file.exists():
            db_file.unlink()
```

### 数据库测试策略

```python
# test/conftest.py
import pytest
import tempfile
from pathlib import Path
from celestial_nasops.media_status_db import MediaStatusDB

@pytest.fixture(scope="function")
def temp_db():
    """临时测试数据库"""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    db = MediaStatusDB(db_path)
    yield db
    
    db.close()
    Path(db_path).unlink(missing_ok=True)

@pytest.fixture(scope="function")
def populated_db(temp_db):
    """预填充数据的测试数据库"""
    # 插入测试数据
    test_files = [
        ('test1.mp4', '/path/test1.mp4', 'hash1', 1048576, 'PENDING'),
        ('test2.mp4', '/path/test2.mp4', 'hash2', 52428800, 'COMPLETED'),
        ('test3.mp4', '/path/test3.mp4', 'hash3', 1073741824, 'FAILED')
    ]
    
    for filename, filepath, file_hash, size, status in test_files:
        temp_db.insert_file(filename, filepath, file_hash, size, status)
    
    return temp_db
```

## 性能测试策略

### 基准测试

```python
# test/performance/benchmark.py
import time
import psutil
import pytest
from memory_profiler import profile

class PerformanceBenchmark:
    def __init__(self):
        self.metrics = {}
    
    def measure_execution_time(self, func, *args, **kwargs):
        """测量执行时间"""
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        
        execution_time = end_time - start_time
        self.metrics['execution_time'] = execution_time
        return result, execution_time
    
    def measure_memory_usage(self, func, *args, **kwargs):
        """测量内存使用"""
        process = psutil.Process()
        initial_memory = process.memory_info().rss
        
        result = func(*args, **kwargs)
        
        final_memory = process.memory_info().rss
        memory_delta = final_memory - initial_memory
        
        self.metrics['memory_usage'] = {
            'initial': initial_memory,
            'final': final_memory,
            'delta': memory_delta
        }
        
        return result, memory_delta
    
    @profile
    def profile_function(self, func, *args, **kwargs):
        """详细内存分析"""
        return func(*args, **kwargs)
```

### 负载测试

```python
# test/performance/load_test.py
import concurrent.futures
import threading
from typing import List, Callable

class LoadTester:
    def __init__(self, max_workers: int = 10):
        self.max_workers = max_workers
        self.results = []
        self.lock = threading.Lock()
    
    def run_concurrent_test(self, func: Callable, test_data: List, duration: int = 60):
        """并发负载测试"""
        start_time = time.time()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = []
            
            while time.time() - start_time < duration:
                for data in test_data:
                    if time.time() - start_time >= duration:
                        break
                    
                    future = executor.submit(self._execute_and_record, func, data)
                    futures.append(future)
            
            # 等待所有任务完成
            concurrent.futures.wait(futures)
        
        return self.results
    
    def _execute_and_record(self, func: Callable, data):
        """执行函数并记录结果"""
        start_time = time.time()
        try:
            result = func(data)
            success = True
            error = None
        except Exception as e:
            result = None
            success = False
            error = str(e)
        
        end_time = time.time()
        
        with self.lock:
            self.results.append({
                'success': success,
                'execution_time': end_time - start_time,
                'error': error,
                'timestamp': start_time
            })
```

## 工具和框架选择

### 测试框架对比

| 工具 | 用途 | 优势 | 劣势 |
|------|------|------|------|
| pytest | 单元/集成测试 | 简洁语法、丰富插件、参数化 | 学习曲线 |
| unittest | 单元测试 | Python标准库、熟悉度高 | 语法冗长 |
| nose2 | 单元测试 | 兼容unittest、插件系统 | 社区较小 |
| tox | 多环境测试 | 环境隔离、版本兼容性 | 配置复杂 |

### 推荐工具栈

**核心框架**：
- **pytest**: 主要测试框架
- **pytest-cov**: 代码覆盖率
- **pytest-xdist**: 并行测试
- **pytest-html**: HTML报告

**模拟和存根**：
- **unittest.mock**: 标准库模拟
- **responses**: HTTP请求模拟
- **freezegun**: 时间模拟

**性能测试**：
- **pytest-benchmark**: 性能基准
- **memory-profiler**: 内存分析
- **psutil**: 系统资源监控

**数据生成**：
- **factory-boy**: 测试数据工厂
- **faker**: 假数据生成
- **hypothesis**: 属性测试

## 持续改进策略

### 测试质量指标

1. **覆盖率指标**：
   - 代码覆盖率 ≥ 80%
   - 分支覆盖率 ≥ 70%
   - 关键路径覆盖率 = 100%

2. **性能指标**：
   - 测试执行时间 < 10分钟
   - 单元测试 < 5秒
   - API测试 < 2分钟
   - E2E测试 < 8分钟

3. **稳定性指标**：
   - 测试通过率 ≥ 95%
   - 误报率 < 5%
   - 测试环境可用性 ≥ 99%

### 测试维护策略

1. **定期审查**：
   - 每月测试用例审查
   - 季度测试策略评估
   - 年度工具栈评估

2. **自动化改进**：
   - 测试结果趋势分析
   - 失败模式识别
   - 测试数据自动生成

3. **团队培训**：
   - 测试最佳实践培训
   - 新工具使用培训
   - 代码审查标准

---

**下一步**：基于自动化策略，设计可观测性和运维监控方案（Stage 5）。