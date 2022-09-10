import sys
import re

def add_indent_class(text: str) -> str:
    return text.replace('from parsival.helper_rules import *',
                        f"""
from parsival.helper_rules import *

class CustomIndent(Indent):

    @classmethod
    def indent(cls) -> parsival.Rule:
        return {sys.argv[1]}""".lstrip())

def insert_indent_class(text: str) -> str:
    return re.sub(r"parsival\s*\.\s*parse\s*\(\s*([^\)]+?)\s*,?\s*\)",
                  r"parsival.parse(\1, indent=CustomIndent)", text)

if __name__ == '__main__':
    for line in sys.stdin:
        if 'helper' in line:
            line = add_indent_class(line)
        elif 'parse' in line:
            line = insert_indent_class(line)
        print(line, end='')
