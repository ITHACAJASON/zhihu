#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能知乎爬虫系统演示

展示系统的主要功能：
1. 参数池管理
2. 智能爬虫初始化
3. 监控系统
4. API请求构建
"""

import asyncio
import json
from loguru import logger
from smart_crawler import SmartCrawler
from params_pool_manager import ParamsPoolManager
from monitor_recovery import MonitorRecovery
import time

async def demo_system():
    """演示智能爬虫系统"""
    logger.info("🚀 智能知乎爬虫系统演示开始")
    logger.info("="*60)
    
    # 1. 参数池管理演示
    logger.info("📦 1. 参数池管理系统")
    manager = ParamsPoolManager("demo_params.db")
    
    # 添加示例参数
    demo_params = {
        'x_zse_96': "2.0_demo_x_zse_96_value",
        'x_zst_81': "demo_x_zst_81_value", 
        'session_id': "demo_session_id_12345",
        'user_agent': "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        'referer': "https://www.zhihu.com/question/19550225",
        'question_id': "19550225",
        'timestamp': time.time()
    }
    
    success = manager.add_params(demo_params)
    if success:
        stats = manager.get_pool_stats()
        logger.info(f"✅ 参数添加成功，池统计: {stats}")
    else:
        logger.warning("⚠️ 参数添加失败（可能已存在）")
    
    # 2. 智能爬虫系统演示
    logger.info("\n🤖 2. 智能爬虫系统")
    crawler = SmartCrawler("demo_params.db")
    
    # 显示系统状态
    logger.info(f"✅ 智能爬虫初始化完成")
    logger.info(f"   - 参数池管理器: 已连接")
    logger.info(f"   - 传统爬虫: 已初始化")
    logger.info(f"   - 最大并发数: {crawler.max_concurrent}")
    logger.info(f"   - API基础URL: {crawler.base_url}")
    
    # 显示统计信息
    stats = crawler.get_stats()
    logger.info(f"   - 当前统计: {stats}")
    
    # 3. 监控系统演示
    logger.info("\n📊 3. 监控恢复系统")
    monitor = MonitorRecovery("demo_params.db")
    
    health_report = monitor.get_health_report()
    logger.info(f"✅ 系统健康报告: {json.dumps(health_report, ensure_ascii=False, indent=2)}")
    
    # 4. API请求构建演示
    logger.info("\n🔗 4. API请求构建")
    question_id = "19550225"
    
    # 构建API URL和参数
    url = f"{crawler.base_url}/{question_id}/answers"
    api_params = {
        'include': 'data[*].is_normal,content,voteup_count,created_time,updated_time,author.follower_count',
        'limit': 20,
        'offset': 0,
        'platform': 'desktop',
        'sort_by': 'default'
    }
    
    logger.info(f"✅ API URL: {url}")
    logger.info(f"✅ 请求参数: {json.dumps(api_params, ensure_ascii=False, indent=2)}")
    
    # 5. 系统功能总结
    logger.info("\n" + "="*60)
    logger.info("📋 系统功能总结")
    logger.info("="*60)
    
    features = [
        "✅ 动态参数提取 - 自动获取反爬虫参数",
        "✅ 参数池管理 - 智能管理和复用参数",
        "✅ API批量请求 - 高效并发爬取",
        "✅ 监控恢复系统 - 实时监控和自动恢复",
        "✅ 智能降级 - API失败时自动切换传统方法",
        "✅ 统一接口 - 命令行工具便于使用"
    ]
    
    for feature in features:
        logger.info(f"  {feature}")
    
    # 6. 使用示例
    logger.info("\n🛠️ 使用示例")
    logger.info("="*60)
    
    examples = [
        "# 爬取单个问题",
        "python3 main.py crawl 19550225",
        "",
        "# 批量爬取多个问题", 
        "python3 main.py batch 19550225,20000000,30000000",
        "",
        "# 提取新参数",
        "python3 main.py extract_params https://www.zhihu.com/question/19550225",
        "",
        "# 查看参数池状态",
        "python3 main.py pool_status",
        "",
        "# 启动监控",
        "python3 main.py monitor",
        "",
        "# 运行测试",
        "python3 main.py test"
    ]
    
    for example in examples:
        if example.startswith("#"):
            logger.info(f"\n{example}")
        elif example == "":
            continue
        else:
            logger.info(f"  {example}")
    
    logger.info("\n🎉 智能知乎爬虫系统演示完成！")
    
    # 清理演示数据
    import os
    if os.path.exists("demo_params.db"):
        os.remove("demo_params.db")
        logger.info("🧹 清理演示数据完成")

if __name__ == "__main__":
    asyncio.run(demo_system())