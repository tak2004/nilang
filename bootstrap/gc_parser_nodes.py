import sys
from typing import Iterable, List
from lark import Transformer, ast_utils, v_args, Tree
from dataclasses import dataclass

from lark.lexer import Token
from lark.visitors import Interpreter

this_module = sys.modules[__name__]

class NodeVisitor:
    def visit(self, node):
        if issubclass(node.__class__,AstNode):
            members = [a for a in dir(node) if not a.startswith('_') and not callable(getattr(node, a))]
            for m in members:
                member = getattr(node,m)
                if isinstance(member,List):
                    for e in member:
                        self.visit(e)
                else:
                    self.visit(member)
            node.accept(self)
        return node

    def transform(self, node):
        result = node
        if issubclass(node.__class__,AstNode):
            members = [a for a in dir(node) if not a.startswith('_') and not callable(getattr(node, a))]
            for m in members:
                member = getattr(node,m)
                if isinstance(member,List):
                    for e in member:
                        e = self.transform(e)
                else:
                    setattr(node,m, self.transform(member))
            result = node.transform(self)
        return result

    
    def visit_top_down(self, node, parent = None):
        if issubclass(node.__class__,AstNode):
            if node.accept_top_down(self,parent):
                members = [a for a in dir(node) if not a.startswith('_') and not callable(getattr(node, a))]
                for m in members:
                    member = getattr(node,m)
                    if isinstance(member,List):
                        for e in member:
                            self.visit_top_down(e,node)
                    else:
                        self.visit_top_down(member,node)            
        return node

    def __fallback__(self, node, parent = None):
        return True

@dataclass
class AstNode(ast_utils.Ast):
    def accept_top_down(self, NodeVisitor, Parent = None):
        return getattr(NodeVisitor,self.__class__.__name__, NodeVisitor.__fallback__)(self, Parent)
    def accept(self, NodeVisitor):
        getattr(NodeVisitor,self.__class__.__name__, NodeVisitor.__fallback__)(self)
    def transform(self, NodeVisitor):
        return getattr(NodeVisitor,self.__class__.__name__, NodeVisitor.__fallback__)(self)

@dataclass
class Variable(AstNode):
    decorations: object #List(Decoration)
    static: object
    type_: object # Type
    name: str
    init: object # None or value_stmt

@dataclass
class Decoration(AstNode):
    key: str
    value: object #StringLiteral, NumericLiteral or None

@dataclass
class Return(AstNode):
    value: object

@dataclass
class StringLiteral(AstNode):
    value: str
    def __str__(self) -> str:
        return "\""+self.value+"\""

@dataclass
class NumericLiteral(AstNode):
    value: str
    def __str__(self) -> str:
        return self.value

@dataclass
class FunctionDeclaration(AstNode):
    decorations: object #List(Decoration)
    name: str
    parameters: object #Tree
    returnType: str

@dataclass
class InterfaceFunction(AstNode):
    decorations: object #List(Decoration)
    name: str
    parameters: object #Tree
    returnType: str

@dataclass
class FunctionDefinition(AstNode):
    decorations: object #List(Decoration)
    name: str
    parameters: object #Tree
    returnType: str
    statements: object # List

@dataclass
class Var(AstNode, ast_utils.AsList):
    members: object # List

@dataclass
class ScopeVar(AstNode, ast_utils.AsList):
    scopes: object # List

@dataclass
class Interface(AstNode):
    name: str
    functions: object # List

@dataclass
class TypeDecl(AstNode):
    const: object # None or CONST-Token
    name: str
    template_parameter: object # List(TypeDecl)

@dataclass
class FuncCall(AstNode):
    name: str
    arguments: object # List or var

@dataclass
class IfStmt(AstNode):
    condition: object
    then_: object # block_stmt
    else_: object # block_stmt

@dataclass
class ForStmt(AstNode):
    entry: str
    iterable: object
    do: object

@dataclass
class AstDecorator(AstNode):
    name: str
    sender: str
    root: str
    target: str
    statements: object # List(small_stmt)

@dataclass
class Unit(AstNode):
    package: str
    imports: object # List(StringLiteral or Match) or None
    statements: object #List(unit_stmt)

@dataclass
class Include(AstNode):
    file: str

@dataclass
class Param(AstNode):
    type_: object
    name: str

@dataclass
class BinopExpr(AstNode):
    left: object
    operation: object
    right: object

@dataclass
class Alias(AstNode):
    alias: str
    type_: object

@dataclass
class UnaryExpr(AstNode):
    operation: object
    object_: object

@dataclass
class PostfixExpr(AstNode):
    object_: object
    operation: object
    parameter: object # value_stmt

@dataclass
class Cast(AstNode):
    toType:object
    object_:object

@dataclass
class MatchCase(AstNode):
    value: object # value_stmt
    result: object # value_stmt or block_value

@dataclass
class Match(AstNode):
    input: object # value_stmt
    input_alias: str
    explicitType: object # Type
    cases: object # List(MatchCase)
    fallbackResult: object # None, value_stmt or block_value

@dataclass
class Enum(AstNode):
    name: str
    values: object # List(str)

@dataclass
class Struct_(AstNode):
    decoration: object # List(decoation)
    name: str
    template_parameter: object
    body: object

@dataclass
class Compose(AstNode):
    typename: str

class TranformToNodes(Transformer):
    def NAME(self, s):
        return str(s)
    def decorations(self, s):        
        return s
    def unit_stmt(self,s):
        return s
    def import_(self,s):
        return s
    def small_stmt_list(self,s):
        return s
    def ESCAPED_STRING(self, s):
        # Remove quotation marks
        return s[1:-1]
    def block_stmt(self, s):
        return s
    def call_chain(self, s):
        return s
    def func_call_empty(self, s):
        return None
    def arglist(self,s):
        return s
    def call_chain(self,s):
        return Var(s)
    def paramlist(self, s):
        return s
    def INT_CONSTANT(self, s):
        return int(s)
    def FLOATING_POINT(self, s):
        return float(s)
    def match_cases(self,s):
        return s
    @v_args(inline=True)
    def index_query(self,obj,parameter):
        return PostfixExpr(obj,Token("Subscript","[]"),parameter)
    def enum_values(self, s):
        return s
    def struct_body(self,s):
        return s
    def intf_functions(self,s):
        return s
    def typelist(self,s):
        return s
    def AUTO(self, s):
        return str(s)

def TokensToNodes(tree):
    transformer = ast_utils.create_transformer(this_module, TranformToNodes())
    return transformer.transform(tree)