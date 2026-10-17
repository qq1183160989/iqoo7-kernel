#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
patch_module.py — 让内核接受"版本不匹配"的厂商模块

背景:
  vendor_boot 里的原厂模块是用 5.4.147-qgki-gd725e4d6c02e 编的,
  而我们编的内核是 5.4.289-qgki。正常情况下内核会拒绝加载:
    - check_modinfo(): vermagic 不一致 -> -ENOEXEC
    - check_version(): 符号 CRC 不一致 -> 拒绝

  第三方 AK3 内核用的就是同样一招 —— 否则它的模块也加载不了。

改动 (在 kernel/module.c 里):
  1. check_modinfo()  开头插入 return 0;   (跳过 vermagic)
  2. check_version()  开头插入 return 1;   (跳过 CRC, 1 = 成功)

用法:
  python3 patch_module.py <path/to/kernel/module.c>
"""
import re
import sys


def main():
    if len(sys.argv) < 2:
        print("用法: python3 patch_module.py <kernel/module.c>")
        return 2
    path = sys.argv[1]
    src = open(path, encoding="utf-8", errors="surrogateescape").read()
    orig = src

    # ---- 1) check_modinfo: 跳过 vermagic ----
    pat1 = re.compile(r"(static int check_modinfo\([^)]*\)\s*\n\{\n)")
    m = pat1.search(src)
    if m:
        src = (src[:m.end()]
               + "\treturn 0; /* patched: skip vermagic check */\n"
               + src[m.end():])
        print("[patch] check_modinfo -> return 0  (跳过 vermagic)")
    else:
        print("[!] 没找到 check_modinfo，可能函数签名不同")

    # ---- 2) check_version: 跳过 CRC ----
    pat2 = re.compile(
        r"(static int check_version\(const struct load_info \*info,"
        r".*?\)\s*\n\{\n)",
        re.S)
    m = pat2.search(src)
    if m:
        src = (src[:m.end()]
               + "\treturn 1; /* patched: skip CRC check */\n"
               + src[m.end():])
        print("[patch] check_version -> return 1  (跳过 CRC)")
    else:
        print("[!] 没找到 check_version，可能函数签名不同")

    if src == orig:
        print("[!] 补丁没有生效")
        return 1

    open(path, "w", encoding="utf-8", errors="surrogateescape").write(src)

    # ---- 验证 ----
    check = open(path, encoding="utf-8", errors="surrogateescape").read()
    n = check.count("patched: skip")
    print("[verify] 补丁标记出现 %d 次 (应为 2)" % n)
    return 0 if n == 2 else 1


if __name__ == "__main__":
    sys.exit(main())
