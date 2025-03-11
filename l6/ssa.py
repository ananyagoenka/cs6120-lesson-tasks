#!/usr/bin/env python3
import json
import sys
import copy
from collections import defaultdict

from bril_cfg import form_basic_blocks, build_cfg
from dom_utils import Dominators, ensure_unique_entry

def compute_live_vars(blocks, cfg):
    n = len(blocks)
    live_in = {i: set() for i in range(n)}
    live_out = {i: set() for i in range(n)}
    block_use = {}
    block_def = {}
    for i, block in enumerate(blocks):
        use = set()
        defs = set()
        for instr in block:
            if "label" in instr:
                continue
            if "args" in instr:
                for arg in instr["args"]:
                    if arg not in defs:
                        use.add(arg)
            if "dest" in instr:
                defs.add(instr["dest"])
        block_use[i] = use
        block_def[i] = defs
    changed = True
    while changed:
        changed = False
        for i in range(n):
            new_out = set()
            for succ in cfg.get(i, {}).get("succs", []):
                new_out |= live_in[succ]
            if new_out != live_out[i]:
                live_out[i] = new_out
                changed = True
            new_in = block_use[i] | (live_out[i] - block_def[i])
            if new_in != live_in[i]:
                live_in[i] = new_in
                changed = True
    return live_in, live_out

def get_types(func):
    types = {}
    for arg in func.get("args", []):
        types[arg["name"]] = arg["type"]
    for instr in func["instrs"]:
        if "dest" in instr and "type" in instr:
            if instr["dest"] not in types:
                types[instr["dest"]] = instr["type"]
    return types

def to_ssa(func):
    blocks = form_basic_blocks(func["instrs"])
    cfg_raw = build_cfg(blocks)
    cfg = {}
    for i in range(len(blocks)):
        cfg[i] = {"succs": list(cfg_raw.get(i, [])), "preds": []}
    for i, succs in cfg_raw.items():
        for s in succs:
            cfg[s]["preds"].append(i)
    block_labels = {}
    for i, block in enumerate(blocks):
        if block and "label" in block[0]:
            block_labels[i] = block[0]["label"]
        else:
            block_labels[i] = f"blk{i}"
    live_in, live_out = compute_live_vars(blocks, cfg)
    types = get_types(func)
    arg_names = {arg["name"] for arg in func.get("args", [])}
    prologue = []
    entry_label = block_labels[0]
    for v in sorted(live_in.get(0, set())):
        if v not in arg_names and v in types:
            prologue.append({"dest": v, "op": "undef", "type": types[v]})
    for v in sorted(live_in.get(0, set())):
        prologue.append({"op": "set", "args": [f"{v}.{entry_label}", v]})
    entry_block = 0
    entry_block = ensure_unique_entry(cfg, entry_block, block_labels)
    doms = Dominators(cfg, entry_block)
    dom_tree = doms.dom_tree
    stack = defaultdict(list)
    counters = defaultdict(int)
    for v in arg_names:
        stack[v].append(v)
    pre_instructions = defaultdict(list)
    post_instructions = defaultdict(list)
    def rename(b):
        label = block_labels[b]
        for v in sorted(live_in.get(b, set())):
            new_name = f"{v}.{label}"
            stack[v].append(new_name)
            pre_instructions[b].append({"op": "get", "dest": new_name, "type": types.get(v, "unknown")})
        for instr in blocks[b]:
            if "label" in instr:
                continue
            if "args" in instr:
                new_args = []
                for arg in instr["args"]:
                    if stack[arg]:
                        new_args.append(stack[arg][-1])
                    else:
                        new_args.append("undef")
                instr["args"] = new_args
            if "dest" in instr:
                var = instr["dest"]
                counters[(var, label)] += 1
                new_name = f"{var}.{label}"
                if counters[(var, label)] > 1:
                    new_name = f"{new_name}.{counters[(var, label)]}"
                instr["dest"] = new_name
                stack[var].append(new_name)
        for succ in cfg.get(b, {}).get("succs", []):
            succ_label = block_labels[succ]
            for v in sorted(live_in.get(succ, set()) & live_out.get(b, set())):
                current_ver = stack[v][-1] if stack[v] else "undef"
                post_instructions[b].append({"op": "set", "args": [f"{v}.{succ_label}", current_ver]})
        for child in sorted(dom_tree.get(b, [])):
            rename(child)
        for v in sorted(live_in.get(b, set())):
            if stack[v]:
                stack[v].pop()
        for instr in blocks[b]:
            if "dest" in instr:
                var = instr["dest"].split('.')[0]
                if stack[var]:
                    stack[var].pop()
    rename(entry_block)
    new_instrs = []
    new_instrs.extend(prologue)
    for i, block in enumerate(blocks):
        if block and "label" in block[0]:
            new_instrs.append(block[0])
        else:
            new_instrs.append({"label": block_labels[i]})
        new_instrs.extend(pre_instructions[i])
        start_idx = 1 if block and "label" in block[0] else 0
        new_instrs.extend(block[start_idx:])
        new_instrs.extend(post_instructions[i])
    if not new_instrs or new_instrs[-1].get("op") != "ret":
        new_instrs.append({"op": "ret"})
    func["instrs"] = new_instrs
    return func

def from_ssa(func):
    new_instrs = []
    for instr in func["instrs"]:
        op = instr.get("op")
        if op in ("set", "get", "undef"):
            continue
        new_instr = instr.copy()
        if "dest" in new_instr:
            new_instr["dest"] = new_instr["dest"].split('.')[0]
        if "args" in new_instr:
            new_instr["args"] = [arg.split('.')[0] for arg in new_instr["args"]]
        new_instrs.append(new_instr)
    func["instrs"] = new_instrs
    return func

def count_insns(prog):
    total = 0
    for func in prog.get("functions", []):
        total += len(func.get("instrs", []))
    return total

def transform_program(prog, mode):
    for func in prog.get("functions", []):
        if mode == "to_ssa":
            to_ssa(func)
        elif mode == "from_ssa":
            from_ssa(func)
    return prog

def main():
    if len(sys.argv) < 3:
        print("Usage: python ssa.py <to_ssa|from_ssa|stats> <bril_json_file>")
        sys.exit(1)
    mode = sys.argv[1]
    filename = sys.argv[2]
    with open(filename, "r") as f:
        prog = json.load(f)
    if mode == "stats":
        prog_orig = copy.deepcopy(prog)
        prog_ssa = transform_program(copy.deepcopy(prog), "to_ssa")
        prog_rt = transform_program(copy.deepcopy(prog), "to_ssa")
        prog_rt = transform_program(prog_rt, "from_ssa")
        orig_count = count_insns(prog_orig)
        ssa_count = count_insns(prog_ssa)
        rt_count = count_insns(prog_rt)
        stats = {
            "original_instruction_count": orig_count,
            "ssa_instruction_count": ssa_count,
            "roundtrip_instruction_count": rt_count,
            "increase_from_to_ssa": ssa_count - orig_count,
            "increase_from_roundtrip": rt_count - orig_count,
        }
        print(json.dumps(stats, indent=2))
    else:
        transformed = transform_program(prog, mode)
        print(json.dumps(transformed, indent=2))

if __name__ == "__main__":
    import copy
    main()