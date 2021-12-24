from os import read
from numpy.lib.function_base import kaiser
from nilang_ir import *
from ctypes import *

class VM:
    def __init__(self) -> None:
        self.functionTable = []
        self.InitFunctionTable()
        self.irCode = bytearray()
        self.pc = 0
        self.fp = 0
        self.end = 0
        self.constants = {}
        self.imports = {}
        self.loadedLibs = {}
        self.loadedFunctions = {} 
        self.stack = []
        self.labels = {}
        self.functions = {}
        self.structs = {}
        self.types = {}
        self.loadedDeps = {}

    def AddMainModule(self,irModule):
        reader = IRModule()        
       # print(irModule)
        reader.read(irModule)  
        self.functions = reader.functions
        self.LoadLabels(reader.code)
        self.irCode = reader.code
        self.imports = reader.imports
        self.constants = reader.constants
        self.structs = reader.structs
        self.types = reader.types
        self.unresolvedTypes = reader.unresolvedTypes
        for dep in reader.dependencies:
            if not dep in self.loadedDeps.keys():
                self.AddModule(dep)
        self.solveUnresolvedTypes()

    def AddModule(self,name):
        reader = IRModule()        
        bytes = open('gc_cache/'+name+'.gc.nimo','rb').read()        
        reader.read(bytes)
        self.loadedDeps[name] = reader
        for dep in reader.dependencies:
            if not dep in self.loadedDeps.keys(): 
                self.AddModule(dep)

    def DecodeOperation(self):
        operation = self.irCode[self.pc]
        if operation >= FirstFiveByteOperation:
            consumedBytes = 5
        elif operation >= FirstThreeByteOperation:
            consumedBytes = 3
        elif operation >= FirstTwoByteOperation:
            consumedBytes = 2
        else:
            consumedBytes = 1
        if self.pc + consumedBytes <= self.end:
            #print(operation)
            self.functionTable[operation]()
        return consumedBytes

    def Run(self):
        self.LoadImports()   
        self.pc = 0        
        if "run" in self.functions:
            self.pc = self.functions["run"]
        self.end = len(self.irCode)        
        while self.pc < self.end:
            # decode, execute(can change the pc) and then adjust the pc
            offset = self.DecodeOperation()
            self.pc += offset

    def LoadImports(self):
        for lib in self.imports:
            print("Import "+lib)
            self.loadedLibs[lib] = windll.LoadLibrary(lib)
            for f in self.imports[lib]:
                function = self.loadedLibs[lib][f]
                self.loadedFunctions[f]=function

    def LoadLabels(self, irCode):
        pc = 0
        end = len(irCode)
        labels = {}
        codeOffset = len(self.irCode)
        # load relative labels
        while pc < end:
            operation = irCode[pc]
            if operation >= FirstFiveByteOperation:
                consumedBytes = 5
            elif operation >= FirstThreeByteOperation:
                consumedBytes = 3
            elif operation >= FirstTwoByteOperation:
                consumedBytes = 2
            else:
                consumedBytes = 1
            if operation == bc['Label']:
                id = irCode[pc+1]
                labels[id]=pc
            pc += consumedBytes
        # add absolute jump address
        pc = 0
        while pc < end:
            operation = irCode[pc]
            if operation >= FirstFiveByteOperation:
                consumedBytes = 5
            elif operation >= FirstThreeByteOperation:
                consumedBytes = 3
            elif operation >= FirstTwoByteOperation:
                consumedBytes = 2
            else:
                consumedBytes = 1
            if operation == bc['JumpIf']:
                id = irCode[pc+1]
                self.labels[pc+codeOffset] = labels[id]+codeOffset
            if operation == bc['Invoke']:
                id = irCode[pc+1]
                self.labels[pc+codeOffset] = labels[id]+codeOffset
            if operation == bc['Goto']:
                id = irCode[pc+1]
                self.labels[pc+codeOffset] = labels[id]+codeOffset 
            pc += consumedBytes
        for f in self.functions:
            self.functions[f] = labels[self.functions[f]]+codeOffset

    def Nop(self):
        pass

    def JumpIf(self):
        condition = self.stack.pop()
        if condition:
            self.pc = self.labels[self.pc]-2

    def Goto(self):
        self.pc = self.labels[self.pc]-2

    def Invoke(self):
        argc = self.irCode[self.pc+2]
        self.stack.append(argc)# add how many
        self.stack.append(self.fp)# save the current fp 
        self.stack.append(self.pc+2)# save the pc after this operation
        self.fp = len(self.stack)
        self.pc = self.labels[self.pc]-2
        #print(self.stack)
        #print(self.pc)

    def Return(self):
        #print(self.stack)
        # remove all local variables
        while len(self.stack) > self.fp:
            self.stack.pop()
        # on the top of the stack is the current frame contex now
        self.pc = self.stack.pop()
        self.fp = self.stack.pop()
        argc = self.stack.pop()
        #print(self.stack)
        # remove all parameters
        for i in range(argc):
            self.stack.pop()
        #print(self.stack)

    def Copy(self):
        index = self.irCode[self.pc+1]
        index -= 32
        val = self.stack[self.fp+index]
        self.stack.append(val)

    def PushOne(self):
        self.stack.append(1)

    def PushZero(self):
        self.stack.append(0)

    def Equal(self):
        left = self.stack.pop()
        right = self.stack.pop()
        self.stack.append(left.value == right.value)

    def Not(self):
        value = self.stack.pop()
        self.stack.append(not value)

    def ResolveAddrOfImportIndex(self):
        #print(self.stack)
        index = self.stack.pop()
#        print(self.loadedFunctions)        
        func = list(self.loadedFunctions.values())[index]
        self.stack.append(func)

    def Call(self):
        #print(self.stack)
        argc = self.irCode[self.pc+1]
        args = []
        index = len(self.stack)-argc
        for i in range(argc):
            args.append(self.stack.pop(index))
        func = self.stack.pop()
        res = func(*args)
        if func.restype != None:
            res = func.restype(res)
        self.stack.append(res)

    def PushConst(self):
        index = self.stack.pop()
        const = list(self.constants.values())[index]
        value = self.convertValue(const['value'],const['type'])
        self.stack.append(value)

    def convertValue(self,val,type):
        result = val
        if type==20:
            result = c_char_p(bytes(val,'ascii'))
        elif type==22:
            result = c_void_p(int(val))
        elif type==2:
            result = c_uint32(val)
        elif type==9:
            result = c_int32(val)
        else:
            print('Implement type')
        return result

    def ResolveAddrOfConstIndex(self):
        index = self.stack.pop()
        #print(self.constants)
        const = list(self.constants.values())[index]
        value = self.convertValue(const['value'],const['type'])
        self.stack.append(value)

    def PushU8(self):
        value = self.irCode[self.pc+1]
        self.stack.append(value)

    def Pop(self):
        self.stack.pop()

    def CallIntrinsic(self):
        intrinsic = self.irCode[self.pc+1]
        if intrinsic == 0:
            print("Loaded functions:")
            print(self.loadedFunctions)
            print("Stack:")
            print(self.stack)
            print("Program counter: "+str(self.pc))
            print("Code:")
            print(self.irCode)                                   

    def Init(self):
        typeid = np.frombuffer(self.irCode,np.uint16,1,self.pc+1)[0]
        print(typeid)
        if typeid in self.structs.keys():
            print(self.structs[typeid])
        elif typeid in self.types.keys():
            pass

    def InitFunctionTable(self):
        for i in range(256):
            self.functionTable.append(self.Nop)
        availableFunctions = [a for a in dir(self) if not a.startswith('_') and callable(getattr(self, a))]
        for name, id in bc.items():
            if name in availableFunctions:
                self.functionTable[id]=getattr(self,name)
        #print(self.functionTable)