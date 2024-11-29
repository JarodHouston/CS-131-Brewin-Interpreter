from intbase import InterpreterBase, ErrorType
from brewparse import parse_program
import copy
from enum import Enum

class Interpreter(InterpreterBase):
    class Obj(Enum):
        CATCHERS = "catchers"

    class LazyExpr():
        def __init__(self, expr, vars):
            self.expr = expr
            self.vars = [(copy.copy(d), bool) for d, bool in vars]
            self.elem_type = "var"
            self.result = None
            self.captured_variables = self.get_captured_variables() # {name: val}
        
        def get_captured_variables(self):
            captured_variables = {}
            list_of_vars = self.find_vars()

            for var_name in list_of_vars:
                for scope_vars, is_func in self.vars[::-1]:
                    if var_name in scope_vars:
                        captured_variables[var_name] = scope_vars[var_name]

            return captured_variables
        
        def find_vars(self):
            expr_string = str(self.expr)
            substrings = []
            var_string = "var: name: "
            start_index = 0
            
            while True:
                # Find the next occurrence of "var" starting from start_index
                start_index = expr_string.find(var_string, start_index)
                
                if start_index == -1:
                    break  # No more "var" found, exit the loop
                start_index += len(var_string)
                
                # Find the position of the next "]" after "var"
                end_index = expr_string.find("]", start_index)
                
                if end_index == -1:
                    break  # No closing bracket found, exit the loop
                
                # Extract the substring from "var" to "]"
                substrings.append(expr_string[start_index:end_index])
                
                # Move the start_index past the current "]" to find the next "var"
                start_index = end_index + 1
            
            substrings = list(set(substrings))
            return substrings

    def __init__(self, console_output=True, inp=None, trace_output=False):
        super().__init__(console_output, inp)

        self.funcs = {} # {(name,n_args):element,}
        self.vars = [] # [({name:val,},bool),]
        self.cached_expr = {} # {(expr: LazyExpr or result)}
        self.temp = {}
        self.bops = {'+', '-', '*', '/', '==', '!=', '>', '>=', '<', '<=', '||', '&&'}
        self.BREAK_TRY = False

    def run(self, program):
        ast = parse_program(program)

        for func in ast.get('functions'):
            self.funcs[(func.get('name'),len(func.get('args')))] = func

        main_key = None

        for k in self.funcs:
            if k[0] == 'main':
                main_key = k
                break

        if main_key is None:
            super().error(ErrorType.NAME_ERROR, '')

        self.run_fcall(self.funcs[main_key])

    def run_vardef(self, statement):
        name = statement.get('name')

        if name in self.vars[-1][0]:
            super().error(ErrorType.NAME_ERROR, '')

        self.vars[-1][0][name] = None

    def run_assign(self, statement):
        name = statement.get('name')

        for scope_vars, is_func in self.vars[::-1]:
            if name in scope_vars:
                scope_vars[name] = self.LazyExpr(statement.get('expression'), self.vars)
                return

            if is_func: break

        super().error(ErrorType.NAME_ERROR, '')

    def run_fcall(self, statement):
        fcall_name, args = statement.get('name'), statement.get('args')

        if fcall_name == 'inputi' or fcall_name == 'inputs':
            if len(args) > 1:
                super().error(ErrorType.NAME_ERROR, '')

            if args:
                super().output(str(self.run_expr(args[0], self.vars)))

            res = super().get_input()

            return int(res) if fcall_name == 'inputi' else res

        if fcall_name == 'print':
            out = ''

            for arg in args:
                c_out = self.run_expr(arg, self.vars)
                if type(c_out) == tuple:
                    return c_out
                if type(c_out) == bool:
                    out += str(c_out).lower()
                else:
                    out += str(c_out)

            super().output(out)

            return None
        
        if (fcall_name, len(args)) not in self.funcs:
            super().error(ErrorType.NAME_ERROR, '')

        func_def = self.funcs[(fcall_name, len(args))]

        template_args = [a.get('name') for a in func_def.get('args')]

        passed_args = []
        for arg in args:
            arg_name = arg.get('name')
            var_found = False
            for scope_vars, is_func in self.vars[::-1]:
                if arg_name in scope_vars:
                    if type(scope_vars[arg_name]) is self.LazyExpr:
                        passed_args.append(self.run_expr(arg, scope_vars[arg_name].vars))
                    else:
                        passed_args.append(self.run_expr(arg, self.vars))
                    var_found = True
                    break
            if not var_found:
                passed_args.append(self.run_expr(arg, self.vars))
            
        # passed_args = [self.run_expr(a, self.vars) for a in args]

        self.vars.append(({k:v for k,v in zip(template_args, passed_args)}, True))
        res, _ = self.run_statements(func_def.get('statements'))
        self.vars.pop()

        return res

    def run_if(self, statement):
        res, ret = None, False
        cond = self.run_expr(statement.get('condition'), self.vars)

        if type(cond) != bool:
            if type(cond) == tuple:
                res, ret = self.handle_raise(cond)
                return res, ret
            else:
                super().error(ErrorType.TYPE_ERROR, '')

        self.vars.append(({}, False))

        if cond:
            res, ret = self.run_statements(statement.get('statements'))
        elif statement.get('else_statements'):
            res, ret = self.run_statements(statement.get('else_statements'))

        self.vars.pop()

        return res, ret

    def run_for(self, statement):
        res, ret = None, False

        self.run_assign(statement.get('init'))

        while True:
            cond = self.run_expr(statement.get('condition'), self.vars)

            if type(cond) != bool:
                if type(cond) == tuple:
                    res, ret = self.handle_raise(cond)
                    return res, ret
                else:
                    super().error(ErrorType.TYPE_ERROR, '')

            if ret or not cond: break

            self.vars.append(({}, False))
            res, ret = self.run_statements(statement.get('statements'))
            self.vars.pop()

            self.run_assign(statement.get('update'))

        return res, ret

    def run_return(self, statement):
        expr = statement.get('expression')
        if expr:
            return self.run_expr(expr, self.vars)
        return None
    
    def run_try(self, statement):
        res, ret = None, False
        catchers = statement.get('catchers')

        self.vars.append(({}, False))
        self.vars[-1][0][self.Obj.CATCHERS] = catchers

        res, ret = self.run_statements(statement.get('statements'))
        # if type(res) is tuple:
        #     self.handle_raise(res)
        #     # self.vars.pop()
        #     # (_, raise_expr) = res
        #     # for catcher in catchers:
        #     #     exception_type = catcher.get('exception_type')
        #     #     if raise_expr == exception_type:
        #     #         self.vars.append(({}, False))
        #     #         res, ret = self.run_statements(catcher.get('statements'))
        #     #         self.vars.pop()
        # else:
        #     self.vars.pop()
        # if type(res) is tuple: 
        #     print("HEREEEEE")
        #     self.handle_raise(res)

        return res, ret

    def run_raise(self, statement):
        res, ret = None, False
        res = self.run_expr(statement.get('exception_type'), self.vars)

        if type(res) != str:
            super().error(ErrorType.TYPE_ERROR, '')

        return ('RAISE', res), True
    
    def handle_raise(self, raise_ret):
        res, ret = None, False
        (_, raise_expr) = raise_ret

        idx = len(self.vars) - 1
        while idx >= 0:
            scope_vars, is_func = self.vars[idx]
            if self.Obj.CATCHERS in scope_vars:
                for catcher in scope_vars[self.Obj.CATCHERS]:
                    exception_type = catcher.get('exception_type')
                    if raise_expr == exception_type:
                        self.vars.append(({}, False))
                        res, ret = self.run_statements(catcher.get('statements'))
                        self.vars.pop()
                        idx = 0
                        self.BREAK_TRY = True
                        break
            self.vars.pop()
            idx -= 1
        if len(self.vars) == 0:
            super().error(ErrorType.FAULT_ERROR, '')
                
        return res, ret

    def run_statements(self, statements):
        res, ret = None, False

        for statement in statements:
            # if self.BREAK_TRY:
            #     self.BREAK_TRY = False
            #     break
            kind = statement.elem_type

            if kind == 'vardef':
                self.run_vardef(statement)
            elif kind == '=':
                self.run_assign(statement)
            elif kind == 'fcall':
                res = self.run_fcall(statement)
                if type(res) is tuple: 
                    res, ret = self.handle_raise(res)
                    break
            elif kind == 'if':
                res, ret = self.run_if(statement)
                if type(res) is not tuple and ret: break
            elif kind == 'for':
                res, ret = self.run_for(statement)
                if type(res) is not tuple and ret: break
            elif kind == 'return':
                res = self.run_return(statement)
                ret = True
                break
            elif kind == 'try':
                res, ret = self.run_try(statement)
                # if type(res) is tuple and ret: break
                if type(res) is not tuple and ret: break
            elif kind == 'raise':
                res, ret = self.run_raise(statement)
                break
            
            if type(res) is tuple: 
                res, ret = self.handle_raise(res)
                # break

        return res, ret

    def run_expr(self, expr, vars):
        # print("PRINTING...", vars)
        kind = expr.elem_type

        if kind == 'int' or kind == 'string' or kind == 'bool':
            return expr.get('val')

        elif kind == 'var':
            var_name = expr.get('name')

            for scope_vars, is_func in vars[::-1]:
                if var_name in scope_vars:
                    if type(scope_vars[var_name]) is self.LazyExpr:
                        if scope_vars[var_name].result is None:
                            # print(scope_vars[var_name].vars)
                            scope_vars[var_name].result = self.run_expr(scope_vars[var_name].expr, scope_vars[var_name].vars)
                        return scope_vars[var_name].result
                    return scope_vars[var_name]

                if is_func: break

            super().error(ErrorType.NAME_ERROR, '')

        elif kind == 'fcall':
            return self.run_fcall(expr)

        elif kind in self.bops:
            l = self.run_expr(expr.get('op1'), vars)
            if kind == '&&' or kind == '||':
                if type(l) == bool and kind == '&&' and not l: return False
                if type(l) == bool and kind == '||' and l: return True

            r = self.run_expr(expr.get('op2'), vars)
            if kind == '&&' or kind == '||':
                if type(r) == bool and kind == '&&': return l and r
                if type(r) == bool and kind == '||': return l or r

                super().error(ErrorType.TYPE_ERROR, '')
            if type(l) == tuple:
                return l 
            if type(r) == tuple:
                return r
            # l, r = self.run_expr(expr.get('op1'), vars), self.run_expr(expr.get('op2'), vars)
            tl, tr = type(l), type(r)

            if kind == '==': return tl == tr and l == r
            if kind == '!=': return not (tl == tr and l == r)

            if tl == str and tr == str:
                if kind == '+': return l + r

            if tl == int and tr == int:
                if kind == '+': return l + r
                if kind == '-': return l - r
                if kind == '*': return l * r
                if kind == '/': return l // r
                if kind == '<': return l < r
                if kind == '<=': return l <= r
                if kind == '>': return l > r
                if kind == '>=': return l >= r

            super().error(ErrorType.TYPE_ERROR, '')

        elif kind == 'neg':
            o = self.run_expr(expr.get('op1'), vars)
            if type(o) == int: return -o
            
            super().error(ErrorType.TYPE_ERROR, '')

        elif kind == '!':
            o = self.run_expr(expr.get('op1'), vars)
            if type(o) == bool: return not o

            super().error(ErrorType.TYPE_ERROR, '')

        return None

def main():
    interpreter = Interpreter()

    with open('./test.br', 'r') as f:
        program = f.read()

    interpreter.run(program)

if __name__ == '__main__':
    main()
