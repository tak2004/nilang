from ast import Num
from gc_parser_decorator import PreProcessor
from gc_parser_nodes import *

class PostProcessor(NodeVisitor):
    def __fallback__(self,node,parent=None):
        return node
    def UnaryExpr(self, node):
        result = node
        if node.operation == "-" and isinstance(node.object_, NumericLiteral):
            result = NumericLiteral(-node.object_.value)
        return result
    def BinopExpr(self, node):
        result = node
        if isinstance(node.left, NumericLiteral) and isinstance(node.right,NumericLiteral):
            if node.operation == '<<':
                result = NumericLiteral(node.left.value << node.right.value)
            if node.operation == '>>':
                result = NumericLiteral(node.left.value >> node.right.value)
            if node.operation == '-':
                result = NumericLiteral(node.left.value - node.right.value)
            if node.operation == '+':
                result = NumericLiteral(node.left.value + node.right.value)
            if node.operation == '*':
                result = NumericLiteral(node.left.value * node.right.value)
            if node.operation == '/':
                result = NumericLiteral(node.left.value / node.right.value)
            if node.operation == '%':
                result = NumericLiteral(node.left.value % node.right.value)
            if node.operation == '|':
                result = NumericLiteral(node.left.value | node.right.value)
            if node.operation == '&':
                result = NumericLiteral(node.left.value & node.right.value)
            #print(str(node.left.value)+node.operation+str(node.right.value)+" = "+str(result.value))
        return result