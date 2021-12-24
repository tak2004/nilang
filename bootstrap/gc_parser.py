import sys
from lark import Lark, UnexpectedInput
import pickle
from gc_parser_decorator import Decorate,PrepareProcessing,GenerateIR
from gc_parser_nodes import TokensToNodes
from gc_parser_postprocessor import PostProcessor
from nilang_ir import IRModule

gamecode_grammar = r"""
    _separated{e, sep}: e (sep e)*

    unit: package [import_] unit_stmt
    unit_stmt: ( ast_decorator 
               | struct_
               | enum 
               | alias 
               | function_definition 
               | function_declaration 
               | namespace 
               | variable
               | interface)* 
    ?package: "module" NAME
    import_: "use" (string_literal | match) ("," (string_literal | match))*

    // Post processor
    ast_decorator: "decorator" NAME "(" _AST NAME "," _AST NAME "," _AST NAME ")" "{" small_stmt_list "}"
    _AST: "__AST__"

    interface: "interface" NAME "{" intf_functions "}"
    ?intf_functions: interface_function*
    interface_function: [decorations] NAME "(" [paramlist] ")" ["->" type_decl ] ";"

    namespace: [decorations] "namespace" NAME "{" (function_definition
                                                  |function_declaration
                                                  |variable
                                                  |struct_
                                                  |enum
                                                  |alias
                                                  |namespace
                                                  |interface)* "}"
    enum: "enum" NAME "{" enum_values "}"
    enum_values: _separated{NAME, ","}
    struct_: [decorations] "struct" NAME ["<" typelist ">"] "{" struct_body "}"
    struct_body:(function_definition|function_declaration|variable|operator|compose)*
    alias: "alias" NAME "=" type_decl

    ?type_decl: [CONST] (NAME|AUTO) ["<" typelist ">"]
    typelist: type_decl (","type_decl)*
    CONST: "const"
    variable: [decorations] [STATIC] type_decl NAME [init_var] ";"
    ?init_var: "=" logical_or
    STATIC: "static"
    compose: NAME ";"

    function_declaration: [decorations] NAME "(" [paramlist] ")" ["->" type_decl ] ";"
    function_definition: [decorations] NAME "(" [paramlist] ")" ["->" type_decl ] "{" small_stmt_list "}"
    lambda_: [decorations] "(" [paramlist] ")" ["->" NAME] "{" small_stmt_list "}"
    paramlist : param ("," param)*
    param : type_decl NAME
    call_chain: ((NAME | func_call) ".")* func_call
    func_call : NAME (func_call_empty | "("[arglist]")")
    func_call_empty: "()"
    arglist: logical_or ("," logical_or)*

    operator: "operator" (escape_operator 
                         |index_operator
                         |newindex_operator
                         |call_operator
                         |inheritance_operator) "{" small_stmt_list "}"
    // runtime
    index_operator: "[]" "(" param ")" "->" NAME
    newindex_operator: "[]" "(" param "," param ")"
    call_operator: "()" "(" [paramlist] ")" ["->" NAME]
    // parser/compiler time
    escape_operator: "\'" NAME "'" "()"
    inheritance_operator: ":" "(" _AST NAME "," _AST NAME ")"

    decorations : "[[" _separated{decoration, ","} "]]"
    ?decoration: NAME [":" (numeric_literal | string_literal)]

    small_stmt_list : small_stmt*
    ?small_stmt: variable
               | arithmetic_expr 
               | conditional_expr 
               | return 
               | for_stmt 
               | match 
               | switch 
               | call_chain 
               | lambda_                
               | if_stmt
               | assignment

    return: "return" value_stmt
    
    arithmetic_expr: small_stmt ("+"|"-") (small_stmt | string_literal)
    // logical expression
    block_stmt: "{" small_stmt* "}"
              | small_stmt
    if_stmt: "if" "(" logical_or ")" block_stmt ["else" block_stmt]
    conditional_expr: logical_or "?" (block_value | value_stmt) [":" (block_value | value_stmt)]
   
    ?assignment: var (ASSIGN|ASSIGN_OP) value_stmt -> binop_expr

    ?logical_or: logical_and
               | logical_or LOG_OR_OP logical_and -> binop_expr
    ?logical_and: inclusive_or
                | logical_and LOG_AND_OP inclusive_or -> binop_expr
    ?inclusive_or: exclusive_or
                 | inclusive_or OR_OP exclusive_or -> binop_expr
    ?exclusive_or: and_
                 | exclusive_or XOR_OP and_ -> binop_expr
    ?and_: equality
         | and_ AND_OP equality -> binop_expr
    ?equality: relational
             | equality EQ relational -> binop_expr
             | equality NEQ relational -> binop_expr
    ?relational: shift
               | relational REL_OP shift -> binop_expr
    ?shift: add
          | shift SHIFT_OP add -> binop_expr
    ?add: mul
        | add (MINUS|PLUS) mul -> binop_expr
    ?mul: cast
        | mul MUL_OP cast -> binop_expr
    ?cast: "(" type_decl ")" cast
         | unary
    ?unary: postfix
          | (MINUS|PLUS) cast -> unary_expr
    ?postfix: primary
            | postfix "[" assignment "]" -> array_subscript
            | postfix "(" [arglist] ")" -> func_call
    ?primary: var
            | scope_var
            | numeric_literal
            | string_literal
            | "(" logical_or ")"
    
    ?value_stmt: numeric_literal 
               | string_literal 
               | arithmetic_expr 
               | conditional_expr 
               | var 
               | index_query 
               | match 
               | logical_or
               | scope_var
    
    block_value: "{" small_stmt* return "}"
    var: (NAME|func_call|scope_var) ("." (NAME|func_call|scope_var))*
    scope_var: NAME ("::" NAME)*

    index_query: var "[" value_stmt "]"

    for_stmt: "for" NAME "in" var "{" small_stmt "}"

    switch: "switch" "(" var ")" "{" switch_case ("," switch_case)* [[","] "default" ":" (var|scope_var)] "}"
    switch_case: (numeric_literal | string_literal | var | scope_var) ":" (var|scope_var) [switch_break]
    switch_break: "break"

    match: "match" "(" value_stmt ["as" NAME] ")" ["->" type_decl] "{" match_cases [[","] "default" ":" (value_stmt | block_value)] "}"
    match_cases: match_case*
    match_case: (numeric_literal | string_literal | NAME) ":" (value_stmt | block_value) []

    string_literal: ESCAPED_STRING
    numeric_literal: INT_CONSTANT
                   | FLOATING_POINT

    AUTO: "auto"
    MINUS.0: "-"
    PLUS.0: "+"
    ASSIGN: "="
    SHIFT_OP.2: "<<"
              | ">>"
    ASSIGN_OP: ASSIGN
             | "*="
             | "/="
             | "%="
             | "+="
             | "-="
             | "<<="
             | ">>="
             | "^="
             | "&="
             | "|="
    LOG_OR_OP: "||"
    LOG_AND_OP: "&&"
    OR_OP: "|"
    XOR_OP: "^"
    AND_OP: "&"
    EQ.2: "=="
    NEQ: "!="
    REL_OP: "<"
          | ">"
          | ">="
          | "<="
    MUL_OP: "*"
          | "/"
          | "%"

    INT_CONSTANT: HEX_NUMBER 
                | DEC_NUMBER 
                | "0"

    HEX_NUMBER: /0x[\da-f]+/i
    DEC_NUMBER: /[1-9]\d*/
    FLOATING_POINT.2: /[0-9]*\.[0-9]+/

    %import common.ESCAPED_STRING
    %import common.CNAME -> NAME
    %import common.WS
    %import common.CPP_COMMENT
    %import common.C_COMMENT
    %ignore WS
    %ignore CPP_COMMENT
    %ignore C_COMMENT
    """

def parse(f):
    gamecode_parser = Lark(gamecode_grammar, start='unit', lexer='standard', maybe_placeholders=True)
    try:        
        tree = gamecode_parser.parse(f.read())        
        #pickle.dump(tree, open('gc_cache/'+f.name+'.ast','wb'))
        dbg = open('gc_cache/'+f.name+'.ast.txt','w')
        dbg.write(tree.pretty())
        dbg.close()
        ast = TokensToNodes(tree)
        #print(ast)
        # Add parent to the nodes.
        PrepareProcessing().visit_top_down(ast)
        # Manipulate the AST by decoration.
        Decorate(ast).visit(ast)
        # Do simple compile time optimizations.
        PostProcessor().transform(ast)
        # Convert high level abstraction(classes) to low level.
        # Build the interpreter code.
        unit = GenerateIR()
        unit.visit_top_down(ast)
        irFile=open('gc_cache/'+f.name+'.nimo','wb')
        irFile.write(unit.IR)
        irFile.close()
        
        reader = IRModule()
        #print(unit.IR)
        reader.read(unit.IR)
        readableIRFile = open('gc_cache/'+f.name+'.nimo.txt','w')
        readableIRFile.write(reader.generateText())
        readableIRFile.close()
        return True
    except UnexpectedInput as u:
        print('Parser error: '+f.name)
        print(u)
        return False

if __name__ == '__main__':
    with open(sys.argv[1]) as f:
        parse(f)