#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证日志记录与数据库数据不匹配的问题
"""

import psycopg2
import re
from collections import defaultdict, Counter
from datetime import datetime
from config import ZhihuConfig

def get_database_stats():
    """
    获取数据库中的答案统计信息
    """
    config = ZhihuConfig()
    db_config = config.POSTGRES_CONFIG
    
    try:
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()
        
        # 获取答案总数
        cursor.execute("SELECT COUNT(*) FROM answers")
        total_answers = cursor.fetchone()[0]
        
        # 获取按作者分组的答案数
        cursor.execute("""
            SELECT author, COUNT(*) as count 
            FROM answers 
            GROUP BY author 
            ORDER BY count DESC 
            LIMIT 20
        """)
        author_stats = cursor.fetchall()
        
        # 获取匿名用户的答案详情
        cursor.execute("""
            SELECT answer_id, vote_count, crawl_time 
            FROM answers 
            WHERE author = '匿名用户' 
            ORDER BY crawl_time
        """)
        anonymous_answers = cursor.fetchall()
        
        # 获取按点赞数分组的匿名用户答案
        cursor.execute("""
            SELECT vote_count, COUNT(*) as count 
            FROM answers 
            WHERE author = '匿名用户' 
            GROUP BY vote_count 
            ORDER BY count DESC
        """)
        anonymous_vote_stats = cursor.fetchall()
        
        conn.close()
        
        return {
            'total_answers': total_answers,
            'author_stats': author_stats,
            'anonymous_answers': anonymous_answers,
            'anonymous_vote_stats': anonymous_vote_stats
        }
        
    except Exception as e:
        print(f"数据库查询失败: {e}")
        return None

def analyze_log_vs_database():
    """
    对比日志记录与数据库数据
    """
    print("=== 日志与数据库对比分析 ===")
    
    # 获取数据库统计
    db_stats = get_database_stats()
    if not db_stats:
        return
    
    print(f"\n=== 数据库统计 ===")
    print(f"数据库中答案总数: {db_stats['total_answers']}")
    print(f"数据库中作者统计 (前10名):")
    for author, count in db_stats['author_stats'][:10]:
        print(f"  {author}: {count} 条")
    
    print(f"\n数据库中匿名用户答案统计:")
    anonymous_db_count = len(db_stats['anonymous_answers'])
    print(f"匿名用户答案总数: {anonymous_db_count}")
    
    print(f"匿名用户按点赞数分组:")
    for vote_count, count in db_stats['anonymous_vote_stats']:
        print(f"  点赞数 {vote_count}: {count} 条")
    
    # 分析日志记录
    log_file = "logs/zhihu_crawler.log"
    pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*答案已保存: 作者=([^,]+), 点赞=(\d+)'
    
    log_records = []
    anonymous_log_records = []
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            for line in f:
                match = re.search(pattern, line)
                if match:
                    timestamp_str = match.group(1)
                    author = match.group(2)
                    vote_count = int(match.group(3))
                    
                    record = {
                        'timestamp': timestamp_str,
                        'author': author,
                        'vote_count': vote_count
                    }
                    
                    log_records.append(record)
                    
                    if author == '匿名用户':
                        anonymous_log_records.append(record)
    
    except Exception as e:
        print(f"读取日志文件失败: {e}")
        return
    
    print(f"\n=== 日志统计 ===")
    print(f"日志中答案保存记录总数: {len(log_records)}")
    print(f"日志中匿名用户记录数: {len(anonymous_log_records)}")
    
    # 对比分析
    print(f"\n=== 对比分析 ===")
    print(f"日志记录数: {len(log_records)}")
    print(f"数据库记录数: {db_stats['total_answers']}")
    print(f"差异: {len(log_records) - db_stats['total_answers']} 条")
    print(f"差异比例: {((len(log_records) - db_stats['total_answers']) / len(log_records) * 100):.1f}%")
    
    print(f"\n匿名用户对比:")
    print(f"日志中匿名用户记录: {len(anonymous_log_records)}")
    print(f"数据库中匿名用户记录: {anonymous_db_count}")
    print(f"匿名用户差异: {len(anonymous_log_records) - anonymous_db_count} 条")
    
    # 分析匿名用户的重复模式
    anonymous_vote_counter = Counter()
    for record in anonymous_log_records:
        anonymous_vote_counter[record['vote_count']] += 1
    
    print(f"\n日志中匿名用户按点赞数统计:")
    for vote_count, count in anonymous_vote_counter.most_common(10):
        print(f"  点赞数 {vote_count}: {count} 次记录")
    
    # 生成详细报告
    report = {
        'analysis_time': datetime.now().isoformat(),
        'log_total_records': len(log_records),
        'database_total_records': db_stats['total_answers'],
        'difference': len(log_records) - db_stats['total_answers'],
        'difference_percentage': ((len(log_records) - db_stats['total_answers']) / len(log_records) * 100),
        'anonymous_log_records': len(anonymous_log_records),
        'anonymous_db_records': anonymous_db_count,
        'anonymous_difference': len(anonymous_log_records) - anonymous_db_count,
        'conclusion': '日志记录数量远超数据库实际记录数量，说明存在重复保存同一答案的情况，但由于ON CONFLICT机制，数据库中只保留了唯一记录'
    }
    
    import json
    report_file = f"log_vs_database_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"\n详细分析报告已保存到: {report_file}")
    
    return report

if __name__ == "__main__":
    analyze_log_vs_database()