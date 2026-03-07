# document_cleaner_enhanced.py - FIXED VERSION
"""
增强版文档清洗工具 - 修复版
主要改进：
1. Title提取：优先使用文件名，避免提取到正文
2. Summary生成：扩展到500字符或前3句话
3. 为每个chunk添加特定的chunk_summary
"""
import re
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
from pathlib import Path

# 可选导入
try:
    import chardet
    HAS_CHARDET = True
except ImportError:
    HAS_CHARDET = False
    print("⚠️ chardet未安装，使用UTF-8编码（可能出现乱码）")

try:
    import nltk
    from nltk.tokenize import sent_tokenize
    HAS_NLTK = False
    try:
        nltk.data.find('tokenizers/punkt')
        HAS_NLTK = True
    except LookupError:
        print("⚠️ NLTK punkt 数据缺失，将回退到正则分句")
except ImportError:
    HAS_NLTK = False
    print("⚠️ NLTK未安装，使用简单正则分割句子")

try:
    import spacy
    HAS_SPACY = True
    try:
        nlp_zh = spacy.load("zh_core_web_sm")
        nlp_en = spacy.load("en_core_web_sm")
        print("✅ spaCy模型已加载（中文+英文）")
    except OSError:
        print("⚠️ spaCy模型未安装")
        HAS_SPACY = False
        nlp_zh = None
        nlp_en = None
except ImportError:
    HAS_SPACY = False
    nlp_zh = None
    nlp_en = None
    print("⚠️ spaCy未安装，无法使用NLP功能")

try:
    from pypdf import PdfReader
    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False
    print("⚠️ pypdf未安装，PDF将无法可靠抽取正文")


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
        self.use_pypdf = HAS_PYPDF
        
        print(f"📊 增强功能状态:")
        print(f"   Chardet: {'✅' if self.use_chardet else '❌'}")
        print(f"   NLTK: {'✅' if self.use_nltk else '❌'}")
        print(f"   spaCy: {'✅' if self.use_spacy else '❌'}")
        print(f"   pypdf: {'✅' if self.use_pypdf else '❌'}")
    
    def load_file_with_encoding(self, file_path: str) -> str:
        """智能加载文件 - 自动检测编码"""
        path = Path(file_path)
        ext = path.suffix.lower()

        if ext == '.pdf':
            return self._extract_pdf_text(path)

        if ext in ['.html', '.htm']:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    return f.read()

        if self.use_chardet:
            with open(path, 'rb') as f:
                raw_data = f.read()
            
            result = chardet.detect(raw_data)
            encoding = result['encoding']
            confidence = result['confidence'] or 0.0
            
            if confidence < 0.7:
                print(f"⚠️ 编码检测置信度较低: {confidence:.2f}, 使用UTF-8")
                encoding = 'utf-8'
            
            try:
                return raw_data.decode(encoding)
            except Exception:
                return raw_data.decode('utf-8', errors='ignore')
        else:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    return f.read()

    @staticmethod
    def _normalize_line(line: str) -> str:
        line = re.sub(r'\s+', ' ', line).strip()
        return line

    def _extract_pdf_text(self, file_path: Path) -> str:
        """使用 pypdf 抽取 PDF 文本，并移除跨页高频页眉页脚噪音。"""
        if not HAS_PYPDF:
            return ""

        try:
            reader = PdfReader(str(file_path))
        except Exception as e:
            print(f"⚠️ PDF 读取失败: {file_path.name}: {e}")
            return ""

        page_texts: List[str] = []
        line_frequency: Dict[str, int] = {}

        for page in reader.pages:
            text = page.extract_text() or ""
            text = text.replace('\x00', ' ')
            page_texts.append(text)

            # 每页只计一次，避免同页重复行影响统计
            lines = {
                self._normalize_line(line)
                for line in text.splitlines()
                if self._normalize_line(line)
            }
            for line in lines:
                if 8 <= len(line) <= 120:
                    line_frequency[line] = line_frequency.get(line, 0) + 1

        if not page_texts:
            return ""

        # 出现在 60% 页面且至少 3 页的行，视为高频噪音（页眉页脚/水印说明）
        min_repeat = max(3, int(len(page_texts) * 0.6))
        noisy_lines = {line for line, cnt in line_frequency.items() if cnt >= min_repeat}

        cleaned_pages: List[str] = []
        for text in page_texts:
            kept = []
            for raw_line in text.splitlines():
                line = self._normalize_line(raw_line)
                if not line:
                    continue
                if line in noisy_lines:
                    continue
                kept.append(line)
            cleaned_pages.append('\n'.join(kept))

        return '\n\n'.join(cleaned_pages).strip()
    
    def clean_text(self, text: str, source_type: str = 'txt') -> str:
        """清洗文本"""
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
        # 仅去掉连续重复行，避免误删语义上重复但分散出现的内容
        deduped_lines = []
        prev_line = None
        for line in lines:
            if line and line == prev_line:
                continue
            deduped_lines.append(line)
            prev_line = line
        text = '\n'.join(deduped_lines)
        
        return text
    
    def extract_metadata_enhanced(
        self, 
        text: str, 
        source_path: str, 
        language: str = 'auto'
    ) -> dict:
        """
        🔧 改进版元数据提取
        
        主要改进：
        1. Title优先使用文件名（更可靠）
        2. Summary扩展到500字符或前3句话
        3. 添加更多有用的元数据
        """
        metadata = {
            'source': source_path,
            'word_count': len(text.split()),
            'char_count': len(text)
        }
        
        # ✅ 改进1：Title提取 - 优先使用文件名
        file_name = Path(source_path).stem
        # 清理文件名作为标题（替换下划线、短横线）
        title = file_name.replace('_', ' ').replace('-', ' ').strip()
        
        # 如果文件名太短或不合适，尝试从内容提取
        if len(title) < 3 or title.isdigit():
            lines = text.split('\n')[:15]  # 增加到前15行
            for line in lines:
                line = line.strip()
                # 寻找合适的标题行
                if 10 < len(line) < 200:
                    # 排除纯数字、日期、页码等
                    if not re.match(r'^[\d\s\-./]+$', line):
                        title = line
                        break
            
            # 如果还是没找到，用文件名
            if not title or len(title) < 3:
                title = file_name
        
        metadata['title'] = title[:200]  # 限制长度
        
        # ✅ 改进2：Summary生成 - 更长、更有信息量
        clean_text = ' '.join(text.split())
        
        # 尝试提取前3-5个句子作为摘要
        if HAS_NLTK:
            try:
                # 只处理前3000字符以提高性能
                sentences = sent_tokenize(clean_text[:3000])
                
                # 选择前3-5个句子，总长度不超过500字符
                summary_sentences = []
                summary_length = 0
                
                for sent in sentences[:5]:  # 最多5个句子
                    if summary_length + len(sent) <= 500:
                        summary_sentences.append(sent)
                        summary_length += len(sent)
                    else:
                        break
                
                if summary_sentences:
                    summary = ' '.join(summary_sentences)
                else:
                    summary = clean_text[:500]
                
                # 如果摘要被截断，添加省略号
                if len(clean_text) > len(summary):
                    summary = summary.rstrip() + '...'
                    
            except Exception as e:
                print(f"⚠️ NLTK摘要生成失败: {e}")
                summary = clean_text[:500] + '...' if len(clean_text) > 500 else clean_text
        else:
            # 回退方案：使用500字符
            summary = clean_text[:500] + '...' if len(clean_text) > 500 else clean_text
        
        metadata['summary'] = summary
        
        # ✅ 改进3：如果有spaCy，提取更多信息
        if self.use_spacy:
            try:
                # 自动检测语言
                if language == 'auto':
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
                
                # 去重并限制数量
                for key in entities:
                    entities[key] = list(set(entities[key]))[:5]
                
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
    
    def extract_chunk_metadata(self, chunk_text: str, chunk_index: int) -> dict:
        """
        🆕 为单个chunk提取特定的元数据
        
        这个方法可以在分块后调用，为每个chunk生成独特的摘要
        """
        chunk_meta = {}
        
        # 为chunk生成简短摘要（前100字符）
        clean_chunk = ' '.join(chunk_text.split())
        chunk_meta['chunk_summary'] = clean_chunk[:100] + '...' if len(clean_chunk) > 100 else clean_chunk
        
        # 提取chunk中的关键信息（简化版）
        # 例如：是否包含问题、是否包含代码等
        chunk_meta['has_question'] = '?' in chunk_text or '？' in chunk_text
        chunk_meta['has_code'] = bool(re.search(r'```|`\w+`|def |class |function ', chunk_text))
        
        return chunk_meta


# 保留原有的分块函数（不变）
def smart_chunk_text_enhanced(
    text: str,
    chunk_size: int = 800,
    overlap: int = 150,
    min_chunk_size: int = 100,
    respect_sentence: bool = True,
    language: str = 'auto',
    use_nltk: bool = True,
    use_spacy: bool = True,
) -> List[str]:
    """增强版智能文本分块"""
    if not text or len(text.strip()) < min_chunk_size:
        return []
    
    if not respect_sentence:
        return _chunk_by_chars(text, chunk_size, overlap, min_chunk_size)
    
    if use_spacy and HAS_SPACY:
        try:
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
    
    if use_nltk and HAS_NLTK:
        try:
            return _chunk_by_nltk(text, chunk_size, overlap, min_chunk_size)
        except Exception as e:
            print(f"⚠️ NLTK分块失败，回退到正则: {e}")
    
    return _chunk_by_sentences_regex(text, chunk_size, overlap, min_chunk_size)


def _chunk_by_spacy(text: str, chunk_size: int, overlap: int, min_size: int, nlp) -> List[str]:
    """使用spaCy分块"""
    max_chars_per_batch = 100000
    all_sentences = []
    
    for i in range(0, len(text), max_chars_per_batch):
        batch = text[i:i + max_chars_per_batch]
        doc = nlp(batch)
        all_sentences.extend([sent.text for sent in doc.sents])
    
    return _build_chunks_from_sentences(all_sentences, chunk_size, overlap, min_size)


def _chunk_by_nltk(text: str, chunk_size: int, overlap: int, min_size: int) -> List[str]:
    """使用NLTK分块"""
    try:
        sentences = sent_tokenize(text)
        return _build_chunks_from_sentences(sentences, chunk_size, overlap, min_size)
    except Exception as e:
        print(f"NLTK分块错误: {e}")
        return _chunk_by_sentences_regex(text, chunk_size, overlap, min_size)


def _chunk_by_sentences_regex(text: str, chunk_size: int, overlap: int, min_size: int) -> List[str]:
    """使用正则分块"""
    sentences = re.split(r'([.!?。！？]\s+)', text)
    
    full_sentences = []
    for i in range(0, len(sentences), 2):
        if i + 1 < len(sentences):
            full_sentences.append(sentences[i] + sentences[i + 1])
        else:
            full_sentences.append(sentences[i])
    
    return _build_chunks_from_sentences(full_sentences, chunk_size, overlap, min_size)


def _split_overlong_sentence(sentence: str, chunk_size: int) -> List[str]:
    """
    将异常超长“句子”切分成较短片段。
    真实 PDF/网页文本常出现缺少句号的超长段，若不拆分会导致超大 chunk。
    """
    sentence = sentence.strip()
    if not sentence:
        return []
    if len(sentence) <= chunk_size:
        return [sentence]

    segments: List[str] = []
    remaining = sentence

    while len(remaining) > chunk_size:
        # 优先在 chunk_size 附近寻找自然断点，避免硬切
        candidate_positions = [
            remaining.rfind("。", 0, chunk_size),
            remaining.rfind("！", 0, chunk_size),
            remaining.rfind("？", 0, chunk_size),
            remaining.rfind(".", 0, chunk_size),
            remaining.rfind("!", 0, chunk_size),
            remaining.rfind("?", 0, chunk_size),
            remaining.rfind("，", 0, chunk_size),
            remaining.rfind(",", 0, chunk_size),
            remaining.rfind("；", 0, chunk_size),
            remaining.rfind(";", 0, chunk_size),
            remaining.rfind(" ", 0, chunk_size),
        ]
        cut = max(candidate_positions)

        # 断点过早时，直接按长度切，避免过碎分片
        if cut < int(chunk_size * 0.6):
            cut = chunk_size

        part = remaining[:cut].strip()
        if part:
            segments.append(part)
        remaining = remaining[cut:].strip()

    if remaining:
        segments.append(remaining)

    return segments


def _build_chunks_from_sentences(sentences: List[str], chunk_size: int, overlap: int, min_size: int) -> List[str]:
    """从句子列表构建分块"""
    chunks = []
    current_chunk = []
    current_size = 0
    
    for raw_sentence in sentences:
        for sentence in _split_overlong_sentence(raw_sentence, chunk_size):
            sentence = sentence.strip()
            if not sentence:
                continue
            
            sentence_len = len(sentence)
            
            if current_size + sentence_len > chunk_size and current_chunk:
                chunk_text = ' '.join(current_chunk)
                if len(chunk_text) >= min_size:
                    chunks.append(chunk_text)
                
                if overlap > 0:
                    # 句子级 overlap：回溯当前块末尾句子，避免字符截断造成语义破碎
                    overlap_sentences = []
                    overlap_size = 0
                    for prev_sentence in reversed(current_chunk):
                        if overlap_size + len(prev_sentence) > overlap and overlap_sentences:
                            break
                        overlap_sentences.append(prev_sentence)
                        overlap_size += len(prev_sentence)
                        if overlap_size >= overlap:
                            break
                    overlap_sentences.reverse()

                    current_chunk = overlap_sentences + [sentence]
                    current_size = sum(len(s) for s in current_chunk)
                else:
                    current_chunk = [sentence]
                    current_size = sentence_len
            else:
                current_chunk.append(sentence)
                current_size += sentence_len
    
    if current_chunk:
        chunk_text = ' '.join(current_chunk)
        if len(chunk_text) >= min_size:
            chunks.append(chunk_text)
    
    return chunks


def _chunk_by_chars(text: str, chunk_size: int, overlap: int, min_size: int) -> List[str]:
    """简单的字符级分块"""
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


if __name__ == "__main__":
    print("\n" + "="*60)
    print("🧪 测试改进后的metadata提取")
    print("="*60)
    
    cleaner = EnhancedDocumentCleaner()
    
    # 模拟你的场景
    test_text = """
Anthropic 发现，在他们的内部研究评估中，一个以 Claude Opus 4 为主智能体、
Claude Sonnet 4 为子智能体的多智能体系统，其性能比单智能体的 Claude Opus 4 高出 90.2%。
当智能达到一定阈值，多智能体系统就成为扩展性能的重要方式。

就像人类社会意义，在过去相当漫长的时间里，人类的单体智能并未有显著式的增长，
但人类社会在信息时代的整体能力却在指数级提升。一方面是因为计算机/更强大工具的出现，
另一方面也是人类协作与群体智慧的结果。

过于严格的 hardcode 只会变成 if-else 式的工作流。
做到这点并不容易，需要careful prompt engineering和system design。
    """.strip()
    
    # 提取文档级metadata
    doc_metadata = cleaner.extract_metadata_enhanced(
        test_text, 
        "documents/agentic_ai/multi-agent-system.txt"
    )
    
    print("\n📄 文档级 Metadata:")
    print(f"  Title: {doc_metadata['title']}")
    print(f"  Summary: {doc_metadata['summary'][:100]}...")
    print(f"  Word Count: {doc_metadata['word_count']}")
    
    # 分块
    chunks = smart_chunk_text_enhanced(test_text, chunk_size=200, overlap=50)
    print(f"\n✂️  生成 {len(chunks)} 个chunks")
    
    # 为第一个chunk生成特定metadata
    chunk_meta = cleaner.extract_chunk_metadata(chunks[0], 0)
    print(f"\n📦 Chunk 0 的特定metadata:")
    print(f"  Chunk Summary: {chunk_meta['chunk_summary']}")
    print(f"  Has Question: {chunk_meta['has_question']}")
    print(f"  Has Code: {chunk_meta['has_code']}")
    
    print("\n✅ 改进后的metadata更准确！")
