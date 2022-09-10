import sys
import re
from typing import Optional, Union, cast
from parsival import parse
from parsival.peg_grammar import (
    Alt, Item, Item_1, Item_2, Item_3, Item_4,
    LookaheadOrCut, LookaheadOrCut_1, LookaheadOrCut_2, LookaheadOrCut_3,
    MoreAlts, NamedItem, NamedItem_1, Plain, Plain_1, Plain_2, Plain_3, Plain_4,
    Rule, Start
)

rule_classes: dict[str, str] = {}

def snake_to_camel(s: str) -> str:
    return re.sub(r'[a-z]+(?:_|$)|[A-Z][a-z]*',
                  lambda m: m.group(0).capitalize().rstrip('_'), s)

def get_rule_name(rule: Rule) -> str:
    if rule.rulename.type:
        rulename = rule.rulename.type.type
    else:
        rulename = rule.rulename.name
    rulename = snake_to_camel(rulename)
    rule_classes[rule.rulename.name] = rulename
    return rulename

def collapse_more_alts(more_alts: Optional[MoreAlts]) -> list[Alt]:
    if more_alts is None:
        return []
    return more_alts.alts.alts + collapse_more_alts(more_alts.more_alts)

def make_annotation(name: str, item: Union[Item, LookaheadOrCut, Plain]) -> str:
    if isinstance(item, Item_1):
        name = snake_to_camel(name)
        process_rule(name, item.node.alts.alts)
        return f'Optional[{name}]'
    if isinstance(item, Item_2):
        node = item.node
        annotation = make_annotation(name, node.node)
        if node.quantifier == '?':
            return f'Optional[{annotation}]'
        if node.quantifier == '*':
            return f'list[{annotation}]'
        if node.quantifier == '+':
            return f'Annotated[list[{annotation}], "+"]'
        raise RuntimeError('Exhausted quantifiers')
    if isinstance(item, Item_3):
        sep = make_annotation(f'{name}_sep', item.node.sep)
        node = make_annotation(f'{name}_node', item.node.node)
        return f'Annotated[list[{node}], "+", {sep}]'
    if isinstance(item, Item_4):
        return make_annotation(name, item.node)
    if isinstance(item, (LookaheadOrCut_1, LookaheadOrCut_2)):
        annotation = make_annotation(name, item.atom)
        if item.type == '&':
            return f'Lookahead[{annotation}]'
        if item.type == '!':
            return f'Not[{annotation}]'
        raise RuntimeError('Exhausted lookaheads')
    if isinstance(item, LookaheadOrCut_3):
        return 'Commit'
    if isinstance(item, Plain_1):
        # fold plain rules into group annotation
        if all(len(alt.items) == 1
               and isinstance(alt.items[0].item, Item_4)
               for alt in item.atom.alts.alts):
            rulenames = [make_annotation(name, alt.items[0].item)
                         for alt in item.atom.alts.alts]
            return f'Union[{", ".join(rulenames)}]'
        name = snake_to_camel(name)
        process_rule(name, item.atom.alts.alts)
        return name
    if isinstance(item, Plain_2):
        return f'Regex[str, r"""{item.atom.pattern.string}"""]'
    if isinstance(item, Plain_3):
        try:
            return rule_classes[item.atom]
        except KeyError:
            if item.atom.upper() == item.atom: # i.e. is uppercase
                if item.atom == 'NONE':
                    return 'None'
                return item.atom # all caps items are special tokens
            raise
    if isinstance(item, Plain_4):
        return f'Literal[{item.atom.string!r}]'
    raise RuntimeError('Unreachable')

def process_item(name: str, named_item: NamedItem) -> str:
    """Returns whether the item was a literal."""
    if isinstance(named_item, NamedItem_1):
        name = named_item.name
        item = named_item.item
    else:
        item = named_item.item
    annotation = make_annotation(name, item)
    return f'    {name}: {annotation}'

def process_rule(rulename: str, alts: list[Alt]) -> None:

    if len(alts) > 1: # union time
        rulenames: list[str]
        if all(len(alt.items) == 1
               and isinstance(alt.items[0].item, Item_4)
               for alt in alts):
            rulenames = [make_annotation(f'{rulename}_{i}', alt.items[0].item)
                         for i, alt in enumerate(alts, start=1)]
        else:
            rulenames = []
            for i, alt in enumerate(alts, start=1):
                rulenames.append(f'{rulename}_{i}')
                process_rule(rulenames[-1], [alt])
        print(f'\n{rulename} = Union[{", ".join(rulenames)}]')
    else:
        alt = alts[0]
        items: list[str] = []
        for i, item in enumerate(alt.items, start=1):
            items.append(process_item(f'item_{i}', item))
        print(f"""
@dataclass
class {rulename}:
""".rstrip())
        print('\n'.join(items))

def print_header() -> None:
    print(r"""
from __future__ import annotations
from typing import Literal, Annotated, Union, Optional
from dataclasses import dataclass
from parsival import Commit
from parsival.helper_rules import *
""".strip())

def print_footer() -> None:
    start = next(iter(rule_classes.values()))
    print(r"""
if __name__ == '__main__':
    import sys
    import parsival

    text = sys.stdin.read()

    try:
        from prettyprinter import pprint, install_extras
    except ImportError:
        from pprint import pprint
    else:
        install_extras(include=frozenset({'dataclasses'}))

    try:
        parsival.DEBUG = '--debug' in sys.argv
        pprint(parsival.parse(text, %s))
    except (SyntaxError, parsival.Failed) as exc:
        print('Failed:', str(exc)[:50], file=sys.stderr)
""".rstrip() % start)


def main(text: str) -> None:
    ast: Start = cast(Start, parse(text, Start))

    print_header()

    # populate rule_classes table first
    rules: dict[str, list[Alt]] = {}
    for rule in ast.item_1.rules:
        name = get_rule_name(rule)
        alts: list[Alt] = []
        if rule.alts:
            alts.extend(rule.alts.alts)
        if rule.more_alts:
            alts.extend(collapse_more_alts(rule.more_alts))
        if name in rules:
            raise ValueError(f'Already used {name!r} class')
        else:
            rules[name] = alts

    for name, alts in reversed(rules.items()):
        process_rule(name, alts)

    print_footer()

    print('Done. You may need to manually reorder definitions in the',
          'generated module contents, to resolve unbound name errors,',
          'especially if your grammar file is not top-down.',
          file=sys.stderr, sep='\n')

def capture_main(text: str) -> str:
    import io
    from contextlib import redirect_stdout
    out = io.StringIO()
    with redirect_stdout(out):
        main(text)
    return out.getvalue()

if __name__ == '__main__':
    main(sys.stdin.read())
