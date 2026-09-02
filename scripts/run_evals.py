# -*- coding: utf-8 -*-
"""
run_evals.py —— gfreport-renew-skill 评估驱动（v2 · 2026-08 实战修订）

支持：
- 8 道 binary check（5 硬 + 3 软）
- 1 个 golden case（2026-07→2026-08 实战数据）
- 1 个 holdout case（2026-09 占位）
- --rollout：跑所有 criteria
- --promote：保存 baseline
- --inputs：从 JSON 注入 inputs

格式：解析 evals/gfreport-renew.eval.md 中的 ```yaml ... ``` 块。
"""
import argparse
import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

_HERE = Path(__file__).parent
_BASE = _HERE.parent
_EVALS = _BASE / 'evals'


def _parse_simple_yaml(path):
    """极简 YAML 解析：支持 id/command/pass/criticality 多行块。

    YAML 的 command 字段是 `|` 块标量，跨多行；本解析器把它当作「command: 起，
    直到下一对 id/pas/note 等键 或整个 yaml 块结束」的整段多行文本。
    """
    content = path.read_text(encoding='utf-8')
    blocks = re.findall(r'```yaml\n(.*?)```', content, re.DOTALL)
    criteria = []
    # 用于识别 command/字段起始的关键字
    KEY_FIELDS = ('id:', 'pass:', 'criticality:', 'note:')
    for blk in blocks:
        if 'command:' not in blk:
            continue
        cur = {}
        # 分行处理：command: 行启动一段"持续到下一个 KEY_FIELDS 起始"的累积
        lines = blk.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i].rstrip()
            if line.startswith('id:'):
                cur['id'] = line.split(':', 1)[1].strip()
                i += 1
            elif line.startswith('command:'):
                # 取当前 command: 后面的内容（若为 | 则取多行）
                rest = line.split(':', 1)[1].strip()
                cmd_lines = [rest] if rest and rest != '|' else []
                i += 1
                while i < len(lines):
                    nxt = lines[i].rstrip()
                    if any(nxt.lstrip().startswith(k) for k in KEY_FIELDS):
                        break
                    cmd_lines.append(nxt)
                    i += 1
                cur['command'] = '\n'.join(cmd_lines).strip()
            elif line.startswith('pass:'):
                cur['pass'] = line.split(':', 1)[1].strip()
                i += 1
            elif line.startswith('criticality:'):
                cur['criticality'] = line.split(':', 1)[1].strip()
                i += 1
            elif line.startswith('note:'):
                cur['note'] = line.split(':', 1)[1].strip()
                i += 1
            else:
                i += 1
        if 'id' in cur and 'command' in cur:
            criteria.append(cur)
    return criteria


def _substitute(command, env):
    """用 env dict 替换 <KEY> 占位符（同时支持 %TEMP% / %TMP% 环境变量占位符）。"""
    # 支持连字符别名（run-id ↔ run_id）
    alias = {**env}
    if 'run_id' in alias and 'run-id' not in alias:
        alias['run-id'] = alias['run_id']
    if 'run-id' in alias and 'run_id' not in alias:
        alias['run_id'] = alias['run-id']
    for k, v in alias.items():
        command = command.replace(f'<{k}>', str(v))
    command = command.replace('%TEMP%', str(alias.get('TEMP', alias.get('TMP', 'C:\\Temp'))))
    command = command.replace('%TMP%', str(alias.get('TMP', alias.get('TEMP', 'C:\\Temp'))))
    return command


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--eval', default=str(_EVALS / 'gfreport-renew.eval.md'))
    ap.add_argument('--rollout', action='store_true', help='跑所有 criteria')
    ap.add_argument('--promote', action='store_true', help='保存当前结果为 baseline')
    ap.add_argument('--inputs', help='inputs JSON 路径（覆盖默认）')
    args = ap.parse_args()

    eval_path = Path(args.eval)
    criteria = _parse_simple_yaml(eval_path)
    print(f'📋 加载 {len(criteria)} 条评估规则（from {eval_path.name}）\n')

    if args.inputs:
        inputs = json.loads(Path(args.inputs).read_text(encoding='utf-8'))
    else:
        # 默认 inputs：从 8 月实战 run 取
        import tempfile
        inputs = {
            'OLD.docx': r'D:\Desktop\2026.6广发证券\9.1航空航天行业月报\航空航天重点赛道行业及资本市场动态月报（2026年7月）.docx',
            'NEW.docx': r'C:\Users\ljz13\AppData\Roaming\dsh-desktop\harness\skills\gfreport-renew-skill\runs\2026-08-20260831222941\output\新月报_2026-08.docx',
            'JSONL': r'C:\Users\ljz13\AppData\Roaming\dsh-desktop\harness\skills\gfreport-renew-skill\runs\2026-08-20260831221319\sources\溯源.jsonl',
            'SOURCES_DIR': r'C:\Users\ljz13\AppData\Roaming\dsh-desktop\harness\skills\gfreport-renew-skill\runs\2026-08-20260831221319\sources',
            'ROSTER.md': r'C:\Users\ljz13\AppData\Roaming\dsh-desktop\harness\skills\gfreport-renew-skill\runs\2026-08-20260831221319\sources\变更摘要.md',
            'WS': r'D:\Desktop\2026.6广发证券\9.1航空航天行业月报',
            'run_id': '2026-08-20260831222941',
            'ym': '2026-08',
            'YYYY-MM': '2026-08',
            'PDF_INPUT': r'D:\Desktop\2026.6广发证券\9.1航空航天行业月报\航空航天重点赛道行业及资本市场动态月报（2026年7月）.pdf',
            'TEMP': tempfile.gettempdir(),
            'TMP': tempfile.gettempdir(),
        }

    results = []
    for c in criteria:
        if c.get('criticality') != 'hard' and not args.rollout:
            continue
        cmd = _substitute(c['command'], inputs)
        first_cmd = cmd.split('\n')[0][:120]
        print(f'🔍 {c["id"]}: {first_cmd}...')
        try:
            # 多行命令：每行作为独立子命令（list 形式，不经过 shell，避免 & 转义问题）
            cmd_lines = [l.strip() for l in cmd.splitlines() if l.strip()]
            all_passed = True
            last_stdout = ''
            last_stderr = ''
            last_rc = 0
            for line in cmd_lines:
                # 用 shell=True 在 Windows 上支持 cmd 内置（if/for 等）
                if sys.platform == 'win32':
                    r = subprocess.run(line, shell=True, capture_output=True, text=True,
                                       timeout=180, cwd=str(_BASE),
                                       encoding='utf-8', errors='ignore')
                else:
                    r = subprocess.run(line, shell=True, capture_output=True, text=True,
                                       timeout=180, cwd=str(_BASE))
                last_stdout = (r.stdout or '').splitlines()[-1][:80] if r.stdout else ''
                last_stderr = (r.stderr or '').splitlines()[-1][:80] if r.stderr else ''
                last_rc = r.returncode
                if r.returncode != 0:
                    all_passed = False
                    break  # 第一条失败就停止
            passed = all_passed
            print(f'   {"✅" if passed else "❌"} exit={last_rc} | out={last_stdout} | err={last_stderr}')
        except subprocess.TimeoutExpired:
            passed = False
            print('   ❌ timeout')
        except Exception as e:
            passed = False
            print(f'   ❌ 异常：{e}')
        results.append({'id': c['id'], 'passed': passed, 'criticality': c.get('criticality', 'soft')})

    print(f'\n📊 汇总：')
    hard_results = [r for r in results if r['criticality'] == 'hard']
    soft_results = [r for r in results if r['criticality'] != 'hard']
    hard_pass = sum(1 for r in hard_results if r['passed'])
    soft_pass = sum(1 for r in soft_results if r['passed'])
    print(f'   硬门禁：{hard_pass}/{len(hard_results)} PASS')
    print(f'   软门禁：{soft_pass}/{len(soft_results)} PASS')

    if args.promote:
        baseline = {
            'created_at': datetime.datetime.now().isoformat(timespec='seconds'),
            'results': results,
        }
        baseline_path = _EVALS / 'baseline.json'
        baseline_path.write_text(json.dumps(baseline, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'\n📌 baseline 已保存：{baseline_path}')

    sys.exit(0 if hard_pass == len(hard_results) else 1)


if __name__ == '__main__':
    main()
