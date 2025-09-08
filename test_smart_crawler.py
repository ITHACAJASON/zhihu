#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能爬虫系统集成测试

测试动态参数获取+API批量请求的完整流程
"""

import asyncio
import time
import json
from pathlib import Path
from loguru import logger
import sys
import os

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from smart_crawler import SmartCrawler
from monitor_recovery import MonitorRecovery
from params_pool_manager import ParamsPoolManager
from dynamic_params_extractor import DynamicParamsExtractor


class SmartCrawlerTester:
    """智能爬虫测试器"""
    
    def __init__(self):
        self.test_results = {
            'total_tests': 0,
            'passed_tests': 0,
            'failed_tests': 0,
            'test_details': []
        }
        
    def log_test_result(self, test_name: str, success: bool, message: str = "", data: dict = None):
        """记录测试结果"""
        self.test_results['total_tests'] += 1
        
        if success:
            self.test_results['passed_tests'] += 1
            logger.info(f"✅ {test_name}: {message}")
        else:
            self.test_results['failed_tests'] += 1
            logger.error(f"❌ {test_name}: {message}")
            
        self.test_results['test_details'].append({
            'test_name': test_name,
            'success': success,
            'message': message,
            'data': data or {},
            'timestamp': time.time()
        })
        
    async def test_params_extractor(self) -> bool:
        """测试参数提取器"""
        logger.info("🧪 测试参数提取器...")
        
        try:
            # 使用一个知名问题进行测试
            test_question_id = "19550225"  # 知乎经典问题
            
            with DynamicParamsExtractor(headless=True) as extractor:
                params = extractor.extract_params_from_question(test_question_id)
                
                if params:
                    # 验证参数
                    is_valid = extractor.validate_params(params)
                    
                    self.log_test_result(
                        "参数提取器", 
                        is_valid,
                        f"成功提取并验证参数" if is_valid else "参数验证失败",
                        {'question_id': test_question_id, 'params_keys': list(params.keys())}
                    )
                    return is_valid
                else:
                    self.log_test_result("参数提取器", False, "未能提取到参数")
                    return False
                    
        except Exception as e:
            self.log_test_result("参数提取器", False, f"测试异常: {e}")
            return False
            
    def test_params_pool_manager(self) -> bool:
        """测试参数池管理器"""
        logger.info("🧪 测试参数池管理器...")
        
        try:
            # 创建临时数据库
            test_db_path = "test_params_pool.db"
            
            manager = ParamsPoolManager(test_db_path, max_pool_size=10)
            
            # 测试添加参数
            test_params = {
                'x_zse_96': '2.0_test_value',
                'x_zst_81': '3_2.0_test_value',
                'session_id': 'test_session_id',
                'user_agent': 'test_user_agent',
                'referer': 'https://www.zhihu.com/question/123456',
                'question_id': '123456',
                'timestamp': time.time()
            }
            
            # 添加参数
            add_success = manager.add_params(test_params)
            
            # 获取参数
            params_record = manager.get_best_params()
            
            # 标记使用
            if params_record:
                manager.mark_params_used(params_record.id, True)
                
            # 获取统计
            stats = manager.get_pool_stats()
            
            # 清理测试数据库
            Path(test_db_path).unlink(missing_ok=True)
            
            success = add_success and params_record is not None and stats['total_count'] > 0
            
            self.log_test_result(
                "参数池管理器", 
                success,
                f"参数池操作{'成功' if success else '失败'}",
                {'stats': stats}
            )
            
            return success
            
        except Exception as e:
            self.log_test_result("参数池管理器", False, f"测试异常: {e}")
            return False
            
    async def test_smart_crawler_basic(self) -> bool:
        """测试智能爬虫基本功能"""
        logger.info("🧪 测试智能爬虫基本功能...")
        
        try:
            test_db_path = "test_smart_crawler.db"
            
            async with SmartCrawler(
                params_db_path=test_db_path,
                max_pool_size=5,
                max_concurrent=2
            ) as crawler:
                
                # 测试单个问题爬取
                test_question_id = "19550225"
                result = await crawler.crawl_question_feeds(test_question_id, limit=5)
                
                # 获取统计信息
                stats = crawler.get_stats()
                
                # 清理测试数据库
                Path(test_db_path).unlink(missing_ok=True)
                
                self.log_test_result(
                    "智能爬虫基本功能", 
                    result.success,
                    f"爬取{'成功' if result.success else '失败'}: {result.error or '正常'}",
                    {
                        'question_id': test_question_id,
                        'response_time': result.response_time,
                        'stats': stats
                    }
                )
                
                return result.success
                
        except Exception as e:
            self.log_test_result("智能爬虫基本功能", False, f"测试异常: {e}")
            return False
            
    async def test_smart_crawler_batch(self) -> bool:
        """测试智能爬虫批量功能"""
        logger.info("🧪 测试智能爬虫批量功能...")
        
        try:
            test_db_path = "test_batch_crawler.db"
            
            # 测试问题列表
            test_question_ids = [
                "19550225",  # 知乎经典问题
                "20831813",  # 另一个问题
                "21362402"   # 第三个问题
            ]
            
            async with SmartCrawler(
                params_db_path=test_db_path,
                max_pool_size=5,
                max_concurrent=2
            ) as crawler:
                
                # 进度回调
                progress_data = []
                
                def progress_callback(current, total, result):
                    progress_data.append({
                        'current': current,
                        'total': total,
                        'success': result.success,
                        'question_id': result.question_id
                    })
                    logger.info(f"📋 进度: {current}/{total} - {result.question_id} {'✅' if result.success else '❌'}")
                    
                # 批量爬取
                results = await crawler.batch_crawl(
                    test_question_ids, 
                    limit=5,
                    progress_callback=progress_callback
                )
                
                # 统计结果
                successful_count = sum(1 for r in results if r.success)
                total_count = len(results)
                
                # 获取统计信息
                stats = crawler.get_stats()
                
                # 清理测试数据库
                Path(test_db_path).unlink(missing_ok=True)
                
                success = successful_count > 0
                
                self.log_test_result(
                    "智能爬虫批量功能", 
                    success,
                    f"批量爬取完成: {successful_count}/{total_count} 成功",
                    {
                        'total_questions': total_count,
                        'successful_questions': successful_count,
                        'progress_data': progress_data,
                        'stats': stats
                    }
                )
                
                return success
                
        except Exception as e:
            self.log_test_result("智能爬虫批量功能", False, f"测试异常: {e}")
            return False
            
    def test_monitor_recovery(self) -> bool:
        """测试监控恢复系统"""
        logger.info("🧪 测试监控恢复系统...")
        
        try:
            test_db_path = "test_monitor.db"
            
            # 创建参数池管理器
            params_manager = ParamsPoolManager(test_db_path, max_pool_size=5)
            
            # 创建监控系统
            monitor = MonitorRecovery(
                params_manager=params_manager,
                monitor_interval=5,  # 5秒间隔用于测试
                recovery_enabled=True
            )
            
            # 记录一些测试数据
            monitor.record_request(True, 1.5)
            monitor.record_request(False, 2.0)
            monitor.record_request(True, 1.2)
            
            # 获取健康度报告
            health_report = monitor.get_health_report()
            
            # 启动监控（短时间）
            monitor.start_monitoring()
            time.sleep(10)  # 运行10秒
            monitor.stop_monitoring()
            
            # 导出指标
            metrics_file = "test_metrics.json"
            export_success = monitor.export_metrics(metrics_file)
            
            # 清理文件
            Path(test_db_path).unlink(missing_ok=True)
            Path(metrics_file).unlink(missing_ok=True)
            
            success = health_report['status'] != 'no_data' and export_success
            
            self.log_test_result(
                "监控恢复系统", 
                success,
                f"监控系统{'正常' if success else '异常'}",
                {'health_report': health_report}
            )
            
            return success
            
        except Exception as e:
            self.log_test_result("监控恢复系统", False, f"测试异常: {e}")
            return False
            
    async def run_integration_test(self) -> bool:
        """运行完整集成测试"""
        logger.info("🚀 开始智能爬虫系统集成测试")
        
        # 测试列表
        tests = [
            ("参数池管理器", self.test_params_pool_manager),
            ("监控恢复系统", self.test_monitor_recovery),
            ("智能爬虫基本功能", self.test_smart_crawler_basic),
            ("智能爬虫批量功能", self.test_smart_crawler_batch),
            # 参数提取器测试放在最后，因为需要浏览器
            ("参数提取器", self.test_params_extractor),
        ]
        
        # 执行测试
        for test_name, test_func in tests:
            logger.info(f"\n{'='*50}")
            logger.info(f"🧪 开始测试: {test_name}")
            
            try:
                if asyncio.iscoroutinefunction(test_func):
                    await test_func()
                else:
                    test_func()
            except Exception as e:
                self.log_test_result(test_name, False, f"测试执行异常: {e}")
                
            logger.info(f"✅ 完成测试: {test_name}")
            
        # 输出测试总结
        self.print_test_summary()
        
        return self.test_results['failed_tests'] == 0
        
    def print_test_summary(self):
        """打印测试总结"""
        logger.info(f"\n{'='*60}")
        logger.info("📊 测试总结")
        logger.info(f"{'='*60}")
        
        total = self.test_results['total_tests']
        passed = self.test_results['passed_tests']
        failed = self.test_results['failed_tests']
        
        logger.info(f"总测试数: {total}")
        logger.info(f"通过测试: {passed} ✅")
        logger.info(f"失败测试: {failed} ❌")
        logger.info(f"成功率: {(passed/total*100):.1f}%" if total > 0 else "成功率: 0%")
        
        if failed > 0:
            logger.info("\n❌ 失败的测试:")
            for detail in self.test_results['test_details']:
                if not detail['success']:
                    logger.error(f"  - {detail['test_name']}: {detail['message']}")
                    
        logger.info(f"\n{'='*60}")
        
        # 保存详细结果
        with open('test_results.json', 'w', encoding='utf-8') as f:
            json.dump(self.test_results, f, indent=2, ensure_ascii=False)
            
        logger.info("📄 详细测试结果已保存到 test_results.json")


async def main():
    """主函数"""
    # 配置日志
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO"
    )
    
    # 创建测试器
    tester = SmartCrawlerTester()
    
    try:
        # 运行集成测试
        success = await tester.run_integration_test()
        
        if success:
            logger.info("🎉 所有测试通过！智能爬虫系统运行正常")
            return 0
        else:
            logger.error("💥 部分测试失败，请检查系统配置")
            return 1
            
    except KeyboardInterrupt:
        logger.warning("⚠️ 测试被用户中断")
        return 1
    except Exception as e:
        logger.error(f"❌ 测试过程中发生异常: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)