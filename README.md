# 知乎爬虫项目

一个功能强大的知乎爬虫，支持按关键字搜索并采集指定时间范围内的问题和答案数据。

## 功能特性
- 关键字搜索，按时间范围过滤（默认 2015-01-01 至 2025-12-31）
- 采集问题：标题、内容、关注数、浏览量
- 采集答案：全部答案、作者、点赞数、回答时间、答案链接

- 懒加载处理：自动滚动加载所有结果
- 反爬策略：随机延时、User-Agent 轮换、防检测设置
- 数据持久化：PostgreSQL，支持任务恢复和实时数据存储
- 命令行接口：一条命令即可启动

## 安装

```bash
pip3 install -r requirements.txt
```

## 使用

### 🚀 一键运行多关键字采集

#### 批量采集多个关键字（推荐）

```bash
# 一键批量采集多个关键字
python3 postgres_main.py batch-crawl --keywords "海归 回国,留学生 回国,海外 回国,博士 回国" --no-headless

# 指定时间范围的批量采集
python3 postgres_main.py batch-crawl --keywords "博士回国,海归就业,留学生" --start-date "2023-01-01" --end-date "2023-12-31"

# 使用有头模式进行批量采集（可观察浏览器操作）
python3 postgres_main.py batch-crawl --keywords "博士回国,海归就业" --no-headless

# 使用非批量模式（逐个关键字完整处理）
python3 postgres_main.py batch-crawl --keywords "博士回国,海归就业" --no-batch-mode
```

#### 单个关键字采集

```bash
# 采集单个关键字
python3 postgres_main.py crawl --keyword "博士回国"

# 指定时间范围
python3 postgres_main.py crawl --keyword "博士回国" --start-date "2023-01-01" --end-date "2023-12-31"

# 使用有头模式（显示浏览器界面）
python3 postgres_main.py crawl --keyword "博士回国" --no-headless
```

### 🔄 中断/恢复任务管理

#### 查看任务状态

```bash
# 列出所有未完成任务
python3 postgres_main.py list-tasks

# 使用专用脚本查看详细任务信息
python3 resume_tasks.py --list
```

#### 恢复中断的任务

```bash
# 交互式选择恢复任务（推荐）
python3 postgres_main.py resume

# 恢复指定任务ID
python3 postgres_main.py resume --task-id "your_task_id"

# 使用专用脚本恢复所有未完成任务
python3 resume_tasks.py --all

# 按关键词恢复任务
python3 resume_tasks.py --keyword "博士回国"

# 恢复指定任务ID
python3 resume_tasks.py --task-id "your_task_id"
```

### 🛠️ 系统管理

#### 数据库管理

```bash
# 初始化PostgreSQL数据库
python3 postgres_main.py init-db

# 从SQLite迁移数据到PostgreSQL
python3 postgres_main.py migrate --sqlite-path "path/to/your/sqlite.db"

# 迁移时不备份SQLite数据库
python3 postgres_main.py migrate --sqlite-path "path/to/your/sqlite.db" --no-backup
```

#### 创建测试任务

```bash
# 创建测试任务
python3 create_test_task.py create --keyword "测试关键字" --search-stage "completed" --qa-stage "pending"

# 更新任务状态
python3 create_test_task.py update --task-id "your_task_id" --search-stage "completed" --qa-stage "completed"

# 列出所有任务
python3 create_test_task.py list
```

## 目录结构

```
zhihu/
├── README.md
├── requirements.txt
├── config.py
├── postgres_models.py
├── postgres_crawler.py
├── postgres_main.py
├── migrate_to_postgres.py
├── check_selectors.py
├── cache/
├── cookies/
├── logs/
└── output/
```

## 常见问题
- 若首次运行自动下载 ChromeDriver 较慢，请耐心等待
- 若页面加载失败，可在 config.py 调整 PAGE_LOAD_TIMEOUT、ELEMENT_WAIT_TIMEOUT
- 若遇到访问限制，适当增大随机延时范围
- 使用前请确保已配置PostgreSQL数据库，并在config.py中设置正确的连接信息
- 首次使用请运行 `python3 postgres_main.py init-db` 初始化数据库
- 如需从旧版SQLite数据迁移，请使用 `python3 postgres_main.py migrate` 命令

## 免责声明
本项目仅供学习与研究使用，请遵守目标网站的服务条款与 robots 协议。


## 📋 常用命令速查

### 🚀 快速开始

```bash
# 一键批量采集（最常用）
python3 postgres_main.py batch-crawl --keywords "博士回国,海归就业,留学生"

# 单个关键字采集
python3 postgres_main.py crawl --keyword "博士回国"

# 查看所有未完成任务
python3 postgres_main.py list-tasks

# 交互式恢复任务
python3 postgres_main.py resume
```

### 🔧 高级功能

```bash
# 指定时间范围的批量采集
python3 postgres_main.py batch-crawl --keywords "博士回国,海归就业" --start-date "2023-01-01" --end-date "2023-12-31"

# 使用有头模式（显示浏览器）
python3 postgres_main.py batch-crawl --keywords "博士回国,海归就业" --no-headless

# 恢复所有未完成任务
python3 resume_tasks.py --all

# 按关键词恢复特定任务
python3 resume_tasks.py --keyword "博士回国"

# 按任务ID恢复
python3 resume_tasks.py --task-id "your_task_id"
```

### 📖 查看帮助

```bash
# 查看主程序帮助
python3 postgres_main.py --help

# 查看各命令帮助
python3 postgres_main.py crawl --help
python3 postgres_main.py batch-crawl --help
python3 postgres_main.py resume --help
python3 postgres_main.py list-tasks --help

# 查看恢复脚本帮助
python3 resume_tasks.py --help
```

### 🛠️ 系统维护

```bash
# 初始化数据库
python3 postgres_main.py init-db

# 数据迁移
python3 postgres_main.py migrate --sqlite-path "old_database.db"

# 查看详细任务信息
python3 resume_tasks.py --list
```

## 📊 任务状态管理

### 两阶段处理机制

本爬虫采用两阶段处理机制，每个任务包含两个独立的处理阶段：

1. **搜索阶段 (Search Stage)**: 搜索问题列表
   - `pending`: 等待开始
   - `running`: 正在执行
   - `completed`: 已完成
   - `failed`: 执行失败

2. **问答阶段 (QA Stage)**: 爬取问题详情和答案
   - `pending`: 等待开始
   - `running`: 正在执行
   - `completed`: 已完成
   - `failed`: 执行失败

### 任务状态查看

```bash
# 查看所有任务状态
python3 postgres_main.py list-tasks

# 查看详细任务信息（包括各阶段状态）
python3 resume_tasks.py --list
```

### 智能恢复机制

系统会根据任务的两个阶段状态智能选择恢复策略：

- **搜索阶段未完成**: 从搜索阶段开始恢复
- **搜索阶段已完成，问答阶段未完成**: 直接从问答阶段开始恢复
- **两个阶段都已完成**: 任务无需恢复

```bash
# 自动选择恢复策略
python3 postgres_main.py resume

# 恢复所有中断任务
python3 resume_tasks.py --all
```