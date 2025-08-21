# 知乎爬虫任务恢复指南

## 概述

本指南详细说明如何处理和恢复各种类型的任务中断，包括 Terminal#1003-1016 外键约束错误等常见问题。

## 错误类型与恢复方案

### 1. Terminal#1003-1016 (外键约束错误)

**错误原因：**
- 测试时使用了不存在的 `task_id`
- 数据库中 `questions` 表存在记录，但对应的 `task_info` 表中缺少相关任务记录
- 数据迁移或清理过程中产生的数据不一致

**恢复步骤：**

1. **自动修复脚本**（推荐）
```bash
# 创建修复脚本
cat > fix_foreign_key_error.py << 'EOF'
#!/usr/bin/env python3
from postgres_models import PostgreSQLManager, TaskInfo
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_foreign_key_errors():
    db = PostgreSQLManager()
    
    # 查找孤立的task_id
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT q.task_id, q.title, q.created_at
            FROM questions q 
            LEFT JOIN task_info t ON q.task_id = t.task_id 
            WHERE t.task_id IS NULL
            LIMIT 1
        """)
        orphaned = cursor.fetchall()
    
    for task_id, title, created_at in orphaned:
        # 创建缺失的任务记录
        keywords = title[:50] if title else f"恢复任务_{task_id[:8]}"
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO task_info 
                (task_id, keywords, start_date, end_date, status, current_stage,
                 created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                task_id, keywords, 
                created_at.date() if created_at else datetime.now().date(),
                datetime.now().date(),
                'completed', 'questions',
                created_at if created_at else datetime.now(),
                datetime.now()
            ))
            conn.commit()
        
        logger.info(f"✅ 已修复task_id: {task_id}")

if __name__ == "__main__":
    fix_foreign_key_errors()
EOF

# 运行修复脚本
python3 fix_foreign_key_error.py
```

2. **手动修复**
```bash
# 查找问题记录
python3 -c "
from postgres_models import PostgreSQLManager
db = PostgreSQLManager()
with db.get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute('SELECT DISTINCT task_id FROM questions WHERE task_id NOT IN (SELECT task_id FROM task_info)')
    print('孤立的task_id:', [r[0] for r in cursor.fetchall()])
"

# 为每个孤立的task_id创建任务记录
python3 -c "
from postgres_models import PostgreSQLManager
from datetime import datetime
db = PostgreSQLManager()
# 替换 'your_task_id' 为实际的task_id
task_id = 'your_task_id'
with db.get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO task_info (task_id, keywords, start_date, end_date, status)
        VALUES (%s, %s, %s, %s, %s)
    ''', (task_id, '恢复任务', datetime.now().date(), datetime.now().date(), 'completed'))
    conn.commit()
print('任务记录已创建')
"
```

### 2. KeyboardInterrupt (Ctrl+C中断)

**错误原因：** 用户手动中断任务执行

**恢复步骤：**
```bash
# 查看未完成的任务
python3 postgres_main.py list-tasks

# 交互式恢复
python3 postgres_main.py resume

# 或直接恢复指定任务
python3 -c "
from postgres_crawler import PostgresZhihuCrawler
crawler = PostgresZhihuCrawler()
crawler.resume_task('your_task_id')
"
```

### 3. 网络连接错误

**错误原因：** 网络不稳定或被反爬虫机制阻止

**恢复步骤：**
```bash
# 检查网络连接
ping zhihu.com

# 检查登录状态
python3 check_cookies.py

# 重新登录后恢复任务
python3 postgres_main.py resume
```

### 4. 浏览器崩溃

**错误原因：** ChromeDriver或浏览器进程异常退出

**恢复步骤：**
```bash
# 清理僵尸进程
pkill -f chrome
pkill -f chromedriver

# 重启任务
python3 postgres_main.py resume
```

### 5. 数据库连接失败

**错误原因：** PostgreSQL服务停止或连接配置错误

**恢复步骤：**
```bash
# 检查PostgreSQL服务状态
brew services list | grep postgresql

# 启动PostgreSQL服务
brew services start postgresql

# 测试数据库连接
python3 -c "
from postgres_models import PostgreSQLManager
try:
    db = PostgreSQLManager()
    with db.get_connection() as conn:
        print('✅ 数据库连接正常')
except Exception as e:
    print(f'❌ 数据库连接失败: {e}')
"
```

## 快速恢复命令

### 常用恢复命令

```bash
# 1. 查看所有任务状态
python3 postgres_main.py list-tasks

# 2. 交互式恢复未完成任务
python3 postgres_main.py resume

# 3. 检查系统状态
python3 -c "
from postgres_models import PostgreSQLManager
db = PostgreSQLManager()
print('数据库连接测试...')
with db.get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM task_info')
    print(f'任务总数: {cursor.fetchone()[0]}')
    cursor.execute('SELECT COUNT(*) FROM questions')
    print(f'问题总数: {cursor.fetchone()[0]}')
print('✅ 系统状态正常')
"

# 4. 修复外键约束错误
python3 -c "
from postgres_models import PostgreSQLManager
db = PostgreSQLManager()
with db.get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute('''
        SELECT DISTINCT q.task_id 
        FROM questions q 
        LEFT JOIN task_info t ON q.task_id = t.task_id 
        WHERE t.task_id IS NULL
    ''')
    orphaned = cursor.fetchall()
    if orphaned:
        print(f'发现 {len(orphaned)} 个外键约束错误')
        print('请运行修复脚本')
    else:
        print('✅ 无外键约束错误')
"
```

### 一键恢复脚本

```bash
# 创建一键恢复脚本
cat > quick_recovery.py << 'EOF'
#!/usr/bin/env python3
from postgres_models import PostgreSQLManager
from postgres_crawler import PostgresZhihuCrawler
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def quick_recovery():
    try:
        # 1. 检查数据库连接
        db = PostgreSQLManager()
        with db.get_connection() as conn:
            logger.info("✅ 数据库连接正常")
        
        # 2. 检查外键约束
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT q.task_id 
                FROM questions q 
                LEFT JOIN task_info t ON q.task_id = t.task_id 
                WHERE t.task_id IS NULL
            """)
            orphaned = cursor.fetchall()
            
            if orphaned:
                logger.info(f"修复 {len(orphaned)} 个外键约束错误...")
                # 自动修复逻辑
                for (task_id,) in orphaned:
                    cursor.execute("""
                        INSERT INTO task_info (task_id, keywords, start_date, end_date, status)
                        VALUES (%s, %s, CURRENT_DATE, CURRENT_DATE, 'completed')
                    """, (task_id, f"恢复任务_{task_id[:8]}"))
                conn.commit()
                logger.info("✅ 外键约束错误已修复")
        
        # 3. 查找未完成任务
        unfinished = db.get_unfinished_tasks()
        if unfinished:
            logger.info(f"发现 {len(unfinished)} 个未完成任务")
            for task in unfinished:
                logger.info(f"  - {task.task_id}: {task.keywords} ({task.status})")
            
            # 询问是否恢复
            choice = input("是否恢复第一个未完成任务? (y/n): ")
            if choice.lower() == 'y':
                crawler = PostgresZhihuCrawler()
                crawler.resume_task(unfinished[0].task_id)
        else:
            logger.info("✅ 没有未完成的任务")
            
    except Exception as e:
        logger.error(f"恢复过程中发生错误: {e}")

if __name__ == "__main__":
    quick_recovery()
EOF

# 运行一键恢复
python3 quick_recovery.py
```

## 预防措施

### 1. 使用正确的测试方式

```bash
# 创建测试任务而非使用虚假task_id
python3 -c "
from postgres_models import PostgreSQLManager
db = PostgreSQLManager()
task_id = db.create_task('测试关键词', '2024-01-01', '2024-01-02')
print(f'测试任务ID: {task_id}')
"
```

### 2. 优雅中断

- 使用 `Ctrl+C` 而非 `kill -9`
- 任务会自动保存进度并设置为可恢复状态

### 3. 定期检查

```bash
# 添加到定时任务中
# 每天检查系统状态
0 9 * * * cd /path/to/zhihu && python3 -c "from postgres_models import PostgreSQLManager; db = PostgreSQLManager(); print('系统状态检查:', len(db.get_unfinished_tasks()), '个未完成任务')"
```

### 4. 数据备份

```bash
# 定期备份数据库
pg_dump zhihu_crawler > backup_$(date +%Y%m%d).sql

# 备份重要配置
cp config.py config_backup_$(date +%Y%m%d).py
```

## 故障排除

### 常见问题诊断

```bash
# 系统健康检查脚本
cat > health_check.py << 'EOF'
#!/usr/bin/env python3
from postgres_models import PostgreSQLManager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def health_check():
    checks = []
    
    # 数据库连接检查
    try:
        db = PostgreSQLManager()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
        checks.append(("数据库连接", True, "正常"))
    except Exception as e:
        checks.append(("数据库连接", False, str(e)))
    
    # 表结构检查
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name IN ('task_info', 'questions', 'answers', 'search_results')
            """)
            tables = [row[0] for row in cursor.fetchall()]
            expected = ['task_info', 'questions', 'answers', 'search_results']
            missing = set(expected) - set(tables)
            
            if not missing:
                checks.append(("表结构", True, "完整"))
            else:
                checks.append(("表结构", False, f"缺少: {missing}"))
    except Exception as e:
        checks.append(("表结构", False, str(e)))
    
    # 外键约束检查
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM questions q 
                LEFT JOIN task_info t ON q.task_id = t.task_id 
                WHERE t.task_id IS NULL
            """)
            orphaned_count = cursor.fetchone()[0]
            
            if orphaned_count == 0:
                checks.append(("外键约束", True, "正常"))
            else:
                checks.append(("外键约束", False, f"{orphaned_count}个孤立记录"))
    except Exception as e:
        checks.append(("外键约束", False, str(e)))
    
    # 输出结果
    logger.info("=== 系统健康检查 ===")
    all_ok = True
    for name, status, message in checks:
        icon = "✅" if status else "❌"
        logger.info(f"{icon} {name}: {message}")
        if not status:
            all_ok = False
    
    if all_ok:
        logger.info("\n🎉 系统状态良好")
    else:
        logger.info("\n⚠️ 系统存在问题，建议修复")
    
    return all_ok

if __name__ == "__main__":
    health_check()
EOF

# 运行健康检查
python3 health_check.py
```

## 总结

**Terminal#1003-1016 等错误完全可以恢复**，系统具备：

- ✅ **自动检测**：识别各种类型的中断和错误
- ✅ **智能修复**：自动修复外键约束等数据完整性问题
- ✅ **断点续传**：从中断点继续执行，不丢失已采集数据
- ✅ **状态管理**：区分不同类型的中断，采用相应的恢复策略
- ✅ **预防机制**：提供最佳实践避免常见问题

**推荐恢复流程：**
1. 运行 `python3 health_check.py` 检查系统状态
2. 如有外键约束错误，运行修复脚本
3. 使用 `python3 postgres_main.py resume` 恢复任务
4. 定期备份和监控，预防问题发生