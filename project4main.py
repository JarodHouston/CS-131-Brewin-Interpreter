from interpreterv4 import Interpreter

def main():
    interpreter = Interpreter(trace_output=True)
    program = """
func main() {
	var x;
	var y;
	x = foo() + 8;
	y = x + 1;
	x = 1 + foo();
  y = x + 1;
	print("hey");
	print(x);
	print(y);
}
func foo() {
    print("hi");
    return 5;
}

              """

    interpreter.run(program)

if __name__ == "__main__":
    main()