from intbase import InterpreterBase
from intbase import ErrorType
from brewparse import parse_program

# Enumerated type for our different language data types
class Type:
    INT = "int"
    BOOL = "bool"
    STRING = "string"
    NODE = "node"
    NIL = "nil"

class Struct:
    def __init__(self, name, attr, alive):
        self.name = name
        self.alive = alive
        self.type = name
        attr_list = {}
        for elem in attr:
            default_val = None
            type = elem.get("var_type")
            if type == "bool":
                default_val = False
            elif type == "int":
                default_val = 0
            elif type == "string":
                default_val = ""
            else:
                default_val = Type.NIL
            attr_list[elem.get("name")] = Value(type, default_val)
        self.attr = attr_list
    
    def set_alive(self, state):
        self.alive = state
    
    def print(self):
        print(self.name)
        print(self.attr)
        

# Represents a value, which has a type and its value
class Value:
    def __init__(self, type, value=None):
        self.type = type
        self.value = value

    def value(self):
        return self.value

    def type(self):
        return self.type
    
    def change_value(self, val):
        if self.type == Type.BOOL and isinstance(val, int):
            if val == 0:
                self.value = False
            else:
                self.value = True
        else:
            self.value = val

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
        # Stack of stacks of dictionaries
        self.stack = []
        # List of Struct objects
        self.structs = []

        # List of struct objects
        self.struct_list = []
        # List of defined structs
        self.defined_structs = self.get_defined_structs(ast)
        # List of functions
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
        self.check_function_validity(func_list)
        return func_list
    
    # def check_struct_attr_validity(self):
    #     initialized_structs = []
    #     for struct in self.defined_structs:
    #         initialized_structs.extend(struct.keys())
    #         for val in struct.values():
    #             for attr in val:
    #                 print(attr)
    
    def check_function_validity(self, func_list):
        for key in func_list:
            return_type = func_list[key].get("return_type")
            if return_type is None:
                super().error(
                    ErrorType.TYPE_ERROR,
                    "Function missing its return type",
                )
            if not self.is_valid_type(return_type):
                super().error(
                    ErrorType.TYPE_ERROR,
                    "Function has invalid return type",
                )
            for arg in func_list[key].get("args"):
                arg_var_type = arg.get("var_type")
                if arg_var_type is None:
                    super().error(
                        ErrorType.TYPE_ERROR,
                        "Function argument missing its type",
                    )
                if not self.is_valid_type(arg_var_type):
                    super().error(
                        ErrorType.TYPE_ERROR,
                        "Function has invalid argument type",
                    )
    
    def get_defined_structs(self, ast):
        struct_list = []
        for struct in ast.get("structs"):
            struct_list.append({struct.get("name"): struct.get("fields")})
            # struct_list.append(Struct(struct.get("name"), struct.get("fields"), False))
        return struct_list
    
    def get_struct_fields(self, name):
        for struct in self.defined_structs:
            if name in struct:
                return struct[name]
        return None

    def run_func(self, func_node, call_arguments):
        list_to_append = [{}]
        func_args = func_node.get("args")
        for i in range(len(func_args)):
            var_name = func_args[i].get("name")
            var_type = func_args[i].get("var_type")
            val = self.evaluate_expression(call_arguments[i])
            if self.is_valid_return(val, var_type):
                if var_type == "bool" and self.is_int(val):
                    val = (val != 0)
                list_to_append[0][var_name] = Value(var_type, val)
            else: 
                super().error(
                    ErrorType.TYPE_ERROR,
                    "Incompatible types for function's arguments",
                )

        self.stack.append(list_to_append)
        self.stack[-1].append({})
        statements = func_node.get("statements")
        result = None
        stack_length = len(self.stack)
        result = self.run_statements(statements)
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
                # print(self.stack[-1][-1]['p'].value.print())
            elif statement.elem_type == "fcall":
                result = self.do_func_call(statement)              
            elif statement.elem_type == "if":
                result = self.do_if_statement(statement)
            elif statement.elem_type == "for":
                result = self.do_for_loop(statement)
            elif statement.elem_type == "return":
                result = self.do_return_statement(statement)
                self.stack.pop()
                return result
            
            if len(self.stack) < stack_length:
                return result
    
    def create_value(self, type):
        if type == "int":
            return Value(Type.INT, 0)
        if type == "bool":
            return Value(Type.BOOL, False)
        if type == "string":
            return Value(Type.STRING, "")
        for struct in self.defined_structs:
            if type in struct:
                return Value(Type.NODE, Type.NIL)
        else:
            super().error(
                ErrorType.TYPE_ERROR,
                "Unknown value type",
            )
    
    def do_definition(self, definition):
        var_name = definition.get("name")
        var_type = definition.get("var_type")
        if not self.is_valid_type(var_type):
            super().error(
                ErrorType.TYPE_ERROR,
                "Invalid type in variable definition",
            )
        if var_name in self.stack[-1][-1]:
            super().error(
                ErrorType.NAME_ERROR,
                f"Variable {var_name} defined more than once",
            )
        else:
            self.stack[-1][-1][var_name] = self.create_value(var_type)
    
    def is_valid_assignment(self, curr_var, val):
        if (type(val) == bool or type(val) == int) and curr_var.type == Type.BOOL:
            return True
        elif type(val) == int and curr_var.type == Type.INT:
            return True
        elif type(val) == str and curr_var.type == Type.STRING:
            return True
        elif (type(val) == Struct or val == Type.NIL) and (curr_var.type == Type.NODE or self.struct_exists(curr_var.type)):
            return True
        return False
    
    def get_var_name_split(self, var_name):
        struct_name = None
        attr_name = None
        if "." in var_name:
            
            struct_name, attr_name = var_name.split('.')
        if struct_name and attr_name:
            return (struct_name, attr_name)
        return (var_name,)
    
    def do_assignment(self, assignment):
        var_name = assignment.get("name")
        split = self.get_var_name_split(var_name)
        if len(split) > 1:
            var_name = split[0]
        scope = self.get_scope(var_name)
        if scope:
            expression = assignment.get("expression")
            expression_result = self.evaluate_expression(expression)
            if len(split) > 1:
                if type(scope[var_name].value) is not Struct:
                    super().error(
                        ErrorType.FAULT_ERROR,
                        "Variable to the left of the dot is not of type struct",
                    )
                if self.is_valid_assignment(scope[var_name].value.attr[split[1]], expression_result):
                    scope[var_name].value.attr[split[1]].change_value(expression_result)
            elif self.is_valid_assignment(scope[var_name], expression_result):
                scope[var_name].change_value(expression_result)
            else:
                super().error(
                    ErrorType.TYPE_ERROR,
                    "Incompatible types for assignment",
                )
        # if len(split) > 1:
        #     print(scope[var_name].value.attr[split[1]].value)
            
    def evaluate_coercion(self, val1, val2):
        if val1 == 0:
            return not val2
        return val2
    
    def is_int(self, val):
        if isinstance(val, int) and not isinstance(val, bool):
            return True
        return False
    
    def evaluate_equality(self, val1, val2):
        if self.is_int(val1) and isinstance(val2, bool):
            return self.evaluate_coercion(val1, val2)
        if self.is_int(val2) and isinstance(val1, bool):
            return self.evaluate_coercion(val2, val1)
        return val1 == val2

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
            
            op_map = {
                "&&": lambda x, y: (x != 0 if self.is_int(x) else x) and (y != 0 if self.is_int(y) else y),
                "||": lambda x, y: (x != 0 if self.is_int(x) else x) or (y != 0 if self.is_int(y) else y)
            }

            if exp_type in op_map:
                return op_map[exp_type](val1, val2)

            # if exp_type == "&&": 
            #     if self.is_int(val1) and isinstance(val2, bool):
            #         return val1 != 0 and val2
            #     if self.is_int(val2) and isinstance(val1, bool):
            #         return val2 != 0 and val1
            #     return val1 and val2
            # if exp_type == "||":
            #     if self.is_int(val1) and isinstance(val2, bool):
            #         return val1 != 0 or val2
            #     if self.is_int(val2) and isinstance(val1, bool):
            #         return val2 != 0 or val1
            #     return val1 or val2

            # if exp_type == "==" and not isinstance(val1, type(val2)):
            # if exp_type == "==":
            #     return False
            # if exp_type == "!=" and not isinstance(val1, type(val2)):
            #     return True

            if exp_type == "==": return self.evaluate_equality(val1, val2)
            if exp_type == "!=": return not self.evaluate_equality(val1, val2)
            if exp_type == ">": return val1 > val2
            if exp_type == "<": return val1 < val2
            if exp_type == ">=": return val1 >= val2
            if exp_type == "<=": return val1 <= val2

            if exp_type == "+": return val1 + val2
            if exp_type == "-": return val1 - val2
            if exp_type == "*": return val1 * val2
            if exp_type == "/": return int(val1 // val2)

            super().error(
                ErrorType.TYPE_ERROR,
                "Error in evaluating expression",
            )
        
        if exp_type in self.unary_ops:
            op1 = expression.get("op1")
            val1 = self.get_exp_value(op1)
            
            if self.is_not_type_valid_unary_op(exp_type, val1):
                super().error(
                    ErrorType.TYPE_ERROR,
                    "Incompatible types for arithmetic operation",
                )
            
            if exp_type == "neg": return val1 * -1
            if exp_type == "!":
                if not isinstance(val1, bool) and isinstance(val1, int):
                    if val1 == 0:
                        return True
                    return False
                if val1 is False: return True

            super().error(
                ErrorType.TYPE_ERROR,
                "Error in evaluating expression",
            )
        
        # Handles evaluating assignment to value
        if exp_type == "int" or exp_type == "string" or exp_type == "bool":
            return expression.get("val")
        
        if exp_type == "nil":
            return Type.NIL
        
        # Handles evaluating assignment to variable
        if exp_type == "var":
            value = self.get_variable(expression.get("name")).value
            return value
        
        if exp_type == "new":
            struct_type = expression.get("var_type")
            fields = self.get_struct_fields(struct_type)
            return Struct(struct_type, fields, False)

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
                    result = self.do_func_call(arg)
                    if isinstance(result, bool):
                        if result is True:
                            result = "true"
                        else:
                            result = "false"
                    total_output = total_output + str(result)
                elif arg.elem_type == "nil":
                    total_output = total_output + Type.NIL
                else:
                    if arg.elem_type == "var":
                        value = self.get_variable(arg.get("name")).value
                        if type(value) is Struct:
                            split = self.get_var_name_split(arg.get("name"))
                            value = value.attr[split[1]].value
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
            result = self.run_func(func_node, func_call.get("args"))
            return_type = func_node.get("return_type")
            if result is None:
                result = self.get_default_value(return_type)
            if self.is_valid_return(result, return_type):
                if return_type == Type.BOOL and not isinstance(result, bool) and isinstance(result, int):
                    if result == 0:
                        return False
                    return True
                return result
            super().error(
                ErrorType.TYPE_ERROR,
                f"Returned value does not match function's return type"
            )
    
    def do_if_statement(self, if_statement):
        statements = if_statement.get("statements")
        else_statements = if_statement.get("else_statements")
        self.stack[-1].append({})

        condition = self.evaluate_expression(if_statement.get("condition"))
        if not isinstance(condition, bool) and isinstance(condition, int):
            if condition == 0:
                condition = False
            else:
                condition = True
        elif not isinstance(condition, bool):
            super().error(
                ErrorType.TYPE_ERROR,
                f"If statement condition does not evaluate to boolean"
            )
        result = None
        stack_length = len(self.stack)
        if condition:
            result = self.run_statements(statements)
        elif else_statements:
            result = self.run_statements(else_statements)
        if len(self.stack) == stack_length:
            self.stack[-1].pop()   
        return result    

    def do_for_loop(self, for_loop):
        init = for_loop.get("init")
        condition = for_loop.get("condition")
        update = for_loop.get("update")
        statements = for_loop.get("statements")

        self.do_assignment(init)

        if not isinstance(self.evaluate_expression(condition), bool) and not isinstance(self.evaluate_expression(condition), int):
            super().error(
                ErrorType.TYPE_ERROR,
                f"For loop condition does not evaluate to boolean",
            )

        result = None
        
        while self.evaluate_expression(condition):
            self.stack[-1].append({})
            # for s in statements:
            stack_length = len(self.stack)
            result = self.run_statements(statements)
            if len(self.stack) != stack_length:
                return result
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

        if op_type == Type.NIL:
            return op_type
        if op_type == "var":
            val = self.get_variable(op.get("name")).value
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
        attribute = None
        if "." in var_name:
            var_name, attribute = var_name.split('.')
        scope = self.get_scope(var_name)
        if attribute:
            if scope[var_name].value != Type.NIL:
                if attribute in scope[var_name].value.attr:
                    return scope[var_name].value.attr[attribute]
                super().error(
                    ErrorType.FAULT_ERROR,
                    f"Attribute does not exist",
                )
            super().error(
                ErrorType.FAULT_ERROR,
                f"Attribute undefined",
            )
        if scope:
            return scope[var_name]
        super().error(
            ErrorType.NAME_ERROR,
            f"Variable {var_name} has not been defined",
        )
    
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
        if val1 is None or val2 is None:
            return True
        if exp_type in self.comp_ops:
            if exp_type == "==" or exp_type == "!=":
                if isinstance(val1, int) and isinstance(val2, int):
                    return False
                if val1 == "nil":
                    if val2 == "nil" or type(val2) is Struct:
                        return False
                    return True
                if val2 == "nil":
                    if val1 == "nil" or type(val1) is Struct:
                        return False
                    return True
        # if exp_type in self.comp_ops:
        #     if not exp_type == "==" and not exp_type == "!=":
        #         if isinstance(val1, bool): return True
        #         if not isinstance(val1, int): return True
        #     else:
        #         return False
        if exp_type in self.bin_bool_ops:
            if isinstance(val1, int) and isinstance(val2, int):
                return False
            if not isinstance(val1, bool): return True
        if type(val1) != type(val2): return True
        if exp_type in self.bin_ops:
            if isinstance(val1, bool): return True
            if exp_type == "+":
                if not isinstance(val1, (int, str)): return True
            else:
                if not isinstance(val1, int): return True

    def is_not_type_valid_unary_op(self, exp_type, val1):
        if exp_type == "neg":
            if isinstance(val1, bool): return True
            if not isinstance(val1, int): return True
        if exp_type == "!":
            if not isinstance(val1, int): return True
    
    def is_valid_return(self, result, return_type):
        if (return_type == "bool" and isinstance(result, int) or
           (return_type == "int" and not isinstance(result, bool) and isinstance(result, int)) or 
           (return_type == "string" and isinstance(result, str)) or
           (self.struct_exists(return_type) and ((result and result != Type.NIL and return_type == result.type) or result == Type.NIL)) or
           (return_type == "void" and result == None)):
            return True
        return False

    def get_default_value(self, type):
        if type == "bool":
            return False
        if type == "int":
            return 0
        if type == "string":
            return ""
        if(self.struct_exists(type)):
            return Type.NIL
    
    def is_valid_type(self, type):
        if type not in [Type.INT, Type.BOOL, Type.STRING, "void"] and not self.struct_exists(type):
            return False
        return True

    def struct_exists(self, name):
        return any(name in struct for struct in self.defined_structs)

# check if you pass an int to a function that takes a boolean, if it treats it like a boolean