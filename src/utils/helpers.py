# utils/helpers.py
"""
工具函数集合
包含：重试机制、日志系统、性能监控、缓存等
"""
import time
import logging
import sys
import hashlib
import pickle
from pathlib import Path
from functools import wraps
from contextlib import contextmanager
from typing import Callable, Iterator, List, TypeVar, Optional, Any, Dict
from collections import defaultdict

# ============================================
# 1. 重试机制
# ============================================

def retry_on_failure(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
    logger: logging.Logger = None
):
    """
    重试装饰器
    
    Args:
        max_retries: 最大重试次数
        delay: 初始延迟（秒）
        backoff: 延迟倍增因子
        exceptions: 需要重试的异常类型
        logger: 日志记录器
        
    Example:
        @retry_on_failure(max_retries=3, delay=1.0)
        def fetch_data():
            return requests.get(url)
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt < max_retries - 1:
                        msg = f"⚠️  {func.__name__} 失败 (尝试 {attempt+1}/{max_retries}): {e}"
                        if logger:
                            logger.warning(msg)
                        else:
                            print(msg)
                            
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        msg = f"❌ {func.__name__} 最终失败: {e}"
                        if logger:
                            logger.error(msg)
                        else:
                            print(msg)
                        raise
                        
            raise last_exception
            
        return wrapper
    return decorator


# ============================================
# 2. 日志系统
# ============================================

class ColoredFormatter(logging.Formatter):
    """带颜色的日志格式化器（仅在终端显示）"""
    
    COLORS = {
        'DEBUG': '\033[36m',    # 青色
        'INFO': '\033[32m',     # 绿色
        'WARNING': '\033[33m',  # 黄色
        'ERROR': '\033[31m',    # 红色
        'CRITICAL': '\033[35m', # 紫色
    }
    RESET = '\033[0m'
    
    def format(self, record):
        # 添加颜色
        if sys.stdout.isatty():  # 只在终端显示颜色
            levelname = record.levelname
            if levelname in self.COLORS:
                record.levelname = f"{self.COLORS[levelname]}{levelname}{self.RESET}"
                
        return super().format(record)


def setup_logger(
    name: str = "RAG",
    level: str = "INFO",
    log_file: Optional[str] = None,
    console_output: bool = True,
    colored_output: bool = True
) -> logging.Logger:
    """
    配置日志系统
    
    Args:
        name: 日志名称
        level: 日志级别
        log_file: 日志文件路径
        console_output: 是否输出到控制台
        colored_output: 控制台是否使用颜色
        
    Returns:
        配置好的 Logger
        
    Example:
        logger = setup_logger("RAG", "INFO", "logs/app.log")
        logger.info("系统启动")
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # 避免重复添加 handler
    if logger.handlers:
        return logger
    
    # 格式化器
    log_format = '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    
    # 控制台输出
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        
        if colored_output:
            console_formatter = ColoredFormatter(log_format, datefmt=date_format)
        else:
            console_formatter = logging.Formatter(log_format, datefmt=date_format)
            
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
    
    # 文件输出
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_formatter = logging.Formatter(log_format, datefmt=date_format)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    return logger


# ============================================
# 3. 性能监控
# ============================================

class PerformanceMetrics:
    """
    性能指标收集器
    
    Example:
        metrics = PerformanceMetrics()
        
        with metrics.timer('embedding'):
            embed_documents()
            
        metrics.increment('documents_processed', 10)
        metrics.print_stats()
    """
    
    def __init__(self):
        self.timings: Dict[str, List[float]] = defaultdict(list)
        self.counters: Dict[str, int] = defaultdict(int)
        self.start_time = time.time()
        
    @contextmanager
    def timer(self, name: str):
        """计时上下文管理器"""
        start = time.time()
        try:
            yield
        finally:
            elapsed = time.time() - start
            self.timings[name].append(elapsed)
            
    def increment(self, name: str, value: int = 1):
        """增加计数器"""
        self.counters[name] += value
        
    def set_counter(self, name: str, value: int):
        """设置计数器"""
        self.counters[name] = value
        
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = {}
        
        # 计时统计
        for name, times in self.timings.items():
            if times:
                stats[name] = {
                    'count': len(times),
                    'total': sum(times),
                    'avg': sum(times) / len(times),
                    'min': min(times),
                    'max': max(times)
                }
        
        # 计数器
        stats['counters'] = dict(self.counters)
        
        # 总运行时间
        stats['total_runtime'] = time.time() - self.start_time
        
        return stats
        
    def print_stats(self):
        """打印统计信息"""
        stats = self.get_stats()
        
        print("\n" + "="*60)
        print("📊 性能统计")
        print("="*60)
        
        # 计时统计
        timing_stats = {k: v for k, v in stats.items() if k not in ['counters', 'total_runtime']}
        if timing_stats:
            print("\n⏱️  计时:")
            for name, data in timing_stats.items():
                print(f"\n  {name}:")
                print(f"    调用次数: {data['count']}")
                print(f"    总时间: {data['total']:.2f}s")
                print(f"    平均: {data['avg']:.3f}s")
                print(f"    范围: {data['min']:.3f}s - {data['max']:.3f}s")
        
        # 计数器
        if stats.get('counters'):
            print("\n🔢 计数器:")
            for name, count in stats['counters'].items():
                print(f"    {name}: {count:,}")
        
        # 总运行时间
        print(f"\n⏰ 总运行时间: {stats['total_runtime']:.2f}s")
        print("="*60 + "\n")
        
    def reset(self):
        """重置所有统计"""
        self.timings.clear()
        self.counters.clear()
        self.start_time = time.time()


# ============================================
# 4. 缓存系统
# ============================================

class DiskCache:
    """
    磁盘缓存系统（用于缓存 embedding）
    
    Example:
        cache = DiskCache("data/cache")
        
        # 获取缓存
        embedding = cache.get(text)
        if embedding is None:
            embedding = compute_embedding(text)
            cache.set(text, embedding)
    """
    
    def __init__(self, cache_dir: str = "data/cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
    @staticmethod
    def _normalize_text(text: str) -> str:
        """
        规范化文本用于缓存键计算。
        仅做轻量归一化，避免因空白差异导致缓存 miss。
        """
        if text is None:
            return ""
        return " ".join(str(text).split())

    def _get_key(self, text: str, namespace: str = "") -> str:
        """生成缓存键（命名空间 + 规范化文本）"""
        normalized = self._normalize_text(text)
        cache_input = f"{namespace}::{normalized}" if namespace else normalized
        return hashlib.md5(cache_input.encode('utf-8')).hexdigest()
        
    def get(self, text: str, namespace: str = "") -> Optional[Any]:
        """获取缓存"""
        key = self._get_key(text, namespace=namespace)
        cache_file = self.cache_dir / f"{key}.pkl"
        
        if cache_file.exists():
            try:
                with open(cache_file, 'rb') as f:
                    return pickle.load(f)
            except Exception as e:
                print(f"⚠️  缓存读取失败: {e}")
                return None
                
        return None
        
    def set(self, text: str, value: Any, namespace: str = ""):
        """设置缓存"""
        key = self._get_key(text, namespace=namespace)
        cache_file = self.cache_dir / f"{key}.pkl"
        
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump(value, f)
        except Exception as e:
            print(f"⚠️  缓存写入失败: {e}")
            
    def clear(self):
        """清除所有缓存"""
        count = 0
        for cache_file in self.cache_dir.glob("*.pkl"):
            cache_file.unlink()
            count += 1
        print(f"✅ 已清除 {count} 个缓存文件")
        
    def size(self) -> int:
        """获取缓存大小（字节）"""
        total_size = 0
        for cache_file in self.cache_dir.glob("*.pkl"):
            total_size += cache_file.stat().st_size
        return total_size
        
    def count(self) -> int:
        """获取缓存文件数量"""
        return len(list(self.cache_dir.glob("*.pkl")))
        
    def stats(self):
        """打印缓存统计"""
        count = self.count()
        size = self.size()
        size_mb = size / (1024 * 1024)
        
        print(f"📦 缓存统计:")
        print(f"   文件数: {count:,}")
        print(f"   总大小: {size_mb:.2f} MB")


# ============================================
# 5. 批处理工具
# ============================================

T = TypeVar('T')

def batch_iterator(
    items: List[T],
    batch_size: int
) -> Iterator[List[T]]:
    """
    批量迭代器
    
    Args:
        items: 项目列表
        batch_size: 批次大小
        
    Yields:
        批次列表
        
    Example:
        for batch in batch_iterator(documents, 32):
            process_batch(batch)
    """
    for i in range(0, len(items), batch_size):
        yield items[i:i + batch_size]


def file_batch_iterator(
    directory: Path,
    file_extensions: List[str],
    batch_size: int = 32,
    recursive: bool = True
) -> Iterator[List[Path]]:
    """
    文件批处理迭代器
    
    Args:
        directory: 目录路径
        file_extensions: 文件扩展名列表
        batch_size: 批次大小
        recursive: 是否递归搜索
        
    Yields:
        文件路径批次
        
    Example:
        for file_batch in file_batch_iterator(Path("documents/"), ['.pdf', '.txt']):
            process_files(file_batch)
    """
    files = []
    seen = set()

    for ext in sorted(file_extensions):
        iterator = directory.rglob(f"*{ext}") if recursive else directory.glob(f"*{ext}")
        for file_path in iterator:
            if not file_path.is_file():
                continue
            normalized = str(file_path.resolve())
            if normalized in seen:
                continue
            seen.add(normalized)
            files.append(file_path)

    files.sort(key=lambda p: str(p.resolve()))
    
    for batch in batch_iterator(files, batch_size):
        yield batch


# ============================================
# 6. 进度显示
# ============================================

def show_progress(
    iterable,
    desc: str = "Processing",
    total: int = None,
    unit: str = "it",
    disable: bool = False
):
    """
    显示进度条（基于 tqdm）
    
    Args:
        iterable: 可迭代对象
        desc: 描述
        total: 总数
        unit: 单位
        disable: 是否禁用
        
    Example:
        for item in show_progress(items, desc="Processing"):
            process(item)
    """
    try:
        from tqdm import tqdm
        return tqdm(iterable, desc=desc, total=total, unit=unit, disable=disable)
    except ImportError:
        # 如果没有 tqdm，返回原始迭代器
        return iterable


# ============================================
# 7. 文件操作工具
# ============================================

def safe_filename(filename: str, max_length: int = 255) -> str:
    """
    生成安全的文件名
    
    Args:
        filename: 原始文件名
        max_length: 最大长度
        
    Returns:
        安全的文件名
    """
    # 移除不安全字符
    import re
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # 限制长度
    if len(filename) > max_length:
        name, ext = Path(filename).stem, Path(filename).suffix
        max_name_length = max_length - len(ext)
        filename = name[:max_name_length] + ext
        
    return filename


def get_file_hash(filepath: Path) -> str:
    """
    计算文件 MD5 哈希
    
    Args:
        filepath: 文件路径
        
    Returns:
        MD5 哈希值
    """
    md5 = hashlib.md5()
    
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            md5.update(chunk)
            
    return md5.hexdigest()


def format_bytes(size: int) -> str:
    """
    格式化字节大小
    
    Args:
        size: 字节数
        
    Returns:
        格式化后的字符串（如 "1.5 MB"）
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"


# ============================================
# 使用示例
# ============================================

if __name__ == "__main__":
    # 1. 日志系统
    logger = setup_logger("TestApp", "INFO", "logs/test.log")
    logger.info("✅ 日志系统测试")
    logger.warning("⚠️  警告测试")
    logger.error("❌ 错误测试")
    
    # 2. 性能监控
    metrics = PerformanceMetrics()
    
    with metrics.timer('task1'):
        time.sleep(0.1)
        
    with metrics.timer('task2'):
        time.sleep(0.2)
        
    metrics.increment('processed', 100)
    metrics.print_stats()
    
    # 3. 缓存系统
    cache = DiskCache("data/test_cache")
    cache.set("test_key", {"data": "value"})
    result = cache.get("test_key")
    print(f"缓存结果: {result}")
    cache.stats()
    cache.clear()
    
    # 4. 重试机制
    @retry_on_failure(max_retries=3, delay=0.5, logger=logger)
    def unstable_function():
        import random
        if random.random() < 0.7:
            raise Exception("随机失败")
        return "成功"
    
    try:
        result = unstable_function()
        print(f"重试结果: {result}")
    except Exception as e:
        print(f"最终失败: {e}")
    
    # 5. 批处理
    items = list(range(100))
    for i, batch in enumerate(batch_iterator(items, 32)):
        print(f"批次 {i+1}: {len(batch)} 项")
    
    # 6. 文件工具
    print(f"安全文件名: {safe_filename('test<file>name?.txt')}")
    print(f"格式化大小: {format_bytes(1536000)}")
    
    print("\n✅ 所有工具测试完成！")
