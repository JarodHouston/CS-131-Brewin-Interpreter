from intbase import InterpreterBase, ErrorType
from brewparse import parse_program
import copy

class Interpreter(InterpreterBase):
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
        passed_args = [self.run_expr(a, self.vars) for a in args]

        self.vars.append(({k:v for k,v in zip(template_args, passed_args)}, True))
        res, _ = self.run_statements(func_def.get('statements'))
        self.vars.pop()

        return res

    def run_if(self, statement):
        cond = self.run_expr(statement.get('condition'), self.vars)

        if type(cond) != bool:
            super().error(ErrorType.TYPE_ERROR, '')

        self.vars.append(({}, False))

        res, ret = None, False

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

    def run_statements(self, statements):
        res, ret = None, False

        for statement in statements:
            kind = statement.elem_type

            if kind == 'vardef':
                self.run_vardef(statement)
            elif kind == '=':
                self.run_assign(statement)
            elif kind == 'fcall':
                self.run_fcall(statement)
            elif kind == 'if':
                res, ret = self.run_if(statement)
                if ret: break
            elif kind == 'for':
                res, ret = self.run_for(statement)
                if ret: break
            elif kind == 'return':
                res = self.run_return(statement)
                ret = True
                break

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
                    # if hasattr(scope_vars[var_name], 'elem_type'):
                    #     return self.run_expr(scope_vars[var_name])
                    if type(scope_vars[var_name]) is self.LazyExpr:
                        if scope_vars[var_name].result is None:
                            scope_vars[var_name].result = self.run_expr(scope_vars[var_name].expr, scope_vars[var_name].vars)
                        return scope_vars[var_name].result
                    return scope_vars[var_name]

                if is_func: break

            super().error(ErrorType.NAME_ERROR, '')

        elif kind == 'fcall':
            return self.run_fcall(expr)

        elif kind in self.bops:
            if kind == '&&' or kind == '||':
                l = self.run_expr(expr.get('op1'), vars)
                if type(l) == bool and kind == '&&' and not l: return False
                if type(l) == bool and kind == '||' and l: return True

                r = self.run_expr(expr.get('op2'), vars)
                if type(r) == bool and kind == '&&': return l and r
                if type(r) == bool and kind == '||': return l or r

                super().error(ErrorType.TYPE_ERROR, '')
                
            l, r = self.run_expr(expr.get('op1'), vars), self.run_expr(expr.get('op2'), vars)
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
