#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix_trace_includes.py — 自动修补 CAF 树里缺失的 "-I$(src)"

问题根源
--------
内核里带 tracepoint 的头文件经常这样写:

    #define TRACE_INCLUDE_PATH .
    #define TRACE_INCLUDE_FILE xxx-trace
    #include <trace/define_trace.h>

include/trace/define_trace.h 里:

    #define __TRACE_INCLUDE(system) __stringify(TRACE_INCLUDE_PATH/system.h)
    #include TRACE_INCLUDE(TRACE_INCLUDE_FILE)      // => #include "./xxx-trace.h"

因为路径带 "./"，编译器只会去「当前目录」找，找不到就报
    fatal error: './xxx-trace.h' file not found

标准内核的做法是在该目录的 Makefile 里加一行:
    CFLAGS_<文件名>.o := -I$(src)

CAF 树里若干目录漏了这行（vivo/高通删改时漏掉），导致编译失败。

本脚本的做法
-----------
遍历整棵树:
  1. 找所有含 "define TRACE_INCLUDE_PATH ." 的头文件
  2. 找出创建 tracepoint 的 .c（同名 .c，或 include 了该头且定义了
     CREATE_TRACE_POINTS 的 .c）
  3. 若该目录 Makefile 里没有对应的 CFLAGS_<x>.o，就补上

用法:
  python3 fix_trace_includes.py <kernel_tree_root>
"""
import os
import re
import sys

# 只修补这些量级，避免扫到无关目录
SKIP_DIRS = {".git", "Documentation", "tools", "samples", "scripts", ".tmp"}


def read(p):
    try:
        return open(p, encoding="utf-8", errors="surrogateescape").read()
    except Exception:
        return ""


def main():
    root = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
    fixed = []
    scanned_h = 0

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        hs = [f for f in filenames if f.endswith(".h")]
        if not hs:
            continue
        cs = {f[:-2]: f for f in filenames if f.endswith(".c")}
        if not cs:
            continue
        mk = os.path.join(dirpath, "Makefile")
        if not os.path.exists(mk):
            continue
        mk_text = read(mk)
        need = set()

        for h in hs:
            ht = read(os.path.join(dirpath, h))
            if "TRACE_INCLUDE_PATH" not in ht:
                continue
            scanned_h += 1
            # 只处理 TRACE_INCLUDE_PATH 被定义成 "." 的
            if not re.search(r"#\s*define\s+TRACE_INCLUDE_PATH\s+\.\s*$",
                             ht, re.M):
                continue
            base = h[:-2]
            target = None
            if base in cs:
                target = base
            else:
                for cbase, cfile in cs.items():
                    ct = read(os.path.join(dirpath, cfile))
                    if "CREATE_TRACE_POINTS" in ct and h in ct:
                        target = cbase
                        break
            if target and ("CFLAGS_%s.o" % target) not in mk_text:
                need.add(target)

        if need:
            with open(mk, "a", encoding="utf-8",
                      errors="surrogateescape") as f:
                for t in sorted(need):
                    f.write("\nCFLAGS_%s.o := -I$(src)\n" % t)
                    fixed.append(os.path.relpath(
                        os.path.join(dirpath, t + ".c"), root))
            mk_text = read(mk)

    print("[fix] 扫描了 %d 个 trace 头文件" % scanned_h)
    print("[fix] 修补了 %d 个目标:" % len(fixed))
    for f in fixed[:60]:
        print("   ", f)
    if len(fixed) > 60:
        print("    ... 还有 %d 个" % (len(fixed) - 60))
    return 0


if __name__ == "__main__":
    sys.exit(main())
