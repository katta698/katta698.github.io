# -*- coding: utf-8 -*-
"""A walking figure drawn as filled outlines, not as thick strokes.

The first build stacked round-capped strokes. That puts a ball the width of
the limb at every knee and ankle, and the foot is another stroke stuck on at
an angle -- reported, correctly, as uneven legs and club feet. A stroke has
one width along its whole length; a leg does not.

So every part here is a filled polygon that TAPERS: thigh wide at the hip
and narrow at the knee, calf narrow again at the ankle, and a shoe with a
heel, a sole and a toe. Joints are closed with a circle of exactly the
limb's half-width at that point, which meets the taper flush instead of
bulging past it.
"""
import math

H = 100.0
HEAD_R, NECK_Y, HIP_Y = 0.064*H, 0.170*H, 0.470*H
THIGH, CALF = 0.238*H, 0.232*H
SHOULDER_Y, UPPER_ARM, FOREARM = 0.212*H, 0.163*H, 0.150*H
W_SHOULDER, W_WAIST, W_HIPW = 0.165*H, 0.128*H, 0.140*H
W_HIPJ, W_KNEE, W_ANKLE = 0.090*H, 0.062*H, 0.044*H
W_SHLD, W_ELBOW, W_WRIST = 0.058*H, 0.044*H, 0.034*H
SHOE_L, SHOE_H, HEEL = 0.098*H, 0.040*H, 0.026*H
CX, LEAN = 50.0, 10.0

# Arms swing a good deal wider than the first pass. They were ±26°, and
# the FAR arm is drawn behind the torso -- at that amplitude it never came
# out past the body, so he looked like a man with one arm. At ±38 both
# swing clear of the silhouette on every stride, which is also just what a
# brisk walk looks like.
CYCLE = [( 34, -4, -30,-10, -38,-16,  36,-12),
         ( 18,-20, -20,-38, -22,-28,  24,-16),
         (  4,-12,  -2,-64,  -5,-22,   6,-30),
         (-16, -6,  24,-42,  22,-14, -20,-24),
         (-30,-10,  34, -4,  36,-12, -38,-16),
         (-20,-38,  18,-20,  24,-16, -22,-28),
         ( -2,-64,   4,-12,   6,-30,  -5,-22),
         ( 24,-42, -16, -6, -20,-24,  22,-14)]


def pt(x, y, ang, L):
    a = math.radians(ang)
    return (x + L*math.sin(a), y + L*math.cos(a))


def seg(p, q, w1, w2):
    """A tapered limb section: a quad from a width at p to a width at q,
    plus a disc at each end so consecutive sections meet without a seam."""
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


def shoe(ank, ang):
    """A shoe: flat sole, heel behind the ankle, toe in front, lifted a
    little at the front. Not a capsule pointing wherever the shin did."""
    fwd = ang
    heel = pt(ank[0], ank[1], fwd-90, HEEL)
    toe = pt(ank[0], ank[1], fwd+90, SHOE_L-HEEL)
    dn = lambda p, k: pt(p[0], p[1], 180, -k)
    h1, t1 = dn(heel, SHOE_H*0.55), dn(toe, SHOE_H*0.30)
    h2, t2 = dn(heel, -SHOE_H*0.45), dn(toe, -SHOE_H*0.62)
    return ('<path d="M%.2f %.2f L%.2f %.2f Q%.2f %.2f %.2f %.2f '
            'L%.2f %.2f Q%.2f %.2f %.2f %.2f Z"/>'
            % (h1[0],h1[1], t1[0],t1[1],
               t1[0]+1.2,(t1[1]+t2[1])/2, t2[0],t2[1],
               h2[0],h2[1], h2[0]-1.6,(h2[1]+h1[1])/2, h1[0],h1[1]))


def frame(a):
    tF, kF, tB, kB, aF, eF, aB, eB = a
    hip = (CX, HIP_Y)
    neck = pt(CX, HIP_Y, 180-LEAN, HIP_Y-NECK_Y)
    sh = pt(CX, HIP_Y, 180-LEAN, HIP_Y-SHOULDER_Y)
    globals()['_SH'] = sh
    o = []

    top = pt(sh[0], sh[1], 180-LEAN, -0.030*H)
    bot = pt(sh[0], sh[1], 180-LEAN, -0.235*H)
    o.append('<g class="pack">%s</g>'
             % seg((top[0]-6.2, top[1]), (bot[0]-7.0, bot[1]), 0.185*H, 0.215*H))

    def leg(t, k, far):
        knee = pt(hip[0], hip[1], t, THIGH)
        ank = pt(knee[0], knee[1], t+k, CALF)
        return '<g%s>%s%s%s</g>' % (
            ' class="far"' if far else '',
            seg(hip, knee, W_HIPJ, W_KNEE),
            seg(knee, ank, W_KNEE, W_ANKLE),
            shoe(ank, (t+k)*0.3))

    def arm(s, e, far):
        # The far shoulder sits a little behind the near one, so the far
        # arm reads as the other side of a body rather than as a copy
        # hiding directly behind the first.
        sh = (globals()['_SH'][0] - (2.2 if far else 0.0), globals()['_SH'][1])
        el = pt(sh[0], sh[1], s, UPPER_ARM)
        wr = pt(el[0], el[1], s+e, FOREARM)
        return '<g%s>%s%s</g>' % (' class="far"' if far else '',
            seg(sh, el, W_SHLD, W_ELBOW), seg(el, wr, W_ELBOW, W_WRIST))

    o.append(leg(tB, kB, True)); o.append(arm(aB, eB, True))
    waist = ((hip[0]+neck[0])/2, (hip[1]+neck[1])/2)
    o.append(seg(hip, waist, W_HIPW, W_WAIST))
    o.append(seg(waist, neck, W_WAIST, W_SHOULDER))
    o.append(leg(tF, kF, False)); o.append(arm(aF, eF, False))

    head = pt(neck[0], neck[1], 180-LEAN, HEAD_R*1.22)
    o.append('<circle cx="%.2f" cy="%.2f" r="%.2f"/>' % (head[0], head[1], HEAD_R))
    for ang, d, rx, ry, rot in ((54, .72, 1.05, .62, 30), (16, .80, 1.02, .58, 8),
                                (-34, .74, .66, .46, -30)):
        h = pt(head[0], head[1], 180-LEAN+ang, HEAD_R*d)
        o.append('<ellipse cx="%.2f" cy="%.2f" rx="%.2f" ry="%.2f" '
                 'transform="rotate(%.1f %.2f %.2f)"/>'
                 % (h[0], h[1], HEAD_R*rx, HEAD_R*ry, -LEAN+rot, h[0], h[1]))
    return "".join(o)


def cheer(tuck):
    """Off the ground, both arms up. Upright rather than leaning, legs
    tucked under him, arms raised past the head -- the one pose in the set
    that is not a walk, so it has to read instantly at this size."""
    global LEAN
    keep, LEAN = LEAN, 1.0
    hip = (CX, HIP_Y - tuck)
    neck = pt(CX, hip[1], 180-LEAN, HIP_Y-NECK_Y)
    sh = pt(CX, hip[1], 180-LEAN, HIP_Y-SHOULDER_Y)
    globals()['_SH'] = sh
    o = []
    top = pt(sh[0], sh[1], 180-LEAN, -0.030*H)
    bot = pt(sh[0], sh[1], 180-LEAN, -0.235*H)
    o.append('<g class="pack">%s</g>'
             % seg((top[0]-6.2, top[1]), (bot[0]-7.0, bot[1]), 0.185*H, 0.215*H))

    def leg(t, k, far):
        knee = pt(hip[0], hip[1], t, THIGH)
        ank = pt(knee[0], knee[1], t+k, CALF)
        foot = shoe(ank, (t+k)*0.3 + 16)
        return '<g%s>%s%s%s</g>' % (' class="far"' if far else '',
            seg(hip, knee, W_HIPJ, W_KNEE), seg(knee, ank, W_KNEE, W_ANKLE), foot)

    def arm(a1, far):
        shx = sh[0] - (2.2 if far else 0.0)
        # A V, not straight up: from the side, two arms raised vertically
        # land on top of the head and the pose reads as no arms at all.
        el = pt(shx, sh[1], a1, UPPER_ARM)
        wr = pt(el[0], el[1], a1 + (10 if a1 > 0 else -10), FOREARM)
        return '<g%s>%s%s</g>' % (' class="far"' if far else '',
            seg((shx, sh[1]), el, W_SHLD, W_ELBOW), seg(el, wr, W_ELBOW, W_WRIST))

    o.append(leg(-16, -46, True)); o.append(arm(-148, True))
    waist = ((hip[0]+neck[0])/2, (hip[1]+neck[1])/2)
    o.append(seg(hip, waist, W_HIPW, W_WAIST))
    o.append(seg(waist, neck, W_WAIST, W_SHOULDER))
    o.append(leg(14, -42, False)); o.append(arm(150, False))
    head = pt(neck[0], neck[1], 180-LEAN, HEAD_R*1.22)
    o.append('<circle cx="%.2f" cy="%.2f" r="%.2f"/>' % (head[0], head[1], HEAD_R))
    for ang, d, rx, ry, rot in ((54,.72,1.05,.62,30), (16,.80,1.02,.58,8),
                                (-34,.74,.66,.46,-30)):
        h = pt(head[0], head[1], 180-LEAN+ang, HEAD_R*d)
        o.append('<ellipse cx="%.2f" cy="%.2f" rx="%.2f" ry="%.2f" '
                 'transform="rotate(%.1f %.2f %.2f)"/>'
                 % (h[0], h[1], HEAD_R*rx, HEAD_R*ry, -LEAN+rot, h[0], h[1]))
    LEAN = keep
    return "".join(o)


FRAMES = [frame(a) for a in CYCLE]
CHEER = [cheer(0.0), cheer(2.5)]


def sprite(cls="walker"):
    walk = "".join('<g class="k%d">%s</g>' % (i, f) for i, f in enumerate(FRAMES))
    cheers = "".join('<g class="c%d">%s</g>' % (i, f) for i, f in enumerate(CHEER))
    return ('<svg class="%s" viewBox="18 -20 64 122" aria-hidden="true">'
            '<g class="wcyc">%s</g><g class="wcheer">%s</g></svg>'
            % (cls, walk, cheers))
