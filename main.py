#!/usr/bin/env python3
"""coolest-art-01 FINAL: ECLIPSE — black hole accretion disk over deep space.
Python 3.13, stdlib only. Deterministic. Writes /output/entry.png (or $MAKEFUN_OUTPUT_DIR).
Final: 768x768, tuned ring (orange-gold, doppler-brightened) + lensing arcs + starfield.
"""
import math, os, struct, zlib

W = 768
H = 768

# ---------- tiny deterministic RNG ----------
def _hash(x, y, s):
    h = (x * 374761393 + y * 668265263 + s * 144665) & 0xFFFFFFFF
    h = (h ^ (h >> 13)) * 1274126177 & 0xFFFFFFFF
    return ((h ^ (h >> 16)) & 0xFFFFFFFF) / 4294967295.0

def noise2(x, y):
    xi, yi = math.floor(x), math.floor(y)
    xf, yf = x - xi, y - yi
    u = xf * xf * (3 - 2 * xf)
    v = yf * yf * (3 - 2 * yf)
    a = _hash(xi, yi, 7); b = _hash(xi + 1, yi, 7)
    c = _hash(xi, yi + 1, 7); d = _hash(xi + 1, yi + 1, 7)
    return (a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v)

def fbm(x, y):
    return (noise2(x, y) * 0.55 + noise2(x * 2.13, y * 2.13) * 0.28
            + noise2(x * 4.31, y * 4.31) * 0.17)

def clamp(v, a=0.0, b=1.0):
    return a if v < a else (b if v > b else v)

def smooth(t, e0, e1):
    t = clamp((t - e0) / (e1 - e0))
    return t * t * (3 - 2 * t)

def heat(t):
    """Black -> deep red -> orange -> gold -> white."""
    t = clamp(t)
    r = clamp(t * 3.0)
    g = clamp(t * 3.0 - 1.0) * 0.92 + clamp(t * 2.0 - 1.4) * 0.35
    b = clamp(t * 3.0 - 2.0)
    return (r, min(1.0, g), b)

# ---------- precomputed fields (fast bilinear sampling) ----------
def _grid(fn, gw, gh):
    return [fn(x / (gw - 1), y / (gh - 1)) for y in range(gh) for x in range(gw)]

def _sample(grid, gw, gh, u, v):
    u = clamp(u); v = clamp(v)
    fx = u * (gw - 1); fy = v * (gh - 1)
    x0 = int(fx); y0 = int(fy)
    x1 = min(x0 + 1, gw - 1); y1 = min(y0 + 1, gh - 1)
    tx = fx - x0; ty = fy - y0
    a = grid[y0 * gw + x0]; b = grid[y0 * gw + x1]
    c = grid[y1 * gw + x0]; d = grid[y1 * gw + x1]
    return a + (b - a) * tx + (c - a) * ty + (a - b - c + d) * tx * ty

NEB = _grid(lambda u, v: fbm((u * 0.8 - v * 0.6) * 3.6 + 5.0, (u * 0.6 + v * 0.8) * 3.6 + 2.0), 96, 96)
NEB2 = _grid(lambda u, v: fbm((u * 0.6 + v * 0.8) * 6.8 - 2.0, (u * -0.8 + v * 0.6) * 6.8 + 7.0), 96, 96)
# disk turbulence in (angle, radius) space
TURB = _grid(lambda u, v: fbm(u * 14.0 + 3.0, v * 9.0 - 1.0), 256, 64)

# ---------- render ----------
def render(w, h):
    buf = bytearray(w * h * 3)
    cx, cy = w * 0.5, h * 0.52
    R = w * 0.5
    cos_t, sin_t = math.cos(0.42), math.sin(0.42)
    sqrt = math.sqrt; atan2 = math.atan2; exp = math.exp
    sin = math.sin; cos = math.cos
    xs = [(x - cx) / R for x in range(w)]
    # star brightness grid (96x96)
    STAR = [_hash(x, y, 99) for y in range(96) for x in range(96)]
    for y in range(h):
        dy = (y - cy) / R
        row = y * w * 3
        vy = (dy + 1.0) * 0.5
        if vy < 0.0: vy = 0.0
        elif vy > 1.0: vy = 1.0
        fy = vy * 95.0
        y0 = int(fy); y1 = y0 + 1 if y0 < 95 else 95
        ty = fy - y0
        arcv = _arcv(dy)
        sy = int((y / h) * 96)
        for xi, dx in enumerate(xs):
            d = sqrt(dx * dx + dy * dy)
            ang = atan2(dy, dx)
            # nebula bilinear (96x96)
            fx = (dx + 1.0) * 0.5 * 95.0
            x0 = int(fx); x1 = x0 + 1 if x0 < 95 else 95
            tx = fx - x0
            i00 = y0 * 96 + x0; i01 = y0 * 96 + x1
            i10 = y1 * 96 + x0; i11 = y1 * 96 + x1
            a = NEB[i00]; b = NEB[i01]; c = NEB[i10]; e = NEB[i11]
            neb = a + (b - a) * tx + (c - a) * ty + (a - b - c + e) * tx * ty
            a = NEB2[i00]; b = NEB2[i01]; c = NEB2[i10]; e = NEB2[i11]
            neb2 = a + (b - a) * tx + (c - a) * ty + (a - b - c + e) * tx * ty
            r = 0.030 + neb * 0.14 + neb2 * 0.06
            g = 0.034 + neb * 0.09 + neb2 * 0.13
            b = 0.10 + neb * 0.26 + neb2 * 0.22
            fd = d - 0.6
            if fd > 0.0:
                f2 = 1.0 - 0.35 * fd
                r *= f2; g *= f2; b *= 1.0 - 0.30 * fd
            # --- stars ---
            sx = int((xi / w) * 96)
            sv = STAR[sy * 96 + sx]
            if sv > 0.95:
                fx2 = (xi / w) * 96 - sx; fy2 = (y / h) * 96 - sy
                dd = (fx2 - 0.5) ** 2 + (fy2 - 0.5) ** 2
                br = (1.0 - dd * 14.0)
                if br > 0.0:
                    br *= (sv - 0.95) * 26.0
                    tw = 0.75 + 0.25 * sin(xi * 0.11 + y * 0.07)
                    r += br * tw; g += br * tw; b += br * tw * 1.05
            # --- accretion disk ---
            ex = dx * cos_t - dy * sin_t
            ey = dx * sin_t + dy * cos_t
            er = sqrt(ex * ex + ey * ey * 3.4)
            ea = atan2(ey * 1.84, ex)
            # turb bilinear in (angle, radius): 256x64
            tu = (ea / 6.283185307179586 + 0.5) % 1.0
            tv = er / 0.75
            if tv > 1.0: tv = 1.0
            fx3 = tu * 255.0; fy3 = tv * 63.0
            x0 = int(fx3); x1 = x0 + 1 if x0 < 255 else 255
            y0 = int(fy3); y1 = y0 + 1 if y0 < 63 else 63
            tx = fx3 - x0; ty2 = fy3 - y0
            j00 = y0 * 256 + x0; j01 = y0 * 256 + x1
            j10 = y1 * 256 + x0; j11 = y1 * 256 + x1
            a = TURB[j00]; bb = TURB[j01]; c = TURB[j10]; e = TURB[j11]
            turb = a + (bb - a) * tx + (c - a) * ty2 + (a - bb - c + e) * tx * ty2
            # band: smoothstep(er, .235, .285) * (1 - smoothstep(er, .335, .46))
            t = (er - 0.345) / 0.055
            if t < 0.0: t = 0.0
            elif t > 1.0: t = 1.0
            s1 = t * t * (3 - 2 * t)
            t = (er - 0.46) / 0.14
            if t < 0.0: t = 0.0
            elif t > 1.0: t = 1.0
            s2 = t * t * (3 - 2 * t)
            band = s1 * (1.0 - s2) * (0.72 + 0.55 * turb)
            dop = 1.0 + 0.55 * cos(ea)
            glow = exp(-abs(er - 0.42) * 8.0) * 0.8
            disk = (band * 1.9 + glow) * dop
            ht = 0.08 + band * 0.52 + glow * 0.15 + 0.35 * (1.0 - s2) * s1
            if ht > 1.0: ht = 1.0
            hr = ht * 3.0
            if hr > 1.0: hr = 1.0
            hg = ht * 3.0 - 1.0
            if hg < 0.0: hg = 0.0
            elif hg > 1.0: hg = 1.0
            hg = hg * 0.92 + (ht * 2.0 - 1.4 if ht * 2.0 - 1.4 > 0.0 else 0.0) * 0.35
            if hg > 1.0: hg = 1.0
            hb = ht * 3.0 - 2.0
            if hb < 0.0: hb = 0.0
            elif hb > 1.0: hb = 1.0
            r += hr * disk; g += hg * disk; b += hb * disk
            # --- lensing arcs ---
            dd2 = d - 0.46
            arc = exp(-(dd2 * dd2) / 0.00045)
            arc *= 0.55 + 0.45 * sin(ang * 2.0 + 1.2)
            arc *= arcv
            r += arc * 0.85; g += arc * 0.55; b += arc * 0.28
            # --- black shadow ---
            t = (d - 0.33) / 0.025
            if t < 0.0: t = 0.0
            elif t > 1.0: t = 1.0
            sh = t * t * (3 - 2 * t)
            r *= sh; g *= sh; b *= sh
            # --- vignette ---
            t = (d - 0.75) / 0.6
            if t < 0.0: t = 0.0
            elif t > 1.0: t = 1.0
            vg = 1.0 - 0.28 * t * t * (3 - 2 * t)
            rr = r * vg; gg = g * vg; bb = b * vg
            i = row + xi * 3
            buf[i] = 255 if rr > 1.0 else (0 if rr < 0.0 else int(rr * 255))
            buf[i + 1] = 255 if gg > 1.0 else (0 if gg < 0.0 else int(gg * 255))
            buf[i + 2] = 255 if bb > 1.0 else (0 if bb < 0.0 else int(bb * 255))
    return buf

def _arcv(dy):
    a = abs(dy)
    t = (a - 0.10) / 0.20
    if t < 0.0: t = 0.0
    elif t > 1.0: t = 1.0
    return t * t * (3 - 2 * t)

# ---------- PNG encoder (filter 0, zlib level 9) ----------
def write_png(path, w, h, buf):
    def chunk(typ, data):
        c = struct.pack(">I", len(data)) + typ + data
        return c + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)
    raw = bytearray()
    stride = w * 3
    for y in range(h):
        raw.append(0)
        raw += buf[y * stride:(y + 1) * stride]
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
           + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)
    return len(png)

def main():
    outdir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(outdir, exist_ok=True)
    buf = render(W, H)
    n = write_png(os.path.join(outdir, "entry.png"), W, H, buf)
    print(f"wrote entry.png {W}x{H} {n} bytes")

if __name__ == "__main__":
    main()
