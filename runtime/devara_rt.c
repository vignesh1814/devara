/* Devara runtime library (plan §C, P1–P11, P22).
 *
 * Calling convention: every value is passed/returned as a 64-bit integer
 * (bool/char widened: bool 0/1, char sign-extended) or a double (f64).
 *
 * A padham value is a pointer to  { int64_t refcnt; int64_t len; char bytes[len + 1]; }
 * or NULL (= the empty string).  Strings are reference counted:
 *   - every runtime function that produces a padham returns an owned (+1) reference;
 *   - arguments of runtime functions are borrowed (never consumed);
 *   - refcnt < 0 marks an immortal string (literals, see dv_rt_strlit): retain/release
 *     ignore it and it is not counted as live;
 *   - dv_rt_retain / dv_rt_release are the only functions that change a count.
 * Heap arrays (dv_rt_newarray) are freed explicitly by compiler-generated code at scope exit
 * (dv_rt_freearray / dv_rt_freearray_str); constant-size arrays live in the caller's frame.
 *
 * Leak accounting: the runtime counts live heap arrays and strings; with the environment
 * variable DEVARA_RT_STATS=1, dv_rt_shutdown (called at the end of the program entry,
 * i.e. at normal exit only) prints "devara-rt: live=<n>" to stderr.
 */
#if defined(_WIN32) && !defined(__USE_MINGW_ANSI_STDIO)
#define __USE_MINGW_ANSI_STDIO 1   /* C99 printf/scanf: %g, %lld identical to glibc */
#endif
#include <errno.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif

typedef struct dv_str { int64_t refcnt; int64_t len; char bytes[]; } dv_str;

#define DV_IMMORTAL (-1)

static int64_t live_arrays = 0;
static int64_t live_strings = 0;

/* Called once by the generated `main`: byte-exact standard streams on Windows (no CRLF translation). */
void dv_rt_init(void) {
#ifdef _WIN32
    _setmode(_fileno(stdin), _O_BINARY);
    _setmode(_fileno(stdout), _O_BINARY);
    _setmode(_fileno(stderr), _O_BINARY);
#endif
}

/* ── errors (P11) ── */

static void fail(const char *msg) __attribute__((noreturn));
static void fail(const char *msg) {
    fflush(stdout);
    fprintf(stderr, "devara: runtime error: %s\n", msg);
    exit(1);
}

void dv_rt_trap_div0(void)   { fail("division by zero"); }
void dv_rt_trap_rem0(void)   { fail("remainder by zero"); }
void dv_rt_trap_divovf(void) { fail("integer overflow in division"); }

void dv_rt_checkdim(int64_t n) {
    if (n < 1) fail("invalid array size");
}

void *dv_rt_newarray(int64_t n) {
    if (n < 1 || (uint64_t)n > SIZE_MAX / 8) fail("invalid array size");
    void *p = calloc((size_t)n, 8);
    if (!p) fail("invalid array size");
    live_arrays++;
    return p;
}

/* ── reference counting (P22) ── */

void dv_rt_retain(dv_str *s) {
    if (s && s->refcnt > 0) s->refcnt++;
}

void dv_rt_release(dv_str *s) {
    if (!s || s->refcnt < 0) return;
    if (--s->refcnt == 0) {
        live_strings--;
        free(s);
    }
}

/* Release every padham element of an n-element array and reset it to "" (NULL). */
void dv_rt_release_elems(dv_str **p, int64_t n) {
    if (!p) return;
    for (int64_t i = 0; i < n; i++) {
        dv_rt_release(p[i]);
        p[i] = NULL;
    }
}

/* Free a heap array obtained from dv_rt_newarray. */
void dv_rt_freearray(void *p) {
    if (!p) return;
    live_arrays--;
    free(p);
}

/* Same for an array of padham: release the n elements first. */
void dv_rt_freearray_str(dv_str **p, int64_t n) {
    dv_rt_release_elems(p, n);
    dv_rt_freearray(p);
}

/* Called once at the end of the program entry (normal exit only). */
void dv_rt_shutdown(void) {
    const char *e = getenv("DEVARA_RT_STATS");
    if (e && e[0] == '1' && e[1] == 0) {
        fflush(stdout);
        fprintf(stderr, "devara-rt: live=%lld\n", (long long)(live_arrays + live_strings));
        fflush(stderr);
    }
}

/* ── output (P1–P6): every value is followed by '\n' ── */

void dv_rt_output_i64(int64_t v)  { printf("%lld\n", (long long)v); }
void dv_rt_output_f64(double v)   { printf("%g\n", v); }
void dv_rt_output_bool(int64_t v) { fputs(v ? "nijam\n" : "abaddham\n", stdout); }
void dv_rt_output_char(int64_t v) { putchar((unsigned char)v); putchar('\n'); }
void dv_rt_output_str(const dv_str *s) {
    if (s && s->len > 0) fwrite(s->bytes, 1, (size_t)s->len, stdout);
    putchar('\n');
}

/* ── input (P7–P10): own character stream with unbounded pushback ── */

static int *pushback = NULL;
static size_t npush = 0, cap_push = 0;
static int after_token = 0; /* previous input operation was a token read (P9) */

static int in_get(void) { return npush > 0 ? pushback[--npush] : getc(stdin); }
static void in_unget(int c) {
    if (c == EOF) return;
    if (npush == cap_push) {
        cap_push = cap_push ? cap_push * 2 : 64;
        pushback = realloc(pushback, cap_push * sizeof(int));
    }
    pushback[npush++] = c;
}

static int is_space(int c) { return c == ' ' || c == '\t' || c == '\n' || c == '\r' || c == '\v' || c == '\f'; }

static char *read_token(size_t *len_out) {
    int c;
    do { c = in_get(); } while (c != EOF && is_space(c));
    if (c == EOF) fail("invalid input");
    size_t cap = 64, n = 0;
    char *buf = malloc(cap);
    while (c != EOF && !is_space(c)) {
        if (n + 2 > cap) { cap *= 2; buf = realloc(buf, cap); }
        buf[n++] = (char)c;
        c = in_get();
    }
    in_unget(c);
    buf[n] = 0;
    *len_out = n;
    after_token = 1;
    return buf;
}

int64_t dv_rt_input_i64(void) {
    size_t n;
    char *t = read_token(&n);
    size_t i = 0;
    if (t[i] == '+' || t[i] == '-') i++;
    if (i >= n) fail("invalid input");
    for (size_t k = i; k < n; k++)
        if (t[k] < '0' || t[k] > '9') fail("invalid input");
    errno = 0;
    char *end;
    long long v = strtoll(t, &end, 10);
    if (errno == ERANGE || *end != 0) fail("invalid input");
    free(t);
    return (int64_t)v;
}

double dv_rt_input_f64(void) {
    size_t n;
    char *t = read_token(&n);
    char *end;
    double v = strtod(t, &end);
    if (end == t || *end != 0) fail("invalid input");
    free(t);
    return v;
}

int64_t dv_rt_input_bool(void) {
    size_t n;
    char *t = read_token(&n);
    for (size_t i = 0; i < n; i++) if (t[i] >= 'A' && t[i] <= 'Z') t[i] += 32;
    int64_t r;
    if (!strcmp(t, "nijam") || !strcmp(t, "1")) r = 1;
    else if (!strcmp(t, "abaddham") || !strcmp(t, "0")) r = 0;
    else fail("invalid input");
    free(t);
    return r;
}

int64_t dv_rt_input_char(void) {
    int c;
    do { c = in_get(); } while (c != EOF && is_space(c));
    if (c == EOF) fail("invalid input");
    after_token = 1;
    return (int64_t)(signed char)c;
}

/* A fresh owned (+1) string of n bytes copied from p. */
static dv_str *make_str(const char *p, int64_t n) {
    dv_str *s = malloc(sizeof(dv_str) + (size_t)n + 1);
    if (!s) fail("out of memory");
    live_strings++;
    s->refcnt = 1;
    s->len = n;
    if (n) memcpy(s->bytes, p, (size_t)n);
    s->bytes[n] = 0;
    return s;
}

dv_str *dv_rt_input_str(void) {
    if (after_token) {
        /* skip the rest of the current line if it only holds whitespace (P9) */
        size_t cap = 16, ns = 0;
        int *saved = malloc(cap * sizeof(int));
        int c;
        for (;;) {
            c = in_get();
            if (c == ' ' || c == '\t' || c == '\r' || c == '\v' || c == '\f') {
                if (ns == cap) { cap *= 2; saved = realloc(saved, cap * sizeof(int)); }
                saved[ns++] = c;
                continue;
            }
            if (c == '\n' || c == EOF) ns = 0;   /* whitespace-only remainder: consumed */
            else in_unget(c);                   /* real content: keep the leading blanks */
            break;
        }
        while (ns > 0) in_unget(saved[--ns]);
        free(saved);
        after_token = 0;
    }
    int c = in_get();
    if (c == EOF) fail("invalid input");
    size_t cap = 64, n = 0;
    char *buf = malloc(cap);
    while (c != EOF && c != '\n') {
        if (n + 2 > cap) { cap *= 2; buf = realloc(buf, cap); }
        buf[n++] = (char)c;
        c = in_get();
    }
    if (c == '\n' && n > 0 && buf[n - 1] == '\r') n--;   /* CRLF line ending */
    dv_str *s = make_str(buf, (int64_t)n);
    free(buf);
    return s;
}

/* ── padham operations ── */

static int64_t slen(const dv_str *s) { return s ? s->len : 0; }

/* A string literal arrives as the compiler's read-only constant { int64_t len; char bytes[len+1]; }
 * (no header). Returns the immortal runtime object for it; called once per literal at startup. */
typedef struct dv_lit { int64_t len; char bytes[]; } dv_lit;

dv_str *dv_rt_strlit(const dv_lit *lit) {
    int64_t n = lit->len;
    dv_str *s = malloc(sizeof(dv_str) + (size_t)n + 1);
    if (!s) fail("out of memory");
    s->refcnt = DV_IMMORTAL;
    s->len = n;
    if (n) memcpy(s->bytes, lit->bytes, (size_t)n);
    s->bytes[n] = 0;
    return s;
}

dv_str *dv_rt_strcat(dv_str *a, dv_str *b) {
    int64_t la = slen(a), lb = slen(b);
    if (lb == 0) { dv_rt_retain(a); return a; }     /* x + "": share; still an owned reference */
    if (la == 0) { dv_rt_retain(b); return b; }
    dv_str *s = malloc(sizeof(dv_str) + (size_t)(la + lb) + 1);
    if (!s) fail("out of memory");
    live_strings++;
    s->refcnt = 1;
    s->len = la + lb;
    memcpy(s->bytes, a->bytes, (size_t)la);
    memcpy(s->bytes + la, b->bytes, (size_t)lb);
    s->bytes[la + lb] = 0;
    return s;
}

int64_t dv_rt_streq(const dv_str *a, const dv_str *b) {
    int64_t la = slen(a), lb = slen(b);
    return la == lb && (la == 0 || memcmp(a->bytes, b->bytes, (size_t)la) == 0);
}

int64_t dv_rt_strlen(const dv_str *s) { return slen(s); }

int64_t dv_rt_strindex(const dv_str *s, int64_t i) {
    if (i < 0 || i >= slen(s)) fail("string index out of range");
    return (int64_t)(signed char)s->bytes[i];
}

dv_str *dv_rt_char2str(int64_t c) {
    char ch = (char)c;
    return make_str(&ch, 1);
}

int64_t dv_rt_str2char(const dv_str *s) {
    if (slen(s) != 1) fail("invalid char conversion");
    return (int64_t)(signed char)s->bytes[0];
}
