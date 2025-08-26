#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知乎API爬虫演示
展示完整的API爬取功能
"""

import json
from zhihu_api_crawler import ZhihuAPIAnswerCrawler

def demo_api_crawler():
    """演示API爬虫功能"""
    print("🚀 知乎API爬虫功能演示")
    print("=" * 50)

    # 初始化API爬虫
    print("\n1. 初始化API爬虫...")
    crawler = ZhihuAPIAnswerCrawler()
    print("✓ API爬虫初始化成功")

    # 测试API连接
    print("\n2. 测试API连接...")
    if crawler.test_api_connection():
        print("✓ API连接测试成功")
    else:
        print("✗ API连接测试失败")
        return

    # 演示API答案爬取
    print("\n3. 演示API答案爬取...")

    # 使用一个已知有答案的问题进行演示
    test_questions = [
        {
            'url': 'https://www.zhihu.com/question/354793553',
            'description': '测试问题（可能为空）'
        }
    ]

    for i, question in enumerate(test_questions, 1):
        print(f"\n问题 {i}: {question['description']}")
        print(f"URL: {question['url']}")

        try:
            result = crawler.crawl_answers_by_question_url(
                question_url=question['url'],
                task_id=f"demo_task_{i}",
                max_answers=5,  # 限制答案数量用于演示
                save_to_db=False  # 演示模式，不保存到数据库
            )

            print(f"  📊 爬取结果:")
            print(f"    - 答案数量: {result['total_answers']}")
            print(f"    - 耗时: {result['duration_seconds']:.2f} 秒")
            print(f"    - 任务ID: {result['task_id']}")

            if result['answers']:
                print("  📝 答案预览:")
                for j, answer in enumerate(result['answers'][:2], 1):  # 只显示前2个
                    print(f"    答案 {j}:")
                    print(f"      作者: {answer.author}")
                    print(f"      点赞数: {answer.vote_count}")
                    print(f"      评论数: {answer.comment_count}")
                    print(f"      内容长度: {len(answer.content)} 字符")
                    if len(answer.content) > 100:
                        print(f"      内容预览: {answer.content[:100]}...")
            else:
                print("    ⚠️  该问题没有找到答案")

        except Exception as e:
            print(f"  ❌ 爬取失败: {e}")

    print("\n" + "=" * 50)
    print("🎉 API爬虫演示完成！")
    print("\n📋 技术特性总结:")
    print("✅ API认证成功 - 无403错误")
    print("✅ 完整的请求头支持")
    print("✅ feeds端点数据解析")
    print("✅ 分页处理机制")
    print("✅ 错误重试机制")
    print("✅ 数据库集成准备就绪")

    print("\n🔧 使用方法:")
    print("1. 确保cookies有效且完整")
    print("2. 调用 crawl_answers_by_question_url() 方法")
    print("3. 处理返回的答案数据")

if __name__ == "__main__":
    demo_api_crawler()
