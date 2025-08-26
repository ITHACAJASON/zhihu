# 知乎API爬虫方法

## 📋 完成状态

✅ **API认证问题已解决**
✅ **数据解析逻辑已完善**
✅ **集成到主流程**
✅ **完整测试通过**

## 🚀 使用方法

### 1. 测试API连接

```bash
# 测试API连接是否正常
python3 zhihu_api_main.py test
```

### 2. 爬取单个问题答案

```bash
# 使用API方法爬取指定问题的所有答案
python3 zhihu_api_main.py crawl --question-url "https://www.zhihu.com/question/354793553"

# 限制答案数量
python3 zhihu_api_main.py crawl --question-url "https://www.zhihu.com/question/354793553" --max-answers 10

# 指定任务ID
python3 zhihu_api_main.py crawl --question-url "https://www.zhihu.com/question/354793553" --task-id "my_task"
```

### 3. 批量爬取

```bash
# 批量爬取多个问题的答案
python3 zhihu_api_main.py batch --question-urls "https://www.zhihu.com/question/123" "https://www.zhihu.com/question/456"

# 限制每个问题的答案数量
python3 zhihu_api_main.py batch --question-urls "https://www.zhihu.com/question/123" --max-answers 5
```

### 4. 在Python代码中使用

```python
from zhihu_api_main import ZhihuAPIMain

# 初始化
crawler = ZhihuAPIMain()

# 爬取单个问题
result = crawler.crawl_question_answers_api(
    question_url="https://www.zhihu.com/question/354793553",
    max_answers=10
)

print(f"获取到 {result['total_answers']} 个答案")

# 批量爬取
results = crawler.batch_crawl_answers_api(
    question_urls=["https://www.zhihu.com/question/123", "https://www.zhihu.com/question/456"],
    max_answers_per_question=5
)
```

## 🛠️ 技术特性

### ✅ 核心功能
- **完整的API认证** - 使用真实的浏览器cookies和请求头
- **智能数据解析** - 自动处理feeds端点的数据结构
- **分页支持** - 自动获取所有答案页面
- **错误重试** - 网络异常自动重试机制
- **数据库集成** - 自动保存到PostgreSQL数据库

### ✅ 技术优势
- ⚡ **速度快** - 直接调用API，无需解析HTML
- 🎯 **数据完整** - 获取结构化答案数据
- 🔄 **稳定性高** - API接口相对稳定
- 📊 **易于分析** - JSON格式数据便于处理

### ✅ 安全特性
- 🛡️ **真实请求头** - 模拟真实浏览器请求
- 🔐 **Cookies管理** - 自动加载和更新cookies
- 🚦 **频率控制** - 内置延时避免请求过快
- 📝 **日志记录** - 详细的操作日志

## 📁 文件结构

```
zhihu/
├── zhihu_api_main.py          # API爬虫主程序
├── zhihu_api_crawler.py       # API爬虫核心逻辑
├── demo_api_crawler.py        # API功能演示
├── check_api_cookies.py       # API连接测试
├── test_direct_access.py      # 直接页面访问测试
├── cookies/zhihu_cookies.json # 浏览器cookies
└── cache/zhihu_cookies.pkl    # 序列化cookies
```

## 🔧 配置说明

### Cookies更新
当遇到403错误时，需要更新cookies：

```bash
# 1. 在浏览器中访问知乎并登录
# 2. 按F12打开开发者工具
# 3. 访问任意知乎问题页面
# 4. 复制Network标签页中API请求的完整cookies
# 5. 更新 cookies/zhihu_cookies.json 文件
# 6. 运行更新脚本：
python3 -c "
import json
import pickle
import os

# 读取JSON cookies
with open('cookies/zhihu_cookies.json', 'r', encoding='utf-8') as f:
    cookies_data = json.load(f)

# 转换为pickle格式
os.makedirs('cache', exist_ok=True)
with open('cache/zhihu_cookies.pkl', 'wb') as f:
    pickle.dump(cookies_data, f)

print('✓ Cookies已更新')
"
```

### 数据库配置
确保PostgreSQL数据库已配置：

```python
# 在 config.py 中设置数据库连接信息
POSTGRES_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'zhihu_crawler',
    'user': 'your_username',
    'password': 'your_password'
}
```

## 📊 API数据结构

### 请求参数
```javascript
{
  "include": "data[*].is_normal,admin_closed_comment,reward_info,...",
  "offset": "",
  "limit": "20",
  "order": "default",
  "ws_qiangzhisafe": "0",
  "platform": "desktop",
  "session_id": "1756125566118409"
}
```

### 响应结构
```javascript
{
  "data": [
    {
      "target_type": "answer",
      "target": {
        "id": "答案ID",
        "content": "答案内容HTML",
        "author": {
          "name": "作者姓名",
          "url_token": "作者标识"
        },
        "created_time": 时间戳,
        "voteup_count": 点赞数,
        "comment_count": 评论数
      }
    }
  ],
  "paging": {
    "is_end": false,
    "next": "下一页URL"
  }
}
```

## 🔍 故障排除

### 常见问题

1. **403 Forbidden错误**
   - 检查cookies是否过期
   - 更新 `cookies/zhihu_cookies.json`
   - 重新生成pickle文件

2. **返回空数据**
   - 可能是问题已被删除或无公开答案
   - 检查问题URL是否正确
   - 尝试其他问题测试

3. **网络超时**
   - 检查网络连接
   - 程序会自动重试失败的请求

### 调试方法

```bash
# 查看详细日志
tail -f logs/zhihu_crawler.log

# 测试单个API调用
python3 check_api_cookies.py

# 演示功能
python3 demo_api_crawler.py
```

## 🎯 使用建议

1. **定期更新cookies** - 避免认证过期
2. **合理设置延时** - 避免请求过于频繁
3. **监控日志** - 及时发现和解决问题
4. **数据备份** - 定期备份数据库中的数据

## 📈 性能对比

| 特性 | Selenium方法 | API方法 |
|------|-------------|---------|
| 速度 | 🐌 较慢 | ⚡ 很快 |
| 稳定性 | 🎯 一般 | 🔒 高 |
| 数据完整性 | 📊 一般 | 🎯 高 |
| 维护成本 | 🔧 高 | ⚙️ 低 |
| 反爬虫风险 | 🛡️ 高 | 🛡️ 低 |

## 🔄 集成到现有系统

API方法可以与现有的Selenium方法混合使用：

```python
from api_integration import IntegratedZhihuCrawler

# 使用混合模式：Selenium搜索 + API获取答案
crawler = IntegratedZhihuCrawler(
    headless=True,
    use_api_for_answers=True  # 启用API答案获取
)

result = crawler.crawl_by_keyword_hybrid(
    keyword="人工智能",
    max_questions=5,
    max_answers_per_question=10
)
```

---

🎉 **API方法开发完成！** 现在你拥有了一个功能完整、高效稳定的知乎答案爬虫！

