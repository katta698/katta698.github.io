# -*- coding: utf-8 -*-
"""Who travels and who stays, and where the ones who stay are posted.

The six robots used to be a retinue: all of them walked behind him
everywhere, which says the work follows the person. It does not. The
agents are already running in each cloud whether he is stood next to
them or not -- the Azure series and its labs, the GCP series, the AWS
series and the weekly labs -- so a picture with all of them at his heels
is a picture of the wrong thing.

So one robot travels and five are posted:

  the model    walks with him everywhere. It is the Gen AI model he
               actually works in, and the name on it cycles, because
               which one it is changes week to week.
  Azure        one agent, posted, standing by its board.
  GCP          one agent, posted, standing by its board.
  AWS          three, because that is where most of the work is.

He crosses to Azure and back, to GCP and back, and spends the rest of
the loop at AWS with the crew that lives there -- which is the true
shape of it, and needs no caption.
"""

# Where HE stops, which is no longer under the middle of each board.
# The agents took that spot: they are what the cloud is, so they stand at
# the drop line and he walks up and stands beside them. He used to have
# it and they were pushed out to one side, which is what made them look
# like they were watching rather than working.
AZURE, AWS, GCP = 33.9, 107.1, 180.3
GROUND = 42.0        # where every foot lands

# The loop, in per cent of the 26s cycle. Both legs are the same length
# on purpose -- Azure is 73px from AWS and GCP is 74 -- so the two trips
# take the same time and neither cloud reads as further away than it is.
#
# Azure and GCP get a real stop now, not just a turn. There is somebody
# posted at each of them, and a visit you cannot see him standing through
# is not a visit.
LEG = 13.0                        # per cent of the loop spent walking a leg
AT_AZ, OFF_AZ = 13.0, 21.0        # reach Azure, two seconds, head back
HOME_1, OFF_HOME = 34.0, 36.0     # back through AWS without stopping
AT_GCP, OFF_GCP = 49.0, 57.0      # reach GCP, two seconds, head back
HOME_2 = 70.0                     # home for good
JUMP = 80.0                       # and the two of them jump

SPEED = (AWS - AZURE) / LEG       # his pace, in px per per-cent
VMAX = SPEED * 1.2                # the model's -- a little quicker, so it
                                  # can cross him at a stop and still be
                                  # in place before he moves off again

STOPS = [(0.0, AWS), (AT_AZ, AZURE), (OFF_AZ, AZURE),
         (HOME_1, AWS), (OFF_HOME, AWS), (AT_GCP, GCP), (OFF_GCP, GCP),
         (HOME_2, AWS), (100.0, AWS)]

# Where he is standing still. The model settles beside him inside these
# and trails him outside them. The pass back through AWS at HOME_1 is
# deliberately not one: he does not stop there, so neither does it.
RESTS = [(AT_AZ, OFF_AZ), (AT_GCP, OFF_GCP), (HOME_2, 100.0)]


def man_at(pct):
    """Where the leader is at a given point of the loop."""
    for (p0, x0), (p1, x1) in zip(STOPS, STOPS[1:]):
        if p0 <= pct <= p1:
            return x0 if p1 == p0 else x0 + (x1 - x0) * (pct - p0) / (p1 - p0)
    return AWS


def resting(pct):
    return any(a <= pct <= b for a, b in RESTS)


# The one that travels. name, px behind on the march, height, seconds per
# step, hop delay, and where it stands when he stops.
#
# That last one is negative: it takes his left at every stop, so he never
# has his back to the model. Coming home from GCP he is already facing
# left, so it costs him no turn at all.
MODEL = ("f1", 15.0, 19.0, 0.48, 0.8, -5.0)

# The ones that stay. name, height, x, how far back it stands, which way
# it faces, and how often it stirs.
#
# Each one stands just right of the drop line of its own board, outside
# the shop behind it, so the board it belongs to is the thing it is
# working under rather than something off in the distance. They had been
# seven to twenty pixels clear of it, which with nothing around them read
# as a row of spectators.
# and the model always takes his left, so at each stop the three of them
# line up the same way: model, him, the agent who lives there. The first
# version put the Azure outpost out past its board on the far side and it
# read as stranded rather than posted -- fifteen pixels clear of the only
# thing that said which cloud it was standing in.
#
# It also means the AWS crew is a crew: three together to the right of
# the board, rather than two of them with a gap between where his own
# place is. An empty slot in a group of five reads as somebody missing.
#
# The x values come from scripts/measure_connect_formation.py, which
# reports the gaps that are actually rendered. Box edges lie about this:
# a figure's SVG box is much wider than the figure in it -- his is 17px
# around 8px of ink -- so offsets that look tight on paper leave gaps
# wider than the robots standing in them.
STATIONS = [
    #  name  height   x      back  faces  stirs
    ("f2", 11.0,  50.8,  0.0,  -1,  3.1),   # the Azure outpost
    ("f3", 11.0, 197.2,  0.0,  -1,  3.7),   # the GCP outpost
    ("f4", 12.0, 124.0,  0.0,  -1,  3.4),   # and the AWS crew
    ("f5", 11.0, 132.2,  0.0,  -1,  4.0),
    ("f6", 10.0, 140.0, -2.5,  -1,  4.6),
]


def follow(back, hud, dt=0.05):
    """Walk the model through the loop instead of placing it.

    Hand-written keyframes kept producing the same two faults, because
    both are what you get from saying where something should BE without
    asking whether it could have got there: a figure given an arrival
    time it cannot reach sprints at twice the pace its legs animate at,
    and several given the same one converge into a heap.

    So this is a pursuit. It wants to be `back` behind him on whichever
    side is behind while he walks, and beside him at `hud` while he
    stands; it moves at VMAX and no faster; and where it ends up is
    wherever that leaves it. The crossing it does at Azure -- he arrives
    walking left, so the model is on his right, and its place is on his
    left -- falls out of those two rules rather than being timed by hand.

    Closing the loop needs no second pass: the last stop pins it beside
    him, so t=100 always lands where t=0 starts.
    """
    p, side, path = AWS + hud, 1.0, []
    for k in range(int(100.0 / dt) + 1):
        t = k * dt
        ahead, behind = man_at(min(100.0, t + dt)), man_at(max(0.0, t - dt))
        if ahead < behind - 1e-9:
            side = 1.0          # he is heading left, so behind him is right
        elif ahead > behind + 1e-9:
            side = -1.0
        target = man_at(t) + (hud if resting(t) else back * side)
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


def moving(path, eps=0.02, knit=1.0):
    """The stretches of the loop the model is actually walking.

    A figure only steps while it is going somewhere. Every robot used to
    run its walk cycle for the whole 26s regardless, so one that stopped
    stopped by marching on the spot -- a treadmill, which undoes the one
    thing a stop exists to say.

    Gaps shorter than `knit` are knitted up: crawling the last pixel into
    place dips under the threshold for a twentieth of a second at a time,
    and honouring every one of those would emit sixty keyframes to
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


def _frames(name, kind, keys, fmt):
    out = ["@keyframes %s-%s {" % (kind, name)]
    for pct, val in keys:
        out.append("  %.2f%% { transform: %s; }" % (pct, fmt % val))
    out.append("}")
    return chr(10).join(out)


def gait(name, spans):
    """Walking pose on while it walks, standing pose on while it stands.

    steps(1) and windows that tile exactly, for the reason written up
    over showwalk in make_connect_road.py: adjacent keyframe stops still
    interpolate across the gap between them, and interpolating between
    two silhouettes is how a figure ends up part-drawn.
    """
    marks = [(0.0, False)]
    for a, b in spans:
        marks += [(a, True), (b, False)]
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


def face(name, path, hud):
    """Facing the way it is actually walking, read off the simulation.

    By hand this was wrong twice, because the model's turns do not happen
    where his do: it keeps walking toward Azure for a moment after he has
    turned round, which is the whole reason it swings in behind him
    rather than pivoting with him. The velocity already knows. Once it is
    parked for the last time, it faces him.
    """
    look = 1 if hud < 0 else -1
    keys, last = [], None
    for (t0, p0), (t1, p1) in zip(path, path[1:]):
        if abs(p1 - p0) < 1e-6:
            continue
        d = -1 if p1 < p0 else 1
        if d != last:
            keys.append((t0, d))
            last = d
    keys.append((99.5, look))
    out = ["@keyframes face-%s {" % name]
    for i, (t, d) in enumerate(keys):
        nxt = keys[i + 1][0] if i + 1 < len(keys) else 100.0
        out.append("  %.2f%%, %.2f%% { transform: scaleX(%d); }"
                   % (t, max(t, nxt - 0.01), d))
    out.append("}")
    return chr(10).join(out)


def hop(name, delay):
    """Up after him -- the model catches the jump a beat late."""
    a = JUMP + delay
    return _frames(name, "hop", [
        (0.0, 0.0), (a, 0.0), (a + 1.5, -5.0), (a + 3.0, 0.0), (100.0, 0.0),
    ], "translateY(%.1fpx)")


def stir(name, lift):
    """A posted robot is working, not frozen.

    Standing perfectly still for twenty-six seconds reads as a prop. One
    small dip, on its own clock rather than the loop's, is enough to say
    somebody is home -- and because the five periods are all different
    and none of them divides 26, they never fall into step and start
    looking choreographed.

    It carries the depth offset too, because transform is one property
    and this is the one already on the element: a robot standing a row
    back is drawn a couple of pixels higher, the way anything further
    away sits higher in a frame.
    """
    return _frames(name, "stir", [
        (0.0, lift), (54.0, lift), (62.0, lift - 1.6),
        (70.0, lift), (100.0, lift),
    ], "translateY(%.1fpx)")


def css():
    out = []

    # --- the one that travels ----------------------------------------
    name, back, h, step, delay, hud = MODEL
    w = round(h * 11.0 / 19.0, 1)
    path = follow(back, hud)
    out.append(".%s { top: %.0fpx; width: %.1fpx; z-index: 3; }"
               % (name, GROUND - h, w))
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
    # The four poses are held by four delays a quarter of a cycle apart,
    # and the selector reaches the POSES, not the groups they sit in. One
    # level too high and the duration lands on the 26s gait window and
    # re-times it to half a second.
    out.append("  .%s .bot .rcyc > g { animation-duration: %.3fs; }" % (name, step))
    for k in range(4):
        out.append("  .%s .bot .rcyc .r%d { animation-delay: %.3fs; }"
                   % (name, k, step * k / 4.0))
    out.append("}")
    out.append("@media (prefers-reduced-motion: reduce) {")
    out.append("  .%s { transform: translateX(%.1fpx); }" % (name, AWS + hud))
    out.append("}")
    out.append(_frames(name, "trek", _simplify(path), "translateX(%.1fpx)"))
    out.append(hop(name, delay))
    out.append(face(name, path, hud))
    out.append(gait(name, moving(path)))

    # --- the ones that stay ------------------------------------------
    for name, h, x, lift, look, period in STATIONS:
        w = round(h * 11.0 / 19.0, 1)
        out.append(".%s { top: %.0fpx; width: %.1fpx; z-index: %d;"
                   " transform: translateX(%.1fpx); }"
                   % (name, GROUND - h, w, 3 + int(round(lift / 2.0)), x))
        out.append(".%s .bot { width: %.1fpx; height: %.1fpx;"
                   " transform: scaleX(%d); }" % (name, w, h, look))
        # Posted, so: never the walk cycle, always the standing pose.
        # Written flat rather than as a 26s window, because there is no
        # window -- it does not walk at any point of the loop.
        out.append(".%s .rcyc { opacity: 0; }" % name)
        out.append(".%s .rstand { opacity: 1; }" % name)
        out.append("@media (prefers-reduced-motion: no-preference) {")
        out.append("  .%s > span { animation: stir-%s %.1fs ease-in-out"
                   " infinite; }" % (name, name, period))
        out.append("}")
        out.append("@media (prefers-reduced-motion: reduce) {")
        out.append("  .%s > span { transform: translateY(%.1fpx); }"
                   % (name, lift))
        out.append("}")
        out.append(stir(name, lift))
    return chr(10).join(out)


# A little open laptop, drawn rather than dotted in: a base, a screen
# raked back, and a hinge between them. Three pixels tall at the foot of
# a ten-pixel robot, which is all it takes -- a figure with something in
# front of it is working, and a figure with empty hands is watching. That
# was the real complaint. Being a few pixels off the board was only how
# it showed.
# A data centre on the far side of the road, one per cloud --------------
#
# The agents had laptops and it read as robots sitting in a carriageway.
# Then they had a coffee shop, which fixed where they were standing but
# not what they were standing at. A data centre is the right building:
# it is what a cloud actually is, the agents are minding it, and the
# services come out of it rather than off a sign.
#
# The awning went with the coffee shop. It was there because a coloured
# band across a shopfront is about the only thing that separates a shop
# from a plain block at eleven pixels -- but a rust smear on a building
# is what it looked like, and a data centre does not have one.
#
# What says data centre at this size is repetition: one long low block,
# a flat roof with plant on it, and a regular row of lit slots. Nothing
# pitched, nothing domestic. Behind everything at z-index 0, muted and
# part-transparent, because the far side of a street is not the subject.
def _datacentre(wide):
    w, units = (68.0, 3) if wide else (38.0, 2)
    o = ['<svg class="shops" viewBox="0 0 %.0f 22" aria-hidden="true">'
         % w]
    # plant on the roof, which is the half of the silhouette that is not
    # just a box
    for i in range(units):
        x = 5.0 + i * (w - 16.0) / max(units - 1, 1)
        o.append('<path d="M%.1f 2.5h7v4h-7Z"/>' % x)
    o.append('<path d="M0 6.5h%.1fv15.5H0Z"/>' % w)
    # a row of lit slots, evenly spaced, which is the other half
    n = int(w // 8)
    gap = w / n
    for i in range(n):
        o.append('<rect class="win" x="%.1f" y="10" width="2.6" height="5.5"/>'
                 % (gap * i + gap / 2.0 - 1.3))
    # and a door, so there is a way in
    o.append('<rect class="win" x="%.1f" y="16.5" width="5" height="5.5"/>'
             % (w / 2.0 - 2.5))
    o.append('</svg>')
    return "".join(o)


def _shops(wide):
    return _datacentre(wide)


SHOPS_WIDE = _shops(True)
SHOPS_SMALL = _shops(False)


def markup(sprite):
    return "\n      ".join(
        '<div class="follow %s">%s<span>%s</span></div>'
        % (n, puff_markup(n), sprite)
        for n in [MODEL[0]] + [s[0] for s in STATIONS])


# What each one puffs out and lets go of ----------------------------------
#
# The model breathes out MODELS, because which one he is working in
# changes week to week. Every posted agent breathes out its own name and
# then the services it minds in the cloud it is standing in -- which is
# the point of posting them there at all. Azure's services rise over
# Azure, GCP's over GCP, and AWS's over the three at AWS.
#
# The tool names stayed. Each agent leads with its own -- Copilot at
# Azure, Antigravity at GCP, Kiro and Bedrock Agents at AWS -- because
# dropping them to make room for services would have traded the half of
# this that is Jayanth's actual stack for the half that is any cloud
# diagram. Both halves are true and both fit.
#
# This is his own stack, not a chart of what is popular. The first
# version listed sixteen tools picked on general prominence -- Cursor,
# Devin, Windsurf, Llama, Mistral -- and a contact card naming tools you
# do not use is a claim you have to defend to anyone who asks. The
# services are held to the same standard: the ones a platform engineer
# actually touches, not the ones with the best launch posts.
#
# One queue PER CLOUD, so all three speak at once ------------------------
#
# There was a single queue across the whole card, and it was right while
# the labels could reach each other: twenty-nine names taking turns, one
# every two seconds. The cost was that any given cloud got a word in once
# a minute, from a list of four, so the services were barely there.
#
# They cannot reach each other any more. The labels are anchored to the
# data centres now and left-aligned at each one's near corner, and
# scripts/../\_sweep measured the room between them: Azure has 73px
# before AWS's labels start, AWS has 73px before GCP's, and GCP has 143px
# to the card edge at the narrowest width the card is read at. Nothing
# here is longer than eighteen characters, which is about 65px. So the
# three clouds each run their own stream and none of them waits.
#
# Each cloud's queue carries its agent's own name as well as its
# services, which is what keeps THOSE from colliding: an agent stands in
# front of its building, so the two labels share a column and must share
# a queue.
#
# The model is the exception and it gets its own answer further down.
MODELS = ["Claude", "ChatGPT", "Gemini", "Grok", "DeepSeek"]

# The services a platform engineer actually touches, not the ones with
# the best launch posts -- the same standard the tool names are held to.
AZURE_SVCS = [
    "Entra ID", "AKS", "Azure Functions", "Blob Storage", "VNet",
    "Key Vault", "Cosmos DB", "Azure SQL", "App Service", "Azure Monitor",
    "Log Analytics", "Service Bus", "Event Hubs", "Front Door",
    "Container Apps", "Load Balancer", "Private Link", "Bicep",
]
AWS_SVCS = [
    "IAM", "VPC", "EC2", "S3", "Lambda", "DynamoDB", "EKS", "ECS",
    "Fargate", "RDS", "Aurora", "CloudFront", "Route 53", "CloudWatch",
    "CloudTrail", "EventBridge", "SQS", "SNS", "KMS", "Secrets Manager",
    "API Gateway", "Step Functions", "Transit Gateway", "CloudFormation",
    "Organizations", "GuardDuty", "Systems Manager",
]
GCP_SVCS = [
    "GKE", "BigQuery", "Cloud Run", "Cloud Storage", "Cloud SQL",
    "Pub/Sub", "Spanner", "Vertex AI", "Dataflow", "Firestore",
    "Cloud Armor", "Cloud IAM", "Cloud DNS", "Cloud Build",
    "Artifact Registry", "Cloud Logging", "Bigtable", "Dataproc",
]
# Which agent says its own name in which cloud's queue.
AWS_AGENTS = [("f4", "Kiro"), ("f4", "Claude Code"), ("f5", "Bedrock Agents"),
              ("f5", "Codex"), ("f6", "Grok bot")]

VISIBLE = 1.5              # seconds a name is legible, whatever its queue


def _aws_queue():
    """The agents' own names spread through the services, not bunched.

    All five in a row at the top of a thirty-two name queue is ten
    seconds of robots introducing themselves followed by a minute of
    nothing but AWS, which is not what the card is about.
    """
    out, step = [], max(len(AWS_SVCS) // len(AWS_AGENTS), 1)
    ag = list(AWS_AGENTS)
    for i, svc in enumerate(AWS_SVCS):
        if i % step == 0 and ag:
            who, txt = ag.pop(0)
            out.append((who, "bot", txt))
        out.append(("s-aws", "sign", svc))
    out += [(who, "bot", txt) for who, txt in ag]
    return out


# name, seconds between one name and the next, and the entries.
# The four periods are all different and none divides the 26s walk, so
# the card never settles into a rhythm.
QUEUES = [
    ("model", 3.6, [("f1", "bot", n) for n in MODELS]),
    ("azure", 2.6, [("f2", "bot", "Copilot")]
     + [("s-azu", "sign", n) for n in AZURE_SVCS]),
    ("aws", 2.0, _aws_queue()),
    ("gcp", 2.8, [("f3", "bot", "Antigravity")]
     + [("s-gcp", "sign", n) for n in GCP_SVCS]),
]


def queue_slots():
    """Every name, with the queue it is in and its place in that queue."""
    for qname, step, entries in QUEUES:
        cycle = step * len(entries)
        for slot, (who, kind, txt) in enumerate(entries):
            yield qname, cycle, step, slot, who, kind, txt


def _texts(target):
    """Everything one element says, in the order its <b> tags appear."""
    out = []
    for _q, _c, _s, _slot, who, kind, txt in queue_slots():
        if who == target:
            out.append(txt)
    return out


def _keyframes(qname, cycle, down, left):
    """One on-window, sized so every queue shows a name for VISIBLE seconds.

    The queues run at different lengths, so a duty written as one
    percentage would mean a name lingering for four seconds on the short
    queue and flashing for one on the long one.
    """
    d = 100.0 * VISIBLE / cycle
    y0, y1 = (-2, 2) if down else (2, -2)
    x = "0" if left else "-50%"
    return ("@keyframes %s {\n"
            "  0%% { opacity: 0; transform: translate(%s, %dpx); }\n"
            "  %.2f%% { opacity: .95; transform: translate(%s, 0); }\n"
            "  %.2f%% { opacity: .95; transform: translate(%s, %.1fpx); }\n"
            "  %.2f%% { opacity: 0; transform: translate(%s, %dpx); }\n"
            "  100%% { opacity: 0; transform: translate(%s, %dpx); }\n"
            "}" % (qname, x, y0, d * 0.16, x, d * 0.62, x, y1 * 0.5,
                   d, x, y1, x, y1)).replace("\n", chr(10))


def puff_css():
    # The -50% is inside every keyframe on purpose. transform is one
    # property: a keyframe setting translateY REPLACES the translateX that
    # was centring the label, and the name drifts half its own width off
    # the thing it belongs to.
    out = []
    seen = set()
    for qname, cycle, _step, _slot, _who, kind, _txt in queue_slots():
        key = (qname, kind)
        if key in seen:
            continue
        seen.add(key)
        down = qname == "model"
        out.append(_keyframes("%s-%s" % (kind, qname), cycle, down,
                              kind == "sign"))
    out += [
        ".puff { position: absolute; left: 50%; bottom: 100%;",
        "        margin-bottom: -1px; width: 0; pointer-events: none; }",
        "/* The model's name hangs BELOW the road, and it is the only one",
        "   that does. Everything else is anchored to something that never",
        "   moves, so a queue per cloud is enough to keep two labels apart;",
        "   the model walks the whole road and would sooner or later pass",
        "   under every one of them. Under the tarmac is nine pixels nobody",
        "   else is using, and it reads as his companion rather than as",
        "   something a cloud is offering, which is the truth of it. */",
        ".f1 .puff { bottom: auto; top: 100%; margin-top: 1px; }",
        "/* Anchored to the DATA CENTRE and left-aligned at its near",
        "   corner, rising off the roof. A service comes out of the",
        "   building that runs it. */",
        ".svcs { position: absolute; left: var(--svcx); top: 22px; width: 0;",
        "        pointer-events: none; z-index: 5; }",
        ".puff b, .svcs b { position: absolute; left: 0; opacity: 0;",
        "          transform: translate(-50%, 0); white-space: nowrap;",
        "          font-family: inherit; font-size: 6px; font-weight: 700;",
        "          font-style: normal; line-height: 1; letter-spacing: .06em;",
        "          text-transform: none; color: var(--muted); }",
        "/* AFTER the shared rule, not before it: same specificity, so the",
        "   later one wins. Before it, the static transform stayed centred",
        "   while the keyframes ran left-aligned -- the animation was right",
        "   and every still of it was wrong, which is worse than both being",
        "   wrong, because the check takes the still. */",
        ".svcs b { bottom: 0; transform: translate(0, 0); }",
        "/* Colour says which cloud a name belongs to, which is work the",
        "   position was doing on its own and not doing well: every label",
        "   was the same ink, so a service and an agent and a model name",
        "   all read as one kind of thing in one pile. They are three",
        "   kinds of thing.",
        "",
        "   The three cloud colours are the ones already on the boards, so",
        "   a service arrives in the colour of the board it belongs under",
        "   and nothing new is introduced. An agent takes the colour of",
        "   the cloud it is posted at, because that is what it is: the",
        "   thing minding that cloud.",
        "",
        "   The model takes rust, which is the card's own accent and the",
        "   one colour here that belongs to no cloud -- correctly, because",
        "   it is the only one of them that travels. */",
        "/* --c-model is the card's rust taken a shade further than the",
        "   seal's. The seal and the name wink are display type, where",
        "   the floor is 3:1 and rust clears it easily; these are six",
        "   pixels, where the floor is 4.5:1 and it measured 3.84 on",
        "   paper and 4.24 at night. A shade down in daylight and a",
        "   shade up in the dark puts both at 4.6:1, hue unmoved. */",
        ".road { --c-azu: #33506d; --c-aws: #6a4e30; --c-gcp: #49552b;",
        "        --c-model: #943b25; }",
        '[data-theme="dark"] .road {',
        "  --c-azu: #9fbcd8; --c-aws: #c9a06e; --c-gcp: #a0b378;",
        "  --c-model: #cb6b3f; }",
        ".s-azu b, .f2 .puff b { color: var(--c-azu); }",
        ".s-aws b, .f4 .puff b, .f5 .puff b, .f6 .puff b { color: var(--c-aws); }",
        ".s-gcp b, .f3 .puff b { color: var(--c-gcp); }",
        ".f1 .puff b { color: var(--c-model); }",
        "@media (prefers-reduced-motion: no-preference) {"]
    nth = {}
    for qname, cycle, step, slot, who, kind, _txt in queue_slots():
        nth[who] = nth.get(who, 0) + 1
        out.append("  .%s %s b:nth-child(%d) { animation: %s-%s %.1fs "
                   "ease-out %.2fs infinite; }"
                   % (who, ".svcs" if kind == "sign" else ".puff", nth[who],
                      kind, qname, cycle, 1.5 + slot * step))
    out.append("}")
    return chr(10).join(out)


def puff_markup(name):
    words = _texts(name)
    if not words:
        return ""
    return ('<i class="%s">%s</i>'
            % ("svcs" if name.startswith("s-") else "puff",
               "".join("<b>%s</b>" % w for w in words)))
