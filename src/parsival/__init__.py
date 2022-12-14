from __future__ import annotations
import re
import sys
import typing as t
from collections import defaultdict
import dataclasses
from enum import Enum
from contextlib import contextmanager

from .helper_rules import (
    _Regex, _Not, _Lookahead, SPACE, NO_LF_SPACE, NEWLINE,
    Indent, INDENT, DEDENT, SpaceOrTabIndent
)

__all__ = [
    'parse',
    'Failed',
    'Commit',
    'Here',
    'Rule',
    'AST',
    'Parser',
]

__version__ = '0.0.0a1'

DEBUG: bool = False

Annotations = dict[str, t.Union[t.Any, type]]

class Failed(SyntaxError):
    """Parsing using this class failed."""

class FailedToCommit(Failed):
    """Parsing failed after committing to an option."""

class Commit(Enum):
    """Commit to parsing this rule; do not try alternatives."""
    COMMIT = None # quick & easy singleton

class Here(Enum):
    """Apply the annotated rule here; discard all other tuple elements."""
    HERE = None

### t.Annotated-like rules

# get_type_hints() fails when InitVar is involved without this monkeypatch
# adapted from https://stackoverflow.com/a/70430449/6605349
dataclasses.InitVar.__call__ = lambda *_: None # type: ignore

### Packrat memoization data types

_AST = t.NewType('_AST', object)
AST = t.Optional[_AST]
AST_F = t.Union[AST, Failed]
_Rule = t.NewType('_Rule', object)
Rule = t.Union[type, _Rule, None]
Pos = t.NewType('Pos', int)

@dataclasses.dataclass
class MemoEntry:
    ans: t.Union[AST, LR, Failed]
    pos: Pos

@dataclasses.dataclass
class LR:
    seed: AST_F
    rule: Rule
    head: t.Optional[Head]
    next: t.Optional[LR]

@dataclasses.dataclass
class Head:
    rule: Rule
    involved: set[Rule]
    eval: set[Rule]

class Parser:

    # basic attributes
    text: str
    pos: Pos = Pos(0)
    # my own cache, to avoid repeated get_type_hints() calls
    annotations_cache: dict[type, dict[str, t.Any]]
    # data for packrat memoization
    memo: defaultdict[tuple[Rule, Pos], t.Optional[MemoEntry]]
    lr_stack: t.Optional[LR] = None
    heads: defaultdict[int, t.Optional[Head]]
    # indentation mechanics
    indent_skips: dict[Pos, Pos]
    indent_positions: dict[Pos, type[t.Union[INDENT, DEDENT]]]
    skipping_spaces: bool = True

    @property
    def lineno(self) -> int:
        return len(self.text[:self.pos].split('\n'))
    @property
    def colno(self) -> int:
        m = list(re.compile('^', re.M).finditer(self.text, 0, self.pos))[-1]
        return self.pos - m.start() + 1
    @property
    def strpos(self) -> str:
        return f'line {self.lineno} col {self.colno}'

    def __init__(self, text: str, indent: t.Optional[type[Indent]] = None) -> None:
        self.text = text
        self.annotations_cache = {}
        self.indent_skips = {}
        self.indent_positions = {}
        # type(None) is noticeably faster than lambda: None
        self.memo = defaultdict(type(None)) # type: ignore
        self.heads = defaultdict(type(None)) # type: ignore
        if indent is not None:
            self.generate_indents(indent)
            self.memo.clear()
            self.heads.clear()
            self.lr_stack = None
            if DEBUG:
                print(' Generated indents '.center(79, '-'), file=sys.stderr)

    def parse(self, top_level: Rule, raise_on_unconsumed: bool = True) -> AST:
        self.pos = Pos(0)
        try:
            ans = self.apply_rule(top_level, self.pos)
        except Failed as exc:
            raise SyntaxError(f'Failed to parse: {exc!s}') from exc
        self.skip_spaces()
        if raise_on_unconsumed and self.pos < len(self.text):
            raise SyntaxError(f'Data remains after parse: {self.text[self.pos:]!r}')
        return ans

    @contextmanager
    def backtrack(self, *, reraise: bool = False):
        start = self.pos
        try:
            yield start
        except Failed:
            self.pos = start
            if reraise:
                raise

    @contextmanager
    def no_skip_spaces(self):
        try:
            self.skipping_spaces = False
            yield
        finally:
            self.skipping_spaces = True

    def generate_indents(self, indent: type[Indent]) -> None:
        self.pos = Pos(0)
        current_indent = 0
        for match in re.finditer('^', self.text, re.M):
            start = self.pos = Pos(match.start())
            with self.backtrack(), self.no_skip_spaces():
                indent_count = 0
                while 1:
                    try:
                        with self.backtrack(reraise=True):
                            self.apply_rule(indent.indent(), self.pos)
                    except Failed:
                        break
                    else:
                        indent_count += 1
                if indent_count > current_indent:
                    self.indent_positions[start] = INDENT
                elif indent_count < current_indent:
                    self.indent_positions[start] = DEDENT
                current_indent = indent_count
                if self.pos != start:
                    self.indent_skips[start] = self.pos

    def get_annotations(self, cls: type) -> dict[str, t.Any]:
        """Get the annotations of a class.

        Since this evaluates them, cache them for future retrieval.
        """
        if cls not in self.annotations_cache:
            self.annotations_cache[cls] = t.get_type_hints(
                cls.__init__, include_extras=True)
            # "return" may be in annotations but is never
            # a valid attribute name
            self.annotations_cache[cls].pop('return', '')
        return self.annotations_cache[cls]

    def get_annotation(self, cls: type, attr: str) -> t.Any:
        return self.get_annotations(cls)[attr]

    def skip_spaces(self) -> None:
        space_match = re.compile(r'\s*').match(self.text, self.pos)
        if space_match is not None:
            self.pos = Pos(space_match.end())

    def unpeel_initvar(self, rule: Rule) -> Rule:
        if isinstance(rule, dataclasses.InitVar):
            return rule.type
        return rule

    def try_rule(self, rule: Rule) -> AST:
        rule = self.unpeel_initvar(rule)

        try:
            # process indents before skipping them
            if rule is INDENT:
                if self.indent_positions.get(self.pos) is not INDENT:
                    raise Failed(f'Expected indent at {self.strpos}')
                return INDENT.INDENT  # type: ignore

            if rule is DEDENT:
                if self.indent_positions.get(self.pos) is not DEDENT:
                    raise Failed(f'Expected dedent at {self.strpos}')
                return DEDENT.DEDENT  # type: ignore
        finally:
            self.pos = self.indent_skips.get(self.pos, self.pos)

        if isinstance(rule, str):
            raise TypeError(f'{rule!r} is not a valid rule. '
                            f'Did you mean Literal[{rule!r}]?')

        if isinstance(rule, _Not):
            # Not might check against spaces, so check before skipping them.
            # If rule.rule isn't SPACE, they will get skipped later.
            rule = rule.rule
            try:
                self.apply_rule(rule, self.pos)
            except Failed:
                return None
            else:
                raise Failed(f'Expected not to parse {rule!r} at {self.strpos}')

        if isinstance(rule, _Lookahead):
            # Same note as for Not
            rule = rule.rule
            start = self.pos
            try:
                return self.apply_rule(rule, self.pos)
            finally:
                self.pos = start

        # don't skip spaces before a none match (to prevent changing position)
        if rule is None or rule is type(None):
            return None

        # check union before skipping spaces,
        # so that each individual rule can decide whether to skip or not
        if t.get_origin(rule) is t.Union:
            union_args = t.get_args(t.cast(t.Union, rule))
            for union_arg in union_args:
                try:
                    with self.backtrack(reraise=True):
                        return self.apply_rule(union_arg, self.pos)
                except FailedToCommit as exc:
                    raise Failed(
                        f'Expecting {union_arg} at {self.strpos}') from exc
                except Failed:
                    pass  # try next
            else:
                raise Failed(f'Expecting one of {union_args} at {self.strpos}')

        ## ALL RULES BEFORE THIS LINE HAVE REASON TO BE CHECKED BEFORE SKIPPING SPACES ##

        # don't skip spaces before checking for them
        if self.skipping_spaces:
            if not (isinstance(rule, type) and issubclass(rule, (
                    SPACE, NO_LF_SPACE, NEWLINE))):
                self.skip_spaces()
            else:
                rule = self.get_annotation(rule, 'text')
        elif isinstance(rule, type) and issubclass(rule, (
                SPACE, NO_LF_SPACE, NEWLINE)):
            # still need to extract the rule itself
            rule = self.get_annotation(rule, 'text')

        ## ALL RULES AFTER THIS LINE WILL HAVE SPACES ALREADY SKIPPED ##

        if isinstance(rule, type) and issubclass(rule, Enum):
            # unpack enum values into literal
            rule = t.Literal[tuple(rule)] # type: ignore
            return self.apply_rule(rule, self.pos)

        if isinstance(rule, _Regex):
            match = rule.pattern.match(self.text, self.pos)
            if not match:
                raise Failed(f'Expected regex r"""{rule.pattern.pattern!s}""" to match at {self.strpos}')
            self.pos = Pos(match.end())
            return t.cast(AST, match.group(0))

        if t.get_origin(rule) is t.Literal:
            # try each literal in turn
            if t.TYPE_CHECKING:
                rule = t.cast(type[t.Literal], rule)
            literal_values: tuple[str, ...] = t.get_args(rule)
            for literal_value in literal_values:
                result = literal_value  # so that we return the enum object
                if isinstance(literal_value, Enum):
                    # use the enum value for startswith() check
                    literal_value = literal_value.value
                if self.text.startswith(literal_value, self.pos):
                    self.pos = Pos(self.pos + len(literal_value))
                    return result
            else:
                raise Failed(
                    f'Expecting one of {literal_values} at {self.strpos}')

        if t.get_origin(rule) is list:
            # for use in next clause
            rule = t.Annotated[rule, '*'] # type: ignore

        if t.get_origin(rule) is t.Annotated:
            rule, *args = t.get_args(rule)
            if t.get_origin(rule) is list and args[0] in {'*', '+'}:
                # potentially multiple of the argument
                rule, = t.get_args(rule) # rule is now the rule to repeat
                values: list[t.Any] = []
                while 1:
                    try:
                        with self.backtrack(reraise=True):
                            value = self.apply_rule(rule, self.pos)
                    except Failed:
                        break
                    values.append(value)
                    if len(args) >= 2:
                        try:
                            with self.backtrack(reraise=True):
                                self.apply_rule(args[1], self.pos)
                        except Failed:
                            break
                if len(args) >= 1:
                    min_len = {
                        '*': 0,
                        '+': 1,
                    }[args[0]]
                else:
                    min_len = 0
                if len(values) < min_len:
                    raise Failed(f'Failed to match at least {min_len} of {rule!r} at {self.strpos}')
                return t.cast(AST, values)
            elif t.get_origin(args[0]) is tuple:
                # ordered sequence of rules, of which one is captured
                value = None
                here_found = False
                committed = False
                for annotation in t.get_args(args[0]):
                    if self.unpeel_initvar(annotation) is Commit:
                        committed = True
                        continue
                    if annotation is Here and here_found:
                        raise TypeError('Only allowed one Here per tuple annotation')
                    try:
                        if annotation is Here:
                            value = self.apply_rule(rule, self.pos)
                            here_found = True
                        else:
                            self.apply_rule(annotation, self.pos)
                    except Failed as exc:
                        if committed:
                            raise FailedToCommit(str(exc)) from exc
                        else:
                            raise
                if not here_found:
                    raise TypeError('Must have a Here in the tuple annotation')
                return value

        rule = t.cast(type, rule)
        kwargs: dict[str, t.Any] = {}
        committed = False
        for name, annotation in self.get_annotations(rule).items():
            if self.unpeel_initvar(annotation) is Commit:
                committed = True
                kwargs[name] = Commit.COMMIT
                continue
            try:
                kwargs[name] = self.apply_rule(annotation, self.pos)
            except Failed as exc:
                if committed:
                    raise FailedToCommit(str(exc)) from exc
                else:
                    raise
        return rule(**kwargs)

    def eval_(self, rule: Rule) -> AST_F:
        if DEBUG:
            print(f'{self.strpos}: Trying {rule!r}', file=sys.stderr)
        try:
            ans = self.try_rule(rule)
        except Failed as exc:
            if DEBUG:
                print(f'{self.strpos}: Failure of {rule!r}\n\t{exc!s}', file=sys.stderr)
            return exc
        else:
            if DEBUG:
                print(f'{self.strpos}: Success with {rule!r}\n\t{ans!r}', file=sys.stderr)
        return ans

    def apply_rule(self, rule: Rule, pos: Pos) -> AST:
        ans = self.apply_rule_inner(rule, pos)
        if isinstance(ans, Failed):
            raise ans
        return ans

    # The following functions are adapted from
    # http://web.cs.ucla.edu/~todd/research/pepm08.pdf

    def apply_rule_inner(self, rule: Rule, pos: Pos
                         ) -> AST_F:
        """Packrat parse with memoize.

        Args:
            rule: The rule (class, etc) to parse.
            pos: The position to start parsing from.

        Returns:

        """
        m = self.recall(rule, pos)
        if m is None:
            # Create a new LR and push onto the rule invocation stack.
            lr = LR(Failed('Invalid parser state 1'), rule, None, self.lr_stack)
            self.lr_stack = lr
            # Memoize lr, then evaluate rule.
            m = MemoEntry(lr, pos)
            self.memo[rule, pos] = m

            ans = self.eval_(rule)
            # Pop lr off the rule invocation stack.
            self.lr_stack = self.lr_stack.next
            m.pos = self.pos

            if lr.head is not None:
                lr.seed = ans
                return self.lr_answer(rule, pos, m)
            else:
                m.ans = ans
                return ans
        else:
            self.pos = m.pos
            if isinstance(m.ans, LR):
                self.setup_lr(rule, m.ans)
                return m.ans.seed
            else:
                return m.ans

    def setup_lr(self, rule: Rule, lr: LR) -> None:
        if lr.head is None:
            lr.head = Head(rule, set(), set())
        stack = self.lr_stack
        while stack is not None and stack.head != lr.head:
            stack.head = lr.head
            lr.head.involved |= {stack.rule}
            stack = stack.next

    def lr_answer(self, rule: Rule, pos: Pos, m: MemoEntry) -> AST_F:
        assert isinstance(m.ans, LR) # guaranteed at callsite
        assert m.ans.head is not None # guaranteed at callsite
        head = m.ans.head
        if head.rule != rule:
            return m.ans.seed
        else:
            m.ans = m.ans.seed
            if isinstance(m.ans, Failed):
                return m.ans
            else:
                return self.grow_lr(rule, pos, m, head)

    def recall(self, rule: Rule, pos: Pos) -> t.Optional[MemoEntry]:
        m = self.memo[rule, pos]
        head = self.heads[pos]
        # If not growing a seed parse, just return what is stored
        # in the memo table.
        if head is None:
            return m
        # Do not evaluate any rule that is not involved in this left recursion.
        if m is None and rule not in ({head.rule} | head.involved):
            return MemoEntry(Failed('Invalid parser state 2'), pos)
        # Allow involved rules to be evaluated, but only once,
        # during a seed-growing iteration.
        if rule in head.eval:
            head.eval.remove(rule)
            ans = self.eval_(rule)
            if m is None:
                m = MemoEntry(Failed('Invalid parser state 3'), Pos(0))
            m.ans = ans
            m.pos = self.pos
        return m

    def grow_lr(self, rule: Rule, pos: Pos, m: MemoEntry, head: Head) -> AST_F:
        assert not isinstance(m.ans, LR) # guaranteed at callsite
        self.heads[pos] = head
        while True:
            self.pos = pos
            head.eval = head.involved.copy()
            ans = self.eval_(rule)
            if isinstance(ans, Failed) or self.pos <= m.pos:
                break
            m.ans = ans
            m.pos = self.pos
        self.heads[pos] = None
        self.pos = m.pos
        return m.ans

def parse(
    text: str,
    top_level: t.Any,
    *,
    raise_on_unconsumed: bool = True,
    indent: t.Optional[type[Indent]] = SpaceOrTabIndent
) -> AST:
    return Parser(text, indent=indent).parse(top_level, raise_on_unconsumed)
