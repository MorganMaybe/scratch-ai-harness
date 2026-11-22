"""Static sanity checks for the Squeak .st scripts in image/.

Checks that every top-level statement and every embedded `compile:` method
string has balanced quotes, parens, and brackets. This catches the common
causes of a modal syntax-error dialog in the headless image.
"""

from __future__ import annotations

import sys
from pathlib import Path


class Checker:
    def __init__(self, text: str, name: str, line: int = 1):
        self.text = text
        self.name = name
        self.line = line

    def scan(self) -> list[str]:
        problems: list[str] = []
        depth_paren = 0
        depth_bracket = 0
        i = 0
        line = self.line
        tokens: list[tuple[str, int]] = []
        while i < len(self.text):
            ch = self.text[i]
            if ch == "\n":
                line += 1
                i += 1
                continue
            if ch == '"':
                end = self.text.find('"', i + 1)
                if end < 0:
                    return [f"{self.name}:{line}: unterminated comment"]
                line += self.text.count("\n", i, end)
                i = end + 1
                continue
            if ch == "'":
                start_line = line
                i += 1
                while True:
                    if i >= len(self.text):
                        return [f"{self.name}:{start_line}: unterminated string"]
                    if self.text[i] == "'":
                        if i + 1 < len(self.text) and self.text[i + 1] == "'":
                            i += 2
                            continue
                        i += 1
                        break
                    if self.text[i] == "\n":
                        line += 1
                    i += 1
                continue
            if ch == "$":
                # Skip a character literal such as $) or $[ so its bracket
                # is not counted.
                i += 2
                continue
            if ch == "(":
                depth_paren += 1
                tokens.append(("(", line))
            elif ch == ")":
                depth_paren -= 1
                if depth_paren < 0:
                    problems.append(f"{self.name}:{line}: unexpected ')'")
                    depth_paren = 0
            elif ch == "[":
                depth_bracket += 1
            elif ch == "]":
                depth_bracket -= 1
                if depth_bracket < 0:
                    problems.append(f"{self.name}:{line}: unexpected ']'")
                    depth_bracket = 0
            i += 1
        if depth_paren:
            problems.append(f"{self.name}: unclosed '(' x{depth_paren}")
        if depth_bracket:
            problems.append(f"{self.name}: unclosed '[' x{depth_bracket}")
        return problems


def split_embedded(text: str) -> list[tuple[str, str, int]]:
    """Return (label, method_source, line) for each compile: '...' string."""
    results: list[tuple[str, str, int]] = []
    i = 0
    line = 1
    while i < len(text):
        ch = text[i]
        if ch == "\n":
            line += 1
            i += 1
            continue
        if ch == '"':
            end = text.find('"', i + 1)
            if end < 0:
                break
            line += text.count("\n", i, end)
            i = end + 1
            continue
        if ch == "'":
            i += 1
            while i < len(text):
                if text[i] == "'":
                    if i + 1 < len(text) and text[i + 1] == "'":
                        i += 2
                        continue
                    i += 1
                    break
                if text[i] == "\n":
                    line += 1
                i += 1
            continue
        if text.startswith("compile:", i):
            j = i + len("compile:")
            while j < len(text) and text[j] in " \t":
                j += 1
            if j < len(text) and text[j] == "'":
                start_line = line
                j += 1
                out: list[str] = []
                while j < len(text):
                    if text[j] == "'":
                        if j + 1 < len(text) and text[j + 1] == "'":
                            out.append("'")
                            j += 2
                            continue
                        j += 1
                        break
                    if text[j] == "\n":
                        line += 1
                    out.append(text[j])
                    j += 1
                method = "".join(out)
                selector = method.strip().split("\n", 1)[0].strip()
                results.append((selector, method, start_line))
                i = j
                continue
        i += 1
    return results


def main() -> int:
    paths = sys.argv[1:]
    if not paths:
        paths = [str(p) for p in sorted(Path("image").glob("*.st"))]
    failed = False
    for path in paths:
        text = Path(path).read_text(encoding="utf-8")
        print(f"== {path}")
        problems = Checker(text, path).scan()
        methods = split_embedded(text)
        for selector, method, line in methods:
            method_problems = Checker(method, f"{path}:{line} [{selector}]").scan()
            problems.extend(method_problems)
        if problems:
            failed = True
            for problem in problems:
                print("  " + problem)
        else:
            print(f"  ok ({len(methods)} embedded methods)")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
