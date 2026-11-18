// SPDX-License-Identifier: GPL-2.0-only
/* Offscreen texture/shader/readback correctness test, independent of screen lock.
 * Run as the normal desktop user. This does not prove every desktop workload.
 */
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <GLES2/gl2.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define W 128
#define BYTES (W * W * 4)
static void fail(const char *what) { fprintf(stderr, "%s: EGL=%#x GL=%#x\n", what, eglGetError(), glGetError()); exit(1); }
static GLuint shader(GLenum type, const char *source)
{
    GLuint s = glCreateShader(type);
    GLint ok;
    glShaderSource(s, 1, &source, NULL);
    glCompileShader(s);
    glGetShaderiv(s, GL_COMPILE_STATUS, &ok);
    if (!ok) { char log[2048]; glGetShaderInfoLog(s, sizeof(log), NULL, log); fprintf(stderr, "%s\n", log); fail("shader compilation"); }
    return s;
}
static void pressure_color(unsigned index, unsigned char *color)
{
    color[0] = (index * 17) & 255;
    color[1] = (index * 37) & 255;
    color[2] = (index * 61 + (index >> 8) * 53) & 255;
    color[3] = 255;
}
static void pressure_verify(GLuint texture, unsigned index, unsigned char *output)
{
    unsigned char color[4]; pressure_color(index, color);
    glBindTexture(GL_TEXTURE_2D, texture);
    glDrawArrays(GL_TRIANGLE_STRIP, 0, 4); glFinish();
    glReadPixels(0, 0, W, W, GL_RGBA, GL_UNSIGNED_BYTE, output);
    if (glGetError() != GL_NO_ERROR) fail("pressure render/readback");
    for (unsigned i = 0; i < BYTES; i++)
        if (output[i] != color[i % 4]) fail("pressure texture mismatch");
}
int main(int argc, char **argv)
{
    unsigned pressure_mib = 0;
    if (argc != 1) {
        char *end = NULL;
        unsigned long value = argc == 3 ? strtoul(argv[2], &end, 10) : 0;
        if (argc != 3 || strcmp(argv[1], "--pressure-mib") || !end || *end || value < 32 || value > 1024) {
            fprintf(stderr, "Usage: %s [--pressure-mib 32..1024]\n", argv[0]); return 2;
        }
        pressure_mib = (unsigned)value;
    }
    PFNEGLGETPLATFORMDISPLAYEXTPROC get_platform = (void *)eglGetProcAddress("eglGetPlatformDisplayEXT");
    if (!get_platform) fail("no platform display extension");
    EGLDisplay d = get_platform(EGL_PLATFORM_SURFACELESS_MESA, EGL_DEFAULT_DISPLAY, NULL);
    EGLint attrs[] = { EGL_SURFACE_TYPE, EGL_PBUFFER_BIT, EGL_RENDERABLE_TYPE, EGL_OPENGL_ES2_BIT,
        EGL_RED_SIZE, 8, EGL_GREEN_SIZE, 8, EGL_BLUE_SIZE, 8, EGL_ALPHA_SIZE, 8, EGL_NONE };
    EGLConfig cfg; EGLint count;
    if (!eglInitialize(d, NULL, NULL) || !eglBindAPI(EGL_OPENGL_ES_API) ||
        !eglChooseConfig(d, attrs, &cfg, 1, &count) || count != 1) fail("EGL configuration");
    EGLint size[] = { EGL_WIDTH, W, EGL_HEIGHT, W, EGL_NONE };
    EGLint version[] = { EGL_CONTEXT_CLIENT_VERSION, 2, EGL_NONE };
    EGLSurface surface = eglCreatePbufferSurface(d, cfg, size);
    EGLContext ctx = eglCreateContext(d, cfg, EGL_NO_CONTEXT, version);
    if (surface == EGL_NO_SURFACE || ctx == EGL_NO_CONTEXT || !eglMakeCurrent(d, surface, surface, ctx)) fail("EGL context");
    const char *renderer = (const char *)glGetString(GL_RENDERER);
    printf("renderer=%s\n", renderer ? renderer : "unknown");
    if (!renderer || !strstr(renderer, "Mali")) fail("requires physical Mali renderer; software result rejected");
    GLuint p = glCreateProgram();
    glAttachShader(p, shader(GL_VERTEX_SHADER, "attribute vec2 pos; varying vec2 uv; void main(){uv=(pos+1.0)*0.5; gl_Position=vec4(pos,0.0,1.0);}"));
    glAttachShader(p, shader(GL_FRAGMENT_SHADER, "precision highp float; varying vec2 uv; uniform sampler2D tex; void main(){gl_FragColor=texture2D(tex,uv);}"));
    glBindAttribLocation(p, 0, "pos"); glLinkProgram(p);
    GLint linked; glGetProgramiv(p, GL_LINK_STATUS, &linked);
    if (!linked) fail("program link");
    glUseProgram(p); glUniform1i(glGetUniformLocation(p, "tex"), 0);
    const GLfloat vertices[] = { -1,-1, 1,-1, -1,1, 1,1 };
    glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 0, vertices); glEnableVertexAttribArray(0);
    GLuint tex; glGenTextures(1, &tex); glBindTexture(GL_TEXTURE_2D, tex);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
    glDisable(GL_DITHER); glDisable(GL_BLEND); glViewport(0, 0, W, W);
    unsigned char input[BYTES], output[BYTES];
    GLuint *pool = NULL;
    if (pressure_mib) {
        /* One 512x512 RGBA texture has 1MiB nominal pixel data; retain every live GL object. */
        unsigned char *data = malloc(1U << 20);
        pool = calloc(pressure_mib, sizeof(*pool));
        if (!data || !pool) fail("pressure allocation");
        glGenTextures(pressure_mib, pool);
        for (unsigned t = 0; t < pressure_mib; t++) {
            unsigned char color[4]; pressure_color(t, color);
            for (unsigned i = 0; i < (1U << 20); i++) data[i] = color[i % 4];
            glBindTexture(GL_TEXTURE_2D, pool[t]);
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, 512, 512, 0, GL_RGBA, GL_UNSIGNED_BYTE, data);
            if (glGetError() != GL_NO_ERROR) fail("pressure texture upload");
            pressure_verify(pool[t], t, output);
        }
        free(data);
        glBindTexture(GL_TEXTURE_2D, tex);
    }
    for (unsigned frame = 0; frame < 100; frame++) {
        for (unsigned i = 0; i < BYTES; i++) input[i] = (i * 37 + (i >> 8) + frame * 19) & 255;
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, W, W, 0, GL_RGBA, GL_UNSIGNED_BYTE, input);
        glDrawArrays(GL_TRIANGLE_STRIP, 0, 4); glFinish();
        /* Leave GPU-written data unread across runtime idle. Reading before
         * sleeping can flush it and hide loss during core/domain power-off.
         * Keep the surface/context/texture alive; do not upload or redraw. */
        if (frame % 10 == 9) usleep(250000);
        glReadPixels(0, 0, W, W, GL_RGBA, GL_UNSIGNED_BYTE, output);
        if (glGetError() != GL_NO_ERROR) fail("render/readback");
        if (memcmp(input, output, BYTES)) { fprintf(stderr, "pixel mismatch frame=%u\n", frame); return 1; }
    }
    printf("PASS frames=100 compared_bytes=%u mismatches=0\n", 100 * BYTES);
    if (pool) {
        /* Recheck all retained textures after allocation churn and idle. */
        for (unsigned t = 0; t < pressure_mib; t++) pressure_verify(pool[t], t, output);
        printf("PRESSURE_PASS live_texture_mib=%u mismatches=0\n", pressure_mib);
        glDeleteTextures(pressure_mib, pool); free(pool);
    }
    glDeleteTextures(1, &tex); glDeleteProgram(p);
    eglMakeCurrent(d, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT);
    eglDestroyContext(d, ctx); eglDestroySurface(d, surface); eglTerminate(d);
    return 0;
}
