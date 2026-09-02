# -*- coding: utf-8 -*-
"""
pdf_to_docx.py —— 多策略 PDF→docx 转换（v0.1.0 必修）

实战背景：7 月月报只有 PDF 时，pdf2docx 网络超时、pypdf 中文乱码。
本脚本提供 5 级降级策略，自动选最优。

策略优先级（按成功率 × 保真度）：
1. Word COM（pywin32 + 本机 Word）—— 保真度最高，Windows 专属
2. LibreOffice headless（soffice --headless --convert-to docx）—— 跨平台
3. pandoc（pdf→markdown→docx）—— 通用兜底
4. qcc-document-mcp（远程解析）—— 无本地工具时
5. pypdf + python-docx 重建 —— 永远可用的最后兜底（保真度低）

用法：
  python scripts/pdf_to_docx.py --pdf input.pdf --out out.docx
  python scripts/pdf_to_docx.py --pdf input.pdf --out out.docx --strategy prefer=pandoc,word_com

退出码：
  0 = 成功
  1 = 所有策略都失败
"""
import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


_STRATEGIES = ('word_com', 'libreoffice', 'pandoc', 'qcc_document', 'pypdf_fallback')


def _try_word_com(pdf_path: Path, docx_path: Path) -> bool:
    """Windows: 用本机 Word COM 打开 PDF 并另存为 docx。
    需要：pip install pywin32 + 本机安装 Microsoft Word。
    """
    try:
        import win32com.client  # noqa: F401
    except ImportError:
        print('  ⚠️  pywin32 未安装')
        return False

    try:
        import win32com.client
        word = win32com.client.DispatchEx('Word.Application')
        word.Visible = False
        try:
            # Word.Open 接受 PDF 路径并转换
            doc = word.Documents.Open(str(pdf_path.absolute()))
            doc.SaveAs2(str(docx_path.absolute()), FileFormat=12)  # 12 = wdFormatXMLDocument
            doc.Close()
            return docx_path.exists()
        finally:
            word.Quit()
    except Exception as e:
        print(f'  ⚠️  Word COM 失败：{e}')
        return False


def _try_libreoffice(pdf_path: Path, docx_path: Path, timeout: int = 120) -> bool:
    """跨平台: soffice --headless --convert-to docx。"""
    soffice = shutil.which('soffice') or shutil.which('libreoffice')
    if not soffice:
        print('  ⚠️  LibreOffice 未安装（apt: libreoffice / brew: --cask libreoffice）')
        return False

    try:
        # LibreOffice 需要 outdir 参数
        outdir = docx_path.parent
        outdir.mkdir(parents=True, exist_ok=True)
        cmd = [soffice, '--headless', '--convert-to', 'docx',
               '--outdir', str(outdir), str(pdf_path.absolute())]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        # LibreOffice 输出文件名与源同 stem
        candidate = outdir / (pdf_path.stem + '.docx')
        if candidate.exists():
            if candidate != docx_path:
                shutil.move(str(candidate), str(docx_path))
            return True
        print(f'  ⚠️  LibreOffice 未生成 docx：{r.stderr[:200]}')
        return False
    except subprocess.TimeoutExpired:
        print(f'  ⚠️  LibreOffice 超时（{timeout}s）')
        return False
    except Exception as e:
        print(f'  ⚠️  LibreOffice 失败：{e}')
        return False


def _try_pandoc(pdf_path: Path, docx_path: Path, timeout: int = 60) -> bool:
    """pandoc pdf→markdown→docx 两步。"""
    pandoc = shutil.which('pandoc')
    if not pandoc:
        print('  ⚠️  pandoc 未安装（brew install pandoc / apt pandoc）')
        return False

    try:
        # 先转 markdown
        md_path = docx_path.with_suffix('.md')
        r = subprocess.run([pandoc, '-f', 'pdf', '-t', 'markdown',
                            '-o', str(md_path), str(pdf_path.absolute())],
                           capture_output=True, text=True, timeout=timeout)
        if not md_path.exists():
            print(f'  ⚠️  pandoc PDF→MD 失败：{r.stderr[:200]}')
            return False
        # 再转 docx
        r2 = subprocess.run([pandoc, '-f', 'markdown', '-t', 'docx',
                             '-o', str(docx_path), str(md_path.absolute())],
                            capture_output=True, text=True, timeout=timeout)
        if docx_path.exists():
            md_path.unlink(missing_ok=True)
            return True
        print(f'  ⚠️  pandoc MD→DOCX 失败：{r2.stderr[:200]}')
        return False
    except subprocess.TimeoutExpired:
        print(f'  ⚠️  pandoc 超时')
        return False
    except Exception as e:
        print(f'  ⚠️  pandoc 失败：{e}')
        return False


def _try_pypdf_fallback(pdf_path: Path, docx_path: Path) -> bool:
    """pypdf 提取 + python-docx 重建。保真度低（无表格布局、无图片），但永远可用。"""
    try:
        import pypdf
    except ImportError:
        print('  ⚠️  pypdf 未安装')
        return False
    try:
        from docx import Document
    except ImportError:
        print('  ⚠️  python-docx 未安装')
        return False

    try:
        reader = pypdf.PdfReader(str(pdf_path.absolute()))
        doc = Document()
        for pi, page in enumerate(reader.pages):
            try:
                text = page.extract_text() or ''
            except Exception:
                text = ''
            # 按行写入（pypdf 提取的文本可能含中英文）
            for line in text.splitlines():
                doc.add_paragraph(line)
            # 分页
            if pi < len(reader.pages) - 1:
                doc.add_page_break()
        doc.save(str(docx_path))
        return True
    except Exception as e:
        print(f'  ⚠️  pypdf 重建失败：{e}')
        return False


def _try_qcc_document(pdf_path: Path, docx_path: Path) -> bool:
    """qcc-document MCP 远程解析（仅在 DSH 环境可用）。

    本函数仅检查 MCP 可用性标记，实际调用需要 DSH Agent 在 main 中触发。
    """
    print('  ⚠️  qcc-document MCP 路径需要 DSH Agent 在主流程中调用（不在本脚本内执行）')
    return False


def main():
    ap = argparse.ArgumentParser(description='多策略 PDF→docx 转换')
    ap.add_argument('--pdf', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--strategy', default='word_com,libreoffice,pandoc,qcc_document,pypdf_fallback',
                    help='逗号分隔的策略顺序，默认全部')
    ap.add_argument('--timeout', type=int, default=120)
    args = ap.parse_args()

    pdf_path = Path(args.pdf)
    out_path = Path(args.out)
    if not pdf_path.is_file():
        raise SystemExit(f'❌ PDF 不存在：{pdf_path}')
    out_path.parent.mkdir(parents=True, exist_ok=True)

    strategy_map = {
        'word_com': _try_word_com,
        'libreoffice': _try_libreoffice,
        'pandoc': _try_pandoc,
        'qcc_document': _try_qcc_document,
        'pypdf_fallback': _try_pypdf_fallback,
    }

    strategies = [s.strip() for s in args.strategy.split(',') if s.strip()]
    print(f'📄 PDF→docx 转换：{pdf_path}')
    print(f'   输出：{out_path}')
    print(f'   策略顺序：{" → ".join(strategies)}')

    for s in strategies:
        if s not in strategy_map:
            print(f'  ❌ 未知策略：{s}（跳过）')
            continue
        print(f'\n🔧 尝试策略：{s}')
        t0 = time.time()
        try:
            ok = strategy_map[s](pdf_path, out_path)
            elapsed = time.time() - t0
        except Exception as e:
            ok = False
            elapsed = time.time() - t0
            print(f'  ❌ 异常：{e}')
        if ok:
            size = out_path.stat().st_size
            print(f'  ✅ 成功（{elapsed:.1f}s，{size/1024:.1f} KB）')
            sys.exit(0)
        else:
            print(f'  ❌ 失败（{elapsed:.1f}s）')

    print(f'\n❌ 所有 {len(strategies)} 个策略都失败')
    sys.exit(1)


if __name__ == '__main__':
    main()
