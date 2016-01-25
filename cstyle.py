#!/usr/bin/env python2
"""CStyle Checker based on libclang"""

import argparse
import ConfigParser
import clang.cindex
import os
import re
import sys

class CStyle(object):
    """CStyle checker"""
    def __init__(self, Options, RulesDB, Files):
        self.Options = Options
        self.RulesDB = RulesDB
        self.Files = Files
        self._NReturns = 0

    def Invalid(self, Node):
        """Check if Node is invalid."""
        Invalid = False
        Reason = ''
        Local = Node.location.file and Node.location.file.name in self.Files
        if not Local:
            return Invalid, Reason

        Name = Node.spelling
        if (self.Options['pointer_prefix'] and
            (Node.kind == clang.cindex.CursorKind.VAR_DECL or
             Node.kind == clang.cindex.CursorKind.PARM_DECL) and
            Node.type and Node.type.spelling.count('*') > 0):
            Prefix = self.Options['pointer_prefix']
            Type = Node.type.spelling
            Invalid = not Name.startswith(Prefix * Type.count('*'))
            if Invalid:
                Reason = 'Expected pointer prefix "{Prefix}"'.format(
                    Prefix=Prefix * Type.count('*'))
            else:
                # strip n prefix chars
                Name = Name[Type.count('*'):]

        if self.Options['prefer_goto']:
            if Node.kind == clang.cindex.CursorKind.FUNCTION_DECL:
                self._NReturns = 0
            elif Node.kind == clang.cindex.CursorKind.RETURN_STMT:
                self._NReturns = self._NReturns + 1
            Invalid = self._NReturns > 1
            if Invalid:
                Reason = 'Only 1 return statement per function (prefer_goto)'
        else:
            Invalid = (Node.kind == clang.cindex.CursorKind.GOTO_STMT)
            if Invalid:
                Reason = 'goto considered harmful'

        if not Invalid:
            Invalid = (Node.kind in self.RulesDB and
                       not self.RulesDB[Node.kind].match(Name))
            if Invalid:
                Reason = 'Failed regexp check "{Regex}"'.format(
                    Regex=self.RulesDB[Node.kind].pattern)
        return Invalid, Reason

    def CheckStyle(self):
        """Check Files against RulesDB and report violations to stderr"""
        for File in self.Files:
            Index = clang.cindex.Index.create()
            Unit = Index.parse(File)
            InvalidNodes = []
            for Node in Unit.cursor.walk_preorder():
                Invalid, Reason = self.Invalid(Node)
                if Invalid:
                    InvalidNodes.append((Node, Reason))

            for (Node, Reason) in InvalidNodes:
                sys.stderr.write(('{File}:{Line}:{Column}: "{Name}" '
                                  'is invalid: {Reason})\n').
                                 format(File=Node.location.file.name,
                                        Line=Node.location.line,
                                        Column=Node.location.column,
                                        Name=Node.spelling,
                                        Reason=Reason))
        return 1 if InvalidNodes else 0

def ConfigSection(Config, Section, Defaults={}):
    """Create a dict from a Section of Config"""
    Dict = Defaults
    for (Name, Value) in Config.items(Section):
        Dict[Name] = Value
    return Dict

def Main():
    """Run cstyle.py"""
    Status = 0
    Parser = argparse.ArgumentParser(description='C Style Checker')
    Parser.add_argument('--config', dest='config',
                        default=os.path.expanduser('~/.cstyle'),
                        help='configuration file')
    Parser.add_argument('FILES', metavar='FILE', nargs='+',
                        help='files to check')
    Args = Parser.parse_args()
    Config = ConfigParser.ConfigParser()
    Config.read(Args.config)
    Options = ConfigSection(Config, 'Options',
                            {'pointer_prefix': None,
                             'prefer_goto': False})
    Rules = ConfigSection(Config, 'Rules')

    Kinds = {Kind.name.lower(): Kind for Kind in clang.cindex.CursorKind.get_all_kinds()}
    RulesDB = {Kinds[Kind]: re.compile(Pattern) for (Kind, Pattern) in Rules.items()}
    Status = CStyle(Options, RulesDB, Args.FILES).CheckStyle()
    sys.exit(Status)

if __name__ == '__main__':
    Main()
