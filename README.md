# RAG System — 基于 Azure OpenAI + Qdrant 的检索增强生成系统

一个支持中英文跨语言检索的 RAG（Retrieval-Augmented Generation）文档处理与查询系统，使用 Azure OpenAI `text-embedding-3-large` 生成向量，Qdrant 作为向量数据库。

---

## 功能特性

- **文档摄取**：支持 `.txt`、`.md`、`.pdf`、`.html` 格式
- **智能分块**：支持基于 spaCy / NLTK / 正则的句子感知分块，自动降级
- **跨语言检索**：中文查询可匹配英文文档，反之亦然
- **自动分类**：根据关键词自动将文档归类（AI Agent、CS 架构、机器学习、编程等）
- **Embedding 缓存**：磁盘级缓存，避免重复调用 API
- **增强元数据提取**：基于 spaCy 的命名实体识别（人名、机构、地点）和关键词提取
- **自动编码检测**：使用 `chardet` 处理 GBK / GB2312 等非 UTF-8 编码文件

---

## 项目结构

```
rag-system/
├── src/
│   ├── azure_embedding.py          # Azure OpenAI Embedding 客户端
│   ├── document_cleaner_enhanced.py # 增强版文档清洗与分块
│   ├── ingest_qdrant_v2.py         # 文档摄取主脚本
│   └── utils/
│       └── helpers.py              # 工具函数（日志、缓存、重试、进度条）
├── config/
│   ├── settings.py                 # 统一配置管理
│   ├── config_azure.yaml           # Azure OpenAI 配置（推荐使用）
│   └── config.yaml                 # 通用配置模板
├── query.py                        # 查询脚本（基础版）
├── query_search.py                 # 查询脚本（多查询测试版）
├── test_pdf_extraction.py          # PDF 文本提取测试工具
├── requirements.txt                # 基础依赖
├── requirements_enhanced.txt       # 增强依赖（含 NLTK / spaCy）
└── .env                            # 环境变量（不提交到 Git）
```

---

## 快速开始

### 1. 安装依赖

**基础安装：**
```bash
pip install -r requirements.txt
```

**增强安装（推荐，支持更好的分块和实体识别）：**
```bash
pip install -r requirements_enhanced.txt
pip install chardet nltk spacy

# 下载 NLTK 数据
python -m nltk.downloader punkt punkt_tab

# 下载 spaCy 语言模型
python -m spacy download zh_core_web_sm   # 中文
python -m spacy download en_core_web_sm   # 英文
```

### 2. 配置环境变量

在项目根目录创建 `.env` 文件：

```env
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key
AZURE_EMBEDDING_DEPLOYMENT=text-embedding-3-large
```

### 3. 启动 Qdrant

```bash
docker run -d \
  --name qdrant \
  -p 6333:6333 \
  -v $(pwd)/data/qdrant_storage:/qdrant/storage \
  qdrant/qdrant
```

> ⚠️ **重要**：务必挂载 `-v` 数据卷，否则容器删除后数据丢失。

验证 Qdrant 是否运行：
```bash
curl http://localhost:6333/collections
```

### 4. 摄取文档

将文档放入 `documents/` 目录，然后运行：

```bash
python src/ingest_qdrant_v2.py documents/ --config config/config_azure.yaml
```

可选参数：
```bash
# 指定分类
python src/ingest_qdrant_v2.py documents/ --category agentic_ai

# 不递归处理子目录
python src/ingest_qdrant_v2.py documents/ --no-recursive
```

### 5. 查询

```bash
# 基础查询
python query.py "AI Agent 是什么"
python query.py "What is Kubernetes"

# 多查询测试（中英文对比）
python query_search.py
```

---

## 配置说明

主配置文件为 `config/config_azure.yaml`，关键参数：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `qdrant.vector_size` | 3072 | text-embedding-3-large 的维度 |
| `chunking.chunk_size` | 1000 | 每块目标字符数 |
| `chunking.overlap` | 200 | 块间重叠字符数 |
| `embedding.batch_size` | 20 | 每批 Embedding 请求数量 |
| `processing.batch_size` | 2 | 每批处理文件数 |
| `processing.enable_caching` | true | 启用磁盘缓存 |

---

## 文档分块策略

系统按优先级依次尝试以下分块方式，自动降级：

1. **spaCy**（最优）— 理解句子结构和实体边界
2. **NLTK**（较好）— 基于统计的句子分割，正确处理缩写
3. **正则表达式**（基础）— 按句子结束符分割

---

## Qdrant 管理

### 启动（带持久化）
```bash
docker run -d \
  --name qdrant \
  -p 6333:6333 \
  -v $(pwd)/data/qdrant_storage:/qdrant/storage \
  qdrant/qdrant
```

### 停止 / 重启（不删除数据）
```bash
docker stop qdrant
docker start qdrant
```

### 查看集合信息
```bash
curl http://localhost:6333/collections/rag_documents
```

### 删除集合（慎用）
```bash
curl -X DELETE http://localhost:6333/collections/rag_documents
```

---

## 工具脚本

### 测试 PDF 文本提取质量
```bash
python test_pdf_extraction.py your_paper.pdf
```

### 对比基础版 vs 增强版分块效果
```bash
python src/compare_versions.py
```

---

## 依赖说明

| 库 | 是否必需 | 用途 |
|----|---------|------|
| `qdrant-client` | ✅ 必需 | 向量数据库客户端 |
| `requests` | ✅ 必需 | HTTP 请求 |
| `pypdf` | ✅ 必需 | PDF 文本提取 |
| `beautifulsoup4` | ✅ 必需 | HTML 解析 |
| `python-dotenv` | ✅ 必需 | 环境变量加载 |
| `chardet` | ⭐ 推荐 | 自动检测文件编码，避免中文乱码 |
| `nltk` | ⭐ 推荐 | 更准确的句子分割 |
| `spacy` | 🔵 可选 | 命名实体识别、关键词提取 |

---

## 注意事项

- Azure OpenAI 有速率限制，系统内置了自动重试和速率保护（每分钟最多 50 次请求）
- 处理大量文档时建议开启缓存（`enable_caching: true`），避免重复计费
- `text-embedding-3-large` 最大输入约 8191 tokens，系统自动截断超长文本
- Qdrant 数据默认存储在内存中，**必须挂载数据卷**才能持久化
