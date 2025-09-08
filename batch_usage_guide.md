# crawl_specific_question.py 批量使用指南

## 📋 脚本功能

`crawl_specific_question.py` 是一个专门用于采集指定知乎问题的完整答案数据的脚本，支持：

- 单个问题完整答案采集
- API响应自动保存到文件
- 数据保存到PostgreSQL数据库
- 任务进度管理和断点续传
- 反爬策略和错误处理

## 🔧 准备参数

### 必备参数

1. **question_url** (必需)
   - 知乎问题页面的URL
   - 支持多种URL格式：
     - `https://www.zhihu.com/question/378706911/answer/1080446596`
     - `https://www.zhihu.com/question/378706911`
     - `https://www.zhihu.com/question/378706911?sort=created`

2. **task_name** (可选)
   - 任务名称，用于标识和分组
   - 默认值: `"specific_question_crawl"`
   - 建议格式: `"question_{question_id}_crawl"`

### 可选参数

3. **max_answers** (可选)
   - 最大采集答案数量限制
   - 类型: `int`
   - 默认值: `None` (采集全部答案)
   - 示例: `max_answers=1000`

## 📝 使用方法

### 方式1: 直接在脚本中修改参数

```python
# 在main函数中修改参数
def main():
    """主函数"""
    # 修改这里的参数
    question_url = "https://www.zhihu.com/question/YOUR_QUESTION_ID/answer/ANY_ANSWER_ID"
    task_name = "your_custom_task_name"

    try:
        # 初始化爬虫
        crawler = SpecificQuestionCrawler(question_url, task_name)

        # 开始爬取 (可设置最大答案数)
        result = crawler.crawl_all_answers(max_answers=1000)  # 或 None 采集全部

        # ... 其他代码保持不变
```

### 方式2: 创建批量处理脚本

```python
#!/usr/bin/env python3
"""
批量采集多个问题的示例脚本
"""

from crawl_specific_question import SpecificQuestionCrawler
import logging
logging.basicConfig(level=logging.INFO)

def batch_crawl_questions():
    """批量采集多个问题"""

    # 定义要采集的问题列表
    questions = [
        {
            "url": "https://www.zhihu.com/question/378706911/answer/1080446596",
            "task_name": "question_378706911_full",
            "max_answers": None  # 采集全部答案
        },
        {
            "url": "https://www.zhihu.com/question/457478394/answer/1910416671937659055",
            "task_name": "question_457478394_sample",
            "max_answers": 100  # 限制采集100个答案
        },
        {
            "url": "https://www.zhihu.com/question/37197524",
            "task_name": "question_37197524_test",
            "max_answers": 50   # 测试用，采集50个答案
        }
    ]

    results = []

    for i, question in enumerate(questions, 1):
        print(f"\n{'='*60}")
        print(f"开始处理第 {i}/{len(questions)} 个问题")
        print(f"问题URL: {question['url']}")
        print(f"任务名称: {question['task_name']}")
        print(f"最大答案数: {question['max_answers']}")
        print(f"{'='*60}")

        try:
            # 初始化爬虫
            crawler = SpecificQuestionCrawler(
                question_url=question["url"],
                task_name=question["task_name"]
            )

            # 开始爬取
            result = crawler.crawl_all_answers(max_answers=question["max_answers"])

            # 保存摘要
            summary_file = crawler.save_crawl_summary(result)

            # 记录结果
            results.append({
                "question": question,
                "result": result,
                "summary_file": summary_file
            })

            print(f"✅ 问题 {question['url']} 处理完成")
            print(f"📊 采集答案: {result.get('total_answers', 0)}")
            print(f"⏱️ 耗时: {result.get('duration_seconds', 0)} 秒")

        except Exception as e:
            print(f"❌ 处理问题 {question['url']} 时发生错误: {e}")
            results.append({
                "question": question,
                "error": str(e)
            })

        # 问题间延时，避免过于频繁
        if i < len(questions):
            print("⏳ 等待30秒后处理下一个问题...")
            import time
            time.sleep(30)

    return results

if __name__ == "__main__":
    results = batch_crawl_questions()

    # 输出汇总结果
    print(f"\n{'='*80}")
    print("批量处理完成！")
    print(f"{'='*80}")

    success_count = 0
    total_answers = 0

    for result in results:
        if "result" in result:
            success_count += 1
            total_answers += result["result"].get("total_answers", 0)

    print(f"成功处理问题: {success_count}/{len(results)}")
    print(f"总共采集答案: {total_answers}")
    print(f"{'='*80}")
```

### 方式3: 从数据库读取URL批量处理

```python
#!/usr/bin/env python3
"""
从数据库读取URL进行批量处理的示例脚本
"""

from crawl_specific_question import SpecificQuestionCrawler
from postgres_models import PostgreSQLManager
import logging
logging.basicConfig(level=logging.INFO)

def crawl_from_database():
    """从数据库读取问题URL进行批量采集"""

    # 初始化数据库管理器
    db = PostgreSQLManager()

    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()

            # 查询需要采集的问题 (例如未处理或需要更新的问题)
            cursor.execute("""
                SELECT question_id, title, url, answer_count
                FROM questions
                WHERE processed = FALSE
                AND answer_count > 100  -- 只处理答案数量较多的
                ORDER BY answer_count DESC
                LIMIT 5  -- 限制处理数量
            """)

            questions = cursor.fetchall()

            print(f"从数据库找到 {len(questions)} 个问题需要处理")

            for i, (question_id, title, url, expected_answers) in enumerate(questions, 1):
                print(f"\n{'='*60}")
                print(f"处理第 {i}/{len(questions)} 个问题")
                print(f"问题ID: {question_id}")
                print(f"标题: {title[:50]}...")
                print(f"预期答案数: {expected_answers}")
                print(f"{'='*60}")

                try:
                    # 创建任务名称
                    task_name = f"db_question_{question_id}"

                    # 初始化爬虫
                    crawler = SpecificQuestionCrawler(url, task_name)

                    # 开始采集 (可根据预期答案数设置限制)
                    max_answers = min(expected_answers, 1000) if expected_answers > 1000 else None
                    result = crawler.crawl_all_answers(max_answers=max_answers)

                    # 保存摘要
                    summary_file = crawler.save_crawl_summary(result)

                    print(f"✅ 问题 {question_id} 处理完成")
                    print(f"📊 采集答案: {result.get('total_answers', 0)}")
                    print(f"📈 完成率: {result.get('completion_rate', 0):.2f}%")

                except Exception as e:
                    print(f"❌ 处理问题 {question_id} 时发生错误: {e}")

                # 延时
                if i < len(questions):
                    import time
                    time.sleep(30)

    except Exception as e:
        print(f"数据库操作错误: {e}")

if __name__ == "__main__":
    crawl_from_database()
```

## 🚀 运行脚本

### 基本运行

```bash
# 直接运行脚本 (使用脚本中硬编码的参数)
python3 crawl_specific_question.py
```

### 带参数运行

```bash
# 如果脚本支持命令行参数，可以这样运行
python3 crawl_specific_question.py --url "https://www.zhihu.com/question/378706911" --task "my_task"
```

### 批量处理运行

```bash
# 运行批量处理脚本
python3 batch_crawl_example.py

# 运行数据库批量处理脚本
python3 db_batch_crawl_example.py
```

## 📊 参数配置建议

### 1. 根据问题规模选择参数

```python
# 小问题 (< 100个答案)
crawler = SpecificQuestionCrawler(url, task_name)
result = crawler.crawl_all_answers(max_answers=None)

# 中等规模问题 (100-1000个答案)
result = crawler.crawl_all_answers(max_answers=1000)

# 大问题 (> 1000个答案)
result = crawler.crawl_all_answers(max_answers=5000)
```

### 2. 任务命名建议

```python
# 按问题ID命名
task_name = f"question_{question_id}_full_crawl"

# 按主题命名
task_name = "留学生回国问题调研"

# 按时间命名
task_name = f"crawl_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
```

### 3. URL格式处理

```python
# 推荐的URL格式
valid_urls = [
    "https://www.zhihu.com/question/378706911/answer/1080446596",  # 完整格式
    "https://www.zhihu.com/question/378706911",                    # 简洁格式
    "https://www.zhihu.com/question/378706911?sort=created"        # 带参数格式
]
```

## ⚠️ 注意事项

### 1. URL格式要求
- 必须包含 `question/` 和问题ID
- 问题ID必须是纯数字
- 支持answer参数但不是必需

### 2. 数据库准备
- 确保PostgreSQL数据库已初始化
- 确保有相应的cookies文件
- 确保网络连接正常

### 3. 资源消耗
- 大问题可能需要较长时间
- 确保有足够的磁盘空间存储API响应
- 建议在网络稳定的环境下运行

### 4. 反爬策略
- 脚本内置了反爬处理
- 如遇403错误会自动尝试验证解决
- 建议不要并发运行多个实例

## 📋 批量采集检查清单

- [ ] 准备好要采集的问题URL列表
- [ ] 确定每个问题的task_name
- [ ] 确认是否需要限制max_answers
- [ ] 检查PostgreSQL数据库连接
- [ ] 确认cookies文件存在且有效
- [ ] 准备好足够的磁盘空间
- [ ] 确认网络连接稳定
- [ ] 选择适当的运行时间（避免高峰期）

按照这个指南，您就可以成功使用 `crawl_specific_question.py` 进行批量问题采集了！
