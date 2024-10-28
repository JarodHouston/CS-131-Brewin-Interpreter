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
        self.variable_name_to_value = {}

        main_func_node = self.get_main_func_node(ast)
        if not main_func_node or main_func_node.get("name") != "main":
            super().error(
                ErrorType.NAME_ERROR,
                "No main() function was found",
            )
        if self.trace_output:
            print(main_func_node)
        self.run_func(main_func_node)
    
    def get_main_func_node(self, ast):
        return ast.get("functions")[0]

    def run_func(self, main_func_node):
        statements = main_func_node.get("statements")
        for s in statements:
            self.run_statement(s)

    def run_statement(self, statement):
        if self.is_definition(statement):
            self.do_definition(statement)
        elif self.is_assignment(statement):
            self.do_assignment(statement)
        elif self.is_func_call(statement):
            self.do_func_call(statement)
    
    def is_definition(self, statement):
        if statement.elem_type == "vardef":
            return True
        return False
    
    def is_assignment(self, statement):
        if statement.elem_type == "=":
            return True
        return False
    
    def is_func_call(self, statement):
        if statement.elem_type == "fcall":
            return True
        return False
    
    def do_definition(self, definition):
        var_name = definition.get("name")
        if var_name in self.variable_name_to_value:
            super().error(
                ErrorType.NAME_ERROR,
                f"Variable {var_name} defined more than once",
            )
        else:
            self.variable_name_to_value[var_name] = None
    
    def do_assignment(self, assignment):
        var_name = assignment.get("name")
        if var_name not in self.variable_name_to_value:
            super().error(
                ErrorType.NAME_ERROR,
                f"Variable {var_name} has not been defined",
            )
        else:
            expression = assignment.get("expression")
            expression_result = self.evaluate_expression(expression)
            self.variable_name_to_value[var_name] = expression_result

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
        
        # Handles evaluating assignment to variable
        if exp_type == "var":
            value = self.get_variable(expression.get("name"))
            return value

        if exp_type == "fcall" and (expression.get("name") == "inputi" or expression.get("name") == "inputs"):
            return self.handle_input(expression.get("name"), expression.get("args"))
    
    def do_func_call(self, func_call):
        func_name = func_call.get("name")
        if func_name == "print":
            total_output = ""
            for arg in func_call.get("args"):
                if arg.elem_type == "int" or arg.elem_type == "string":
                    total_output = total_output + str(arg.get("val"))
                if arg.elem_type == "bool":
                    if arg.get("val") is True:
                        total_output = total_output + "true"
                    else:
                        total_output = total_output + "false"
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
            super().error(
                ErrorType.NAME_ERROR,
                f"Function {func_name} has not been defined",
            )
    
    def get_exp_value(self, op):
        op_type = op.elem_type

        if op_type == "var":
            val = self.get_variable(op.get("name"))
        elif op_type in self.bin_ops or op_type in self.bin_bool_ops or op_type in self.unary_ops or op_type in self.comp_ops:
            val = self.evaluate_expression(op)
        elif op_type == "fcall" and (op.get("name") == "inputi" or op.get("name") == "inputs"):
            val = self.handle_input(op.get("name"), op.get("args"))
        else:
            val = op.get("val")

        return val

    
    def get_variable(self, var_name):
        if var_name not in self.variable_name_to_value:
            super().error(
                ErrorType.NAME_ERROR,
                f"Variable {var_name} has not been defined",
            )
            return None
        return self.variable_name_to_value[var_name]
    
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
        
