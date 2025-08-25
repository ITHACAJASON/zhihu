#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知乎爬虫数据修复脚本
用于修复数据库中问题与答案数量不匹配的问题

主要功能：
1. 修复questions表中answer_count字段
2. 修复search_results表中answer_count字段
3. 生成数据修复报告
4. 验证修复结果
"""

import psycopg2
import json
from datetime import datetime
from typing import Dict, List, Tuple
from config import ZhihuConfig
from postgres_models import PostgreSQLManager

class DataFixer:
    def __init__(self):
        self.config = ZhihuConfig()
        self.db = PostgreSQLManager(self.config.POSTGRES_CONFIG)
        self.fix_report = {
            'start_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'questions_fixed': 0,
            'search_results_fixed': 0,
            'orphaned_answers': 0,
            'questions_without_answers': 0,
            'details': []
        }
    
    def get_connection(self):
        """获取数据库连接"""
        return psycopg2.connect(
            host=self.config.POSTGRES_CONFIG['host'],
            port=self.config.POSTGRES_CONFIG['port'],
            database=self.config.POSTGRES_CONFIG['database'],
            user=self.config.POSTGRES_CONFIG['user'],
            password=self.config.POSTGRES_CONFIG['password']
        )
    
    def analyze_current_state(self) -> Dict:
        """分析当前数据状态"""
        print("=== 分析当前数据状态 ===")
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 统计基本信息
            cursor.execute("SELECT COUNT(*) FROM task_info")
            total_tasks = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM search_results")
            total_search_results = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM questions")
            total_questions = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM answers")
            total_answers = cursor.fetchone()[0]
            
            # 统计问题
            cursor.execute("""
                SELECT COUNT(*) FROM questions WHERE answer_count = 0
            """)
            questions_with_zero_count = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT COUNT(*) FROM search_results WHERE answer_count = 0
            """)
            search_results_with_zero_count = cursor.fetchone()[0]
            
            # 统计没有答案的问题
            cursor.execute("""
                SELECT COUNT(*) 
                FROM questions q 
                LEFT JOIN answers a ON q.question_id = a.question_id 
                WHERE a.answer_id IS NULL
            """)
            questions_without_answers = cursor.fetchone()[0]
            
            # 统计孤立的答案
            cursor.execute("""
                SELECT COUNT(*) 
                FROM answers a 
                LEFT JOIN questions q ON a.question_id = q.question_id 
                WHERE q.question_id IS NULL
            """)
            orphaned_answers = cursor.fetchone()[0]
            
            state = {
                'total_tasks': total_tasks,
                'total_search_results': total_search_results,
                'total_questions': total_questions,
                'total_answers': total_answers,
                'questions_with_zero_count': questions_with_zero_count,
                'search_results_with_zero_count': search_results_with_zero_count,
                'questions_without_answers': questions_without_answers,
                'orphaned_answers': orphaned_answers
            }
            
            print(f"任务总数: {total_tasks}")
            print(f"搜索结果总数: {total_search_results}")
            print(f"问题总数: {total_questions}")
            print(f"答案总数: {total_answers}")
            print(f"答案数量为0的问题: {questions_with_zero_count}")
            print(f"答案数量为0的搜索结果: {search_results_with_zero_count}")
            print(f"没有答案的问题: {questions_without_answers}")
            print(f"孤立的答案: {orphaned_answers}")
            
            return state
    
    def fix_questions_answer_count(self) -> int:
        """修复questions表中的answer_count字段"""
        print("\n=== 修复问题表中的答案数量 ===")
        
        fixed_count = 0
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 获取所有需要修复的问题
            cursor.execute("""
                SELECT 
                    q.question_id,
                    q.task_id,
                    q.title,
                    q.answer_count as current_count,
                    COUNT(a.answer_id) as actual_count
                FROM questions q
                LEFT JOIN answers a ON q.question_id = a.question_id AND q.task_id = a.task_id
                GROUP BY q.question_id, q.task_id, q.title, q.answer_count
                HAVING q.answer_count != COUNT(a.answer_id)
                ORDER BY COUNT(a.answer_id) DESC
            """)
            
            questions_to_fix = cursor.fetchall()
            
            print(f"发现 {len(questions_to_fix)} 个需要修复的问题")
            
            for question in questions_to_fix:
                question_id, task_id, title, current_count, actual_count = question
                
                # 更新答案数量
                cursor.execute("""
                    UPDATE questions 
                    SET answer_count = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE question_id = %s AND task_id = %s
                """, (actual_count, question_id, task_id))
                
                fixed_count += 1
                
                detail = {
                    'type': 'question_fix',
                    'question_id': question_id,
                    'task_id': task_id,
                    'title': title[:50] + '...' if len(title) > 50 else title,
                    'old_count': current_count,
                    'new_count': actual_count
                }
                self.fix_report['details'].append(detail)
                
                print(f"修复问题 {question_id}: {current_count} -> {actual_count} ({title[:30]}...)")
            
            conn.commit()
            
        print(f"问题表修复完成，共修复 {fixed_count} 条记录")
        return fixed_count
    
    def fix_search_results_answer_count(self) -> int:
        """修复search_results表中的answer_count字段"""
        print("\n=== 修复搜索结果表中的答案数量 ===")
        
        fixed_count = 0
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 获取所有需要修复的搜索结果
            cursor.execute("""
                SELECT 
                    sr.result_id,
                    sr.task_id,
                    sr.question_id,
                    sr.title,
                    sr.answer_count as current_count,
                    COUNT(a.answer_id) as actual_count
                FROM search_results sr
                LEFT JOIN answers a ON sr.question_id = a.question_id AND sr.task_id = a.task_id
                GROUP BY sr.result_id, sr.task_id, sr.question_id, sr.title, sr.answer_count
                HAVING sr.answer_count != COUNT(a.answer_id)
                ORDER BY COUNT(a.answer_id) DESC
            """)
            
            results_to_fix = cursor.fetchall()
            
            print(f"发现 {len(results_to_fix)} 个需要修复的搜索结果")
            
            for result in results_to_fix:
                result_id, task_id, question_id, title, current_count, actual_count = result
                
                # 更新答案数量
                cursor.execute("""
                    UPDATE search_results 
                    SET answer_count = %s
                    WHERE result_id = %s AND task_id = %s
                """, (actual_count, result_id, task_id))
                
                fixed_count += 1
                
                detail = {
                    'type': 'search_result_fix',
                    'result_id': result_id,
                    'task_id': task_id,
                    'question_id': question_id,
                    'title': title[:50] + '...' if len(title) > 50 else title,
                    'old_count': current_count,
                    'new_count': actual_count
                }
                self.fix_report['details'].append(detail)
                
                print(f"修复搜索结果 {result_id}: {current_count} -> {actual_count} ({title[:30]}...)")
            
            conn.commit()
            
        print(f"搜索结果表修复完成，共修复 {fixed_count} 条记录")
        return fixed_count
    
    def identify_data_issues(self) -> Dict:
        """识别数据问题"""
        print("\n=== 识别数据问题 ===")
        
        issues = {
            'orphaned_answers': [],
            'questions_without_answers': [],
            'duplicate_questions': [],
            'duplicate_answers': []
        }
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 查找孤立的答案
            cursor.execute("""
                SELECT a.answer_id, a.question_id, a.task_id, a.author
                FROM answers a 
                LEFT JOIN questions q ON a.question_id = q.question_id AND a.task_id = q.task_id
                WHERE q.question_id IS NULL
                LIMIT 10
            """)
            
            orphaned = cursor.fetchall()
            for answer in orphaned:
                issues['orphaned_answers'].append({
                    'answer_id': answer[0],
                    'question_id': answer[1],
                    'task_id': answer[2],
                    'author': answer[3]
                })
            
            # 查找没有答案的问题
            cursor.execute("""
                SELECT q.question_id, q.task_id, q.title
                FROM questions q 
                LEFT JOIN answers a ON q.question_id = a.question_id AND q.task_id = a.task_id
                WHERE a.answer_id IS NULL
                LIMIT 10
            """)
            
            no_answers = cursor.fetchall()
            for question in no_answers:
                issues['questions_without_answers'].append({
                    'question_id': question[0],
                    'task_id': question[1],
                    'title': question[2]
                })
            
            # 查找重复的问题
            cursor.execute("""
                SELECT question_id, COUNT(*) as count
                FROM questions
                GROUP BY question_id
                HAVING COUNT(*) > 1
                LIMIT 10
            """)
            
            duplicates = cursor.fetchall()
            for dup in duplicates:
                issues['duplicate_questions'].append({
                    'question_id': dup[0],
                    'count': dup[1]
                })
            
            # 查找重复的答案
            cursor.execute("""
                SELECT answer_id, COUNT(*) as count
                FROM answers
                GROUP BY answer_id
                HAVING COUNT(*) > 1
                LIMIT 10
            """)
            
            dup_answers = cursor.fetchall()
            for dup in dup_answers:
                issues['duplicate_answers'].append({
                    'answer_id': dup[0],
                    'count': dup[1]
                })
        
        # 输出问题统计
        print(f"孤立答案: {len(issues['orphaned_answers'])}")
        print(f"无答案问题: {len(issues['questions_without_answers'])}")
        print(f"重复问题: {len(issues['duplicate_questions'])}")
        print(f"重复答案: {len(issues['duplicate_answers'])}")
        
        return issues
    
    def generate_report(self) -> str:
        """生成修复报告"""
        self.fix_report['end_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        report_filename = f"data_fix_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(report_filename, 'w', encoding='utf-8') as f:
            json.dump(self.fix_report, f, ensure_ascii=False, indent=2)
        
        print(f"\n=== 修复报告已生成: {report_filename} ===")
        print(f"修复开始时间: {self.fix_report['start_time']}")
        print(f"修复结束时间: {self.fix_report['end_time']}")
        print(f"修复的问题数: {self.fix_report['questions_fixed']}")
        print(f"修复的搜索结果数: {self.fix_report['search_results_fixed']}")
        print(f"总修复项目数: {len(self.fix_report['details'])}")
        
        return report_filename
    
    def verify_fix_results(self) -> bool:
        """验证修复结果"""
        print("\n=== 验证修复结果 ===")
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 检查是否还有答案数量不匹配的问题
            cursor.execute("""
                SELECT COUNT(*)
                FROM questions q
                LEFT JOIN (
                    SELECT question_id, task_id, COUNT(*) as actual_count
                    FROM answers
                    GROUP BY question_id, task_id
                ) a ON q.question_id = a.question_id AND q.task_id = a.task_id
                WHERE COALESCE(q.answer_count, 0) != COALESCE(a.actual_count, 0)
            """)
            
            remaining_issues = cursor.fetchone()[0]
            
            if remaining_issues == 0:
                print("✅ 所有问题的答案数量已修复完成")
                return True
            else:
                print(f"❌ 仍有 {remaining_issues} 个问题的答案数量不匹配")
                return False
    
    def run_full_fix(self):
        """执行完整的数据修复流程"""
        print("开始执行知乎爬虫数据修复...")
        print("=" * 50)
        
        # 1. 分析当前状态
        initial_state = self.analyze_current_state()
        
        # 2. 识别数据问题
        issues = self.identify_data_issues()
        
        # 3. 修复问题表
        questions_fixed = self.fix_questions_answer_count()
        self.fix_report['questions_fixed'] = questions_fixed
        
        # 4. 修复搜索结果表
        search_results_fixed = self.fix_search_results_answer_count()
        self.fix_report['search_results_fixed'] = search_results_fixed
        
        # 5. 记录问题统计
        self.fix_report['orphaned_answers'] = len(issues['orphaned_answers'])
        self.fix_report['questions_without_answers'] = len(issues['questions_without_answers'])
        
        # 6. 验证修复结果
        success = self.verify_fix_results()
        
        # 7. 生成报告
        report_file = self.generate_report()
        
        print("\n" + "=" * 50)
        if success:
            print("🎉 数据修复完成！所有答案数量已正确更新。")
        else:
            print("⚠️ 数据修复完成，但仍有部分问题需要手动处理。")
        
        print(f"详细报告请查看: {report_file}")
        
        return success

def main():
    """主函数"""
    try:
        fixer = DataFixer()
        fixer.run_full_fix()
    except Exception as e:
        print(f"修复过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()