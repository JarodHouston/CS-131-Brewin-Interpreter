from intbase import InterpreterBase
from intbase import ErrorType
from brewparse import parse_program

class Interpreter(InterpreterBase):
    def __init__(self, console_output=True, inp=None, trace_output=False):
        super().__init__(console_output, inp)   # call InterpreterBase's constructor
        self.trace_output = trace_output
        self.bin_ops = ["+", "-", "*", "/"]
        self.bin_bool_ops = ["&&", "||"]
        self.comp_ops = ["==", "!=", ">", "<", ">=", "<="]
        self.unary_ops = ["neg", "!"]

    def run(self, program):
        ast = parse_program(program)
        # Stack of scopes, dictionary with key: tuple (function name, nesting level), value: (list of variables in current scope)
        # key: function name, value: hash map? where you have the key be variable name and value be the value of the variable
        # Okay, try a stack of stacks when implementing functions/recursions
        self.stack = []

        self.func_list = self.get_func_list(ast)
        main_func_node = next((value for key, value in self.func_list.items() if key[0] == "main"), None)
        if not main_func_node:
            super().error(
                ErrorType.NAME_ERROR,
                "No main() function was found",
            )
        
        self.run_func(main_func_node, main_func_node.get("args"))
    
    def get_func_list(self, ast):
        func_list = {}
        for function in ast.get("functions"):
            func_list[(function.get("name"), len(function.get("args")))] = function
        return func_list

    def run_func(self, func_node, call_arguments):
        list_to_append = [{}]
        # for arg in call_arguments:
        #     print(arg)
        # print(self.stack)
        func_args = func_node.get("args")
        for i in range(len(func_args)):
            var_name = func_args[i].get("name")
            list_to_append[0][var_name] = self.evaluate_expression(call_arguments[i])
            # self.stack[-1][-1][var_name] = self.evaluate_expression(call_arguments[i])
        self.stack.append(list_to_append)
        # for arg in func_args:
        #     for scope in reversed(self.stack[-2]):
        #         var_name = arg.get("name")
        #         if scope.get(var_name):
        #             self.stack[-1][-1][var_name] = scope[var_name]
        self.stack[-1].append({})
        statements = func_node.get("statements")
        result = None
        # for s in statements:
        #     if s.elem_type == "return":
        #         result = self.do_return_statement(s)
        #         break
        stack_length = len(self.stack)
        result = self.run_statements(statements)
        # print(self.stack)
        if len(self.stack) == stack_length:
            self.stack.pop()

        return result

    def run_statements(self, statements):
        stack_length = len(self.stack)
        for statement in statements:
            result = None
            if statement.elem_type == "vardef":
                self.do_definition(statement)
            elif statement.elem_type == "=":
                self.do_assignment(statement)
            elif statement.elem_type == "fcall":
                result = self.do_func_call(statement)              
            elif statement.elem_type == "if":
                result = self.do_if_statement(statement)
            elif statement.elem_type == "for":
                result = self.do_for_loop(statement)
            elif statement.elem_type == "return":
                print(self.stack)
                result = self.do_return_statement(statement)
                self.stack.pop()
                return result
            
            if len(self.stack) < stack_length:
                return result
    
    def do_definition(self, definition):
        var_name = definition.get("name")
        if var_name in self.stack[-1][-1]:
            super().error(
                ErrorType.NAME_ERROR,
                f"Variable {var_name} defined more than once",
            )
        else:
            self.stack[-1][-1][var_name] = None
    
    def do_assignment(self, assignment):
        var_name = assignment.get("name")
        scope = self.get_scope(var_name)
        if scope:
        # if var_name not in self.stack[-1][self.curr_func]:
        #     super().error(
        #         ErrorType.NAME_ERROR,
        #         f"Variable {var_name} has not been defined",
        #     )
        # else:
            expression = assignment.get("expression")
            expression_result = self.evaluate_expression(expression)
            scope[var_name] = expression_result

    def evaluate_expression(self, expression):
        exp_type = expression.elem_type

        # Handles expression node as operators
        if exp_type in self.bin_ops or exp_type in self.bin_bool_ops or exp_type in self.comp_ops:
            op1 = expression.get("op1")
            op2 = expression.get("op2")

            val1 = self.get_exp_value(op1)
            val2 = self.get_exp_value(op2)
            
            if self.is_not_type_valid_op(exp_type, val1, val2):
                super().error(
                    ErrorType.TYPE_ERROR,
                    "Incompatible types for arithmetic operation",
                )

            if exp_type == "&&": return val1 and val2
            if exp_type == "||": return val1 or val2

            if exp_type == "==": return val1 == val2
            if exp_type == "!=": return val1 != val2
            if exp_type == ">": return val1 > val2
            if exp_type == "<": return val1 < val2
            if exp_type == ">=": return val1 >= val2
            if exp_type == "<=": return val1 <= val2

            if exp_type == "+": return val1 + val2
            if exp_type == "-": return val1 - val2
            if exp_type == "*": return val1 * val2
            if exp_type == "/": return int(val1 / val2)

            return "Error in evaluating expression"
        
        if exp_type in self.unary_ops:
            op1 = expression.get("op1")
            val1 = self.get_exp_value(op1)
            
            if self.is_not_type_valid_unary_op(exp_type, val1):
                super().error(
                    ErrorType.TYPE_ERROR,
                    "Incompatible types for arithmetic operation",
                )
            
            if exp_type == "neg": return val1 * -1
            if val1 is False: return True
            return False
        
        # Handles evaluating assignment to value
        if exp_type == "int" or exp_type == "string" or exp_type == "bool":
            return expression.get("val")
        
        if exp_type == "nil":
            return None
        
        # Handles evaluating assignment to variable
        if exp_type == "var":
            value = self.get_variable(expression.get("name"))
            return value

        if exp_type == "fcall":
            if expression.get("name") == "inputi" or expression.get("name") == "inputs":
                return self.handle_input(expression.get("name"), expression.get("args"))
            return self.do_func_call(expression)
    
    def do_func_call(self, func_call):
        func_name = func_call.get("name")
        if func_name == "print":
            total_output = ""
            for arg in func_call.get("args"):
                if arg.elem_type == "int" or arg.elem_type == "string":
                    total_output = total_output + str(arg.get("val"))
                elif arg.elem_type == "bool":
                    if arg.get("val") is True:
                        total_output = total_output + "true"
                    else:
                        total_output = total_output + "false"
                elif arg.elem_type == "fcall":
                    total_output = self.do_func_call(arg)
                else:
                    if arg.elem_type == "var":
                        value = self.get_variable(arg.get("name"))
                    elif arg.elem_type in self.bin_ops or arg.elem_type in self.bin_bool_ops or arg.elem_type in self.unary_ops or arg.elem_type in self.comp_ops:
                        value = self.evaluate_expression(arg)

                    if value is True:
                        value = "true"
                    elif value is False:
                        value = "false"
                    total_output = total_output + str(value)
            super().output(total_output)
        elif func_name == "inputi" or func_name == "inputs":
            self.handle_input(func_name, func_call.get("args"))
        else:
            func_node = self.func_list.get((func_name, len(func_call.get("args"))))
            if not func_node:
                super().error(
                    ErrorType.NAME_ERROR,
                    f"Function {func_name} has not been defined",
                )
            return self.run_func(func_node, func_call.get("args"))
    
    def do_if_statement(self, if_statement):
        statements = if_statement.get("statements")
        else_statements = if_statement.get("else_statements")
        self.stack[-1].append({})

        condition = self.evaluate_expression(if_statement.get("condition"))
        result = None
        if condition:
            # for s in statements:
            #     if s.elem_type == "return":
            #         result = self.do_return_statement(s)
            #         break
            result = self.run_statements(statements)
        elif else_statements:
            # for s in else_statements:
            result = self.run_statements(else_statements)
        self.stack[-1].pop()   
        return result    

    def do_for_loop(self, for_loop):
        init = for_loop.get("init")
        condition = for_loop.get("condition")
        update = for_loop.get("update")
        statements = for_loop.get("statements")

        self.do_assignment(init)

        if not isinstance(self.evaluate_expression(condition), bool):
            super().error(
                ErrorType.NAME_ERROR,
                f"For loop condition does not evaluate to boolean",
            )
        
        while self.evaluate_expression(condition):
            self.stack[-1].append({})
            result = None
            # for s in statements:
            result = self.run_statements(statements)
            self.do_assignment(update)
            self.stack[-1].pop()
            return result

    def do_return_statement(self, statement):
        if not statement.get("expression"):
            return None
        result = self.evaluate_expression(statement.get("expression"))
        return result
    
    def get_exp_value(self, op):
        op_type = op.elem_type

        if op_type == "var":
            val = self.get_variable(op.get("name"))
        elif op_type in self.bin_ops or op_type in self.bin_bool_ops or op_type in self.unary_ops or op_type in self.comp_ops:
            val = self.evaluate_expression(op)
        elif op_type == "fcall":
            if op.get("name") == "inputi" or op.get("name") == "inputs":
                val = self.handle_input(op.get("name"), op.get("args"))
            else:
                val = self.do_func_call(op)
        else:
            val = op.get("val")

        return val

    def get_scope(self, var_name):
        for scope in reversed(self.stack[-1]):
            if var_name in scope:
                return scope
        super().error(
            ErrorType.NAME_ERROR,
            f"Variable {var_name} has not been defined",
        )
    
    def get_variable(self, var_name):
        # if var_name not in self.stack[-1][self.curr_func]:
            # super().error(
            #     ErrorType.NAME_ERROR,
            #     f"Variable {var_name} has not been defined",
            # )
        scope = self.get_scope(var_name)
        if scope:
            return scope[var_name]
        
        # return self.stack[-1][self.curr_func][var_name]
    
    def handle_input(self, func_name, args):
        if len(args) > 1:
            super().error(
                ErrorType.NAME_ERROR,
                f"No {func_name}() function found that takes > 1 parameter",
            )
        else:
            if len(args) == 1:
                super().output(args[0].get("val"))
            user_input = super().get_input()
            if func_name == "inputi":
                return int(user_input)
            return user_input
    
    def is_not_type_valid_op(self, exp_type, val1, val2):
        if exp_type in self.comp_ops:
            if not exp_type == "==" and not exp_type == "!=":
                if isinstance(val1, bool): return True
                if not isinstance(val1, int): return True
        if type(val1) != type(val2): return True
        if exp_type in self.bin_ops:
            if isinstance(val1, bool): return True
            if exp_type == "+":
                if not isinstance(val1, (int, str)): return True
            else:
                if not isinstance(val1, int): return True
        if exp_type in self.bin_bool_ops:
            if not isinstance(val1, bool): return True
        # if ((type(val1) != type(val2)) or
        #     (exp_type in self.bin_bool_ops and (not isinstance(val1, bool) or not isinstance(val2, bool))) or
        #     (exp_type == "+" and ((not isinstance(val1, (int, str)) and not isinstance(val2, (int, str))) or (isinstance(val1, bool)))) or
        #     (exp_type in self.bin_ops and exp_type != "+" and ((not isinstance(val1, int) and not isinstance(val2, int)) or (isinstance(val1, bool))))):
        #     return True

    def is_not_type_valid_unary_op(self, exp_type, val1):
        if exp_type == "neg":
            if isinstance(val1, bool): return True
            if not isinstance(val1, int): return True
        if exp_type == "!":
            if not isinstance(val1, bool): return True
        # if ((exp_type == "neg" and (not isinstance(val1, int) or isinstance(val1, bool))) or
        #     (exp_type == "!" and not isinstance(val1, bool))):
        #     return True
        
