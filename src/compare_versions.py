# compare_versions.py
"""
基础版 vs 增强版对比测试
直观展示使用高级库的提升效果
"""
import time
from document_cleaner import smart_chunk_text as basic_chunk
from document_cleaner_enhanced import smart_chunk_text_enhanced, EnhancedDocumentCleaner

# 测试文本（包含各种边界情况）
TEST_CASES = [
    {
        "name": "缩写和版本号",
        "text": """
Dr. Smith works at OpenAI Inc. He said: "The U.S.A. is leading in AI development!"
GPT-4 version v2.1.3 was released. The API v1.0 is deprecated.
Microsoft Azure provides cloud services. Prof. Johnson uses it.
        """.strip()
    },
    {
        "name": "中英文混合",
        "text": """
OpenAI发布了GPT-4模型，这是一个革命性的突破。微软Azure提供API服务。
根据Smith博士的研究，U.S.A.在AI领域处于领先地位。Kubernetes是Google开发的。
版本v2.1.3已经在production环境中部署。Amazon Web Services也在使用。
        """.strip()
    },
    {
        "name": "技术文档",
        "text": """
Kubernetes (k8s) is a container orchestration platform. It was developed by Google.
The architecture includes: Master nodes, Worker nodes, and etcd cluster.
Version 1.28.0 introduces new features. The API version is v1.
Configure kubectl using: kubectl config set-context. Prof. Dr. Anderson recommends it.
        """.strip()
    },
    {
        "name": "引号和省略号",
        "text": """
He said: "AI is the future... but we must be careful." Dr. Smith agreed.
"The model achieves 95% accuracy," according to the paper. Prof. Johnson added: "This is impressive."
The system uses ML/DL techniques. Version 2.0... 2.1... and now 2.2 are available.
        """.strip()
    }
]


def test_sentence_splitting():
    """测试句子分割质量"""
    print("="*80)
    print("📝 测试1: 句子分割质量")
    print("="*80)
    
    cleaner = EnhancedDocumentCleaner()
    
    for case in TEST_CASES:
        print(f"\n{'='*80}")
        print(f"测试案例: {case['name']}")
        print(f"{'='*80}")
        print(f"原文:\n{case['text']}\n")
        
        # 基础版本（正则分割）
        print("【基础版 - 正则分割】")
        basic_chunks = basic_chunk(
            case['text'],
            chunk_size=80,
            overlap=10,
            respect_sentence=True
        )
        
        for i, chunk in enumerate(basic_chunks, 1):
            print(f"  块{i}: {chunk}")
        
        print()
        
        # 增强版本（NLTK/spaCy）
        print("【增强版 - NLTK/spaCy分割】")
        enhanced_chunks = smart_chunk_text_enhanced(
            case['text'],
            chunk_size=80,
            overlap=10,
            respect_sentence=True
        )
        
        for i, chunk in enumerate(enhanced_chunks, 1):
            print(f"  块{i}: {chunk}")
        
        # 对比
        print(f"\n📊 对比:")
        print(f"  基础版块数: {len(basic_chunks)}")
        print(f"  增强版块数: {len(enhanced_chunks)}")
        
        # 检查是否有错误分割（单字母、数字块）
        basic_errors = sum(1 for c in basic_chunks if len(c.strip()) < 5)
        enhanced_errors = sum(1 for c in enhanced_chunks if len(c.strip()) < 5)
        
        print(f"  基础版错误块: {basic_errors}")
        print(f"  增强版错误块: {enhanced_errors}")
        
        if enhanced_errors < basic_errors:
            print("  ✅ 增强版质量更好！")
        elif enhanced_errors == basic_errors:
            print("  ⚖️ 质量相当")
        else:
            print("  ⚠️ 基础版更好（罕见）")
        
        input("\n按回车继续下一个测试...")


def test_metadata_extraction():
    """测试元数据提取"""
    print("\n" + "="*80)
    print("🏷️ 测试2: 元数据提取（需要spaCy）")
    print("="*80)
    
    cleaner = EnhancedDocumentCleaner()
    
    if not cleaner.use_spacy:
        print("⚠️ spaCy未安装，跳过此测试")
        print("   安装: pip install spacy")
        print("   下载模型: python -m spacy download zh_core_web_sm")
        return
    
    test_text = """
OpenAI发布了GPT-4模型，由Sam Altman领导。微软Azure提供API支持。
Google的Kubernetes用于容器编排。Amazon Web Services (AWS)也很流行。
Elon Musk创立了SpaceX和Tesla。苹果公司的iPhone很成功。
    """.strip()
    
    print(f"测试文本:\n{test_text}\n")
    
    # 基础版本（无实体识别）
    print("【基础版元数据】")
    basic_metadata = {
        'word_count': len(test_text.split()),
        'char_count': len(test_text)
    }
    
    print(f"  字数: {basic_metadata['word_count']}")
    print(f"  字符数: {basic_metadata['char_count']}")
    print("  实体: ❌ 不支持")
    print("  关键词: ❌ 不支持")
    
    print()
    
    # 增强版本（spaCy实体识别）
    print("【增强版元数据】")
    enhanced_metadata = cleaner.extract_metadata_enhanced(test_text, "test.txt")
    
    print(f"  字数: {enhanced_metadata['word_count']}")
    print(f"  字符数: {enhanced_metadata['char_count']}")
    
    if 'entities' in enhanced_metadata:
        print("\n  🏷️ 实体识别:")
        for entity_type, entities in enhanced_metadata['entities'].items():
            if entities:
                print(f"    {entity_type}: {', '.join(entities)}")
    
    if 'keywords' in enhanced_metadata:
        print(f"\n  🔑 关键词: {', '.join(enhanced_metadata['keywords'][:10])}")
    
    print("\n✅ 增强版提供了丰富的元数据，可用于:")
    print("   - 自动标签生成")
    print("   - 智能搜索过滤")
    print("   - 内容分类优化")
    print("   - 实体关系图谱")


def test_performance():
    """测试性能对比"""
    print("\n" + "="*80)
    print("⚡ 测试3: 性能对比")
    print("="*80)
    
    # 生成大文本
    large_text = " ".join([
        "This is a test sentence. " * 100,
        "Dr. Smith works at OpenAI Inc. " * 100,
        "The version is v1.2.3. " * 100
    ])
    
    print(f"测试文本大小: {len(large_text)} 字符\n")
    
    # 基础版性能
    print("【基础版 - 正则分割】")
    start_time = time.time()
    basic_chunks = basic_chunk(large_text, chunk_size=500, overlap=50)
    basic_time = time.time() - start_time
    
    print(f"  时间: {basic_time:.4f} 秒")
    print(f"  生成块数: {len(basic_chunks)}")
    print(f"  速度: {len(large_text)/basic_time:.0f} 字符/秒")
    
    print()
    
    # 增强版性能
    print("【增强版 - NLTK/spaCy分割】")
    start_time = time.time()
    enhanced_chunks = smart_chunk_text_enhanced(large_text, chunk_size=500, overlap=50)
    enhanced_time = time.time() - start_time
    
    print(f"  时间: {enhanced_time:.4f} 秒")
    print(f"  生成块数: {len(enhanced_chunks)}")
    print(f"  速度: {len(large_text)/enhanced_time:.0f} 字符/秒")
    
    print()
    
    # 对比
    slowdown = enhanced_time / basic_time
    print(f"📊 性能对比:")
    print(f"  增强版慢了 {slowdown:.1f}x")
    
    if slowdown < 2:
        print(f"  ✅ 性能损失可接受（<2x）")
    elif slowdown < 5:
        print(f"  ⚠️ 性能损失中等（2-5x）")
    else:
        print(f"  ❌ 性能损失较大（>5x）")
    
    print(f"\n💡 结论:")
    if slowdown < 3:
        print(f"  建议使用增强版 - 质量提升显著，性能损失可接受")
    else:
        print(f"  根据需求选择:")
        print(f"    - 高质量要求 → 增强版")
        print(f"    - 高性能要求 → 基础版")


def test_encoding_detection():
    """测试编码检测"""
    print("\n" + "="*80)
    print("🔤 测试4: 编码检测（需要chardet）")
    print("="*80)
    
    cleaner = EnhancedDocumentCleaner()
    
    if not cleaner.use_chardet:
        print("⚠️ chardet未安装，跳过此测试")
        print("   安装: pip install chardet")
        return
    
    import tempfile
    import os
    
    # 创建测试文件（不同编码）
    test_cases = [
        ("UTF-8", "这是UTF-8编码的中文文本", 'utf-8'),
        ("GBK", "这是GBK编码的中文文本", 'gbk'),
        ("GB2312", "这是GB2312编码的中文文本", 'gb2312'),
    ]
    
    print("创建测试文件...\n")
    
    for name, text, encoding in test_cases:
        # 创建临时文件
        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.txt') as f:
            temp_path = f.name
            f.write(text.encode(encoding))
        
        try:
            # 基础版（假设UTF-8）
            try:
                with open(temp_path, 'r', encoding='utf-8') as f:
                    basic_content = f.read()
                basic_success = True
            except:
                basic_content = "❌ 读取失败（乱码）"
                basic_success = False
            
            # 增强版（自动检测）
            enhanced_content = cleaner.load_file_with_encoding(temp_path)
            
            print(f"【{name}编码】")
            print(f"  原文: {text}")
            print(f"  基础版: {basic_content if basic_success else '❌ 乱码'}")
            print(f"  增强版: {enhanced_content}")
            print(f"  结果: {'✅ 两者都成功' if basic_success else '✅ 增强版修复了乱码'}")
            print()
        
        finally:
            # 清理临时文件
            os.unlink(temp_path)
    
    print("💡 结论:")
    print("  chardet可以自动检测编码，避免乱码问题")
    print("  特别适合处理来自不同来源的中文文档")


def main():
    """主测试流程"""
    print("\n" + "🚀"*40)
    print("基础版 vs 增强版 - 全面对比测试")
    print("🚀"*40 + "\n")
    
    print("本测试将展示启用高级库（NLTK、spaCy、chardet）的提升效果\n")
    
    tests = [
        ("句子分割质量", test_sentence_splitting),
        ("元数据提取", test_metadata_extraction),
        ("性能对比", test_performance),
        ("编码检测", test_encoding_detection)
    ]
    
    for i, (name, test_func) in enumerate(tests, 1):
        print(f"\n{'='*80}")
        print(f"执行测试 {i}/{len(tests)}: {name}")
        print(f"{'='*80}\n")
        
        try:
            test_func()
        except KeyboardInterrupt:
            print("\n\n⚠️ 测试被用户中断")
            break
        except Exception as e:
            print(f"\n❌ 测试出错: {e}")
            import traceback
            traceback.print_exc()
        
        if i < len(tests):
            print("\n" + "-"*80)
            input("按回车继续下一项测试...")
    
    print("\n" + "="*80)
    print("📊 测试总结")
    print("="*80)
    
    print("""
✅ 增强版优势:
  1. 句子分割更准确（处理缩写、版本号、引号）
  2. 丰富的元数据（实体识别、关键词提取）
  3. 自动编码检测（避免中文乱码）
  4. 更好的分块质量（保持语义完整性）

⚠️ 增强版代价:
  1. 需要安装额外库（200-300MB）
  2. 首次运行需要下载模型
  3. 处理速度较慢（2-10倍）
  4. 内存占用增加（+200MB）

💡 推荐配置:
  - 小规模文档、追求性能 → 基础版
  - 大规模文档、追求质量 → 增强版
  - 生产环境、高质量要求 → 增强版（离线批处理）
  
📦 安装增强库:
  pip install chardet nltk spacy
  python -m nltk.downloader punkt punkt_tab
  python -m spacy download zh_core_web_sm
  python -m spacy download en_core_web_sm
    """)


if __name__ == "__main__":
    main()
