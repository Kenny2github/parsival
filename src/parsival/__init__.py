from __future__ import annotations
import re
import typing as t
from collections import defaultdict
import dataclasses
from enum import Enum
from contextlib import contextmanager

Annotations = dict[str, t.Union[t.Any, type]]

class Failed(SyntaxError):
    """Parsing using this class failed."""

class FailedToCommit(Failed):
    """Parsing failed after committing to an option."""

class Commit(Enum):
    """Commit to parsing this rule; do not try alternatives."""
    COMMIT = None # quick & easy singleton

### t.Annotated-like rules

# get_type_hints() fails when InitVar is involved without this monkeypatch
# adapted from https://stackoverflow.com/a/70430449/6605349
dataclasses.InitVar.__call__ = lambda *_: None # type: ignore

class _RuleAnnotation:
    args: tuple

    def __init__(self, *args) -> None:
        self.args = args

    def __call__(self, *args: t.Any, **kwds: t.Any) -> t.Any:
        pass

    def __repr__(self) -> str:
        return f'{type(self).__qualname__}[' + ', '.join(map(repr, self.args)) + ']'

    def __class_getitem__(cls, arg: tuple):
        return cls(*arg)

class _Regex(_RuleAnnotation):
    converter: t.Callable[[str], t.Any]
    pattern: re.Pattern[str]

    def __init__(self, converter: t.Callable[[str], t.Any],
                 pattern: str, flags: int = 0) -> None:
        super().__init__(converter, pattern, flags)
        self.converter = converter
        self.pattern = re.compile(pattern, flags)

    def __repr__(self) -> str:
        return f'parsival.Regex[{self.converter!r}, r"""{self.pattern.pattern}""", {self.pattern.flags}]'

T = t.TypeVar('T')

class _Not(_RuleAnnotation, t.Generic[T]):
    rule: T

    def __init__(self, rule: T) -> None:
        super().__init__(rule)
        self.rule = rule

    def __class_getitem__(cls, rule: T) -> _Not[T]:
        return cls(rule)

if t.TYPE_CHECKING:
    Not = t.Optional # since successful parse returns None
    Regex = t.Annotated
else:
    Not = _Not
    Regex = _Regex

SPACE = Regex[str, r'\s+']
NO_LF = Regex[str, r'[\S\n]*']
NO_SPACE = Not[SPACE]

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

    text: str
    pos: Pos = Pos(0)
    annotations_cache: dict[type, dict[str, t.Any]]
    memo: defaultdict[tuple[Rule, Pos], t.Optional[MemoEntry]]
    lr_stack: t.Optional[LR] = None
    heads: defaultdict[int, t.Optional[Head]]

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

    def __init__(self, text: str) -> None:
        self.text = text.strip()
        self.annotations_cache = {}
        # type(None) is noticeably faster than lambda: None
        self.memo = defaultdict(type(None)) # type: ignore
        self.heads = defaultdict(type(None))  # type: ignore

    def parse(self, top_level: Rule, raise_on_unconsumed: bool = True) -> AST:
        self.pos = Pos(0)
        try:
            ans = self.apply_rule(top_level, self.pos)
        except Failed as exc:
            raise SyntaxError(f'Failed to parse: {exc!s}') from exc
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

    def get_annotations(self, cls: type) -> dict[str, t.Any]:
        """Get the annotations of a class.

        Since this evaluates them, cache them for future retrieval.
        """
        if cls not in self.annotations_cache:
            self.annotations_cache[cls] = t.get_type_hints(cls, include_extras=True)
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

        if rule not in {SPACE, NO_LF}: # don't skip spaces before checking for them
            self.skip_spaces()

        if isinstance(rule, type) and issubclass(rule, Enum):
            # unpack enum values into literal
            rule = t.Literal[tuple(rule)] # type: ignore
            return self.apply_rule(rule, self.pos)

        if rule is None:
            return None

        if isinstance(rule, _Regex):
            match = rule.pattern.match(self.text, self.pos)
            if not match:
                raise Failed(f'Expecting regex r"""{rule.pattern.pattern!s}""" to match at {self.strpos}')
            self.pos = Pos(match.end())
            return rule.converter(match.group(0))

        if t.get_origin(rule) is t.Literal:
            # try each literal in turn
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

        if t.get_origin(rule) is t.Union:
            union_args = t.get_args(t.cast(t.Union, rule))
            for union_arg in union_args:
                try:
                    with self.backtrack(reraise=True):
                        return self.apply_rule(union_arg, self.pos)
                except FailedToCommit as exc:
                    raise Failed(f'Expecting {union_arg} at {self.strpos}') from exc
                except Failed:
                    pass # try next
            else:
                raise Failed(f'Expecting one of {union_args} at {self.strpos}')

        if t.get_origin(rule) is list:
            # for use in next clause
            rule = t.Annotated[rule, '*'] # type: ignore

        if t.get_origin(rule) is t.Annotated:
            rule, *args = t.get_args(rule)
            if t.get_origin(rule) is list:
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
                    try:
                        min_len = {
                            '*': 0,
                            '+': 1,
                        }[args[0]]
                    except KeyError:
                        raise TypeError('List annotation must be either * or +') from None
                else:
                    min_len = 0
                if len(values) < min_len:
                    raise Failed(f'Failed to match at least {min_len} of {rule!r} at {self.strpos}')
                return t.cast(AST, values)

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
        try:
            return self.try_rule(rule)
        except Failed as exc:
            return exc

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

def parse(text: str, top_level: t.Any, raise_on_unconsumed: bool = True) -> AST:
    return Parser(text).parse(top_level, raise_on_unconsumed)
