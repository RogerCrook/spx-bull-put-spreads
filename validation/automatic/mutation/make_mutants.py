"""
Mutation testing, part 1 of 2: plant bugs in copies of the code.

What this file is for
---------------------
Method 6 of the validation measures the other tests: small bugs ("mutants") are
planted in copies of the code, and we count how many the tests catch. A test suite
that catches few planted bugs would also miss real ones.

So that nobody picks bugs the tests are known to catch, the bugs are chosen
mechanically. Python's own parser (the module ast, "abstract syntax tree") reads
each code file into a tree of its parts. This script lists every place where one of
these typical slips fits:
    comparison   <  <->  <=,   >  <->  >=,   ==  <->  !=
    arithmetic   +  <->  -,    *  <->  /     (also in +=, -=)
    number       an integer n -> n + 1,  a decimal x -> 1.1 x  (0 -> 0.1)
    text         "bid" <-> "ask",  "P" <-> "C"
    true/false   True <-> False
and draws a fixed random sample from them (seed below, so a rerun draws the same).
Each mutant is a full copy of Code/ with one change in one file. The changed file is
written back by ast.unparse, which keeps the meaning but drops the comments.

Left out, because a change there is no bug in a result: text inside print(),
f-strings, docstrings, the test `if __name__ == "__main__"`, and "+" that joins text.

The project's Code/ is only read. Everything is written into MUTATION_FOLDER.

How to run (from the main folder; seconds):
    python validation/automatic/mutation/make_mutants.py
Writes MUTATION_FOLDER/mutants/m000 (an unchanged copy, which must pass every test),
m001, m002, ..., and MUTATION_FOLDER/manifest.csv (one row per mutant: file, line,
the change, the line of code).
"""

import ast              # Python's parser: code -> tree of parts -> code
import csv              # writes the manifest
import os               # folders and paths
import random           # the fixed random sample
import shutil           # copying files
import tempfile         # the computer's temporary folder


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

MUTATION_FOLDER = os.path.join(tempfile.gettempdir(), "masterarbeit_mutation")
CODE_FOLDER = "Code"
RANDOM_SEED = 20261119

# How many mutants per file (choice): most in the backtest, the core of the thesis,
# a few in each pipeline file. s12 (runs variants), s13 and s14 (figures) are left out.
MUTANTS_PER_FILE = {
    "s11_backtest.py": 30,
    "s01_stage1_extract_simple.py": 6,
    "s03_rates.py": 6,
    "s04_forward.py": 6,
    "s05_volatility.py": 6,
    "s06_greeks.py": 6,
    "s07_stage2_greeks.py": 5,
    "s08_atm_vol.py": 6,
}

COMPARISON_SWAPS = {ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE, ast.GtE: ast.Gt,
                    ast.Eq: ast.NotEq, ast.NotEq: ast.Eq}
ARITHMETIC_SWAPS = {ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.Div, ast.Div: ast.Mult}
SYMBOL = {ast.Lt: "<", ast.LtE: "<=", ast.Gt: ">", ast.GtE: ">=", ast.Eq: "==", ast.NotEq: "!=",
          ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/"}
TEXT_SWAPS = {"bid": "ask", "ask": "bid", "P": "C", "C": "P"}


# ---------------------------------------------------------------------------
# Finding the places
# ---------------------------------------------------------------------------

def contains_text(node):
    """True if a part of the code holds a piece of text (so its "+" joins text, not numbers)."""
    for part in ast.walk(node):                    # ast.walk visits a part and everything inside it
        if isinstance(part, ast.Constant) and isinstance(part.value, str):
            return True
        if isinstance(part, ast.JoinedStr):        # an f-string
            return True
        if isinstance(part, ast.Call) and isinstance(part.func, ast.Name) and part.func.id == "str":
            return True
    return False


def is_left_out(ancestors):
    """True if a place lies inside print(), an f-string, or the __name__ test."""
    for ancestor in ancestors:
        if isinstance(ancestor, ast.Call) and isinstance(ancestor.func, ast.Name) and ancestor.func.id == "print":
            return True
        if isinstance(ancestor, ast.JoinedStr):
            return True
        if isinstance(ancestor, ast.Compare) and isinstance(ancestor.left, ast.Name) and ancestor.left.id == "__name__":
            return True
    return False


def find_places(tree):
    """
    Every place in the tree where a mutation fits, in a fixed order (the order the
    tree is walked). Each place is (kind, node, position), position = which
    operator of a chained comparison such as a < b <= c.
    """
    places = []
    # Walk the tree by hand, keeping the list of parts above each part ("ancestors").
    stack = [(tree, [])]                           # (part, the parts above it)
    while len(stack) > 0:
        node, ancestors = stack.pop()
        if not is_left_out(ancestors + [node]):
            if isinstance(node, ast.Compare):
                for position in range(len(node.ops)):
                    if type(node.ops[position]) in COMPARISON_SWAPS:
                        places.append(("comparison", node, position))
            elif isinstance(node, ast.BinOp) and type(node.op) in ARITHMETIC_SWAPS:
                if not (contains_text(node.left) or contains_text(node.right)):
                    places.append(("arithmetic", node, 0))
            elif isinstance(node, ast.AugAssign) and type(node.op) in ARITHMETIC_SWAPS:
                if not contains_text(node.value):
                    places.append(("arithmetic", node, 0))
            elif isinstance(node, ast.Constant):
                is_docstring = False                # a bare text on its own line is a docstring
                if len(ancestors) > 0 and isinstance(ancestors[-1], ast.Expr):
                    is_docstring = True
                if isinstance(node.value, bool):
                    places.append(("true/false", node, 0))
                elif isinstance(node.value, (int, float)) and not is_docstring:
                    places.append(("number", node, 0))
                elif isinstance(node.value, str) and node.value in TEXT_SWAPS and not is_docstring:
                    places.append(("text", node, 0))
        # Put the parts inside this one on the stack, last first, so they come out in order.
        children = list(ast.iter_child_nodes(node))
        children.reverse()
        for child in children:
            stack.append((child, ancestors + [node]))
    return places


def mutate(place):
    """Change the code at one place, in the tree itself. Returns the change in words."""
    kind, node, position = place
    if kind == "comparison":
        old = type(node.ops[position])
        new = COMPARISON_SWAPS[old]
        node.ops[position] = new()
        return SYMBOL[old] + " -> " + SYMBOL[new]
    if kind == "arithmetic":
        old = type(node.op)
        new = ARITHMETIC_SWAPS[old]
        node.op = new()
        return SYMBOL[old] + " -> " + SYMBOL[new]
    if kind == "number":
        old = node.value
        if isinstance(old, int):
            node.value = old + 1
        elif old == 0:
            node.value = 0.1
        else:
            node.value = old * 1.1
        return repr(old) + " -> " + repr(node.value)
    if kind == "text":
        old = node.value
        node.value = TEXT_SWAPS[old]
        return '"' + old + '" -> "' + node.value + '"'
    if kind == "true/false":
        old = node.value
        node.value = not old
        return repr(old) + " -> " + repr(node.value)
    raise ValueError("unknown kind " + kind)


# ---------------------------------------------------------------------------
# Writing the mutants
# ---------------------------------------------------------------------------

def copy_code(target):
    """Copy every .py file of the project's Code/ into target."""
    os.makedirs(target)
    for name in sorted(os.listdir(CODE_FOLDER)):
        if name.endswith(".py"):
            shutil.copy(os.path.join(CODE_FOLDER, name), target)


def main():
    if os.path.exists(MUTATION_FOLDER):
        raise ValueError(MUTATION_FOLDER + " exists already: delete it first")
    mutants_folder = os.path.join(MUTATION_FOLDER, "mutants")
    generator = random.Random(RANDOM_SEED)         # its own random numbers, fixed by the seed

    # m000: the unchanged code. It must pass every test, or the harness is wrong.
    copy_code(os.path.join(mutants_folder, "m000", "Code"))
    manifest = [{"mutant": "m000", "file": "", "line": "", "kind": "none", "change": "unchanged code", "code": ""}]

    number = 0
    for file_name in sorted(MUTANTS_PER_FILE):
        path = os.path.join(CODE_FOLDER, file_name)
        source = open(path, encoding="utf-8").read()
        source_lines = source.splitlines()
        places = find_places(ast.parse(source))
        how_many = min(MUTANTS_PER_FILE[file_name], len(places))
        chosen = generator.sample(range(len(places)), how_many)   # distinct positions in the list
        chosen.sort()
        print(file_name + ": " + str(len(places)) + " places, " + str(how_many) + " mutants")

        for index in chosen:
            number = number + 1
            name = "m" + str(number).zfill(3)
            tree = ast.parse(source)                # a fresh tree for each mutant
            place = find_places(tree)[index]        # the same place, found again in the fresh tree
            line = place[1].lineno
            change = mutate(place)
            new_source = ast.unparse(tree)          # the tree back into code (comments are lost)
            compile(new_source, file_name, "exec")  # make sure the mutant is valid Python

            code_folder = os.path.join(mutants_folder, name, "Code")
            copy_code(code_folder)
            with open(os.path.join(code_folder, file_name), "w", encoding="utf-8") as file:
                file.write(new_source)
            manifest.append({"mutant": name, "file": file_name, "line": line, "kind": place[0],
                             "change": change, "code": source_lines[line - 1].strip()})

    with open(os.path.join(MUTATION_FOLDER, "manifest.csv"), "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["mutant", "file", "line", "kind", "change", "code"])
        writer.writeheader()
        for row in manifest:
            writer.writerow(row)
    print("wrote " + str(number) + " mutants and the unchanged copy m000 to " + mutants_folder)


main()
