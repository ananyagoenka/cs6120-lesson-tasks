#!/usr/bin/env python3
import json
import sys
from bril_cfg import form_basic_blocks, build_cfg
from dom_utils import Dominators, ensure_unique_entry

def has_side_effects(instr):
    return instr.get("op") in ["call", "print", "jmp", "br", "ret"]

def is_loop_invariant(instr, loop_blocks, defs, invariant):
    if has_side_effects(instr):
        return False
    if "args" not in instr:
        return True  # const instr
    for arg in instr["args"]:
        arg_defs = defs.get(arg, [])
        if any(def_block in loop_blocks and arg not in invariant for def_block in arg_defs):
            return False
    return True

def licm(func):
    blocks = form_basic_blocks(func["instrs"])
    cfg_raw = build_cfg(blocks)
    cfg = {i: {"succs": list(cfg_raw.get(i, [])), "preds": []} for i in range(len(blocks))}
    for b, succs in cfg_raw.items():
        for s in succs:
            cfg[s]["preds"].append(b)

    entry = ensure_unique_entry(cfg, 0, {})
    doms = Dominators(cfg, entry)

    loops = []
    for src, succs in cfg_raw.items():
        for dst in succs:
            if dst in doms.dominators[src]:
                loop_blocks = set([dst, src])
                worklist = [src]
                while worklist:
                    b = worklist.pop()
                    for pred in cfg[b]["preds"]:
                        if pred not in loop_blocks:
                            loop_blocks.add(pred)
                            worklist.append(pred)
                loops.append((dst, loop_blocks))

    defs = {}
    for i, block in enumerate(blocks):
        for instr in block:
            if "dest" in instr:
                defs.setdefault(instr["dest"], []).append(i)

    for header, loop_blocks in loops:
        invariant_instrs = []
        invariant = set()
        changed = True
        while changed:
            changed = False
            for block_idx in loop_blocks:
                for instr in blocks[block_idx]:
                    if "dest" in instr and instr["dest"] not in invariant:
                        if is_loop_invariant(instr, loop_blocks, defs, invariant):
                            invariant.add(instr["dest"])
                            invariant_instrs.append((block_idx, instr))
                            changed = True

        if not invariant_instrs:
            continue  # Do NOT create preheader if nothing to move

        preheader_idx = len(blocks)
        preheader_label = f"preheader{preheader_idx}"
        preheader_block = [{"label": preheader_label}, {"op": "jmp", "labels": [blocks[header][0]["label"]]}]

        # Actually move invariant instructions
        for block_idx, instr in invariant_instrs:
            blocks[block_idx].remove(instr)
            preheader_block.insert(-1, instr)

        blocks.append(preheader_block)
        cfg[preheader_idx] = {"succs": [header], "preds": []}

        for pred in cfg[header]["preds"][:]:
            if pred not in loop_blocks:
                cfg[pred]["succs"].remove(header)
                cfg[pred]["succs"].append(preheader_idx)
                cfg[preheader_idx]["preds"].append(pred)
                cfg[header]["preds"].remove(pred)
        cfg[header]["preds"].append(preheader_idx)

    func["instrs"] = [instr for block in blocks for instr in block]

def main():
    if len(sys.argv) != 2:
        print("Usage: python loop_opt.py <bril_json_file>")
        sys.exit(1)

    with open(sys.argv[1], "r") as f:
        prog = json.load(f)

    for func in prog.get("functions", []):
        licm(func)

    print(json.dumps(prog, indent=2))

if __name__ == "__main__":
    main()