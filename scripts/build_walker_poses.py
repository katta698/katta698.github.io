# -*- coding: utf-8 -*-
"""Redraw the hiker's STANDING and JUMPING poses on the connect card.

    python scripts/build_walker_poses.py          # rewrite the poses
    python scripts/build_walker_poses.py --check  # verify, change nothing

Reported 2026-10-22: "the human is kind of weird ... while he jumps it
doesn't look great". Rendered at 10x, the three static poses were the
problem and the eight walk frames were not:

  stand   both legs fused into one narrow stalk, arms lost inside the torso
  crouch  hunched, arms hidden behind the body
  jump    torso leaning BACK with the legs splayed -- it reads as falling

So this touches those three and leaves the walk cycle byte-for-byte alone.

What makes a 17px figure read as a person is silhouette, not detail: a head
that is clearly separate from the shoulders, arms that break the outline
instead of disappearing into it, and legs that are two legs. Every pose
here is built from the same primitives the walk frames use -- a limb is a
quad between two joints with a circle at each -- so nothing about the
drawing style changes.

The torso, head, hair and backpack are IDENTICAL in all eleven existing
poses. They are lifted verbatim from frame k0 rather than re-emitted, which
is what keeps a redrawn pose from drifting away from the walk.
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(ROOT, "connect", "index.html")

# Joint radii, read off the existing frames. Shoulder/elbow/hand and
# hip/knee/ankle taper the same way in every pose.
ARM = (2.90, 2.20, 1.70)
LEG = (4.50, 3.10, 2.20)

# The joints the body hangs off, also from the existing frames.
SHOULDER_NEAR = (54.48, 21.59)
SHOULDER_FAR = (52.28, 21.59)
HIP = (50.00, 47.00)


def seg(a, b, ra, rb):
    """One limb segment: a quad from a to b, with a circle at each end.

    The quad is the segment's own width tapering from ra to rb; the circles
    round the joints off. Exactly how the walk frames are built.
    """
    (x1, y1), (x2, y2) = a, b
    dx, dy = x2 - x1, y2 - y1
    L = (dx * dx + dy * dy) ** 0.5 or 1.0
    # Unit normal, for offsetting each end by its own radius.
    nx, ny = -dy / L, dx / L
    p = [(x1 + nx * ra, y1 + ny * ra), (x2 + nx * rb, y2 + ny * rb),
         (x2 - nx * rb, y2 - ny * rb), (x1 - nx * ra, y1 - ny * ra)]
    d = "M%.2f %.2f L%.2f %.2f L%.2f %.2f L%.2f %.2f Z" % (
        p[0][0], p[0][1], p[1][0], p[1][1],
        p[2][0], p[2][1], p[3][0], p[3][1])
    return ('<path d="%s"/><circle cx="%.2f" cy="%.2f" r="%.2f"/>'
            '<circle cx="%.2f" cy="%.2f" r="%.2f"/>'
            % (d, x1, y1, ra, x2, y2, rb))


def foot(ankle, toe_dx):
    """The little wedge at the end of a leg, pointing the way he faces."""
    x, y = ankle
    x2 = x + toe_dx
    return ('<path d="M%.2f %.2f L%.2f %.2f Q%.2f %.2f %.2f %.2f '
            'L%.2f %.2f Q%.2f %.2f %.2f %.2f Z"/>'
            % (x - 1.6, y + 2.4, x2, y + 1.6,
               x2 + 1.2, y - 0.2, x2, y - 2.0,
               x - 1.6, y - 1.6, x - 3.2, y + 0.4, x - 1.6, y + 2.4))


def limb(a, b, c, radii):
    r0, r1, r2 = radii
    return seg(a, b, r0, r1) + seg(b, c, r1, r2)


def arm(shoulder, elbow, hand):
    return '<g>' + limb(shoulder, elbow, hand, ARM) + '</g>'


def leg(hip, knee, ankle, toe_dx):
    return '<g>' + limb(hip, knee, ankle, LEG) + foot(ankle, toe_dx) + '</g>'


def far(markup):
    """The limbs on the far side of the body, drawn paler."""
    return '<g class="far">' + markup[3:-4] + '</g>'


# ── the poses ──────────────────────────────────────────────────────────────
#
# Standing: legs apart and both visible, knees barely bent, arms hanging
# clear of the torso rather than inside it. The old pose put both ankles
# within 2 units of each other, which at 17px is one leg.
STAND = {
    "far_arm": ((52.28, 21.59), (49.6, 36.2), (47.4, 50.4)),
    "far_leg": ((50.0, 47.0), (46.6, 70.2), (44.4, 92.6), -4.2),
    "near_arm": ((54.48, 21.59), (58.4, 36.0), (60.6, 50.2)),
    "near_leg": ((50.0, 47.0), (54.2, 70.4), (56.6, 92.8), 4.6),
}

# Crouch: the gather before the jump. Knees forward, heels up, arms swung
# BACK -- which is what a person does before leaving the ground, and reads
# as intent rather than as a stumble.
CROUCH = {
    "far_arm": ((52.28, 25.0), (46.0, 37.5), (39.0, 46.0)),
    "far_leg": ((50.0, 50.0), (44.0, 70.0), (47.0, 90.0), -4.2),
    "near_arm": ((54.48, 25.0), (60.5, 38.0), (66.5, 46.5)),
    "near_leg": ((50.0, 50.0), (57.5, 69.5), (54.5, 90.0), 4.6),
    "dy": 3.0,
}

# Airborne: both knees tucked the same way, arms up and OUTSIDE the
# silhouette. The old one leaned the torso back with the legs trailing,
# which is the shape of a fall.
JUMP = {
    "far_arm": ((52.28, 21.59), (47.5, 8.0), (44.0, -5.0)),
    "far_leg": ((50.0, 47.0), (44.5, 64.0), (50.5, 76.0), -4.2),
    "near_arm": ((54.48, 21.59), (60.0, 8.5), (64.0, -4.5)),
    "near_leg": ((50.0, 47.0), (57.5, 63.0), (52.0, 77.5), 4.6),
    "dy": -9.0,
}


def pose_body(spec, fixed):
    """far arm, far leg, torso, near leg, near arm, head -- in paint order."""
    pack, torso, head = fixed
    out = [pack]
    out.append(far(arm(*spec["far_arm"])))
    out.append(far(leg(*spec["far_leg"])))
    out.append(torso)
    out.append(leg(*spec["near_leg"]))
    out.append(arm(*spec["near_arm"]))
    out.append(head)
    body = "".join(out)
    o, c = body.count("<g"), body.count("</g>")
    assert o == c, "pose is unbalanced: %d opens, %d closes" % (o, c)
    dy = spec.get("dy")
    if dy:
        body = '<g transform="translate(0 %.1f)">%s</g>' % (dy, body)
    return body


def fixed_parts(k0):
    """pack, torso, head -- lifted verbatim out of walk frame k0."""
    pack = re.search(r'<g class="pack">.*?</g>', k0, re.S).group(0)
    # The torso is the pair of quads with the three body circles between
    # the two `far` groups and the near leg.
    t = re.search(r'(<path d="M56\.89 48\.22.*?r="8\.25"/>)', k0, re.S)
    assert t, "torso block not found"
    head = re.search(r'(<circle cx="56\.57" cy="9\.77".*)$', k0, re.S).group(1)
    # k0's own closing </g> comes along with that greedy match. Left in, it
    # gave every rebuilt pose one extra close: the browser then shut
    # <g class="wcheer"> early and dropped the jump frame entirely, which
    # rendered as nothing at all rather than as anything wrong.
    if head.endswith("</g>"):
        head = head[:-4]
    return pack, t.group(1), head


def main():
    check = "--check" in sys.argv
    s = io.open(PAGE, encoding="utf-8").read()

    i = s.index('<g class="wcyc">')
    k0 = s[i + len('<g class="wcyc">'):s.index('<g class="k1">')]
    k0 = k0[k0.index(">") + 1:]            # strip the <g class="k0"> opener
    fixed = fixed_parts(k0)

    new_stand = ('<g class="wstand"><g class="s0">'
                 + pose_body(STAND, fixed) + '</g></g>')
    new_cheer = ('<g class="wcheer"><g class="c0">'
                 + pose_body(CROUCH, fixed) + '</g><g class="c1">'
                 + pose_body(JUMP, fixed) + '</g></g>')

    old_stand = re.search(r'<g class="wstand">.*?</g></g>', s, re.S)
    old_cheer = re.search(r'<g class="wcheer">.*?</g></g></svg>', s, re.S)
    assert old_stand and old_cheer, "could not find the poses to replace"

    out = s[:old_stand.start()] + new_stand
    out += s[old_stand.end():old_cheer.start()] + new_cheer + "</svg>"
    out += s[old_cheer.end():]

    # The walk cycle must come through untouched. This is the whole premise
    # of the change, so it is asserted rather than assumed.
    a = s[s.index('<g class="wcyc">'):s.index('<g class="wstand">')]
    b = out[out.index('<g class="wcyc">'):out.index('<g class="wstand">')]
    assert a == b, "the walk cycle changed -- it must not"

    if check:
        print("stand/cheer would be rewritten; walk cycle identical")
        return 0
    io.open(PAGE, "w", encoding="utf-8", newline="").write(out)
    print("redrew stand, crouch and jump; walk cycle untouched")
    return 0


if __name__ == "__main__":
    sys.exit(main())
