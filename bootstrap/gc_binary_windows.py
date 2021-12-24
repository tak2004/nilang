from enum import Enum
from io import BytesIO
import io
import numpy as np

class Imports:
    def __init__(self, sectionAddr):
        self.addr = sectionAddr
        self.libs = []
        self.flt = {}

    def addLibraryFunctions(self, libname, functions):
        lib = {}
        lib['name'] = libname
        lib['functions'] = functions
        self.libs.append(lib)

    def generate(self):
        # Calculate the size of the descriptor list.
        # dataBytes counts the bytes of the whole section
        dataBytes = 20 # one zero filled description entry must for termination
        dataBytes += len(self.libs)*20 # description entry
        offsetToDataSection = dataBytes
        # points to the absolute addr of the first lookup table
        lookupTable = self.addr + offsetToDataSection
        # counts the bytes of a lookup table
        totalLookupTableSize = 0
        libnameOffset = 0
        # point to the absolute addr of the library name list
        librarynameOffset = lookupTable # start in data section
        # point to the absolute addr of the function name list
        functionnameOffset = lookupTable # start in the data section
        for lib in self.libs:
            lib['lookupTable'] = lookupTable
            # calculate the bytes needed for the lookup table of this library
            lookupTableSize = (len(lib['functions'])+1)*8
            lookupTable += lookupTableSize
            totalLookupTableSize += lookupTableSize
            dataBytes += lookupTableSize # import lookup table
            lib['nameOffset'] = libnameOffset
            librarynameBytes = len(lib['name']) + 1
            libnameOffset += librarynameBytes                 
            dataBytes += librarynameBytes #library names
            functionnameBytes = 0
            for f in lib['functions']:
                functionnameBytes += len(f) + 3
            dataBytes += functionnameBytes #function names
            # add the size of both lookup tables and the function names
            librarynameOffset += lookupTableSize + functionnameBytes
            functionnameOffset += lookupTableSize
        
        # generate a memory buffer for the whole data
        stream = BytesIO()
        # write descriptor list
        for lib in self.libs:
            stream.write(np.uint32(lib['lookupTable']))
            stream.write(np.uint32(0))#time stamp
            stream.write(np.uint32(0))#forwarder chain
            stream.write(np.uint32(lib['nameOffset'] + librarynameOffset))
            stream.write(np.uint32(lib['lookupTable']))
        stream.write(bytearray(20))
        
        # write data
        ## write import lookup table
        functionnameBytes = 0
        for lib in self.libs: 
            offset = lib['lookupTable']           
            for f in lib['functions']:
                self.flt[f] = offset
                offset += 8
                stream.write(np.uint64(functionnameBytes+functionnameOffset))
                functionnameBytes += len(f) + 3
            stream.write(np.uint64(0))
        ## write import functions
        for lib in self.libs:
            for f in lib['functions']:
                stream.write(np.uint16(0))
                stream.write(f.encode('ascii'))
                stream.write(np.uint8(0))
        ## write import libraries
        for lib in self.libs:
            stream.write(lib['name'].encode('ascii'))
            stream.write(np.uint8(0))
        self.buffer = stream.getbuffer().tobytes()

class SectionTable:
    def __init__(self, imgBytes, memBytes, imgOffset, memOffset):
        self.sections = {}
        self.imgBytes = imgBytes
        self.memBytes = memBytes
        self.imgOffset = imgOffset
        self.memOffset = memOffset

    def add(self,name,flags):
        section = {}
        section['name'] = name.encode('ascii')
        section['flags'] = flags
        section['imgBytes'] = self.imgBytes
        section['imgOffset'] = self.imgOffset
        section['memBytes'] = self.memBytes
        section['memOffset'] = self.memOffset
        self.sections[name] = section
        self.updateOffsets()

    def setSize(self, name, bytes):
        self.sections[name]['imgBytes'] = int((bytes + (self.imgBytes-1))/self.imgBytes)*self.imgBytes
        self.sections[name]['memBytes'] = int((bytes + (self.memBytes-1))/self.memBytes)*self.memBytes
        self.updateOffsets()

    def updateOffsets(self):
        imgOffset = self.imgOffset
        memOffset = self.memOffset
        for sectionKey in self.sections:
            s = self.sections[sectionKey]
            s['imgOffset'] = imgOffset
            s['memOffset'] = memOffset
            imgOffset += s['imgBytes']
            memOffset += s['memBytes']
    
    def get(self, name):
        return self.sections[name]
    
    def getTable(self):
        return self.sections

#https://docs.microsoft.com/en-us/windows/win32/debug/pe-format
def linker(f,arch):
    base = 0x400000
    sections = SectionTable(512,0x1000,512,0x1000)
    sections.add(".rdata",SectionFlags.Initialized | SectionFlags.Read)
    sections.add(".text",SectionFlags.Code | SectionFlags.Execute | SectionFlags.Read)
    sections.add(".data",SectionFlags.Initialized | SectionFlags.Write | SectionFlags.Read)
    
    imports = Imports(sections.get(".rdata")['memOffset'])
    imports.addLibraryFunctions("kernel32.dll", ["ExitProcess"])
    imports.addLibraryFunctions("user32.dll", ["MessageBoxA"])
    imports.generate()
    sections.setSize(".rdata",len(imports.buffer))    

    # write header
    writeDOSHeader(f)
    writePEHeader(f,arch)
    writeOptionalHeaders(f,arch,sections.get(".text")['memOffset'])
    writeDataDirectories(f, sections.get(".rdata")['memOffset'])
    writeSectionsTable(f,arch, sections.getTable())
    # write sections
    writeCode(f, arch, base, imports.flt, sections.get(".text")['imgOffset'])
    f.seek(sections.get(".rdata")['imgOffset'])
    f.write(imports.buffer)
    writeData(f,sections.get(".data")['imgOffset'],sections.get(".data")['imgBytes'])

def writeDOSHeader(f): # 64 bytes
    constantSignature = bytearray(32)
    constantSignature[0] = 0x4D
    constantSignature[1] = 0x5a
    f.write(constantSignature)
    offsetPEHeader = bytearray(32)
    offsetPEHeader[28] = 0x40
    f.write(offsetPEHeader)

class Machine(np.uint16,Enum):
    AMD64 = 0x8664
    ARM = 0x01c0
    ARM64 = 0xaa64
    ARMNT = 0x01c4
    I386 = 0x014c
    IA64 = 0x0200

class Characteristic(np.uint16,Enum):
    EXE = 0x22

#also known as COFF
def writePEHeader(f,arch): # 18 bytes
    f.write(np.uint32(0x4550)) # Signature
    if arch == 32:
        f.write(Machine.I386) # Machine 2b
    else:
        f.write(Machine.AMD64)
    f.write(np.uint16(3)) # NumberOfSections 2b
    f.write(np.uint32(0)) # TimeDateStamp 4b
    f.write(np.uint32(0)) # PointerTosymbolTable 4b
    f.write(np.uint32(0)) # NumberOfSymbols 4b
    if arch == 32:
        f.write(np.uint16(0xe0)) # SizeOfOptionalHeader 2b
    else:
        f.write(np.uint16(0xf0))
    f.write(Characteristic.EXE) # Characteristics 2b

class OptionalHeadertype(np.uint16,Enum):
    PE32 = 0x010b
    PE32plus = 0x020b

def writeOptionalHeaders(f,arch,codeOffset):
    if arch == 32:        
        writePE32(f,codeOffset)
    else:
        writePE32plus(f,codeOffset)

def writePE32(f,codeOffset):
    f.write(OptionalHeadertype.PE32)
    f.write(np.uint8(0)) # MajorLinkerVersion
    f.write(np.uint8(0)) # MinorLinkerVersion
    f.write(np.uint32(512)) # SizeOfCode
    f.write(np.uint32(0)) # SizeOfInitializedData
    f.write(np.uint32(0)) # SizeOfUninitializedData
    f.write(np.uint32(codeOffset)) # AddresOfEntryPoint
    f.write(np.uint32(codeOffset)) # BaseOfCode
    f.write(np.uint32(0)) # BaseOfData
    f.write(np.uint32(0x400000)) # ImageBase
    f.write(np.uint32(0x1000)) # SectionAlignment
    f.write(np.uint32(0x200)) # FileAlignment
    f.write(np.uint16(0x6)) # MajorOperatingSystemVersion
    skip = bytearray(6)
    f.write(skip)
    f.write(np.uint16(0x6)) # MajorSubsystemVersion
    skip = bytearray(6)
    f.write(skip)
    f.write(np.uint32(0x4000)) # SizeOfImage
    f.write(np.uint32(0x200)) # SizeOfHeaders
    f.write(np.uint32(0))
    f.write(np.uint16(2)) # Subsystem
    f.write(np.uint16(0x400)) # DllCharacteristics
    f.write(np.uint32(0x100000)) # SizeOfStackReserve
    f.write(np.uint32(0x1000)) # SizeOfStackCommit
    f.write(np.uint32(0x100000)) # SizeOfHeapReserve
    f.write(np.uint32(0x1000)) # SizeOfHeapCommit
    f.write(np.uint32(0)) # LoaderFlags must be 0
    f.write(np.uint32(16)) # NumberOfRvaAndSizes

def writePE32plus(f,codeOffset):
    f.write(OptionalHeadertype.PE32plus)
    f.write(np.uint8(0)) # MajorLinkerVersion
    f.write(np.uint8(0)) # MinorLinkerVersion
    f.write(np.uint32(512)) # SizeOfCode
    f.write(np.uint32(0)) # SizeOfInitializedData
    f.write(np.uint32(0)) # SizeOfUninitializedData
    f.write(np.uint32(codeOffset)) # AddresOfEntryPoint
    f.write(np.uint32(codeOffset)) # BaseOfCode
    f.write(np.uint64(0x400000)) # ImageBase
    f.write(np.uint32(0x1000)) # SectionAlignment
    f.write(np.uint32(0x200)) # FileAlignment
    f.write(np.uint16(0x6)) # MajorOperatingSystemVersion
    skip = bytearray(6)
    f.write(skip)
    f.write(np.uint16(0x6)) # MajorSubsystemVersion
    skip = bytearray(6)
    f.write(skip)
    f.write(np.uint32(0x4000)) # SizeOfImage
    f.write(np.uint32(0x200)) # SizeOfHeaders
    f.write(np.uint32(0))
    f.write(np.uint16(2)) # Subsystem
    f.write(np.uint16(0x400)) # DllCharacteristics
    f.write(np.uint64(0x100000)) # SizeOfStackReserve
    f.write(np.uint64(0x1000)) # SizeOfStackCommit
    f.write(np.uint64(0x100000)) # SizeOfHeapReserve
    f.write(np.uint64(0x1000)) # SizeOfHeapCommit
    f.write(np.uint32(0)) # LoaderFlags must be 0
    f.write(np.uint32(16)) # NumberOfRvaAndSizes

def writeDataDirectories(f,offset):
    skip = bytearray(8)
    f.write(skip)
    f.write(np.uint32(offset)) # ImportsVA
    f.write(np.uint32(0))
    skip = bytearray(8*10)
    f.write(skip)
    f.write(np.uint32(0))
    f.write(np.uint32(0))

class SectionFlags(np.uint32,Enum):
    Read = 0x40000000
    Write = 0x80000000
    Execute = 0x20000000
    Code = 0x00000020
    Initialized = 0x00000040

def writeSectionsTable(f,arch,sections):
    if arch == 32:
        f.seek(0x138)
    else:
        f.seek(0x148)
    for sectionKey in sections:
        section = sections[sectionKey]
        writeSection(f,section['name'],section['memBytes'],section['memOffset'],section['imgBytes'],section['imgOffset'],section['flags'])

def writeSection(f,name, vsize, vaddr, rawsize,rawptr, flags):
    sname = bytearray(8-len(name))
    f.write(name)
    f.write(sname)
    f.write(np.int32(vsize))# VirtualSize
    f.write(np.int32(vaddr))# VirtualAddress
    f.write(np.int32(rawsize))# SizeOfRawData
    f.write(np.int32(rawptr))# PointerToRawData
    skip = bytearray(12)
    f.write(skip)
    f.write(np.uint32(flags))# Characteristics

def writeCode(f,arch,base,flt,offset):
    f.seek(offset)
    if arch == 64:
        # sub rsp, 0x28
        f.write(np.uint8(0x48))
        f.write(np.uint8(0x83))
        f.write(np.uint8(0xec))
        f.write(np.uint8(0x28))
        # mov r9d, 0
        f.write(np.uint16(0xb941))
        f.write(np.uint32(0))
        # mov r8d, 0x403000
        f.write(np.uint16(0xb841))
        f.write(np.uint32(0x403000))
        # mov edx, 0x40301B
        f.write(np.uint8(0xba))
        f.write(np.uint32(0x40301b))
        # mov ecx, 0
        f.write(np.uint8(0xb9))
        f.write(np.uint32(0))
        # call [0x402088]
        f.write(np.uint8(0xff))
        f.write(np.uint16(0x2514))
        f.write(np.uint32(flt['MessageBoxA']+base))
        # mov ecx, 0 
        f.write(np.uint8(0xb9))
        f.write(np.uint32(0))
        # call [0x402078]
        f.write(np.uint8(0xff))
        f.write(np.uint16(0x2514))
        f.write(np.uint32(flt['ExitProcess']+base))
    else:
        f.write(np.uint8(0x6a))
        f.write(np.uint8(0))
        f.write(np.uint8(0x68))
        f.write(np.uint32(0x403000))
        f.write(np.uint8(0x68))
        f.write(np.uint32(0x403017))
        f.write(np.uint8(0x6a))
        f.write(np.uint8(0))
        f.write(np.uint16(0x15ff))
        f.write(np.uint32(0x402070))
        f.write(np.uint8(0))
        f.write(np.uint16(0x15ff))
        f.write(np.uint32(0x402068))

def writeData(f,offset,bytes):
    f.seek(offset)
    f.write(b"a simple 64b PE executable")
    f.write(np.uint8(0))
    f.write(b"Hello world!")
    f.write(np.uint8(0))
    f.seek(offset+bytes-1)
    f.write(np.int8(0))