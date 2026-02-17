# document_cleaner_enhanced.py
"""
增强版文档清洗工具 - 集成NLTK和spaCy
提供更智能的句子分割、实体识别、关键词提取
"""
import re
from typing import List, Dict, Optional
from bs4 import BeautifulSoup

# 可选导入 - 如果库不存在会回退到基础版本
try:
    import chardet
    HAS_CHARDET = True
except ImportError:
    HAS_CHARDET = False
    print("⚠️ chardet未安装，使用UTF-8编码（可能出现乱码）")

try:
    import nltk
    from nltk.tokenize import sent_tokenize
    HAS_NLTK = True
    # 自动下载必要的数据
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        print("📥 下载NLTK punkt数据...")
        nltk.download('punkt', quiet=True)
        nltk.download('punkt_tab', quiet=True)
except ImportError:
    HAS_NLTK = False
    print("⚠️ NLTK未安装，使用简单正则分割句子")

try:
    import spacy
    HAS_SPACY = True
    # 尝试加载模型
    try:
        nlp_zh = spacy.load("zh_core_web_sm")
        nlp_en = spacy.load("en_core_web_sm")
        print("✅ spaCy模型已加载（中文+英文）")
    except OSError:
        print("⚠️ spaCy模型未安装")
        print("   安装命令:")
        print("   python -m spacy download zh_core_web_sm")
        print("   python -m spacy download en_core_web_sm")
        HAS_SPACY = False
        nlp_zh = None
        nlp_en = None
except ImportError:
    HAS_SPACY = False
    nlp_zh = None
    nlp_en = None
    print("⚠️ spaCy未安装，无法使用NLP功能")


class EnhancedDocumentCleaner:
    """增强版文档清洗类 - 支持NLTK和spaCy"""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.remove_patterns = self.config.get('remove_patterns', [])
        self.min_line_length = self.config.get('min_line_length', 10)
        
        # 功能标志
        self.use_chardet = HAS_CHARDET
        self.use_nltk = HAS_NLTK
        self.use_spacy = HAS_SPACY
        
        print(f"📊 增强功能状态:")
        print(f"   Chardet: {'✅' if self.use_chardet else '❌'}")
        print(f"   NLTK: {'✅' if self.use_nltk else '❌'}")
        print(f"   spaCy: {'✅' if self.use_spacy else '❌'}")
    
    def load_file_with_encoding(self, file_path: str) -> str:
        """
        智能加载文件 - 自动检测编码
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件内容（str）
        """
        if self.use_chardet:
            # 使用chardet自动检测编码
            with open(file_path, 'rb') as f:
                raw_data = f.read()
            
            result = chardet.detect(raw_data)
            encoding = result['encoding']
            confidence = result['confidence']
            
            if confidence < 0.7:
                print(f"⚠️ 编码检测置信度较低: {confidence:.2f}, 使用UTF-8")
                encoding = 'utf-8'
            
            try:
                return raw_data.decode(encoding)
            except:
                # 回退到UTF-8
                return raw_data.decode('utf-8', errors='ignore')
        else:
            # 回退到基础方法
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    return f.read()
    
    def clean_text(self, text: str, source_type: str = 'txt') -> str:
        """清洗文本（与基础版本相同）"""
        if not text or not text.strip():
            return ""
            
        if source_type in ['html', 'htm']:
            text = self._clean_html(text)
        elif source_type == 'pdf':
            text = self._clean_pdf(text)
        
        text = self._general_clean(text)
        
        return text.strip()
    
    def _clean_html(self, html_content: str) -> str:
        """清洗HTML内容"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            for script in soup(['script', 'style', 'meta', 'link', 'noscript']):
                script.decompose()
            
            text = soup.get_text(separator='\n')
            lines = [line.strip() for line in text.split('\n')]
            lines = [line for line in lines if line]
            
            return '\n'.join(lines)
        except Exception as e:
            print(f"HTML清洗失败: {e}")
            return html_content
    
    def _clean_pdf(self, text: str) -> str:
        """清洗PDF文本"""
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            
            if not line:
                continue
            
            if re.match(r'^[-\s]*\d+[-\s]*$', line):
                continue
            if re.match(r'^Page\s+\d+\s+of\s+\d+$', line, re.IGNORECASE):
                continue
            if re.match(r'^Copyright.*$', line, re.IGNORECASE):
                continue
            if re.match(r'^©.*$', line):
                continue
            if 'All rights reserved' in line:
                continue
            
            if len(line) < self.min_line_length:
                continue
            
            cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)
    
    def _general_clean(self, text: str) -> str:
        """通用文本清洗"""
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        for pattern in self.remove_patterns:
            text = re.sub(pattern, '', text, flags=re.MULTILINE | re.IGNORECASE)
        
        lines = [line.strip() for line in text.split('\n')]
        text = '\n'.join(lines)
        
        return text
    
    def extract_metadata_enhanced(self, text: str, source_path: str, language: str = 'auto') -> dict:
        """
        增强版元数据提取 - 使用spaCy
        
        Args:
            text: 文档内容
            source_path: 文件路径
            language: 语言（'zh', 'en', 'auto'）
            
        Returns:
            包含丰富元数据的字典
        """
        metadata = {
            'source': source_path,
            'word_count': len(text.split()),
            'char_count': len(text)
        }
        
        # 基础标题提取
        lines = text.split('\n')[:10]
        for line in lines:
            line = line.strip()
            if len(line) > 10 and len(line) < 200:
                if not line[0].isdigit():
                    metadata['title'] = line
                    break
        
        # 基础摘要
        clean_text = ' '.join(text.split())
        metadata['summary'] = clean_text[:200] + '...' if len(clean_text) > 200 else clean_text
        
        # 如果有spaCy，提取更多信息
        if self.use_spacy:
            try:
                # 自动检测语言
                if language == 'auto':
                    # 简单启发式：检查中文字符比例
                    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text[:1000]))
                    is_chinese = chinese_chars > 50
                    nlp = nlp_zh if is_chinese else nlp_en
                else:
                    nlp = nlp_zh if language == 'zh' else nlp_en
                
                if nlp is None:
                    return metadata
                
                # 只处理前5000字符（性能考虑）
                doc = nlp(text[:5000])
                
                # 提取命名实体
                entities = {
                    'persons': [],
                    'organizations': [],
                    'locations': [],
                    'products': [],
                    'other': []
                }
                
                for ent in doc.ents:
                    if ent.label_ in ['PERSON', 'PER']:
                        entities['persons'].append(ent.text)
                    elif ent.label_ in ['ORG', 'ORGANIZATION']:
                        entities['organizations'].append(ent.text)
                    elif ent.label_ in ['GPE', 'LOC', 'LOCATION']:
                        entities['locations'].append(ent.text)
                    elif ent.label_ in ['PRODUCT', 'WORK_OF_ART']:
                        entities['products'].append(ent.text)
                    else:
                        entities['other'].append(ent.text)
                
                # 去重
                for key in entities:
                    entities[key] = list(set(entities[key]))[:5]  # 最多保留5个
                
                metadata['entities'] = entities
                
                # 提取关键词（名词和专有名词）
                keywords = []
                for token in doc:
                    if token.pos_ in ['NOUN', 'PROPN'] and len(token.text) > 2:
                        keywords.append(token.text)
                
                # 统计频率，取top 10
                from collections import Counter
                keyword_freq = Counter(keywords)
                metadata['keywords'] = [kw for kw, _ in keyword_freq.most_common(10)]
                
            except Exception as e:
                print(f"⚠️ spaCy元数据提取失败: {e}")
        
        return metadata


def smart_chunk_text_enhanced(
    text: str,
    chunk_size: int = 800,
    overlap: int = 150,
    min_chunk_size: int = 100,
    respect_sentence: bool = True,
    language: str = 'auto'
) -> List[str]:
    """
    增强版智能文本分块 - 使用NLTK或spaCy
    
    Args:
        text: 输入文本
        chunk_size: 目标块大小
        overlap: 重叠大小
        min_chunk_size: 最小块大小
        respect_sentence: 是否尊重句子边界
        language: 语言（'zh', 'en', 'auto'）
        
    Returns:
        文本块列表
    """
    if not text or len(text.strip()) < min_chunk_size:
        return []
    
    if not respect_sentence:
        # 简单字符分块
        return _chunk_by_chars(text, chunk_size, overlap, min_chunk_size)
    
    # 尝试使用spaCy（最佳）
    if HAS_SPACY:
        try:
            # 检测语言
            if language == 'auto':
                chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text[:1000]))
                is_chinese = chinese_chars > 50
                nlp = nlp_zh if is_chinese else nlp_en
            else:
                nlp = nlp_zh if language == 'zh' else nlp_en
            
            if nlp is not None:
                return _chunk_by_spacy(text, chunk_size, overlap, min_chunk_size, nlp)
        except Exception as e:
            print(f"⚠️ spaCy分块失败，回退到NLTK: {e}")
    
    # 回退到NLTK
    if HAS_NLTK:
        try:
            return _chunk_by_nltk(text, chunk_size, overlap, min_chunk_size)
        except Exception as e:
            print(f"⚠️ NLTK分块失败，回退到正则: {e}")
    
    # 最终回退到正则
    return _chunk_by_sentences_regex(text, chunk_size, overlap, min_chunk_size)


def _chunk_by_spacy(text: str, chunk_size: int, overlap: int, min_size: int, nlp) -> List[str]:
    """
    使用spaCy分块 - 最智能的方式
    考虑句子边界和实体边界
    """
    # 分段处理（spaCy处理长文本较慢）
    max_chars_per_batch = 100000
    all_sentences = []
    
    for i in range(0, len(text), max_chars_per_batch):
        batch = text[i:i + max_chars_per_batch]
        doc = nlp(batch)
        all_sentences.extend([sent.text for sent in doc.sents])
    
    return _build_chunks_from_sentences(all_sentences, chunk_size, overlap, min_size)


def _chunk_by_nltk(text: str, chunk_size: int, overlap: int, min_size: int) -> List[str]:
    """使用NLTK分块 - 较好的方式"""
    try:
        sentences = sent_tokenize(text)
        return _build_chunks_from_sentences(sentences, chunk_size, overlap, min_size)
    except Exception as e:
        print(f"NLTK分块错误: {e}")
        return _chunk_by_sentences_regex(text, chunk_size, overlap, min_size)


def _chunk_by_sentences_regex(text: str, chunk_size: int, overlap: int, min_size: int) -> List[str]:
    """使用正则分块 - 基础方式"""
    sentences = re.split(r'([.!?。！？]\s+)', text)
    
    full_sentences = []
    for i in range(0, len(sentences), 2):
        if i + 1 < len(sentences):
            full_sentences.append(sentences[i] + sentences[i + 1])
        else:
            full_sentences.append(sentences[i])
    
    return _build_chunks_from_sentences(full_sentences, chunk_size, overlap, min_size)


def _build_chunks_from_sentences(sentences: List[str], chunk_size: int, overlap: int, min_size: int) -> List[str]:
    """从句子列表构建分块"""
    chunks = []
    current_chunk = []
    current_size = 0
    
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        
        sentence_len = len(sentence)
        
        if current_size + sentence_len > chunk_size and current_chunk:
            # 保存当前块
            chunk_text = ' '.join(current_chunk)
            if len(chunk_text) >= min_size:
                chunks.append(chunk_text)
            
            # 开始新块，保留overlap
            if overlap > 0:
                overlap_text = chunk_text[-overlap:] if len(chunk_text) > overlap else chunk_text
                current_chunk = [overlap_text, sentence]
                current_size = len(overlap_text) + sentence_len
            else:
                current_chunk = [sentence]
                current_size = sentence_len
        else:
            current_chunk.append(sentence)
            current_size += sentence_len
    
    # 添加最后一块
    if current_chunk:
        chunk_text = ' '.join(current_chunk)
        if len(chunk_text) >= min_size:
            chunks.append(chunk_text)
    
    return chunks


def _chunk_by_chars(text: str, chunk_size: int, overlap: int, min_size: int) -> List[str]:
    """简单的字符级分块（回退方案）"""
    chunks = []
    start = 0
    text_len = len(text)
    
    while start < text_len:
        end = min(start + chunk_size, text_len)
        chunk = text[start:end].strip()
        
        if len(chunk) >= min_size:
            chunks.append(chunk)
        
        start = end - overlap
        if start <= 0:
            break
    
    return chunks


# 使用示例
if __name__ == "__main__":
    # 创建增强版清洗器
    cleaner = EnhancedDocumentCleaner()
    
    # 测试文本
    test_text = """
    Dr. Smith从OpenAI学习了GPT-4的架构设计。他说："U.S.A.的AI发展很快！"
    微软Azure提供了API服务。版本v2.1.3已经发布。
    Kubernetes是一个容器编排平台，由Google开发。
    """
    
    # 测试元数据提取
    print("\n" + "="*60)
    print("📊 元数据提取测试")
    print("="*60)
    
    metadata = cleaner.extract_metadata_enhanced(test_text, "test.txt")
    
    print(f"\n标题: {metadata.get('title', 'N/A')}")
    print(f"字数: {metadata['word_count']}")
    print(f"字符数: {metadata['char_count']}")
    
    if 'entities' in metadata:
        print("\n🏷️ 实体识别:")
        for entity_type, entities in metadata['entities'].items():
            if entities:
                print(f"  {entity_type}: {', '.join(entities)}")
    
    if 'keywords' in metadata:
        print(f"\n🔑 关键词: {', '.join(metadata['keywords'])}")
    
    # 测试分块
    print("\n" + "="*60)
    print("✂️ 智能分块测试")
    print("="*60)
    
    chunks = smart_chunk_text_enhanced(test_text, chunk_size=100, overlap=20)
    
    print(f"\n生成 {len(chunks)} 个分块:\n")
    for i, chunk in enumerate(chunks, 1):
        print(f"块 {i}: {chunk[:80]}...")
        print()
