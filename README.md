# 知乎爬虫项目

一个功能强大的知乎爬虫，支持按关键字搜索并采集指定时间范围内的问题、答案和评论数据。

## 功能特性
- 关键字搜索，按时间范围过滤（默认 2015-01-01 至 2025-12-31）
- 采集问题：标题、内容、关注数、浏览量
- 采集答案：全部答案、作者、点赞数、回答时间、答案链接
- 采集评论：用户名、时间、评论内容、点赞量
- 懒加载处理：自动滚动加载所有结果
- 反爬策略：随机延时、User-Agent 轮换、防检测设置
- 数据持久化：PostgreSQL，支持任务恢复和实时数据存储
- 命令行接口：一条命令即可启动

## 安装

```bash
pip3 install -r requirements.txt
```

## 使用

```bash
# 基本用法（必须指定 --keyword）
python3 postgres_main.py crawl --keyword "机器学习"

# 指定时间范围
python3 postgres_main.py crawl --keyword "人工智能" --start-date "2020-01-01" --end-date "2023-12-31"

# 无头模式/非无头模式
python3 postgres_main.py crawl --keyword "大模型" --headless
python3 postgres_main.py crawl --keyword "大模型" --no-headless

# 批量爬取多个关键字
python3 postgres_main.py batch-crawl --keywords "人工智能,机器学习,大模型"

# 恢复中断的任务
python3 postgres_main.py resume
# 或指定任务ID恢复
python3 postgres_main.py resume --task-id "任务ID"

# 列出所有未完成任务
python3 postgres_main.py list-tasks

# 初始化数据库
python3 postgres_main.py init-db
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


### 常用命令示例

# 批量爬取多个关键字
```bash
python3 postgres_main.py batch-crawl --keywords "海归 回国,留学生 回国,海外 回国, 博士 回国"
```

# 指定时间范围爬取
```bash
python3 postgres_main.py batch-crawl --keywords "海归 回国,留学生 回国" --start-date 2024-01-01 --end-date 2024-01-02
```

# 非无头模式（显示浏览器界面）
```bash
python3 postgres_main.py batch-crawl --keywords "海归 回国,留学生 回国" --no-headless
```

# 恢复所有未完成任务
```bash
python3 postgres_main.py resume
```

# 查看所有未完成任务
```bash
python3 postgres_main.py list-tasks
```