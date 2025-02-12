import json
import sys
from collections import defaultdict
from bril_cfg import form_basic_blocks, build_cfg

# ------------------ Data Flow Solver ------------------

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
        else:  # backward
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
        else:  # backward analysis
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

# ------------------ Reaching Definitions ------------------

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

# ------------------ Live Variables ------------------

class LiveVariables:
    def __init__(self, cfg, blocks):
        self.cfg = cfg
        self.blocks = blocks
        self.uses, self.defs = self.extract_uses_and_defs()

    def extract_uses_and_defs(self):
        # Compute use and def sets in a block-sensitive (ordered) manner.
        uses = {}
        defs = {}
        for block in self.blocks:
            label = block[0]["label"]
            block_use = set()
            block_def = set()
            for instr in block:
                # For each used variable, add it to use if it hasn't been defined in this block yet.
                if "args" in instr:
                    for var in instr["args"]:
                        if var not in block_def:
                            block_use.add(var)
                # Then, add any definition.
                if "dest" in instr:
                    block_def.add(instr["dest"])
            uses[label] = block_use
            defs[label] = block_def
        return uses, defs

    def merge(self, sets):
        return set().union(*sets)

    def transfer(self, block, out_set):
        # Live variables: in[B] = use[B] ∪ (out[B] - def[B])
        return self.uses[block].union(out_set - self.defs[block])

    def analyze(self):
        solver = DataFlowSolver(
            cfg=self.cfg,
            direction="backward",  # backward analysis for live variables
            merge=self.merge,
            transfer=self.transfer,
            initial=set(),
            gen_sets=self.uses  # initial in-sets are the block's use sets
        )
        return solver.solve()

# ------------------ Output Formatting ------------------

def format_set(data):
    return ", ".join(sorted(data)) if data else "∅"

def print_analysis_results(block_labels, in_sets, out_sets):
    for label in block_labels:
        print(f"{label}:")
        print(f"  in:  {format_set(in_sets.get(label, set()))}")
        print(f"  out: {format_set(out_sets.get(label, set()))}")
    print("\n")

# ------------------ Main Execution ------------------

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
        # Build a CFG that holds both successors and predecessors.
        cfg = {label: {"succs": list(cfg_raw[label]), "preds": []} for label in cfg_raw}
        for label, succs in cfg_raw.items():
            for succ in succs:
                if succ not in cfg:
                    cfg[succ] = {"succs": [], "preds": []}
                cfg[succ]["preds"].append(label)

        print("\nControl Flow Graph:")
        for label, data in cfg.items():
            print(f"{label}: {data}")

        # Get the block labels in the order they appear.
        block_labels = [block[0]["label"] for block in blocks]

        if analysis_type == "reaching-definitions":
            print("\nReaching Definitions Analysis \n")
            analysis = ReachingDefinitions(cfg, blocks)
        elif analysis_type == "live":
            print("\nLive Variables Analysis \n")
            analysis = LiveVariables(cfg, blocks)
        else:
            print("Unknown analysis type. Use 'reaching-definitions' or 'live'.")
            sys.exit(1)

        in_sets, out_sets = analysis.analyze()
        print_analysis_results(block_labels, in_sets, out_sets)

if __name__ == "__main__":
    main()