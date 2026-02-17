#!/usr/bin/env python3
# ingest_qdrant_v2.py
"""
RAG 文档摄取脚本 - Azure OpenAI 版本
支持增强的文本处理和 Azure OpenAI embedding
"""
import uuid
import argparse
import sys
from pathlib import Path
from typing import List, Dict
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

# 获取项目根目录（ingest_qdrant_v2.py 的父级的父级）
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 导入配置和工具
try:
    from config.settings import get_settings
    from utils.helpers import (
        setup_logger,
        PerformanceMetrics,
        DiskCache,
        show_progress,
        file_batch_iterator
    )
    from document_cleaner_enhanced import (
        EnhancedDocumentCleaner,
        smart_chunk_text_enhanced
    )
    from azure_embedding import AzureOpenAIEmbedding
except ImportError as e:
    print(f"❌ 导入错误: {e}")
    print("请确保所有必需文件都在正确位置")
    sys.exit(1)


class DocumentIngester:
    """文档摄取器 - 支持 Azure OpenAI"""
    
    def __init__(self, config_path: str = "config/config_azure.yaml"):
        """
        初始化摄取器
        
        Args:
            config_path: 配置文件路径
        """
        # 加载配置
        self.settings = get_settings(config_path)
        
        # 设置日志
        self.logger = setup_logger(
            name="DocumentIngester",
            level=self.settings.logging.level,
            log_file=self.settings.logging.file,
            console_output=self.settings.logging.console_output,
            colored_output=self.settings.logging.colored_output
        )
        
        self.logger.info("="*60)
        self.logger.info("🚀 RAG 文档摄取系统启动")
        self.logger.info("="*60)
        
        # 初始化组件
        self.logger.info("📦 初始化组件...")
        
        # 1. Qdrant 客户端
        self.qdrant = QdrantClient(
            host=self.settings.qdrant.host,
            port=self.settings.qdrant.port
        )
        self.logger.info(f"✅ Qdrant: {self.settings.qdrant.host}:{self.settings.qdrant.port}")
        
        # 2. Azure OpenAI Embedding
        try:
            self.embedder = AzureOpenAIEmbedding(
                max_retries=self.settings.embedding.max_retries,
                timeout=self.settings.embedding.timeout
            )
            self.logger.info(f"✅ Azure OpenAI Embedding")
            
            # 测试连接
            #if not self.embedder.test_connection():
                #raise Exception("Azure OpenAI 连接测试失败")
                
        except Exception as e:
            self.logger.error(f"❌ Azure OpenAI 初始化失败: {e}")
            raise
        
        # 3. 文档清洗器
        self.cleaner = EnhancedDocumentCleaner({
            'remove_patterns': self.settings.cleaning.custom_patterns,
            'min_line_length': self.settings.cleaning.min_line_length
        })
        self.logger.info(f"✅ 文档清洗器 (增强功能已启用)")
        
        # 4. 缓存系统
        if self.settings.processing.enable_caching:
            self.cache = DiskCache(self.settings.processing.cache_dir)
            self.logger.info(f"✅ Embedding 缓存: {self.settings.processing.cache_dir}")
        else:
            self.cache = None
        
        # 5. 性能监控
        self.metrics = PerformanceMetrics()
        
        # 确保集合存在
        self._ensure_collection()
        
        self.logger.info("✨ 初始化完成\n")
        
    def _ensure_collection(self):
        """确保 Qdrant 集合存在"""
        collection_name = self.settings.qdrant.collection_name
        
        try:
            # 检查集合是否存在
            collections = self.qdrant.get_collections().collections
            exists = any(c.name == collection_name for c in collections)
            
            if not exists:
                self.logger.info(f"📦 创建集合: {collection_name}")
                
                self.qdrant.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=self.settings.qdrant.vector_size,
                        distance=Distance.COSINE
                    )
                )
                self.logger.info(f"✅ 集合创建成功")
            else:
                self.logger.info(f"✅ 集合已存在: {collection_name}")
                
        except Exception as e:
            self.logger.error(f"❌ 集合创建失败: {e}")
            raise
            
    def process_document(
        self,
        file_path: Path,
        category: str = None
    ) -> List[Dict]:
        """
        处理单个文档
        
        Args:
            file_path: 文件路径
            category: 文档分类
            
        Returns:
            文档块列表
        """
        with self.metrics.timer('document_processing'):
            try:
                # 1. 加载文件
                with self.metrics.timer('file_loading'):
                    content = self.cleaner.load_file_with_encoding(str(file_path))
                    
                if not content or len(content) < 10:
                    self.logger.warning(f"⚠️  文件内容为空或太短: {file_path.name}")
                    return []
                
                # 2. 清洗文本
                with self.metrics.timer('text_cleaning'):
                    extension = file_path.suffix.lower().lstrip('.')
                    cleaned = self.cleaner.clean_text(content, extension)
                    
                # 3. 提取元数据
                with self.metrics.timer('metadata_extraction'):
                    metadata = self.cleaner.extract_metadata_enhanced(
                        cleaned,
                        str(file_path)
                    )
                
                # 4. 自动分类（如果未指定）
                if not category:
                    detected_category = self.settings.auto_categorize(cleaned)
                    category = detected_category.name
                    self.logger.info(f"   自动分类: {category}")
                
                # 5. 分块
                with self.metrics.timer('text_chunking'):
                    chunks = smart_chunk_text_enhanced(
                        cleaned,
                        chunk_size=self.settings.chunking.chunk_size,
                        overlap=self.settings.chunking.overlap,
                        min_chunk_size=self.settings.chunking.min_chunk_size,
                        respect_sentence=self.settings.chunking.respect_sentence,
                        language=self.settings.chunking.language
                    )
                
                if not chunks:
                    self.logger.warning(f"⚠️  无法分块: {file_path.name}")
                    return []
                
                # 6. 构建文档块
                documents = []
                for i, chunk in enumerate(chunks):
                    doc = {
                        'id': f"{file_path.stem}_{i}",
                        'text': chunk,
                        'metadata': {
                            'source': str(file_path.name),
                            'category': category,
                            'chunk_index': i,
                            'total_chunks': len(chunks),
                            'file_type': extension,
                            **metadata
                        }
                    }
                    documents.append(doc)
                
                self.logger.info(f"✅ {file_path.name}: {len(chunks)} 块")
                self.metrics.increment('documents_processed')
                self.metrics.increment('chunks_created', len(chunks))
                
                return documents
                
            except Exception as e:
                self.logger.error(f"❌ 处理失败 {file_path.name}: {e}")
                self.metrics.increment('documents_failed')
                if not self.settings.processing.skip_errors:
                    raise
                return []
                
    def embed_documents(self, documents: List[Dict]) -> List[Dict]:
        """
        为文档生成 embeddings
        
        Args:
            documents: 文档列表
            
        Returns:
            带 embedding 的文档列表
        """
        with self.metrics.timer('embedding'):
            # 收集需要 embedding 的文本
            texts_to_embed = []
            cached_indices = []
            
            for i, doc in enumerate(documents):
                text = doc['text']
                
                # 检查缓存
                if self.cache:
                    cached_emb = self.cache.get(text)
                    if cached_emb is not None:
                        doc['vector'] = cached_emb
                        cached_indices.append(i)
                        continue
                
                texts_to_embed.append((i, text))
            
            if cached_indices:
                self.logger.info(f"   💾 使用缓存: {len(cached_indices)} 个")
                self.metrics.increment('cache_hits', len(cached_indices))
            
            # 批量 embedding
            if texts_to_embed:
                self.logger.info(f"   🔄 Embedding: {len(texts_to_embed)} 个...")
                
                indices, texts = zip(*texts_to_embed)
                
                try:
                    embeddings = self.embedder.embed_batch(
                        list(texts),
                        batch_size=self.settings.embedding.batch_size,
                        show_progress=False
                    )
                    
                    # 分配 embeddings 并缓存
                    for idx, emb in zip(indices, embeddings):
                        documents[idx]['vector'] = emb
                        
                        # 缓存
                        if self.cache:
                            self.cache.set(documents[idx]['text'], emb)
                    
                    self.metrics.increment('embeddings_generated', len(embeddings))
                    
                except Exception as e:
                    self.logger.error(f"❌ Embedding 失败: {e}")
                    raise
            
            return documents
                
    def upsert_to_qdrant(self, documents: List[Dict]):
        """
        上传文档到 Qdrant（分批上传，避免 payload 过大）
        
        Args:
            documents: 文档列表
        """
        import time
        
        with self.metrics.timer('qdrant_upsert'):
            try:
                # 构建 points
                all_points = []
                for doc in documents:
                    point = PointStruct(
                        id=str(uuid.uuid5(uuid.NAMESPACE_DNS, doc['id'])),
                        vector=doc['vector'],
                        payload={
                            'text': doc['text'],
                            'metadata': doc['metadata']
                        }
                    )
                    all_points.append(point)
                
                # 分批上传（避免 payload 过大）
                # Qdrant 限制：32MB per request
                # 每个向量约 3072 * 4 bytes = 12KB + text + metadata ≈ 40KB
                # 安全批次：500 个点 ≈ 20MB
                batch_size = 500
                total_uploaded = 0
                
                self.logger.info(f"   准备上传 {len(all_points)} 个向量（分 {(len(all_points)-1)//batch_size + 1} 批）")
                
                for i in range(0, len(all_points), batch_size):
                    batch = all_points[i:i + batch_size]
                    batch_num = i // batch_size + 1
                    total_batches = (len(all_points) - 1) // batch_size + 1
                    
                    self.logger.info(f"   📤 上传批次 {batch_num}/{total_batches} ({len(batch)} 个向量)")
                    
                    # 批量上传
                    self.qdrant.upsert(
                        collection_name=self.settings.qdrant.collection_name,
                        points=batch
                    )
                    
                    total_uploaded += len(batch)
                    
                    # 批次间短暂延迟（避免过载）
                    if i + batch_size < len(all_points):
                        time.sleep(1)
                
                self.logger.info(f"✅ 全部上传完成: {total_uploaded} 个向量")
                self.metrics.increment('vectors_upserted', total_uploaded)
                
            except Exception as e:
                self.logger.error(f"❌ Qdrant 上传失败: {e}")
                raise
                    
    def ingest_directory(
        self,
        directory: Path,
        category: str = None,
        recursive: bool = True
    ):
        """
        摄取整个目录
        
        Args:
            directory: 目录路径
            category: 文档分类
            recursive: 是否递归处理
        """
        self.logger.info(f"📂 处理目录: {directory}")
        
        # 支持的文件类型
        file_extensions = ['.txt', '.md', '.pdf', '.html', '.htm']
        
        # 收集文件
        file_batches = list(file_batch_iterator(
            directory,
            file_extensions,
            batch_size=self.settings.processing.batch_size,
            recursive=recursive
        ))
        
        total_files = sum(len(batch) for batch in file_batches)
        self.logger.info(f"📊 找到 {total_files} 个文件")
        
        if total_files == 0:
            self.logger.warning("⚠️  未找到可处理的文件")
            return
        
        # 处理文件
        for batch in show_progress(
            file_batches,
            desc="处理文件批次",
            total=len(file_batches)
        ):
            # 1. 处理文档
            all_documents = []
            for file_path in batch:
                docs = self.process_document(file_path, category)
                all_documents.extend(docs)
            
            if not all_documents:
                continue
            
            # 2. 生成 embeddings
            try:
                all_documents = self.embed_documents(all_documents)
            except Exception as e:
                self.logger.error(f"❌ Embedding 批次失败: {e}")
                if not self.settings.processing.skip_errors:
                    raise
                continue
            
            # 3. 上传到 Qdrant
            try:
                self.upsert_to_qdrant(all_documents)
            except Exception as e:
                self.logger.error(f"❌ Qdrant 上传批次失败: {e}")
                if not self.settings.processing.skip_errors:
                    raise
                continue
        
        # 打印统计
        self.logger.info("\n" + "="*60)
        self.logger.info("📊 摄取完成")
        self.logger.info("="*60)
        self.metrics.print_stats()
        
        # 缓存统计
        if self.cache:
            self.cache.stats()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="RAG 文档摄取工具 - Azure OpenAI 版本"
    )
    parser.add_argument(
        "directory",
        type=str,
        help="文档目录路径"
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config/config_azure.yaml",
        help="配置文件路径"
    )
    parser.add_argument(
        "--category",
        type=str,
        help="文档分类（如果不指定则自动检测）"
    )
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="不递归处理子目录"
    )
    
    args = parser.parse_args()
    
    # 验证目录
    directory = Path(args.directory)
    if not directory.exists():
        print(f"❌ 目录不存在: {directory}")
        sys.exit(1)
    
    if not directory.is_dir():
        print(f"❌ 不是目录: {directory}")
        sys.exit(1)
    
    # 创建摄取器
    try:
        ingester = DocumentIngester(args.config)
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        sys.exit(1)
    
    # 运行摄取
    try:
        ingester.ingest_directory(
            directory,
            category=args.category,
            recursive=not args.no_recursive
        )
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断")
        ingester.metrics.print_stats()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 摄取失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
