import logging
import sys
import os
from datetime import datetime

class LoggerSingleton:
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not LoggerSingleton._initialized:
            self.setup_logger()
            LoggerSingleton._initialized = True

    def setup_logger(self):
        # 🔥 日志文件保存在目录
        os.makedirs("logs", exist_ok=True)
        log_file = f"logs/app_{datetime.now().strftime('%Y-%m-%d')}.log"

        # 定义日志格式
        log_format = "%(asctime)s - %(levelname)s - %(message)s"
        date_format = "%Y-%m-%d %H:%M:%S"
        formatter = logging.Formatter(log_format, datefmt=date_format)

        # 根logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        root_logger.handlers.clear()  # 清空默认handler

        # 1. 控制台输出
        console_handler = logging.StreamHandler(sys.__stdout__)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

        # 2. 文件输出（自动生成 app.log）
        file_handler = logging.FileHandler(
            log_file,
            mode="a",        # 追加模式
            encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

        # 屏蔽第三方库噪音日志
        # for lib in ["transformers", "datasets", "peft", "torch", "accelerate"]:
        for lib in ["transformers", "datasets", "torch", "accelerate"]:
            logging.getLogger(lib).setLevel(logging.WARNING)

    @staticmethod
    def get_logger(name=__name__):
        return logging.getLogger(name)


# 全局单例 logger
logger = LoggerSingleton().get_logger()