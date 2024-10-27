from intbase import InterpreterBase
from intbase import ErrorType
from brewparse import parse_program

class Interpreter(InterpreterBase):
    def __init__(self, console_output=True, inp=None, trace_output=False):
        super().__init__(console_output, inp)   # call InterpreterBase's constructor
        self.trace_output = trace_output

    def run(self, program):
        ast = parse_program(program)
        self.variable_name_to_value = {}

        main_func_node = self.get_main_func_node(ast)
        if not main_func_node or main_func_node.get("name") != "main":
            super().error(
                ErrorType.NAME_ERROR,
                "No main() function was found",
            )

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
        type = expression.elem_type

        # Handles expression node as operators
        if type == "+" or type == "-":
            op1 = expression.get("op1")
            op2 = expression.get("op2")

            if op1.elem_type == "var":
                val1 = self.get_variable(op1.get("name"))
            elif op1.elem_type == "+" or op1.elem_type == "-":
                val1 = self.evaluate_expression(op1)
            elif op1.elem_type == "fcall" and op1.get("name") == "inputi":
                val1 = self.handle_input(op1.get("args"))
            else:
                val1 = op1.get("val")

            if op2.elem_type == "var":
                val2 = self.get_variable(op2.get("name"))
            elif op2.elem_type == "+" or op2.elem_type == "-":
                val2 = self.evaluate_expression(op2)
            elif op2.elem_type == "fcall" and op2.get("name") == "inputi":
                val2 = self.handle_input(op2.get("args"))
            else:
                val2 = op2.get("val")
            
            if isinstance(val1, str) or isinstance(val2, str):
                super().error(
                    ErrorType.TYPE_ERROR,
                    "Incompatible types for arithmetic operation",
                )

            if type == "-":
                val2 = val2 * -1
            return val1 + val2
        
        # Handles evaluating assignment to value
        if type == "int" or type == "string" or type == "bool":
            return expression.get("val")
        
        # Handles evaluating assignment to variable
        if type == "var":
            value = self.get_variable(expression.get("name"))
            return value

        if type == "fcall" and expression.get("name") == "inputi":
            return self.handle_input(expression.get("args"))
    
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
                elif arg.elem_type == "var":
                    value = self.get_variable(arg.get("name"))
                    total_output = total_output + str(value)
                elif arg.elem_type == "+" or arg.elem_type == "-":
                    value = self.evaluate_expression(arg)
                    total_output = total_output + str(value)
            # if len(func_call.get("args")) != 0:
            super().output(total_output)
        elif func_name == "inputi":
            self.handle_input(func_call.get("args"))
        else:
            super().error(
                ErrorType.NAME_ERROR,
                f"Function {func_name} has not been defined",
            )
    
    def get_variable(self, var_name):
        if var_name not in self.variable_name_to_value:
            super().error(
                ErrorType.NAME_ERROR,
                f"Variable {var_name} has not been defined",
            )
            return None
        value = self.variable_name_to_value[var_name]
        if value is True:
            return "true"
        elif value is False:
            return "false"
        return value
    
    def handle_input(self, args):
        if len(args) > 1:
            super().error(
                ErrorType.NAME_ERROR,
                f"No inputi() function found that takes > 1 parameter",
            )
        else:
            if len(args) == 1:
                super().output(args[0].get("val"))
            user_input = super().get_input()
            return int(user_input)
        
