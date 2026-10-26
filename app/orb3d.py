"""Software 3D renderer for the hero area: a holographic ring of 12 microphone
nodes joined by curved links, inside a glowing halo with drifting particles.

Everything is true 3D (rotation + perspective projection) in numpy, drawn with
Pillow; the ring yaws/pitches with the mouse and breathes with the voice.
One RGB frame per call to Renderer.render().
"""
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter


def _rgb(c):
    return np.array([int(c[i:i + 2], 16) for i in (1, 3, 5)], dtype=np.float32) / 255.0


def _hex(v):
    return "#%02x%02x%02x" % tuple(int(max(0, min(1, x)) * 255) for x in v)


def _tup(v, k=1.0):
    return tuple(int(max(0, min(1, x * k)) * 255) for x in v)


class Renderer:
    N = 12
    N_PARTICLES = 160
    CAM = 3.4          # camera distance in ring radii (perspective strength)

    def __init__(self, w: int, h: int, bg: str):
        self.w, self.h = w, h
        self.bg = _rgb(bg)
        self.cx, self.cy = w / 2, h / 2
        self.R = min(h * 0.34, w * 0.30, 170)
        R, cx, cy = self.R, self.cx, self.cy

        # static halo pattern (inner haze + thin outer shell + wide shell glow)
        ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
        d = np.sqrt(((xs - cx) / R) ** 2 + ((ys - cy) / R) ** 2)
        self.halo = (0.10 * np.exp(-d * d * 1.1)
                     + 0.20 * np.exp(-((d - 1.28) / 0.02) ** 2)
                     + 0.07 * np.exp(-((d - 1.28) / 0.12) ** 2)
                     + 0.10 * np.exp(-d * 0.9) * (d > 1.28)).astype(np.float32)
        self.base = Image.new("RGB", (w, h), _tup(self.bg))

        # ring + nodes (node 0 at the top)
        th = 2 * math.pi * np.arange(self.N) / self.N + math.pi / 2
        self.nodes = np.stack([np.cos(th), np.sin(th), np.zeros(self.N)], 1).astype(np.float32)
        a = np.linspace(0, 2 * math.pi, 181)
        self.ring = np.stack([np.cos(a), np.sin(a), np.zeros_like(a)], 1).astype(np.float32)

        # curved links across the interior, bulging in z so the web has depth
        u = np.linspace(0, 1, 22, dtype=np.float32)[:, None]
        links, self.link_ij = [], []
        for i in range(self.N):
            for j in range(i + 1, self.N):
                if min(j - i, self.N - (j - i)) < 2:
                    continue
                p0, p2 = self.nodes[i], self.nodes[j]
                c = (p0 + p2) / 2 * 0.30
                c[2] = 0.55 * math.sin(i * 1.7 + j * 0.9)
                links.append((1 - u) ** 2 * p0 + 2 * (1 - u) * u * c + u ** 2 * p2)
                self.link_ij.append((i, j))
        self.links = np.stack(links).astype(np.float32)            # (L, 22, 3)

        # particle shell (fibonacci sphere)
        k = np.arange(self.N_PARTICLES, dtype=np.float32) + 0.5
        phi = np.arccos(1 - 2 * k / self.N_PARTICLES)
        tht = math.pi * (1 + 5 ** 0.5) * k
        self.P = (1.22 * np.stack([np.cos(tht) * np.sin(phi), np.cos(phi),
                                   np.sin(tht) * np.sin(phi)], 1)).astype(np.float32)
        self.sprites = {}

    # ------------------------------------------------------------- helpers
    def _rot(self, yaw, pitch):
        cy_, sy_ = math.cos(yaw), math.sin(yaw)
        cp, sp = math.cos(pitch), math.sin(pitch)
        Ry = np.array([[cy_, 0, sy_], [0, 1, 0], [-sy_, 0, cy_]], np.float32)
        Rx = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]], np.float32)
        return (Ry.T @ Rx.T)  # row-vector convention: p @ M

    def _proj(self, P, M):
        Q = P @ M
        s = self.CAM / (self.CAM - Q[..., 2])
        px = self.cx + Q[..., 0] * self.R * s
        py = self.cy - Q[..., 1] * self.R * s
        return px, py, Q[..., 2], s

    def _sprite(self, r, col, bright):
        """Mic node (ring + dark disc + mic icon), supersampled and cached."""
        key = (int(round(r)), _hex(col), int(bright * 6))
        sp = self.sprites.get(key)
        if sp is not None:
            return sp
        if len(self.sprites) > 400:
            self.sprites.clear()
        S = int(r * 2.5) + 2
        Z = 4
        big = Image.new("RGBA", (S * Z, S * Z), (0, 0, 0, 0))
        d = ImageDraw.Draw(big)
        c, u = S * Z / 2, r * Z
        ring_col = _tup(col * 0.5 + 0.5, 0.65 + 0.35 * bright) + (255,)
        d.ellipse((c - u, c - u, c + u, c + u), fill=_tup(col * 0.42 + 0.02) + (255,),
                  outline=ring_col, width=max(3, int(u * 0.13)))
        ic = _tup(col * (1 - 0.6) + 0.6, 0.75 + 0.25 * bright) + (255,)
        d.rounded_rectangle((c - 0.17 * u, c - 0.50 * u, c + 0.17 * u, c + 0.10 * u),
                            radius=0.17 * u, fill=ic)
        lw = max(3, int(0.075 * u))
        d.arc((c - 0.33 * u, c - 0.28 * u, c + 0.33 * u, c + 0.32 * u), 0, 180, fill=ic, width=lw)
        d.line((c, c + 0.32 * u, c, c + 0.52 * u), fill=ic, width=lw)
        d.line((c - 0.18 * u, c + 0.52 * u, c + 0.18 * u, c + 0.52 * u), fill=ic, width=lw)
        sp = big.resize((S, S), Image.LANCZOS)
        self.sprites[key] = sp
        return sp

    @staticmethod
    def _blur(img, radius):
        """Cheap glow: blur at half resolution."""
        w, h = img.size
        small = img.resize((w // 2, h // 2), Image.BILINEAR).filter(ImageFilter.GaussianBlur(radius / 2))
        return small.resize((w, h), Image.BILINEAR)

    # --------------------------------------------------------------- frame
    def render(self, col_hex: str, t: float, amp: float, level: float, energy: float,
               light=(0.0, 0.0, 1.0), tilt=0.30, hot=None) -> Image.Image:
        w, h = self.w, self.h
        col = _rgb(col_hex)
        hotc = col * 0.35 + 0.65
        act = float(min(1.0, amp + level * 0.5))

        yaw = 0.55 * math.sin(t * 0.35) + light[0] * 1.6
        pitch = 0.20 + (tilt - 0.30) * 2.6 + 0.08 * math.sin(t * 0.5)
        M = self._rot(yaw, pitch)

        # halo
        canvas = np.empty((h, w, 3), np.float32)
        canvas[:] = self.bg
        canvas += self.halo[..., None] * col * (0.50 + 0.9 * act + 0.25 * energy)

        glow = Image.new("RGB", (w, h), (0, 0, 0))
        crisp = Image.new("RGB", (w, h), (0, 0, 0))
        gd, cd = ImageDraw.Draw(glow), ImageDraw.Draw(crisp)

        # ring: silver tube, brighter where it faces the camera
        rx, ry, rz, _ = self._proj(self.ring, M)
        for k in range(len(rx) - 1):
            depth = (rz[k] + 1) / 2
            seg = [(float(rx[k]), float(ry[k])), (float(rx[k + 1]), float(ry[k + 1]))]
            gd.line(seg, fill=_tup(col, 0.55), width=7)
            v = 0.45 + 0.55 * depth
            cd.line(seg, fill=_tup(np.array([0.85, 0.95, 0.97]) * 0.7 + col * 0.3, min(1.0, v * 1.15)),
                    width=3 + int(2 * depth))

        # links
        L = len(self.links)
        lx, ly, lz, _ = self._proj(self.links.reshape(-1, 3), M)
        lx, ly, lz = (a.reshape(L, -1) for a in (lx, ly, lz))
        for n in range(L):
            pts = list(zip(lx[n].tolist(), ly[n].tolist()))
            depth = (float(lz[n].mean()) + 1) / 2
            b = 0.25 + 0.55 * depth
            gd.line(pts, fill=_tup(col, 0.30 * b), width=3)
            cd.line(pts, fill=_tup(col * 0.45 + 0.55, b * 0.8), width=1)
            if act > 0.08:                       # light pulses travelling along links
                u0 = (t * 0.55 + n * 0.173) % 1.0
                i0 = int(u0 * 18)
                seg = pts[i0:i0 + 4]
                cd.line(seg, fill=_tup(hotc, min(1.0, 0.45 + act)), width=2)
                gd.line(seg, fill=_tup(col, min(1.0, 0.4 + act)), width=5)

        # particles
        px, py, pz, ps = self._proj(self.P @ self._rot(t * 0.12, 0.0), M)
        for x, y, z in zip(px.tolist(), py.tolist(), pz.tolist()):
            depth = (z + 1.3) / 2.6
            r = 0.7 + 1.5 * depth
            cd.ellipse((x - r, y - r, x + r, y + r), fill=_tup(col * 0.5 + 0.5, 0.25 + 0.75 * depth))

        # node glows (before blur)
        nx, ny, nz, ns = self._proj(self.nodes, M)
        r0 = self.R * 0.118
        acts = []
        for i in range(self.N):
            a_i = float(np.clip(act * (0.55 + 0.45 * math.sin(t * 3.0 - i * 0.52)) + 0.06, 0, 1))
            acts.append(a_i)
            rr = r0 * float(ns[i]) * (1 + 0.20 * a_i) * 1.9
            gd.ellipse((nx[i] - rr, ny[i] - rr, nx[i] + rr, ny[i] + rr),
                       fill=_tup(col, 0.25 + 0.6 * a_i))

        canvas += (np.asarray(self._blur(glow, 10), np.float32) * 1.25
                   + np.asarray(crisp, np.float32)) / 255.0
        np.clip(canvas, 0, 1, out=canvas)
        img = Image.fromarray((canvas * 255).astype(np.uint8), "RGB")

        # nodes, back to front, on top of everything (opaque dark discs)
        for i in sorted(range(self.N), key=lambda k: nz[k]):
            r = r0 * float(ns[i]) * (1 + 0.20 * acts[i])
            spr = self._sprite(r, col, acts[i])
            img.paste(spr, (int(nx[i] - spr.width / 2), int(ny[i] - spr.height / 2)), spr)
        return img
