# 知乎爬虫任务中断记录机制说明

## 概述

本文档详细说明知乎爬虫任务在中断后如何被合理记录，以及如何确保任务状态能够正确保存以便后续恢复。

## 任务状态定义

系统中定义了以下任务状态：

- **`running`**: 任务正在执行中
- **`paused`**: 任务已暂停（可恢复）
- **`completed`**: 任务已完成
- **`failed`**: 任务执行失败
- **`pending`**: 任务已创建，等待开始

## 当前中断处理机制

### 1. 异常中断处理

当任务执行过程中发生异常时，系统会：

```python
# 在 crawl_by_keyword 方法中
try:
    # 执行爬取逻辑
    ...
except Exception as e:
    logger.error(f"爬取过程中发生错误: {e}")
    # 更新任务状态为失败
    self.db.update_task_status(task_id, status='failed')
    return stats
```

**状态记录**: 任务状态被设置为 `failed`

### 2. 用户手动中断（Ctrl+C）

目前在主程序中有KeyboardInterrupt处理：

```python
# 在 postgres_main.py 中
try:
    # 执行爬取任务
    ...
except KeyboardInterrupt:
    logger.warning("用户中断爬取")
except Exception as e:
    logger.error(f"爬取失败: {e}")
    sys.exit(1)
finally:
    if crawler:
        crawler.close()
```

**当前问题**: 用户按Ctrl+C中断时，任务状态**不会**被自动设置为`paused`，而是保持原有状态（通常是`running`）。

## 中断后任务进入恢复列表的条件

任务会进入恢复列表的条件是状态为 `running` 或 `paused`：

```python
# 在 postgres_models.py 的 get_unfinished_tasks 方法中
SELECT task_id, keywords, start_date, end_date, status, current_stage,
       total_questions, processed_questions, total_answers, processed_answers,
       created_at, updated_at
FROM task_info 
WHERE status IN ('running', 'paused')
ORDER BY created_at
```

### 具体场景分析

#### 场景1：正常异常中断
- **触发条件**: 代码执行过程中抛出异常
- **状态记录**: `failed`
- **是否进入恢复列表**: ❌ 否
- **原因**: `failed` 状态不在恢复列表查询条件中

#### 场景2：用户手动中断（当前实现）
- **触发条件**: 用户按Ctrl+C
- **状态记录**: 保持原状态（通常是`running`）
- **是否进入恢复列表**: ✅ 是
- **原因**: 状态仍为`running`，符合恢复条件

#### 场景3：系统崩溃/强制终止
- **触发条件**: 系统崩溃、进程被杀死等
- **状态记录**: 保持原状态（通常是`running`）
- **是否进入恢复列表**: ✅ 是
- **原因**: 状态仍为`running`，符合恢复条件

## 改进建议

### 1. 增强KeyboardInterrupt处理

为了更好地记录用户主动中断的任务，建议在主要的爬取方法中添加KeyboardInterrupt处理：

```python
def crawl_by_keyword(self, keyword: str, start_date: str = None, end_date: str = None, process_immediately: bool = True) -> Dict:
    # ... 现有代码 ...
    
    try:
        # 执行爬取逻辑
        # ...
        
    except KeyboardInterrupt:
        logger.warning(f"用户中断任务: {task_id}")
        # 将任务状态设置为暂停，便于后续恢复
        self.db.update_task_status(task_id, status='paused')
        raise  # 重新抛出异常，让上层处理
        
    except Exception as e:
        logger.error(f"爬取过程中发生错误: {e}")
        # 更新任务状态为失败
        self.db.update_task_status(task_id, status='failed')
        return stats
```

### 2. 添加任务暂停功能

可以考虑添加一个专门的暂停方法：

```python
def pause_task(self, task_id: str, reason: str = "用户主动暂停"):
    """暂停指定任务"""
    try:
        self.db.update_task_status(task_id, status='paused')
        logger.info(f"任务已暂停: {task_id}, 原因: {reason}")
    except Exception as e:
        logger.error(f"暂停任务失败: {e}")
```

### 3. 增加任务恢复时的状态检查

在恢复任务时，可以根据任务的当前状态和阶段来决定从哪里继续：

```python
def resume_task(self, task_id: str) -> Dict:
    """恢复中断的任务"""
    task_info = self.db.get_task_info(task_id)
    
    if task_info.status == 'paused':
        logger.info(f"恢复暂停的任务: {task_id}")
        # 从暂停点继续
    elif task_info.status == 'running':
        logger.info(f"恢复中断的任务: {task_id}")
        # 检查进度，从适当位置继续
    
    # 更新状态为运行中
    self.db.update_task_status(task_id, status='running')
    
    # ... 恢复逻辑 ...
```

## 最佳实践

### 1. 优雅中断

如果需要中断正在运行的任务，建议：

1. **使用Ctrl+C**: 这会触发KeyboardInterrupt，任务状态会保持为`running`，可以通过恢复脚本继续
2. **避免强制杀死进程**: 使用`kill -9`等强制终止可能导致数据不一致

### 2. 定期检查任务状态

可以定期运行以下命令检查未完成的任务：

```bash
# 列出所有未完成任务
python3 resume_tasks.py --list

# 或使用主程序
python3 postgres_main.py resume
```

### 3. 任务恢复策略

- **单个任务恢复**: 适用于特定任务出现问题
- **批量恢复**: 适用于系统重启后恢复所有中断任务
- **按关键词恢复**: 适用于特定主题的任务恢复

## 监控和日志

### 日志记录

所有任务状态变更都会记录在日志中：

- 日志文件位置: `./logs/zhihu_crawler.log`
- 包含任务创建、状态更新、错误信息等

### 数据库记录

任务信息存储在PostgreSQL数据库的`task_info`表中：

- `status`: 当前任务状态
- `current_stage`: 当前执行阶段
- `created_at`: 任务创建时间
- `updated_at`: 最后更新时间
- 进度信息: `total_questions`, `processed_questions`等

## 总结

**当前机制下，任务中断后进入恢复列表的条件是**：

1. **状态为`running`**: 通常是用户中断（Ctrl+C）或系统崩溃导致
2. **状态为`paused`**: 需要手动设置或通过改进的中断处理机制

**不会进入恢复列表的情况**：

1. **状态为`failed`**: 异常导致的失败任务
2. **状态为`completed`**: 已完成的任务

通过改进KeyboardInterrupt处理机制，可以更好地区分用户主动中断和异常失败，提供更精确的任务恢复功能。