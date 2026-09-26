# -*- coding: utf-8 -*-
"""The followers' tracks, simulated rather than hand-typed.

One robot became four and then six: the model he works with, and the five
agents it runs. Each trails a little further back and stands a little
shorter, so the chain reads as a hierarchy without a word of explanation
-- him, then what he uses, then what that uses.

The loop is a round trip now, not a patrol. Out to Azure and back, out to
GCP and back, then the whole team stands at AWS with him at the centre
and the six of them around him. That is the claim the picture is making:
the other two clouds are places he goes, and AWS is where the work
happens -- so AWS is the only place anybody stops, and the length of that
stop is the point.
"""

AZURE, AWS, GCP = 39.0, 112.0, 186.0
GROUND = 42.0        # where every foot lands

# The loop, in per cent of the 26s cycle. Both legs are the same length
# on purpose -- Azure is 73px from AWS and GCP is 74 -- so the two trips
# take the same time and neither cloud reads as further away than it is.
LEG = 15.0                        # per cent of the loop spent walking a leg
AT_AZ, OFF_AZ = 15.0, 18.0        # reach Azure, turn round
HOME_1, OFF_HOME = 33.0, 36.0     # back through AWS, straight out again
AT_GCP, OFF_GCP = 51.0, 54.0      # reach GCP, turn round
HOME_2 = 69.0                     # home for good; the huddle starts here
JUMP = 86.5                       # and the team jumps once it has formed

SPEED = (AWS - AZURE) / LEG       # his pace, in px per per-cent
VMAX = SPEED * 1.2                # theirs -- a little quicker, so one that
                                  # loses ground at a turn has some way of
                                  # getting it back

STOPS = [(0.0, AWS), (AT_AZ, AZURE), (OFF_AZ, AZURE),
         (HOME_1, AWS), (OFF_HOME, AWS), (AT_GCP, GCP), (OFF_GCP, GCP),
         (HOME_2, AWS), (100.0, AWS)]


def man_at(pct):
    """Where the leader is at a given point of the loop."""
    for (p0, x0), (p1, x1) in zip(STOPS, STOPS[1:]):
        if p0 <= pct <= p1:
            return x0 if p1 == p0 else x0 + (x1 - x0) * (pct - p0) / (p1 - p0)
    return AWS


# name, px behind him on the march, height, seconds per step, hop delay,
# where it stands in the formation, and how far back it steps into it.
#
# The standing offsets are set from MEASURED ink, not from the boxes.
# A figure's SVG box is a good deal wider than the figure in it -- his is
# 17px around 8px of ink, and the robots' are half empty too -- so
# offsets that look tight on paper left gaps of six to ten pixels
# between figures three to eight pixels wide. The gaps were wider than
# the people, which is not what a team standing together looks like.
# scripts/measure_connect_formation.py renders the formation, hides
# the road and the boards, and reports the gaps that are actually
# there; these numbers come back from it, and any change to a pose,
# a size or the formation needs it run again.
#
# The three that take his left are the three nearest the front. They come
# home from GCP strung out to his right, so anyone bound for his left has
# to get past him -- and the way they do it is simply to keep walking
# after he stops, which is both the shortest path and the only one that
# needs no explaining. Give that walk to the tail instead and the
# smallest robots have to cover 90px in the time he covers none.
FOLLOWERS = [
    #  name  back  height  step   hop  stand   back-step
    ("f1", 15.0, 19.0, 0.48, 0.8,  -5.4,  0.0),   # the model he works with
    ("f2", 26.0, 13.0, 0.40, 1.4, -10.1, -2.0),   # and the five agents it runs
    ("f3", 34.0, 12.0, 0.36, 2.0, -15.2, -4.0),
    ("f4", 42.0, 11.0, 0.34, 2.6,  14.1,  0.0),
    ("f5", 50.0, 10.0, 0.32, 3.2,  20.0, -2.0),
    ("f6", 58.0,  9.5, 0.30, 3.8,  25.6, -4.0),
]


def follow(back, hud, dt=0.05):
    """Walk the follower through the loop instead of placing it.

    Hand-written keyframes kept producing the same two faults, because
    both are what you get from saying where something should BE without
    asking whether it could have got there. Six figures given the same
    arrival time converge into a heap; a small robot told to be on the
    far side of the group in three seconds sprints at twice the pace its
    legs are animating at.

    So this is a pursuit instead. A follower wants to be `back` behind
    him on whichever side is behind, it moves at VMAX and no faster, and
    where it ends up is wherever that leaves it. Falling in, the way the
    chain reflects off each turn one robot at a time, and the order the
    formation assembles in are all consequences of those two rules
    rather than timings chosen by hand -- and none of them can ask a
    figure for a speed it does not have.

    Closing the loop needs no second pass: the last third pins everyone
    to their formation place, so t=100 always lands where t=0 starts.
    """
    p, side, path = AWS + hud, 1.0, []
    for k in range(int(100.0 / dt) + 1):
        t = k * dt
        ahead, behind = man_at(min(100.0, t + dt)), man_at(max(0.0, t - dt))
        if ahead < behind - 1e-9:
            side = 1.0          # he is heading left, so behind him is right
        elif ahead > behind + 1e-9:
            side = -1.0
        target = (AWS + hud) if t >= HOME_2 else man_at(t) + back * side
        p += max(-VMAX * dt, min(VMAX * dt, target - p))
        path.append((t, p))
    return path


def _simplify(path, tol=0.4):
    """Keep the corners, drop the straights.

    The simulation is two thousand points, and between its corners the
    motion is a straight line at a constant pace -- which is exactly what
    CSS already gives you between two keyframes. So the only points worth
    emitting are the ones a straight line would miss by more than a third
    of a pixel.
    """
    keep, stack = {0, len(path) - 1}, [(0, len(path) - 1)]
    while stack:
        i, j = stack.pop()
        if j - i < 2:
            continue
        (t0, p0), (t1, p1) = path[i], path[j]
        m = (p1 - p0) / (t1 - t0) if t1 != t0 else 0.0
        worst, at = tol, None
        for k in range(i + 1, j):
            d = abs(path[k][1] - (p0 + m * (path[k][0] - t0)))
            if d > worst:
                worst, at = d, k
        if at is not None:
            keep.add(at)
            stack += [(i, at), (at, j)]
    return [path[i] for i in sorted(keep)]


def arrival(path, hud):
    """When it last settles into its place in the formation."""
    home = AWS + hud
    for t, p in reversed(path):
        if abs(p - home) > 0.5:
            return min(t + 0.5, 100.0)
    return HOME_2


def moving(path, eps=0.02, knit=1.0):
    """The stretches of the loop this follower is actually walking.

    A figure only steps while it is going somewhere. Every one of them
    used to run its walk cycle for the whole 26s regardless, so the team
    that stops at AWS to work stopped by marching on the spot -- which
    reads as a treadmill and undoes the one thing the stop exists to
    say. The simulation already knows who is moving and when, including
    the beats where a follower is still walking after he has halted, so
    the windows come from it rather than from the man's timeline.

    Gaps shorter than `knit` are knitted up: a follower crawling through
    a turn dips under the threshold for a twentieth of a second at a
    time, and honouring every one of those would emit sixty keyframes to
    describe a pause nobody can see.
    """
    spans, run = [], None
    for (t0, p0), (t1, p1) in zip(path, path[1:]):
        if abs(p1 - p0) > eps:
            run = (run[0] if run else t0), t1
        elif run and t0 - run[1] > 0.0:
            spans.append(run)
            run = None
    if run:
        spans.append(run)
    out = []
    for a, b in spans:
        if out and a - out[-1][1] < knit:
            out[-1] = (out[-1][0], b)
        else:
            out.append((a, b))
    return [(a, b) for a, b in out if b - a > 0.3]


def gait(name, spans):
    """One pose group on while it walks, the other on while it stands.

    steps(1) and stops that tile exactly, for the reason written up over
    showwalk in make_connect_road.py: adjacent keyframe stops still
    interpolate across the gap between them, and interpolating between
    two silhouettes is how the figure ends up part-drawn.
    """
    marks = [(0.0, False)]
    for a, b in spans:
        marks.append((a, True))
        marks.append((b, False))
    out = []
    for kind, walking in (("showwalk", True), ("showstand", False)):
        rows = ["@keyframes %s-%s {" % (kind, name)]
        for i, (t, w) in enumerate(marks):
            nxt = marks[i + 1][0] if i + 1 < len(marks) else 100.0
            rows.append("  %.2f%%, %.2f%% { opacity: %d; }"
                        % (t, max(t, nxt - 0.01), 1 if w == walking else 0))
        rows.append("}")
        out.append(chr(10).join(rows))
    return chr(10).join(out)


def _frames(name, kind, keys, fmt):
    out = ["@keyframes %s-%s {" % (kind, name)]
    for pct, val in keys:
        out.append("  %.2f%% { transform: %s; }" % (pct, fmt % val))
    out.append("}")
    return "\n".join(out)


def track(name, path):
    return _frames(name, "trek", _simplify(path), "translateX(%.1fpx)")


def hop(name, delay, lift, settled):
    """Up after him, not with him -- the line catches the jump one by one.

    It carries the formation's depth as well, because transform is one
    property and this is the one already on the element: a follower that
    stands a row back is drawn a couple of pixels higher, the way
    anything further away sits higher in a frame. The jump has to return
    to that height rather than to zero, or the back row lands in the
    front row's lap.
    """
    a = JUMP + delay
    return _frames(name, "hop", [
        (0.0, lift), (2.0, lift),          # still in formation
        (8.0, 0.0), (HOME_2, 0.0),         # down on the road with everyone
        (settled, lift),                   # stepped back into its row
        (a, lift), (a + 1.5, lift - 5.0), (a + 3.0, lift), (100.0, lift),
    ], "translateY(%.1fpx)")


def face(name, path, hud, settled):
    """Facing the way it is actually walking, read off the simulation.

    By hand this was wrong twice, because a follower's turns do not
    happen where his do: it keeps walking toward Azure for a moment after
    he has turned round and started back, which is the whole reason the
    chain reflects off each end instead of pivoting on the spot. The
    velocity already knows. Once it is parked, it faces him.
    """
    look = 1 if hud < 0 else -1
    keys, last = [], None
    for (t0, p0), (t1, p1) in zip(path, path[1:]):
        if t1 > settled:
            break
        if abs(p1 - p0) < 1e-6:
            continue
        d = -1 if p1 < p0 else 1
        if d != last:
            keys.append((t0, d))
            last = d
    keys.append((settled, look))
    out = ["@keyframes face-%s {" % name]
    for i, (t, d) in enumerate(keys):
        nxt = keys[i + 1][0] if i + 1 < len(keys) else 100.0
        out.append("  %.2f%%, %.2f%% { transform: scaleX(%d); }"
                   % (t, max(t, nxt - 0.01), d))
    out.append("}")
    return "\n".join(out)


def css():
    out = []
    for i, (name, back, h, step, delay, hud, lift) in enumerate(FOLLOWERS):
        w = round(h * 11.0 / 19.0, 1)
        path = follow(back, hud)
        settled = arrival(path, hud)
        # Every foot on the same line. They were landing on 33 and the man
        # on 44 -- eleven pixels apart, one lot on the top edge of the
        # road and him on the bottom, which is what "not natural" was.
        # Stacked by which row of the formation it stands in, not by
        # its place in the line. Indexed by position it paired a back-row
        # robot with a front-row one, so the one standing further away
        # was drawn in front of the one standing nearer.
        out.append(".%s { top: %.0fpx; width: %.1fpx; z-index: %d; }"
                   % (name, GROUND - h, w, 3 + int(round(lift / 2.0))))
        out.append(".%s .bot { width: %.1fpx; height: %.1fpx; }" % (name, w, h))
        out.append("@media (prefers-reduced-motion: no-preference) {")
        out.append("  .%s { animation: trek-%s 26s linear infinite; }" % (name, name))
        out.append("  .%s > span { animation: hop-%s 26s ease-out infinite; }"
                   % (name, name))
        out.append("  .%s .bot { animation: face-%s 26s steps(1) infinite; }"
                   % (name, name))
        out.append("  .%s .rcyc { animation: showwalk-%s 26s steps(1) infinite; }"
                   % (name, name))
        out.append("  .%s .rstand { animation: showstand-%s 26s steps(1) infinite; }"
                   % (name, name))
        # The four poses are held by four delays a quarter of a cycle
        # apart. Change the duration and keep the delays and they no
        # longer divide it -- at some instants two poses show, at others
        # NONE, and the follower vanishes while still animating. Both
        # have to scale together.
        # .rcyc > g, NOT .bot > g. The poses gained a wrapper when the
        # standing frame arrived, and a duration aimed one level too high
        # lands on the groups -- which re-timed the 26s walk/stand window
        # to 0.4s, so a robot's gait flickered four times a second and it
        # never once stood still. It also left these delays sized for a
        # duration the poses no longer had, which is the old vanishing
        # bug all over again.
        out.append("  .%s .bot .rcyc > g { animation-duration: %.3fs; }"
                   % (name, step))
        for k in range(4):
            out.append("  .%s .bot .rcyc .r%d { animation-delay: %.3fs; }"
                       % (name, k, step * k / 4.0))
        out.append("}")
        out.append("@media (prefers-reduced-motion: reduce) {")
        out.append("  .%s { transform: translateX(%.1fpx); }" % (name, AWS + hud))
        out.append("}")
        out.append(track(name, path))
        out.append(hop(name, delay, lift, settled))
        out.append(face(name, path, hud, settled))
        out.append(gait(name, moving(path)))
    return "\n".join(out)


def markup(sprite):
    return "\n      ".join(
        '<div class="follow %s">%s<span>%s</span></div>'
        % (f[0], puff_markup(f[0]), sprite)
        for f in FOLLOWERS)


# What each one puffs out and lets go of ----------------------------------
#
# The model names rise off the big robot, the tool names off the small ones.
# One at a time across the whole chain, each visible for about a second --
# four per cent of the cycle. Any more and it is a tag cloud walking down
# a road.
#
# Back above the robots, where they belong. They were moved under the
# road when the gantries took that air; the answer was to make the
# boards shorter rather than to put the names somewhere they made no
# sense. The rise is 3px, which is what the gap allows.
#
# This is Jayanth's own stack, not a chart of what is popular. The first
# version listed sixteen names picked on general prominence -- Cursor,
# Devin, Windsurf, Llama, Mistral -- and a contact card naming tools you
# do not use is a claim you have to defend to anyone who asks. Three you
# can talk about beat sixteen you cannot.
PUFFS = [
    ("f1", ["Claude", "ChatGPT", "Gemini", "Grok", "DeepSeek"]),
    ("f2", ["Claude Code", "Codex"]),
    ("f3", ["Kiro", "Antigravity"]),
    ("f4", ["Copilot"]),
    ("f5", ["Bedrock Agents"]),
    ("f6", ["Grok bot"]),
]
PUFF_CYCLE = 42.0          # not a multiple of the 26s walk, so the two
                           # never fall into step and start looking canned
PUFF_DUTY = 4.0            # per cent of the cycle a name is on screen


def puff_css():
    # The -50% is inside every keyframe on purpose. transform is one
    # property: a keyframe setting translateY REPLACES the translateX that
    # was centring the label, and the name drifts half its own width off
    # the robot it belongs to.
    d = PUFF_DUTY
    out = ["""@keyframes puff {
  0%% { opacity: 0; transform: translate(-50%%, 2px); }
  %.2f%% { opacity: .95; transform: translate(-50%%, 0); }
  %.2f%% { opacity: .95; transform: translate(-50%%, -1px); }
  %.2f%% { opacity: 0; transform: translate(-50%%, -3px); }
  100%% { opacity: 0; transform: translate(-50%%, -3px); }
}""" % (d * 0.16, d * 0.62, d),
".puff { position: absolute; left: 50%; bottom: 100%; margin-bottom: 1px;",
"        width: 0; pointer-events: none; }",
".puff b { position: absolute; left: 0; bottom: 0; opacity: 0;",
"          transform: translate(-50%, 0); white-space: nowrap;",
"          font-family: inherit; font-size: 6px; font-weight: 700;",
"          font-style: normal; line-height: 1; letter-spacing: .06em;",
"          text-transform: none; color: var(--muted); }",
"@media (prefers-reduced-motion: no-preference) {"]
    slot = 0
    total = sum(len(n) for _, n in PUFFS)
    step = PUFF_CYCLE / total
    for name, words in PUFFS:
        for i in range(len(words)):
            out.append("  .%s .puff b:nth-child(%d) { animation: puff %.0fs "
                       "ease-out %.2fs infinite; }"
                       % (name, i + 1, PUFF_CYCLE, 1.5 + slot * step))
            slot += 1
    out.append("}")
    return "\n".join(out)


def puff_markup(name):
    for n, words in PUFFS:
        if n == name:
            return ('<i class="puff">%s</i>'
                    % "".join("<b>%s</b>" % w for w in words))
    return ""
