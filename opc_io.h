#ifndef OPC_IO_H
#define OPC_IO_H

/*
 * opc_io.h — file-reading runtime for the OPC / SimplC language.
 *
 * Bundled and auto-included by transpiler.py (just like stb_ds.h) whenever a
 * program uses read_file / read_lines / read_files. You never include it by
 * hand. It is portable by default and picks an operating-system-specific fast
 * path automatically.
 *
 *   SimplC                      strategy / mechanism
 *   --------------------------- -----------------------------------------------
 *   read_file(path)             whole file, sequential, large blocks  (read())
 *   read_file(path, "mmap")     zero-copy memory map, random access   (mmap)
 *   read_file(path, "pread")    positioned reads, large file          (pread)
 *   read_file(path, "stream")   buffered standard I/O                 (fread)
 *   read_file(path, "uring")    io_uring chunked read (Linux opt-in)
 *   read_lines(path)            -> list[char*]   line-oriented text   (getline)
 *   read_files(paths)           -> list[OpcFile] many files at once   (io_uring)
 *
 * read_file / read_files yield an OpcFile { data, size, ok }. Release each one
 * with file_close(f) — it frees or unmaps as appropriate. read_lines yields a
 * dynamic list[char*]; release it with free_lines(list).
 *
 * Linux io_uring is opt-in to keep the default build dependency-free. Enable it
 * by compiling with:   -DOPC_USE_URING -luring
 *
 * The array-returning helpers (read_lines / read_files) require stb_ds.h and
 * are only compiled when stb_ds.h has been included first (the transpiler
 * guarantees the ordering).
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

#if defined(__GNUC__) || defined(__clang__)
  #define OPC_UNUSED __attribute__((unused))
#else
  #define OPC_UNUSED
#endif

typedef struct OpcFile {
    char *data;   /* file bytes; NUL-terminated except for the "mmap" strategy */
    long  size;   /* number of bytes in `data` (the convenience NUL is extra)  */
    int   ok;     /* 1 on success, 0 on failure                                */
    /* --- internal bookkeeping for file_close(); do not read or write --- */
    int   _opc_mapped;
    void *_opc_base;
    long  _opc_maplen;
#if defined(_WIN32)
    void *_opc_fh;
    void *_opc_mh;
#endif
} OpcFile;

#if defined(_WIN32)
  #include <windows.h>
#elif defined(__unix__) || defined(__APPLE__) || defined(__linux__)
  #define OPC_POSIX 1
  #include <errno.h>
  #include <fcntl.h>
  #include <unistd.h>
  #include <sys/stat.h>
  #include <sys/mman.h>
#endif

static OPC_UNUSED OpcFile opc__file_fail(void) {
    OpcFile f;
    memset(&f, 0, sizeof(f));
    f.ok = 0;
    return f;
}

static OPC_UNUSED int opc__streq(const char *a, const char *b) {
    return a && b && strcmp(a, b) == 0;
}

/* Portable buffered fallback — works on every host with <stdio.h>. */
static OPC_UNUSED OpcFile opc__read_stdio(const char *path) {
    OpcFile f = opc__file_fail();
    FILE *fp = fopen(path, "rb");
    if (!fp) return f;
    if (fseek(fp, 0, SEEK_END) != 0) { fclose(fp); return f; }
    long n = ftell(fp);
    if (n < 0) { fclose(fp); return f; }
    rewind(fp);
    char *buf = (char *) malloc((size_t) n + 1);
    if (!buf) { fclose(fp); return f; }
    size_t got = fread(buf, 1, (size_t) n, fp);
    fclose(fp);
    buf[got] = '\0';
    f.data = buf;
    f.size = (long) got;
    f.ok = 1;
    return f;
}

#if defined(OPC_POSIX)
/* POSIX whole-file read. `use_pread` selects positioned reads; `want_mmap`
 * memory-maps the file (zero-copy) and falls back to a buffered read on
 * failure. */
static OPC_UNUSED OpcFile opc__read_posix(const char *path, int use_pread, int want_mmap) {
    OpcFile f = opc__file_fail();
    int fd = open(path, O_RDONLY);
    if (fd < 0) return f;
    struct stat st;
    if (fstat(fd, &st) != 0) { close(fd); return f; }
    long n = (long) st.st_size;

    if (want_mmap && n > 0) {
        void *m = mmap(NULL, (size_t) n, PROT_READ, MAP_PRIVATE, fd, 0);
        if (m != MAP_FAILED) {
            close(fd);
            f.data = (char *) m;
            f.size = n;
            f.ok = 1;
            f._opc_mapped = 1;
            f._opc_base = m;
            f._opc_maplen = n;
            return f;
        }
        /* mmap failed — fall through to a buffered read */
    }

    char *buf = (char *) malloc((size_t) n + 1);
    if (!buf) { close(fd); return f; }
    long off = 0;
    while (off < n) {
        ssize_t r;
        if (use_pread) r = pread(fd, buf + off, (size_t) (n - off), off);
        else           r = read(fd, buf + off, (size_t) (n - off));
        if (r < 0) {
            if (errno == EINTR) continue;
            free(buf); close(fd); return f;
        }
        if (r == 0) break; /* unexpected EOF (file shrank under us) */
        off += r;
    }
    close(fd);
    buf[off] = '\0';
    f.data = buf;
    f.size = off;
    f.ok = 1;
    return f;
}
#endif /* OPC_POSIX */

#if defined(_WIN32)
static OPC_UNUSED OpcFile opc__read_win_mmap(const char *path) {
    OpcFile f = opc__file_fail();
    HANDLE fh = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL,
                            OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (fh == INVALID_HANDLE_VALUE) return f;
    LARGE_INTEGER sz;
    if (!GetFileSizeEx(fh, &sz)) { CloseHandle(fh); return f; }
    if (sz.QuadPart == 0) { CloseHandle(fh); f.ok = 1; return f; }
    HANDLE mh = CreateFileMappingA(fh, NULL, PAGE_READONLY, 0, 0, NULL);
    if (!mh) { CloseHandle(fh); return f; }
    void *view = MapViewOfFile(mh, FILE_MAP_READ, 0, 0, 0);
    if (!view) { CloseHandle(mh); CloseHandle(fh); return f; }
    f.data = (char *) view;
    f.size = (long) sz.QuadPart;
    f.ok = 1;
    f._opc_mapped = 1;
    f._opc_base = view;
    f._opc_maplen = (long) sz.QuadPart;
    f._opc_fh = fh;
    f._opc_mh = mh;
    return f;
}
#endif /* _WIN32 */

/* Dispatch a single-file read by strategy string. Unknown strategies fall back
 * to "auto" so a typo never breaks a build, only its performance profile. */
static OPC_UNUSED OpcFile opc_read_file(const char *path, const char *strategy) {
    if (!strategy) strategy = "auto";
#if defined(OPC_POSIX)
    if (opc__streq(strategy, "mmap"))
        return opc__read_posix(path, 0, 1);
    if (opc__streq(strategy, "pread"))
        return opc__read_posix(path, 1, 0);
    if (opc__streq(strategy, "stream") || opc__streq(strategy, "fread"))
        return opc__read_stdio(path);
    /* "uring" on a single file is no faster than a positioned read, so it maps
     * to pread; io_uring earns its keep across many files (read_files). */
    if (opc__streq(strategy, "uring"))
        return opc__read_posix(path, 1, 0);
    return opc__read_posix(path, 0, 0); /* auto / read / blocks */
#elif defined(_WIN32)
    if (opc__streq(strategy, "mmap"))
        return opc__read_win_mmap(path);
    return opc__read_stdio(path);
#else
    (void) strategy;
    return opc__read_stdio(path);
#endif
}

static OPC_UNUSED void opc_file_close(OpcFile f) {
    if (!f.data) return;
    if (f._opc_mapped) {
#if defined(OPC_POSIX)
        munmap(f._opc_base, (size_t) f._opc_maplen);
#elif defined(_WIN32)
        UnmapViewOfFile(f._opc_base);
        if (f._opc_mh) CloseHandle((HANDLE) f._opc_mh);
        if (f._opc_fh) CloseHandle((HANDLE) f._opc_fh);
#endif
    } else {
        free(f.data);
    }
}

/* ── array-returning helpers (require stb_ds.h, included first) ──────────── */
#ifdef INCLUDE_STB_DS_H

/* Read a text file into a dynamic list of NUL-terminated lines (newline
 * stripped). Returns NULL if the file cannot be opened. */
static OPC_UNUSED char **opc_read_lines(const char *path) {
    char **lines = NULL;
    FILE *fp = fopen(path, "r");
    if (!fp) return NULL;
#if defined(OPC_POSIX)
    char *line = NULL;
    size_t cap = 0;
    ssize_t len;
    while ((len = getline(&line, &cap, fp)) != -1) {
        while (len > 0 && (line[len - 1] == '\n' || line[len - 1] == '\r'))
            line[--len] = '\0';
        char *copy = (char *) malloc((size_t) len + 1);
        if (copy) { memcpy(copy, line, (size_t) len + 1); arrput(lines, copy); }
    }
    free(line);
#else
    char buf[65536];
    while (fgets(buf, (int) sizeof(buf), fp)) {
        size_t len = strlen(buf);
        while (len > 0 && (buf[len - 1] == '\n' || buf[len - 1] == '\r'))
            buf[--len] = '\0';
        char *copy = (char *) malloc(len + 1);
        if (copy) { memcpy(copy, buf, len + 1); arrput(lines, copy); }
    }
#endif
    fclose(fp);
    return lines;
}

static OPC_UNUSED void opc_free_lines(char **lines) {
    long i, n = (long) arrlen(lines);
    for (i = 0; i < n; i++) free(lines[i]);
    arrfree(lines);
}

#if defined(OPC_POSIX) && defined(OPC_USE_URING)
#include <liburing.h>
/* Submit one read per file through io_uring and reap them as they complete —
 * this is the path that keeps an NVMe queue full when reading many files. */
static OPC_UNUSED OpcFile *opc__read_files_uring(char **paths) {
    long n = (long) arrlen(paths), i;
    OpcFile *out = NULL;
    struct io_uring ring;
    if (io_uring_queue_init((unsigned) (n > 0 ? n : 1), &ring, 0) < 0) {
        for (i = 0; i < n; i++) arrput(out, opc_read_file(paths[i], "auto"));
        return out;
    }
    int  *fds   = (int  *) calloc((size_t) n, sizeof(int));
    long *sizes = (long *) calloc((size_t) n, sizeof(long));
    char **bufs = (char **) calloc((size_t) n, sizeof(char *));
    long pending = 0;
    for (i = 0; i < n; i++) {
        fds[i] = open(paths[i], O_RDONLY);
        sizes[i] = -1;
        if (fds[i] < 0) continue;
        struct stat st;
        if (fstat(fds[i], &st) != 0) continue;
        sizes[i] = (long) st.st_size;
        bufs[i] = (char *) malloc((size_t) sizes[i] + 1);
        if (!bufs[i]) continue;
        struct io_uring_sqe *sqe = io_uring_get_sqe(&ring);
        io_uring_prep_read(sqe, fds[i], bufs[i], (unsigned) sizes[i], 0);
        io_uring_sqe_set_data(sqe, (void *) (intptr_t) i);
        pending++;
    }
    io_uring_submit(&ring);
    while (pending > 0) {
        struct io_uring_cqe *cqe;
        if (io_uring_wait_cqe(&ring, &cqe) < 0) break;
        long idx = (long) (intptr_t) io_uring_cqe_get_data(cqe);
        int res = cqe->res;
        if (res >= 0 && bufs[idx]) {
            long off = res;
            while (off < sizes[idx]) { /* finish any short read */
                ssize_t r = pread(fds[idx], bufs[idx] + off,
                                   (size_t) (sizes[idx] - off), off);
                if (r <= 0) break;
                off += r;
            }
            bufs[idx][off] = '\0';
            sizes[idx] = off;
        }
        io_uring_cqe_seen(&ring, cqe);
        pending--;
    }
    for (i = 0; i < n; i++) {
        OpcFile f;
        memset(&f, 0, sizeof(f));
        if (bufs[i]) { f.data = bufs[i]; f.size = sizes[i]; f.ok = 1; }
        arrput(out, f);
        if (fds[i] >= 0) close(fds[i]);
    }
    free(fds); free(sizes); free(bufs);
    io_uring_queue_exit(&ring);
    return out;
}
#endif /* OPC_POSIX && OPC_USE_URING */

/* Read many files, returning a list[OpcFile] in the same order as `paths`. On
 * Linux built with -DOPC_USE_URING they are issued concurrently via io_uring;
 * everywhere else they are read one after another. */
static OPC_UNUSED OpcFile *opc_read_files(char **paths) {
#if defined(OPC_POSIX) && defined(OPC_USE_URING)
    return opc__read_files_uring(paths);
#else
    OpcFile *out = NULL;
    long i, n = (long) arrlen(paths);
    for (i = 0; i < n; i++) arrput(out, opc_read_file(paths[i], "auto"));
    return out;
#endif
}

#endif /* INCLUDE_STB_DS_H */

#endif /* OPC_IO_H */
