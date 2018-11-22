#!/usr/bin/env python2

import sys
import os
import xml.etree.ElementTree as ET
import getopt

script_dir = os.path.dirname(os.path.realpath(__file__))
gltree = ET.parse(os.path.join(script_dir, '../../../thirdparty/opengl-registry/xml/gl.xml'))
egltree = ET.parse(os.path.join(script_dir, '../../../thirdparty/egl-registry/api/egl.xml'))
glroot = gltree.getroot()
eglroot = egltree.getroot()
glcommands = {}
eglcommands = {}

# Parser for Khronos XML
def khronos_xml_parser(root, commands):
    for command in root.find('commands'):
        d = {}
        proto = command.find('proto')
        d['return_type_str'] = ''.join([text for text in proto.itertext()][:-1]).strip()
        d['function_name'] = proto.find('name').text
        d['name_list'] = list()
        for param in command.findall('param/name'):
            d['name_list'].append(param.text)
        p = [{"strlist": [text.strip() for text in param.itertext() if text.strip()],
              "length": param.attrib.get('len')}
            for param in command.findall('param')]

        for param in p:
            splitted = []
            for string in param['strlist']:
                for word in string.split():
                    splitted.append(word)
            param['strlist'] = splitted

        d['parameters'] = p

        commands[d['function_name']] = d

# Parse commands from XML and store them in globals
khronos_xml_parser(glroot, glcommands)
khronos_xml_parser(eglroot, eglcommands)

############################################################################
# generateSourceFile
def generateSourceFile(protos, folder, fname, pythonCmd, manual_imp_funcs, includes=[]):
    dirname = os.path.join(os.path.dirname(os.path.realpath(__file__)), folder)
    filename = os.path.join(dirname, fname)

    keys = protos.keys()
    keys.sort()

    if not os.path.exists(dirname):
        os.makedirs(dirname)

    with open(filename, "w") as f:
        f.write('// This code is auto-generated by: \n')
        f.write('// '+pythonCmd+'\n')
        f.write('#include "../common.h"\n\n')

        for include in includes:
            f.write('#include "' + include + '"\n')

        f.write("\nextern \"C\" {\n\n")

        if folder == 'gles1':
            f.write("typedef struct __GLsync *GLsync;\n")
            f.write("typedef uint64_t GLuint64;\n")
            f.write("typedef int64_t GLint64;\n")
        elif folder != 'egl':
            f.write("typedef GLDEBUGPROCKHR GLDEBUGPROC;\n")
            f.write("typedef void (*GLVULKANPROCNV)(void);\n")
        f.write('\n')

        # Output the function bodies of the intercept later
        # Each function must call the plugin version of the function
        for i in keys:
            if i in manual_imp_funcs:
                continue
            command = protos[i]
            param = [' '.join(p['strlist']) for p in command['parameters']]
            command['param_string'] = ', '.join(param)
            f.write('typedef {return_type_str} (*FUNCPTR_{function_name})({param_string});\n'.format(**command))
        f.write("\n")

        for i in keys:
            if i in manual_imp_funcs:
                continue
            command = protos[i]
            f.write('static FUNCPTR_{function_name} sp_{function_name} = 0;\n'.format(**command))
        f.write("\n")

        for i in keys:
            if i in manual_imp_funcs:
                continue
            command = protos[i]
            f.write('static bool warned_{function_name} = false;\n'.format(**command))
        f.write("\n")

        f.write("/// force new function lookups\n")
        f.write("__attribute__ ((unused)) static void fakedriverReset()\n{\n")
        for i in keys:
            if i in manual_imp_funcs:
                continue
            command = protos[i]
            f.write('    sp_{function_name} = 0;\n'.format(**command));
            f.write('    warned_{function_name} = false;\n'.format(**command));
        f.write("}\n\n")

        for i in keys:
            if i in manual_imp_funcs:
                continue
            command = protos[i]
            param = [' '.join(p['strlist']) for p in command['parameters']]
            command['param_string'] = ', '.join(param)
            f.write('PUBLIC {return_type_str} {function_name}({param_string});\n'.format(**command))
        f.write("\n")

        for i in keys:
            if i in manual_imp_funcs:
                continue
            command = protos[i]
            param = [' '.join(p['strlist']) for p in command['parameters']]
            command['param_string'] = ', '.join(param)
            command['call_list'] = ', '.join(command['name_list'])

            real_call = 'tmp({call_list})'.format(**command)
            returnValue = '{return_type_str}'.format(**command)
            hasReturnValue = returnValue.lower() != "void" or not returnValue

            f.write('{return_type_str} {function_name}({param_string})\n'.format(**command))
            f.write("{\n")
            if i == 'eglInitialize':
                f.write("    fakedriverReset(); // forcibly break any OS caching of these functions\n")
            # need temporary for thread-safety in case of reentrancy or dispatch table is cleared
            f.write('    FUNCPTR_{function_name} tmp = sp_{function_name};\n'.format(**command))
            f.write('    if (tmp != 0)\n')
            f.write('    {\n')
            if i == 'eglSwapBuffers':
                f.write('        if (wrapper::CWrapper::sShowFPS)\n')
                f.write('        {\n')
                f.write('            gFpsLog.SwapBufferHappens();\n')
                f.write('        }\n')
            f.write('        return ' + real_call + ';\n')
            f.write('    }\n')
            f.write('    tmp = (FUNCPTR_{function_name}) wrapper::CWrapper::GetProcAddress("{function_name}");\n'.format(**command))
            f.write('    if (tmp == 0)\n')
            f.write('    {\n')
            if i.startswith('eglSwapBuffersWithDamage'):
                # On the Nexus 6P with Android N, the Adreno drivers does not support eglSwapBuffersWithDamageKHR;
                # eglGetProcAddress(..) will return NULL and the symbol is not exported by the lib.
                # However, the fakdriver *does* export this symbol, and it appears Android N will try to call this
                # function despite first trying eglGetProcAddress(...) which properly returns NULL.
                # The result is that no swapping occurs, and the Android UI isn't updated on the phone.
                # As a workaround, we here try calling 'normal' eglSwapBuffers() if WithDamage* is NULL but
                # is still called.
                f.write('        if (!warned_{function_name}) DBG_LOG("Warning: Fakedriver failed to get function pointer for {function_name}. eglSwapBuffers() will be called instead.\\n");\n'.format(**command))
                f.write('        // Try calling normal eglSwapBuffers(). See autogencode.py for details why.\n')
                f.write('        eglSwapBuffers(dpy, surface);\n')
            else:
                f.write('        if (!warned_{function_name}) DBG_LOG("Warning: Fakedriver failed to get function pointer for {function_name}\\n");\n'.format(**command))
            f.write('        warned_{function_name} = true;\n'.format(**command))
            if (hasReturnValue):
                f.write('        return 0;\n')
            else:
                f.write('        return;\n')
            f.write('    }\n')
            f.write('    sp_{function_name} = tmp;\n'.format(**command))
            f.write('    return ' + real_call + ';\n')
            f.write("}\n\n")
        f.write("} // end of extern C")

    print 'Generated %s/%s' % (folder, fname)

    return 0

def GenerateWrapper(headerDir, pythonCmd, manual_imp_funcs):
    all_commands = {}
    all_includes = list()

    # EGL
    sum_commands = {}
    includes = ['EGL/egl.h', 'EGL/eglext.h', 'fps_log.hpp']
    generateSourceFile(eglcommands, 'egl', 'auto.cpp', pythonCmd, manual_imp_funcs, includes)
    all_commands.update(eglcommands)
    all_includes.extend(includes)

    # GLES2+
    # We need to include GLES2+ before GLES1 because glext.h contains a subset of KHR_debug
    # but with identical include guards...
    sum_commands = {}
    includes = ['GLES2/gl2.h', 'GLES2/gl2ext.h', 'GLES3/gl3.h', 'GLES3/gl31.h', 'GLES3/gl32.h']
    for version in ['GL_ES_VERSION_2_0', 'GL_ES_VERSION_3_0', 'GL_ES_VERSION_3_1', 'GL_ES_VERSION_3_2']:
        for command in glroot.findall("feature[@name='{v}']/require/command".format(v=version)):
            command_name = command.get('name')
            sum_commands[command_name] = glcommands[command_name]
    for ext in glroot.findall("extensions/extension"):
        if 'gles2' in ext.get('supported') or 'gles3' in ext.get('supported'):
            for require in ext.findall("require"):
                api = require.get('api', None)
                if api != None and api != 'gles2' and api != 'gles3':
                    continue
                for command in require.findall("command"):
                    command_name = command.get('name')
                    sum_commands[command_name] = glcommands[command_name]
    generateSourceFile(sum_commands, 'gles2', 'auto.cpp', pythonCmd, manual_imp_funcs, includes)
    all_commands.update(sum_commands)
    all_includes.extend(includes)

    # GLES1
    sum_commands = {}
    includes = ['GLES/gl.h', 'GLES/glext.h']
    for version in ['GL_VERSION_ES_CM_1_0']:
        for command in glroot.findall("feature[@name='{v}']/require/command".format(v=version)):
            command_name = command.get('name')
            sum_commands[command_name] = glcommands[command_name]
    for ext in glroot.findall("extensions/extension"):
        if 'gles1' in ext.get('supported'):
            for require in ext.findall("require"):
                api = require.get('api', None)
                if api != None and api != 'gles1':
                    continue
                for command in require.findall("command"):
                    command_name = command.get('name')
                    sum_commands[command_name] = glcommands[command_name]
        elif not ext.get('supported'):
            print 'No supported attribute for extension %s' % ext.get('name')
    generateSourceFile(sum_commands, 'gles1', 'auto.cpp', pythonCmd, manual_imp_funcs, includes)
    all_commands.update(sum_commands)
    all_includes.extend(includes)

    # single .so file
    generateSourceFile(all_commands, 'single', 'auto.cpp', pythonCmd, manual_imp_funcs, all_includes)

    return 0

def usage():
    print "Generate wrapper libraries based on khronos XML"
    print "Options:"
    print "-h Path to the khronos headers (Default = '../../../thirdparty/opengl-registry/api/'"

if __name__ == '__main__':
    opts = None
    args = None
    script_dir = os.path.dirname(os.path.realpath(__file__))
    headerDir   = os.path.join(script_dir, "../../../thirdparty/opengl-registry/api")

    try:
        opts,args = getopt.getopt(sys.argv[1:], "h:", ["help"])
    except getopt.GetoptError, err:
        print str(err)
        usage()
        sys.exit(0)

    # Parse options:
    for o, a in opts:
        print o, a
        if o == '-h':
            headerDir = a
        elif o == "--help":
            usage()
            sys.exit(0)

    pythonCmd = 'python autogencode.py'
    manual_imp_funcs = [ 'eglGetProcAddress', 'eglStreamConsumerGLTextureExternalAttribsNV' ]
    GenerateWrapper(headerDir, pythonCmd, manual_imp_funcs)
