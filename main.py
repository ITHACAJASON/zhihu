#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import time
import logging
import signal
from typing import List, Tuple

from database import DatabaseManager
from zhihu_crawler import ZhihuCrawler
from config import (
    setup_logging, 
    get_database_config, 
    get_crawler_config
)

class ZhihuCrawlerApp:
    """知乎爬虫应用主类"""
    
    def __init__(self):
        self.db_manager = None
        self.crawler = None
        self.running = True
        
        # 设置信号处理
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        """信号处理器，用于优雅退出"""
        print("\n收到退出信号，正在安全关闭...")
        self.running = False
        self.cleanup()
        sys.exit(0)
    
    def setup(self) -> bool:
        """初始化应用"""
        try:
            # 设置日志
            setup_logging()
            logging.info("知乎爬虫应用启动")
            
            # 初始化数据库管理器
            db_config = get_database_config()
            self.db_manager = DatabaseManager(**db_config)
            
            if not self.db_manager.connect():
                logging.error("数据库连接失败")
                return False
            
            # 初始化爬虫
            crawler_config = get_crawler_config()
            self.crawler = ZhihuCrawler(
                db_manager=self.db_manager,
                headless=crawler_config['headless']
            )
            
            self.crawler.setup_driver()
            
            logging.info("应用初始化完成")
            return True
            
        except Exception as e:
            logging.error(f"应用初始化失败: {e}")
            return False
    
    def run(self):
        """运行爬虫应用"""
        try:
            if not self.setup():
                print("应用初始化失败，退出")
                return
            
            # 等待用户登录
            print("\n=== 知乎爬虫启动 ===")
            if not self.crawler.wait_for_login():
                print("用户取消登录，退出应用")
                return
            
            # 持续运行直到完成采集
            while self.running:
                # 获取待爬取的问题列表
                questions = self.get_questions_to_crawl()
                if not questions:
                    print("\n🎉 所有问题已完成采集！")
                    break
                
                print(f"\n找到 {len(questions)} 个待爬取的问题")
                
                # 开始爬取
                success = self.crawl_questions(questions)
                
                # 如果全部成功或用户中断，退出循环
                if success or not self.running:
                    break
                    
                # 如果有失败的，等待一段时间后重试
                print("\n等待 30 秒后重新检查待采集问题...")
                for i in range(30):
                    if not self.running:
                        break
                    time.sleep(0.33)
            
        except KeyboardInterrupt:
            print("\n用户中断操作")
        except Exception as e:
            logging.error(f"应用运行出错: {e}")
        finally:
            self.cleanup()
    
    def get_questions_to_crawl(self) -> List[Tuple[str, int]]:
        """获取待爬取的问题列表"""
        try:
            questions = self.db_manager.get_questions()
            
            # 过滤已完成的问题
            filtered_questions = []
            for url, answer_count in questions:
                crawled_count = self.db_manager.get_crawled_count(url)
                if crawled_count < answer_count:
                    filtered_questions.append((url, answer_count))
                    logging.info(f"问题 {url}: 目标 {answer_count} 个回答，已爬取 {crawled_count} 个")
                else:
                    logging.info(f"问题 {url} 已完成爬取")
            
            return filtered_questions
            
        except Exception as e:
            logging.error(f"获取问题列表失败: {e}")
            return []
    
    def crawl_questions(self, questions: List[Tuple[str, int]]) -> bool:
        """批量爬取问题"""
        total_questions = len(questions)
        success_count = 0
        total_answers = 0
        start_time = time.time()
        
        print(f"\n=== 开始采集 {total_questions} 个问题 ===")
        
        for i, (url, target_count) in enumerate(questions, 1):
            if not self.running:
                break
                
            current_time = time.time()
            elapsed_time = current_time - start_time
            
            print(f"\n[{i}/{total_questions}] 开始采集问题: {url}")
            print(f"目标回答数: {target_count}, 已用时: {elapsed_time:.1f}秒")
            
            try:
                # 检查已爬取数量
                crawled_count = self.db_manager.get_crawled_count(url)
                remaining_count = target_count - crawled_count
                
                if remaining_count <= 0:
                    print(f"✅ 问题已完成采集，跳过")
                    success_count += 1
                    total_answers += crawled_count
                    continue
                
                print(f"已采集: {crawled_count}，还需采集: {remaining_count}")
                
                # 开始爬取
                question_start_time = time.time()
                new_crawled = self.crawler.crawl_question_answers(url, target_count)
                question_end_time = time.time()
                
                # 统计结果
                total_crawled = self.db_manager.get_crawled_count(url)
                completion_rate = (total_crawled / target_count) * 100
                
                if total_crawled >= target_count:
                    print(f"✅ 采集完成！")
                    success_count += 1
                else:
                    print(f"⚠️  部分完成")
                    
                print(f"本次新增: {new_crawled} 个回答")
                print(f"总计采集: {total_crawled} 个回答")
                print(f"完成度: {completion_rate:.1f}%")
                print(f"耗时: {question_end_time - question_start_time:.1f} 秒")
                
                total_answers += total_crawled
                
                # 显示实时进度
                progress = (i / total_questions) * 100
                print(f"总进度: {progress:.1f}% ({i}/{total_questions}), 成功: {success_count}, 总回答数: {total_answers}")
                
                # 问题间隔已取消，直接继续下一个问题
                    
            except Exception as e:
                logging.error(f"爬取问题 {url} 失败: {e}")
                print(f"❌ 采集失败: {e}")
                continue
        
        # 最终统计
        total_time = time.time() - start_time
        print(f"\n=== 本轮采集完成 ===")
        print(f"总问题数: {total_questions}")
        print(f"成功采集: {success_count}")
        print(f"失败数量: {total_questions - success_count}")
        print(f"总回答数: {total_answers}")
        print(f"总用时: {total_time:.1f} 秒")
        if total_questions > 0:
            print(f"平均每个问题: {total_time/total_questions:.1f} 秒")
        
        self.print_summary(questions)
        
        # 返回是否全部成功
        return success_count == total_questions
    
    def print_summary(self, questions: List[Tuple[str, int]]):
        """打印爬取总结"""
        print("\n=== 爬取总结 ===")
        
        total_target = 0
        total_crawled = 0
        completed_questions = 0
        
        for url, target_count in questions:
            crawled_count = self.db_manager.get_crawled_count(url)
            total_target += target_count
            total_crawled += crawled_count
            
            if crawled_count >= target_count:
                completed_questions += 1
            
            completion_rate = (crawled_count / target_count) * 100
            status = "✓" if crawled_count >= target_count else "○"
            print(f"{status} {url}: {crawled_count}/{target_count} ({completion_rate:.1f}%)")
        
        overall_completion = (total_crawled / total_target) * 100 if total_target > 0 else 0
        
        print(f"\n总体统计:")
        print(f"问题总数: {len(questions)}")
        print(f"完成问题: {completed_questions}")
        print(f"目标回答总数: {total_target}")
        print(f"实际爬取总数: {total_crawled}")
        print(f"总体完成度: {overall_completion:.1f}%")
    
    def cleanup(self):
        """清理资源"""
        try:
            if self.crawler:
                self.crawler.close()
            
            if self.db_manager:
                self.db_manager.disconnect()
            
            logging.info("资源清理完成")
            
        except Exception as e:
            logging.error(f"资源清理失败: {e}")

def main():
    """主函数"""
    app = ZhihuCrawlerApp()
    app.run()

if __name__ == "__main__":
    main()