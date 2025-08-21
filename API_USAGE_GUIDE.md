# 知乎API爬虫使用指南

本文档介绍基于知乎API接口的答案采集功能，该功能参考了[这篇博客](https://blog.csdn.net/weixin_50238287/article/details/119974388)的实现思路。

## 功能特性

### 🚀 API答案爬取优势
- **高效率**: 直接调用知乎API，无需浏览器渲染
- **稳定性**: 避免页面元素变化导致的爬取失败
- **完整性**: 可获取问题的所有答案，无分页限制
- **准确性**: 直接获取结构化数据，解析更准确

### 📊 支持的数据字段
- 答案内容（完整HTML格式）
- 作者信息（姓名、个人主页）
- 统计数据（点赞数、评论数）
- 时间信息（创建时间、更新时间）
- 答案链接

## 使用方法

### 1. 测试API功能

首先测试API连接是否正常：

```bash
python3 postgres_main.py test-api
```

### 2. 爬取指定问题的答案

使用API直接爬取某个问题的所有答案：

```bash
# 基本用法
python3 postgres_main.py api-crawl-answers -u "https://www.zhihu.com/question/25038841"

# 限制答案数量
python3 postgres_main.py api-crawl-answers -u "https://www.zhihu.com/question/25038841" -m 50

# 指定任务ID
python3 postgres_main.py api-crawl-answers -u "https://www.zhihu.com/question/25038841" -t "my-task-001"
```

### 3. 混合模式爬取

结合Selenium搜索和API答案获取的混合模式：

```bash
# 基本混合爬取
python3 postgres_main.py hybrid-crawl -k "人工智能"

# 限制问题和答案数量
python3 postgres_main.py hybrid-crawl -k "机器学习" -q 10 -a 20

# 指定时间范围
python3 postgres_main.py hybrid-crawl -k "深度学习" -s "2023-01-01" -e "2023-12-31"

# 使用有头模式（可观察过程）
python3 postgres_main.py hybrid-crawl -k "数据科学" --no-headless
```

## 命令参数说明

### api-crawl-answers 命令

| 参数 | 简写 | 必需 | 说明 |
|------|------|------|------|
| --question-url | -u | ✓ | 知乎问题URL |
| --max-answers | -m | ✗ | 最大答案数量限制 |
| --task-id | -t | ✗ | 自定义任务ID |

### hybrid-crawl 命令

| 参数 | 简写 | 必需 | 说明 |
|------|------|------|------|
| --keyword | -k | ✓ | 搜索关键字 |
| --start-date | -s | ✗ | 开始日期 (YYYY-MM-DD) |
| --end-date | -e | ✗ | 结束日期 (YYYY-MM-DD) |
| --headless/--no-headless | | ✗ | 是否使用无头模式 |
| --max-questions | -q | ✗ | 最大问题数量限制 |
| --max-answers | -a | ✗ | 每个问题的最大答案数量 |

## 技术实现

### API接口分析

根据博客分析，知乎答案数据通过以下API获取：

```
https://www.zhihu.com/api/v4/questions/{question_id}/answers
```

关键参数：
- `include`: 指定返回的数据字段
- `offset`: 分页偏移量
- `limit`: 每页答案数量
- `sort_by`: 排序方式

### 分页处理

API返回的分页信息：
```json
{
  "paging": {
    "is_end": false,
    "next": "下一页URL"
  },
  "data": [答案数据]
}
```

程序会自动处理分页，直到获取所有答案。

### 数据解析

每个答案包含的主要字段：
```json
{
  "id": "答案ID",
  "content": "答案内容HTML",
  "author": {
    "name": "作者姓名",
    "url_token": "作者标识"
  },
  "voteup_count": "点赞数",
  "comment_count": "评论数",
  "created_time": "创建时间戳",
  "updated_time": "更新时间戳"
}
```

## 使用示例

### 示例1：爬取热门问题答案

```bash
# 爬取"如何看待人工智能的发展"问题的答案
python3 postgres_main.py api-crawl-answers \
  -u "https://www.zhihu.com/question/123456789" \
  -m 100
```

### 示例2：批量爬取相关问题

```bash
# 搜索并爬取人工智能相关问题
python3 postgres_main.py hybrid-crawl \
  -k "人工智能发展趋势" \
  -q 5 \
  -a 30 \
  -s "2023-01-01" \
  -e "2023-12-31"
```

### 示例3：程序化调用

```python
from zhihu_api_crawler import ZhihuAPIAnswerCrawler

# 初始化爬虫
crawler = ZhihuAPIAnswerCrawler()

# 爬取答案
result = crawler.crawl_answers_by_question_url(
    question_url="https://www.zhihu.com/question/25038841",
    max_answers=50,
    save_to_db=True
)

print(f"获取到 {result['total_answers']} 个答案")
```

## 注意事项

### 1. 网络要求
- 需要稳定的网络连接
- 建议使用国内网络环境
- API请求有频率限制，程序已内置延时

### 2. 数据库配置
- 确保PostgreSQL数据库正常运行
- 检查数据库连接配置
- 建议定期备份数据

### 3. 使用限制
- 遵守知乎服务条款
- 合理控制爬取频率
- 仅用于学习和研究目的

### 4. 错误处理
- API连接失败时会自动重试
- 网络异常时程序会记录错误日志
- 可通过日志文件查看详细错误信息

## 性能对比

| 方式 | 速度 | 稳定性 | 完整性 | 资源占用 |
|------|------|--------|--------|----------|
| API爬取 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Selenium爬取 | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ |
| 混合模式 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |

## 故障排除

### 常见问题

1. **API连接失败**
   ```
   解决方案：检查网络连接，确认知乎网站可正常访问
   ```

2. **数据库连接错误**
   ```
   解决方案：检查PostgreSQL服务状态和连接配置
   ```

3. **问题ID提取失败**
   ```
   解决方案：确认URL格式正确，支持以下格式：
   - https://www.zhihu.com/question/123456789
   - https://www.zhihu.com/question/123456789/answer/987654321
   ```

4. **答案数量为0**
   ```
   解决方案：
   - 检查问题是否存在
   - 确认问题是否有答案
   - 查看日志了解具体错误
   ```

### 日志查看

```bash
# 查看实时日志
tail -f logs/zhihu_crawler.log

# 查看错误日志
grep "ERROR" logs/zhihu_crawler.log
```

## 更新日志

### v1.0.0 (2024-01-XX)
- ✅ 实现基于API的答案爬取功能
- ✅ 支持分页自动处理
- ✅ 集成到现有爬虫系统
- ✅ 添加混合模式爬取
- ✅ 完善错误处理和日志记录

## 参考资料

- [知乎答案抓取：解析API接口实现全量数据获取](https://blog.csdn.net/weixin_50238287/article/details/119974388)
- [知乎API文档](https://www.zhihu.com/api)
- [项目GitHub仓库](https://github.com/your-repo)

---

如有问题或建议，请提交Issue或联系开发者。