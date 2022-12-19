import sys
import re
from typing import TextIO

def add_indent_class(text: str, cls: str) -> str:
    return text.replace('from parsival.helper_rules import *',
                        f"""
from parsival.helper_rules import *

class CustomIndent(Indent):

    @classmethod
    def indent(cls) -> parsival.Rule:
        return {cls}""".lstrip())

def insert_indent_class(text: str) -> str:
    return re.sub(r"parsival\s*\.\s*parse\s*\(\s*([^\)]+?)\s*,?\s*\)",
                  r"parsival.parse(\1, indent=CustomIndent)", text)

def disable_indent(text: str) -> str:
    return re.sub(r"parsival\s*\.\s*parse\s*\(\s*([^\)]+?)\s*,?\s*\)",
                  r"parsival.parse(\1, indent=None)", text)

def main(file: TextIO, cls: str) -> str:
    lines: list[str] = []
    for line in file:
        if 'helper' in line:
            line = add_indent_class(line, cls)
        elif 'parse' in line:
            line = insert_indent_class(line)
        lines.append(line)
    return ''.join(lines)

def unmain(file: TextIO) -> str:
    lines: list[str] = []
    for line in file:
        if 'parse' in line:
            line = disable_indent(line)
        lines.append(line)
    return ''.join(lines)

if __name__ == '__main__':
    print(main(sys.stdin, sys.argv[1]))
