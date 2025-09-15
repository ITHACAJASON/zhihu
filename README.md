# 知乎问答爬虫

一个基于 Selenium 的知乎问答爬虫，能够从 PostgreSQL 数据库读取问题 URL，自动采集问题页面的所有回答。

## 功能特点

- 🚀 **智能爬取**: 从数据库读取问题 URL 和目标回答数，自动判断爬取完成条件
- 🔐 **用户登录**: 支持手动登录知乎账号，避免登录验证问题
- 🛡️ **反反爬**: 使用多种反检测技术，模拟真实用户行为
- 💾 **内存优化**: 每采集 200 个回答自动清理 DOM，避免内存溢出
- 📊 **进度跟踪**: 实时显示爬取进度和完成度统计
- 🔄 **断点续爬**: 支持中断后继续爬取，避免重复采集

## 系统要求

- Python 3.7+
- PostgreSQL 数据库
- Chrome 浏览器
- macOS/Linux/Windows

## 安装依赖

```bash
# 安装 Python 依赖
pip3 install -r requirements.txt

# 确保 Chrome 浏览器已安装
# ChromeDriver 会自动下载管理
```

## 数据库准备

### 1. 创建数据库

```sql
CREATE DATABASE zhihu_crawl;
```

### 2. 创建 questions 表

```sql
CREATE TABLE questions (
    id SERIAL PRIMARY KEY,
    url TEXT NOT NULL,
    answer_count INTEGER NOT NULL,
    crawl_status VARCHAR(20) DEFAULT 'pending',
    crawled_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 3. 插入测试数据

```sql
INSERT INTO questions (url, answer_count) VALUES 
('https://www.zhihu.com/question/123456789', 100),
('https://www.zhihu.com/question/987654321', 50);
```

## 配置设置

### 环境变量配置（可选）

```bash
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=zhihu_crawl
export DB_USER=postgres
export DB_PASSWORD=your_password
```

### 修改配置文件

编辑 `config.py` 文件，根据需要调整以下配置：

```python
# 数据库配置
DATABASE_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'zhihu_crawl',
    'user': 'postgres',
    'password': 'your_password'
}

# 爬虫配置
CRAWLER_CONFIG = {
    'headless': False,  # 设置为 True 启用无头模式
    'answers_per_cleanup': 200,  # DOM 清理频率
    'scroll_delay': (1, 3),  # 滚动延时
    'page_load_delay': (2, 4),  # 页面加载延时
}
```

## 使用方法

### 1. 环境初始化

#### 安装依赖
```bash
# 进入项目目录
cd /path/to/zhihu

# 安装 Python 依赖
pip3 install -r requirements.txt
```

#### 数据库初始化
```bash
# 连接 PostgreSQL 数据库
psql -U postgres

# 创建数据库
CREATE DATABASE zhihu_crawl;

# 切换到新数据库
\c zhihu_crawl;

# 创建 questions 表
CREATE TABLE questions (
    id SERIAL PRIMARY KEY,
    url TEXT NOT NULL,
    answer_count INTEGER NOT NULL,
    crawl_status VARCHAR(20) DEFAULT 'pending',
    crawled_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

# 创建 answers 表
CREATE TABLE answers (
    id SERIAL PRIMARY KEY,
    question_id TEXT NOT NULL,
    answer_id TEXT UNIQUE NOT NULL,
    author TEXT,
    content TEXT,
    vote_count INTEGER DEFAULT 0,
    create_time TIMESTAMP,
    task_id TEXT,
    url TEXT,
    crawl_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

# 退出 psql
\q
```

#### 配置文件设置
```bash
# 编辑配置文件
vim config.py

# 或使用其他编辑器
nano config.py
```

### 2. 数据准备

#### 添加待爬取问题
```bash
# 方法1: 直接使用 SQL 插入
psql -U postgres -d zhihu_crawl -c "
INSERT INTO questions (url, answer_count) VALUES 
('https://www.zhihu.com/question/123456789', 100),
('https://www.zhihu.com/question/987654321', 50);"

# 方法2: 从 CSV 文件批量导入
# 准备 questions.csv 文件，格式：url,answer_count
# https://www.zhihu.com/question/123456789,100
# https://www.zhihu.com/question/987654321,50

psql -U postgres -d zhihu_crawl -c "
\COPY questions(url, answer_count) FROM 'questions.csv' DELIMITER ',' CSV HEADER;"
```

#### 查看待爬取问题
```bash
# 查看所有问题
psql -U postgres -d zhihu_crawl -c "SELECT * FROM questions;"

# 查看待爬取问题统计
psql -U postgres -d zhihu_crawl -c "
SELECT 
    crawl_status,
    COUNT(*) as count,
    SUM(answer_count) as total_answers,
    SUM(crawled_count) as crawled_answers
FROM questions 
GROUP BY crawl_status;"
```

### 3. 全量采集

#### 启动完整爬虫流程
```bash
# 启动爬虫（交互模式）
python3 main.py

# 程序启动后的操作步骤：
# 1. 等待 Chrome 浏览器自动打开
# 2. 手动登录知乎账号（包括验证码）
# 3. 登录成功后在控制台输入 'done' 继续
# 4. 程序自动开始爬取所有待处理问题
```

#### 后台运行模式
```bash
# 使用 nohup 后台运行
nohup python3 main.py > crawler.log 2>&1 &

# 查看运行状态
tail -f crawler.log

# 查看进程
ps aux | grep main.py

# 停止后台进程
kill -TERM <进程ID>
```

### 4. 断点续传

#### 查看爬取进度
```bash
# 查看整体进度
psql -U postgres -d zhihu_crawl -c "
SELECT 
    url,
    answer_count as target_count,
    crawled_count,
    ROUND(crawled_count::float / answer_count * 100, 2) as progress_percent,
    crawl_status
FROM questions 
ORDER BY id;"

# 查看未完成的问题
psql -U postgres -d zhihu_crawl -c "
SELECT * FROM questions 
WHERE crawl_status != 'completed' 
OR crawled_count < answer_count;"
```

#### 重新启动爬虫
```bash
# 直接重新启动，程序会自动从中断处继续
python3 main.py

# 程序会自动：
# 1. 检查数据库中的爬取状态
# 2. 跳过已完成的问题
# 3. 从未完成的问题继续爬取
```

#### 重置特定问题状态
```bash
# 重置某个问题的爬取状态
psql -U postgres -d zhihu_crawl -c "
UPDATE questions 
SET crawl_status = 'pending', crawled_count = 0 
WHERE url = 'https://www.zhihu.com/question/123456789';"

# 重置所有问题状态
psql -U postgres -d zhihu_crawl -c "
UPDATE questions 
SET crawl_status = 'pending', crawled_count = 0;"
```

### 5. 数据导出

#### 导出回答数据
```bash
# 导出所有回答为 CSV
psql -U postgres -d zhihu_crawl -c "
\COPY (SELECT * FROM answers) TO 'answers_export.csv' DELIMITER ',' CSV HEADER;"

# 导出特定问题的回答
psql -U postgres -d zhihu_crawl -c "
\COPY (
    SELECT * FROM answers 
    WHERE question_id = '123456789'
) TO 'question_123456789_answers.csv' DELIMITER ',' CSV HEADER;"

# 导出回答统计信息
psql -U postgres -d zhihu_crawl -c "
\COPY (
    SELECT 
        question_id,
        COUNT(*) as answer_count,
        AVG(vote_count) as avg_votes,
        MAX(vote_count) as max_votes,
        MIN(create_time) as earliest_answer,
        MAX(create_time) as latest_answer
    FROM answers 
    GROUP BY question_id
) TO 'questions_summary.csv' DELIMITER ',' CSV HEADER;"
```

#### 导出为 JSON 格式
```bash
# 导出为 JSON（需要 PostgreSQL 9.2+）
psql -U postgres -d zhihu_crawl -c "
\COPY (
    SELECT row_to_json(answers) FROM answers
) TO 'answers_export.json';"

# 导出结构化 JSON
psql -U postgres -d zhihu_crawl -c "
\COPY (
    SELECT json_build_object(
        'question_id', question_id,
        'answers', json_agg(
            json_build_object(
                'answer_id', answer_id,
                'author', author,
                'content', content,
                'vote_count', vote_count,
                'create_time', create_time
            )
        )
    )
    FROM answers 
    GROUP BY question_id
) TO 'questions_with_answers.json';"
```

#### 数据备份
```bash
# 备份整个数据库
pg_dump -U postgres zhihu_crawl > zhihu_crawl_backup.sql

# 仅备份数据（不包括表结构）
pg_dump -U postgres --data-only zhihu_crawl > zhihu_crawl_data.sql

# 恢复数据库
psql -U postgres -d zhihu_crawl < zhihu_crawl_backup.sql
```

### 6. 监控和管理

#### 实时监控爬取进度
```bash
# 监控脚本（每10秒刷新一次）
watch -n 10 "psql -U postgres -d zhihu_crawl -c '
SELECT 
    COUNT(*) as total_questions,
    SUM(CASE WHEN crawl_status = \"completed\" THEN 1 ELSE 0 END) as completed,
    SUM(answer_count) as total_target_answers,
    SUM(crawled_count) as total_crawled_answers,
    ROUND(SUM(crawled_count)::float / SUM(answer_count) * 100, 2) as overall_progress
FROM questions;'"
```

#### 查看日志
```bash
# 查看实时日志
tail -f zhihu_crawler.log

# 查看错误日志
grep -i error zhihu_crawler.log

# 查看特定时间段的日志
grep "2024-01-01" zhihu_crawler.log
```

#### 性能优化
```bash
# 查看数据库性能
psql -U postgres -d zhihu_crawl -c "
SELECT 
    schemaname,
    tablename,
    attname,
    n_distinct,
    correlation
FROM pg_stats 
WHERE tablename IN ('questions', 'answers');"

# 创建索引优化查询性能
psql -U postgres -d zhihu_crawl -c "
CREATE INDEX IF NOT EXISTS idx_answers_question_id ON answers(question_id);
CREATE INDEX IF NOT EXISTS idx_answers_create_time ON answers(create_time);
CREATE INDEX IF NOT EXISTS idx_questions_crawl_status ON questions(crawl_status);"
```

### 7. 快速命令参考

#### 常用命令速查表

| 操作类型 | 命令 | 说明 |
|---------|------|------|
| **环境初始化** | `pip3 install -r requirements.txt` | 安装依赖 |
| | `psql -U postgres` | 连接数据库 |
| | `CREATE DATABASE zhihu_crawl;` | 创建数据库 |
| **数据准备** | `psql -U postgres -d zhihu_crawl -c "INSERT INTO questions..."` | 添加问题 |
| | `psql -U postgres -d zhihu_crawl -c "SELECT * FROM questions;"` | 查看问题 |
| **爬虫运行** | `python3 main.py` | 启动爬虫 |
| | `nohup python3 main.py > crawler.log 2>&1 &` | 后台运行 |
| | `tail -f crawler.log` | 查看日志 |
| **进度监控** | `psql -U postgres -d zhihu_crawl -c "SELECT crawl_status, COUNT(*) FROM questions GROUP BY crawl_status;"` | 查看状态统计 |
| | `watch -n 10 "psql -U postgres -d zhihu_crawl -c 'SELECT COUNT(*) FROM answers;'"` | 实时监控 |
| **数据导出** | `psql -U postgres -d zhihu_crawl -c "\COPY (SELECT * FROM answers) TO 'answers.csv' CSV HEADER;"` | 导出CSV |
| | `pg_dump -U postgres zhihu_crawl > backup.sql` | 数据库备份 |
| **故障处理** | `ps aux | grep main.py` | 查看进程 |
| | `kill -TERM <PID>` | 停止进程 |
| | `UPDATE questions SET crawl_status = 'pending';` | 重置状态 |

#### 一键脚本示例

**完整初始化脚本** (`init.sh`):
```bash
#!/bin/bash
echo "=== 知乎爬虫初始化 ==="

# 1. 安装依赖
echo "安装 Python 依赖..."
pip3 install -r requirements.txt

# 2. 创建数据库和表
echo "初始化数据库..."
psql -U postgres -c "CREATE DATABASE zhihu_crawl;"
psql -U postgres -d zhihu_crawl -c "
CREATE TABLE questions (
    id SERIAL PRIMARY KEY,
    url TEXT NOT NULL,
    answer_count INTEGER NOT NULL,
    crawl_status VARCHAR(20) DEFAULT 'pending',
    crawled_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE answers (
    id SERIAL PRIMARY KEY,
    question_id TEXT NOT NULL,
    answer_id TEXT UNIQUE NOT NULL,
    author TEXT,
    content TEXT,
    vote_count INTEGER DEFAULT 0,
    create_time TIMESTAMP,
    task_id TEXT,
    url TEXT,
    crawl_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_answers_question_id ON answers(question_id);
CREATE INDEX idx_answers_create_time ON answers(create_time);
CREATE INDEX idx_questions_crawl_status ON questions(crawl_status);
"

echo "初始化完成！"
```

**批量添加问题脚本** (`add_questions.sh`):
```bash
#!/bin/bash
# 使用方法: ./add_questions.sh questions.txt
# questions.txt 格式: 每行一个URL，用空格分隔URL和目标回答数
# 例如: https://www.zhihu.com/question/123456789 100

if [ $# -eq 0 ]; then
    echo "使用方法: $0 <questions_file>"
    echo "文件格式: URL 目标回答数"
    exit 1
fi

while read -r url count; do
    if [ -n "$url" ] && [ -n "$count" ]; then
        psql -U postgres -d zhihu_crawl -c "
        INSERT INTO questions (url, answer_count) VALUES ('$url', $count);"
        echo "已添加: $url (目标: $count 个回答)"
    fi
done < "$1"

echo "批量添加完成！"
```

**监控脚本** (`monitor.sh`):
```bash
#!/bin/bash
# 实时监控爬取进度

while true; do
    clear
    echo "=== 知乎爬虫监控面板 ==="
    echo "更新时间: $(date)"
    echo ""
    
    # 总体统计
    psql -U postgres -d zhihu_crawl -t -c "
    SELECT 
        '总问题数: ' || COUNT(*) || ' 个' as total,
        '已完成: ' || SUM(CASE WHEN crawl_status = 'completed' THEN 1 ELSE 0 END) || ' 个' as completed,
        '进行中: ' || SUM(CASE WHEN crawl_status = 'in_progress' THEN 1 ELSE 0 END) || ' 个' as in_progress,
        '待处理: ' || SUM(CASE WHEN crawl_status = 'pending' THEN 1 ELSE 0 END) || ' 个' as pending
    FROM questions;
    "
    
    echo ""
    echo "=== 回答采集统计 ==="
    psql -U postgres -d zhihu_crawl -t -c "
    SELECT 
        '目标回答总数: ' || SUM(answer_count) || ' 个' as target_total,
        '已采集回答: ' || SUM(crawled_count) || ' 个' as crawled_total,
        '完成度: ' || ROUND(SUM(crawled_count)::float / SUM(answer_count) * 100, 2) || '%' as progress
    FROM questions;
    "
    
    echo ""
    echo "=== 最近采集的回答 ==="
    psql -U postgres -d zhihu_crawl -c "
    SELECT 
        question_id,
        author,
        vote_count,
        crawl_time
    FROM answers 
    ORDER BY crawl_time DESC 
    LIMIT 5;
    "
    
    sleep 10
done
```

**数据导出脚本** (`export_data.sh`):
```bash
#!/bin/bash
# 一键导出所有数据

EXPORT_DIR="exports_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$EXPORT_DIR"

echo "=== 开始导出数据到 $EXPORT_DIR ==="

# 导出问题列表
psql -U postgres -d zhihu_crawl -c "
\COPY (SELECT * FROM questions) TO '$EXPORT_DIR/questions.csv' DELIMITER ',' CSV HEADER;"
echo "✓ 问题列表已导出"

# 导出所有回答
psql -U postgres -d zhihu_crawl -c "
\COPY (SELECT * FROM answers) TO '$EXPORT_DIR/answers.csv' DELIMITER ',' CSV HEADER;"
echo "✓ 回答数据已导出"

# 导出统计信息
psql -U postgres -d zhihu_crawl -c "
\COPY (
    SELECT 
        question_id,
        COUNT(*) as answer_count,
        AVG(vote_count) as avg_votes,
        MAX(vote_count) as max_votes,
        MIN(create_time) as earliest_answer,
        MAX(create_time) as latest_answer
    FROM answers 
    GROUP BY question_id
) TO '$EXPORT_DIR/statistics.csv' DELIMITER ',' CSV HEADER;"
echo "✓ 统计信息已导出"

# 数据库备份
pg_dump -U postgres zhihu_crawl > "$EXPORT_DIR/database_backup.sql"
echo "✓ 数据库备份已创建"

echo "=== 导出完成！文件保存在 $EXPORT_DIR 目录 ==="
ls -la "$EXPORT_DIR"
```

使用这些脚本:
```bash
# 给脚本添加执行权限
chmod +x init.sh add_questions.sh monitor.sh export_data.sh

# 运行初始化
./init.sh

# 批量添加问题
./add_questions.sh my_questions.txt

# 启动监控
./monitor.sh

# 导出数据
./export_data.sh
```

## 项目结构

```
zhihu/
├── main.py              # 主程序入口
├── zhihu_crawler.py     # 爬虫核心模块
├── database.py          # 数据库操作模块
├── config.py            # 配置文件
├── requirements.txt     # 依赖列表
├── README.md           # 说明文档
└── zhihu_crawler.log   # 日志文件（运行时生成）
```

## 数据表结构

### questions 表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL | 主键 |
| url | TEXT | 问题 URL |
| answer_count | INTEGER | 目标回答数 |
| crawl_status | VARCHAR(20) | 爬取状态 |
| crawled_count | INTEGER | 已爬取数量 |
| created_at | TIMESTAMP | 创建时间 |

### answers 表（自动创建）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL | 主键 |
| question_url | TEXT | 问题 URL |
| answer_id | TEXT | 回答 ID |
| author | TEXT | 作者 |
| content | TEXT | 回答内容 |
| vote_count | INTEGER | 点赞数 |
| created_time | TIMESTAMP | 回答时间 |
| crawl_time | TIMESTAMP | 爬取时间 |

## 反反爬机制

本爬虫采用多种技术规避知乎的反爬检测：

1. **浏览器伪装**: 使用真实的 Chrome 浏览器和用户代理
2. **行为模拟**: 随机延时、滚动加载、人工登录
3. **DOM 清理**: 定期清理页面元素，减少内存占用
4. **请求控制**: 合理的请求频率和重试机制

## 注意事项

⚠️ **重要提醒**

1. **遵守法律法规**: 请确保爬取行为符合相关法律法规
2. **尊重网站规则**: 遵守知乎的 robots.txt 和服务条款
3. **合理使用**: 控制爬取频率，避免对服务器造成压力
4. **数据安全**: 妥善保管爬取的数据，不要泄露用户隐私

## 常见问题

### Q: 登录时遇到验证码怎么办？
A: 手动完成验证码验证，程序会等待您完成所有登录步骤。

### Q: 爬取过程中程序崩溃怎么办？
A: 重新启动程序，会自动从上次中断的地方继续爬取。

### Q: 如何调整爬取速度？
A: 修改 `config.py` 中的延时参数，增大延时可以降低被检测的风险。

### Q: 数据库连接失败怎么办？
A: 检查数据库配置和网络连接，确保 PostgreSQL 服务正常运行。

## 故障排除

### 1. Chrome 浏览器问题

```bash
# 检查 Chrome 版本
google-chrome --version

# 手动更新 ChromeDriver
pip3 install --upgrade webdriver-manager
```

### 2. 数据库连接问题

```bash
# 测试数据库连接
psql -h localhost -U postgres -d zhihu_crawl
```

### 3. 依赖问题

```bash
# 重新安装依赖
pip3 install --upgrade -r requirements.txt
```

## 日志文件

程序运行时会生成 `zhihu_crawler.log` 日志文件，包含详细的运行信息：

- 数据库连接状态
- 爬取进度和结果
- 错误信息和异常
- 性能统计

## 许可证

本项目仅供学习和研究使用，请勿用于商业用途。使用时请遵守相关法律法规和网站服务条款。

## 更新日志

- v1.0.0: 初始版本，支持基本的问答爬取功能
- 支持用户登录和反反爬机制
- 支持 DOM 清理和内存优化
- 支持断点续爬和进度跟踪