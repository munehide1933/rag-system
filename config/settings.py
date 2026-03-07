# config/settings.py
"""
统一配置管理系统
支持 YAML 配置文件 + 环境变量 + Azure OpenAI
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from pathlib import Path
import yaml
import os

@dataclass
class QdrantConfig:
    """Qdrant 向量数据库配置"""
    host: str = "localhost"
    port: int = 6333
    collection_name: str = "rag_documents"
    vector_size: int = 1536
    distance_metric: str = "Cosine"
    
    def __post_init__(self):
        self.host = os.getenv('QDRANT_HOST', self.host)
        self.port = int(os.getenv('QDRANT_PORT', self.port))


@dataclass
class EmbeddingConfig:
    """Embedding 模型配置 - 支持 OpenAI 和 Azure OpenAI"""
    provider: str = "openai"
    model: str = "text-embedding-ada-002"
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    batch_size: int = 100
    max_retries: int = 3
    timeout: int = 30
    
    # Azure OpenAI 专用字段
    azure_endpoint_env: Optional[str] = None
    azure_api_key_env: Optional[str] = None
    azure_deployment_name_env: Optional[str] = None
    api_version: Optional[str] = None
    
    def __post_init__(self):
        # OpenAI 标准配置
        if self.provider == "openai" and self.api_key is None:
            self.api_key = os.getenv('OPENAI_API_KEY')


@dataclass
class ChunkingConfig:
    """文本分块配置"""
    chunk_size: int = 800
    overlap: int = 150
    min_chunk_size: int = 100
    max_chunk_size: int = 2000
    respect_sentence: bool = True
    language: str = "auto"
    use_nltk: bool = True
    use_spacy: bool = True
    use_semantic_chunking: bool = False


@dataclass
class CleaningConfig:
    """文本清洗配置"""
    remove_headers: bool = True
    remove_footers: bool = True
    remove_page_numbers: bool = True
    min_line_length: int = 10
    custom_patterns: List[str] = field(default_factory=list)
    use_chardet: bool = True
    default_encoding: str = "utf-8"

@dataclass
class QualityConfig:
    """入库前质量闸门配置"""
    enabled: bool = True
    min_chunk_chars: int = 120
    min_information_density: float = 0.35
    max_non_text_ratio: float = 0.45
    drop_numeric_only: bool = True


@dataclass
class Category:
    """文档分类配置"""
    name: str
    keywords: List[str] = field(default_factory=list)
    path: Optional[str] = None
    description: Optional[str] = None
    metadata: Dict = field(default_factory=dict)
    
    def match_score(self, text: str) -> float:
        """计算文本与分类的匹配度"""
        if not self.keywords:
            return 0.0
        text_lower = text.lower()
        matches = sum(1 for kw in self.keywords if kw.lower() in text_lower)
        return matches / len(self.keywords)


@dataclass
class ProcessingConfig:
    """处理配置"""
    batch_size: int = 32
    max_workers: int = 4
    use_multiprocessing: bool = True
    show_progress: bool = True
    enable_caching: bool = True
    cache_dir: str = "data/cache"
    replace_existing_source: bool = True
    skip_errors: bool = True
    max_errors: int = 10


@dataclass
class LoggingConfig:
    """日志配置"""
    level: str = "INFO"
    file: Optional[str] = "logs/rag_system.log"
    format: str = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    date_format: str = "%Y-%m-%d %H:%M:%S"
    console_output: bool = True
    colored_output: bool = True
    
    def __post_init__(self):
        self.level = os.getenv('LOG_LEVEL', self.level).upper()


class Settings:
    """
    全局配置管理器
    
    优先级：环境变量 > 配置文件 > 默认值
    """
    
    def __init__(self, config_path: str = "config/config_azure.yaml"):
        self.config_path = config_path
        self._load_env()
        self._load_config()
        
    def _load_env(self):
        """加载环境变量"""
        try:
            from dotenv import load_dotenv
            env_path = Path(".env")
            if env_path.exists():
                load_dotenv(env_path)
            else:
                for parent in Path.cwd().parents:
                    env_path = parent / ".env"
                    if env_path.exists():
                        load_dotenv(env_path)
                        break
        except ImportError:
            pass
            
    def _load_config(self):
        """从 YAML 加载配置"""
        config = {}
        
        config_file = Path(self.config_path)
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f) or {}
            except Exception as e:
                print(f"⚠️  配置文件加载失败: {e}")
                print(f"   使用默认配置")
        else:
            print(f"⚠️  配置文件不存在: {config_file}")
            print(f"   使用默认配置")
            
        # 初始化配置对象
        self.qdrant = QdrantConfig(**config.get('qdrant', {}))
        self.embedding = EmbeddingConfig(**config.get('embedding', {}))
        self.chunking = ChunkingConfig(**config.get('chunking', {}))
        self.cleaning = CleaningConfig(**config.get('cleaning', {}))
        self.quality = QualityConfig(**config.get('quality', {}))
        self.processing = ProcessingConfig(**config.get('processing', {}))
        self.logging = LoggingConfig(**config.get('logging', {}))
        
        # 加载分类
        self.categories = [
            Category(**cat) for cat in config.get('categories', [])
        ]
        
        if not self.categories:
            self.categories = [
                Category(name="general", keywords=[], description="默认分类")
            ]
            
    def get_category_by_name(self, name: str) -> Optional[Category]:
        """根据名称获取分类"""
        for cat in self.categories:
            if cat.name == name:
                return cat
        return None
        
    def auto_categorize(self, text: str, threshold: float = 0.3) -> Category:
        """根据文本内容自动分类"""
        best_category = None
        best_score = 0.0
        
        for category in self.categories:
            score = category.match_score(text)
            if score > best_score:
                best_score = score
                best_category = category
                
        if best_score < threshold:
            return self.get_category_by_name("general") or self.categories[0]
            
        return best_category or self.categories[0]
        
    def validate(self) -> bool:
        """验证配置有效性"""
        errors = []
        
        if not self.qdrant.host:
            errors.append("Qdrant host 不能为空")
        if self.qdrant.port < 1 or self.qdrant.port > 65535:
            errors.append(f"Qdrant port 无效: {self.qdrant.port}")
            
        if self.embedding.provider == "openai" and not self.embedding.api_key:
            errors.append("OpenAI API key 未设置")
            
        if self.chunking.chunk_size < self.chunking.min_chunk_size:
            errors.append("chunk_size 不能小于 min_chunk_size")
        if self.chunking.overlap >= self.chunking.chunk_size:
            errors.append("overlap 不能大于等于 chunk_size")

        if not (0.0 <= self.quality.min_information_density <= 1.0):
            errors.append("quality.min_information_density 必须在 [0, 1] 范围内")
        if not (0.0 <= self.quality.max_non_text_ratio <= 1.0):
            errors.append("quality.max_non_text_ratio 必须在 [0, 1] 范围内")
            
        if errors:
            print("❌ 配置验证失败:")
            for error in errors:
                print(f"   - {error}")
            return False
            
        return True
        
    def print_config(self):
        """打印当前配置"""
        print("\n" + "="*60)
        print("📋 当前配置")
        print("="*60)
        
        print("\n🗄️  Qdrant:")
        print(f"   Host: {self.qdrant.host}:{self.qdrant.port}")
        print(f"   Collection: {self.qdrant.collection_name}")
        print(f"   Vector Size: {self.qdrant.vector_size}")
        
        print("\n🤖 Embedding:")
        print(f"   Provider: {self.embedding.provider}")
        print(f"   Model: {self.embedding.model}")
        
        print("\n✂️  Chunking:")
        print(f"   Chunk Size: {self.chunking.chunk_size}")
        print(f"   Overlap: {self.chunking.overlap}")

        print("\n🧪 Quality Gate:")
        print(f"   Enabled: {self.quality.enabled}")
        print(f"   Min Chunk Chars: {self.quality.min_chunk_chars}")
        print(f"   Min Information Density: {self.quality.min_information_density}")
        
        print("\n🏷️  Categories:")
        for cat in self.categories:
            print(f"   - {cat.name}: {len(cat.keywords)} keywords")
        print()


# 全局单例
_settings = None

def get_settings(config_path: str = None) -> Settings:
    """获取全局配置实例（单例模式）"""
    global _settings
    
    target_path = config_path or "config/config_azure.yaml"
    if _settings is None or _settings.config_path != target_path:
        _settings = Settings(target_path)
        
    return _settings


if __name__ == "__main__":
    settings = Settings()
    settings.validate()
    settings.print_config()
