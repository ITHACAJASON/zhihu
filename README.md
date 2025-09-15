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

### 1. 启动爬虫

```bash
python3 main.py
```

### 2. 登录知乎

- 程序启动后会自动打开 Chrome 浏览器
- 浏览器会导航到知乎登录页面
- 手动完成登录操作（包括验证码等）
- 登录成功后在控制台输入 `done` 继续

### 3. 自动爬取

- 程序会自动从数据库读取待爬取的问题
- 逐个访问问题页面并采集回答
- 实时显示爬取进度
- 自动保存回答数据到数据库

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