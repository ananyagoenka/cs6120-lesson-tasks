import json
import sys
from collections import defaultdict

def form_basic_blocks(instrs):
    """Splits a Bril program into basic blocks."""
    blocks = []
    current_block = []

    for instr in instrs:
        if "label" in instr or (current_block and instr.get("op") in ["jmp", "br", "ret"]):
            if current_block:
                blocks.append(current_block)
                current_block = []

        current_block.append(instr)

    if current_block:
        blocks.append(current_block)

    return blocks

def build_cfg(blocks):
    """Constructs a control flow graph (CFG) from a list of basic blocks."""
    cfg = defaultdict(set) 
    labels = {}

    for idx, block in enumerate(blocks):
        if "label" in block[0]:  
            labels[block[0]["label"]] = idx  

    for i, block in enumerate(blocks):
        last_instr = block[-1]

        if last_instr.get("op") == "jmp":
            dest = last_instr["labels"][0]
            cfg[i].add(labels[dest])

        elif last_instr.get("op") == "br":
            true_dest, false_dest = last_instr["labels"]
            cfg[i].add(labels[true_dest])
            cfg[i].add(labels[false_dest])

        elif last_instr.get("op") != "ret":  
            if i + 1 < len(blocks):
                cfg[i].add(i + 1)

    return cfg

def main():
    if len(sys.argv) < 2:
        print("Usage: python bril_cfg.py <bril_json_file>")
        sys.exit(1)

    with open(sys.argv[1], "r") as f:
        bril_program = json.load(f)

    for function in bril_program.get("functions", []):
        print(f"\nFunction: {function['name']}")

        # Form basic blocks
        blocks = form_basic_blocks(function["instrs"])
        print("\nBasic Blocks:")
        for idx, block in enumerate(blocks):
            print(f"Block {idx}: {block}")

        # Build CFG
        cfg = build_cfg(blocks)
        print("\nControl Flow Graph:")
        for src, dests in cfg.items():
            print(f"Block {src} -> {list(dests)}")

if __name__ == "__main__":
    main()
