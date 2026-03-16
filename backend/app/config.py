"""
配置管理
统一从项目根目录的 .env 文件加载配置
"""

import os
from urllib.parse import urlparse
from dotenv import load_dotenv

# 加载项目根目录的 .env 文件
# 路径: MiroFish/.env (相对于 backend/app/config.py)
project_root_env = os.path.join(os.path.dirname(__file__), '../../.env')

def _load_project_env():
    """重新加载项目根目录 .env，保证运行时修改配置后可被新请求读取。"""
    if os.path.exists(project_root_env):
        load_dotenv(project_root_env, override=True)
    else:
        # 如果根目录没有 .env，尝试加载环境变量（用于生产环境）
        load_dotenv(override=True)


_load_project_env()


class Config:
    """Flask配置类"""

    # 静态配置
    JSON_AS_ASCII = False
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '../uploads')
    ALLOWED_EXTENSIONS = {'pdf', 'md', 'txt', 'markdown'}
    DEFAULT_CHUNK_SIZE = 500  # 默认切块大小
    DEFAULT_CHUNK_OVERLAP = 50  # 默认重叠大小
    OASIS_SIMULATION_DATA_DIR = os.path.join(os.path.dirname(__file__), '../uploads/simulations')
    OASIS_TWITTER_ACTIONS = [
        'CREATE_POST', 'LIKE_POST', 'REPOST', 'FOLLOW', 'DO_NOTHING', 'QUOTE_POST'
    ]
    OASIS_REDDIT_ACTIONS = [
        'LIKE_POST', 'DISLIKE_POST', 'CREATE_POST', 'CREATE_COMMENT',
        'LIKE_COMMENT', 'DISLIKE_COMMENT', 'SEARCH_POSTS', 'SEARCH_USER',
        'TREND', 'REFRESH', 'DO_NOTHING', 'FOLLOW', 'MUTE'
    ]

    # 运行时配置（由 reload() 填充）
    SECRET_KEY = 'mirofish-secret-key'
    DEBUG = True
    LLM_API_KEY = None
    LLM_BASE_URL = 'https://api.openai.com/v1'
    LLM_MODEL_NAME = 'gpt-4o-mini'
    ZEP_API_KEY = None
    OASIS_DEFAULT_MAX_ROUNDS = 10
    REPORT_AGENT_MAX_TOOL_CALLS = 5
    REPORT_AGENT_MAX_REFLECTION_ROUNDS = 2
    REPORT_AGENT_TEMPERATURE = 0.5

    @classmethod
    def reload(cls):
        """重新读取 .env，并刷新类级配置。"""
        _load_project_env()

        # Flask配置
        cls.SECRET_KEY = os.environ.get('SECRET_KEY', 'mirofish-secret-key')
        cls.DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'

        # LLM配置（统一使用OpenAI格式）
        cls.LLM_API_KEY = os.environ.get('LLM_API_KEY')
        cls.LLM_BASE_URL = os.environ.get('LLM_BASE_URL', 'https://api.openai.com/v1')
        cls.LLM_MODEL_NAME = os.environ.get('LLM_MODEL_NAME', 'gpt-4o-mini')

        # Zep配置
        cls.ZEP_API_KEY = os.environ.get('ZEP_API_KEY')

        # OASIS模拟配置
        cls.OASIS_DEFAULT_MAX_ROUNDS = int(os.environ.get('OASIS_DEFAULT_MAX_ROUNDS', '10'))

        # Report Agent配置
        cls.REPORT_AGENT_MAX_TOOL_CALLS = int(os.environ.get('REPORT_AGENT_MAX_TOOL_CALLS', '5'))
        cls.REPORT_AGENT_MAX_REFLECTION_ROUNDS = int(os.environ.get('REPORT_AGENT_MAX_REFLECTION_ROUNDS', '2'))
        cls.REPORT_AGENT_TEMPERATURE = float(os.environ.get('REPORT_AGENT_TEMPERATURE', '0.5'))

    @classmethod
    def validate_llm_settings(cls, api_key=None, base_url=None, model_name=None):
        """校验 OpenAI 兼容 LLM 配置，尽早暴露常见错配。"""
        cls.reload()

        api_key = (api_key if api_key is not None else cls.LLM_API_KEY or '').strip()
        base_url = (base_url if base_url is not None else cls.LLM_BASE_URL or '').strip()
        model_name = (model_name if model_name is not None else cls.LLM_MODEL_NAME or '').strip()

        errors = []

        if not api_key:
            errors.append("LLM_API_KEY 未配置")
        if not base_url:
            errors.append("LLM_BASE_URL 未配置")
            return errors
        if not model_name:
            errors.append("LLM_MODEL_NAME 未配置")

        parsed = urlparse(base_url)
        host = parsed.netloc.lower()
        path = parsed.path.rstrip('/')
        model_lower = model_name.lower()

        if parsed.scheme not in ('http', 'https'):
            errors.append("LLM_BASE_URL 必须以 http:// 或 https:// 开头")

        if any(segment in path for segment in ('/chat/completions', '/responses', '/embeddings')):
            errors.append(
                "LLM_BASE_URL 应填写 API 根地址，而不是具体接口路径，例如 OpenAI 应为 https://api.openai.com/v1"
            )

        if host == 'api.openai.com' and path and not path.endswith('/v1'):
            errors.append("OpenAI 官方接口的 LLM_BASE_URL 应为 https://api.openai.com/v1")

        if 'dashscope.aliyuncs.com' in host and path and not path.endswith('/v1'):
            errors.append(
                "阿里百炼兼容接口的 LLM_BASE_URL 通常应以 /v1 结尾，例如 https://dashscope.aliyuncs.com/compatible-mode/v1"
            )

        if host == 'api.openai.com' and model_lower.startswith('qwen'):
            errors.append(
                "当前 LLM_BASE_URL 指向 OpenAI 官方接口，但模型名是 qwen 系列；请改成 OpenAI 模型名，例如 gpt-4o-mini"
            )

        if 'dashscope.aliyuncs.com' in host and model_lower.startswith(('gpt-', 'o1', 'o3', 'o4')):
            errors.append(
                "当前 LLM_BASE_URL 指向阿里百炼，但模型名看起来是 OpenAI 模型；请切换到 OpenAI base_url，或改用 qwen 系列模型"
            )

        if api_key.startswith('sk-') and 'dashscope.aliyuncs.com' in host and model_lower.startswith('qwen'):
            errors.append(
                "检测到 sk- 风格 API Key 与 DashScope/qwen 配置混用；如果你填的是 OpenAI Key，请把 LLM_BASE_URL 改为 https://api.openai.com/v1，并把模型改成 OpenAI 模型名"
            )

        return errors

    @classmethod
    def validate(cls):
        """验证必要配置"""
        cls.reload()
        errors = cls.validate_llm_settings()
        if not cls.ZEP_API_KEY:
            errors.append("ZEP_API_KEY 未配置")
        return errors


Config.reload()

