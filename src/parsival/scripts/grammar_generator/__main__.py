import sys
import io
import argparse
from parsival.scripts.grammar_generator.gram_to_py import capture_main as gram_to_py

parser = argparse.ArgumentParser(
    description='Generate a grammar module from a grammar file.')
parser.add_argument('--no-postprocess', action='store_false', default=True,
                    help='Do not post-process the module. Currently post-'
                    'processing involves making all anonymous items into '
                    'private InitVars, and converting Unions of single-arg '
                    'Literals to multi-arg Literals.')
parser.add_argument('--indent', action='store_const', const='SpaceOrTabIndent.indent()',
                    help='Use four spaces and/or a tab to indent.')
parser.add_argument('--custom-indent', metavar='RULE', dest='indent',
                    help='Use this Python expression as the indent rule.')
parser.add_argument('--no-indent', action='store_const', const=None,
                    dest='indent', help='Do not use an indent rule.')
parser.add_argument('infile', default='-',
                    help='The grammar file to read, or - for stdin.')
parser.add_argument('outfile', default='-',
                    help='The module file to write, or - for stdout.')

def main():
    cmdargs = parser.parse_args()

    if cmdargs.infile == '-':
        infile = open(sys.stdin.fileno(), 'r', closefd=False)
    else:
        infile = open(cmdargs.infile, 'r')
    with infile:
        grammar = infile.read()

    module = gram_to_py(grammar)
    if cmdargs.postprocess:
        from parsival.scripts.grammar_generator.postprocess import main as postprocess
        module = postprocess(io.StringIO(module))
    if cmdargs.indent:
        from parsival.scripts.grammar_generator.custom_indent import main as custom_indent
        module = custom_indent(io.StringIO(module), cmdargs.indent)
    elif cmdargs.indent is None:
        from parsival.scripts.grammar_generator.custom_indent import unmain as remove_indent
        module = remove_indent(io.StringIO(module))

    if cmdargs.outfile == '-':
        outfile = open(sys.stdout.fileno(), 'w', closefd=False)
    else:
        outfile = open(cmdargs.outfile, 'w')
    with outfile:
        outfile.write(module)

if __name__ == '__main__':
    main()
