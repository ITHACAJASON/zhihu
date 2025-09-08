#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
监控与自动恢复模块

实时监控爬虫状态、参数池健康度，并提供自动恢复机制
"""

import time
import asyncio
import threading
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from loguru import logger
import json
from pathlib import Path

from params_pool_manager import ParamsPoolManager
# from dynamic_params_extractor import DynamicParamsExtractor  # 延迟导入避免循环依赖


@dataclass
class HealthMetrics:
    """健康度指标"""
    timestamp: float = field(default_factory=time.time)
    pool_size: int = 0
    fresh_params_count: int = 0
    avg_success_rate: float = 0.0
    recent_success_rate: float = 0.0
    extraction_success_rate: float = 0.0
    avg_response_time: float = 0.0
    error_rate: float = 0.0
    
    @property
    def overall_health_score(self) -> float:
        """综合健康度评分 (0-100)"""
        scores = [
            min(self.pool_size / 10, 1.0) * 20,  # 参数池大小 (20分)
            min(self.fresh_params_count / 5, 1.0) * 15,  # 新鲜参数数量 (15分)
            self.avg_success_rate * 25,  # 平均成功率 (25分)
            self.recent_success_rate * 20,  # 近期成功率 (20分)
            self.extraction_success_rate * 10,  # 提取成功率 (10分)
            max(0, 1 - self.error_rate) * 10  # 错误率 (10分)
        ]
        return sum(scores)
        
    @property
    def health_level(self) -> str:
        """健康度等级"""
        score = self.overall_health_score
        if score >= 80:
            return "优秀"
        elif score >= 60:
            return "良好"
        elif score >= 40:
            return "一般"
        elif score >= 20:
            return "较差"
        else:
            return "危险"


@dataclass
class AlertRule:
    """告警规则"""
    name: str
    condition: Callable[[HealthMetrics], bool]
    message: str
    level: str = "warning"  # info, warning, error, critical
    cooldown: int = 300  # 冷却时间（秒）
    last_triggered: float = 0.0
    
    def should_trigger(self, metrics: HealthMetrics) -> bool:
        """是否应该触发告警"""
        if time.time() - self.last_triggered < self.cooldown:
            return False
        return self.condition(metrics)
        
    def trigger(self, metrics: HealthMetrics):
        """触发告警"""
        self.last_triggered = time.time()
        logger.log(self.level.upper(), f"🚨 {self.name}: {self.message}")


class MonitorRecovery:
    """监控与自动恢复系统"""
    
    def __init__(self, 
                 params_manager: ParamsPoolManager,
                 monitor_interval: int = 60,
                 recovery_enabled: bool = True,
                 metrics_history_size: int = 100):
        """
        初始化监控系统
        
        Args:
            params_manager: 参数池管理器
            monitor_interval: 监控间隔（秒）
            recovery_enabled: 是否启用自动恢复
            metrics_history_size: 指标历史记录大小
        """
        self.params_manager = params_manager
        self.monitor_interval = monitor_interval
        self.recovery_enabled = recovery_enabled
        self.metrics_history_size = metrics_history_size
        
        # 监控状态
        self.is_monitoring = False
        self.monitor_thread = None
        
        # 指标历史
        self.metrics_history: List[HealthMetrics] = []
        
        # 统计数据
        self.request_stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'total_response_time': 0.0,
            'extraction_attempts': 0,
            'extraction_successes': 0
        }
        
        # 告警规则
        self.alert_rules = self._init_alert_rules()
        
        # 恢复策略
        self.recovery_strategies = {
            'low_pool_size': self._recover_low_pool_size,
            'high_error_rate': self._recover_high_error_rate,
            'no_fresh_params': self._recover_no_fresh_params,
            'low_success_rate': self._recover_low_success_rate
        }
        
    def _init_alert_rules(self) -> List[AlertRule]:
        """初始化告警规则"""
        return [
            AlertRule(
                name="参数池容量不足",
                condition=lambda m: m.pool_size < 3,
                message="参数池容量不足，可能影响爬取效率",
                level="warning"
            ),
            AlertRule(
                name="无新鲜参数",
                condition=lambda m: m.fresh_params_count == 0,
                message="参数池中无新鲜参数，需要立即补充",
                level="error"
            ),
            AlertRule(
                name="成功率过低",
                condition=lambda m: m.recent_success_rate < 0.5,
                message="近期成功率过低，请检查参数有效性",
                level="warning"
            ),
            AlertRule(
                name="错误率过高",
                condition=lambda m: m.error_rate > 0.3,
                message="错误率过高，可能存在系统问题",
                level="error"
            ),
            AlertRule(
                name="参数提取失败",
                condition=lambda m: m.extraction_success_rate < 0.3 and m.extraction_success_rate > 0,
                message="参数提取成功率过低，请检查浏览器配置",
                level="warning"
            ),
            AlertRule(
                name="系统健康度危险",
                condition=lambda m: m.overall_health_score < 20,
                message="系统健康度处于危险状态，需要立即处理",
                level="critical"
            )
        ]
        
    def start_monitoring(self):
        """开始监控"""
        if self.is_monitoring:
            logger.warning("⚠️ 监控已在运行中")
            return
            
        self.is_monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info(f"🔍 监控系统已启动，间隔: {self.monitor_interval}秒")
        
    def stop_monitoring(self):
        """停止监控"""
        self.is_monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("🔒 监控系统已停止")
        
    def _monitor_loop(self):
        """监控循环"""
        while self.is_monitoring:
            try:
                # 收集指标
                metrics = self._collect_metrics()
                
                # 记录历史
                self._record_metrics(metrics)
                
                # 检查告警
                self._check_alerts(metrics)
                
                # 自动恢复
                if self.recovery_enabled:
                    self._auto_recovery(metrics)
                    
                # 输出状态
                self._log_status(metrics)
                
            except Exception as e:
                logger.error(f"❌ 监控循环出错: {e}")
                
            time.sleep(self.monitor_interval)
            
    def _collect_metrics(self) -> HealthMetrics:
        """收集健康度指标"""
        # 获取参数池统计
        pool_stats = self.params_manager.get_pool_stats()
        
        # 计算近期成功率
        recent_success_rate = self._calculate_recent_success_rate()
        
        # 计算平均响应时间
        avg_response_time = self._calculate_avg_response_time()
        
        # 计算错误率
        error_rate = self._calculate_error_rate()
        
        # 计算提取成功率
        extraction_success_rate = self._calculate_extraction_success_rate()
        
        return HealthMetrics(
            pool_size=pool_stats['active_count'],
            fresh_params_count=pool_stats['fresh_count'],
            avg_success_rate=pool_stats['avg_success_rate'],
            recent_success_rate=recent_success_rate,
            extraction_success_rate=extraction_success_rate,
            avg_response_time=avg_response_time,
            error_rate=error_rate
        )
        
    def _calculate_recent_success_rate(self) -> float:
        """计算近期成功率（最近10分钟）"""
        if len(self.metrics_history) < 2:
            return 1.0
            
        recent_metrics = [m for m in self.metrics_history[-10:] if time.time() - m.timestamp < 600]
        if not recent_metrics:
            return 1.0
            
        total_requests = sum(getattr(m, 'total_requests', 0) for m in recent_metrics)
        successful_requests = sum(getattr(m, 'successful_requests', 0) for m in recent_metrics)
        
        if total_requests == 0:
            return 1.0
            
        return successful_requests / total_requests
        
    def _calculate_avg_response_time(self) -> float:
        """计算平均响应时间"""
        if self.request_stats['total_requests'] == 0:
            return 0.0
        return self.request_stats['total_response_time'] / self.request_stats['total_requests']
        
    def _calculate_error_rate(self) -> float:
        """计算错误率"""
        total = self.request_stats['total_requests']
        if total == 0:
            return 0.0
        return self.request_stats['failed_requests'] / total
        
    def _calculate_extraction_success_rate(self) -> float:
        """计算参数提取成功率"""
        attempts = self.request_stats['extraction_attempts']
        if attempts == 0:
            return 1.0
        return self.request_stats['extraction_successes'] / attempts
        
    def _record_metrics(self, metrics: HealthMetrics):
        """记录指标历史"""
        self.metrics_history.append(metrics)
        
        # 保持历史记录大小
        if len(self.metrics_history) > self.metrics_history_size:
            self.metrics_history = self.metrics_history[-self.metrics_history_size:]
            
    def _check_alerts(self, metrics: HealthMetrics):
        """检查告警"""
        for rule in self.alert_rules:
            if rule.should_trigger(metrics):
                rule.trigger(metrics)
                
    def _auto_recovery(self, metrics: HealthMetrics):
        """自动恢复"""
        # 参数池容量不足
        if metrics.pool_size < 3:
            self.recovery_strategies['low_pool_size'](metrics)
            
        # 无新鲜参数
        if metrics.fresh_params_count == 0:
            self.recovery_strategies['no_fresh_params'](metrics)
            
        # 错误率过高
        if metrics.error_rate > 0.5:
            self.recovery_strategies['high_error_rate'](metrics)
            
        # 成功率过低
        if metrics.recent_success_rate < 0.3:
            self.recovery_strategies['low_success_rate'](metrics)
            
    def _recover_low_pool_size(self, metrics: HealthMetrics):
        """恢复参数池容量不足"""
        logger.info("🔧 执行恢复策略: 补充参数池")
        
        try:
            # 清理过期参数
            cleaned = self.params_manager.cleanup_expired_params()
            logger.info(f"🧹 清理了 {cleaned} 个过期参数")
            
            # 触发参数提取（异步）
            threading.Thread(
                target=self._extract_params_async, 
                args=("popular_question",), 
                daemon=True
            ).start()
            
        except Exception as e:
            logger.error(f"❌ 参数池恢复失败: {e}")
            
    def _recover_high_error_rate(self, metrics: HealthMetrics):
        """恢复高错误率"""
        logger.info("🔧 执行恢复策略: 处理高错误率")
        
        try:
            # 禁用失败率高的参数
            # 这里可以添加更复杂的逻辑
            pass
            
        except Exception as e:
            logger.error(f"❌ 错误率恢复失败: {e}")
            
    def _recover_no_fresh_params(self, metrics: HealthMetrics):
        """恢复无新鲜参数"""
        logger.info("🔧 执行恢复策略: 获取新鲜参数")
        
        try:
            # 立即提取新参数
            threading.Thread(
                target=self._extract_params_async, 
                args=("trending_question",), 
                daemon=True
            ).start()
            
        except Exception as e:
            logger.error(f"❌ 新鲜参数恢复失败: {e}")
            
    def _recover_low_success_rate(self, metrics: HealthMetrics):
        """恢复低成功率"""
        logger.info("🔧 执行恢复策略: 提升成功率")
        
        try:
            # 清理失败率高的参数
            # 重新提取参数
            pass
            
        except Exception as e:
            logger.error(f"❌ 成功率恢复失败: {e}")
            
    def _extract_params_async(self, question_type: str):
        """异步提取参数"""
        try:
            # 延迟导入避免循环依赖
            from dynamic_params_extractor import DynamicParamsExtractor
            
            # 这里可以根据question_type选择不同的问题
            question_ids = ["123456789", "987654321"]  # 示例问题ID
            
            with DynamicParamsExtractor(headless=True) as extractor:
                for question_id in question_ids:
                    self.request_stats['extraction_attempts'] += 1
                    
                    params = extractor.extract_params_from_question(question_id)
                    if params:
                        params['question_id'] = question_id
                        if self.params_manager.add_params(params):
                            self.request_stats['extraction_successes'] += 1
                            logger.info(f"✅ 成功提取并添加参数: {question_id}")
                            
                    time.sleep(2)  # 避免过于频繁
                    
        except Exception as e:
            logger.error(f"❌ 异步参数提取失败: {e}")
            
    def _log_status(self, metrics: HealthMetrics):
        """输出状态日志"""
        logger.info(
            f"📊 系统状态 - 健康度: {metrics.health_level}({metrics.overall_health_score:.1f}), "
            f"参数池: {metrics.pool_size}, 新鲜: {metrics.fresh_params_count}, "
            f"成功率: {metrics.recent_success_rate:.2%}, 错误率: {metrics.error_rate:.2%}"
        )
        
    def record_request(self, success: bool, response_time: float = 0.0):
        """记录请求统计"""
        self.request_stats['total_requests'] += 1
        self.request_stats['total_response_time'] += response_time
        
        if success:
            self.request_stats['successful_requests'] += 1
        else:
            self.request_stats['failed_requests'] += 1
            
    def get_health_report(self) -> Dict:
        """获取健康度报告"""
        if not self.metrics_history:
            return {'status': 'no_data'}
            
        latest_metrics = self.metrics_history[-1]
        
        # 计算趋势
        trend = self._calculate_trend()
        
        return {
            'timestamp': latest_metrics.timestamp,
            'health_score': latest_metrics.overall_health_score,
            'health_level': latest_metrics.health_level,
            'metrics': {
                'pool_size': latest_metrics.pool_size,
                'fresh_params_count': latest_metrics.fresh_params_count,
                'avg_success_rate': latest_metrics.avg_success_rate,
                'recent_success_rate': latest_metrics.recent_success_rate,
                'extraction_success_rate': latest_metrics.extraction_success_rate,
                'avg_response_time': latest_metrics.avg_response_time,
                'error_rate': latest_metrics.error_rate
            },
            'trend': trend,
            'request_stats': self.request_stats.copy()
        }
        
    def _calculate_trend(self) -> str:
        """计算健康度趋势"""
        if len(self.metrics_history) < 2:
            return "stable"
            
        recent_scores = [m.overall_health_score for m in self.metrics_history[-5:]]
        
        if len(recent_scores) < 2:
            return "stable"
            
        # 简单的趋势计算
        avg_early = sum(recent_scores[:len(recent_scores)//2]) / (len(recent_scores)//2)
        avg_late = sum(recent_scores[len(recent_scores)//2:]) / (len(recent_scores) - len(recent_scores)//2)
        
        diff = avg_late - avg_early
        
        if diff > 5:
            return "improving"
        elif diff < -5:
            return "declining"
        else:
            return "stable"
            
    def export_metrics(self, file_path: str) -> bool:
        """导出指标历史"""
        try:
            data = {
                'export_time': time.time(),
                'metrics_history': [
                    {
                        'timestamp': m.timestamp,
                        'pool_size': m.pool_size,
                        'fresh_params_count': m.fresh_params_count,
                        'avg_success_rate': m.avg_success_rate,
                        'recent_success_rate': m.recent_success_rate,
                        'extraction_success_rate': m.extraction_success_rate,
                        'avg_response_time': m.avg_response_time,
                        'error_rate': m.error_rate,
                        'health_score': m.overall_health_score,
                        'health_level': m.health_level
                    }
                    for m in self.metrics_history
                ],
                'request_stats': self.request_stats
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
            logger.info(f"✅ 指标历史已导出到 {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 导出指标历史失败: {e}")
            return False