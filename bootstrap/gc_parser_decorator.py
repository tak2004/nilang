from typing import List
from numpy.lib.arraysetops import isin

from numpy.lib.type_check import iscomplex
from gc_parser_nodes import *
from nilang_ir import *
# Decorator Engine allows to adjust the AST at compile time.
# This step runs before any AST optimization, right after the AST generation.
# The decorator related nodes are part of the package output but not binary.

# How to use ?
# You must define a decorator which name is the key you want to match.
# The parameter of the decorator are always the same.
# Decorator SELF, AST ROOT, AST DECORATOR_NODE
# @SELF Is the node of the AST which triggered the function. It's handy to check the value.
# @ROOT Is the root node of the AST.
# @DECORATOR_NODE Is the node of the AST which will be decorated e.g. function, class,... .
# All three parameter are references to the same AST. If you modify one it impacts the other.

class PreProcessor(NodeVisitor):
    def __init__(self):
        self.bytecode = None
        self.parameter = []
        self.counter = 0

    def debug(self, node):
        pass
        #print("["+str(self.counter)+"]: "+str(node))
        #self.counter+=1

    def __fallback__(self,node,parent=None):
        exit("Not implemented:"+str(node))

    def Type(self, node):
        self.debug(node)
        node._value = ""

    def StringLiteral(self, node):
        node._value = "\""+node.value+"\""
        self.debug(node)

    def AstDecorator(self, node):
        self.debug(node)
        code = ""
        for e in node.statements:
            code += e._value
        self.code = code
        #print(self.code)
        self.bytecode = compile(self.code, filename="",mode="exec")
        self.parameter.append(node.sender)
        self.parameter.append(node.root)
        self.parameter.append(node.target)

    def FuncCall(self, node):
        self.debug(node)
        args = ""
        if node.arguments != None:
            if isinstance(node.arguments, List):
                for e in node.arguments[0:-1]:
                    args += e._value+","
                args += node.arguments[-1]._value
            else:
                args += node.arguments._value
        node._value = node.name+"("+args+")"

    def Variable(self, node):        
        self.debug(node)
        res = node.name + " = "
        if isinstance(node.init, List):
            for e in node.init[0:-1]:
                if isinstance(e,str):
                    res += e+"."
                else:
                    res += e._value+"."
            if isinstance(node.init[-1],str):
                res+= node.init[-1]
            else:
                res += node.init[-1]._value
        else:
            res += node.init._value
        node._value = res

    def Var(self, node):
        self.debug(node)
        res = ""
        for e in node.members[0:-1]:
            if isinstance(e, FuncCall):
                res += e._value + "."
            else:
                res += e + "."
        if isinstance(node.members[-1], FuncCall):
            res += node.members[-1]._value
        else:
            res += node.members[-1]
        node._value = res
        
    def BinopExpr(self, node):
        self.debug(node)
        node._value = node.left._value + " " + node.operation + " " + node.right._value

    def ForStmt(self, node):
        self.debug(node)
        res = "for "+node.entry+" in "+node.iterable._value+":\n"
        lines = node.do._value.split("\n")
        for l in lines:
            res += "  "+l+"\n"
        node._value = res

    def IfStmt(self, node):
        self.debug(node)
        res =  "if "+node.condition._value+":\n"
        if isinstance(node.then_,List):
            for e in node.then_:
                lines = e._value.split("\n")
                for l in lines:
                    res += "  "+l+"\n"
        if isinstance(node.else_, List):
            res += "else:\n"
            for e in node.else_:
                lines = e._value.split("\n")
                for l in lines:
                    res += "  "+l+"\n"
        node._value = res

class NodeFactory():
    def Variable(self, name, type = None, init = None):
        return Variable(type,name, init)
    def Type(self,name, *decorations):
        return Type(list(decorations), name)
    def Decoration(self, key, value = None):
        return Decoration(key, value)
    def FunctionDeclaration(self, name, parameters = [], returnType = None, decorations = []):
        return FunctionDeclaration(decorations, name, parameters, returnType)
    def FunctionDefinition(self, name, parameters = [], returnType = None, decorations = [], statements = []):
        return FunctionDefinition(decorations, name, parameters, returnType, statements)
    def FunctionCall(self, name, *parameter):
        return FuncCall(name, list(parameter))
    def StringLiteral(self, value):
        return StringLiteral(value)
    def BinaryOperation(self, left, op, right):
        return BinopExpr(left, op, right)
    def Var(self, *names):
        return Var(list(names))

class Decorator():
    def __init__(self,tree,root):
        self.tree = tree
        self.root = root
        self.generatedCode = None
        self.parameter = {}
        self.interpret()

    def evaluate(self, decoratedNode, decoration):
        if self.generatedCode != None:
            param = {"ASTFactory":NodeFactory(),self.parameter[0]:decoration,self.parameter[2]:decoratedNode,self.parameter[1]:self.root}
            exec(self.generatedCode,param)

    def interpret(self):
        preProccessor = PreProcessor()
        preProccessor.visit(self.tree)        
        self.generatedCode = preProccessor.bytecode
        self.parameter=preProccessor.parameter

class Decorate(NodeVisitor):
    def __init__(self,root):
        self._decorators = dict()
        self.root = root

    def AstDecorator(self, node):
        self._decorators[node.name] = Decorator(node, self.root)

    def Decoration(self, node):
        if node.key in self._decorators.keys():
            self._decorators[node.key].evaluate(node._parent, node)

class GenerateIR(NodeVisitor):
    def __init__(self):
        self.generator = IRModule()
        self.IR = None
        self.counter = 0
        self.sCounter = 0
        self.scopeParameter = []

    def debug(self, node):
        #print("["+str(self.counter)+"]: "+str(node))
        self.counter+=1

    def resolveVar(self, node):
        self.debug(node)

    def Unit(self, node, parent):
        self.debug(node)
        if node.imports != None:
            for e in node.imports:
                self.generator.addDependency(e.value)
        if node.statements != None:
            for e in node.statements:
                e.accept(self)
        self.IR = self.generator.generate()
        return False

    def Return(self, node):
        self.debug(node)

    def __fallback__(self,node,parent=None):
        exit("Not implemented:"+str(node))

    def FunctionDeclaration(self, node):
        self.debug(node)
        for decorator in node.decorations:
            if decorator.key == 'lib' and decorator.value != None:
                self.generator.addImport(decorator.value.value, node.name)

    def InterfaceFunction(self, node):
        self.debug(node)    

    def FunctionDefinition(self, node):
        self.debug(node)
        labelIndex = self.generator.addLabel(node.name)
        self.generator.addFunction(node.name,labelIndex)
        parameter = []
        if node.parameters != None:
            for arg in node.parameters:
                parameter.append(arg.name)
        self.scopeParameter.append(parameter)
        self.generator.emit(bc['Label'],labelIndex)
        for e in node.statements:
            e.accept(self)
        self.generator.emit(bc['Return'])
        self.scopeParameter.pop()

    def TypeDecl(self, node):
        self.debug(node)

    def Type(self, node):
        self.debug(node)

    def TypeTemplate(self, node):
        self.debug(node)    

    def StringLiteral(self, node):
        self.debug(node)        

    def NumericLiteral(self, node):
        self.debug(node)

    def Param(self, node):
        self.debug(node)

    def Decoration(self, node):
        self.debug(node)

    def AstDecorator(self, node):
        self.debug(node)

    def Alias(self, node):
        self.debug(node)
        id = self.generator.types[node.type_.name]['id']
        tps=[]
        if node.type_.const != None:
            isConst = True
        else:
            isConst = False
        if node.type_.template_parameter != None:
            for tp in node.type_.template_parameter:
                if tp.const != None:
                    isTConst = True
                else:
                    isTConst = False
                tps.append(TP(isTConst,self.generator.types[tp.name]['id']))
        self.generator.addType(node.alias,isConst,id,tps)
        
    def FuncCall(self, node):
        self.debug(node)
        #print(node)
        # Register all string literals as global constants and use the addr instead of the value.
        if node.arguments != None:
            for arg in node.arguments:
                if isinstance(arg, StringLiteral):
                    constIndex = self.generator.getConstIndex(arg.value)
                    if constIndex == None:
                        self.generator.addConstant('__s'+str(self.sCounter),self.generator.types['strlit']['id'],arg.value)
                    self.sCounter += 1

        isAnImportFunction = False
        index = None
        if isinstance(node.name, Var):            
            name = node.name.members[0]
        else:# StringLiteral
            name = node.name
        isAnImportFunction = self.generator.isImportFunction(name)
        index = self.generator.getImportFunctionIndex(name)

        # If the function is an import then get the function addr.
        if isAnImportFunction:
            self.generator.emit(bc['PushU8'],index)
            self.generator.emit(bc['ResolveAddrOfImportIndex'])            
        # Else get the label of the function.
        else:
            pass
        
        # Add the parameter.
        if node.arguments != None:
            for arg in node.arguments:
                if isinstance(arg, Var):
                    constIndex = self.generator.getConstnameIndex(arg.members[0])
                    if constIndex != None:
                        self.generator.emit(bc['PushU8'], constIndex)
                        self.generator.emit(bc['ResolveAddrOfConstIndex'])
                    for i,v in enumerate(self.scopeParameter[-1]): 
                        if v == arg.members[0]:
                            self.generator.emit(bc['Copy'],28-i)
                            break
                elif isinstance(arg, StringLiteral):                
                    constIndex = self.generator.getConstIndex(arg.value)
                    self.generator.emit(bc['PushU8'], constIndex)
                    self.generator.emit(bc['ResolveAddrOfConstIndex'])
                elif isinstance(arg, NumericLiteral):
                    if arg.value == 0:
                        self.generator.emit(bc['PushZero'])
                    elif arg.value == 1:
                        self.generator.emit(bc['PushOne'])
                    elif arg.value < 256:
                        self.generator.emit(bc['PushU8'],arg.value)
                    elif arg.value < pow(2,16):
                        self.generator.emit(bc['PushU16'],arg.value)
                    elif arg.value < pow(2,32):
                        self.generator.emit(bc['PushU32'],arg.value)
                    else:
                        constIndex = self.generator.getConstIndex(arg.value)
                        self.generator.emit(bc['PushU8'], constIndex)
                        self.generator.emit(bc['ResolveAddrOfConstIndex'])

        argc = 0
        if node.arguments != None:
            argc = len(node.arguments)
        # Call if it's an import function.
        if isAnImportFunction:
            self.generator.emit(bc['Call'],argc)
        else:# Else invoke the internal function.
            index = self.generator.labels[name]
            self.generator.emit(bc['Invoke'], index, argc)

    def Variable(self, node):    
        self.debug(node)
        if node.init != None and node.type_.const != None:# const
            type_ = self.generator.types[node.type_.name]['id']
            val = node.init.value
            self.generator.addConstant(node.name,type_,val)
        if node.type_.const == None:# local var            
            if node.type_.name in self.generator.types.keys():
                typeid = self.generator.types[node.type_.name]['id']
            elif node.type_.name in self.generator.structs.keys():
                typeid = self.generator.structs[node.type_.name]['id']
            else:
                typeid = self.generator.addUnresolvedType(node.type_.name)
            self.generator.emit(bc['Init'],typeid)

    def UnaryExpr(self, node):
        self.debug(node)

    def Cast(self, node):
        self.debug(node)

    def Var(self, node):
        self.debug(node)
        for e in node.members:
            if isinstance(e, str):
                index = self.generator.getConstnameIndex(e)
                if index != None:
                    self.generator.emit(bc['PushU8'],index)
                    self.generator.emit(bc['ResolveAddrOfConstIndex'])

                #index = self.generator.getVariableIndex(e)
                #if index != None:
                #    print(e+" = "+str(index))
            else:
                e.accept(self)
        
    def ScopeVar(self, node):
        self.debug(node)

    def BinopExpr(self, node):
        self.debug(node)
        
    def ForStmt(self, node):
        self.debug(node)
        
    def IfStmt(self, node):
        self.debug(node)
        node.condition.left.accept(self)
        node.condition.right.accept(self)
        op = node.condition.operation
        if op == '==':
            self.generator.emit(bc['Equal'])
        else_ = 'else_'+str(self.generator.code.count)
        elseLabelIndex = self.generator.addLabel(else_)
        self.generator.emit(bc['JumpIf'],elseLabelIndex)
        ifEnd_ = 'ifEnd_'+str(self.generator.code.count)
        ifEndLabelIndex = self.generator.addLabel(ifEnd_)
        if node.then_ != None:
            for e in node.then_:
                e.accept(self)       
            self.generator.emit(bc['Goto'],ifEndLabelIndex)
        self.generator.emit(bc['Label'],elseLabelIndex)
        if node.else_ != None:            
            for e in node.else_:
                e.accept(self)     
        self.generator.emit(bc['Label'],ifEndLabelIndex)

    def Interface(self, node):
        self.debug(node)

    def Match(self, node):
        self.debug(node)

    def MatchCase(self, node):
        self.debug(node)

    def PostfixExpr(self, node):
        self.debug(node)

    def Enum(self, node):
        self.debug(node)

    def Struct_(self, node):
        self.debug(node)
        order = 0
        vars = []
        comp = []
        for m in node.body:
            if isinstance(m, Variable):
                if m.type_.const != None:
                    isConst = True
                else:
                    isConst = False
                id = self.generator.types[m.type_.name]['id']
                tps = []
                if m.type_.template_parameter != None:
                    for tp in m.type_.template_parameter:
                        if tp.const != None:
                            isTConst = True
                        else:
                            isTConst = False
                        tps.append(TP(isTConst,self.generator.types[tp.name]['id']))
                type_ = self.generator.addType("__"+node.name+"_"+m.type_.name,isConst,id,tps)
                vars.append(VARIABLE(m,order,type_))
                order += 1
            if isinstance(m, Compose):
                comp.append(COMPOSE(m,order))
                order += 1
            if isinstance(m, FunctionDefinition):# not part of the serialized struct
                pass
            if isinstance(m, FunctionDeclaration):# not part of the serialized struct
                pass
        self.generator.addStruct(node.name,[],vars, comp)

class PrepareProcessing(NodeVisitor):
    def __fallback__(self, node, parent):
        node._parent = parent