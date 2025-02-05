import json
import sys
import os
from collections import defaultdict

sys.path.append(os.path.abspath("../l2"))
from bril_cfg import form_basic_blocks  

SIDE_EFFECT_OPS = {"print", "store", "call", "ret", "jmp", "br"}

def has_side_effect(instr):
    """Check if an instruction has side effects (e.g., print, store)."""
    return 'op' in instr and instr['op'] in SIDE_EFFECT_OPS

def analyze_liveness(func):
    """Compute used variables in a function, including branch conditions."""
    used_vars = set()
    
    for instr in func["instrs"]:
        if "args" in instr:
            used_vars.update(instr["args"]) 
        
        if "op" in instr and instr["op"] == "br":  
            used_vars.add(instr["args"][0]) 

    return used_vars

def remove_unused_variables(func):
    """
    Removes unused variables by working on basic blocks.
    Uses global liveness information to avoid removing needed variables.
    """
    used_vars = analyze_liveness(func)  

    blocks = form_basic_blocks(func["instrs"])
    changed = False

    for block in blocks:
        new_block = []
        for instr in block:
            dest = instr.get("dest")

            if has_side_effect(instr):
                new_block.append(instr)
                continue

            if dest and dest not in used_vars:
                changed = True
                continue  

            new_block.append(instr)

        block[:] = new_block 

    func["instrs"] = [instr for block in blocks for instr in block]
    return changed

def remove_shadowed_assignments(block, global_used_vars):
    """
    Removes assignments that are overwritten **before being used** in the same block.
    Ensures globally needed variables are not removed.
    """
    last_def = {}
    to_drop = set()

    # First pass: Identify droppable assignments
    for i, instr in enumerate(block):
        args = instr.get("args", [])
        dest = instr.get("dest")

        for arg in args:
            if arg in last_def:
                del last_def[arg]

        if dest:
            if dest in last_def and dest not in global_used_vars:
                to_drop.add(last_def[dest]) 
            last_def[dest] = i  

    # Second pass: Remove marked instructions
    new_block = [instr for i, instr in enumerate(block) if i not in to_drop]
    return new_block

def trivial_dce_function(func):
    """
    Iteratively applies DCE and local optimizations until no further progress.
    """
    while True:
        used_vars = analyze_liveness(func)  
        changed1 = remove_unused_variables(func)  
        changed2 = False

        blocks = form_basic_blocks(func["instrs"])
        new_instrs = []
        for block in blocks:
            optimized_block = remove_shadowed_assignments(block, used_vars)  
            if optimized_block != block:
                changed2 = True
            new_instrs.extend(optimized_block)

        if not (changed1 or changed2): 
            break

        func["instrs"] = new_instrs  

def trivial_dce(program):
    """
    Apply DCE to all functions in the program.
    """
    for func in program["functions"]:
        trivial_dce_function(func)
    return program

def main():
    program = json.load(sys.stdin)
    program = trivial_dce(program)
    json.dump(program, sys.stdout, indent=2, sort_keys=True)

if __name__ == "__main__":
    main()