#  Copyright (c) 2016-2018 Rocky Bernstein
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
spark grammar differences over Python 3.5 for Python 3.6.
"""
from __future__ import print_function

from uncompyle6.parser import PythonParserSingle, nop_func
from spark_parser import DEFAULT_DEBUG as PARSER_DEFAULT_DEBUG
from uncompyle6.parsers.parse35 import Python35Parser
from uncompyle6.scanners.tok import Token

class Python36Parser(Python35Parser):

    def __init__(self, debug_parser=PARSER_DEFAULT_DEBUG):
        super(Python36Parser, self).__init__(debug_parser)
        self.customized = {}


    def p_36misc(self, args):
        """
        sstmt ::= sstmt RETURN_LAST

        # 3.6 redoes how return_closure works. FIXME: Isolate to LOAD_CLOSURE
        return_closure   ::= LOAD_CLOSURE DUP_TOP STORE_NAME RETURN_VALUE RETURN_LAST

        stmt               ::= conditional_lambda
        conditional_lambda ::= expr jmp_false expr return_if_lambda
                               return_stmt_lambda LAMBDA_MARKER
        return_stmt_lambda ::= ret_expr RETURN_VALUE_LAMBDA
        return_if_lambda   ::= RETURN_END_IF_LAMBDA


        for_block       ::= l_stmts_opt come_from_loops JUMP_BACK
        come_from_loops ::= COME_FROM_LOOP*

        whilestmt       ::= SETUP_LOOP testexpr l_stmts_opt
                            JUMP_BACK come_froms POP_BLOCK COME_FROM_LOOP

        # A COME_FROM is dropped off because of JUMP-to-JUMP optimization
        and  ::= expr jmp_false expr
        and  ::= expr jmp_false expr jmp_false

        jf_cf       ::= JUMP_FORWARD COME_FROM
        conditional ::= expr jmp_false expr jf_cf expr COME_FROM

        # Adds a COME_FROM_ASYNC_WITH over 3.5
        # FIXME: remove corresponding rule for 3.5?

        except_suite ::= c_stmts_opt COME_FROM POP_EXCEPT jump_except COME_FROM

        jb_cfs      ::= JUMP_BACK come_froms
        ifelsestmtl ::= testexpr c_stmts_opt jb_cfs else_suitel

        # In 3.6+, A sequence of statements ending in a RETURN can cause
        # JUMP_FORWARD END_FINALLY to be omitted from try middle

        except_return    ::= POP_TOP POP_TOP POP_TOP returns
        except_handler   ::= JUMP_FORWARD COME_FROM_EXCEPT except_return

        # Try middle following a returns
        except_handler36 ::= COME_FROM_EXCEPT except_stmts END_FINALLY

        stmt             ::= try_except36
        try_except36     ::= SETUP_EXCEPT returns except_handler36
                             opt_come_from_except
        try_except36     ::= SETUP_EXCEPT suite_stmts

        # 3.6 omits END_FINALLY sometimes
        except_handler36 ::= COME_FROM_EXCEPT except_stmts
        except_handler   ::= jmp_abs COME_FROM_EXCEPT except_stmts

        stmt             ::= tryfinally36
        tryfinally36     ::= SETUP_FINALLY returns
                             COME_FROM_FINALLY suite_stmts
        tryfinally36     ::= SETUP_FINALLY returns
                             COME_FROM_FINALLY suite_stmts_opt END_FINALLY
        except_suite_finalize ::= SETUP_FINALLY returns
                                  COME_FROM_FINALLY suite_stmts_opt END_FINALLY _jump
        """

    def customize_grammar_rules(self, tokens, customize):
        super(Python36Parser, self).customize_grammar_rules(tokens, customize)
        self.remove_rules("""
           dict_comp ::= load_closure LOAD_DICTCOMP LOAD_CONST MAKE_CLOSURE_0 expr GET_ITER CALL_FUNCTION_1
        """)
        self.check_reduce['call_kw'] = 'AST'

        for i, token in enumerate(tokens):
            opname = token.kind

            if opname == 'FORMAT_VALUE':
                rules_str = """
                    expr ::= fstring_single
                    fstring_single ::= expr FORMAT_VALUE
                """
                self.add_unique_doc_rules(rules_str, customize)
            elif opname == 'MAKE_FUNCTION_8':
                if self.seen_LOAD_DICTCOMP:
                    # Is there something general going on here?
                    rule = """
                       dict_comp ::= load_closure LOAD_DICTCOMP LOAD_CONST
                                     MAKE_FUNCTION_8 expr
                                     GET_ITER CALL_FUNCTION_1
                       """
                    self.addRule(rule, nop_func)
                elif self.seen_LOAD_SETCOMP:
                    rule = """
                       set_comp ::= load_closure LOAD_SETCOMP LOAD_CONST
                                    MAKE_FUNCTION_8 expr
                                    GET_ITER CALL_FUNCTION_1
                       """
                    self.addRule(rule, nop_func)

            elif opname == 'BEFORE_ASYNC_WITH':
                rules_str = """
                  stmt ::= async_with_stmt
                  async_with_as_stmt ::= expr
                               BEFORE_ASYNC_WITH GET_AWAITABLE LOAD_CONST YIELD_FROM
                               SETUP_ASYNC_WITH store
                               suite_stmts_opt
                               POP_BLOCK LOAD_CONST
                               COME_FROM_ASYNC_WITH
                               WITH_CLEANUP_START
                               GET_AWAITABLE LOAD_CONST YIELD_FROM
                               WITH_CLEANUP_FINISH END_FINALLY
                 stmt ::= async_with_as_stmt
                 async_with_stmt ::= expr
                               BEFORE_ASYNC_WITH GET_AWAITABLE LOAD_CONST YIELD_FROM
                               SETUP_ASYNC_WITH POP_TOP suite_stmts_opt
                               POP_BLOCK LOAD_CONST
                               COME_FROM_ASYNC_WITH
                               WITH_CLEANUP_START
                               GET_AWAITABLE LOAD_CONST YIELD_FROM
                               WITH_CLEANUP_FINISH END_FINALLY
                """
                self.addRule(rules_str, nop_func)

            elif opname == 'BUILD_STRING':
                v = token.attr
                joined_str_n = "formatted_value_%s" % v
                rules_str = """
                    expr            ::= fstring_expr
                    fstring_expr    ::= expr FORMAT_VALUE
                    str             ::= LOAD_CONST
                    formatted_value ::= fstring_expr
                    formatted_value ::= str

                    expr                 ::= fstring_multi
                    fstring_multi        ::= joined_str BUILD_STRING
                    joined_str           ::= formatted_value+
                    fstring_multi        ::= %s BUILD_STRING
                    %s                   ::= %sBUILD_STRING
                """ % (joined_str_n, joined_str_n, "formatted_value " * v)
                self.add_unique_doc_rules(rules_str, customize)
            elif opname.startswith('BUILD_MAP_UNPACK_WITH_CALL'):
                v = token.attr
                rule = ('build_map_unpack_with_call ::= ' + 'expr1024 ' * int(v//1024) +
                        'expr32 ' * int((v//32) % 32) +
                        'expr ' * (v % 32) + opname)
                self.addRule(rule, nop_func)
            elif opname.startswith('BUILD_TUPLE_UNPACK_WITH_CALL'):
                v = token.attr
                rule = ('build_tuple_unpack_with_call ::= ' + 'expr1024 ' * int(v//1024) +
                        'expr32 ' * int((v//32) % 32) +
                        'expr ' * (v % 32) + opname)
                self.addRule(rule, nop_func)
                rule = ('starred ::= %s %s' % ('expr ' * v, opname))
                self.addRule(rule, nop_func)
            elif opname == 'SETUP_WITH':
                rules_str = """
                withstmt   ::= expr SETUP_WITH POP_TOP suite_stmts_opt POP_BLOCK LOAD_CONST
                               WITH_CLEANUP_START WITH_CLEANUP_FINISH END_FINALLY
                withstmt   ::= expr SETUP_WITH POP_TOP suite_stmts_opt COME_FROM_WITH
                               WITH_CLEANUP_START WITH_CLEANUP_FINISH END_FINALLY

                # Removes POP_BLOCK LOAD_CONST from 3.6-
                withasstmt ::= expr SETUP_WITH store suite_stmts_opt COME_FROM_WITH
                               WITH_CLEANUP_START WITH_CLEANUP_FINISH END_FINALLY
                """
                self.addRule(rules_str, nop_func)

    def custom_classfunc_rule(self, opname, token, customize,
                              possible_class_decorator,
                              seen_GET_AWAITABLE_YIELD_FROM, next_token):

        args_pos, args_kw = self.get_pos_kw(token)

        # Additional exprs for * and ** args:
        #  0 if neither
        #  1 for CALL_FUNCTION_VAR or CALL_FUNCTION_KW
        #  2 for * and ** args (CALL_FUNCTION_VAR_KW).
        # Yes, this computation based on instruction name is a little bit hoaky.
        nak = ( len(opname)-len('CALL_FUNCTION') ) // 3
        uniq_param = args_kw + args_pos

        if seen_GET_AWAITABLE_YIELD_FROM:
            rule = ('async_call ::= expr ' +
                    ('pos_arg ' * args_pos) +
                    ('kwarg ' * args_kw) +
                    'expr ' * nak + token.kind +
                    ' GET_AWAITABLE LOAD_CONST YIELD_FROM')
            self.add_unique_rule(rule, token.kind, uniq_param, customize)
            self.add_unique_rule('expr ::= async_call', token.kind, uniq_param, customize)

        if opname.startswith('CALL_FUNCTION_KW'):
            self.addRule("expr ::= call_kw36", nop_func)
            values = 'expr ' * token.attr
            rule = "call_kw36 ::= expr {values} LOAD_CONST {opname}".format(**locals())
            self.add_unique_rule(rule, token.kind, token.attr, customize)
        elif opname == 'CALL_FUNCTION_EX_KW':
            self.addRule("""expr        ::= call_ex_kw
                            expr        ::= call_ex_kw2
                            expr        ::= call_ex_kw3
                            expr        ::= call_ex_kw4

                            call_ex_kw  ::= expr expr build_map_unpack_with_call
                                            CALL_FUNCTION_EX_KW
                            call_ex_kw2 ::= expr
                                            build_tuple_unpack_with_call
                                            build_map_unpack_with_call
                                            CALL_FUNCTION_EX_KW
                            call_ex_kw3 ::= expr
                                            build_tuple_unpack_with_call
                                            expr
                                            CALL_FUNCTION_EX_KW
                            call_ex_kw4 ::= expr
                                            expr
                                            expr
                                            CALL_FUNCTION_EX_KW
                         """,
                         nop_func)
        elif opname == 'CALL_FUNCTION_EX':
            self.addRule("""
                         expr        ::= call_ex
                         starred     ::= expr
                         call_ex     ::= expr starred CALL_FUNCTION_EX
                         """, nop_func)
            if self.version > 3.6:
                self.addRule("""
                            expr        ::= call_ex_kw3
                            expr        ::= call_ex_kw
                            call_ex_kw3 ::= expr
                                            build_tuple_unpack_with_call
                                            expr
                                            CALL_FUNCTION_EX
                            call_ex_kw  ::= expr expr
                                            build_map_unpack_with_call CALL_FUNCTION_EX
                            """, nop_func)
            pass
        else:
            super(Python36Parser, self).custom_classfunc_rule(opname, token,
                                                              customize,
                                                              possible_class_decorator,
                                                              seen_GET_AWAITABLE_YIELD_FROM,
                                                              next_token)

    def reduce_is_invalid(self, rule, ast, tokens, first, last):
        invalid = super(Python36Parser,
                        self).reduce_is_invalid(rule, ast,
                                                tokens, first, last)
        if invalid:
            return invalid
        if rule[0] == 'call_kw':
            # Make sure we don't derive call_kw
            nt = ast[0]
            while not isinstance(nt, Token):
                if nt[0] == 'call_kw':
                    return True
                nt = nt[0]

        return False
class Python36ParserSingle(Python36Parser, PythonParserSingle):
    pass

if __name__ == '__main__':
    # Check grammar
    p = Python36Parser()
    p.check_grammar()
    from uncompyle6 import PYTHON_VERSION, IS_PYPY
    if PYTHON_VERSION == 3.6:
        lhs, rhs, tokens, right_recursive = p.check_sets()
        from uncompyle6.scanner import get_scanner
        s = get_scanner(PYTHON_VERSION, IS_PYPY)
        opcode_set = set(s.opc.opname).union(set(
            """JUMP_BACK CONTINUE RETURN_END_IF COME_FROM
               LOAD_GENEXPR LOAD_ASSERT LOAD_SETCOMP LOAD_DICTCOMP LOAD_CLASSNAME
               LAMBDA_MARKER RETURN_LAST
            """.split()))
        remain_tokens = set(tokens) - opcode_set
        import re
        remain_tokens = set([re.sub('_\d+$', '', t) for t in remain_tokens])
        remain_tokens = set([re.sub('_CONT$', '', t) for t in remain_tokens])
        remain_tokens = set(remain_tokens) - opcode_set
        print(remain_tokens)
        # print(sorted(p.rule2name.items()))
