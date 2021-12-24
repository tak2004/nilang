import os
from multiprocessing import Pool
from gc_parser import parse
from nilang_interpreter import *
from nilang_ir import *
import sys

def print_parse(arg):
    print('Process:' + arg)
    return parse(open(arg,'r'))

if __name__ == '__main__':
    runInVM = False
    module = 'gc_cache/main.gc.nimo'
    files = []
    for i, arg in enumerate(sys.argv):
        if arg.endswith('.gc'):
            files.append(arg)
        elif arg == 'run':
            runInVM = True
    if len(files) == 0:
        files = os.listdir()
    pool = Pool(5)
    input = []
    units = []
    os.makedirs('gc_cache', exist_ok=True)
    for f in files:
        if f.endswith('.gc'):
            input.append(f)
    print('Process units')
    processed = pool.map(print_parse, input)

    if not all(processed):
        print('skip compiling')
        exit(1)

    if runInVM:
        bytes = open(module,'rb').read()
        vm = VM()
        vm.AddMainModule(bytes)
        vm.Run()

#    irModule = IRModule()
#    irModule.addImport('User32.dll','MessageBoxA')
#    irModule.addImport('Kernel32.dll','ExitProcess')
#
#    irModule.addType('LPCSTR',False,types['ptr'],[TP(True,types['u8'])])#64
#    tid = irModule.addType('HANDLE',False,types['ptr'],[TP(False,types['void'])])#65
#    irModule.addType('HWND',False,tid,[])#66
#
#    irModule.addConstant('HWND_DESKTOP',types['ptr'],0)
#    irModule.addConstant('MB_YESNO',types['u32'],4)
#    irModule.addConstant('MB_OK',types['u32'],0)
#    irModule.addConstant('IDYES',types['i32'],6)
#    __s0 = irModule.addConstant('__s0',types['strlit'],'hello')
#    __s1 = irModule.addConstant('__s1',types['strlit'],'World')
#    __s2 = irModule.addConstant('__s2',types['strlit'],'Bob')
#
#    irModule.code += bytearray([
#        bc["PushZero"],# 0!=1
#        bc["PushOne"],
#        bc["Equal"],
#        bc["Not"],
#        bc["JumpIf"],0,# if 0!=1 then jump to label 0
#        bc["PushZero"],
#        bc["ResolveAddrOfImportIndex"],# MessageBoxA
#        bc["PushZero"],
#        bc["PushU8"],__s0,
#        bc["ResolveAddrOfConstIndex"],# __s0
#        bc["PushU8"],__s1,
#        bc["ResolveAddrOfConstIndex"],# __s1
#        bc["PushZero"],
#        bc["Call"],
#        bc["Pop"],
#        bc["Label"],0,# jump label 0
#        bc["PushOne"],
#        bc["ResolveAddrOfImportIndex"],# ExistProcess
#        bc["PushZero"],
##        bc["CallIntrinsic"],intrinsics["Breakpoint"],
#        bc["Call"]
#    ])
#    byteCode = irModule.generate()
#
#    vm = VM()
#    vm.AddModule(byteCode)
#    vm.Run()
    #print('Compile units')
    #compiled = pool.map(print_compile, units)
    #merge = {}
    #for unit in compiled:
    #    if not unit['name'] in merge:
    #        merge[unit['name']] = []
    #    merge[unit['name']].append(unit)
    #for pkgname in merge:
    #    pkgfile = open(pkgname,'w')
    #    for unit in merge[pkgname]:
    #        pkgfile.write('# '+unit['file']+'\n')
    #        #pkgfile.write(unit['code'])
    #    pkgfile.close()
    
    #print('Linker generates binary')
    #binary = open('test.exe','wb+')
    #linker(binary,64)
    #binary.close()