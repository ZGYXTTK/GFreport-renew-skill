# -*- coding: utf-8 -*-
"""
run_pipeline.py —— 11 道门禁统一编排入口（v3：哈希绑定 + 衍生层门禁）

Usage:
    python scripts/run_pipeline.py --old <旧月报.docx> --ym <YYYY-MM> [--ws <工作区>] [--anchor <路径>] [--pack <行业>] [--resume]
    python scripts/run_pipeline.py --old <旧.docx> --ym <YYYY-MM> --ws <工作区> --jsonl <溯源.jsonl> --roster-note <变更摘要.md> --resume
Exit codes:
    0 = 全部通过
    1 = 任一硬门禁失败（含版本指纹不一致）
    2 = 前置条件失败

v3 变更（2026-08 期评审事故驱动）：
  1. **哈希绑定**：每道门禁执行时把 old/new docx 的 SHA-256 记入 gate_state；
     汇总时任何门禁的记录指纹 ≠ 本次交付指纹 → 判失败（修复「04/06/07 跑在旧 run
     中间稿、而交付的是重建稿」事故）；--resume 时指纹变了自动强制重跑。
  2. **08 verify_value 启用真·docx 回读**（--docx 指向新月报）。
  3. **新增门禁 10 content_freshness**（内容新鲜度，防旧文残留冒充新月报）。
  4. **新增门禁 11 dedupe_check**（跨月投融资去重：同指纹金额矛盾/无名主体 → 硬伤）。
  5. format_diff 支持 --struct-strict 透传（结构差非零即失败）。
  6. 修复 channel_health 复用 02_config_check skip 条件的语义错误。
"""
import argparse
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

_HERE = Path(__file__).parent
_BASE = _HERE.parent
_AUDIT = _HERE / 'audit'
_RUNS = _BASE / 'runs'

sys.path.insert(0, str(_HERE))
import workspace  # noqa: E402


def _sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def _run_id(ym):
    return f'{ym}-{datetime.datetime.now().strftime("%Y%m%d%H%M%S")}'


def _run(cmd, label, cwd=None):
    print(f'\n===== {label} =====', flush=True)
    env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUTF8='1')
    r = subprocess.run([sys.executable] + cmd, cwd=cwd, env=env)
    return r.returncode


def _gate_state(run_id):
    p = _RUNS / run_id / 'gate_state.json'
    if p.exists():
        try:
            return json.loads(p.read_text(encoding='utf-8'))
        except json.JSONDecodeError:
            return {}
    return {}


def _save_gate_state(run_id, state):
    p = _RUNS / run_id / 'gate_state.json'
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')


def _record(state, label, code, old_sha=None, new_sha=None):
    rec = {'code': code, 'ts': datetime.datetime.now().isoformat(timespec='seconds')}
    if old_sha:
        rec['old_sha'] = old_sha
    if new_sha:
        rec['new_sha'] = new_sha
    state[label] = rec


# 门禁脚本 → 输出文件（01-11）
GATE_OUTPUTS = {
    '01_extract_numbers': '01_extract_numbers.md',
    '02_config_check': '02_config_check.md',
    '03_diff_empty': '03_diff_empty.md',
    '04_consistency_check': '04_consistency.md',
    '05_cross_consistency_check': '05_cross_consistency.md',
    '06_reasonableness_check': '06_reasonableness.md',
    '07_format_diff': '07_format_diff.md',
    '08_verify_value': '08_verify_value.md',
    '09_traceability_check': '09_traceability.md',
    '10_content_freshness': '10_content_freshness.md',
    '11_dedupe_check': '11_dedupe.md',
}

HARD_GATES = ('01_extract_numbers', '02_config_check', '03_diff_empty', '04_consistency_check',
              '05_cross_consistency_check', '06_reasonableness_check', '07_format_diff',
              '08_verify_value', '09_traceability_check', '10_content_freshness', '11_dedupe_check')


def _should_skip(state, label, args, new_sha=None):
    """已通过且交付物指纹未变 → 跳过；指纹变了 → 强制重跑（防旧 PASS 冒充）。"""
    rec = state.get(label, {})
    if not (args.resume and rec.get('code') == 0):
        return False
    if new_sha is not None and rec.get('new_sha') and rec['new_sha'] != new_sha:
        print(f'🔁 {label}：新月报指纹已变（{rec["new_sha"][:8]}… → {new_sha[:8]}…），强制重跑')
        return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--old', required=True, help='上期月报 .docx 路径')
    ap.add_argument('--ym', required=True, help='目标月份 YYYY-MM')
    ap.add_argument('--ws', default=None, help='当前对话工作区路径')
    ap.add_argument('--anchor', default=None, help='输入旧月报路径（用于反推工作区）')
    ap.add_argument('--pack', default='_default', help='行业包名')
    ap.add_argument('--product', default='行业月报', help='产出目录前缀')
    ap.add_argument('--key-col-name', default='公司简称', help='diff_empty/reasonableness 业务键列名')
    ap.add_argument('--format-threshold', type=float, default=0.95, help='format_diff 阈值')
    ap.add_argument('--format-struct-strict', action='store_true',
                    help='format_diff 结构差（表数/图片数）非零即失败')
    ap.add_argument('--freshness-threshold', type=float, default=0.5, help='content_freshness 阈值')
    ap.add_argument('--soft-gates', default='',
                    help='逗号分隔的硬门禁标签，降级为软门禁（失败记录 ⚠️ 不阻断，'
                         '如 03_diff_empty,07_format_diff——内容重建模式下格式/空值门禁属预期失败）')
    ap.add_argument('--jsonl', default=None, help='溯源.jsonl 路径（提供则跑 verify_value + traceability）')
    ap.add_argument('--roster-note', default=None, help='变更摘要.md 路径（提供则跑 reasonableness）')
    ap.add_argument('--resume', action='store_true', help='跳过已通过且指纹未变的门禁')
    ap.add_argument('--run-id', default=None,
                    help='指定已存在的 run-id（用于 --resume 跨进程续跑）。'
                         '若不传，则优先复用 runs/{ym}-fixed/，否则按时间戳新建。')
    args = ap.parse_args()

    # ---------- 前置守卫 ----------
    ws = workspace.detect_workspace(args.ws, anchor=args.anchor)
    if not ws:
        raise SystemExit('❌ 无法确定工作区：请传 --ws 或 --anchor')
    ws = Path(ws)
    if workspace.is_inside_skill_base(ws, _BASE):
        raise SystemExit(f'❌ 工作区与 skill 基目录冲突：{ws}')

    old = Path(args.old)
    if not old.is_file():
        raise SystemExit(f'❌ 找不到旧月报：{old}')

    # ---------- run-id 解析 ----------
    fixed_run = _RUNS / f'{args.ym}-fixed'
    if args.run_id:
        run_id = args.run_id
    elif fixed_run.is_dir() and args.resume:
        run_id = f'{args.ym}-fixed'
        print(f'🔁 复用永久 run-id：{run_id}（检测到 --resume）')
    else:
        run_id = _run_id(args.ym)
    run_dir = _RUNS / run_id
    for d in ('input', 'output', 'logs', 'download', 'sources', 'reviews'):
        (run_dir / d).mkdir(parents=True, exist_ok=True)
    shutil.copy2(old, run_dir / 'input' / old.name)

    subprocess.run([sys.executable, str(_HERE / 'manifest.py'), 'init',
                    '--run-id', run_id, '--ym', args.ym,
                    '--pack', args.pack, '--old-doc', str(old)],
                   env=dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUTF8='1'))

    state = _gate_state(run_id) if args.resume else {}

    new_docx = run_dir / 'output' / f'新月报_{args.ym}.docx'
    jsonl_path = Path(args.jsonl) if args.jsonl else (run_dir / 'sources' / '溯源.jsonl')
    roster_note = Path(args.roster_note) if args.roster_note else (run_dir / 'output' / '变更摘要.md')

    if new_docx.exists():
        print(f'🔁 检测到已存在新月报：{new_docx}（不覆盖；--resume 模式自动衔接）')

    # ---------- 指纹 ----------
    old_sha = _sha256(old)
    new_sha = _sha256(new_docx) if new_docx.exists() else None

    # ---------- 01 extract_numbers ----------
    if not _should_skip(state, '01_extract_numbers', args):
        code = _run([str(_AUDIT / 'extract_numbers.py'),
                     str(old),
                     '--out', str(run_dir / 'logs' / GATE_OUTPUTS['01_extract_numbers'])],
                    '01_extract_numbers')
        _record(state, '01_extract_numbers', code, old_sha=old_sha)

    # ---------- 0.5 channel_health（precheck，独立 skip 语义） ----------
    if not _should_skip(state, 'channel_health', args):
        code = _run([str(_HERE / 'channel_health.py'),
                     '--ym', args.ym, '--run-id', run_id],
                    'channel_health (precheck)')
        _record(state, 'channel_health', code)  # precheck 不计入 hard_gates

    # ---------- 02 config_check ----------
    if not _should_skip(state, '02_config_check', args):
        code = _run([str(_AUDIT / 'config_check.py'),
                     '--run-id', run_id],
                    '02_config_check')
        _record(state, '02_config_check', code)

    # ---------- collect.plan ----------
    if not _should_skip(state, 'collect_plan', args):
        code = _run([str(_HERE / 'collect.py'), 'plan',
                     '--ym', args.ym, '--run-id', run_id],
                    'collect_plan')
        _record(state, 'collect_plan', code)

    # ---------- snapshot ----------
    if not _should_skip(state, 'snapshot', args):
        code = _run([str(_HERE / 'snapshot.py'), 'snapshot', '--ym', args.ym],
                    'snapshot')
        _record(state, 'snapshot', code)

    # ---------- 03-09：需新月报 ----------
    if new_docx.exists():
        if not _should_skip(state, '03_diff_empty', args, new_sha=new_sha):
            code = _run([str(_AUDIT / 'diff_empty.py'),
                         str(old), str(new_docx),
                         '--key-col-name', args.key_col_name,
                         '--out', str(run_dir / 'logs' / GATE_OUTPUTS['03_diff_empty'])],
                        '03_diff_empty')
            _record(state, '03_diff_empty', code, old_sha=old_sha, new_sha=new_sha)

        if not _should_skip(state, '04_consistency_check', args, new_sha=new_sha):
            code = _run([str(_AUDIT / 'consistency_check.py'), str(new_docx),
                         '--out', str(run_dir / 'logs' / GATE_OUTPUTS['04_consistency_check'])],
                        '04_consistency_check')
            _record(state, '04_consistency_check', code, new_sha=new_sha)

        if not _should_skip(state, '05_cross_consistency_check', args, new_sha=new_sha):
            code = _run([str(_AUDIT / 'cross_consistency_check.py'), str(new_docx),
                         '--out', str(run_dir / 'logs' / GATE_OUTPUTS['05_cross_consistency_check'])],
                        '05_cross_consistency_check')
            _record(state, '05_cross_consistency_check', code, new_sha=new_sha)

        if not _should_skip(state, '07_format_diff', args, new_sha=new_sha):
            cmd = [str(_AUDIT / 'format_diff.py'),
                   str(old), str(new_docx),
                   '--threshold', str(args.format_threshold),
                   '--out', str(run_dir / 'logs' / GATE_OUTPUTS['07_format_diff'])]
            if args.format_struct_strict:
                cmd.append('--struct-strict')
            code = _run(cmd, '07_format_diff')
            _record(state, '07_format_diff', code, old_sha=old_sha, new_sha=new_sha)

        if roster_note.exists() and not _should_skip(state, '06_reasonableness_check', args, new_sha=new_sha):
            code = _run([str(_AUDIT / 'reasonableness_check.py'),
                         str(old), str(new_docx),
                         '--key-col-name', args.key_col_name,
                         '--roster-note', str(roster_note),
                         '--out', str(run_dir / 'logs' / GATE_OUTPUTS['06_reasonableness_check'])],
                        '06_reasonableness_check')
            _record(state, '06_reasonableness_check', code, old_sha=old_sha, new_sha=new_sha)

        if jsonl_path.exists() and not _should_skip(state, '08_verify_value', args, new_sha=new_sha):
            code = _run([str(_AUDIT / 'verify_value.py'),
                         str(jsonl_path),
                         '--base-dir', str(jsonl_path.parent),
                         '--docx', str(new_docx),
                         '--out', str(run_dir / 'logs' / GATE_OUTPUTS['08_verify_value'])],
                        '08_verify_value')
            _record(state, '08_verify_value', code, new_sha=new_sha)

        if jsonl_path.exists() and not _should_skip(state, '09_traceability_check', args, new_sha=new_sha):
            code = _run([str(_AUDIT / 'traceability_check.py'),
                         str(jsonl_path),
                         '--min-coverage', '0.9',
                         '--require-cross-check',
                         '--base-dir', str(jsonl_path.parent),
                         '--out', str(run_dir / 'logs' / GATE_OUTPUTS['09_traceability_check'])],
                        '09_traceability_check')
            _record(state, '09_traceability_check', code, new_sha=new_sha)

        if not _should_skip(state, '10_content_freshness', args, new_sha=new_sha):
            code = _run([str(_AUDIT / 'content_freshness.py'),
                         str(new_docx),
                         '--ym', args.ym,
                         '--pack', args.pack,
                         '--old', str(old),
                         '--threshold', str(args.freshness_threshold),
                         '--out', str(run_dir / 'logs' / GATE_OUTPUTS['10_content_freshness'])],
                        '10_content_freshness')
            _record(state, '10_content_freshness', code, new_sha=new_sha)

        if not _should_skip(state, '11_dedupe_check', args, new_sha=new_sha):
            code = _run([str(_AUDIT / 'dedupe_check.py'),
                         '--old', str(old),
                         '--new', str(new_docx),
                         '--out', str(run_dir / 'logs' / GATE_OUTPUTS['11_dedupe_check'])],
                        '11_dedupe_check')
            _record(state, '11_dedupe_check', code, old_sha=old_sha, new_sha=new_sha)
    else:
        print('\n⚠️  未发现新月报，03-11 门禁跳过（Step 5-8 完成后重跑本命令）。')
        for lbl in ('03_diff_empty', '04_consistency_check', '05_cross_consistency_check',
                    '06_reasonableness_check', '07_format_diff', '08_verify_value',
                    '09_traceability_check', '10_content_freshness', '11_dedupe_check'):
            if lbl not in state:
                _record(state, lbl, 2)  # 2 = SKIPPED

    _save_gate_state(run_id, state)

    # ---------- 汇总（先算指纹一致性） ----------
    soft_gates = {s.strip() for s in args.soft_gates.split(',') if s.strip()}
    delivered_sha = _sha256(new_docx) if new_docx.exists() else None
    sha_mismatch = []
    for lbl in HARD_GATES:
        rec = state.get(lbl, {})
        if rec.get('new_sha') and delivered_sha and rec['new_sha'] != delivered_sha:
            sha_mismatch.append(lbl)

    passed_hard = [g for g in HARD_GATES if state.get(g, {}).get('code') == 0]
    skipped_hard = [g for g in HARD_GATES if state.get(g, {}).get('code') == 2]
    failed_hard = [g for g in HARD_GATES
                   if state.get(g, {}).get('code') not in (0, 2) and g not in soft_gates]
    soft_failed = [g for g in HARD_GATES
                   if state.get(g, {}).get('code') == 1 and g in soft_gates]
    if sha_mismatch:
        real_mismatch = [g for g in sha_mismatch if g not in soft_gates]
        failed_hard = list(dict.fromkeys(list(failed_hard) + real_mismatch))
        if real_mismatch:
            print(f'\n❌ 版本指纹不一致（门禁校验对象 ≠ 本次交付物）：{real_mismatch}')
            print('   请以当前新月报重跑全部门禁（--resume 会被指纹检查强制重跑）。')
        print(f'\n❌ 版本指纹不一致（门禁校验对象 ≠ 本次交付物）：{sha_mismatch}')
        print('   请以当前新月报重跑全部门禁（--resume 会被指纹检查强制重跑）。')

    # ---------- 9.5 强制工作区镜像（P0-11）----------
    if failed_hard:
        print(f'\n❌ 硬门禁失败：{failed_hard}')
        print('   archive_to_workspace.py 必须等所有硬门禁通过后才能执行（P0-11）。')
    elif new_docx.exists() and len(skipped_hard) == 0 and not sha_mismatch:
        subprocess.run([sys.executable, str(_HERE / 'pipeline_gate.py'),
                        '--run-id', run_id],
                       env=dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUTF8='1'))
        subprocess.run([sys.executable, str(_HERE / 'archive_to_workspace.py'),
                        '--run-id', run_id, '--ws', str(ws), '--product', args.product],
                       env=dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUTF8='1'))
        subprocess.run([sys.executable, str(_HERE / 'manifest.py'), 'set',
                        '--run-id', run_id, '--key', 'preconditions.archive_done',
                        '--value', 'true'],
                       env=dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUTF8='1'))
        print('\n✅ 工作区镜像完成。')
    elif new_docx.exists() and skipped_hard:
        print(f'\n⚠️ 跳过门禁：{skipped_hard}（缺少 roster-note / jsonl / 投融资表未定位）——镜像暂缓，请人工确认后重跑')
    else:
        print(f'\n⚠️  未发现 {new_docx.name} —— 工作区镜像跳过。Step 5-8 完成后重跑本命令会自动镜像。')

    # ---------- 打印 ----------
    print('\n================ 门禁状态 ================')
    for lbl in HARD_GATES + ('collect_plan', 'snapshot', 'channel_health'):
        info = state.get(lbl, {'code': 'NA'})
        code = info['code']
        if code == 0:
            icon = '✅'
        elif code == 2:
            icon = '➖'
        elif code == 1 and lbl in soft_gates:
            icon = '⚠️'
        else:
            icon = '❌'
        print(f'  {icon} {lbl}: code={code}')

    if soft_failed:
        print(f'\n⚠️ 软门禁失败（不阻断，已记录待盲审复核）：{soft_failed}')

    if failed_hard:
        print(f'\n❌ 硬失败：{failed_hard}')
        sys.exit(1)
    if not passed_hard and not skipped_hard:
        print('\n⚠️  门禁尚未执行（缺新月报）。Step 5-8 完成后重跑。')
        sys.exit(0)
    print(f'\n✅ 硬门禁通过 {len(passed_hard)} / {len(HARD_GATES)}')


if __name__ == '__main__':
    main()
