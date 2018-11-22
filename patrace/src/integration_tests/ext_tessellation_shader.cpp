#include "pa_demo.h"
#include "paframework_gl.h"

#ifdef PAFRAMEWORK_OPENGL
// Rename GLES extension functions to OpenGL functions
#define GL_TESS_CONTROL_SHADER_EXT GL_TESS_CONTROL_SHADER
#define GL_TESS_EVALUATION_SHADER_EXT GL_TESS_EVALUATION_SHADER
#define GL_PATCH_VERTICES_EXT GL_PATCH_VERTICES
#define GL_PATCHES_EXT GL_PATCHES

#define glPatchParameteriEXT glPatchParameteri

#endif

static const char * vs_source[] = GLSL_VS(
    void main(void)                                                  
    {                                                                 
    const vec4 vertices[] = vec4[](vec4(0.4, -0.4, 0.5, 1.0),
                                   vec4(-0.4, -0.4, 0.5, 1.0),
                                   vec4(0.4, 0.4, 0.5, 1.0),
                                   vec4(-0.4, 0.4, 0.5, 1.0));
        gl_Position = vertices[gl_VertexID];                          
    }                                                                 
);

static const char * tcs_source_triangles[] = GLSL_CONTROL(
    layout (vertices = 3) out;                                                    
    void main(void)                                                               
    {                                                                             
        if (gl_InvocationID == 0)                                                 
        {                                                                         
            gl_TessLevelInner[0] = 5.0;                                           
            gl_TessLevelOuter[0] = 8.0;                                           
            gl_TessLevelOuter[1] = 8.0;                                           
            gl_TessLevelOuter[2] = 8.0;                                           
        }                                                                         
        gl_out[gl_InvocationID].gl_Position = gl_in[gl_InvocationID].gl_Position; 
    }                                                                             
);

static const char * tes_source_triangles[] = GLSL_EVALUATE(
    layout (triangles) in;      
    flat out vec4 inColor;
    void main(void)                                           
    {                                                         
        gl_Position = (gl_TessCoord.x * gl_in[0].gl_Position) +
                      (gl_TessCoord.y * gl_in[1].gl_Position) +
                      (gl_TessCoord.z * gl_in[2].gl_Position);
        gl_Position.x = gl_Position.x * 0.5f + 0.5f;
        gl_Position.y = gl_Position.y * 0.5f - 0.5f;
        inColor = vec4(gl_TessCoord, 1.0f);
    }                                                         
);

static const char * tes_source_triangles_as_points[] = GLSL_EVALUATE(
    layout (triangles, point_mode) in;    
    flat out vec4 inColor;
    void main(void)                                           
    {                                                         
        gl_Position = (gl_TessCoord.x * gl_in[0].gl_Position) +
                      (gl_TessCoord.y * gl_in[1].gl_Position) +
                      (gl_TessCoord.z * gl_in[2].gl_Position);
        gl_Position.x = gl_Position.x * 0.5f - 0.5f;
        gl_Position.y = gl_Position.y * 0.5f + 0.5f;
        inColor = vec4(gl_TessCoord, 1.0f);
    }                                                         
);

static const char * tcs_source_quads[] = GLSL_CONTROL(
    layout (vertices = 4) out;                                                          
    void main(void)                                                              
    {                                                                            
        if (gl_InvocationID == 0)                                                
        {                                                                        
            gl_TessLevelInner[0] = 9.0;                                          
            gl_TessLevelInner[1] = 7.0;                                          
            gl_TessLevelOuter[0] = 3.0;                                          
            gl_TessLevelOuter[1] = 5.0;                                          
            gl_TessLevelOuter[2] = 3.0;                                          
            gl_TessLevelOuter[3] = 5.0;                                          
        }                                                                        
        gl_out[gl_InvocationID].gl_Position = gl_in[gl_InvocationID].gl_Position;
    }                                                                            
);

static const char * tes_source_quads[] = GLSL_EVALUATE(
    layout (quads) in; 
    flat out vec4 inColor;
    void main(void)                                                               
    {                                                                             
        vec4 p1 = mix(gl_in[0].gl_Position, gl_in[1].gl_Position, gl_TessCoord.x);
        vec4 p2 = mix(gl_in[2].gl_Position, gl_in[3].gl_Position, gl_TessCoord.x);
        gl_Position = mix(p1, p2, gl_TessCoord.y);
        gl_Position.x = gl_Position.x * 0.5f - 0.5f;
        gl_Position.y = gl_Position.y * 0.5f - 0.5f;
        inColor = vec4(gl_TessCoord, 1.0f);
    }                                                                             
);

static const char * tcs_source_isolines[] = GLSL_CONTROL(
    layout (vertices = 4) out;
    void main(void)                                                              
    {                                                                            
        if (gl_InvocationID == 0)                                                
        {                                                                        
            gl_TessLevelOuter[0] = 5.0                                          
            gl_TessLevelOuter[1] = 5.0;                                          
        }                                                                        
        gl_out[gl_InvocationID].gl_Position = gl_in[gl_InvocationID].gl_Position;
    }                                                                            
);

/*
static const char * tes_source_isolines[] =
{
"#version 420 core                                                                    \n"
"                                                                                     \n"
"layout (isolines, equal_spacing, cw) in;                                             \n"
"                                                                                     \n"
"void main(void)                                                                      \n"
"{                                                                                    \n"
"    vec4 p1 = mix(gl_in[0].gl_Position, gl_in[1].gl_Position, gl_TessCoord.x);       \n"
"    vec4 p2 = mix(gl_in[2].gl_Position, gl_in[3].gl_Position, gl_TessCoord.x);       \n"
"    gl_Position = mix(p1, p2, gl_TessCoord.y);                                       \n"
"}                                                                                    \n"
};
*/

static const char * tes_source_isolines[] = GLSL_EVALUATE(
    layout (isolines) in;                                                  
    flat out vec4 inColor;
    void main(void)                                                        
    {                                                                      
        float r = (gl_TessCoord.y + gl_TessCoord.x / gl_TessLevelOuter[0]);
        float t = gl_TessCoord.x * 2.0 * 3.14159;                          
        gl_Position = vec4(sin(t) * r * 0.5 + 0.5, cos(t) * r * 0.5 + 0.5, 0.5, 1.0);        
        gl_Position.x = gl_Position.x * 0.5f + 0.5f;
        gl_Position.y = gl_Position.y * 0.5f + 0.5f;
        inColor = vec4(gl_TessCoord, 1.0f);
    }                                                                      
);

static const char * fs_source[] = GLSL_FS(
    out vec4 color;
    flat in  vec4 inColor;
    void main(void)       
    {  
        color = inColor;
    }                     
);

static const char * const * vs_sources[] =
{
    vs_source, vs_source, vs_source, vs_source
};

static const char * const * tcs_sources[] =
{
    tcs_source_quads, tcs_source_triangles, tcs_source_triangles, tcs_source_isolines
};

static const char * const * tes_sources[] =
{
    tes_source_quads, tes_source_triangles, tes_source_triangles_as_points, tes_source_isolines
};

static const char * const * fs_sources[] =
{
    fs_source, fs_source, fs_source, fs_source
};


int width, height;

GLuint program[4], vao;

bool check_feature_availability()
{
#ifndef PAFRAMEWORK_OPENGL
    if (!PAFW_GL_Is_GLES_Extension_Supported("GL_EXT_tessellation_shader"))
    {
        PALOGE("The extention EXT_tessellation_shader not found -- this may not work\n");
    }
    return true; // try anyway, works on Nvidia desktop EGL
#else
    GLint major_version;
    GLint minor_version;
    int version;

    glGetIntegerv(GL_MAJOR_VERSION, &major_version);
    glGetIntegerv(GL_MINOR_VERSION, &minor_version);
    version = 100 * major_version + 10 * minor_version;

    if (version >= 430)
    {
        return true;
    }
    PALOGE("The OpenGLversion (currently %d) must be 430 or higher\n", version);
    return false;
#endif
}

static int setupGraphics(PAFW_HANDLE pafw_handle, int w, int h, void *user_data)
{
    setup();

    width = w;
    height = h;

    if (!check_feature_availability())
    {
        PALOGE("The extension EXT_gpu_shader5 is not available\n");
        return 1;
    }

    // setup space
    glViewport(0, 0, width, height);

    int i;
    
    for (i = 0; i < 4; i++)
    {
        program[i] = glCreateProgram();
        GLuint vs = glCreateShader(GL_VERTEX_SHADER);
        glShaderSource(vs, 1, vs_sources[i], NULL);
        glCompileShader(vs);

        GLuint tcs = glCreateShader(GL_TESS_CONTROL_SHADER_EXT);

        glShaderSource(tcs, 1, tcs_sources[i], NULL);
        glCompileShader(tcs);

        GLint success = 0;
        glGetShaderiv(tcs, GL_COMPILE_STATUS, &success);

        GLuint tes = glCreateShader(GL_TESS_EVALUATION_SHADER_EXT);
        glShaderSource(tes, 1, tes_sources[i], NULL);
        glCompileShader(tes);

        GLuint fs = glCreateShader(GL_FRAGMENT_SHADER);
        glShaderSource(fs, 1, fs_sources[i], NULL);
        glCompileShader(fs);

        glAttachShader(program[i], vs);
        glAttachShader(program[i], tcs);
        glAttachShader(program[i], tes);
        glAttachShader(program[i], fs);
        glLinkProgram(program[i]);

        glDeleteShader(vs);
        glDeleteShader(tcs);
        glDeleteShader(tes);
        glDeleteShader(fs);
    }

    glGenVertexArrays(1, &vao);
    glBindVertexArray(vao);

    glPatchParameteriEXT(GL_PATCH_VERTICES_EXT, 4);
    //glPolygonMode(GL_FRONT_AND_BACK, GL_LINE_EXT);

    return 0;
}



static void callback_draw(PAFW_HANDLE pafw_handle, void *user_data)
{
    PAGL(glClearColor(0.0f, 0.5f, 0.5f, 1.0f));
    PAGL(glClear(GL_DEPTH_BUFFER_BIT | GL_COLOR_BUFFER_BIT));

    //static const GLfloat black[] = { 0.0f, 0.0f, 0.0f, 1.0f };
    //glClearBufferfv(GL_COLOR, 0, black);

    for (int i = 0; i < 4; i++)
    {
        glUseProgram(program[i]);
        glDrawArrays(GL_PATCHES_EXT, 0, 4);
    }
    glStateDump_ARM();
    assert_fb(width, height);
}

static void test_cleanup(PAFW_HANDLE pafw_handle, void *user_data)
{
    glDeleteVertexArrays(1, &vao);

    for (int i = 0; i < 4; i++)
    {
        glDeleteProgram(program[i]);
    }
}

#include "paframework_android_glue.h"

int PAFW_Entry_Point(PAFW_HANDLE pafw_handle)
{
    return init("ext_tessellation_shader", pafw_handle, callback_draw, setupGraphics, test_cleanup);
}
