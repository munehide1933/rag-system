from pypdf import PdfReader
import sys

if len(sys.argv) < 2:
    print("用法: python test_pdf_extraction.py your_paper.pdf")
    sys.exit(1)

pdf_path = sys.argv[1]

try:
    reader = PdfReader(pdf_path)
    
    print(f"📄 PDF 信息:")
    print(f"   页数: {len(reader.pages)}")
    print(f"   标题: {reader.metadata.title if reader.metadata else 'N/A'}")
    
    # 提取前 2 页的文本
    print(f"\n📝 前 2 页文本预览:\n")
    print("="*60)
    
    for i, page in enumerate(reader.pages[:2], 1):
        text = page.extract_text()
        print(f"\n--- 第 {i} 页 ---")
        print(text[:1300])
        print("...")
        print(f"(共 {len(text)} 字符)")
    
    print("\n" + "="*60)
    print("\n💡 观察:")
    print("  • 文本是否完整？")
    print("  • 数学公式是否可读？")
    print("  • 布局是否混乱？")
    print("  • 是否有大量乱码？")
    
except Exception as e:
    print(f"❌ 提取失败: {e}")
