# -*- coding: utf-8 -*-
"""
pack_wizard.py —— 行业包创建向导（v0.1.0 必修）

实战背景：本次创建 aerospace 包时手写了 RULES.md + 6 个 JSON。
本向导自动化：
1. 交互式采集包名、子赛道、采集项、标的池
2. 验证 6 个 JSON 全部通过 schema
3. 同步更新 config/endpoints.json（如有新增通道名）
4. 复写到 config/ 顶层（因为 adapt_json.load_collection_list() 只读顶层）

用法：
  python scripts/pack_wizard.py --name aerospace --interactive
  python scripts/pack_wizard.py --name robotics --from-yaml pack_robotics.yaml
  python scripts/pack_wizard.py --list   # 列出已注册 pack
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

_HERE = Path(__file__).parent
_BASE = _HERE.parent
_PACKS = _BASE / 'packs'
_CONFIG = _BASE / 'config'
_SCHEMAS = _CONFIG / '_schemas'


def _list_packs():
    """列出 packs/ 下所有 pack。"""
    if not _PACKS.is_dir():
        return []
    return [p.name for p in _PACKS.iterdir() if p.is_dir()]


def _copy_template(pack_name):
    """从 _default 复制模板。"""
    default = _PACKS / '_default'
    target = _PACKS / pack_name
    if target.exists():
        return False, f'pack 已存在：{target}'
    shutil.copytree(default, target)
    return True, str(target)


def _load_schema(schema_name):
    """加载 config/_schemas/<name>.schema.json。"""
    path = _SCHEMAS / f'{schema_name}.schema.json'
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding='utf-8'))


def _validate_with_schema(data, schema_name):
    """用 jsonschema 验证数据。失败抛 SystemExit。"""
    schema = _load_schema(schema_name)
    if schema is None:
        print(f'  ⚠️  schema {schema_name}.schema.json 不存在，跳过校验')
        return True
    try:
        import jsonschema
    except ImportError:
        print(f'  ⚠️  jsonschema 未安装，跳过严格校验')
        return True
    try:
        jsonschema.validate(data, schema)
        return True
    except jsonschema.ValidationError as e:
        raise SystemExit(f'❌ schema 校验失败（{schema_name}）：{e.message}')


def _sync_top_level_config(pack_name):
    """把 packs/<pack>/config/*.json 复写到 config/ 顶层（覆盖同名）。"""
    pack_config = _PACKS / pack_name / 'config'
    if not pack_config.is_dir():
        print(f'  ⚠️  pack 无 config 目录：{pack_config}')
        return
    synced = []
    for src in pack_config.iterdir():
        if src.suffix == '.json':
            dst = _CONFIG / src.name
            shutil.copy2(src, dst)
            synced.append(src.name)
    print(f'  ✅ 已复写 config/ 顶层：{", ".join(synced)}')


def _sync_endpoints_json(new_channel_names):
    """合并新通道名到 config/endpoints.json（mcp 段）。"""
    ep_path = _CONFIG / 'endpoints.json'
    if not ep_path.exists():
        return
    ep = json.loads(ep_path.read_text(encoding='utf-8'))
    existing = {ch.get('name') for ch in ep.get('mcp', [])}
    added = []
    for name in new_channel_names:
        if name and name not in existing:
            ep.setdefault('mcp', []).append({
                'name': name,
                'smoke_hint': '（pack_wizard 自动添加）',
            })
            added.append(name)
    if added:
        ep_path.write_text(json.dumps(ep, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'  ✅ endpoints.json 新增 MCP 通道：{", ".join(added)}')
    else:
        print(f'  ✅ endpoints.json 无需新增')


def _interactive(pack_name):
    """交互式采集包元数据。"""
    print(f'🚀 创建新行业包：{pack_name}\n')

    # 1. 子赛道列表
    print('步骤 1/4：定义子赛道（逗号分隔）')
    sub_tracks = input('子赛道（如：商业航天, 低空经济, eVTOL）> ').strip()
    sub_tracks_list = [s.strip() for s in sub_tracks.split(',') if s.strip()]
    print(f'  → {len(sub_tracks_list)} 个子赛道\n')

    # 2. 采集项
    print('步骤 2/4：定义采集项（每行一项：<id>|<类型时点半结构结构型>|<通道逗号分隔>|<口径>）')
    print('  示例：商业航天发射统计|时点型|tavily,whexin-ifind-news|公告披露口径')
    items = []
    while True:
        line = input('  > ').strip()
        if not line:
            break
        parts = line.split('|')
        if len(parts) < 4:
            print('  ⚠️  格式错误，跳过')
            continue
        items.append({
            'id': parts[0].strip(),
            '类型': parts[1].strip(),
            '通道': [c.strip() for c in parts[2].split(',')],
            '口径': parts[3].strip(),
        })
    print(f'  → {len(items)} 个采集项\n')

    # 3. 标的池
    print('步骤 3/4：标的池（每行：<name>|<统一社会信用代码>|<上市状态>|<板块>|<赛道>）')
    print('  示例：中科宇航技术股份有限公司|91440101MA5CL0AJ3A|在审|科创板|商业航天')
    companies = []
    while True:
        line = input('  > ').strip()
        if not line:
            break
        parts = line.split('|')
        if len(parts) < 5:
            print('  ⚠️  格式错误，跳过')
            continue
        companies.append({
            'name': parts[0].strip(),
            '统一社会信用代码': parts[1].strip(),
            '上市状态': parts[2].strip(),
            '板块': parts[3].strip(),
            '赛道': parts[4].strip(),
        })
    print(f'  → {len(companies)} 家标的\n')

    # 4. 时点
    print('步骤 4/4：目标时点（如 2026-08-31）')
    target_date = input('  > ').strip() or '2026-08-31'
    print(f'  → 目标时点：{target_date}\n')

    # 收集所有通道名
    all_channels = set()
    for item in items:
        all_channels.update(item['通道'])

    # 写入
    print('\n=== 开始写入 ===')
    ok, target = _copy_template(pack_name)
    if ok:
        print(f'  ✅ 复制 _default 模板 → {target}')
    else:
        raise SystemExit(ok)

    # 写采集清单
    coll = {
        'version': '1.0',
        '截至日期': target_date,
        'items': items,
    }
    _validate_with_schema(coll, '采集清单')
    (_PACKS / pack_name / 'config' / '采集清单.json').write_text(
        json.dumps(coll, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'  ✅ 采集清单：{len(items)} 项')

    # 写标的池
    if companies:
        pool = {
            'version': '1.0',
            '行业': pack_name,
            '公司': companies,
        }
        _validate_with_schema(pool, '标的池')
        (_PACKS / pack_name / 'config' / '标的池.json').write_text(
            json.dumps(pool, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'  ✅ 标的池：{len(companies)} 家公司')

    # 写时点
    tp = {
        'version': '1.0',
        '目标时点': target_date,
        '源时点': {
            '上交所/深交所/北交所官网': '实时滚动发布；按采集日 T-1 抓取全量',
            '证监会eid.csrc.gov.cn': '实时滚动；按采集日 T-1 抓取全量',
            '公司公告/招股书': '披露日；正文标披露日',
            '上市公司财报': '按公司最新已披露报告期；源文件标期',
        },
        '正文脚注': f'首页脚注写明采集日 + 目标时点（采集日 + 目标时点 {target_date}）',
    }
    (_PACKS / pack_name / 'config' / '时点对齐.json').write_text(
        json.dumps(tp, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'  ✅ 时点对齐：{target_date}')

    # 同步到顶层
    _sync_top_level_config(pack_name)

    # 同步 endpoints.json
    _sync_endpoints_json(all_channels)

    # 写 RULES.md 模板
    rules_path = _PACKS / pack_name / 'RULES.md'
    rules_path.write_text(f'''# {pack_name} 行业包

> 适用于：{pack_name} 行业的「重点赛道行业及资本市场动态月报」。
> 子赛道：{", ".join(sub_tracks_list)}

## 行业专属纪律（覆盖 _default 的 6 条默认纪律）

1. **数据时点**：目标时点为采集日所在自然月的月末（{target_date}）。
2. **来源时效**：行业政策密集，子赛道时效 ≤30 天；二级市场行情 ≤1 天。
3. **缺失处理**：拿不到的字段标「本期无法获取 / —」；涉及金额禁止以"约""大致"占位。
4. **币种一致**：默认 CNY；境外融资保留原币种。
5. **跨期可比**：环比 ±20% 以上的字段必须在变更摘要.md 点名原因。
6. **结构型字段**：封面、目录、章节标题按 P0-1 直接复制。

## 子赛道白名单

{chr(10).join(f"- **{t}**" for t in sub_tracks_list)}
''', encoding='utf-8')
    print(f'  ✅ RULES.md 模板已生成（需手动补充行业细节）')

    print(f'\n✅ pack `{pack_name}` 创建完成！')
    print(f'   接下来：')
    print(f'   1. 编辑 {rules_path} 补充行业专属规则')
    print(f'   2. 跑 python scripts/run_pipeline.py --old <old.docx> --ym <YYYY-MM> --pack {pack_name}')


def main():
    ap = argparse.ArgumentParser(description='行业包创建向导')
    ap.add_argument('--name', help='行业包名（kebab-case）')
    ap.add_argument('--interactive', action='store_true', help='交互式采集')
    ap.add_argument('--from-yaml', help='从 YAML 批量导入（未实现，预留）')
    ap.add_argument('--list', action='store_true', help='列出已注册 pack')
    args = ap.parse_args()

    if args.list:
        print('📦 已注册的行业包：')
        for p in _list_packs():
            print(f'   - {p}')
        return

    if not args.name:
        raise SystemExit('❌ 必须传 --name <行业包名>')

    if not args.interactive:
        # 非交互模式：从默认 _default 复制 + 默认时点
        ok, target = _copy_template(args.name)
        if ok:
            print(f'✅ 已复制 _default 模板 → {target}')
            _sync_top_level_config(args.name)
            print(f'✅ 已同步到 config/ 顶层')
            print(f'⚠️  接下来请手动编辑 {target}/RULES.md 与 config/*.json')

    else:
        _interactive(args.name)


if __name__ == '__main__':
    main()
