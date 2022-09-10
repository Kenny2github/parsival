from pathlib import Path
import sys
sys.path.append(str(Path(__file__).resolve().parent.parent))

import io
import argparse
from parsival.scripts.grammar_generator.gram_to_py import capture_main as gram_to_py

parser = argparse.ArgumentParser(
    description='Generate a grammar module from a grammar file.')
parser.add_argument('--postprocess', action='store_true', default=False,
                    help='Post-process the module. Currently this involves '
                    'making all anonymous items into private InitVars.')
parser.add_argument('--indent', action='store_const', const='SpaceOrTabIndent.indent()',
                    help='Use four spaces and/or a tab to indent.')
parser.add_argument('--custom-indent', metavar='RULE', dest='indent',
                    help='Use this Python expression as the indent rule.')
parser.add_argument('infile', default='-',
                    help='The grammar file to read, or - for stdin.')
parser.add_argument('outfile', default='-',
                    help='The module file to write, or - for stdout.')

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
    from parsival.scripts.grammar_generator.custom_indent import main as postprocess
    module = postprocess(io.StringIO(module), cmdargs.indent)

if cmdargs.outfile == '-':
    outfile = open(sys.stdout.fileno(), 'w', closefd=False)
else:
    outfile = open(cmdargs.outfile, 'w')
with outfile:
    outfile.write(module)
