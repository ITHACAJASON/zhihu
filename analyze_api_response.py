#!/usr/bin/env python3
"""
分析知乎API响应文件的详细结构
"""

import json
import os
from pathlib import Path
from loguru import logger

def analyze_api_response_files():
    """分析API响应文件的结构"""
    output_dir = Path("output/question_378706911")

    if not output_dir.exists():
        logger.error(f"输出目录不存在: {output_dir}")
        return

    # 获取所有API响应文件
    api_files = [f for f in output_dir.iterdir() if f.name.startswith('api_response_')]
    api_files.sort()

    logger.info(f"找到 {len(api_files)} 个API响应文件")

    if not api_files:
        logger.error("没有找到API响应文件")
        return

    # 分析第一个文件
    first_file = api_files[0]
    logger.info(f"分析文件: {first_file.name}")

    with open(first_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 分析metadata结构
    metadata = data.get('metadata', {})
    logger.info("=== Metadata 结构 ===")
    for key, value in metadata.items():
        if isinstance(value, str) and len(value) > 50:
            logger.info(f"  {key}: {value[:50]}...")
        else:
            logger.info(f"  {key}: {value}")

    # 分析response结构
    response = data.get('response', {})
    logger.info("\\n=== Response 结构 ===")
    logger.info(f"  Top-level keys: {list(response.keys())}")

    # 分析data数组
    data_array = response.get('data', [])
    logger.info(f"  Data items count: {len(data_array)}")

    if data_array:
        first_answer = data_array[0]
        logger.info("\\n=== 第一个答案对象的结构 ===")
        logger.info(f"  Answer keys: {list(first_answer.keys())}")

        # 分析作者信息
        author = first_answer.get('author', {})
        logger.info(f"  Author keys: {list(author.keys())}")

        # 分析问题信息
        question = first_answer.get('question', {})
        logger.info(f"  Question keys: {list(question.keys())}")

        # 检查是否有content字段
        has_content = 'content' in first_answer
        logger.info(f"  Has content field: {has_content}")

        if has_content:
            content_length = len(first_answer.get('content', ''))
            logger.info(f"  Content length: {content_length}")
        else:
            logger.warning("  ❌ 答案对象中没有content字段！")

    # 分析paging信息
    paging = response.get('paging', {})
    logger.info("\\n=== 分页信息 ===")
    logger.info(f"  Is end: {paging.get('is_end', 'N/A')}")
    logger.info(f"  Is start: {paging.get('is_start', 'N/A')}")
    logger.info(f"  Totals: {paging.get('totals', 'N/A')}")
    logger.info(f"  Has next: {'next' in paging}")
    logger.info(f"  Has previous: {'previous' in paging}")

    # 统计信息
    logger.info("\\n=== 统计信息 ===")
    total_files = len(api_files)
    total_responses = 0
    total_answers = 0
    total_with_content = 0

    for file_path in api_files[:5]:  # 只分析前5个文件
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                file_data = json.load(f)
                file_response = file_data.get('response', {})
                file_data_array = file_response.get('data', [])
                total_responses += 1
                total_answers += len(file_data_array)

                # 检查content
                for answer in file_data_array:
                    if 'content' in answer and answer['content']:
                        total_with_content += 1

        except Exception as e:
            logger.error(f"分析文件 {file_path.name} 时出错: {e}")

    logger.info(f"分析的文件数: {total_responses}")
    logger.info(f"总答案数: {total_answers}")
    logger.info(f"有content的答案数: {total_with_content}")

if __name__ == "__main__":
    analyze_api_response_files()
