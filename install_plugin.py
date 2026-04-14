#!/usr/bin/env python3
"""
本地开发安装脚本：先卸载旧版 webnovel-writer 插件，再重新安装当前目录的本地版本。

用法：
    cd /path/to/webnovel-writer
    python install_plugin.py

说明：
    - 卸载和安装均使用 --scope project（仅当前项目生效）。
    - 如果插件未安装过，卸载命令会失败，脚本会忽略该错误并继续安装。
    - 如果 marketplace 已存在，add 命令会失败，脚本同样会忽略并继续。
"""

import subprocess
import sys
from pathlib import Path


def run(cmd: list[str], ignore_errors: bool = False) -> None:
    """执行命令，失败时打印错误并按需退出。"""
    print(f"\n▶ {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout.strip())
    if result.returncode != 0:
        if result.stderr:
            print(result.stderr.strip(), file=sys.stderr)
        if not ignore_errors:
            print(f"\n❌ 命令失败: {' '.join(cmd)}", file=sys.stderr)
            sys.exit(result.returncode)
        else:
            print(f"⚠️ 忽略错误（可能已满足预期状态）: {' '.join(cmd)}")


def main() -> None:
    plugin_dir = Path(__file__).parent.resolve()
    plugin_name = "webnovel-writer"
    marketplace_name = "webnovel-writer-marketplace"
    scope = "project"

    print(f"插件目录: {plugin_dir}")

    # 1. 先卸载已有插件（如果未安装则忽略错误）
    run(["claude", "plugin", "uninstall", plugin_name, "--scope", scope], ignore_errors=True)

    # 2. 注册本地 marketplace（如果已存在则忽略错误）
    run(
        ["claude", "plugin", "marketplace", "add", str(plugin_dir), "--scope", scope],
        ignore_errors=True,
    )

    # 3. 安装插件
    run(
        ["claude", "plugin", "install", f"{plugin_name}@{marketplace_name}", "--scope", scope],
        ignore_errors=False,
    )

    print(f"\n✅ 本地插件 '{plugin_name}' 安装完成，重启 Claude Code 后生效。")


if __name__ == "__main__":
    main()
