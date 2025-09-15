import os
import logging

# 数据库配置
DATABASE_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 5432)),
    'database': os.getenv('DB_NAME', 'zhihu_crawler'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'password')
}

# 爬虫配置
CRAWLER_CONFIG = {
    'headless': False,  # 是否无头模式运行
    'answers_per_cleanup': 200,  # 每采集多少个回答清空DOM
    'scroll_delay': (0.67, 1.33),  # 滚动延时范围（秒）- 缩短为原来的1/3
    'page_load_delay': (0.67, 1.33),  # 页面加载延时范围（秒）- 缩短为原来的1/3
    'max_retries': 3,  # 最大重试次数
    'timeout': 10,  # 元素等待超时时间（秒）
}

# 日志配置
LOGGING_CONFIG = {
    'level': logging.INFO,
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'filename': 'zhihu_crawler.log',
    'filemode': 'a',
    'encoding': 'utf-8'
}

# 反爬虫配置
ANTI_DETECTION_CONFIG = {
    'user_agents': [
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15'
    ],
    'chrome_options': [
        '--no-sandbox',
        '--disable-dev-shm-usage',
        '--disable-blink-features=AutomationControlled',
        '--disable-extensions',
        '--disable-plugins',
        '--disable-images',  # 禁用图片加载以提高速度
    ],
    'exclude_switches': ['enable-automation'],
    'experimental_options': {
        'useAutomationExtension': False,
        'excludeSwitches': ['enable-automation']
    }
}

# 知乎相关配置
ZHIHU_CONFIG = {
    'base_url': 'https://www.zhihu.com',
    'login_url': 'https://www.zhihu.com/signin',
    'selectors': {
        'answer_item': '.List-item, .AnswerItem',
        'author_name': '.AuthorInfo-name, .UserLink-link',
        'answer_content': '.RichContent-inner, .CopyrightRichText-richText',
        'vote_button': '.VoteButton--up .Button-label, .VoteButton .Voters',
        'answer_time': '.ContentItem-time, .AnswerItem-time',
        'load_more_btn': '.Button--primary, .QuestionAnswers-more button',
        'user_avatar': '.Avatar, .Menu-item, [data-za-detail-view-element_name="Profile"]'
    }
}

def setup_logging():
    """设置日志配置"""
    logging.basicConfig(**LOGGING_CONFIG)
    
    # 同时输出到控制台
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter(LOGGING_CONFIG['format'])
    console_handler.setFormatter(formatter)
    
    # 获取根日志记录器并添加控制台处理器
    root_logger = logging.getLogger()
    root_logger.addHandler(console_handler)

def get_database_config():
    """获取数据库配置"""
    return DATABASE_CONFIG.copy()

def get_crawler_config():
    """获取爬虫配置"""
    return CRAWLER_CONFIG.copy()

def get_zhihu_config():
    """获取知乎相关配置"""
    return ZHIHU_CONFIG.copy()

def get_anti_detection_config():
    """获取反检测配置"""
    return ANTI_DETECTION_CONFIG.copy()