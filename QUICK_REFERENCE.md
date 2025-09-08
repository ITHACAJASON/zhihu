# ⚡ crawl_specific_question.py 快速参考

## 🚀 快速开始

### 1. 参数验证
```bash
python3 validate_crawl_params.py
# 选择: 3 (交互式验证)
```

### 2. 单问题采集
```python
# 编辑 crawl_specific_question.py 中的参数:
question_url = "https://www.zhihu.com/question/YOUR_ID"
task_name = "your_task_name"
max_answers = 1000  # 或 None

# 运行
python3 crawl_specific_question.py
```

### 3. 批量采集
```python
# 编辑 batch_crawl_example.py 中的配置:
questions_config = [
    {
        "url": "https://www.zhihu.com/question/378706911",
        "task_name": "question_378706911_full",
        "max_answers": None
    }
]

# 运行
python3 batch_crawl_example.py
```

## 📋 参数速查

### 必需参数
- `question_url`: 知乎问题URL (必须)
- `task_name`: 任务名称 (可选，默认: "specific_question_crawl")
- `max_answers`: 最大答案数 (可选，默认: None)

### URL格式
```python
# ✅ 正确格式
"https://www.zhihu.com/question/378706911/answer/1080446596"
"https://www.zhihu.com/question/378706911"
"https://www.zhihu.com/question/378706911?sort=created"

# ❌ 错误格式
"https://www.zhihu.com"  # 缺少question路径
"378706911"             # 不是完整URL
```

## 🎯 常用命令

### 验证环境
```bash
python3 validate_crawl_params.py
```

### 单问题采集
```bash
python3 crawl_specific_question.py
```

### 批量采集
```bash
python3 batch_crawl_questions.py          # 数据库驱动
python3 batch_crawl_example.py            # 示例配置
python3 batch_crawl_questions_enhanced.py # 增强版
```

### 故障排除
```bash
python3 resolve_verification.py           # 解决403错误
python3 update_cookies_manual.py          # 更新cookies
```

## 📊 性能参考

| 问题规模 | 答案数 | 建议max_answers | 预计时间 |
|---------|-------|----------------|---------|
| 小问题 | < 100 | None | 1-2分钟 |
| 中等问题 | 100-1000 | 1000 | 5-15分钟 |
| 大问题 | > 1000 | None | 30-60分钟 |

## ⚠️ 重要提醒

### ✅ 必须检查
- [ ] PostgreSQL数据库已启动
- [ ] cookies文件存在且有效 (`cache/zhihu_cookies.pkl`)
- [ ] output目录存在且可写
- [ ] 网络连接正常

### 🔄 定期维护
- [ ] 每周更新cookies
- [ ] 监控磁盘空间
- [ ] 定期备份数据库
- [ ] 清理旧的输出文件

## 📁 输出文件结构

```
output/
├── question_378706911/           # 问题专用目录
│   ├── api_response_page_*.json  # API响应文件
│   └── crawl_summary.json        # 采集摘要
├── batch_crawl/                  # 批量采集目录
│   ├── question_*/               # 各问题目录
│   └── batch_crawl_summary_*.json
└── batch_crawl_enhanced/         # 增强版目录
```

## 🔍 监控和调试

### 查看日志
```bash
tail -f crawler.log              # 实时日志
cat crawler.log | grep ERROR     # 查看错误
```

### 检查数据库
```python
from postgres_models import PostgreSQLManager
db = PostgreSQLManager()

# 查看总答案数
cursor = db.db.cursor()
cursor.execute("SELECT COUNT(*) FROM answers")
print("总答案数:", cursor.fetchone()[0])
```

### 检查输出文件
```bash
# 查看最新的输出
ls -lt output/ | head -10

# 检查文件大小
du -sh output/question_*/

# 验证JSON文件
python3 -m json.tool output/question_*/api_response_page_1*.json
```

## 🎯 最佳实践

### 1. 渐进式采集
```python
# 先测试小问题
result = crawler.crawl_all_answers(max_answers=10)

# 再采集中等规模
result = crawler.crawl_all_answers(max_answers=100)

# 最后采集全部
result = crawler.crawl_all_answers(max_answers=None)
```

### 2. 分批处理
```python
# 按时间分批
morning_batch = ["question_378706911", "question_457478394"]
afternoon_batch = ["question_37197524", "question_67330244"]
```

### 3. 监控资源
```bash
# 内存使用
ps aux | grep python | grep -v grep

# 磁盘使用
df -h

# 网络连接
ping -c 3 www.zhihu.com
```

## 🆘 紧急情况处理

### 程序卡住
```bash
# 查找进程
ps aux | grep python

# 终止进程
kill -9 PROCESS_ID

# 清理临时文件
find output/ -name "*.tmp" -delete
```

### 数据库错误
```bash
# 重启数据库
sudo systemctl restart postgresql

# 检查连接
python3 -c "from postgres_models import PostgreSQLManager; print('OK' if PostgreSQLManager().db else 'FAIL')"
```

### 网络错误
```bash
# 测试网络
curl -I https://www.zhihu.com

# 更换网络或使用代理
# 更新hosts文件
```

## 📞 快速帮助

### 问题诊断流程
1. **运行验证**: `python3 validate_crawl_params.py`
2. **检查日志**: `tail -f crawler.log`
3. **测试连接**: `curl -I https://www.zhihu.com/api/v4/questions/378706911/answers`
4. **检查数据库**: 查看PostgreSQL状态
5. **验证cookies**: 检查cookies文件

### 常见错误及解决

| 错误 | 原因 | 解决方法 |
|-----|-----|---------|
| 403错误 | cookies过期/反爬 | `python3 resolve_verification.py` |
| 连接错误 | 网络问题 | 检查网络连接 |
| 磁盘错误 | 空间不足 | 清理output目录 |
| 数据库错误 | 服务未启动 | 重启PostgreSQL |

---

*快速参考版本: 1.0*
*更新日期: 2025-01-26*
