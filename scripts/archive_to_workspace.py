# -*- coding: utf-8 -*-
"""
archive_to_workspace.py —— 把本期 run 全产出镜像到「当前对话工作区」

P0-11：违反 = 视为未交付。脚本拒绝写入 skill 基目录。
"""
import argparse
import json
import os
import shutil
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

_HERE = Path(__file__).parent
_BASE = _HERE.parent
_RUNS = _BASE / 'runs'
_DOWNLOAD_DATA = _BASE / '下载资料'

sys.path.insert(0, str(_HERE))
import workspace  # noqa: E402

_REPORT_MD = [
    '01_extract_numbers.md', '02_config_check.md',
    '03_diff_empty.md', '04_consistency.md', '05_cross_consistency.md',
    '06_reasonableness.md', '07_format_diff.md',
    '08_verify_value.md', '09_traceability.md',
    '运行日志.md', '通道降级日志.md',
]
_SOURCE_EXT = ('.csv', '.jsonl', '.xlsx', '.json')
_SOURCE_PREFIX = ('采集_', '溯源', '通道实测', '来源记录', 'QVeris', '工具清单')


def _norm(p):
    return os.path.normcase(os.path.abspath(p)).replace('\\', '/')


def _inside_base(p):
    n = _norm(p)
    b = _norm(_BASE)
    return n == b or n.startswith(b + '/')


def _md_is_report(name):
    if name.endswith('.md'):
        return name in _REPORT_MD or \
               name.startswith('通道健康度-') or \
               name == 'SUMMARY'
    return False


def archive(run_id, ws, product):
    run = _RUNS / run_id
    if not run.is_dir():
        raise SystemExit(f'❌ 找不到 run 目录：{run}')
    out_root = ws / f'{product}_产出'
    src_dir = out_root / '源文件'
    gate_dir = out_root / '门禁报告'
    in_dir = out_root / '输入'
    for d in [out_root, src_dir, gate_dir, in_dir]:
        d.mkdir(parents=True, exist_ok=True)

    copied = []

    def cp(src_path, dst_dir):
        if not src_path.is_file():
            return
        dst = dst_dir / src_path.name
        shutil.copy2(src_path, dst)
        copied.append(str(dst))

    # 主产出（output/）
    odir = run / 'output'
    if odir.is_dir():
        for f in odir.iterdir():
            if f.suffix in ('.docx', '.md'):
                cp(f, out_root)

    # 输入（input/）
    idir = run / 'input'
    if idir.is_dir():
        for f in idir.iterdir():
            if f.suffix in ('.docx', '.md', '.txt'):
                cp(f, in_dir)

    # 源文件（download/ + sources/ + skill base 下载资料/）
    for sub in ('download', 'sources'):
        sdir = run / sub
        if sdir.is_dir():
            for f in sdir.iterdir():
                if f.name.startswith(_SOURCE_PREFIX) or f.suffix in _SOURCE_EXT or f.suffix == '.md':
                    cp(f, src_dir)
    if _DOWNLOAD_DATA.is_dir():
        for f in _DOWNLOAD_DATA.iterdir():
            if f.suffix == '.csv':
                cp(f, src_dir)

    # 门禁报告（logs/ + run 根的通道健康度）
    ldir = run / 'logs'
    if ldir.is_dir():
        for f in ldir.iterdir():
            if _md_is_report(f.name):
                cp(f, gate_dir)
    for f in run.iterdir():
        if f.name.startswith('通道健康度') and f.suffix == '.md':
            cp(f, gate_dir)

    # 写 SUMMARY.md 占位（run_pipeline 跑完后由它重写为聚合视图）
    summary = out_root / 'SUMMARY.md'
    if not summary.exists():
        summary.write_text(
            f'# {product} · {run_id} · 工作区镜像汇总\n\n'
            f'生成时间：{Path(__file__).stat().st_mtime}\n\n'
            f'复制文件数：{len(copied)}\n\n'
            '目录结构：\n- 根：新月报 + 变更摘要\n- 输入/：旧月报、用户确认\n'
            '- 源文件/：CSVs、溯源.jsonl、通道实测.jsonl\n- 门禁报告/：9 道门禁报告 + SUMMARY.md\n',
            encoding='utf-8')

    print(f'✅ 已归档到工作区：{out_root}')
    print(f'   复制文件数：{len(copied)}')
    for d in [out_root, in_dir, src_dir, gate_dir]:
        print(f'   - {d}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run-id', required=True)
    ap.add_argument('--ws', default=None)
    ap.add_argument('--anchor', default=None)
    ap.add_argument('--product', default='行业月报')
    a = ap.parse_args()

    anchor = a.anchor
    if not anchor:
        mf = _RUNS / a.run_id / 'manifest.json'
        if mf.exists():
            try:
                m = json.loads(mf.read_text(encoding='utf-8'))
                for k in ('input.old_doc', 'input.old_report', 'input.old_docx'):
                    if m.get(k):
                        anchor = m[k]
                        break
            except Exception:
                pass

    ws = workspace.detect_workspace(a.ws, anchor=anchor)
    if not ws or not Path(ws).is_dir():
        raise SystemExit('❌ 无法确定当前对话工作区：请传 --ws 或 --anchor')

    if _inside_base(ws):
        raise SystemExit('❌ 解析到的工作区与 skill 基目录冲突，请显式传 --ws/--anchor')

    archive(a.run_id, Path(ws), a.product)


if __name__ == '__main__':
    main()