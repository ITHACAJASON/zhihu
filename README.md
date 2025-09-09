# 智能知乎爬虫系统

一个集成动态参数获取、API批量请求、监控恢复等功能的智能知乎爬虫系统。

## 🚀 系统特性

### 核心功能
- **动态参数提取** - 自动获取知乎反爬虫参数（x-zse-96, x-zst-81等）
- **参数池管理** - 智能管理和复用反爬虫参数，提高爬取效率
- **API批量请求** - 高效并发爬取，支持异步处理
- **监控恢复系统** - 实时监控系统状态，自动故障恢复
- **智能降级** - API失败时自动切换到传统浏览器方法
- **统一接口** - 命令行工具，便于使用和集成

### 技术架构
- **异步编程** - 基于asyncio和aiohttp的高性能异步架构
- **模块化设计** - 各功能模块独立，便于维护和扩展
- **数据持久化** - SQLite数据库存储参数池和统计信息
- **智能重试** - 多层重试机制，提高成功率
- **日志监控** - 完整的日志记录和监控体系

## 📦 安装依赖

```bash
pip3 install -r requirements.txt
```

## 🛠️ 使用方法

### 命令行接口

```bash
# 查看帮助
python3 main.py --help

# 爬取单个问题
python3 main.py crawl 19550225

# 批量爬取多个问题
python3 main.py batch 19550225,20000000,30000000

# 提取新的反爬虫参数
python3 main.py extract_params https://www.zhihu.com/question/19550225

# 查看参数池状态
python3 main.py pool_status

# 启动监控系统
python3 main.py monitor

# 清理过期参数
python3 main.py cleanup

# 运行系统测试
python3 main.py test
```

### 编程接口

```python
import asyncio
from smart_crawler import SmartCrawler

async def example():
    # 初始化爬虫
    crawler = SmartCrawler()
    
    # 爬取单个问题
    result = await crawler.crawl_question_feeds("19550225")
    
    if result.success:
        print(f"爬取成功: {len(result.data['data'])} 条答案")
    else:
        print(f"爬取失败: {result.error}")
    
    # 批量爬取
    results = await crawler.batch_crawl(["19550225", "20000000"])
    
    for result in results:
        if result.success:
            print(f"问题 {result.question_id}: {len(result.data['data'])} 条答案")

# 运行示例
asyncio.run(example())
```

## 📁 项目结构

```
.
├── main.py                     # 主入口脚本
├── smart_crawler.py            # 智能爬虫核心
├── dynamic_params_extractor.py # 动态参数提取器
├── params_pool_manager.py      # 参数池管理器
├── monitor_recovery.py         # 监控恢复系统
├── zhihu_lazyload_crawler.py   # 传统爬虫（降级方案）
├── zhihu_api_crawler.py        # API爬虫基础
├── config.py                   # 配置文件
├── requirements.txt            # 依赖包列表
├── demo.py                     # 系统演示脚本
└── README.md                   # 项目文档
```

## 🔧 核心模块

### SmartCrawler (智能爬虫)
- 整合所有功能的主要接口
- 支持异步并发爬取
- 智能参数管理和重试机制
- 自动降级到传统方法

### DynamicParamsExtractor (动态参数提取器)
- 使用Selenium自动化浏览器
- 监听网络请求获取反爬虫参数
- 支持多种参数提取策略

### ParamsPoolManager (参数池管理器)
- SQLite数据库存储参数
- 智能参数选择和复用
- 参数有效性跟踪
- 自动清理过期参数

### MonitorRecovery (监控恢复系统)
- 实时系统健康监控
- 自动故障检测和恢复
- 性能统计和报告

## 📊 系统监控

### 健康状态指标
- 参数池状态（总数、活跃数、成功率）
- 请求统计（总数、成功数、失败数）
- 系统性能（响应时间、并发数）
- 错误率和恢复情况

### 日志系统
- 结构化日志记录
- 多级别日志输出
- 错误追踪和调试信息

## ⚙️ 配置说明

### 主要配置项
- `max_pool_size`: 参数池最大容量（默认100）
- `max_concurrent`: 最大并发数（默认5）
- `timeout`: 请求超时时间（默认30秒）
- `retry_times`: 重试次数（默认3）

### 环境要求
- Python 3.7+
- Chrome浏览器（用于参数提取）
- 稳定的网络连接

## 🚨 注意事项

1. **合规使用**: 请遵守知乎的robots.txt和使用条款
2. **频率控制**: 建议设置合理的请求间隔，避免过于频繁的请求
3. **参数时效**: 反爬虫参数有时效性，需要定期更新
4. **错误处理**: 系统具有自动重试和降级机制，但仍需关注错误日志
5. **资源管理**: 长时间运行时注意内存和数据库文件大小

## 🔄 更新日志

### v1.0.0 (2025-09-08)
- ✅ 完成智能爬虫系统核心功能
- ✅ 集成动态参数提取器
- ✅ 实现参数池管理系统
- ✅ 添加监控恢复机制
- ✅ 提供统一命令行接口
- ✅ 完善文档和演示

## 📝 许可证

本项目仅供学习和研究使用，请勿用于商业用途。使用时请遵守相关法律法规和网站服务条款。

## 🤝 贡献

欢迎提交Issue和Pull Request来改进这个项目。

## 📞 联系

如有问题或建议，请通过Issue联系。