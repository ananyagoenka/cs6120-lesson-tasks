import json
import sys
from collections import defaultdict
from bril_cfg import form_basic_blocks, build_cfg

def dfs_postorder(cfg, start, visited=None, result=None):
    if visited is None:
        visited = set()
    if result is None:
        result = []
    visited.add(start)
    for s in cfg[start]["succs"]:
        if s not in visited:
            dfs_postorder(cfg, s, visited, result)
    result.append(start)
    return result

def build_postorder_map(cfg, entry):
    post = dfs_postorder(cfg, entry)
    return {b: i for i, b in enumerate(post)}

def intersect_idom(x, y, idom, postorder_index):
    while x != y:
        if postorder_index[x] < postorder_index[y]:
            x = idom[x]
        else:
            y = idom[y]
    return x

def compute_idom(cfg, entry, dominators):
    idom = {entry: entry}
    for b in cfg:
        if b != entry:
            idom[b] = None
    postorder_index = build_postorder_map(cfg, entry)
    changed = True
    while changed:
        changed = False
        rev_post = sorted(cfg.keys(), key=lambda x: postorder_index[x], reverse=True)
        if entry in rev_post:
            rev_post.remove(entry)
        for b in rev_post:
            preds = [p for p in cfg[b]["preds"] if idom[p] is not None]
            if not preds:
                continue
            new_idom = preds[0]
            for p in preds[1:]:
                new_idom = intersect_idom(new_idom, p, idom, postorder_index)
            if idom[b] != new_idom:
                idom[b] = new_idom
                changed = True
    return idom

def find_all_paths(cfg, start, end, path=None):
    if path is None:
        path = []
    path = path + [start]
    if start == end:
        return [path]
    if start not in cfg:
        return []
    paths = []
    for succ in cfg[start]["succs"]:
        if succ not in path:
            paths.extend(find_all_paths(cfg, succ, end, path))
    return paths

def verify_dominators(cfg, entry, dominators):
    for b in cfg:
        for d in dominators[b]:
            all_paths = find_all_paths(cfg, entry, b)
            if any(d not in p for p in all_paths):
                return False
    return True

def ensure_unique_entry(cfg, entry_block, block_labels):
    external_preds = [p for p in cfg[entry_block]["preds"] if p < entry_block]
    if not external_preds:
        return entry_block
    new_block = max(cfg.keys()) + 1
    cfg[new_block] = {"succs": [entry_block], "preds": []}
    block_labels[new_block] = ".uentry"
    for p in external_preds:
        if entry_block in cfg[p]["succs"]:
            cfg[p]["succs"].remove(entry_block)
            if new_block not in cfg[p]["succs"]:
                cfg[p]["succs"].append(new_block)
    remaining = [p for p in cfg[entry_block]["preds"] if p >= entry_block]
    cfg[entry_block]["preds"] = remaining + [new_block]
    return new_block

def print_tree_viz(root, dom_tree, block_labels, prefix="", is_tail=True):
    label = block_labels.get(root, f".blk{root}")
    connector = "└── " if is_tail else "├── "
    print(prefix + connector + label)
    children = sorted(dom_tree.get(root, []))
    for i, child in enumerate(children):
        last_child = (i == len(children) - 1)
        new_prefix = prefix + ("    " if is_tail else "│   ")
        print_tree_viz(child, dom_tree, block_labels, new_prefix, last_child)

class Dominators:
    def __init__(self, cfg, entry):
        self.cfg = cfg
        self.entry = entry
        self.dominators = self.compute_full_dominators()
        self.idom = compute_idom(cfg, entry, self.dominators)
        self.dom_tree = self.build_dominator_tree()
        self.dom_frontier = self.compute_dominance_frontier()

    def compute_full_dominators(self):
        all_blocks = set(self.cfg.keys())
        dom = {b: set(all_blocks) for b in all_blocks}
        dom[self.entry] = {self.entry}
        changed = True
        while changed:
            changed = False
            for block in self.cfg:
                if block == self.entry:
                    continue
                preds = [dom[p] for p in self.cfg[block]["preds"]]
                if preds:
                    common = set.intersection(*preds)
                else:
                    common = {block}
                new_dom = {block} | common
                if new_dom != dom[block]:
                    dom[block] = new_dom
                    changed = True
        return dom

    def build_dominator_tree(self):
        tree = defaultdict(list)
        for b, parent in self.idom.items():
            if b != self.entry:
                tree[parent].append(b)
        return dict(tree)

    def compute_dominance_frontier(self):
        DF = defaultdict(set)
        tree_children = self.dom_tree
        for x in self.cfg:
            DF[x] = set()
        for x in self.cfg:
            for s in self.cfg[x]["succs"]:
                if self.idom[s] != x:
                    DF[x].add(s)
        for x in self.cfg:
            for p in self.cfg[x]["preds"]:
                if p != x and x in self.dominators[p]:
                    DF[x].add(x)
                    break
        def dfs_df(x):
            for c in tree_children.get(x, []):
                dfs_df(c)
                for y in DF[c]:
                    if self.idom[y] != x:
                        DF[x].add(y)
        dfs_df(self.entry)
        return dict(DF)

def main():
    if len(sys.argv) < 2:
        sys.exit(1)
    bril_file = sys.argv[1]
    with open(bril_file, "r") as f:
        prog = json.load(f)
    for func in prog.get("functions", []):
        blocks = form_basic_blocks(func['instrs'])
        raw_cfg = build_cfg(blocks)
        block_labels = {}
        for i, block in enumerate(blocks):
            if "label" in block[0]:
                block_labels[i] = block[0]["label"]
            else:
                block_labels[i] = f".blk{i}"
        cfg = {}
        for i in raw_cfg:
            cfg[i] = {"succs": list(raw_cfg[i]), "preds": []}
        for i, succs in raw_cfg.items():
            for s in succs:
                if s not in cfg:
                    cfg[s] = {"succs": [], "preds": []}
                cfg[s]["preds"].append(i)
        entry_block = min(cfg.keys())
        entry_block = ensure_unique_entry(cfg, entry_block, block_labels)
        doms = Dominators(cfg, entry_block)
        print("\n-- Dominator Sets -- ")
        for b in sorted(cfg.keys()):
            dom_set = sorted(doms.dominators[b])
            names = [block_labels[d] for d in dom_set]
            print(f"Block {block_labels.get(b, f'.blk{b}')}: {', '.join(names)}")
        print("\n-- Dominance Tree -- ")
        print_tree_viz(entry_block, doms.dom_tree, block_labels)
        print("\n-- Dominance Frontier --")
        for x in sorted(cfg.keys()):
            frontier = sorted(doms.dom_frontier[x])
            f_labels = [block_labels[y] for y in frontier]
            x_label = block_labels.get(x, f".blk{x}")
            print(f"{x_label}: {', '.join(f_labels) if f_labels else '∅'}")

if __name__ == "__main__":
    main()