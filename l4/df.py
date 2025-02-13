import json
import sys
from collections import defaultdict
from bril_cfg import form_basic_blocks, build_cfg

class DataFlowSolver:
    def __init__(self, cfg, direction, merge, transfer, initial, gen_sets):
        self.cfg = cfg
        self.direction = direction
        self.merge = merge
        self.transfer = transfer
        self.initial = initial
        if direction == "forward":
            self.in_sets = {b: set() for b in cfg}
            self.out_sets = {b: gen_sets[b].copy() for b in cfg}
        else:
            self.out_sets = {b: set() for b in cfg}
            self.in_sets = {b: gen_sets[b].copy() for b in cfg}

    def solve(self):
        if self.direction == "forward":
            worklist = set(self.cfg.keys())
            while worklist:
                block = worklist.pop()
                preds = self.cfg[block]["preds"]
                new_in = self.merge([self.out_sets[p] for p in preds]) if preds else self.initial.copy()
                if new_in != self.in_sets[block]:
                    self.in_sets[block] = new_in
                    new_out = self.transfer(block, new_in)
                    if new_out != self.out_sets[block]:
                        self.out_sets[block] = new_out
                        worklist.update(self.cfg[block]["succs"])
            return self.in_sets, self.out_sets
        else:
            worklist = set(self.cfg.keys())
            while worklist:
                block = worklist.pop()
                succs = self.cfg[block]["succs"]
                new_out = self.merge([self.in_sets[s] for s in succs]) if succs else self.initial.copy()
                if new_out != self.out_sets[block]:
                    self.out_sets[block] = new_out
                    new_in = self.transfer(block, new_out)
                    if new_in != self.in_sets[block]:
                        self.in_sets[block] = new_in
                        worklist.update(self.cfg[block]["preds"])
            return self.in_sets, self.out_sets

class ReachingDefinitions:
    def __init__(self, cfg, blocks):
        self.cfg = cfg
        self.blocks = blocks
        self.definitions, self.kill_sets = self.extract_definitions_and_kills()

    def extract_definitions_and_kills(self):
        definitions = defaultdict(set)
        kill_sets = defaultdict(set)
        all_defs = defaultdict(set)
        for block in self.blocks:
            label = block[0]["label"]
            for instr in block:
                if "dest" in instr:
                    var = instr["dest"]
                    def_name = f"{var}_{label}"
                    definitions[label].add(def_name)
                    all_defs[var].add(def_name)
        for block in self.blocks:
            label = block[0]["label"]
            for instr in block:
                if "dest" in instr:
                    var = instr["dest"]
                    kill_sets[label] = all_defs[var] - {f"{var}_{label}"}
        return definitions, kill_sets

    def merge(self, sets):
        return set().union(*sets)

    def transfer(self, block, in_set):
        return self.definitions[block].union(in_set - self.kill_sets[block])

    def analyze(self):
        solver = DataFlowSolver(
            cfg=self.cfg,
            direction="forward",
            merge=self.merge,
            transfer=self.transfer,
            initial=set(),
            gen_sets=self.definitions
        )
        return solver.solve()

class LiveVariables:
    def __init__(self, cfg, blocks):
        self.cfg = cfg
        self.blocks = blocks
        self.uses, self.defs = self.extract_uses_and_defs()

    def extract_uses_and_defs(self):
        uses = {}
        defs = {}
        for block in self.blocks:
            label = block[0]["label"]
            block_use = set()
            block_def = set()
            for instr in block:
                if "args" in instr:
                    for var in instr["args"]:
                        if var not in block_def:
                            block_use.add(var)
                if "dest" in instr:
                    block_def.add(instr["dest"])
            uses[label] = block_use
            defs[label] = block_def
        return uses, defs

    def merge(self, sets):
        return set().union(*sets)

    def transfer(self, block, out_set):
        return self.uses[block].union(out_set - self.defs[block])

    def analyze(self):
        solver = DataFlowSolver(
            cfg=self.cfg,
            direction="backward",
            merge=self.merge,
            transfer=self.transfer,
            initial=set(),
            gen_sets=self.uses
        )
        return solver.solve()

BOTTOM = "⊥"
NC = "NC"

def meet_val(x, y):
    if x == y:
        return x
    elif x == BOTTOM:
        return y
    elif y == BOTTOM:
        return x
    else:
        return NC

def merge_maps(maps):
    result = {}
    all_keys = set()
    for m in maps:
        all_keys |= set(m.keys())
    for key in all_keys:
        vals = [m.get(key, BOTTOM) for m in maps]
        merged = vals[0]
        for v in vals[1:]:
            merged = meet_val(merged, v)
        result[key] = merged
    return result

def transfer_block(block, in_map):
    state = in_map.copy()
    for instr in block:
        if "dest" in instr:
            var = instr["dest"]
            op = instr.get("op")
            if op == "const":
                state[var] = instr["value"]
            elif op in {"add", "sub", "mul", "div"}:
                args = instr.get("args", [])
                arg_vals = []
                all_const = True
                for arg in args:
                    val = state.get(arg, BOTTOM)
                    if isinstance(val, (int, float)):
                        arg_vals.append(val)
                    else:
                        all_const = False
                        break
                if all_const and len(arg_vals) == len(args):
                    if op == "add":
                        res = arg_vals[0] + arg_vals[1]
                    elif op == "sub":
                        res = arg_vals[0] - arg_vals[1]
                    elif op == "mul":
                        res = arg_vals[0] * arg_vals[1]
                    elif op == "div":
                        res = arg_vals[0] // arg_vals[1] if arg_vals[1] != 0 else NC
                    state[var] = res
                else:
                    state[var] = NC
            else:
                state[var] = NC
    return state

class ConstantPropagation:
    def __init__(self, cfg, blocks):
        self.cfg = cfg
        self.blocks = blocks
        self.blocks_dict = {block[0]["label"]: block for block in blocks}
        self.gen_sets = {block[0]["label"]: transfer_block(block, {}) for block in blocks}

    def merge(self, maps):
        return merge_maps(maps)

    def transfer(self, block_label, in_map):
        block = self.blocks_dict[block_label]
        return transfer_block(block, in_map)

    def analyze(self):
        solver = DataFlowSolver(
            cfg=self.cfg,
            direction="forward",
            merge=self.merge,
            transfer=self.transfer,
            initial={},
            gen_sets=self.gen_sets
        )
        return solver.solve()

def format_set(data):
    return ", ".join(sorted(data)) if data else "∅"

def print_analysis_results(block_labels, in_sets, out_sets):
    for label in block_labels:
        print(f"{label}:")
        print(f"  in:  {format_set(in_sets.get(label, set()))}")
        print(f"  out: {format_set(out_sets.get(label, set()))}")
    print("\n")

def format_const_map(mapping):
    if not mapping:
        return "∅"
    items = []
    for var, val in sorted(mapping.items()):
        items.append(f"{var} = {val}")
    return ", ".join(items)

def print_constant_results(block_labels, in_sets, out_sets):
    for label in block_labels:
        print(f"{label}:")
        print(f"  in:  {format_const_map(in_sets.get(label, {}))}")
        print(f"  out: {format_const_map(out_sets.get(label, {}))}")
    print("\n")

def main():
    if len(sys.argv) < 3:
        print("Usage: python df.py <bril_json_file> <analysis_type>")
        sys.exit(1)

    bril_file = sys.argv[1]
    analysis_type = sys.argv[2]

    with open(bril_file, "r") as f:
        bril_program = json.load(f)

    for function in bril_program.get("functions", []):
        blocks = form_basic_blocks(function["instrs"])
        cfg_raw = build_cfg(blocks)
        cfg = {label: {"succs": list(cfg_raw[label]), "preds": []} for label in cfg_raw}
        for label, succs in cfg_raw.items():
            for succ in succs:
                if succ not in cfg:
                    cfg[succ] = {"succs": [], "preds": []}
                cfg[succ]["preds"].append(label)

        print("\nControl Flow Graph:")
        for label, data in cfg.items():
            print(f"{label}: {data}")

        block_labels = [block[0]["label"] for block in blocks]

        if analysis_type == "reaching-definitions":
            from df import ReachingDefinitions
            print("\nReaching Definitions Analysis \n")
            analysis = ReachingDefinitions(cfg, blocks)
            in_sets, out_sets = analysis.analyze()
            print_analysis_results(block_labels, in_sets, out_sets)
        elif analysis_type == "live":
            from df import LiveVariables
            print("\nLive Variables Analysis \n")
            analysis = LiveVariables(cfg, blocks)
            in_sets, out_sets = analysis.analyze()
            print_analysis_results(block_labels, in_sets, out_sets)
        elif analysis_type == "constant":
            print("\nConstant Propagation Analysis \n")
            analysis = ConstantPropagation(cfg, blocks)
            in_sets, out_sets = analysis.analyze()
            print_constant_results(block_labels, in_sets, out_sets)
        else:
            print("Unknown analysis type. Use 'reaching-definitions', 'live', or 'constant'.")
            sys.exit(1)

if __name__ == "__main__":
    main()