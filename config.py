"""
知乎爬虫配置文件
"""

import os
from datetime import datetime

class ZhihuConfig:
    """知乎爬虫配置类"""
    
    # 基础配置
    BASE_URL = "https://www.zhihu.com"
    SEARCH_URL = "https://www.zhihu.com/search"
    
    # 时间范围配置
    DEFAULT_START_DATE = "2015-01-01"
    DEFAULT_END_DATE = "2025-12-31"
    DATE_FORMAT = "%Y-%m-%d"
    
    # 搜索配置
    SEARCH_TYPE = "content"  # content, question, answer
    SEARCH_RANGE = "all"     # all, week, month, year
    
    # 爬虫行为配置
    SCROLL_PAUSE_TIME = 2      # 滚动等待时间（秒）
    PAGE_LOAD_TIMEOUT = 30     # 页面加载超时时间（秒）
    ELEMENT_WAIT_TIMEOUT = 10  # 元素等待超时时间（秒）
    
    # 反爬虫策略配置
    MIN_DELAY = 1              # 最小延时（秒）
    MAX_DELAY = 3              # 最大延时（秒）
    MAX_RETRIES = 3            # 最大重试次数
    
    # 浏览器配置
    HEADLESS = True            # 是否无头模式
    WINDOW_SIZE = (1920, 1080) # 窗口大小
    
    # User-Agent 池
    USER_AGENTS = [
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0'
    ]
    
    # 数据库配置
    DATABASE_PATH = "./zhihu_data.db"  # SQLite数据库路径（向后兼容）
    
    # PostgreSQL数据库配置
    POSTGRES_CONFIG = {
        'host': 'localhost',
        'port': 5432,
        'database': 'zhihu_crawler',
        'user': 'postgres',
        'password': 'password'
    }
    
    # 数据库类型选择
    DATABASE_TYPE = 'postgresql'  # 'sqlite' 或 'postgresql'
    
    # Cookie配置
    COOKIES_FILE = "./cookies/zhihu_cookies.json"
    ENABLE_COOKIE_LOGIN = True
    COOKIE_DOMAIN = ".zhihu.com"
    
    # 日志配置
    LOG_LEVEL = "INFO"
    LOG_FILE = "./logs/zhihu_crawler.log"
    
    # 输出配置
    OUTPUT_DIR = "./output"
    EXPORT_FORMATS = ["json", "csv", "excel"]
    
    # CSS选择器配置
    SELECTORS = {
        # 搜索页面
        "search_results": ".List-item",
        "search_question_title": ".ContentItem-title a",
        "search_question_url": ".ContentItem-title a",
        "search_answer_preview": ".RichContent-inner",
        
        # 问题页面
        "question_title": ".QuestionHeader-title",
        "question_detail": ".QuestionRichText .RichContent-inner",
        "question_stats": ".QuestionHeaderActions",
        "question_author": ".QuestionHeader-detail .UserLink-link",
        "question_follow_count": ".NumberBoard-itemValue",
        "question_view_count": ".NumberBoard-itemValue",
        "question_answer_count": ".List-headerText span",
        "question_tags": ".QuestionHeader-topics .Popover div",
        
        # 答案相关
        "answers_list": ".List-item, .Card.AnswerCard, .Card.MoreAnswers > div > div",
        "answer_content": ".RichContent-inner",
        "answer_author": ".AuthorInfo-name a",
        "answer_time": ".ContentItem-time",
        "answer_vote_count": ".VoteButton--up .VoteButton-label, .ContentItem-actions span > span > button",
        "answer_url": ".ContentItem-title a",
        
        # 评论相关
        "comments_button": "button[aria-label*='评论']",  # 评论按钮
        "comments_list": ".CommentItem, .NestComment, .CommentItemV2",  # 评论列表
        "comment_content": ".CommentItem-content, .NestComment-content, .CommentItemV2-content, .RichText",  # 评论内容
        "comment_author": ".CommentItem-meta .UserLink-link, .NestComment-meta a, .CommentItemV2-meta a",  # 评论作者
        "comment_time": ".CommentItem-meta .CommentItem-time, .NestComment-meta span, .CommentItemV2-meta span",  # 评论时间
        "comment_vote": ".CommentItem-meta .CommentItem-vote, .NestComment-likeCount, .CommentItemV2-like, button[class*='like']",  # 评论点赞数
        
        # 加载更多
        "load_more_answers": ".QuestionAnswers-answerAdd button, .AnswerListV2-answerAdd button, button:contains('显示更多'), button:contains('更多回答'), button.QuestionMainAction",
        "load_more_comments": ".Comments-loadMore button, button:contains('查看全部评论'), button:contains('更多评论'), body > div:nth-child(66) > div > div > div.css-1aq8hf9 > div",
        "scroll_loading": ".ContentItem-arrowIcon, .QuestionAnswers-answerAdd, .AnswerListV2-answerAdd"
    }
    
    @classmethod
    def create_directories(cls):
        """创建必要的目录"""
        os.makedirs(os.path.dirname(cls.LOG_FILE), exist_ok=True)
        os.makedirs(cls.OUTPUT_DIR, exist_ok=True)
    
    @classmethod
    def validate_date_range(cls, start_date: str, end_date: str) -> bool:
        """验证日期范围是否有效"""
        try:
            start = datetime.strptime(start_date, cls.DATE_FORMAT)
            end = datetime.strptime(end_date, cls.DATE_FORMAT)
            return start <= end
        except ValueError:
            return False