#!/usr/bin/env python3
"""
验证crawl_specific_question.py的参数配置
在运行批量采集前进行参数检查和预览
"""

import re
from typing import List, Dict, Optional
from urllib.parse import urlparse, parse_qs
from zhihu_api_crawler import ZhihuAPIAnswerCrawler
from postgres_models import PostgreSQLManager


class CrawlParamsValidator:
    """参数验证器"""

    def __init__(self):
        self.api_crawler = ZhihuAPIAnswerCrawler()
        self.db_manager = PostgreSQLManager()

    def extract_question_id(self, url: str) -> Optional[str]:
        """从URL提取问题ID"""
        return self.api_crawler.extract_question_id_from_url(url)

    def validate_url_format(self, url: str) -> Dict[str, any]:
        """验证URL格式"""
        result = {
            "valid": False,
            "question_id": None,
            "url_type": None,
            "warnings": [],
            "errors": []
        }

        if not url:
            result["errors"].append("URL不能为空")
            return result

        # 检查是否是知乎域名
        if "zhihu.com" not in url:
            result["errors"].append("URL必须是知乎域名")
            return result

        # 检查是否包含question路径
        if "/question/" not in url:
            result["errors"].append("URL必须包含/question/路径")
            return result

        # 提取问题ID
        question_id = self.extract_question_id(url)
        if not question_id:
            result["errors"].append("无法从URL提取问题ID")
            return result

        # 检查问题ID格式
        if not question_id.isdigit():
            result["errors"].append("问题ID必须是纯数字")
            return result

        result["question_id"] = question_id
        result["valid"] = True

        # 确定URL类型
        if "/answer/" in url:
            result["url_type"] = "完整答案链接"
        else:
            result["url_type"] = "问题链接"

        # 检查是否有额外参数
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        if query_params:
            result["warnings"].append(f"URL包含查询参数: {query_params}")

        return result

    def validate_task_name(self, task_name: str) -> Dict[str, any]:
        """验证任务名称"""
        result = {
            "valid": True,
            "suggestions": [],
            "warnings": []
        }

        if not task_name:
            result["valid"] = False
            result["errors"] = ["任务名称不能为空"]
            return result

        # 检查长度
        if len(task_name) > 100:
            result["warnings"].append("任务名称过长(建议不超过100字符)")

        # 检查特殊字符
        if re.search(r'[<>:"/\\|?*]', task_name):
            result["warnings"].append("任务名称包含特殊字符(建议避免<>:\"/\\|?*)")

        # 提供建议
        if not task_name.startswith("question_"):
            result["suggestions"].append("建议以'question_'开头便于识别")

        return result

    def check_database_connection(self) -> Dict[str, any]:
        """检查数据库连接"""
        result = {
            "connected": False,
            "tables_exist": False,
            "warnings": []
        }

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                result["connected"] = True

                # 检查表是否存在
                cursor.execute("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name IN ('questions', 'answers', 'task_info')
                """)

                existing_tables = [row[0] for row in cursor.fetchall()]
                required_tables = {'questions', 'answers', 'task_info'}

                if required_tables.issubset(set(existing_tables)):
                    result["tables_exist"] = True
                else:
                    missing_tables = required_tables - set(existing_tables)
                    result["warnings"].append(f"缺少表: {missing_tables}")

        except Exception as e:
            result["warnings"].append(f"数据库连接失败: {e}")

        return result

    def validate_config(self, config: Dict) -> Dict[str, any]:
        """验证完整配置"""
        result = {
            "valid": False,
            "url_validation": None,
            "task_validation": None,
            "db_validation": None,
            "errors": [],
            "warnings": [],
            "suggestions": []
        }

        # 验证URL
        url = config.get("url")
        if not url:
            result["errors"].append("配置中缺少'url'参数")
            return result

        url_result = self.validate_url_format(url)
        result["url_validation"] = url_result

        if not url_result["valid"]:
            result["errors"].extend(url_result["errors"])
        else:
            result["warnings"].extend(url_result["warnings"])

        # 验证任务名称
        task_name = config.get("task_name", "")
        task_result = self.validate_task_name(task_name)
        result["task_validation"] = task_result

        if not task_result["valid"]:
            result["errors"].extend(task_result.get("errors", []))
        else:
            result["warnings"].extend(task_result["warnings"])
            result["suggestions"].extend(task_result["suggestions"])

        # 检查数据库
        db_result = self.check_database_connection()
        result["db_validation"] = db_result

        if not db_result["connected"]:
            result["errors"].extend(db_result["warnings"])
        elif not db_result["tables_exist"]:
            result["warnings"].extend(db_result["warnings"])

        # 最终验证结果
        result["valid"] = (
            url_result["valid"] and
            task_result["valid"] and
            db_result["connected"] and
            db_result["tables_exist"]
        )

        return result


def validate_single_config():
    """验证单个配置"""
    print("单个配置参数验证")
    print("="*50)

    # 示例配置
    config = {
        "url": "https://www.zhihu.com/question/378706911/answer/1080446596",
        "task_name": "question_378706911_full_crawl",
        "max_answers": 1000
    }

    validator = CrawlParamsValidator()
    result = validator.validate_config(config)

    print(f"配置验证结果: {'✅ 通过' if result['valid'] else '❌ 失败'}")
    print()

    if result["url_validation"]:
        url_val = result["url_validation"]
        print(f"URL验证: {'✅ 通过' if url_val['valid'] else '❌ 失败'}")
        if url_val["question_id"]:
            print(f"问题ID: {url_val['question_id']}")
        if url_val["url_type"]:
            print(f"URL类型: {url_val['url_type']}")
        if url_val["errors"]:
            print("URL错误:")
            for error in url_val["errors"]:
                print(f"  - {error}")
        if url_val["warnings"]:
            print("URL警告:")
            for warning in url_val["warnings"]:
                print(f"  - {warning}")

    print()

    if result["task_validation"]:
        task_val = result["task_validation"]
        print(f"任务名称验证: {'✅ 通过' if task_val['valid'] else '❌ 失败'}")
        if task_val["suggestions"]:
            print("任务名称建议:")
            for suggestion in task_val["suggestions"]:
                print(f"  - {suggestion}")
        if task_val["warnings"]:
            print("任务名称警告:")
            for warning in task_val["warnings"]:
                print(f"  - {warning}")

    print()

    if result["db_validation"]:
        db_val = result["db_validation"]
        print(f"数据库连接: {'✅ 成功' if db_val['connected'] else '❌ 失败'}")
        print(f"数据表存在: {'✅ 完整' if db_val['tables_exist'] else '❌ 不完整'}")
        if db_val["warnings"]:
            print("数据库警告:")
            for warning in db_val["warnings"]:
                print(f"  - {warning}")

    print()

    if result["errors"]:
        print("配置错误:")
        for error in result["errors"]:
            print(f"  - {error}")

    if result["warnings"]:
        print("配置警告:")
        for warning in result["warnings"]:
            print(f"  - {warning}")

    if result["suggestions"]:
        print("配置建议:")
        for suggestion in result["suggestions"]:
            print(f"  - {suggestion}")


def validate_batch_config():
    """验证批量配置"""
    print("批量配置参数验证")
    print("="*50)

    # 示例批量配置
    batch_configs = [
        {
            "url": "https://www.zhihu.com/question/378706911/answer/1080446596",
            "task_name": "question_378706911_full_crawl",
            "max_answers": None
        },
        {
            "url": "https://www.zhihu.com/question/457478394/answer/1910416671937659055",
            "task_name": "question_457478394_sample",
            "max_answers": 100
        },
        {
            "url": "https://www.zhihu.com/question/37197524",
            "task_name": "question_37197524_test",
            "max_answers": 50
        }
    ]

    validator = CrawlParamsValidator()

    all_valid = True
    for i, config in enumerate(batch_configs, 1):
        print(f"配置 {i}:")
        result = validator.validate_config(config)

        if result["valid"]:
            print("  ✅ 验证通过")
            if result["url_validation"]["question_id"]:
                print(f"     问题ID: {result['url_validation']['question_id']}")
        else:
            print("  ❌ 验证失败")
            all_valid = False
            if result["errors"]:
                for error in result["errors"]:
                    print(f"     - {error}")

        print()

    print(f"批量配置验证结果: {'✅ 全部通过' if all_valid else '❌ 部分失败'}")
    print("="*50)


def interactive_validation():
    """交互式参数验证"""
    print("交互式参数验证")
    print("="*50)

    validator = CrawlParamsValidator()

    # 输入URL
    while True:
        url = input("请输入知乎问题URL: ").strip()
        if url:
            break
        print("URL不能为空，请重新输入")

    # 输入任务名称
    task_name = input("请输入任务名称 (可选，直接回车使用默认): ").strip()
    if not task_name:
        task_name = "custom_crawl_task"

    # 输入最大答案数
    max_answers_input = input("请输入最大答案数 (可选，直接回车采集全部): ").strip()
    max_answers = None
    if max_answers_input:
        try:
            max_answers = int(max_answers_input)
        except ValueError:
            print("输入无效，使用默认值(全部)")

    # 构建配置
    config = {
        "url": url,
        "task_name": task_name,
        "max_answers": max_answers
    }

    print("\n验证配置:")
    print(f"URL: {config['url']}")
    print(f"任务名称: {config['task_name']}")
    print(f"最大答案数: {config['max_answers'] or '不限制'}")
    print()

    # 验证
    result = validator.validate_config(config)

    print(f"验证结果: {'✅ 通过' if result['valid'] else '❌ 失败'}")

    if result["errors"]:
        print("错误:")
        for error in result["errors"]:
            print(f"  - {error}")

    if result["warnings"]:
        print("警告:")
        for warning in result["warnings"]:
            print(f"  - {warning}")

    if result["suggestions"]:
        print("建议:")
        for suggestion in result["suggestions"]:
            print(f"  - {suggestion}")

    if result["valid"]:
        print("\n🎉 配置验证通过，可以开始采集！")
        print(f"建议运行命令: python3 crawl_specific_question.py")
    else:
        print("\n❌ 请修正配置错误后重试")


def main():
    """主函数"""
    print("crawl_specific_question.py 参数验证工具")
    print("="*60)

    while True:
        print("\n请选择验证模式:")
        print("1. 验证单个配置示例")
        print("2. 验证批量配置示例")
        print("3. 交互式参数验证")
        print("4. 退出")

        choice = input("\n请选择 (1-4): ").strip()

        if choice == "1":
            validate_single_config()
        elif choice == "2":
            validate_batch_config()
        elif choice == "3":
            interactive_validation()
        elif choice == "4":
            print("再见!")
            break
        else:
            print("无效选择，请重新输入")


if __name__ == "__main__":
    main()
