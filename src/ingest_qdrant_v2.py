#!/usr/bin/env python3
# ingest_qdrant_v2.py
"""
RAG 文档摄取脚本 - Azure OpenAI 版本
支持增强的文本处理和 Azure OpenAI embedding
"""
import uuid
import argparse
import sys
import hashlib
import re
from pathlib import Path
from typing import List, Dict
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)

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
            cache_dir = Path(self.settings.processing.cache_dir)
            if not cache_dir.is_absolute():
                cache_dir = project_root / cache_dir
            self.cache = DiskCache(str(cache_dir))
            self.cache_namespace = (
                f"embedding:{self.settings.embedding.provider}:"
                f"{self.settings.embedding.model}:{self.embedder.deployment_name}:{self.embedder.api_version}"
            )
            self.logger.info(f"✅ Embedding 缓存: {cache_dir}")
        else:
            self.cache = None
            self.cache_namespace = ""
        
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
        category: str = None,
        ingest_root: Path = None
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

                if not cleaned or len(cleaned.strip()) < 50:
                    self.logger.warning(f"⚠️  清洗后内容过短，跳过: {file_path.name}")
                    return []
                    
                # 3. 提取元数据
                with self.metrics.timer('metadata_extraction'):
                    metadata = self.cleaner.extract_metadata_enhanced(
                        cleaned,
                        str(file_path)
                    )
                
                # 4. 分类策略（优先目录名，再回退自动分类）
                effective_category = category
                if not effective_category and ingest_root:
                    try:
                        rel_path = file_path.resolve().relative_to(ingest_root.resolve())
                        if len(rel_path.parts) > 1:
                            folder_category = rel_path.parts[0]
                            if self.settings.get_category_by_name(folder_category):
                                effective_category = folder_category
                                self.logger.info(f"   目录分类: {effective_category}")
                    except Exception:
                        pass

                if not effective_category:
                    detected_category = self.settings.auto_categorize(cleaned)
                    effective_category = detected_category.name
                    self.logger.info(f"   自动分类: {effective_category}")
                
                # 5. 分块
                with self.metrics.timer('text_chunking'):
                    chunks = smart_chunk_text_enhanced(
                        cleaned,
                        chunk_size=self.settings.chunking.chunk_size,
                        overlap=self.settings.chunking.overlap,
                        min_chunk_size=self.settings.chunking.min_chunk_size,
                        respect_sentence=self.settings.chunking.respect_sentence,
                        language=self.settings.chunking.language,
                        use_nltk=self.settings.chunking.use_nltk,
                        use_spacy=self.settings.chunking.use_spacy,
                    )

                # 文件内分块去重，降低噪音和向量冗余
                unique_chunks = []
                seen_chunk_hashes = set()
                for chunk in chunks:
                    chunk_hash = hashlib.md5(chunk.encode("utf-8")).hexdigest()
                    if chunk_hash in seen_chunk_hashes:
                        continue
                    seen_chunk_hashes.add(chunk_hash)
                    unique_chunks.append(chunk)
                removed_dup_chunks = len(chunks) - len(unique_chunks)
                chunks = unique_chunks
                
                if not chunks:
                    self.logger.warning(f"⚠️  无法分块: {file_path.name}")
                    return []
                
                # 6. 构建文档块
                documents = []
                dropped_quality = 0
                resolved_path = file_path.resolve()
                source_path = str(resolved_path)
                if ingest_root:
                    try:
                        source_rel_path = str(resolved_path.relative_to(ingest_root.resolve()))
                    except Exception:
                        source_rel_path = str(file_path)
                else:
                    source_rel_path = str(file_path)
                source_id = hashlib.sha1(source_rel_path.encode("utf-8")).hexdigest()
                base_metadata = dict(metadata)
                base_metadata.pop("source", None)

                for i, chunk in enumerate(chunks):
                    if self.settings.quality.enabled:
                        if not self._passes_quality_gate(chunk):
                            dropped_quality += 1
                            continue

                    chunk_hash = hashlib.md5(chunk.encode("utf-8")).hexdigest()
                    doc = {
                        'id': f"{source_id}:{i}:{chunk_hash[:16]}",
                        'text': chunk,
                        'metadata': {
                            **base_metadata,
                            'source': str(file_path.name),
                            'source_path': source_path,
                            'source_rel_path': source_rel_path,
                            'source_id': source_id,
                            'category': effective_category,
                            'chunk_index': i,
                            'total_chunks': len(chunks),
                            'chunk_hash': chunk_hash,
                            'file_type': extension,
                        }
                    }
                    documents.append(doc)
                
                if removed_dup_chunks:
                    self.logger.info(f"   🧹 去重分块: 删除 {removed_dup_chunks} 个重复块")
                if dropped_quality:
                    self.logger.info(f"   🚧 质量闸门: 过滤 {dropped_quality} 个低质量块")
                    self.metrics.increment('chunks_dropped_quality', dropped_quality)
                if not documents:
                    self.logger.warning(f"⚠️  质量过滤后无有效块: {file_path.name}")
                    return []
                self.logger.info(f"✅ {file_path.name}: {len(documents)} 块")
                self.metrics.increment('documents_processed')
                self.metrics.increment('chunks_created', len(documents))
                
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
            unique_text_to_indices = {}
            cached_indices = []
            dedup_saved = 0
            
            for i, doc in enumerate(documents):
                text = doc['text']
                
                # 检查缓存
                if self.cache:
                    cached_emb = self.cache.get(text, namespace=self.cache_namespace)
                    if cached_emb is not None:
                        doc['vector'] = cached_emb
                        cached_indices.append(i)
                        continue
                
                if text in unique_text_to_indices:
                    unique_text_to_indices[text].append(i)
                    dedup_saved += 1
                else:
                    unique_text_to_indices[text] = [i]
            
            if cached_indices:
                self.logger.info(f"   💾 使用缓存: {len(cached_indices)} 个")
                self.metrics.increment('cache_hits', len(cached_indices))

            if dedup_saved:
                self.logger.info(f"   🔁 批内去重: 复用 {dedup_saved} 个重复块")
                self.metrics.increment('batch_dedup_hits', dedup_saved)
            
            # 批量 embedding
            if unique_text_to_indices:
                unique_texts = list(unique_text_to_indices.keys())
                self.logger.info(
                    f"   🔄 Embedding: {len(unique_texts)} 个唯一文本（总块 {len(documents)}）..."
                )
                
                try:
                    embeddings = self.embedder.embed_batch(
                        unique_texts,
                        batch_size=self.settings.embedding.batch_size,
                        show_progress=False
                    )
                    
                    # 分配 embeddings 并缓存
                    for text, emb in zip(unique_texts, embeddings):
                        for idx in unique_text_to_indices[text]:
                            documents[idx]['vector'] = emb
                        if self.cache:
                            self.cache.set(text, emb, namespace=self.cache_namespace)
                    
                    self.metrics.increment('embeddings_generated', len(embeddings))
                    
                except Exception as e:
                    self.logger.error(f"❌ Embedding 失败: {e}")
                    raise
            
            return documents

    @staticmethod
    def _text_information_density(text: str) -> float:
        if not text:
            return 0.0
        informative = 0
        for ch in text:
            if ch.isalnum() or ('\u4e00' <= ch <= '\u9fff'):
                informative += 1
        return informative / len(text)

    @staticmethod
    def _non_text_ratio(text: str) -> float:
        if not text:
            return 1.0
        non_text = 0
        for ch in text:
            if ch.isspace():
                continue
            if ch.isalnum() or ('\u4e00' <= ch <= '\u9fff'):
                continue
            if ch in ".,!?;:，。！？；：（）()[]{}-_/\"'`%":
                continue
            non_text += 1
        return non_text / max(1, len(text))

    def _passes_quality_gate(self, chunk: str) -> bool:
        quality = self.settings.quality
        if len(chunk) < quality.min_chunk_chars:
            return False

        if quality.drop_numeric_only and re.fullmatch(r"[\d\W_]+", chunk):
            return False

        info_density = self._text_information_density(chunk)
        if info_density < quality.min_information_density:
            return False

        non_text = self._non_text_ratio(chunk)
        if non_text > quality.max_non_text_ratio:
            return False

        return True
                
    def upsert_to_qdrant(self, documents: List[Dict]):
        """
        上传文档到 Qdrant（分批上传，避免 payload 过大）
        
        Args:
            documents: 文档列表
        """
        import time
        
        with self.metrics.timer('qdrant_upsert'):
            try:
                if self.settings.processing.replace_existing_source:
                    source_paths = sorted({
                        doc.get('metadata', {}).get('source_path')
                        for doc in documents
                        if doc.get('metadata', {}).get('source_path')
                    })
                    for source_path in source_paths:
                        selector = Filter(
                            must=[
                                FieldCondition(
                                    key="metadata.source_path",
                                    match=MatchValue(value=source_path),
                                )
                            ]
                        )
                        self.qdrant.delete(
                            collection_name=self.settings.qdrant.collection_name,
                            points_selector=selector,
                            wait=True,
                        )
                    if source_paths:
                        self.logger.info(f"   ♻️ 已清理旧数据源: {len(source_paths)} 个")

                # 构建 points
                all_points = []
                for doc in documents:
                    if 'vector' not in doc:
                        self.logger.warning(f"⚠️  缺少向量，跳过: {doc.get('id')}")
                        continue
                    point = PointStruct(
                        id=str(uuid.uuid5(uuid.NAMESPACE_DNS, doc['id'])),
                        vector=doc['vector'],
                        payload={
                            'text': doc['text'],
                            'metadata': doc['metadata']
                        }
                    )
                    all_points.append(point)

                if not all_points:
                    self.logger.warning("⚠️  无可上传向量，跳过")
                    return
                
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
                docs = self.process_document(file_path, category, ingest_root=directory)
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
