# 任务中断/恢复机制使用指南

## 概述

知乎爬虫现在支持完整的任务中断和恢复机制，可以在任何阶段中断任务并从中断点继续执行，避免重复工作。

## 机制原理

### 任务状态跟踪

系统会在数据库中记录每个处理阶段的状态：

1. **搜索结果阶段**：`search_results` 表的 `processed` 字段
2. **问题详情阶段**：`questions` 表的 `processed` 字段  
3. **答案采集阶段**：`answers` 表的 `processed` 字段


### 处理流程

```
搜索关键词 → 获取搜索结果 → 处理问题详情 → 采集答案
     ↓              ↓              ↓           ↓
  创建任务      标记搜索结果     标记问题      标记答案
               为已处理        为已处理      为已处理
```

## 使用方法

### 1. 创建新任务

```python
from postgres_crawler import PostgresZhihuCrawler

crawler = PostgresZhihuCrawler()

# 创建任务（只搜索，不立即处理）
task_id = crawler.crawl_by_keyword(
    keyword="Python编程",
    start_date="2024-01-01", 
    end_date="2024-12-31",
    process_immediately=False
)

print(f"任务创建成功: {task_id}")
```

### 2. 查看任务进度

```python
from postgres_models import PostgreSQLManager

db = PostgreSQLManager()

# 查看任务进度
progress = db.get_task_progress(task_id)
print(f"任务进度: {progress}")

# 输出示例：
# {
#     'search_results': {'total': 100, 'processed': 100},
#     'questions': {'total': 95, 'processed': 50}, 
#     'answers': {'total': 1200, 'processed': 800},

# }
```

### 3. 恢复中断的任务

```python
# 恢复任务
result = crawler.resume_task(task_id)
print(f"任务恢复结果: {result}")
```

### 4. 列出未完成的任务

```python
# 获取所有未完成的任务
unfinished_tasks = crawler.list_unfinished_tasks()

for task in unfinished_tasks:
    print(f"任务ID: {task.task_id}")
    print(f"关键词: {task.keywords}")
    print(f"状态: {task.status}")
    print(f"创建时间: {task.created_at}")
    print("-" * 50)
```

## 任务状态说明

- **`created`**: 任务已创建，搜索结果收集中
- **`running`**: 任务正在执行中
- **`paused`**: 任务已暂停（通常由于中断）
- **`completed`**: 任务已完成
- **`failed`**: 任务执行失败

## 恢复策略

系统会按照以下优先级恢复任务：

1. **未处理的搜索结果** → 爬取问题详情 → 爬取答案
2. **未处理的问题** → 爬取答案
3. **所有处理完成** → 标记任务为完成状态

## 实际使用示例

### 场景1：任务在问题详情采集阶段中断

```python
# 1. 查看任务状态
progress = db.get_task_progress("task_123")
# 输出：{'search_results': {'total': 50, 'processed': 50}, 
#        'questions': {'total': 45, 'processed': 20}, ...}

# 2. 恢复任务 - 系统会从第21个问题开始继续处理
result = crawler.resume_task("task_123")
```

### 场景2：任务在答案采集阶段中断

```python
# 1. 查看任务状态  
progress = db.get_task_progress("task_456")
# 输出：{'search_results': {'total': 30, 'processed': 30},
#        'questions': {'total': 28, 'processed': 28},
#        'answers': {'total': 500, 'processed': 200}, ...}

# 2. 恢复任务 - 系统会从第201个答案开始继续处理
result = crawler.resume_task("task_456")
```

## 测试脚本

使用提供的测试脚本验证恢复机制：

```bash
# 测试任务中断/恢复机制
python3 test_resume_mechanism.py

# 查看所有任务进度
python3 test_resume_mechanism.py progress
```

## 注意事项

1. **数据一致性**：每个处理阶段完成后立即标记为已处理，确保数据一致性
2. **异常处理**：如果某个项目处理失败，不会影响其他项目的处理
3. **资源管理**：长时间运行的任务建议定期检查系统资源使用情况
4. **网络稳定性**：建议在网络稳定的环境下运行，避免频繁的网络中断

## 故障排除

### 问题：任务恢复后重复处理相同内容

**原因**：可能是标记处理状态的逻辑有问题

**解决方案**：
```python
# 检查数据库中的处理状态
unprocessed = db.get_unprocessed_questions(task_id)
print(f"未处理问题数量: {len(unprocessed)}")

# 手动标记某个项目为已处理（如果确认已处理）
db.mark_question_processed(question_id, task_id)
```

### 问题：任务状态显示异常

**原因**：可能是任务状态更新失败

**解决方案**：
```python
# 手动更新任务状态
db.update_task_status(task_id, status='running')
```

## 性能优化建议

1. **批量处理**：对于大量数据，建议分批处理，避免单次处理时间过长
2. **并发控制**：避免同时运行多个相同关键词的任务
3. **定期清理**：定期清理已完成的旧任务数据，保持数据库性能
4. **监控日志**：关注爬虫日志，及时发现和解决问题

---

通过以上机制，知乎爬虫现在可以可靠地处理长时间运行的任务，即使在中断后也能准确恢复到正确的位置继续执行。