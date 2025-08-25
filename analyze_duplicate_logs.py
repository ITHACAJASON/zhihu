#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析日志中重复答案保存记录的脚本
"""

import re
import json
from collections import defaultdict, Counter
from datetime import datetime

def analyze_log_duplicates():
    """
    分析日志文件中的重复答案保存记录
    """
    log_file = "logs/zhihu_crawler.log"
    
    # 存储答案保存记录
    answer_saves = []
    author_stats = Counter()
    
    # 正则表达式匹配答案保存日志
    pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*答案已保存: 作者=([^,]+), 点赞=(\d+)'
    
    print("正在分析日志文件...")
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                match = re.search(pattern, line)
                if match:
                    timestamp_str = match.group(1)
                    author = match.group(2)
                    vote_count = int(match.group(3))
                    
                    answer_saves.append({
                        'line_num': line_num,
                        'timestamp': timestamp_str,
                        'author': author,
                        'vote_count': vote_count
                    })
                    
                    author_stats[author] += 1
    
    except FileNotFoundError:
        print(f"错误: 找不到日志文件 {log_file}")
        return
    except Exception as e:
        print(f"读取日志文件时出错: {e}")
        return
    
    print(f"\n=== 日志分析结果 ===")
    print(f"总答案保存记录数: {len(answer_saves)}")
    print(f"不同作者数量: {len(author_stats)}")
    
    print(f"\n=== 作者答案保存次数统计 (前20名) ===")
    for author, count in author_stats.most_common(20):
        print(f"{author}: {count} 次")
    
    # 分析匿名用户的记录
    anonymous_records = [record for record in answer_saves if record['author'] == '匿名用户']
    print(f"\n=== 匿名用户分析 ===")
    print(f"匿名用户总记录数: {len(anonymous_records)}")
    
    if anonymous_records:
        # 按点赞数分组
        vote_groups = defaultdict(list)
        for record in anonymous_records:
            vote_groups[record['vote_count']].append(record)
        
        print(f"匿名用户按点赞数分组:")
        for vote_count, records in sorted(vote_groups.items()):
            print(f"  点赞数 {vote_count}: {len(records)} 条记录")
            if len(records) > 1:
                print(f"    可能重复: {len(records)} 条相同点赞数的记录")
    
    # 检查时间模式
    print(f"\n=== 时间模式分析 ===")
    if answer_saves:
        first_record = answer_saves[0]
        last_record = answer_saves[-1]
        print(f"第一条记录时间: {first_record['timestamp']}")
        print(f"最后一条记录时间: {last_record['timestamp']}")
        
        # 分析时间间隔
        time_intervals = []
        for i in range(1, min(100, len(answer_saves))):
            try:
                prev_time = datetime.strptime(answer_saves[i-1]['timestamp'], '%Y-%m-%d %H:%M:%S,%f')
                curr_time = datetime.strptime(answer_saves[i]['timestamp'], '%Y-%m-%d %H:%M:%S,%f')
                interval = (curr_time - prev_time).total_seconds()
                time_intervals.append(interval)
            except:
                continue
        
        if time_intervals:
            avg_interval = sum(time_intervals) / len(time_intervals)
            print(f"前100条记录的平均时间间隔: {avg_interval:.2f} 秒")
    
    # 生成分析报告
    report = {
        'analysis_time': datetime.now().isoformat(),
        'total_log_records': len(answer_saves),
        'unique_authors': len(author_stats),
        'top_authors': dict(author_stats.most_common(10)),
        'anonymous_user_records': len(anonymous_records),
        'potential_duplicates': sum(1 for count in author_stats.values() if count > 10)
    }
    
    report_file = f"log_analysis_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"\n分析报告已保存到: {report_file}")
    
    return report

if __name__ == "__main__":
    analyze_log_duplicates()