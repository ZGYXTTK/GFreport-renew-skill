# -*- coding: utf-8 -*-
"""
workspace.py —— 工作区多源探测（v1，open-source 可移植）

探测优先级（与 SKILL.md 一致）：
  1. 显式 --ws 参数
  2. --anchor（输入旧月报原始路径）所在目录
  3. 环境变量 DSH_WORKSPACE
  4. 从 DSH_SESSION_JSONL 路径解码（Harness 专属）
  5. 当前工作目录 os.getcwd()

返回工作区路径；无法确定时返回 None。
"""
import os
import re
from pathlib import Path

_ENC_SEP = re.compile(r'(?<!\\)-(?!:)')
_ENC_DRIVE = re.compile(r'^([A-Za-z])\\')


def _decode_session_seg():
    """从 DSH_SESSION_JSONL 还原工作区路径（Harness 专属，非空返回 str 否则 None）。"""
    sj = os.environ.get('DSH_SESSION_JSONL')
    if not sj:
        return None
    try:
        seg = os.path.basename(os.path.dirname(os.path.dirname(os.path.abspath(sj))))
    except Exception:
        return None
    seg = seg.strip('-')
    s = re.sub(r'~([0-9A-Fa-f]{4})', lambda m: chr(int(m.group(1), 16)), seg)
    s = _ENC_SEP.sub('\\\\', s)
    s = _ENC_DRIVE.sub(r'\1:\\', s)
    return s


def detect_workspace(explicit=None, anchor=None):
    """返回工作区路径；无法确定时返回 None。"""
    candidates = []

    def _ok(p):
        return p and os.path.isdir(p)

    if _ok(explicit):
        return explicit
    if explicit:
        candidates.append(explicit)

    if anchor:
        if os.path.isdir(anchor):
            if _ok(anchor):
                return anchor
            candidates.append(anchor)
        elif os.path.isfile(anchor):
            parent = os.path.dirname(os.path.abspath(anchor))
            if _ok(parent):
                return parent
            candidates.append(parent)

    env = os.environ.get('DSH_WORKSPACE')
    if _ok(env):
        return env
    if env:
        candidates.append(env)

    dec = _decode_session_seg()
    if _ok(dec):
        return dec
    if dec:
        candidates.append(dec)

    cwd = os.getcwd()
    if _ok(cwd):
        return cwd
    return candidates[0] if candidates else None


def is_inside_skill_base(path, skill_base):
    """p 是否位于 skill 基目录内（路径段边界归一化，Windows 反斜杠也生效）。"""
    n = os.path.normcase(os.path.abspath(path)).replace('\\', '/')
    b = os.path.normcase(os.path.abspath(skill_base)).replace('\\', '/')
    return n == b or n.startswith(b + '/')


if __name__ == '__main__':
    import sys
    ws = detect_workspace()
    print(f'workspace: {ws}')
    print(f'is_dir: {bool(ws) and os.path.isdir(ws)}')