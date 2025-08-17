# 知乎爬虫项目

一个功能强大的知乎爬虫，支持按关键字搜索并采集指定时间范围内的问题、答案和评论数据。

## 功能特性
- 关键字搜索，按时间范围过滤（默认 2015-01-01 至 2025-12-31）
- 采集问题：标题、内容、关注数、浏览量
- 采集答案：全部答案、作者、点赞数、回答时间、答案链接
- 采集评论：用户名、时间、评论内容、点赞量
- 懒加载处理：自动滚动加载所有结果
- 反爬策略：随机延时、User-Agent 轮换、防检测设置
- 数据持久化：SQLite，支持增量更新
- 命令行接口：一条命令即可启动

## 安装

```bash
pip3 install -r requirements.txt
```

## 使用

```bash
# 基本用法（必须指定 --keyword）
python3 main.py --keyword "机器学习"

# 指定时间范围
python3 main.py --keyword "人工智能" --start "2020-01-01" --end "2023-12-31"

# 无头模式/非无头模式
python3 main.py --keyword "大模型" --headless
python3 main.py --keyword "大模型" --no-headless

# 自定义数据库路径与日志级别
python3 main.py --keyword "Python" --db "./my.db" --log-level DEBUG
```

## 目录结构

```
zhihu/
├── README.md
├── requirements.txt
├── config.py
├── models.py
├── crawler.py
└── main.py
```

## 常见问题
- 若首次运行自动下载 ChromeDriver 较慢，请耐心等待
- 若页面加载失败，可在 config.py 调整 PAGE_LOAD_TIMEOUT、ELEMENT_WAIT_TIMEOUT
- 若遇到访问限制，适当增大随机延时范围

## 免责声明
本项目仅供学习与研究使用，请遵守目标网站的服务条款与 robots 协议。


### 一键执行命令
# 使用缓存（默认行为）
```bash
python3 main.py batch --use-cache
```
# 或者直接省略参数（默认启用缓存）
```bash
python3 main.py batch
```
# 指定时间范围使用缓存
```bash
python3 main.py batch --start 2024-01-01 --end 2024-01-02 --use-cache
```
# 使用缓存
```bash
python3 main.py multi --keywords "海归 回国,留学生 回国,海外 回国" --use-cache
```
# 或者省略参数（默认启用缓存）
```bash
python3 main.py multi --keywords "海归 回国,留学生 回国"
```
# 不使用缓存，重新进行搜索
```bash
python3 main.py batch --no-cache
```
# 指定时间范围不使用缓存
```bash
python3 main.py batch --start 2024-01-01 --end 2024-01-02 --no-cache
```
# 不使用缓存
```bash
python3 main.py multi --keywords "海归 回国,留学生 回国,海外 回国" --no-cache
```