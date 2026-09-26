# -*- coding: utf-8 -*-
"""A small robot that walks, built the same way as the man.

Deliberately NOT a tiny copy of him: boxy where he is round, an antenna
where he has hair, a blunt visor brow, and short stiff legs that take
quick steps. At eighteen pixels the only things that can say "robot" are
the square head and the antenna, so both are exaggerated.
"""
import math

H = 100.0
HEAD_W, HEAD_H, HEAD_Y = 0.30*H, 0.25*H, 0.05*H
ANT_H = 0.075*H
BODY_W, BODY_T, BODY_Y, BODY_B = 0.27*H, 0.22*H, 0.325*H, 0.62*H
HIPY = 0.62*H
THIGH, SHIN = 0.145*H, 0.145*H
W_LEG, W_SHIN = 0.075*H, 0.060*H
FOOT_L, FOOT_H = 0.105*H, 0.042*H
SHY, ARM, FORE = 0.40*H, 0.115*H, 0.105*H
W_ARM = 0.055*H
CX = 50.0

# leg-front, knee-front, leg-back, knee-back, arm-front, arm-back
CYCLE = [( 20, -6, -18, -10,  -16,  15),
         (  2, -4,   2, -34,   -2,   2),
         (-18,-10,  20,  -6,   15, -16),
         (  2,-34,   2,  -4,    2,  -2)]


def pt(x, y, ang, L):
    a = math.radians(ang)
    return (x + L*math.sin(a), y + L*math.cos(a))


def seg(p, q, w1, w2):
    dx, dy = q[0]-p[0], q[1]-p[1]
    L = math.hypot(dx, dy) or 1e-6
    nx, ny = -dy/L, dx/L
    a = (p[0]+nx*w1/2, p[1]+ny*w1/2); b = (q[0]+nx*w2/2, q[1]+ny*w2/2)
    c = (q[0]-nx*w2/2, q[1]-ny*w2/2); d = (p[0]-nx*w1/2, p[1]-ny*w1/2)
    return ('<path d="M%.2f %.2f L%.2f %.2f L%.2f %.2f L%.2f %.2f Z"/>'
            '<circle cx="%.2f" cy="%.2f" r="%.2f"/>'
            '<circle cx="%.2f" cy="%.2f" r="%.2f"/>'
            % (a[0],a[1],b[0],b[1],c[0],c[1],d[0],d[1],
               p[0],p[1],w1/2, q[0],q[1],w2/2))


def rrect(x, y, w, h, r):
    return ('<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" rx="%.2f"/>'
            % (x, y, w, h, r))


def frame(a):
    lF, kF, lB, kB, aF, aB = a
    hip = (CX, HIPY)
    o = []
    # antenna first, then head, body
    o.append(seg((CX+2, HEAD_Y), (CX+2, HEAD_Y-ANT_H), 0.030*H, 0.022*H))
    o.append('<circle cx="%.2f" cy="%.2f" r="%.2f"/>'
             % (CX+2, HEAD_Y-ANT_H-1.2, 0.038*H))

    def leg(t, k, far):
        knee = pt(hip[0], hip[1], t, THIGH)
        ank = pt(knee[0], knee[1], t+k, SHIN)
        foot = ('<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" rx="%.2f"/>'
                % (ank[0]-FOOT_L*0.34, ank[1]-FOOT_H*0.4, FOOT_L, FOOT_H, 1.6))
        return '<g%s>%s%s%s</g>' % (' class="far"' if far else '',
            seg(hip, knee, W_LEG, W_SHIN), seg(knee, ank, W_SHIN, W_SHIN*0.9), foot)

    def arm(s, far):
        sh = (CX-1, SHY)
        el = pt(sh[0], sh[1], s, ARM)
        wr = pt(el[0], el[1], s*0.4-14, FORE)
        return '<g%s>%s%s</g>' % (' class="far"' if far else '',
            seg(sh, el, W_ARM, W_ARM*0.85), seg(el, wr, W_ARM*0.85, W_ARM*0.75))

    o.append(leg(lB, kB, True)); o.append(arm(aB, True))
    o.append(rrect(CX-BODY_W/2, BODY_Y, BODY_W, BODY_B-BODY_Y, 0.055*H))
    o.append(rrect(CX-HEAD_W/2+1.5, HEAD_Y, HEAD_W, HEAD_H, 0.070*H))
    # a brow over the visor, so the head is not just a box
    o.append(rrect(CX-HEAD_W/2+0.5, HEAD_Y+HEAD_H*0.30, HEAD_W+2.5,
                   HEAD_H*0.20, 0.018*H))
    o.append(leg(lF, kF, False)); o.append(arm(aF, False))
    return "".join(o)


FRAMES = [frame(a) for a in CYCLE]
# See STAND in make_connect_walker: a stopped robot that keeps stepping
# is a robot on a treadmill.
STAND = frame((4, -3, -4, -3, -5, 5))


def sprite(cls="bot"):
    gs = "".join('<g class="r%d">%s</g>' % (i, f) for i, f in enumerate(FRAMES))
    return ('<svg class="%s" viewBox="28 0 44 100" aria-hidden="true">'
            '<g class="rcyc">%s</g><g class="rstand"><g class="s0">%s</g></g></svg>'
            % (cls, gs, STAND))
