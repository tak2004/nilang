import numpy as np
import struct
from ctypes import *
from numpy.core.fromnumeric import var

from numpy.core.numeric import isclose

MAGIC = np.uint32(1313426767)

def TP(const,id):
    return {'isConstant':const,'typeID':id}

def VARIABLE(variable, order, typeid):
    if variable.static != None:
        isStatic = True
    else:
        isStatic = False
    return {'order': order, 'name': variable.name, 'decoration': [], 'static': isStatic, 'typeid':typeid}

def COMPOSE(compose, order):
    return {'order': order, 'name': compose.typename}

class IRModule:
    def __init__(self) -> None:
        self.code = bytearray()        
        self.imports = {}
        self.types = {}
        self.labels = {}
        self.constants = {}
        self.structs = {}
        self.functions = {}
        self.dependencies = {}
        self.unresolvedTypes = {}
        self.setDefaultTypes()
        self.nextDynamicTypeID = FirstDynamicTypeID

    def addImport(self, library, function):
        if not library in self.imports.keys():
            self.imports[library] = []
        self.imports[library].append(function)

    def addDependency(self, name):
        if not name in self.dependencies.keys():
            self.dependencies[name] = {}

    def addType(self, name, isConst, typeId, templateParameter):
        id = 0
        if not name in self.types.keys():
            id = self.nextDynamicTypeID
            self.nextDynamicTypeID+=1
            self.types[name] = {
                'id': id,
                'isConstant': isConst,
                'typeID': typeId,
                'templateParameter':templateParameter
            }
        else:
            id = self.types[name]['id']
        return id

    def addStruct(self, name, templateParameter, vars, comp):
        if not name in self.structs.keys():
            id = self.nextDynamicTypeID
            self.nextDynamicTypeID += 1
            self.structs[name] = {
                'id': id,
                'templateParameter': templateParameter,
                'variables': vars,
                'compose': comp
            }
        else:
            id = self.structs[name]['id']
        return id

    def addAlias(self, alias, type):
        if not alias in self.alias.keys():
            self.alias[alias] = []
        self.alias[alias].append(type)

    def addConstant(self, name, type, value):
        if not name in self.constants.keys():
            self.constants[name] = {'type':type,'value':value}
        index = list(self.constants.keys()).index(name)
        return index

    def addLabel(self, name):
        if not name in self.labels.keys():
            index = len(self.labels.keys())
            self.labels[name] = index
        else:
            index = self.labels[name]
        return index

    def addFunction(self, name, label):
        if not name in self.functions.keys():
            index = len(self.functions.keys())
            self.functions[name]=label
        else:
            index = self.functions[name]
        return index

    def addUnresolvedType(self, name):
        if not name in self.unresolvedTypes.keys():
            id = self.nextDynamicTypeID
            self.nextDynamicTypeID += 1
            self.unresolvedTypes[name] = {
                'id': id
            }
        else:
            id = self.unresolvedTypes[name]['id']
        return id

    def emit(self,opcode, *parameter):
        # 1 Byte opcode
        self.code += struct.pack("B",opcode)
        if opcode >= FirstFiveByteOperation:# 4Byte parameter
            if len(parameter) == 1:
                self.code += struct.pack("L",*parameter)
            else:
                self.code += struct.pack("BBBB",*parameter)
        elif opcode >= FirstThreeByteOperation:# 2Byte parameter
            if len(parameter) == 1:
                self.code += struct.pack("H",*parameter)
            else:
                self.code += struct.pack("BB",*parameter)
        elif opcode >= FirstTwoByteOperation:# 1Byte parameter
            self.code += struct.pack("B",*parameter)

    def generate(self):
        result = bytearray()
        # magic number NIMO
        result += struct.pack("I",MAGIC)
        # add dependencies
        binaryData = self.generateDependencySegment()
        result += struct.pack("HH",np.uint16(4),np.uint16(len(binaryData)))
        result += binaryData

        # add import segments
        for lib in self.imports:
            binaryData = self.generateImportSegment(lib)
            # segment id
            # segment size in bytes
            # segment data
            result += struct.pack("HH",np.uint16(0),np.uint16(len(binaryData)))
            result += binaryData
        
        binaryData = self.generateTypeSegment()
        result += struct.pack("HH",np.uint16(3),np.uint16(len(binaryData)))
        result += binaryData

        binaryData = self.generateStructSegment()
        result += struct.pack("HH",np.uint16(6),np.uint16(len(binaryData)))
        result += binaryData

        binaryData = self.generateUnresolvedTypes()
        result += struct.pack("HH",np.uint16(7),np.uint16(len(binaryData)))
        result += binaryData

        binaryData = self.generateConstantSegment()
        result += struct.pack("HH",np.uint16(2),np.uint16(len(binaryData)))
        result += binaryData

        binaryData = self.generateFunctionSegment()
        result += struct.pack("HH",np.uint16(5),np.uint16(len(binaryData)))
        result += binaryData

        # code segment
        result += struct.pack("HH",np.uint16(1),np.uint16(len(self.code)))
        result += self.code
        return result

    def generateText(self):
        result = "Dependencies:\n"
        for dep in self.dependencies:
            result += "\t"+dep+"\n"
        result += "Imports:\n"
        for lib in self.imports:
            result += "\tLibrary: "+lib+"\n"
            for func in self.imports[lib]:
                result+= "\t\tFunction: "+func+"\n"
        result+="Types:\n"
        for type in self.types:
            t = self.types[type]
            if t['id'] >= FirstDynamicTypeID:
                const = ''
                if t['isConstant']:
                    const = 'const '
                id = const + self.getTypeName(t['typeID'])
                if len(t['templateParameter']) > 0:
                    id += "<"
                    for tt in t['templateParameter'][:-1]:
                        if tt['isConstant']:
                            id+= "const "
                        id += self.getTypeName(tt['typeID'])+","
                    tt = t['templateParameter'][-1]
                    if tt['isConstant']:
                        id+= "const "
                    id += self.getTypeName(tt['typeID'])
                    id += ">"
                result+= "\t"+type+":"+id+"\n"
        result+="Constants:\n"
        for const in self.constants:
            constant = self.constants[const]
            result += "\t"+self.getTypeName(constant['type'])+" "+const+" = "+str(constant['value'])+"\n"
        result+="Functions:\n"
        for name in self.functions:
            function = self.functions[name]
            result += "\t"+name+" = "+str(function)+"\n"
        result+="Unresolved types:\n"
        for name in self.unresolvedTypes:
            id = self.unresolvedTypes[name]['id']
            result += "\t"+name+": "+str(id)+"\n"
        result+="Structs:\n"
        #print(self.structs)
        for name in self.structs:
            struct_ = self.structs[name]
            result += "\t"+name+": "+str(struct_['id'])+"\n"
            lastIndex = len(struct_['variables'])+len(struct_['compose'])
            for i in range(lastIndex):
                for v in struct_['variables']:
                    if v['order'] == i:
                        isStatic = ""
                        if v['static']:
                            isStatic = "static "
                        result += "\t\t"+isStatic+self.getTypeString(v['typeid'])+" "+v['name']+"\n"
                for c in struct_['compose']:
                    if c['order'] == i:
                        result += "\t\t"+c['name']+"\n"
        result+="Code:\n"
        result+=str(len(self.code))+"bytes\n"
        pc = 0
        while pc < len(self.code):
            opcode = self.code[pc]
            result += "\t"+list(bc.keys())[list(bc.values()).index(opcode)]
            if opcode >= FirstFiveByteOperation:
                pc += 5
            elif opcode >= FirstThreeByteOperation:
                result += ", "+str(self.code[pc+1])
                result += ", "+str(self.code[pc+2])
                pc += 3
            elif opcode >= FirstTwoByteOperation:
                result += ", "+str(self.code[pc+1])
                pc += 2
            else:
                pc += 1
            result += "\n"
        return result

    def generateStructSegment(self):
        result = bytearray()
        result += struct.pack("B", np.uint8(len(self.structs.keys())))
        for name in self.structs:
            struct_ = self.structs[name]
            result += struct.pack("B"+str(len(name))+"s",len(name),name.encode())
            result += struct.pack("=HHHB",np.uint16(struct_['id']),np.uint16(len(struct_['variables'])),np.uint16(len(struct_['compose'])),np.uint8(len(struct_['templateParameter'])))
            for m in struct_['variables']:
                result += struct.pack("=HB"+str(len(m['name']))+"s",np.uint16(m['order']),len(m['name']),m['name'].encode())
                result += struct.pack("=BH",np.uint8(m['static']),np.uint16(m['typeid']))
            for m in struct_['compose']:
                result += struct.pack("=HB"+str(len(m['name']))+"s",np.uint16(m['order']),len(m['name']),m['name'].encode())
            #for tp in struct_['templateParameter']:
            #    result += struct.pack("=BH",np.uint8(tp['isConstant']),np.uint16(tp['typeID']))                
        return result

    def generateUnresolvedTypes(self):
        result = bytearray()
        result += struct.pack("B",np.uint8(len(self.unresolvedTypes.keys())))
        for name in self.unresolvedTypes:
            result += struct.pack("B"+str(len(name))+"s",len(name),name.encode())
            result += struct.pack("=H",np.uint16(self.unresolvedTypes[name]['id']))
        return result

    def generateFunctionSegment(self):
        result = bytearray()
        result += struct.pack("B",np.uint8(len(self.functions.keys())))
        for name in self.functions:
            result += struct.pack("B"+str(len(name))+"s",len(name),name.encode())
            result += struct.pack("=H",np.uint16(self.functions[name]))
        return result

    def generateDependencySegment(self):
        result = bytearray()
        result += struct.pack("B",np.uint8(len(self.dependencies.keys())))
        for dep in self.dependencies:
            result += struct.pack("B"+str(len(dep))+"s",len(dep),dep.encode())
        return result

    def generateTypeSegment(self):
        result = bytearray()
        for t in self.types:
            type_ = self.types[t]
            if type_['id'] >= FirstDynamicTypeID:
                result += struct.pack("B"+str(len(t))+"s",len(t),t.encode())
                result += struct.pack("=HHBB",np.uint16(type_['id']),np.uint16(type_['typeID']),np.uint8(type_['isConstant']),np.uint8(len(type_['templateParameter'])))
                for tp in type_['templateParameter']:
                    result += struct.pack("=BH",np.uint8(tp['isConstant']),np.uint16(tp['typeID']))
        return result

    def generateConstantSegment(self):
        result = bytearray()
        for const in self.constants:
            typeID = self.resolveTypeID(self.constants[const]['type'])
            # store type, namelen, name
            result += struct.pack("BB"+str(len(const))+"s",typeID,len(const),const.encode())
            # store value
            if typeID == 22:#ptr
                result += struct.pack("=BQ",8,self.constants[const]['value'])
            if typeID == 2:#u32
                result += struct.pack("L",self.constants[const]['value'])
            if typeID == 9:#i32
                result += struct.pack("L",self.constants[const]['value'])
            if typeID == 20:#strlit
                string = self.constants[const]['value']
                result += struct.pack("B"+str(len(string))+"s",len(string),string.encode())
        return result

    def generateImportSegment(self, library):
        result = bytearray()
        # library name
        result += struct.pack("B"+str(len(library))+"s",len(library),library.encode())
        # functions of the library
        for func in self.imports[library]:
            result += struct.pack("B"+str(len(func))+"s",len(func),func.encode())
        return result

    def resolveTypeID(self,id):
        if id >= FirstDynamicTypeID:
            for t in self.types:
                if self.types[t]['id'] == id:
                    result = self.resolveTypeID(self.types[t]['typeID'])
                    break
        else:
            result = id
        return result

    def getTypeString(self,id):
        result = ""
        type_ = None
        for t in self.types:
            if self.types[t]['id'] == id:
                type_ = self.types[t]
                break
        if type_ != None:
            if type_['isConstant']:
                result = 'const '
            id = self.getTypeName(type_['typeID'])
            if len(type_['templateParameter']) > 0:
                id += "<"
                for tt in type_['templateParameter'][:-1]:
                    if tt['isConstant']:
                        id+= "const "
                    id += self.getTypeName(tt['typeID'])+","
                tt = type_['templateParameter'][-1]
                if tt['isConstant']:
                    id+= "const "
                id += self.getTypeName(tt['typeID'])
                id += ">"
            result+= id
        return result

    def getTypeName(self,id):
        for t in self.types:
            if self.types[t]['id'] == id:
                return t

    def isImportFunction(self,name):
        for lib in self.imports.values():
            if name in lib:
                return True
        return False

    def getImportFunctionIndex(self,name):
        result = 0
        for lib in self.imports.values():
            for f in lib:
                if name == f:
                    return result
                result += 1
        return None

    def getConstIndex(self,value):
        result = 0
        for const in self.constants.values():
            if const['value'] == value:
                return result
            result += 1
        return None

    def getConstnameIndex(self,name):
        result = 0
        for const in self.constants.keys():
            if const == name:
                return result
            result += 1
        return None

    def read(self, bytes):
        offset = 0
        magic = np.frombuffer(bytes,np.uint32,1,offset)
        offset+=4
        if magic == MAGIC:
            while offset < len(bytes):
                segment = self.readSegment(bytes,offset)
                offset+=segment['size']+4
                if segment['id'] == 1:
                    self.code = segment['data']
                if segment['id'] == 0:
                    importSegment = self.parseImportSegment(segment)
                    if importSegment['lib'] != None and importSegment['functions'] != None:
                        if not importSegment['lib'] in self.imports.keys():
                            self.imports[importSegment['lib']] = []
                        self.imports[importSegment['lib']] += importSegment['functions']
                if segment['id'] == 2:
                    constSegment = self.parseConstSegment(segment)
                    for k in constSegment:
                        self.constants[k] = constSegment[k]
                if segment['id'] == 3:
                    typeSegment = self.parseTypeSegment(segment)
                    for t in typeSegment:
                        self.types[t] = typeSegment[t]
                if segment['id'] == 4:
                    dependencySegment = self.parseDependencySegment(segment)
                    for d in dependencySegment:
                        self.dependencies[d] = dependencySegment[d]
                if segment['id'] == 5:
                    functionSegment = self.parseFunctionSegment(segment)
                    for name in functionSegment:
                        self.functions[name] = functionSegment[name]
                if segment['id'] == 6:
                    structSegment = self.parseStructSegment(segment)
                    for name in structSegment:
                        self.structs[name] = structSegment[name]
                if segment['id'] == 7:
                    unresolvedTypeSegment = self.parseUnresolvedTypeSegment(segment)
                    for name in unresolvedTypeSegment:
                        self.unresolvedTypes[name] = unresolvedTypeSegment[name]

    def parseStructSegment(self, segment):
        data = segment['data']
        size = segment['size']
        result = {}
        offset = 0
        amount = np.frombuffer(data,np.uint8,1,offset)[0]
        offset += 1
        while offset < size:
            len = np.frombuffer(data,np.uint8,1,offset)[0]
            offset += 1
            text = np.frombuffer(data,np.uint8,len,offset)
            offset += len
            name = str(text,'ascii')
            id = np.frombuffer(data,np.uint16,1,offset)[0]
            offset += 2
            variableCount = np.frombuffer(data,np.uint16,1,offset)[0]
            offset += 2
            composeCount = np.frombuffer(data,np.uint16,1,offset)[0]
            offset += 2
            template_parameters = np.frombuffer(data,np.uint8,1,offset)[0]
            offset += 1
            variables = []
            compose = []
            for i in range(variableCount):
                order = np.frombuffer(data,np.uint16,1,offset)[0]
                offset+=2
                len = np.frombuffer(data,np.uint8,1,offset)[0]
                offset += 1
                text = np.frombuffer(data,np.uint8,len,offset)
                offset += len
                mname = str(text,'ascii')
                static = np.frombuffer(data,np.uint8, 1, offset)[0]
                offset += 1
                typeid = np.frombuffer(data,np.uint16,1,offset)[0]
                offset += 2
                if static != 0:
                    isStatic = True
                else:
                    isStatic = False
                variables.append({'order':order, 'name':mname, 'static':isStatic, 'typeid':typeid, 'decoration':[]})
            for i in range(composeCount):
                order = np.frombuffer(data,np.uint16,1,offset)[0]
                offset+=2
                len = np.frombuffer(data,np.uint8,1,offset)[0]
                offset += 1
                text = np.frombuffer(data,np.uint8,len,offset)
                offset += len
                mname = str(text,'ascii')
                compose.append({'order':order, 'name':mname})
            result[name] = {
                'id': id,
                'templateParameter':[],
                'variables':variables,
                'compose':compose
            }
        return result

    def parseFunctionSegment(self, segment):
        data = segment['data']
        size = segment['size']
        result = {}
        offset = 0
        amount = np.frombuffer(data,np.uint8,1,offset)[0]
        offset += 1
        while offset < size:
            len = np.frombuffer(data,np.uint8,1,offset)[0]
            offset += 1
            text = np.frombuffer(data,np.uint8,len,offset)
            offset += len
            name = str(text,'ascii')
            label = np.frombuffer(data,np.uint16,1,offset)[0]
            offset += 2
            result[name] = label
        return result

    def parseTypeSegment(self, segment):
        data = segment['data']
        size = segment['size']
        result = {}
        offset = 0
        while offset < size:
            len = np.frombuffer(data,np.uint8,1,offset)[0]
            offset += 1
            text = np.frombuffer(data,np.uint8,len,offset)
            offset += len
            name = str(text,'ascii')
            id = np.frombuffer(data,np.uint16,1,offset)[0]
            offset += 2
            typeID = np.frombuffer(data,np.uint16,1,offset)[0]
            offset += 2
            isConst = np.frombuffer(data,np.uint8,1,offset)[0] != 0
            offset += 1
            templateParameter = np.frombuffer(data,np.uint8,1,offset)[0]
            offset += 1            
            tp = []
            for i in range(templateParameter):
                isTConst = np.frombuffer(data, np.uint8, 1, offset)[0] != 0
                offset+=1
                tpTypeID = np.frombuffer(data,np.uint16,1,offset)[0]
                offset+=2
                tp.append(TP(isTConst,tpTypeID))
            result[name] = {
                'id': id,
                'isConstant': isConst,
                'typeID': typeID,
                'templateParameter':tp
            }
        return result

    def parseUnresolvedTypeSegment(self, segment):
        data = segment['data']
        size = segment['size']
        result = {}
        offset = 0
        amount = np.frombuffer(data,np.uint8,1,offset)[0]
        offset += 1
        while offset < size:
            len = np.frombuffer(data,np.uint8,1,offset)[0]
            offset += 1
            text = np.frombuffer(data,np.uint8,len,offset)
            offset += len
            name = str(text,'ascii')
            typeId = np.frombuffer(data,np.uint16,1,offset)[0]
            offset += 2
            result[name] = {'id':typeId}
        return result

    def parseDependencySegment(self, segment):
        data = segment['data']
        size = segment['size']
        result = {}
        offset = 0
        amount = np.frombuffer(data,np.uint8,1,offset)[0]
        offset+=1
        while offset < size:
            len = np.frombuffer(data,np.uint8,1,offset)[0]
            offset += 1
            text = np.frombuffer(data,np.uint8,len,offset)
            offset += len
            name = str(text,'ascii')
            result[name] = {}
        return result

    def parseConstSegment(self, segment):
        data = segment['data']
        size = segment['size']
        result = {}
        offset = 0
        while offset < size:
            typeID = np.frombuffer(data, np.uint8,1,offset)[0]
            offset += 1
            len = np.frombuffer(data,np.uint8,1,offset)[0]
            offset += 1
            text = np.frombuffer(data,np.uint8,len,offset)
            offset += len
            name = str(text,'ascii')
            value = None
            if typeID == 20:# strlit
                strlen = np.frombuffer(data,np.uint8,1,offset)[0]
                offset += 1
                text = np.frombuffer(data,np.uint8,strlen,offset)
                offset += strlen
                value = str(text,'ascii')
            if typeID == 9:# i32
                value = np.frombuffer(data,np.int32,1,offset)[0]
                offset += 4
            if typeID == 2:# u32
                value = np.frombuffer(data,np.uint32,1,offset)[0]
                offset += 4
            if typeID == 22:# ptr
                arrlen = np.frombuffer(data,np.uint8,1,offset)[0]
                offset += 1
                value = np.frombuffer(data,np.uint64,1,offset)[0]
                offset += 8
            result[name] = {'type':typeID, 'value': value}
        return result

    def parseImportSegment(self, segment):
        data = segment['data']
        size = segment['size']
        result = {}
        offset = 0
        len = np.frombuffer(data, np.uint8,1, offset)
        offset+=1
        text = np.frombuffer(data, np.uint8,len[0], offset)  
        offset+=len[0]
        result['lib'] = str(text,'ascii')
        result['functions'] = []
        while offset < size:
            len = np.frombuffer(data, np.uint8,1, offset)
            offset+=1
            text = np.frombuffer(data, np.uint8,len[0], offset)
            offset+=len[0]
            result['functions'].append(str(text, 'ascii'))
        return result

    def readSegment(self, bytes, offset):
        segmentHeader = np.frombuffer(bytes, np.uint16, 2,offset)
        offset+=4
        segmentData = np.frombuffer(bytes, np.uint8, segmentHeader[1],offset)
        return {'id' : segmentHeader[0], 'size': segmentHeader[1], 'data': segmentData}

    def setDefaultTypes(self):
        for type in types:
            self.types[type] = {
                'id': types[type],
                'isConstant': False,
                'typeID': types[type],
                'templateParameter':[]
            }
            

intrinsics = {
    "Breakpoint":np.uint8(0)
}

bc = {
# 1byte ops
    "Nop" : np.uint8(0),
    "ResolveAddrOfImportIndex" : np.uint8(1),
    "Return":np.uint8(2),
    "Add":np.uint8(3),
    "Subtract":np.uint8(4),
    "Multiply":np.uint8(5),
    "Divide":np.uint8(6),
    "Negate":np.uint8(7),
    "Modulo":np.uint8(8),
    "Power":np.uint8(9),
    "Equal":np.uint8(10),
    "Less":np.uint8(11),
    "LessEqual":np.uint8(12),
    "Not":np.uint8(13),
    "PushOne":np.uint8(14),
    "PushZero":np.uint8(15),
    "Increase":np.uint8(16),
    "Decrease":np.uint8(17),
    "PushConst":np.uint8(18),
    "ResolveAddrOfConstIndex":np.uint8(19),
    "Pop":np.uint8(20),
# 2byte ops
    "CallIntrinsic" : np.uint8(127),
    "PushU8": np.uint8(128),
    "JumpIf": np.uint8(129),
    "Label": np.uint8(130),
    "Goto": np.uint8(131),
    "Call" : np.uint8(132),
    "Copy": np.uint8(133),
# 3byte ops
    "PushU16": np.uint8(200),
    "Invoke": np.uint8(201),
    "Init": np.uint8(202),
#    "Copy": np.uint8(203),
#    "SizeOf": np.uint8(204),
#    "Store": np.uint8(205),
#    "Load": np.uint8(206),
# 5byte ops
    "PushU32": np.uint8(210),    
}
FirstTwoByteOperation = bc["CallIntrinsic"]
FirstThreeByteOperation = bc["PushU16"]
FirstFiveByteOperation = bc["PushU32"]

types = {
    "u8" : np.uint8(0),
    "u16" : np.uint8(1),
    "u32" : np.uint8(2),
    "u64" : np.uint8(3),
    "u128" : np.uint8(4),
    "u256" : np.uint8(5),
    "u512" : np.uint8(6),
    "i8" : np.uint8(7),
    "i16" : np.uint8(8),
    "i32" : np.uint8(9),
    "i64" : np.uint8(10),
    "i128" : np.uint8(11),
    "i256" : np.uint8(12),
    "i512" : np.uint8(13),
    "f16" : np.uint8(14),
    "f32" : np.uint8(15),
    "f64" : np.uint8(16),
    "f128" : np.uint8(17),
    "bool" : np.uint8(18),
    "uintptr" : np.uint8(19),
    "strlit":np.uint8(20),#count, bytearray
    "arr":np.uint8(21),#type,count,bytearray
    "ptr":np.uint8(22),#count,bytearray
    "simd":np.uint8(23),#Special padding:type,count,bytearray
    "void":np.uint8(24)
    # 25-63 reserved
    #64 dynamic types
}
FirstDynamicTypeID = 64