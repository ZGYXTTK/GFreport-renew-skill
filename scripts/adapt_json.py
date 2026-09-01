# -*- coding: utf-8 -*-
"""
adapt_json.py —— JSON + JSON Schema 化配置加载器（v1）

完全替代原 yaml_lite.py。新增 JSON Schema 校验（jsonschema 可选依赖，
无则降级为「加载即成功」并 WARN，不静默通过）。
"""
import json
import os
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

_HERE = Path(__file__).parent
_BASE = _HERE.parent
_SCHEMA_DIR = _BASE / 'config' / '_schemas'


def _try_jsonschema():
    try:
        import jsonschema
        return jsonschema
    except ImportError:
        return None


def load_json(path, schema_name=None, strict=True):
    """
    读取 JSON 配置（UTF-8，无 BOM）。

    schema_name: 与 config/_schemas/ 下的 schema 文件同名（如 '采集清单' → 采集清单.schema.json）
    strict: True 时若 schema 校验失败则抛 SystemExit；False 时 WARN 后继续

    返回 dict。Schema 校验失败、文件缺失、JSON 解析错误均抛出 SystemExit（不静默）。
    """
    p = Path(path)
    if not p.exists():
        raise SystemExit(f'❌ 配置文件不存在：{p}')

    try:
        with open(p, encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise SystemExit(f'❌ JSON 解析失败（{p}）：{e}')

    if schema_name:
        schema_path = _SCHEMA_DIR / f'{schema_name}.schema.json'
        if not schema_path.exists():
            print(f'⚠️  schema 文件不存在：{schema_path}（跳过校验）')
            return data
        try:
            with open(schema_path, encoding='utf-8') as f:
                schema = json.load(f)
        except Exception as e:
            raise SystemExit(f'❌ schema 读取失败（{schema_path}）：{e}')

        js = _try_jsonschema()
        if js is None:
            print(f'⚠️  jsonschema 未安装（pip install jsonschema），跳过 schema 校验（{schema_name}）')
            return data
        try:
            js.validate(data, schema)
        except js.ValidationError as e:
            msg = f'❌ schema 校验失败（{schema_name}）：{e.message}'
            if strict:
                raise SystemExit(msg)
            else:
                print(msg)
                return data

    return data


def load_endpoints():
    return load_json(_BASE / 'config' / 'endpoints.json', 'endpoints', strict=True)


def load_tool_registry():
    return load_json(_BASE / 'config' / 'tool_registry.json', 'tool_registry', strict=True)


def load_collection_list():
    return load_json(_BASE / 'config' / '采集清单.json', '采集清单', strict=True)


def load_authority_source_map():
    return load_json(_BASE / 'config' / '权威源映射.json', '权威源映射', strict=True)


def load_caliber_dict():
    return load_json(_BASE / 'config' / '口径字典.json', '口径字典', strict=True)


def load_timepoint_alignment():
    return load_json(_BASE / 'config' / '时点对齐.json', '时点对齐', strict=True)


def load_target_pool():
    return load_json(_BASE / 'config' / '标的池.json', '标的池', strict=True)


def load_channels():
    return load_json(_BASE / 'config' / 'channels.json', strict=False)


if __name__ == '__main__':
    """诊断：列出每个 JSON 配置 + schema 校验状态。"""
    funcs = [
        ('endpoints.json', load_endpoints, 'endpoints'),
        ('tool_registry.json', load_tool_registry, 'tool_registry'),
        ('采集清单.json', load_collection_list, '采集清单'),
        ('权威源映射.json', load_authority_source_map, '权威源映射'),
        ('口径字典.json', load_caliber_dict, '口径字典'),
        ('时点对齐.json', load_timepoint_alignment, '时点对齐'),
        ('标的池.json', load_target_pool, '标的池'),
        ('channels.json', load_channels, None),
    ]
    for name, fn, schema in funcs:
        try:
            data = fn()
            print(f'  ✅ {name} ({len(json.dumps(data, ensure_ascii=False))} chars)')
        except SystemExit as e:
            print(f'  ❌ {name}: {e}')