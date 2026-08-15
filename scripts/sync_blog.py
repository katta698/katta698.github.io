"""
Build the blog: read posts/*.md and posts/*.html → clean → build static
pages at blog/. No Blogger dependency — every post lives locally in this
repo. (One-time Blogger migration: scripts/migrate_from_blogger.py.)

Usage:
  python scripts/sync_blog.py
"""

import hashlib
import json
import math
import shutil
import os
import re
import sys
from datetime import datetime
from html import escape
from pathlib import Path
from urllib.parse import quote_plus

import markdown
import yaml
from bs4 import BeautifulSoup

# ── Paths (relative to repo root) ─────────────────────────────
REPO_ROOT   = Path(__file__).parent.parent
BLOG_DIR    = REPO_ROOT / "blog"
POSTS_DIR   = REPO_ROOT / "posts"
ASSETS_URL  = "/blog/assets"

# Hash the repository form of a file, not the working-tree form.
#
# core.autocrlf is true and there is no .gitattributes, so text files are LF in
# the repository and CRLF on disk on Windows. Hashing the bytes as they sit on
# disk therefore produces a different token per checkout: blog.css hashed to
# 2e1d6b7d from a CRLF working tree and 649ff170 from the committed LF form.
#
# That is not cosmetic. Every worktree that ran sync would re-stamp the token to
# its own value and commit it, so two worktrees pushing in turn would flip it
# back and forth forever — each one "fixing" what the other just wrote, with a
# full rebuild of every page in the diff each time. Normalising line endings
# first makes the token a function of content alone, which is what it was always
# meant to be.
def _content_hash(*paths):
    h = hashlib.md5()
    for p in paths:
        h.update(p.read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()[:8]


# Cache-bust blog.css with a short content hash, so a CSS change is
# guaranteed to bypass any stale browser/CDN cache instead of relying on
# everyone hitting a hard refresh.
def _css_version():
    return _content_hash(REPO_ROOT / "blog" / "assets" / "blog.css")

CSS_VERSION = _css_version()


# Cache-bust the JavaScript the same way. blog.js and site-footer.js share one
# combined hash deliberately: blog.js injects site-footer.js at runtime and
# passes its own token straight through, so a single version means a change to
# either file busts both. They are a few KB each — there is nothing to gain
# from versioning them separately, and plenty to lose when the injected one
# silently keeps running a cached copy.
#
# This is not cosmetic. site-footer.js registers the service worker; while it
# was unversioned, a returning visitor kept executing a cached copy and never
# registered at all.
def _js_version():
    # hero-media.js is included: it is loaded by every page, and without it in
    # the hash a change to the rotation would ship behind a cached old copy.
    return _content_hash(*[REPO_ROOT / "blog" / "assets" / name
                           for name in ("blog.js", "site-footer.js",
                                        "hero-media.js", "occasion-banner.js")])


JS_VERSION = _js_version()

# ── PWA ───────────────────────────────────────────────────────
# The whole site is installable as a progressive web app — not just /blog/.
# Site-wide scope is deliberate: the nav links Home, Blog and Resume, so a
# /blog/-scoped app would eject the reader out to the browser on the second
# link they tapped.
#
# These tags render nothing. Desktop browsers show a small install control in
# the address bar once a manifest and a registered service worker both exist;
# that is browser chrome, not page content, and there is deliberately no
# beforeinstallprompt banner.
#
# The same six tags are hand-maintained in index.html, resume.html, now.html
# and the arch pages/template — everything sync_blog.py does not build. Keep
# them in step when changing anything here.
#
# Registration itself lives in blog/assets/site-footer.js, the one script every
# page on the site loads.
PWA_HEAD = """<link rel="manifest" href="/manifest.webmanifest"/>
<meta name="theme-color" content="#1D2322"/>
<link rel="apple-touch-icon" href="/blog/assets/icons/apple-touch-icon.png"/>
<meta name="apple-mobile-web-app-capable" content="yes"/>
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent"/>
<meta name="apple-mobile-web-app-title" content="Jayanth Katta"/>"""


def stamp_static_pages():
    """Re-stamp asset cache-busting tokens on the pages sync does not build.

    index.html, resume.html and now.html are hand-maintained, and the AWS and
    Azure Architecture Series pages are built from _templates/arch-post-template.html
    at publish time and otherwise passed through untouched. All of them reference blog.js or site-footer.js,
    so without this they would pin whatever token they were written with while
    the files underneath them changed.

    This is deliberately narrow: it rewrites an existing ?v= token on the two
    script URLs and the stylesheet, and nothing else. It does not regenerate the
    pages, and it will not add a token to a page that has no reference. The arch
    pages' read-only pass-through (see the "externally_built" note) still holds.

    blog.css is stamped here for the same reason blog.js is, and the omission
    was a standing chore rather than a decision: validate_arch_post.py check 9
    compares each arch page's token against md5(blog.css), so every stylesheet
    change failed the validator on all 18 arch pages at once and had to be
    cleared by hand, one file at a time, before anything else could ship.
    """
    targets = [REPO_ROOT / n for n in ("index.html", "resume.html", "now.html")]
    targets += sorted(BLOG_DIR.glob("aws-architecture-*/index.html"))
    targets += sorted(BLOG_DIR.glob("azure-architecture-*/index.html"))
    targets += sorted(BLOG_DIR.glob("gcp-architecture-*/index.html"))
    targets.append(REPO_ROOT / "_templates" / "arch-post-template.html")

    # A URL may already carry literal tokens, and — in the template — a
    # {{PLACEHOLDER}} the build script substitutes at publish time. Match both,
    # and leave a placeholder alone: stamping a line that already held one is
    # what produced `blog.css?v=<hash>?v={{CSS_VERSION}}` in
    # arch-post-template.html, a doubled query string every page built from the
    # template then inherited. Static servers ignore the query, so nothing broke
    # visibly; the cache key was simply not the thing it appeared to be.
    def _pattern(url):
        return re.compile(url + r'((?:\?v=[0-9a-zA-Z]+)*)(\?v=\{\{[A-Z_0-9]+\}\})?')

    js_pattern = _pattern(r'(/blog/assets/(?:blog|site-footer|occasion-banner)\.js)')
    css_pattern = _pattern(r'(/blog/assets/blog\.css)')

    def _stamp(version):
        def sub(m):
            # A placeholder wins: the build script owns that token.
            return m.group(1) + (m.group(3) or f"?v={version}")
        return sub

    stamped = 0
    for path in targets:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        new = js_pattern.sub(_stamp(JS_VERSION), text)
        new = css_pattern.sub(_stamp(CSS_VERSION), new)
        if new != text:
            path.write_text(new, encoding="utf-8")
            stamped += 1
    print(f"  {stamped} static page(s) re-stamped to js v={JS_VERSION}, css v={CSS_VERSION}")


def write_service_worker():
    """Generate sw.js at the repo root from scripts/sw.template.js.

    It has to sit at the root, not under blog/: a service worker can only claim
    a scope at or below its own path, and this one claims "/".

    The cache name is stamped with CSS_VERSION — the same content hash that
    cache-busts blog.css — so a stylesheet change invalidates the whole cache
    without anyone having to remember to bump a version constant.
    """
    template = (REPO_ROOT / "scripts" / "sw.template.js").read_text(encoding="utf-8")
    (REPO_ROOT / "sw.js").write_text(
        template.replace("__CACHE_VERSION__", CSS_VERSION)
                .replace("__JS_VERSION__", JS_VERSION), encoding="utf-8"
    )
    print(f"  sw.js written at site root (cache jk-site-{CSS_VERSION})")

SITE_URL    = "https://jayanthkatta.com"
BLOG_URL    = f"{SITE_URL}/blog"
DISQUS_ID   = "jayanthkatta"
API_URL     = "https://37arp5b92a.execute-api.us-east-1.amazonaws.com/search"
SUMMARY_API_URL = "https://37arp5b92a.execute-api.us-east-1.amazonaws.com/summary"

# ── AWS service detection ─────────────────────────────────────
# Two mechanisms, because neither works alone.
#
# SEED_SERVICES is the curated vocabulary and the only thing that ever reaches
# a reader. A pure auto-discovery pass was tried and produced bubbles labelled
# "What", "They" and "Auto" -- prose is full of capitalised words following the
# token "AWS", and there is no reliable way to tell a service from a sentence.
#
# The discovery pass survives, but only as a gap detector: it finds candidates
# the curated list does not know about and sync prints them as a warning. That
# is the part that means the list never has to be maintained speculatively --
# write about a service nobody has covered before, and the next sync says so by
# name. What it must not do is put its guesses in front of visitors.
#
# The list this replaced held 43 names and silently hid 36 services that had
# been written about -- Aurora, Bedrock, Backup, Security Hub, CloudTrail and
# CloudFormation among them. Nothing errored; the widget just under-reported.
SERVICE_PREFIX_RE = re.compile(
    r"\b(?:AWS|Amazon)\s+"
    r"((?:[A-Z][A-Za-z0-9]*|for\s+[A-Z][A-Za-z0-9]*)"
    r"(?:\s+(?:[A-Z][A-Za-z0-9]*|for))*)"
)

# Things that follow "AWS"/"Amazon" and are not services. Without this the
# widget fills up with "AWS Region", "AWS Account" and "AWS Documentation".
NOT_SERVICES = {
    "Region", "Regions", "Account", "Accounts", "Console", "Management",
    "Management Console", "Documentation", "Docs", "CLI", "SDK", "API", "APIs",
    "Support", "Partner", "Partners", "Marketplace", "Free", "Free Tier",
    "Cloud", "Web", "Web Services", "Services", "Service", "Blog", "News",
    "Pricing", "Calculator", "Availability", "Availability Zone", "Resource",
    "Resources", "Customer", "Customers", "Provider", "Global", "Public",
    "Managed", "Native", "Official", "General", "Reference", "Guide",
    "User Guide", "Developer Guide", "Best", "Best Practices", "Whitepaper",
    "Summit", "Builder", "Builders", "Certified", "Training", "Skill Builder",
    "Health", "Status", "Root", "Organization", "Tags", "Tag", "Team",
    "Linux", "Linux 2", "Machine", "Machine Image", "S3 Bucket",
    # This blog's own series titles, which all begin "AWS ...". Without these
    # the gap report is mostly the author's own headings and stops being read.
    "Daily Intelligence", "Weekly Intelligence", "Architecture Series",
    "Platform Engineering Lab", "Platform Engineering", "Weekly Lab",
    "Terraform", "Terraform Challenge", "Certified", "Solutions Architect",
    # Regions, protocols and partitions -- not services.
    "GovCloud", "Europe", "Ireland", "Virginia", "Oregon", "Frankfurt",
    "OIDC", "SSO", "STS", "ARN", "ARNs", "JSON", "YAML", "Well",
    # Fragments the capitalised-word run sweeps up mid-sentence, and feature
    # names that belong to a service already catalogued.
    "Reference AWS", "Transform for", "Backup for Amazon", "Knowledge",
    "Elastic Compute", "EC2 G6f", "Security Hub Extended", "Glue Data Catalog",
    "VPC IPAM", "EC2 Instance Request", "Load Balancer", "Instance Request",
}

# Acronyms and product names that rarely carry an "AWS"/"Amazon" prefix in
# running prose. Discovery alone would miss these, so they are seeded -- but a
# seed still only appears if a post actually mentions it.
SEED_SERVICES = [
    "EC2", "S3", "IAM", "VPC", "RDS", "EKS", "ECS", "ECR", "EBS", "EFS", "FSx",
    "SQS", "SNS", "KMS", "WAF", "SSM", "EMR", "MSK", "DMS", "ALB", "NLB",
    "CloudWatch", "CloudFront", "CloudTrail", "CloudFormation", "DynamoDB",
    "Lambda", "Aurora", "Athena", "Glue", "Redshift", "Kinesis", "Firehose",
    "Fargate", "GuardDuty", "Route 53", "Step Functions", "EventBridge",
    "API Gateway", "Transit Gateway", "NAT Gateway", "Internet Gateway",
    "Direct Connect", "PrivateLink", "Auto Scaling", "Secrets Manager",
    "Security Hub", "Control Tower", "Systems Manager", "Elastic Beanstalk",
    "Global Accelerator", "Storage Gateway", "OpenSearch", "ElastiCache",
    "SageMaker", "Bedrock", "Graviton", "CodePipeline", "CodeBuild",
    "CodeDeploy", "Amplify", "AppSync", "Cognito", "QuickSight", "X-Ray",
]

# Names that are ordinary English words as well as AWS services. Counting these
# by substring is how "Config" became the second-largest bubble on the blog
# index -- 285 of its 426 hits were "configuration" and "configure", and only
# 44 were AWS Config. "ECR" was worse: it matched inside "secret" and came out
# at seven times its real size.
#
# For these, a post must name the service properly at least once before bare
# mentions in that post are counted at all.
AMBIGUOUS_SERVICES = {
    "Config": r"AWS Config|Config rule|Config recorder|Config aggregator",
    "Connect": r"Amazon Connect",
    "Backup": r"AWS Backup",
    "Batch": r"AWS Batch",
    "Shield": r"AWS Shield|Shield Advanced",
    "Glue": r"AWS Glue|Glue (?:crawler|catalog|job|table|database)",
    "Inspector": r"Amazon Inspector",
    "Macie": r"Amazon Macie",
    "Budgets": r"AWS Budgets",
    "MQ": r"Amazon MQ",
    "Organizations": r"AWS Organizations",
    "Outposts": r"AWS Outposts",
    "Detective": r"Amazon Detective",
    "Comprehend": r"Amazon Comprehend",
    "Translate": r"Amazon Translate",
    "Transcribe": r"Amazon Transcribe",
    "Polly": r"Amazon Polly",
    "Connect Family": r"Amazon Connect",
}


# Long-form and legacy spellings of services already in the catalogue. Without
# this the homepage listed "Elastic Kubernetes" beside "EKS" and "Kinesis
# Firehose" beside "Firehose" as if they were different products, which reads
# as padding rather than coverage.
SERVICE_ALIASES = {
    "Elastic Kubernetes": "EKS",
    "Elastic Container Registry": "ECR",
    "Elastic Container": "ECS",
    "Kinesis Firehose": "Firehose",
    "Elastic Load Balancing": "ALB",
    "Relational Database": "RDS",
    "Single Sign-On": "IAM Identity Center",
    "SSO": "IAM Identity Center",
    "SSM": "Systems Manager",
    "API Gateway REST": "API Gateway",
    "WAFV2": "WAF",
    "Elasticsearch": "OpenSearch",
    "Kafka": "MSK",
    "CloudWatch Synthetics": "Synthetics",
    "Parallel Computing": "PCS",
}

# Which domain each service belongs to, for the "posts by AWS domain" donut.
# Only services listed here can classify a post; a newly discovered service
# shows up in the bubble widget immediately but contributes to the donut only
# once it is placed here. That is deliberate -- guessing a domain from a name
# is how the previous version decided "Architecture" meant networking.
SERVICE_DOMAIN = {}
for _domain, _members in {
    "Networking": ["VPC", "CloudFront", "Route 53", "ALB", "NLB", "API Gateway",
                   "Transit Gateway", "NAT Gateway", "Internet Gateway",
                   "Direct Connect", "PrivateLink", "Global Accelerator",
                   "VPC Lattice", "Cloud Map", "Network Firewall", "Cloud WAN",
                   "IPAM"],
    "Security": ["STS", "RAM", "IAM Roles Anywhere", "IAM", "IAM Identity Center",
                 "KMS", "Secrets Manager", "WAF",
                 "Shield", "GuardDuty", "Security Hub", "Inspector", "Macie",
                 "Cognito", "Certificate Manager", "Control Tower",
                 "Organizations", "Verified Access", "Resource Access Manager",
                 "Detective"],
    "Compute": ["PCS", "WorkSpaces", "EC2", "Lambda", "Fargate", "ECS", "EKS", "ECR", "Batch",
                "Auto Scaling", "Graviton", "Spot", "App Runner", "Outposts",
                "Elastic Beanstalk", "Compute Optimizer", "Lightsail",
                "App Mesh"],
    "Data": ["Glacier", "S3 Vectors", "S3 Tables", "DynamoDB Streams",
             "Data Pipeline", "RDS", "Aurora", "DynamoDB", "S3", "EFS", "FSx", "EBS",
             "ElastiCache", "MemoryDB", "DocumentDB", "Neptune", "Redshift",
             "Athena", "Glue", "Kinesis", "Firehose", "MSK", "OpenSearch",
             "EMR", "Lake Formation", "QuickSight", "Backup", "Timestream",
             "Keyspaces", "QLDB", "DMS", "Storage Gateway", "Snowball",
             "DataSync", "DataZone"],
    "Observability": ["CloudWatch", "CloudWatch Logs", "Application Signals",
                      "Synthetics", "Prometheus", "Service Quotas",
                      "CloudTrail", "Config", "X-Ray",
                      "Resilience Hub", "Application Recovery Controller",
                      "Trusted Advisor", "Well-Architected"],
    "Integration": ["SQS", "SNS", "EventBridge", "EventBridge Pipes", "Pipes",
                    "Step Functions", "MQ", "AppFlow"],
    "AI & ML": ["Bedrock", "Bedrock AgentCore", "SageMaker", "Textract", "Comprehend",
                "Rekognition", "Transcribe", "Polly", "Translate", "Kendra",
                "Q Developer"],
    "DevOps & IaC": ["CloudFormation", "CDK", "CodePipeline", "CodeBuild",
                     "CodeDeploy", "CodeArtifact", "CodeCommit",
                     "Systems Manager", "Service Catalog"],
    "Cost": ["Cost Explorer", "Budgets", "Savings Plans",
             "Compute Savings Plans", "Cost and Usage Report"],
    "Apps & Front-end": ["Amplify", "AppSync", "SES", "Connect", "Pinpoint"],
}.items():
    for _svc in _members:
        SERVICE_DOMAIN[_svc] = _domain

# Things people write about that are not services in their own right, so AWS's
# API catalogue does not list them: Aurora is part of RDS, Fargate and Spot are
# EC2/ECS features, ALB is Elastic Load Balancing. Short and stable -- these
# change on the timescale of AWS renaming a flagship product, not weekly.
SERVICE_SUPPLEMENT = [
    "Aurora", "Fargate", "Graviton", "Spot", "ALB", "NLB", "EBS",
    "Transit Gateway", "NAT Gateway", "Internet Gateway", "PrivateLink",
    "VPC Lattice", "Savings Plans", "Compute Savings Plans", "S3 Express",
    "IAM Identity Center", "Security Hub", "Systems Manager", "SSM",
    "Step Functions", "Secrets Manager", "Control Tower", "Storage Gateway",
    "Direct Connect", "Global Accelerator", "Well-Architected", "Firehose",
    "Lake Formation", "Cost Explorer", "API Gateway", "Route 53", "CDK",
]


# name -> (AWS's own one-line description, product page URL). Filled from
# scripts/aws_services.json, which refresh_aws_services.py populates from AWS's
# product pages, so the wording is theirs and the weekly refresh keeps it
# current. Nothing here is written by hand -- a description of a service is a
# factual claim, and this repo already learned what happens when those are
# asserted rather than sourced.
SERVICE_INFO = {}


def load_service_catalogue():
    """The service vocabulary: AWS's own list, plus the supplement above.

    scripts/aws_services.json is generated from botocore's service models by
    scripts/refresh_aws_services.py, and refreshed weekly by a workflow. That
    is what makes new services automatic -- the list of AWS services is AWS's
    to maintain, and a service launched at re:Invent lands here as soon as
    botocore ships it, with nothing to edit in this repo.

    Returns (names, ambiguous) where `ambiguous` are the names that are also
    ordinary English words and therefore need a qualifier before a bare
    mention counts.
    """
    names = set(SERVICE_SUPPLEMENT) | set(SERVICE_DOMAIN)
    ambiguous = set(AMBIGUOUS_SERVICES)
    SERVICE_INFO.clear()

    # Names that cannot be disambiguated from ordinary usage at all. "Account"
    # is a real AWS service, and "AWS account" appears in nearly every post
    # meaning something else entirely -- requiring the qualifier does not help
    # when the qualifier IS the ordinary phrase. It read 15 posts before this.
    # Shared with refresh_aws_services.py, which uses the same list to avoid
    # fetching product pages for them.
    links_path = REPO_ROOT / "scripts" / "service_links.json"
    if links_path.is_file():
        skip = json.loads(links_path.read_text(encoding="utf-8"))
        names -= set(skip.get("skip", {}).get("names", []))

    path = REPO_ROOT / "scripts" / "aws_services.json"
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        for name, meta in data.get("services", {}).items():
            names.add(name)
            if meta.get("ambiguous"):
                ambiguous.add(name)
            if meta.get("desc"):
                SERVICE_INFO[name] = (meta["desc"], meta.get("url", ""))
    else:
        print("  WARNING: scripts/aws_services.json missing — falling back to "
              "the built-in list. Run scripts/refresh_aws_services.py.")

    if links_path.is_file():
        names -= set(json.loads(links_path.read_text(encoding="utf-8"))
                     .get("skip", {}).get("names", []))

    # botocore service ids like "deadline", "forecast" and "identitystore" are
    # lower-case and collide with ordinary words -- "deadline" appeared twice
    # on the homepage from prose about project deadlines. A real service name
    # as written is capitalised.
    names = {n for n in names if n[:1].isupper()}

    # Longest first so "Step Functions" wins over a bare "Step", and so the
    # combined regex below prefers the most specific name at each position.
    return sorted(names, key=lambda s: (-len(s), s)), ambiguous


KNOWN_SERVICES, AMBIGUOUS_NAMES = load_service_catalogue()

# One combined regex instead of 650 separate scans per post. The lookarounds
# do the work \b cannot: \b treats "S3" as ending mid-token inside "S3B", so
# short alphanumeric names would match inside longer ones.
SERVICE_SCAN_RE = re.compile(
    r"(?<![A-Za-z0-9])(" +
    "|".join(re.escape(s) for s in KNOWN_SERVICES) +
    r")(?![A-Za-z0-9])"
)


def find_unlisted_services(texts, min_mentions=3):
    """Report services the posts discuss that KNOWN_SERVICES does not have.

    This is the part that means the catalogue never has to be maintained on
    speculation. It does not add anything to the widget -- an earlier version
    did, and shipped bubbles labelled "What" and "They", because a capitalised
    word after "AWS" is not evidence of a service. It just tells you, by name
    and with a count, that you have written about something the widget cannot
    show, and leaves the judgement to a human.
    """
    candidates = {}
    for text in texts:
        for m in SERVICE_PREFIX_RE.finditer(text):
            name = m.group(1).strip()
            # Trim trailing filler swept up by the capitalised-word run, so
            # "AWS Lambda Function URLs" reports as Lambda.
            while name and name.split()[-1] in NOT_SERVICES:
                name = " ".join(name.split()[:-1])
            if not name or name in NOT_SERVICES or name in SERVICE_DOMAIN:
                continue
            if len(name.split()) > 3:
                name = " ".join(name.split()[:3])
            # A service is a proper noun; a sentence fragment usually is not.
            if name in SERVICE_DOMAIN or len(name) < 3:
                continue
            candidates[name] = candidates.get(name, 0) + 1
    return sorted(((n, c) for n, c in candidates.items() if c >= min_mentions),
                  key=lambda x: -x[1])


def count_services(text, services=None):
    """Count AWS service mentions in one post.

    Case-sensitive and word-bounded, which on its own removes most of the
    damage: "configuration" no longer feeds Config, and "secret" no longer
    feeds ECR -- that one was matching inside the word and came out at seven
    times its real size.

    One pass with a combined pattern rather than one scan per service, because
    the catalogue is now ~660 names rather than 43.
    """
    counts = {}
    for m in SERVICE_SCAN_RE.finditer(text):
        name = SERVICE_ALIASES.get(m.group(1), m.group(1))
        counts[name] = counts.get(name, 0) + 1

    for name in list(counts):
        if name not in AMBIGUOUS_NAMES:
            continue
        # A name that is also an English word only counts in a post that names
        # the service properly at least once. After that, bare mentions in the
        # same post are the service -- which is how people write: "AWS Config"
        # once, then "Config" throughout.
        explicit = AMBIGUOUS_SERVICES.get(
            name, r"(?:AWS|Amazon)\s+%s" % re.escape(name))
        if not re.search(explicit, text, re.IGNORECASE):
            del counts[name]
    return counts


# ── 50 evergreen AWS quiz questions ───────────────────────────
AWS_QUIZ_BANK = [
    {"q":"Which AWS service provides managed relational database with automated backups and patching?","a":"RDS","opts":["RDS","DynamoDB","Redshift","Aurora"],"e":"Amazon RDS handles routine database tasks like backups, patching, and failover automatically."},
    {"q":"What is the maximum size of a single object in Amazon S3?","a":"5 TB","opts":["5 GB","5 TB","100 GB","1 TB"],"e":"S3 supports objects up to 5 TB. For objects larger than 5 GB, you must use multipart upload."},
    {"q":"Which IAM entity should be used to grant permissions to an EC2 instance to access S3?","a":"IAM Role","opts":["IAM User","IAM Role","IAM Group","Access Key"],"e":"IAM Roles are attached to EC2 instances via instance profiles — no hardcoded credentials needed."},
    {"q":"What does a VPC Internet Gateway do?","a":"Enables communication between VPC and the internet","opts":["Enables communication between VPC and the internet","Connects two VPCs together","Provides private DNS resolution","Encrypts VPC traffic"],"e":"An Internet Gateway allows resources in public subnets to communicate with the internet."},
    {"q":"Which RDS feature provides automatic failover to a standby instance in another AZ?","a":"Multi-AZ","opts":["Multi-AZ","Read Replica","Aurora Global","Cross-Region Backup"],"e":"Multi-AZ maintains a synchronous standby replica and automatically fails over during outages."},
    {"q":"What is the difference between a Security Group and a Network ACL?","a":"Security Groups are stateful; NACLs are stateless","opts":["Security Groups are stateful; NACLs are stateless","Security Groups are stateless; NACLs are stateful","Both are stateful","Both are stateless"],"e":"Security Groups track connection state (return traffic auto-allowed). NACLs evaluate each packet independently."},
    {"q":"Which S3 storage class is most cost-effective for data accessed less than once a year?","a":"S3 Glacier Deep Archive","opts":["S3 Standard-IA","S3 Glacier","S3 Glacier Deep Archive","S3 One Zone-IA"],"e":"Glacier Deep Archive is the lowest cost at ~$0.00099/GB/month for long-term archival."},
    {"q":"What does an IAM explicit Deny do when combined with an Allow on the same resource?","a":"Deny always wins","opts":["Allow wins","Deny always wins","Last evaluated wins","Depends on policy type"],"e":"Explicit Deny always overrides any Allow — this is a fundamental rule of IAM policy evaluation."},
    {"q":"Which EC2 pricing model provides the largest discount for committing to 1 or 3 years?","a":"Reserved Instances","opts":["Spot Instances","Reserved Instances","Savings Plans","On-Demand"],"e":"Reserved Instances offer up to 72% discount vs On-Demand when you commit to 1 or 3 years."},
    {"q":"What is an AWS Availability Zone?","a":"One or more discrete data centers within a Region","opts":["A geographic region","One or more discrete data centers within a Region","A CDN edge location","A VPC subnet"],"e":"Each AZ is physically separate with independent power, cooling, and networking within a Region."},
    {"q":"Which service distributes incoming traffic across multiple EC2 instances?","a":"Elastic Load Balancer","opts":["Auto Scaling","Elastic Load Balancer","Route 53","CloudFront"],"e":"ELB automatically distributes incoming traffic and integrates with Auto Scaling for high availability."},
    {"q":"What is the purpose of a NAT Gateway?","a":"Allow private subnet instances to reach the internet without being reachable from it","opts":["Allow private subnet instances to reach the internet without being reachable from it","Connect two VPCs","Provide internet access to public subnets","Encrypt outbound traffic"],"e":"NAT Gateway enables outbound internet connectivity for private subnets while blocking inbound connections."},
    {"q":"Which AWS service allows you to run containers without managing servers?","a":"AWS Fargate","opts":["AWS Fargate","EC2","ECS on EC2","Elastic Beanstalk"],"e":"Fargate is a serverless compute engine for containers — no EC2 instances to provision or manage."},
    {"q":"What is the default limit for S3 buckets per AWS account?","a":"100","opts":["10","100","500","Unlimited"],"e":"Each AWS account can create up to 100 S3 buckets by default. You can request an increase."},
    {"q":"Which service provides a managed Kubernetes control plane on AWS?","a":"Amazon EKS","opts":["Amazon ECS","Amazon EKS","AWS Fargate","AWS Batch"],"e":"EKS manages the Kubernetes control plane — patching, scaling, and availability are handled by AWS."},
    {"q":"What does S3 versioning protect against?","a":"Accidental deletion and overwrites","opts":["Accidental deletion and overwrites","Unauthorized access","Data corruption at rest","Cross-region latency"],"e":"Versioning keeps all versions of an object so you can recover from accidental deletes or overwrites."},
    {"q":"Which CloudWatch feature triggers automated actions based on metric thresholds?","a":"CloudWatch Alarms","opts":["CloudWatch Alarms","CloudWatch Logs","CloudWatch Events","CloudWatch Metrics"],"e":"Alarms watch metrics and trigger actions like Auto Scaling, SNS notifications, or EC2 actions."},
    {"q":"Which IAM feature requires users to provide two forms of verification?","a":"Multi-Factor Authentication (MFA)","opts":["IAM Roles","Multi-Factor Authentication (MFA)","IAM Policies","Service Control Policies"],"e":"MFA adds a second layer of security requiring a physical or virtual device in addition to a password."},
    {"q":"What is an EC2 AMI?","a":"A template containing the OS and software to launch an instance","opts":["A template containing the OS and software to launch an instance","An instance type specification","A network configuration","A billing model"],"e":"An AMI (Amazon Machine Image) is a pre-configured template used to create EC2 instances."},
    {"q":"Which service provides a fully managed message queue for decoupling microservices?","a":"Amazon SQS","opts":["Amazon SQS","Amazon SNS","Amazon MQ","Amazon Kinesis"],"e":"SQS is a fully managed message queuing service that decouples and scales distributed systems."},
    {"q":"What is the purpose of AWS Organizations?","a":"Centrally manage and govern multiple AWS accounts","opts":["Centrally manage and govern multiple AWS accounts","Deploy applications across regions","Monitor resource usage","Manage IAM users at scale"],"e":"AWS Organizations allows you to consolidate accounts, apply SCPs, and centralize billing."},
    {"q":"Which EC2 instance type is best optimized for memory-intensive workloads like large databases?","a":"R-series","opts":["C-series","R-series","T-series","P-series"],"e":"R-series instances (e.g., r6i) are memory-optimized, ideal for in-memory databases and big data."},
    {"q":"What does AWS Auto Scaling do when CPU utilization exceeds a defined threshold?","a":"Launches additional EC2 instances","opts":["Launches additional EC2 instances","Upgrades the instance type","Migrates to a different region","Sends an email only"],"e":"Auto Scaling adds instances when demand rises and removes them when demand drops to save cost."},
    {"q":"Which S3 feature prevents objects from being deleted or overwritten for a defined period?","a":"S3 Object Lock","opts":["S3 Object Lock","Bucket Policy","S3 Versioning","Server-Side Encryption"],"e":"S3 Object Lock implements WORM (Write Once Read Many) — used for compliance and data retention."},
    {"q":"What is the difference between horizontal and vertical scaling?","a":"Horizontal adds more instances; vertical increases instance size","opts":["Horizontal adds more instances; vertical increases instance size","Horizontal increases instance size; vertical adds more instances","Both mean adding more instances","Both mean increasing instance size"],"e":"Horizontal (scale out) adds instances. Vertical (scale up) upgrades to a larger instance type."},
    {"q":"Which AWS service helps detect unusual activity and potential threats in your account?","a":"Amazon GuardDuty","opts":["Amazon GuardDuty","AWS Inspector","AWS Shield","AWS WAF"],"e":"GuardDuty uses ML to analyze CloudTrail, VPC Flow Logs, and DNS logs to detect threats."},
    {"q":"What is a VPC subnet?","a":"A range of IP addresses within a VPC","opts":["A range of IP addresses within a VPC","A connection between VPCs","A firewall rule set","A route table"],"e":"Subnets partition a VPC's IP address range. Public subnets route to an IGW; private subnets don't."},
    {"q":"Which service provides infrastructure as code with state management and plan/apply workflow?","a":"Terraform","opts":["Terraform","AWS CloudFormation","AWS CDK","Ansible"],"e":"Terraform by HashiCorp uses HCL to define infrastructure, maintains state, and previews changes before applying."},
    {"q":"What is the purpose of an S3 bucket policy?","a":"Grant or deny access to a bucket and its objects","opts":["Grant or deny access to a bucket and its objects","Encrypt objects at rest","Enable versioning","Configure lifecycle rules"],"e":"Bucket policies are resource-based IAM policies that control who can access the bucket and how."},
    {"q":"Which EC2 feature allows you to run scripts automatically when an instance launches?","a":"User Data","opts":["User Data","Instance Metadata","Launch Template","AMI"],"e":"User Data scripts run once at launch — used for bootstrapping, software installation, and configuration."},
    {"q":"What does RDS Read Replica provide?","a":"A read-only copy of the database for offloading read traffic","opts":["A read-only copy of the database for offloading read traffic","Automatic failover","Cross-region backup","Point-in-time recovery"],"e":"Read Replicas serve read traffic from a copy of the primary, reducing load and improving performance."},
    {"q":"Which AWS service stores and retrieves secrets like database passwords and API keys?","a":"AWS Secrets Manager","opts":["AWS Secrets Manager","AWS KMS","Parameter Store","IAM"],"e":"Secrets Manager stores, rotates, and retrieves secrets — with automatic rotation for RDS passwords."},
    {"q":"What is an AWS Service Control Policy (SCP)?","a":"A policy that sets maximum permissions for accounts in AWS Organizations","opts":["A policy that sets maximum permissions for accounts in AWS Organizations","An IAM policy type","A VPC firewall rule","A CloudWatch alarm policy"],"e":"SCPs in AWS Organizations act as guardrails — they cannot grant permissions but can restrict what accounts can do."},
    {"q":"Which service routes end users to the nearest AWS edge location for low latency?","a":"Amazon CloudFront","opts":["Amazon CloudFront","Route 53","Global Accelerator","Transit Gateway"],"e":"CloudFront is a CDN that caches content at 400+ edge locations worldwide for low-latency delivery."},
    {"q":"What is the purpose of a Terraform state file?","a":"Track the real-world state of managed infrastructure","opts":["Track the real-world state of managed infrastructure","Store secrets and variables","Define provider configurations","Record apply history"],"e":"The state file maps Terraform config to real resources — it's how Terraform knows what already exists."},
    {"q":"Which AWS service provides fully managed ETL (extract, transform, load) for data pipelines?","a":"AWS Glue","opts":["AWS Glue","AWS Batch","Amazon EMR","AWS Step Functions"],"e":"Glue provides a serverless ETL service with a data catalog, crawlers, and Spark-based job runs."},
    {"q":"What does the AWS Shared Responsibility Model mean?","a":"AWS secures the cloud infrastructure; customers secure what's in the cloud","opts":["AWS secures the cloud infrastructure; customers secure what's in the cloud","AWS is responsible for all security","Customers are responsible for all security","Security is split 50/50 by cost"],"e":"AWS manages security OF the cloud (hardware, AZs, services). You manage security IN the cloud (data, IAM, configs)."},
    {"q":"Which EC2 purchasing option is cheapest but can be interrupted by AWS?","a":"Spot Instances","opts":["Spot Instances","Reserved Instances","Dedicated Hosts","On-Demand"],"e":"Spot Instances use spare EC2 capacity at up to 90% discount but can be reclaimed with 2 minutes notice."},
    {"q":"What is an EKS Node Group?","a":"A managed group of EC2 instances that serve as Kubernetes worker nodes","opts":["A managed group of EC2 instances that serve as Kubernetes worker nodes","The Kubernetes control plane","A namespace in Kubernetes","A Helm chart collection"],"e":"Node Groups manage the EC2 fleet that runs your pods — AWS handles provisioning, patching, and scaling."},
    {"q":"Which AWS service orchestrates multi-step workflows as serverless state machines?","a":"AWS Step Functions","opts":["AWS Step Functions","Amazon SQS","AWS Lambda","Amazon EventBridge"],"e":"Step Functions coordinates Lambda, ECS, Glue, and other services into visual, auditable workflows."},
    {"q":"What is the purpose of VPC Flow Logs?","a":"Capture information about IP traffic going to and from network interfaces","opts":["Capture information about IP traffic going to and from network interfaces","Monitor application performance","Log API calls to AWS services","Audit IAM policy changes"],"e":"VPC Flow Logs record accept/reject decisions for traffic — essential for network troubleshooting and security."},
    {"q":"Which service provides DNS routing with health checks and failover?","a":"Amazon Route 53","opts":["Amazon Route 53","CloudFront","Global Accelerator","ELB"],"e":"Route 53 is AWS's DNS service with routing policies like failover, weighted, latency, and geolocation."},
    {"q":"What is the maximum execution timeout for an AWS Lambda function?","a":"15 minutes","opts":["5 minutes","15 minutes","1 hour","30 minutes"],"e":"Lambda functions can run for up to 15 minutes (900 seconds). For longer jobs, use ECS or Step Functions."},
    {"q":"Which Terraform command applies changes shown in a plan?","a":"terraform apply","opts":["terraform apply","terraform plan","terraform deploy","terraform push"],"e":"terraform apply executes the changes. It prompts for confirmation unless run with -auto-approve."},
    {"q":"What is the purpose of an AWS Transit Gateway?","a":"Connect multiple VPCs and on-premises networks through a central hub","opts":["Connect multiple VPCs and on-premises networks through a central hub","Replace Internet Gateways","Provide DDoS protection","Manage IAM across accounts"],"e":"Transit Gateway acts as a cloud router — simplifying network topology by replacing complex VPC peering meshes."},
    {"q":"Which S3 storage class automatically moves objects between tiers based on access patterns?","a":"S3 Intelligent-Tiering","opts":["S3 Intelligent-Tiering","S3 Standard","S3 Standard-IA","S3 Glacier"],"e":"Intelligent-Tiering monitors access and moves objects between frequent and infrequent tiers with no retrieval fees."},
    {"q":"What does 'idempotent' mean in the context of Terraform?","a":"Running apply multiple times produces the same result","opts":["Running apply multiple times produces the same result","Resources are created in parallel","State is stored remotely","Plans are always accurate"],"e":"Idempotency means re-running terraform apply on unchanged config makes no changes — safe to run repeatedly."},
    {"q":"Which AWS service provides managed Elastic MapReduce for big data processing?","a":"Amazon EMR","opts":["Amazon EMR","AWS Glue","Amazon Redshift","AWS Batch"],"e":"EMR runs Apache Spark, Hive, Presto, and other frameworks on managed clusters for big data workloads."},
    {"q":"What is CloudWatch Logs Insights?","a":"An interactive query service for analyzing log data","opts":["An interactive query service for analyzing log data","A log streaming service","A metric dashboard","An alerting service"],"e":"Logs Insights lets you run SQL-like queries against CloudWatch log groups to find patterns and errors fast."},
    {"q":"Which AWS service provides automated patch management for EC2 and on-premises servers?","a":"AWS Systems Manager Patch Manager","opts":["AWS Systems Manager Patch Manager","AWS Inspector","AWS Config","EC2 Image Builder"],"e":"SSM Patch Manager automates OS patching with patch baselines, maintenance windows, and compliance reporting."},
    {"q":"What is the purpose of an AWS IAM policy condition?","a":"Add fine-grained controls like IP range, time, or MFA requirement to permissions","opts":["Add fine-grained controls like IP range, time, or MFA requirement to permissions","Define which services a role can access","Set password complexity rules","Control account spending"],"e":"Conditions allow you to restrict when a policy applies — e.g., only allow S3 access from a specific IP range."},
]

FEEDBACK_WIDGET_HTML = """
<button class="fb-btn" id="fb-btn" aria-label="Give feedback" title="Give feedback">&#9733;</button>
<div class="fb-overlay" id="fb-overlay">
  <div class="fb-modal" id="fb-modal">
    <div class="fb-title">How was your experience?</div>
    <div class="fb-sub">Your feedback helps improve this site.</div>
    <div class="fb-stars" id="fb-stars">
      <button class="fb-star" data-v="1" aria-label="1 star">&#9733;</button>
      <button class="fb-star" data-v="2" aria-label="2 stars">&#9733;</button>
      <button class="fb-star" data-v="3" aria-label="3 stars">&#9733;</button>
      <button class="fb-star" data-v="4" aria-label="4 stars">&#9733;</button>
      <button class="fb-star" data-v="5" aria-label="5 stars">&#9733;</button>
    </div>
    <div class="fb-labels"><span>Poor</span><span>Excellent</span></div>
    <textarea class="fb-textarea" id="fb-text" placeholder="Any thoughts? (optional)"></textarea>
    <div class="fb-footer">
      <button class="fb-skip" id="fb-skip">Skip</button>
      <button class="fb-send" id="fb-send">Send feedback</button>
    </div>
  </div>
</div>
<script>
(function(){
  var FORM_ID='xzdqqvqd';
  var rating=0;
  var btn=document.getElementById('fb-btn'),overlay=document.getElementById('fb-overlay');
  var stars=document.querySelectorAll('.fb-star');
  btn.addEventListener('click',function(){overlay.classList.add('open');});
  overlay.addEventListener('click',function(e){if(e.target===overlay)overlay.classList.remove('open');});
  document.getElementById('fb-skip').addEventListener('click',function(){overlay.classList.remove('open');});
  stars.forEach(function(s){
    s.addEventListener('click',function(){
      rating=parseInt(s.getAttribute('data-v'));
      stars.forEach(function(x){x.classList.toggle('on',parseInt(x.getAttribute('data-v'))<=rating);});
    });
  });
  document.getElementById('fb-send').addEventListener('click',function(){
    var msg=document.getElementById('fb-text').value;
    fetch('https://formspree.io/f/'+FORM_ID,{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({rating:rating,message:msg,page:window.location.pathname})
    });
    document.getElementById('fb-modal').innerHTML='<div class="fb-thanks"><span>&#10003;</span><strong>Thanks for your feedback!</strong><p style="color:#879196;font-size:13px;margin-top:0.35rem;">It means a lot.</p></div>';
    setTimeout(function(){overlay.classList.remove('open');},2000);
  });
})();
</script>"""

ASK_WIDGET_HTML = f"""
<button class="ask-launcher" id="ask-launcher" aria-label="Ask about me" title="Ask about me">
  <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor" stroke="none">
    <path d="M12 2l1.6 4.8L18.4 8.4l-4.8 1.6L12 14.8l-1.6-4.8L5.6 8.4l4.8-1.6L12 2z"/>
    <path d="M19.5 14l.9 2.6 2.6.9-2.6.9-.9 2.6-.9-2.6-2.6-.9 2.6-.9.9-2.6z" opacity=".55"/>
    <path d="M5 17.5l.6 1.9 1.9.6-1.9.6L5 22.5l-.6-1.9-1.9-.6 1.9-.6L5 17.5z" opacity=".35"/>
  </svg>
</button>
<div class="ask-overlay" id="ask-overlay" role="dialog" aria-modal="true" aria-label="Ask about me">
  <div class="ask-terminal">
    <div class="ask-titlebar">
      <span class="ask-dot ask-dot-red"></span>
      <span class="ask-dot ask-dot-yellow"></span>
      <span class="ask-dot ask-dot-green"></span>
      <span class="ask-titlebar-label">ask-jay — about me</span>
      <button class="ask-close" id="ask-close" aria-label="Close">✕</button>
    </div>
    <div class="ask-body">
      <form id="ask-form">
        <div class="ask-prompt-row">
          <span class="ask-prompt-label">jay@me :~$</span>
          <textarea class="ask-input" id="ask-input" rows="1" placeholder='ask "your question here"' autocomplete="off"></textarea>
        </div>
        <div class="ask-send-row">
          <button class="ask-send-btn" id="ask-send" type="submit">Run ↵</button>
        </div>
      </form>
    </div>
    <div class="ask-output" id="ask-output"></div>
  </div>
</div>
<script>
(function(){{
  var API_URL = '{API_URL}';
  var launcher=document.getElementById('ask-launcher'),overlay=document.getElementById('ask-overlay'),
      closeBtn=document.getElementById('ask-close'),form=document.getElementById('ask-form'),
      input=document.getElementById('ask-input'),sendBtn=document.getElementById('ask-send'),
      output=document.getElementById('ask-output');
  function openModal(){{overlay.classList.add('open');document.body.style.overflow='hidden';setTimeout(function(){{input.focus();}},220);}}
  function closeModal(){{overlay.classList.remove('open');document.body.style.overflow='';}}
  launcher.addEventListener('click',openModal);
  closeBtn.addEventListener('click',closeModal);
  overlay.addEventListener('click',function(e){{if(e.target===overlay)closeModal();}});
  document.addEventListener('keydown',function(e){{if(e.key==='Escape')closeModal();}});
  input.addEventListener('input',function(){{this.style.height='auto';this.style.height=this.scrollHeight+'px';}});
  input.addEventListener('keydown',function(e){{if(e.key==='Enter'&&!e.shiftKey){{e.preventDefault();form.dispatchEvent(new Event('submit'));}}}});
  form.addEventListener('submit',function(e){{
    e.preventDefault();var q=input.value.trim();if(!q)return;
    sendBtn.disabled=true;output.className='ask-output visible';
    output.innerHTML='<p class="ask-spinner">▌ thinking…</p>';
    fetch(API_URL,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{question:q}})}})
      .then(function(r){{if(!r.ok)throw new Error('HTTP '+r.status);return r.json();}})
      .then(function(data){{
        var answer=esc(data.answer).replace(/`([^`]+)`/g,'<code>$1</code>');
        var src='';
        if(data.sources&&data.sources.length){{
          src='<div class="ask-sources-label">Sources</div><div class="ask-sources">'+
            data.sources.map(function(s){{return '<a href="'+esc(s.url)+'" target="_blank" rel="noopener">'+esc(s.title)+'</a>';}}).join('')+'</div>';
        }}
        output.innerHTML='<div class="ask-output-label">Answer</div><div class="ask-answer">'+answer+'</div>'+src;
      }})
      .catch(function(){{output.innerHTML='<p class="ask-error">Error — check your connection and try again.</p>';}})
      .finally(function(){{sendBtn.disabled=false;}});
  }});
  function esc(str){{return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}}
}})();
</script>"""

# "At a glance" widget (rebuilt 2026-07-24 as LLM-generated + client-side
# fetched, replacing the old build-time keyword-extraction version removed
# earlier the same day). Generation happens once per post in the
# blog-search-indexer Lambda (Claude Haiku, cached by content hash — see
# blog-search/indexer/handler.py); this script only fetches and renders the
# already-generated result, same "static page, one opt-in API call" shape as
# ASK_WIDGET_HTML. A post with no cached summary yet (brand new, indexer
# hasn't run since) just renders nothing — the mount stays empty, no error
# shown, no broken box. Topics come from this page's own tags (server-side,
# no API round trip needed for those).
SUMMARY_WIDGET_JS = f"""<script>
(function(){{
  var SUMMARY_API_URL = '{SUMMARY_API_URL}';
  var mount = document.querySelector('.quick-summary-mount');
  if (!mount) return;
  var slug = mount.getAttribute('data-slug');
  if (!slug) return;

  fetch(SUMMARY_API_URL + '?slug=' + encodeURIComponent(slug))
    .then(function(r){{ if(!r.ok) throw new Error('no summary'); return r.json(); }})
    .then(function(data){{
      var rows = [
        ['Overview', data.overview],
        ['Key detail', data.key_detail],
        ['Takeaway', data.takeaway]
      ].filter(function(r){{ return r[1]; }});
      if (!rows.length) return;
      var rowsHtml = rows.map(function(r){{
        return '<div class="qs-row"><span class="qs-row-label">'+esc(r[0])+'</span><p class="qs-row-text">'+esc(r[1])+'</p></div>';
      }}).join('');
      var topicsHtml = (mount.getAttribute('data-topics')||'').split(',').filter(Boolean).map(function(t){{
        return '<span class="quick-summary-topic">'+esc(t)+'</span>';
      }}).join('');
      mount.outerHTML =
        '<details class="quick-summary" open>' +
        '<summary><span class="quick-summary-icon" aria-hidden="true">&#10022;</span>' +
        '<span class="quick-summary-heading"><strong>At a glance</strong><small>What this post covers</small></span>' +
        '<span class="quick-summary-toggle" aria-hidden="true"></span></summary>' +
        '<div class="quick-summary-content"><div class="qs-rows">'+rowsHtml+'</div>' +
        '<div class="quick-summary-topics">'+topicsHtml+'</div></div>' +
        '</details>';
    }})
    .catch(function(){{ /* no cached summary yet — leave the mount empty, no visible error */ }});

  function esc(str){{return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}}
}})();
</script>"""

# ── ChatGPT CodeMirror markers ────────────────────────────────
CHATGPT_MARKERS = [
    "q9tKkq_viewer", "cm-editor", "lxnfua_", "cm-scroller",
    "cm-content", "q9tKkq_readonly", "border-token-border-light",
    "ͼd", "ͼr", "ͼm", "ͼg",
]

# ── Tag detection ─────────────────────────────────────────────
# 4, not 3: a post can legitimately belong to a series and still carry three
# real topic tags (e.g. 30 Days of AWS Terraform + AWS + Terraform + Kubernetes).
# At 3 the series label evicted the most specific tag, and the Kubernetes pill
# disappeared entirely because its only three posts were all in the series.
MAX_TAGS = 4
CATEGORY_ORDER = ["All", "AWS Architecture Series", "Azure Architecture Series", "GCP Architecture Series", "AWS Weekly Lab", "AWS Daily Intelligence", "AWS Weekly Intelligence", "30 Days of AWS Terraform", "AWS", "Azure", "GCP", "Terraform", "Databases & Ops", "Kubernetes", "GitOps", "AI", "Tech", "Career", "Health", "Life"]

NAV_SVG = """<svg width="30" height="30" viewBox="0 0 80 80" xmlns="http://www.w3.org/2000/svg">
  <rect width="80" height="80" rx="16" fill="#11140F"/>
  <text x="36" y="52" font-family="monospace" font-size="36" font-weight="700" fill="#C4A484" text-anchor="middle">J</text>
  <polygon points="54,12 46,28 52,28 44,44" fill="#C4A484" opacity="0.9"/>
</svg>"""

# ── Unified #jk-post theme ──────────────────────────────────────
# Canonical theme (matches the Week 4 design). Every post that embeds its own
# <style>#jk-post{...}</style> block gets this swapped in at sync time, so all
# themed posts look consistent regardless of which markup version they were
# originally written with. Includes compatibility rules for older class names
# (stat-box, warning-box, bug-card, before-after, etc.) used by Week 1-3 and
# the RAG-search post, restyled to match this design instead of their own.
JK_POST_THEME_CSS = """
#jk-post {
  font-family: 'Amazon Ember', 'Segoe UI', Arial, sans-serif;
  font-size: 15px;
  line-height: 1.8;
  color: #0f1111;
  max-width: 860px;
  margin: 0 auto;
  background: transparent;
}
#jk-post * { box-sizing: border-box; }

/* ── Post header ── */
#jk-post .post-header { border-bottom: 3px solid #C4A484; padding-bottom: 24px; margin-bottom: 36px; }
#jk-post .post-eyebrow { font-size: 12px; color: #6c757d; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 12px; }
#jk-post .post-title { font-size: 28px; font-weight: 700; color: #0f1111; line-height: 1.25; margin-bottom: 12px; }
#jk-post .post-subtitle { font-size: 16px; color: #3d3d3d; line-height: 1.6; margin-bottom: 14px; }
#jk-post .post-meta { display: flex; flex-wrap: wrap; gap: 20px; font-size: 13px; color: #6c757d; border-top: 1px solid #e5e5e5; padding-top: 12px; margin-top: 12px; }
#jk-post .post-meta span::before { content: "· "; }
#jk-post .post-meta span:first-child::before { content: ""; }

/* ── Layout ── */
#jk-post .container { padding: 0; }
#jk-post .section { padding: 36px 0; border-bottom: 1px solid #e5e5e5; }
#jk-post .section:last-child { border-bottom: none; }
#jk-post h2 { font-size: 22px; font-weight: 700; color: #0f1111; margin: 0 0 20px 0; padding-bottom: 10px; border-bottom: 2px solid #C4A484; display: inline-block; }
#jk-post h3 { font-size: 17px; font-weight: 700; color: #0f1111; margin: 28px 0 10px; }
#jk-post h4 { font-size: 14px; font-weight: 700; color: #0f1111; margin: 16px 0 6px; }
#jk-post p  { color: #3d3d3d; margin-bottom: 14px; }
#jk-post ul, #jk-post ol { margin: 0 0 14px 24px; color: #3d3d3d; }
#jk-post li { margin-bottom: 6px; }

/* ── TOC ── */
#jk-post .toc { background: #fafafa; border: 1px solid #e5e5e5; border-left: 3px solid #C4A484; border-radius: 4px; padding: 20px 24px; margin: 28px 0; }
#jk-post .toc h3 { margin: 0 0 12px 0; font-size: 14px; color: #0f1111; }
#jk-post .toc ol { margin: 0; padding-left: 20px; }
#jk-post .toc li { font-size: 14px; margin-bottom: 4px; }
#jk-post .toc a { color: #0066c0; text-decoration: none; }
#jk-post .toc a:hover { text-decoration: underline; }

/* ── Callouts ── */
#jk-post .callout { border-left: 3px solid #C4A484; background: #fffbf5; border-radius: 0 4px 4px 0; padding: 16px 20px; margin: 20px 0; }
#jk-post .callout.amber { border-color: #d97706; background: #fffbeb; }
#jk-post .callout.green { border-color: #1d8102; background: #f4fbf4; }
#jk-post .callout.red   { border-color: #cc0c39; background: #fff5f5; }
#jk-post .callout strong { font-size: 14px; display: block; margin-bottom: 6px; color: #0f1111; }
#jk-post .callout p { margin: 0; font-size: 14px; color: #3d3d3d; }

/* ── Flow steps ── */
#jk-post .flow { display: flex; flex-direction: column; gap: 0; margin: 24px 0; }
#jk-post .flow-step { display: flex; gap: 16px; align-items: flex-start; padding: 14px 0; }
#jk-post .flow-icon { width: 36px; height: 36px; border-radius: 50%; flex-shrink: 0; background: #C4A484; color: #fff; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 13px; }
#jk-post .flow-content h4 { font-size: 14px; font-weight: 700; margin: 8px 0 4px; }
#jk-post .flow-content p  { font-size: 14px; color: #3d3d3d; margin: 0; }

/* ── Code blocks ── */
#jk-post .code-block { background: #1e293b; border-radius: 4px; overflow: hidden; margin: 16px 0; border: 1px solid #2d3748; }
#jk-post .code-header { background: #0f172a; padding: 8px 14px; display: flex; align-items: center; justify-content: space-between; }
#jk-post .code-lang { font-size: 11px; font-weight: 700; color: #60a5fa; text-transform: uppercase; letter-spacing: 1px; }
#jk-post .code-dots { display: flex; gap: 5px; }
#jk-post .code-dot  { width: 9px; height: 9px; border-radius: 50%; }
#jk-post .code-dot:nth-child(1) { background: #ef4444; }
#jk-post .code-dot:nth-child(2) { background: #f59e0b; }
#jk-post .code-dot:nth-child(3) { background: #10b981; }
#jk-post pre { padding: 18px 20px; overflow-x: auto; font-family: 'Courier New', Consolas, monospace; font-size: 13px; line-height: 1.65; color: #e2e8f0; white-space: pre; margin: 0; }
#jk-post code.inline { background: #f5f5f5; color: #0f1111; padding: 2px 6px; border-radius: 3px; font-family: 'Courier New', Consolas, monospace; font-size: 13px; border: 1px solid #e5e5e5; }

/* ── Skill tags ── */
#jk-post .tag-grid { display: flex; flex-wrap: wrap; gap: 8px; margin: 16px 0; }
#jk-post .tag { display: flex; align-items: center; gap: 6px; background: #fafafa; border: 1px solid #e5e5e5; border-radius: 4px; padding: 6px 12px; font-size: 13px; color: #3d3d3d; }

/* ── Grid cards ── */
#jk-post .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin: 20px 0; }
#jk-post .card { border: 1px solid #e5e5e5; border-radius: 4px; padding: 18px; background: #fafafa; }
#jk-post .card h4 { margin-top: 0; }
#jk-post .card p  { font-size: 13px; margin-bottom: 0; }

/* ── Challenge cards ── */
#jk-post .challenge-card { border: 1px solid #e5e5e5; border-radius: 4px; margin: 16px 0; overflow: hidden; }
#jk-post .challenge-header { background: #fafafa; border-bottom: 1px solid #e5e5e5; padding: 12px 16px; display: flex; align-items: center; gap: 10px; }
#jk-post .challenge-header .num { background: #cc0c39; color: #fff; width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 700; flex-shrink: 0; min-width: 24px; }
#jk-post .challenge-header strong { color: #0f1111; font-size: 14px; }
#jk-post .challenge-body { padding: 14px 16px; }
#jk-post .challenge-body p { font-size: 14px; margin-bottom: 8px; }
#jk-post .fix-label { font-size: 11px; font-weight: 700; letter-spacing: 0.8px; text-transform: uppercase; color: #1d8102; margin-bottom: 6px; display: block; }

/* ── Screenshots ── */
#jk-post figure.screenshot { margin: 24px 0; border-radius: 4px; overflow: hidden; border: 1px solid #e5e5e5; }
#jk-post figure.screenshot img { width: 100%; display: block; }
#jk-post figure.screenshot figcaption { background: #fafafa; border-top: 1px solid #e5e5e5; padding: 8px 14px; font-size: 13px; color: #6c757d; font-style: italic; }

/* ── Tables ── */
/* clean_html() strips every inline style attribute, so the overflow-x:auto
   wrapper documented in CLAUDE.md silently becomes a bare div on any
   sync-built post, and wide tables clip on mobile with no way to scroll.
   Wrap wide tables in the table-scroll class instead: class attributes
   survive cleaning, inline styles do not. (Arch posts are unaffected —
   they bypass clean_html entirely, so inline styles still work there.) */
/* Weekly Intelligence inventory: AWS's own one-line summary under each linked
   announcement. A class rather than an inline style because clean_html()
   strips style attributes. Generated by scripts/build_weekly_inventory.py. */
#jk-post .inv-gist { display: block; color: #6c757d; font-size: 13px; line-height: 1.5; margin-top: 2px; }
#jk-post .table-scroll { overflow-x: auto; margin: 16px 0; }
#jk-post .table-scroll table { margin: 0; }
#jk-post table { width: 100%; border-collapse: collapse; margin: 16px 0; }
#jk-post th { background: #fafafa; text-align: left; padding: 10px 14px; font-size: 13px; font-weight: 700; border-bottom: 2px solid #e5e5e5; color: #0f1111; }
#jk-post td { padding: 10px 14px; font-size: 13px; border-bottom: 1px solid #e5e5e5; color: #3d3d3d; }
#jk-post tr:last-child td { border-bottom: none; }
#jk-post tr:nth-child(even) td { background: #fafafa; }

/* ── Footer ── */
#jk-post .post-footer { background: #fafafa; border-top: 2px solid #C4A484; border-radius: 0 0 4px 4px; padding: 24px; text-align: center; font-size: 13px; color: #6c757d; margin-top: 36px; }
#jk-post .post-footer p { color: #6c757d; margin-bottom: 0; }
#jk-post .post-footer p + p { margin-top: 6px; }

/* ── Compatibility: older post markup (Week 1-3, RAG-search post) ── */
#jk-post .meta { color: #6c757d; font-size: 0.9em; margin-bottom: 24px; }
#jk-post .meta span { background: #fafafa; border: 1px solid #e5e5e5; padding: 4px 12px; border-radius: 20px; margin-right: 6px; display: inline-block; margin-bottom: 6px; font-size: .85em; }
#jk-post .stack-badge { background: #C4A484; color: #0f1111; padding: 10px 18px; border-radius: 4px; font-size: 0.85em; font-weight: 700; display: inline-block; margin-bottom: 20px; }
#jk-post .stat-row { display: flex; flex-wrap: wrap; gap: 12px; margin: 20px 0; }
#jk-post .stat-box { background: #fafafa; border: 1px solid #e5e5e5; border-radius: 4px; padding: 14px 18px; text-align: center; min-width: 120px; flex: 1; }
#jk-post .stat-val { font-size: 1.6em; font-weight: 700; color: #C4A484; display: block; line-height: 1; }
#jk-post .stat-lbl { font-size: 0.78em; color: #6c757d; margin-top: 4px; display: block; }
#jk-post .warning-box { background: #fffbeb; border: 1px solid #fde68a; border-radius: 4px; padding: 14px 20px; margin: 18px 0; color: #0f1111; }
#jk-post .warning-box strong { color: #d97706; }
#jk-post .tip-box { background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 4px; padding: 14px 20px; margin: 18px 0; color: #0f1111; }
#jk-post .tip-box strong { color: #1d4ed8; }
#jk-post .bug-card { border: 1px solid #e5e5e5; border-radius: 4px; margin: 16px 0; overflow: hidden; }
#jk-post .bug-label { background: #fafafa; border-bottom: 1px solid #e5e5e5; padding: 10px 16px; display: block; font-size: 11px; font-weight: 700; letter-spacing: .8px; text-transform: uppercase; color: #cc0c39; }
#jk-post .bug-title { padding: 12px 16px 0; font-size: 14px; font-weight: 700; color: #0f1111; }
#jk-post .section-divider, #jk-post .separator { border: none; border-top: 2px solid #e5e5e5; margin: 32px 0; }
#jk-post .arch-container { margin: 20px 0; border: 1px solid #e5e5e5; border-radius: 4px; overflow: hidden; }
#jk-post .before-after { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin: 20px 0; }
#jk-post .before-card, #jk-post .after-card { border: 1px solid #e5e5e5; border-radius: 4px; padding: 16px; background: #fafafa; }
#jk-post .ba-label { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .6px; color: #6c757d; margin-bottom: 8px; display: block; }
#jk-post .ba-item { font-size: 14px; color: #3d3d3d; margin-bottom: 6px; }
"""



# ── Local posts (written directly in this repo, no Blogger) ────
MD_EXTENSIONS = ["fenced_code", "tables", "sane_lists", "nl2br"]


def _parse_front_matter(raw):
    if raw.startswith("---"):
        _, fm_text, body = raw.split("---", 2)
        # The "---\n" delimiter's trailing newline ends up attached to the
        # body half of the split — strip it so HTML-source posts come out
        # byte-identical to their pre-migration content (a leading blank
        # line is otherwise harmless, but makes every diff noisy).
        return yaml.safe_load(fm_text) or {}, body.lstrip("\n")
    return {}, raw


def fetch_local_posts():
    """Posts written directly in this repo, no Blogger involved.
    Two source formats in posts/, both with YAML front matter (title and
    date required; labels and slug optional — slug defaults to
    slugify(title); draft optional, defaults to false — see the draft-mode
    note above main() for what setting it does):
      - posts/*.md   — Markdown body, converted to HTML here.
      - posts/*.html — body is already HTML (e.g. content migrated from
        Blogger) and is used as-is, with no Markdown conversion.
    Either way, the body is run through the exact same clean_html()
    pipeline as posts used to go through from Blogger, so the canonical
    theme, image handling, and lightbox all apply identically — write new
    posts using the same component classes (.callout, .flow,
    figure.screenshot, etc.) documented in [[project-blog-sync-arch]].
    """
    posts = []
    if not POSTS_DIR.exists():
        return posts
    files = sorted(POSTS_DIR.glob("*.md")) + sorted(POSTS_DIR.glob("*.html"))
    for post_file in files:
        raw = post_file.read_text(encoding="utf-8")
        front_matter, body = _parse_front_matter(raw)
        title = front_matter.get("title")
        date = front_matter.get("date")
        if not title or not date:
            print(f"  Skipping {post_file.name}: missing required 'title' or 'date' front matter")
            continue
        body_html = body if post_file.suffix == ".html" else markdown.markdown(body, extensions=MD_EXTENSIONS)
        published = date.isoformat() if hasattr(date, "isoformat") else str(date)
        posts.append({
            "title": title,
            "url": "",
            "html": body_html,
            "published": published,
            "labels": front_matter.get("labels", []),
            "slug": front_matter.get("slug"),
            "summary": front_matter.get("summary"),
            "takeaway": front_matter.get("takeaway"),
            "problem": front_matter.get("problem"),
            "builds": front_matter.get("builds"),
            "catch": front_matter.get("catch"),
            "draft": bool(front_matter.get("draft", False)),
            # Opt-in accuracy badge. See verification_html() for why this is
            # deliberately NOT auto-stamped on every post.
            "verified": front_matter.get("verified"),
            # Architecture Series posts (arch-NNN-*.html) are built outside this
            # script, from _templates/arch-post-template.html by simple
            # placeholder substitution, not this script's
            # clean_html()/generate_summary()/excerpt(). Reprocessing them here
            # produces genuinely different card text/excerpts than what's live
            # (confirmed live 2026-07-30) -- so main() must treat them as
            # read-only pass-through: never rewrite their individual page, never
            # recompute their display metadata, just reuse whatever's already
            # committed in blog/posts.json for their card.
            #
            # The Azure Architecture Series (az-NNN-*.html) is built the same
            # way, from the same template, and is read-only here for the same
            # reason. Adding a prefix to this tuple is what makes a series
            # custom-built; anything absent from it is regenerated on every sync.
            "externally_built": post_file.name.startswith(("arch-", "az-", "gcp-")),
        })
    return posts


# ── Clean HTML ────────────────────────────────────────────────
def has_chatgpt_junk(html):
    return any(m in html for m in CHATGPT_MARKERS)


def extract_code_text(pre_soup):
    code_el = pre_soup.find("pre", class_="cm-content") or pre_soup.find("code")
    if not code_el:
        return None
    for br in code_el.find_all("br"):
        br.replace_with("\n")
    for span in code_el.find_all("span"):
        span.unwrap()
    return code_el.get_text()


def clean_html(html, title=None):
    soup = BeautifulSoup(html, "html.parser")
    # Standardize the #jk-post theme to the current canonical version, so all
    # posts look consistent. Posts without a #jk-post wrapper get one added
    # around their existing content — this brings the canonical theme's base
    # typography (headings, links, code, tables) to older plain posts too,
    # without altering any of their actual content or structure.
    jk_post_div = soup.find(id="jk-post")
    if jk_post_div is None:
        jk_post_div = soup.new_tag("div", id="jk-post")
        for child in list(soup.contents):
            jk_post_div.append(child.extract())
        soup.append(jk_post_div)
    for style_tag in soup.find_all("style"):
        if "#jk-post" in style_tag.get_text():
            style_tag.string = JK_POST_THEME_CSS
            break
    else:
        new_style = soup.new_tag("style")
        new_style.string = JK_POST_THEME_CSS
        jk_post_div.insert_before(new_style)
    # Posts with a hero block (.post-header/.meta/.stack-badge) sometimes have
    # their own embedded title/subtitle, written as a catchier headline than
    # the metadata title. Pull it out and use it as THE displayed title
    # (consistently, in the standard header position for every post), and
    # strip it from the body so it doesn't also show there.
    embedded_title = None
    embedded_subtitle = None
    has_hero_marker = (
        jk_post_div.find(class_="post-header")
        or jk_post_div.find(class_="meta")
        or jk_post_div.find(class_="stack-badge")
    )
    if title and has_hero_marker:
        title_el = jk_post_div.find("h1") or jk_post_div.find(class_="post-title")
        if title_el and title_el.get_text(strip=True):
            embedded_title = title_el.get_text(strip=True)
            subtitle_el = jk_post_div.find(class_="post-subtitle")
            if subtitle_el:
                embedded_subtitle = subtitle_el.get_text(strip=True)
                subtitle_el.decompose()
            title_el.decompose()
    # Strip any embedded self-link footer (e.g. "Week 05 of 52 ·
    # blog.jayanthkatta.com · github.com/katta698") — redundant with the
    # "Originally on Blogger" link the site already shows, and not present
    # on any other post, so removing it keeps every post consistent.
    footer_el = jk_post_div.find(class_="post-footer")
    if footer_el and (footer_el.find("a", href=re.compile(r"blog\.jayanthkatta\.com|github\.com/katta698"))):
        footer_el.decompose()
    # Strip empty <p> tags and stray top-level <br> left over from Blogger
    # copy-paste — they carry no content, just unwanted vertical whitespace.
    for p in soup.find_all("p"):
        if not p.get_text(strip=True) and not p.find(["img", "iframe"]):
            p.decompose()
    for bq in soup.find_all("blockquote"):
        has_media = bq.find(["img", "iframe"])
        if not bq.get_text(strip=True) and not has_media:
            bq.decompose()
        elif has_media and not bq.get_text(strip=True):
            # Blogger wraps centered images in <blockquote> purely for layout —
            # unwrap so they don't inherit quote styling (cream bg, orange border).
            bq.unwrap()
    for br in jk_post_div.find_all("br", recursive=False):
        br.decompose()
    for pre in soup.find_all("pre"):
        try:
            pre_str = pre.decode()
        except Exception:
            pre_str = ""
        if has_chatgpt_junk(pre_str):
            code_text = extract_code_text(pre)
            if code_text and code_text.strip():
                new_pre = soup.new_tag("pre")
                new_code = soup.new_tag("code")
                new_code.string = code_text.strip()
                new_pre.append(new_code)
                pre.replace_with(new_pre)
            else:
                pre.decompose()
    for pre in soup.find_all("pre"):
        if not pre.get_text(strip=True):
            pre.decompose()
    for h2 in soup.find_all("h2"):
        style = h2.get("style", "")
        spans = h2.find_all("span", style=True)
        if "font-weight: 400" in style or any("font-weight: 400" in s.get("style", "") for s in spans):
            new_p = soup.new_tag("p")
            new_p.string = h2.get_text(strip=True)
            h2.replace_with(new_p)
    for tag in soup.find_all(True):
        if tag.get("style"):
            del tag["style"]
        if tag.get("color"):
            del tag["color"]
        if tag.get("bgcolor"):
            del tag["bgcolor"]
        if tag.name == "font":
            tag.unwrap()
    for code in soup.find_all("code"):
        for span in code.find_all("span"):
            span.unwrap()
        for br in code.find_all("br"):
            br.replace_with("\n")
    # Older posts pasted directly into Blogger auto-wrap images in a link to
    # the full-size original — that just navigates away to a bare image
    # file, which isn't the experience we want. Strip those links so every
    # screenshot behaves the same: blog.js's lightbox (triggered by the
    # magnifier button it injects) is the only way to view a screenshot
    # full-size, consistently across every post.
    #
    # Blogger's <img src> carries a resize marker the <a href> doesn't have —
    # either a "=w640-h156" query-style suffix, or a "/s600/" path segment
    # (older posts) — so comparing the raw strings never matches. Strip
    # both forms from each side before comparing.
    def _strip_blogger_size(url):
        if not url or "googleusercontent.com" not in url:
            return url
        url = re.sub(r"/s\d+/", "/", url)
        url = re.sub(r"=[a-zA-Z]\d+(-[a-zA-Z]\d+)?$", "", url)
        return url

    for img in jk_post_div.find_all("img"):
        parent_link = img.find_parent("a")
        if parent_link is not None and parent_link.get("href") and (
            _strip_blogger_size(parent_link.get("href")) == _strip_blogger_size(img.get("src"))
        ):
            parent_link.unwrap()
    # Blogger's inline <img src> defaults to a small resize (often 600px
    # wide) — fine for its own editor, but blurry once stretched across the
    # post's ~700px-wide column on a retina display. Bump every Blogger
    # image to its "s1600" size so the inline screenshot itself is sharp,
    # not just the lightbox's full-res view.
    def _upsize_blogger_src(url, size=1600):
        if not url or "googleusercontent.com" not in url:
            return url
        url = re.sub(r"/s\d+/", f"/s{size}/", url)
        url = re.sub(r"=[a-zA-Z]\d+(-[a-zA-Z]\d+)?$", f"=s{size}", url)
        return url

    for img in jk_post_div.find_all("img"):
        if img.get("src"):
            img["src"] = _upsize_blogger_src(img["src"])
    return str(soup), embedded_title, embedded_subtitle


# ── Post metadata helpers ─────────────────────────────────────
KNOWN_CATEGORIES = [c for c in CATEGORY_ORDER if c != "All"]


def detect_tags(text, labels=None):
    # Use Jayanth's actual Blogger labels only — far more reliable than
    # guessing from content. Only keep ones matching the site's fixed filter
    # taxonomy (posts have many generic labels like "Technology"/"DevOps"
    # that don't have a filter pill). No keyword-based fallback — content
    # guessing repeatedly produced false positives (e.g. "rag" matching
    # inside "storage", "eks" matching inside "weeks", "beautiful" matching
    # inside "beautifully"). If a post's labels don't match anything known,
    # it defaults to "Tech" — add a real, accurate label in Blogger for any
    # post that deserves better than that.
    if labels:
        matched = [c for c in KNOWN_CATEGORIES if c.lower() in {l.lower() for l in labels}]
        if matched:
            return matched[:MAX_TAGS]
    return ["Tech"]


def soup_text(html):
    """get_text() for a chunk of HTML, parsed once per unique string.

    Profiling sync showed 575 BeautifulSoup parses for 94 posts -- about six
    per post -- and 21 of the run's 34 seconds inside the HTML parser. Most of
    those were the same body being re-parsed by reading_time, tag detection,
    service counting and the domain classifier, each just to read its text.

    Only safe because every caller here reads the text and nothing else. The
    parses that mutate their soup (clean_html strips attributes,
    _summary_sentences decomposes tags) keep their own, because a shared
    mutable soup would let one caller's edits leak into another's output.
    """
    cached = _TEXT_CACHE.get(html)
    if cached is None:
        cached = BeautifulSoup(html, "html.parser").get_text()
        _TEXT_CACHE[html] = cached
    return cached


_TEXT_CACHE = {}


def reading_time(html):
    return max(1, math.ceil(len(soup_text(html).split()) / 200))


def excerpt(html, max_chars=160):
    soup = BeautifulSoup(html, "html.parser")
    for p in soup.find_all("p"):
        txt = p.get_text(strip=True)
        if len(txt) > 30:
            return txt[:max_chars].rstrip() + ("…" if len(txt) > max_chars else "")
    text = soup.get_text(" ", strip=True)
    return text[:max_chars].rstrip() + "…"


SUMMARY_STOP_WORDS = {
    "about", "after", "again", "also", "and", "are", "because", "been",
    "before", "being", "between", "both", "but", "can", "could", "does",
    "each", "from", "have", "into", "just", "more", "most", "not", "only",
    "other", "our", "over", "same", "should", "some", "such", "than", "that",
    "the", "their", "then", "there", "these", "they", "this", "those", "through",
    "under", "using", "very", "was", "were", "what", "when", "where", "which",
    "while", "will", "with", "would", "you", "your",
}


def _summary_sentences(body_html):
    """Return readable prose sentences while ignoring code and page furniture."""
    soup = BeautifulSoup(body_html, "html.parser")
    for tag in soup.find_all(["style", "script", "pre", "code", "nav", "table"]):
        tag.decompose()

    candidates = []
    seen = set()
    for element in soup.find_all(["p", "li"]):
        text = re.sub(r"\s+", " ", element.get_text(" ", strip=True)).strip()
        if not text:
            continue
        for sentence in re.split(r"(?<=[.!?])\s+", text):
            sentence = sentence.strip(" -•\t")
            words = sentence.split()
            if not 7 <= len(words) <= 44 or not 45 <= len(sentence) <= 300:
                continue
            if sentence.endswith(":") or sentence.endswith("?"):
                continue
            if "http://" in sentence or "https://" in sentence:
                continue
            key = re.sub(r"\W+", "", sentence).lower()
            if key in seen:
                continue
            seen.add(key)
            candidates.append(sentence)
    return candidates


def generate_summary(title, body_html, custom_summary=None, custom_takeaway=None):
    """Create a stable extractive summary, with optional front-matter overrides."""
    if custom_summary:
        if isinstance(custom_summary, str):
            bullets = [s.strip() for s in re.split(r"(?<=[.!?])\s+", custom_summary) if s.strip()]
        else:
            bullets = [str(s).strip() for s in custom_summary if str(s).strip()]
        bullets = bullets[:3]
    else:
        sentences = _summary_sentences(body_html)
        if not sentences:
            fallback = excerpt(body_html, 240).rstrip("…")
            return [fallback], custom_takeaway or fallback

        title_terms = {
            w for w in re.findall(r"[a-z][a-z0-9+#.-]{2,}", title.lower())
            if w not in SUMMARY_STOP_WORDS
        }
        frequencies = {}
        for sentence in sentences:
            for word in re.findall(r"[a-z][a-z0-9+#.-]{2,}", sentence.lower()):
                if word not in SUMMARY_STOP_WORDS:
                    frequencies[word] = frequencies.get(word, 0) + 1

        ranked = []
        for index, sentence in enumerate(sentences):
            words = {
                w for w in re.findall(r"[a-z][a-z0-9+#.-]{2,}", sentence.lower())
                if w not in SUMMARY_STOP_WORDS
            }
            topical = sum(min(frequencies.get(w, 0), 5) for w in words) / max(1, len(words) ** .5)
            title_overlap = len(words & title_terms) * 2.2
            position_bonus = max(0, 2.25 - index * .08)
            ranked.append((topical + title_overlap + position_bonus, index, sentence))

        cue_words = (
            "result", "solution", "lesson", "means", "allows", "helps", "approach",
            "instead", "important", "responsibility", "the key", "the goal", "confirms",
            "usually", "root cause", "fixed", "prevents",
        )
        takeaway_candidates = [
            item for item in ranked
            if any(cue in item[2].lower() for cue in cue_words)
        ]
        if takeaway_candidates:
            _, takeaway_index, takeaway = max(
                takeaway_candidates,
                key=lambda item: item[0] + (item[1] / max(1, len(sentences))) * 2,
            )
        else:
            _, takeaway_index, takeaway = max(ranked, key=lambda item: item[0])

        def best_in_range(start, end, excluded):
            pool = [item for item in ranked if start <= item[1] < end and item[1] not in excluded]
            return max(pool, default=None, key=lambda item: item[0])

        count = len(sentences)
        chosen = []
        excluded = {takeaway_index}
        # Context, implementation, and outcome give a more useful overview
        # than three sentences selected from the same keyword-heavy section.
        ranges = [(0, max(1, count // 3)), (count // 3, max(count // 3 + 1, 2 * count // 3)), (2 * count // 3, count)]
        for start, end in ranges:
            item = best_in_range(start, end, excluded)
            if item:
                chosen.append((item[1], item[2]))
                excluded.add(item[1])
        for _, index, sentence in sorted(ranked, reverse=True):
            if len(chosen) == 3:
                break
            if index not in excluded:
                chosen.append((index, sentence))
                excluded.add(index)
        bullets = [sentence for _, sentence in sorted(chosen)]

    if not bullets:
        bullets = [excerpt(body_html, 240).rstrip("…")]

    if custom_takeaway:
        takeaway = str(custom_takeaway).strip()
    elif custom_summary:
        remaining = [s for s in _summary_sentences(body_html) if s not in bullets]
        cue_words = ("result", "solution", "lesson", "means", "allows", "helps", "approach", "instead")
        takeaway = next(
            (s for s in reversed(remaining) if any(cue in s.lower() for cue in cue_words)),
            bullets[0],
        )
    return bullets, takeaway


def summary_html(post):
    # Retired 2026-07-23 (Week 11 review) as a BUILD-TIME extraction/labeling
    # box: it either auto-extracted 3 sentences and stamped fixed
    # Problem/Build/Catch labels on them regardless of fit (mislabeled rows,
    # inline-code content dropped mid-sentence producing broken text like
    # "routes it to ,"), or required hand-authoring per post. The 65-post
    # back catalog has no consistent structure (11 weekly build posts vs.
    # troubleshooting posts, a day-N tutorial series, migrated/career posts)
    # so no single label set or extraction heuristic fit all of it.
    #
    # Rebuilt 2026-07-24 as a CLIENT-SIDE fetch instead: this just emits an
    # empty mount point; SUMMARY_WIDGET_JS fetches the real summary at page
    # load from blog-search's new GET /summary endpoint (generated once per
    # post by Claude Haiku in the indexer Lambda, universal Overview/Key
    # detail/Takeaway labels that fit any post shape — see
    # blog-search/indexer/handler.py). A post with no cached summary yet
    # (indexer hasn't run since it was published) just renders nothing.
    #
    # Excluded on Health/Life posts (Jay's call, 2026-07-24): the box is a
    # "scan fast, decide if this solves my problem" utility frame — a fit
    # for technical/build/troubleshooting posts, not for a personal,
    # first-person reflection where the box would flatten the piece into
    # a spoiler-summary instead of an entry point. Both categories were
    # verified to generate coherent, accurate summaries (the model handles
    # them fine) — this exclusion is about tone/fit, not a quality problem.
    if {"Health", "Life"} & set(post["tags"]):
        return ""
    topics = ",".join(post["tags"])
    return f'<div class="quick-summary-mount" data-slug="{escape(post["slug"])}" data-topics="{escape(topics)}"></div>'


def verification_html(post):
    """Render the "verified against current documentation" badge.

    Opt-in via a `verified: 'YYYY-MM-DD'` front-matter field, and applies to
    EVERY series (Weekly Lab, Architecture Series, Daily Intelligence) — the
    badge markup and wording live here so they stay identical everywhere and
    can be reworded in one place.

    Why this is opt-in rather than stamped on every post automatically
    (deliberate, do not "improve" this by defaulting it on): the badge makes a
    factual claim that a human actually checked this post's figures against
    current vendor documentation on a specific date. Auto-stamping it would
    assert that verification happened on posts where it did not, which is
    worse than having no badge at all — readers would trust a claim nothing
    backs. A post whose author skipped the check simply renders no badge.

    The date is shown verbatim and is intentionally the VERIFICATION date, not
    the publish date. They usually differ: a post drafted and checked on one
    day and held for a weekend publish should still say when the facts were
    actually confirmed. Cloud pricing and APIs move fast enough that a reader
    arriving a year later needs to know how stale the numbers might be.
    """
    verified = post.get("verified")
    if not verified:
        return ""
    # Accept a date object (unquoted YAML) or a string. Quoted ISO dates are
    # the common case because the rest of this repo's front matter quotes
    # dates, so parse those into the same human-readable form rather than
    # printing a bare "2026-08-07" at readers.
    if hasattr(verified, "strftime"):
        dt = verified
    else:
        try:
            dt = datetime.strptime(str(verified).strip()[:10], "%Y-%m-%d")
        except ValueError:
            dt = None  # non-ISO value: show it verbatim rather than guessing
    label = f"{dt.day} {dt.strftime('%B %Y')}" if dt else str(verified)
    return (
        '<div class="verified-badge">'
        '<span class="verified-check" aria-hidden="true">&#10003;</span>'
        '<span class="verified-text">'
        f'<strong>Verified against current vendor documentation on {escape(label)}.</strong> '
        'Pricing, limits and API behaviour were checked against the official docs on that '
        'date. Cloud services change fast &mdash; if you are reading this much later, treat '
        'the specifics as a starting point and re-check the linked sources.'
        '</span></div>'
    )


def parse_date(url, published=None):
    if published:
        try:
            return datetime.fromisoformat(published.replace("Z", "+00:00")).replace(tzinfo=None)
        except (ValueError, AttributeError):
            pass
    m = re.search(r"/(\d{4})/(\d{2})/", url or "")
    if m:
        return datetime(int(m.group(1)), int(m.group(2)), 1)
    return datetime(2024, 1, 1)


def slugify(title):
    s = re.sub(r"[^a-z0-9]+", "-", title.lower())
    return s.strip("-")[:60]


# ── HTML templates ────────────────────────────────────────────
# Default social preview image. Deliberately a raster file: LinkedIn, X and
# Facebook do not render SVG for og:image, so the per-post diagrams in
# blog/assets/diagrams cannot be used here even though they would suit.
# twitter:card is "summary" rather than "summary_large_image" because this is a
# logo, not a 1200x630 card — a large card would render it stretched and empty.
# Replacing this with a real 1200x630 image (or per-post generated cards) is the
# obvious upgrade, and only this constant and the card type need to change.
SOCIAL_IMAGE = f"{SITE_URL}/favicon-transparent.png"


def html_head(title, description, canonical, extra="", og_type="website",
              og_title=None, image=None):
    """Build the <head>.

    og_title defaults to `title`, but post pages pass the bare post title so the
    share card is not padded with the " | Jayanth Katta Blog" suffix that
    belongs in the browser tab.
    """
    social_title = og_title if og_title is not None else title
    social_image = image or SOCIAL_IMAGE
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{escape(title)}</title>
<meta name="description" content="{escape(description)}"/>
<link rel="canonical" href="{canonical}"/>
<meta property="og:type" content="{og_type}"/>
<meta property="og:site_name" content="Jayanth Katta"/>
<meta property="og:title" content="{escape(social_title)}"/>
<meta property="og:description" content="{escape(description)}"/>
<meta property="og:url" content="{canonical}"/>
<meta property="og:image" content="{social_image}"/>
<meta name="twitter:card" content="summary"/>
<meta name="twitter:title" content="{escape(social_title)}"/>
<meta name="twitter:description" content="{escape(description)}"/>
<meta name="twitter:image" content="{social_image}"/>
<link rel="icon" href="/favicon-transparent.png" type="image/png"/>
{PWA_HEAD}
<link rel="stylesheet" href="{ASSETS_URL}/blog.css?v={CSS_VERSION}"/>
{extra}
</head>"""


def nav_html(show_search=True, show_audio=False):
    search_btn = """  <button class="nav-icon-btn" id="nav-search-btn" aria-label="Search" title="Search posts">
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
  </button>""" if show_search else ""
    audio_btn = """  <button class="audio-toggle" id="audio-toggle" onclick="toggleBlogAudio()" title="Toggle beach sounds">🎻</button>""" if show_audio else ""
    return f"""<nav class="nav">
  <a class="nav-logo" href="/blog/" aria-label="Jayanth Katta blog home"><img class="brand-mark" src="/favicon-transparent.png" alt="" width="30" height="30" aria-hidden="true"><span class="brand-name">Jayanth Katta</span></a>
  <div class="nav-spacer"></div>
  <ul class="nav-links">
    <li><a href="/">Home</a></li>
    <li><a href="/blog/" class="active">Blog</a></li>
    <li><a href="/resume.html">Resume</a></li>
  </ul>
{search_btn}
{audio_btn}
  <button class="theme-toggle" id="nav-theme-btn" aria-label="Toggle dark mode">
    <span id="theme-icon-moon">🌙</span><span id="theme-label-text">Dark</span>
  </button>
  <button class="hamburger" id="hamburger-btn" aria-label="Menu">
    <span></span><span></span><span></span>
  </button>
</nav>
<div class="mobile-menu" id="mobile-menu">
  <a href="/">Home</a>
  <a href="/resume.html">Resume</a>
  <button class="theme-toggle" id="nav-theme-btn-mobile" aria-label="Toggle dark mode">
    <span id="theme-icon-moon-m">🌙</span><span id="theme-label-text-m">Dark</span>
  </button>
</div>"""


def footer_html():
    return f"""<footer class="footer">
  <p>&copy; <span data-current-year>{datetime.now().year}</span> Jayanth Katta &mdash; <a href="{SITE_URL}/">jayanthkatta.com</a></p>
</footer>"""


def back_top_html():
    return '<button class="back-top" id="back-top" aria-label="Back to top">↑</button>'


# ── Build individual post page ────────────────────────────────
def build_post_page(post, prev_post, next_post):
    slug          = post["slug"]
    title         = post["title"]
    display_title = post["display_title"]
    tags          = post["tags"]
    post_url = f"{BLOG_URL}/{slug}/"

    tags_html = " ".join(f'<span class="tag-badge">{t}</span>' for t in tags)
    quick_summary = summary_html(post)
    verified_badge = verification_html(post)

    prev_link = (
        f'<a href="/blog/{prev_post["slug"]}/" class="post-nav-link prev">'
        f'<span class="post-nav-dir">← Previous</span>'
        f'<span class="post-nav-title">{escape(prev_post["title"])}</span></a>'
        if prev_post else ""
    )
    next_link = (
        f'<a href="/blog/{next_post["slug"]}/" class="post-nav-link next">'
        f'<span class="post-nav-dir">Next →</span>'
        f'<span class="post-nav-title">{escape(next_post["title"])}</span></a>'
        if next_post else ""
    )

    disqus = f"""<div class="comments-section">
  <h3>Comments</h3>
  <div id="disqus_thread"></div>
  <script>
    var disqus_config = function () {{
      this.page.url = '{post_url}';
      this.page.identifier = '{slug}';
    }};
    (function() {{
      var d = document, s = d.createElement('script');
      s.src = 'https://{DISQUS_ID}.disqus.com/embed.js';
      s.setAttribute('data-timestamp', +new Date());
      (d.head || d.body).appendChild(s);
    }})();
  </script>
  <noscript>Please enable JavaScript to view comments.</noscript>
</div>"""

    extra = '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/atom-one-dark.min.css"/>'
    if post.get("draft"):
        # Belt-and-suspenders: the page is already excluded from every listing
        # (index, rss, posts.json) so nothing links here, but noindex also
        # stops a search engine from surfacing it if it ever gets crawled
        # directly (e.g. via an external link someone shared).
        extra += '\n<meta name="robots" content="noindex,nofollow"/>'

    return f"""{html_head(title + " | Jayanth Katta Blog", post["excerpt"], post_url, extra,
                          og_type="article", og_title=title)}
<body>
{nav_html(show_search=False)}
<div class="post-search-bar" id="post-search-bar">
  <div class="search-bar-inner">
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
    <input id="post-search-input" type="search" placeholder="Search posts… (press Enter)" autocomplete="off"/>
  </div>
</div>
<main class="post-page-layout">
  <div class="post-breadcrumb">
    <a href="/">Home</a><span class="post-breadcrumb-sep">›</span>
    <a href="/blog/">Blog</a><span class="post-breadcrumb-sep">›</span>
    <span>{escape(title[:50])}{"…" if len(title)>50 else ""}</span>
  </div>
  <article>
    <header class="post-header">
      <div class="post-header-meta">{tags_html}</div>
      <h1>{escape(display_title)}</h1>
      {f'<p class="post-description">{escape(post["description"])}</p>' if post["description"] else ""}
      <div class="post-info">
        <span>{post["date_fmt"]}</span>
        <span class="post-info-dot"></span>
        <span>{post["read_time"]} min read</span>
      </div>
    </header>
    {verified_badge}
    {quick_summary}
    <div class="post-divider"></div>
    <div class="post-body">{post["body_html"]}</div>
    <div class="post-tags">
      <span class="post-tags-label">Topics:</span>
      {tags_html}
    </div>
    <nav class="post-nav">{prev_link}{next_link}</nav>
  </article>
  {disqus}
</main>
{FEEDBACK_WIDGET_HTML}
{ASK_WIDGET_HTML}
{SUMMARY_WIDGET_JS}
{back_top_html()}
{footer_html()}
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
<script src="{ASSETS_URL}/hero-media.js?v={JS_VERSION}"></script>
<script src="{ASSETS_URL}/blog.js?v={JS_VERSION}"></script>
<script>
  hljs.highlightAll();
</script>
</body></html>"""


# ── Build index page ──────────────────────────────────────────
# Skills are DERIVED, never curated. TOPIC_VOCAB is a recognition
# vocabulary, not a list of claims: a topic only reaches the homepage once
# a post title or tag actually mentions it, and it ranks by how much has
# been written. Start writing about something new and it appears on its
# own; stop and it falls down the list. Add vocabulary entries as the
# subject matter widens — never add a skill by hand.
#   canonical name -> (match aliases, group)
TOPIC_VOCAB = {
    # Compute
    "EC2":              (["ec2", "instance type"],                    "Compute"),
    "Graviton":         (["graviton", "arm64"],                       "Compute"),
    "Spot":             (["spot"],                                    "Compute"),
    "Auto Scaling":     (["auto scaling", "autoscaling"],             "Compute"),
    "Lambda":           (["lambda", "serverless"],                    "Compute"),
    # Containers
    "EKS":              (["eks"],                                     "Containers"),
    "ECS / Fargate":    (["ecs", "fargate"],                          "Containers"),
    "Kubernetes":       (["kubernetes", "k8s"],                       "Containers"),
    "Docker":           (["docker"],                                  "Containers"),
    # Networking
    "VPC":              (["vpc"],                                     "Networking"),
    "Transit Gateway":  (["transit gateway"],                         "Networking"),
    "Route 53":         (["route 53", "route53", "dns"],              "Networking"),
    "CloudFront":       (["cloudfront", "edge"],                      "Networking"),
    "Load Balancing":   (["alb", "nlb", "load balanc"],               "Networking"),
    "PrivateLink":      (["privatelink", "vpc endpoint"],             "Networking"),
    # Security & Identity
    "IAM":              (["iam"],                                     "Security & Identity"),
    "Identity Center":  (["identity center", "sso"],                  "Security & Identity"),
    "KMS":              (["kms", "encryption"],                       "Security & Identity"),
    "Security Hub":     (["security hub", "guardduty"],               "Security & Identity"),
    "Control Tower":    (["control tower", "landing zone", "aft"],    "Security & Identity"),
    "Organizations":    (["organizations", "scp"],                    "Security & Identity"),
    "Config":           (["config compliance", "aws config"],         "Security & Identity"),
    # Data & Storage
    "S3":               (["s3"],                                      "Data & Storage"),
    "Aurora":           (["aurora"],                                  "Data & Storage"),
    "RDS":              (["rds", "postgres", "mysql"],                "Data & Storage"),
    "DynamoDB":         (["dynamodb"],                                "Data & Storage"),
    "Athena":           (["athena", "glue"],                          "Data & Storage"),
    # IaC & Delivery
    "Terraform":        (["terraform"],                               "IaC & Delivery"),
    "GitOps":           (["gitops", "argo"],                          "IaC & Delivery"),
    "GitHub Actions":   (["github actions"],                          "IaC & Delivery"),
    "CloudFormation":   (["cloudformation"],                          "IaC & Delivery"),
    "Drift Detection":  (["drift"],                                   "IaC & Delivery"),
    # Operations & Cost
    "CloudWatch":       (["cloudwatch", "logging", "observability"],  "Operations & Cost"),
    # Messaging & Events — aliases kept tight on purpose. "sqs"/"sns" are
    # safe letter combinations; avoid loose words like "queue" or
    # "notification" that appear in unrelated posts. See the "arc" note
    # below for what loose matching costs.
    "EventBridge":      (["eventbridge", "event-driven"],             "Messaging & Events"),
    "SQS":              (["sqs"],                                     "Messaging & Events"),
    "SNS":              (["sns"],                                     "Messaging & Events"),
    "Step Functions":   (["step function"],                           "Messaging & Events"),
    "Cost & FinOps":    (["cost", "finops", "cur", "savings", "billing"], "Operations & Cost"),
    "Systems Manager":  (["systems manager", "ssm", "patch"],         "Operations & Cost"),
    # NB: no bare "arc" alias — it matches "Architecture" in every arch title.
    "Resilience / DR":  (["disaster recovery", "multi-region", "failover",
                          "recovery controller"],                     "Operations & Cost"),
}


def topics_for(title, tags, text=""):
    """Canonical topic names a post matches, by the same rule used to count.

    Both the homepage badge and the click-through filter call this, which is
    the whole point: they used to disagree. The badge counted a post if ANY
    alias appeared in its title or tags, then linked to a search for only the
    FIRST alias across title, excerpt and tags -- two different questions with
    two different answers. 17 of 36 topics showed a count that did not match
    what clicking produced, and three ("Resilience / DR", "Systems Manager",
    "PrivateLink") advertised posts and then showed an empty page.
    """
    # Includes the body, not just the title and tags. Counting titles alone
    # said this blog had 6 posts about S3 while the AWS coverage section,
    # which reads the body, said 47 -- the same service with two numbers on
    # one page. A post that spends three paragraphs on S3 is about S3 whether
    # or not the word reached its headline.
    hay = (title + " " + " ".join(tags) + " " + text).lower()
    return [name for name, (aliases, _group) in TOPIC_VOCAB.items()
            if any(a in hay for a in aliases)]


TABBED_PROGRESS_TEMPLATE = """
    <!-- (1) Architecture series progress - one card, one tab per cloud.
         This was three separate cards, one per cloud: three boxes saying the
         same thing, and a lot of sidebar. Collapsing them into three summary
         bars would have thrown away the per-post dots and the read-list, which
         is the part readers actually use. So the tabs switch which series is
         shown, and each series keeps its own localStorage key - arch-read-v1,
         az-read-v1, gcp-read-v1 - exactly the keys the separate widgets used.
         Saved progress surviving the merge is the whole constraint here. -->
    <div class="sidebar-card" id="series-progress-widget">
      <div class="sidebar-title">Architecture series progress</div>
      <div class="sp-tabs" id="sp-tabs"></div>
      <div id="sp-years" style="display:none;gap:4px;margin-bottom:10px;flex-wrap:wrap"></div>
      <div id="sp-dots" style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:12px"></div>
      <div style="height:4px;background:var(--border);border-radius:4px;margin-bottom:9px;overflow:hidden">
        <div id="sp-bar" style="height:100%;background:var(--sp-accent,var(--orange));border-radius:4px;width:0%;transition:width .4s ease"></div>
      </div>
      <div style="display:flex;justify-content:space-between;align-items:center;font-size:11px;color:var(--text-muted)">
        <span><strong id="sp-count" style="color:var(--text)">0</strong> of <span id="sp-total">0</span> <span id="sp-unit">posts read</span></span>
        <a id="sp-next" href="#" style="color:var(--sp-accent,var(--orange));text-decoration:none;font-size:11px"></a>
      </div>
      <div style="font-size:10.5px;color:var(--text-muted);margin-top:9px;padding-top:9px;border-top:0.5px solid var(--border)">Stored in your browser &middot; picks up where you left off</div>
    </div>
    <script>
    (function(){
      var ALL = __ALL_SERIES__;
      if(!ALL.length) return;
      var TABKEY = 'sp-active-v1';
      var card = document.getElementById('series-progress-widget');
      var cur = 0;
      try{
        var saved = localStorage.getItem(TABKEY);
        ALL.forEach(function(s,i){ if(s.id === saved) cur = i; });
      }catch(e){}

      function S(){ return ALL[cur]; }
      function load(){ try{ return JSON.parse(localStorage.getItem(S().key)||'[]'); }catch(e){ return []; } }
      function save(r){ try{ localStorage.setItem(S().key,JSON.stringify(r)); }catch(e){} }

      var COMPACT_AT = 24;
      function dotStyle(isRead, compact){
        var a = 'var(--sp-accent,var(--orange))';
        if(compact){
          return 'width:13px;height:13px;border-radius:3px;display:block;'
            +'border:1px solid '+(isRead?a:'var(--border)')+';'
            +'background:'+(isRead?a:'transparent')+';'
            +'text-decoration:none;flex-shrink:0;transition:all .15s;cursor:pointer';
        }
        return 'width:26px;height:26px;border-radius:50%;display:flex;align-items:center;'
          +'justify-content:center;font-size:10px;font-weight:700;'
          +'border:1.5px solid '+(isRead?a:'var(--border)')+';'
          +'color:'+(isRead?'#1D2322':'var(--text-muted)')+';'
          +'background:'+(isRead?a:'transparent')+';'
          +'text-decoration:none;flex-shrink:0;transition:all .15s;cursor:pointer';
      }

      var curYear = null;
      function years(){
        var seen={}, out=[];
        S().posts.forEach(function(p){ if(!seen[p.y]){ seen[p.y]=1; out.push(String(p.y)); } });
        return out.sort().reverse();
      }
      function maxYearCount(){
        var c={}, m=0;
        S().posts.forEach(function(p){ c[p.y]=(c[p.y]||0)+1; if(c[p.y]>m)m=c[p.y]; });
        return m;
      }

      function renderTabs(){
        var t = document.getElementById('sp-tabs');
        t.innerHTML = '';
        if(ALL.length < 2) return;
        ALL.forEach(function(s,i){
          var b = document.createElement('button');
          b.type = 'button';
          b.className = 'sp-tab' + (i===cur ? ' active' : '') + ' ' + s.cls;
          b.textContent = s.name;
          b.setAttribute('aria-pressed', i===cur ? 'true' : 'false');
          b.addEventListener('click', function(){
            cur = i; curYear = null;
            try{ localStorage.setItem(TABKEY, s.id); }catch(e){}
            render();
          });
          t.appendChild(b);
        });
      }

      function renderYears(useTabs, ys){
        var tw = document.getElementById('sp-years');
        if(!useTabs){ tw.style.display='none'; return; }
        tw.style.display='flex';
        tw.innerHTML='';
        ys.forEach(function(y){
          var b=document.createElement('button');
          b.type='button'; b.dataset.y=y; b.textContent=y;
          var on = String(y)===String(curYear);
          b.style.cssText='font:inherit;font-size:10.5px;padding:2px 8px;border-radius:20px;cursor:pointer;'
            +'border:1px solid '+(on?'var(--sp-accent,var(--orange))':'var(--border)')+';'
            +'background:'+(on?'var(--sp-accent,var(--orange))':'transparent')+';'
            +'color:'+(on?'#1D2322':'var(--text-muted)')+';'
            +'font-weight:'+(on?'600':'400');
          b.addEventListener('click',function(){ curYear=y; render(); });
          tw.appendChild(b);
        });
      }

      function render(){
        var s = S();
        card.style.setProperty('--sp-accent', s.accent);
        var read = load();
        var ys = years();
        var useTabs = ys.length > 1;
        if(useTabs && !curYear) curYear = ys[0];
        var shown = useTabs ? s.posts.filter(function(q){ return String(q.y)===String(curYear); }) : s.posts;
        var compact = (useTabs ? maxYearCount() : s.posts.length) > COMPACT_AT;

        renderTabs();
        renderYears(useTabs, ys);

        var wrap = document.getElementById('sp-dots');
        wrap.style.gap = compact ? '4px' : '6px';
        wrap.innerHTML = '';
        shown.forEach(function(p){
          var d = document.createElement('a');
          d.href = '/blog/'+p.slug+'/';
          d.title = '#'+p.n+': '+p.title;
          var isRead = read.indexOf(p.n) > -1;
          d.style.cssText = dotStyle(isRead, compact);
          if(!compact) d.textContent = p.n;
          d.addEventListener('click',function(e){
            e.preventDefault();
            var r=load(); var i=r.indexOf(p.n);
            if(i>-1)r.splice(i,1); else r.push(p.n);
            save(r); render();
          });
          wrap.appendChild(d);
        });

        var inScope = shown.filter(function(q){ return read.indexOf(q.n) > -1; }).length;
        var pct = shown.length ? Math.round(inScope/shown.length*100) : 0;
        document.getElementById('sp-bar').style.width = pct+'%';
        document.getElementById('sp-count').textContent = inScope;
        document.getElementById('sp-total').textContent = shown.length;
        document.getElementById('sp-unit').textContent = useTabs ? ('posts in '+curYear) : 'posts read';

        var next=null;
        for(var i=0;i<s.posts.length;i++){ if(read.indexOf(s.posts[i].n)===-1){ next=s.posts[i]; break; } }
        var el=document.getElementById('sp-next');
        if(next){ el.href='/blog/'+next.slug+'/'; el.textContent='#'+next.n+' Next →'; }
        else{ el.textContent='✓ All done!'; el.removeAttribute('href'); }
      }
      render();
    })();
    </script>
"""


def tabbed_progress_widget(entries):
    """One progress card with a tab per cloud series.

    `entries` is a list of dicts: id, name, key, cls, accent, posts. A series
    with no posts is dropped by the caller, so a cloud that has not started
    yet contributes no tab rather than an empty one.
    """
    if not entries:
        return ""
    return TABBED_PROGRESS_TEMPLATE.replace(
        "__ALL_SERIES__", json.dumps(entries, separators=(",", ":")))


POSTS_PER_PAGE = 24

# Which cloud a post belongs to, decided by its series label rather than by
# anything in its body: a post that merely mentions Azure is not an Azure post,
# and the label is what the reader is being told. Module level because the blog
# index and the home page's posts.json both need it, and two copies would let
# the blog and the portfolio disagree about what colour a post is.
CLOUD_BY_LABEL = [
    ("Azure Architecture Series", "cloud cloud-azure"),
    ("GCP Architecture Series", "cloud cloud-gcp"),
    ("AWS Architecture Series", "cloud cloud-aws"),
    ("AWS Daily Intelligence", "cloud cloud-aws"),
    ("AWS Weekly Intelligence", "cloud cloud-aws"),
    ("AWS Weekly Lab", "cloud cloud-aws"),
]


# Everything that is not a cloud series. Same warm, desaturated register as the
# three cloud accents -- clay, plum, sage, rose, sand -- so the whole set reads
# as one palette rather than a cloud family plus some other colours. Order
# matters: the first match wins, so the more specific label is listed first.
TOPIC_BY_LABEL = [
    ("30 Days of AWS Terraform", "topic topic-tf30"),
    ("Terraform", "topic topic-terraform"),
    ("GitOps", "topic topic-gitops"),
    ("AI", "topic topic-ai"),
    ("Career", "topic topic-career"),
    ("Health", "topic topic-health"),
    ("Life", "topic topic-life"),
    ("Databases & Ops", "topic topic-db"),
    # The bare cloud tags. Same hue as the matching series so a cloud looks
    # like itself wherever it appears, but the topic treatment so the filter
    # row still separates a series from a tag. Listed after the series entries
    # above, and checked after CLOUD_BY_LABEL, so a post carrying both "AWS"
    # and "AWS Daily Intelligence" is styled as the series.
    ("AWS", "topic topic-aws"),
    ("Azure", "topic topic-azure"),
    ("GCP", "topic topic-gcp"),
]


def cloud_class(tags):
    """The accent class for a post or pill.

    Cloud series first, then topics. Topics are tinted more softly than series
    in blog.css: without that, tinting everything would erase the one thing
    that currently distinguishes "a series" from "a tag" in the filter row.
    Anything matching neither is left neutral rather than given a colour it has
    not earned.
    """
    for label, cls in CLOUD_BY_LABEL:
        if label in tags:
            return " " + cls
    for label, cls in TOPIC_BY_LABEL:
        if label in tags:
            return " " + cls
    return ""


def build_index_page(posts, page_posts=None, page=1, total_pages=1):
    """Build one page of the blog index.

    `posts` is always the full set -- every widget, count and filter pill is
    derived from it, so slicing it would quietly break the sidebar. Only the
    cards are paginated, via `page_posts`.

    Pagination exists because every card used to be embedded in this one file:
    2.8 KB each, so 99 posts was a 279 KB page and 1,000 would be 2.7 MB, all of
    it downloaded before a reader sees the first post. It degrades gradually and
    never errors, which is why it needed catching before it got bad.

    The page links are real <a href> elements rather than JavaScript, because
    there is no sitemap.xml -- this index is the only thing linking to every
    post, so a JS-only pager would cut crawlers off from older posts.
    """
    tag_counts = {}
    for p in posts:
        for t in p["tags"]:
            tag_counts[t] = tag_counts.get(t, 0) + 1

    # Tags that stay ON posts -- so search and data-tags still match them -- but
    # get no pill. Kubernetes reached 3 posts of 100 and Tech says nothing about
    # what a reader would get, and both cost a slot in a row that already wraps
    # to two lines. Removing them from CATEGORY_ORDER instead would strip the
    # tag from the posts entirely, because detect_tags() filters against it.
    NO_PILL = {"Kubernetes", "Tech"}
    cats = [c for c in CATEGORY_ORDER
            if c == "All" or (tag_counts.get(c, 0) > 0 and c not in NO_PILL)]

    # Series pills carry their cloud's accent; topic pills stay neutral. That
    # split is doing real work -- the row used to be one undifferentiated line
    # of grey, and now "a series" and "a tag" are visibly different things.
    # Driven off CLOUD_BY_LABEL so a pill's tint always matches the cards it
    # filters to; a pill tinted for a cloud whose cards were not would be worse
    # than no tint at all.
    filter_pills = "\n".join(
        f'<button class="filter-pill {"active" if c=="All" else ""}{cloud_class([c])}" data-tag="{c.lower()}">'
        f'{c}{" ("+str(tag_counts.get(c,0))+")" if c!="All" else " ("+str(len(posts))+")"}'
        f'</button>'
        for c in cats
    )

    total_posts = len(posts)
    total_mins  = sum(p["read_time"] for p in posts)
    unique_tags = len([c for c in CATEGORY_ORDER if tag_counts.get(c, 0) > 0])

    post_texts = [soup_text(p["body_html"]) for p in posts]

    # The service catalogue is generated from botocore, so it knows AWS and
    # nothing else. Two widgets are built on it — the "AWS services across all
    # posts" bar list and the domain donut — and an Azure or GCP post matches no
    # service in it. Left alone, an Azure post would count as a post with zero
    # AWS services and land in the donut's "Non-AWS" slice beside the health and
    # career posts, which is true but useless: it would say the blog is getting
    # less technical when it is getting broader.
    #
    # So both widgets are scoped to the posts the catalogue can actually
    # describe, and the footer says which posts those are. A non-AWS series gets
    # its own widget when there is a catalogue behind it, not a share of this one.
    NON_AWS_SERIES = ("Azure Architecture Series", "GCP Architecture Series")
    aws_scope = [(p, t) for p, t in zip(posts, post_texts)
                 if not any(s in p["tags"] for s in NON_AWS_SERIES)]
    aws_posts = [p for p, _ in aws_scope]
    aws_texts = [t for _, t in aws_scope]

    # Which services each post mentions, so clicking one in the sidebar can
    # filter the grid to those posts. Pipe-delimited and lower-cased: the
    # filter does a substring test, and service names contain spaces, so a
    # delimiter is what stops "s3" matching inside "s3 express".
    post_services = {}
    for _p, _text in zip(posts, post_texts):
        _hits = set(count_services(_text)) | set(count_services(_p["title"]))
        post_services[_p["slug"]] = "|".join(sorted(h.lower() for h in _hits))

    # Cloud accent. A card carries a colour so the grid is scannable without
    # reading: AWS warm, Azure blue, GCP green. Driven off the series label
    # rather than the post's content, because a post that merely mentions Azure
    # is not an Azure post -- the label is the thing the reader is being told.
    # A post in no cloud series gets no class and is styled exactly as before.
    cards_html = []
    for p in (posts if page_posts is None else page_posts):
        tag1 = p["tags"][0] if p["tags"] else "Tech"
        tags_data = " ".join(p["tags"]).lower()
        cards_html.append(
            f'<a href="/blog/{p["slug"]}/" class="post-card{cloud_class(p["tags"])}"'
            f' data-slug="{p["slug"]}"'
            f' data-title="{escape(p["title"])}"'
            f' data-excerpt="{escape(p["excerpt"])}"'
            f' data-tags="{escape(tags_data)}"'
            f' data-date="{p["date"].strftime("%Y-%m-%d")}"'
            f' data-services="|{post_services.get(p["slug"], "")}|"'
            f' data-topics="|{"|".join(x.lower() for x in topics_for(p["title"], p["tags"], post_texts[posts.index(p)]))}|">'
            f'<div class="post-card-body">'
            f'<div class="post-meta"><span class="tag-badge">{tag1}</span>'
            f'<span class="post-date">{p["date_fmt"]}</span></div>'
            f'<div class="post-title">{escape(p["title"])}</div>'
            f'<div class="post-excerpt">{escape(p["excerpt"])}</div>'
            f'<div class="post-footer">'
            f'<span class="read-time"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg> {p["read_time"]} min read</span>'
            f'<span class="read-more">Read <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"/></svg></span>'
            f'</div></div></a>'
        )

    sb_tags = "\n".join(
        f'<span class="sb-tag" data-tag="{c.lower()}">{c} <span style="opacity:.5;font-size:.65rem">{tag_counts.get(c,0)}</span></span>'
        for c in CATEGORY_ORDER if c != "All" and tag_counts.get(c, 0) > 0
    )

    # ── Posts by cloud ────────────────────────────────────────
    # The blog stopped being an AWS blog when the Azure and GCP series started,
    # and nothing in the sidebar said so. Counted from the same tag test
    # applyFilters() uses rather than from CLOUD_BY_LABEL, so the number on a
    # row always equals the number of cards clicking it produces -- the service
    # badges and their filter drifted apart exactly once, on 17 of 36 topics,
    # by being computed two different ways.
    cloud_defs = [("AWS", "aws", "cloud-aws"),
                  ("Azure", "azure", "cloud-azure"),
                  ("GCP", "gcp", "cloud-gcp")]
    cloud_counts = []
    for _name, _tag, _cls in cloud_defs:
        _n = sum(1 for p in posts if _tag in " ".join(p["tags"]).lower())
        if _n:
            cloud_counts.append((_name, _tag, _cls, _n))
    cloud_total = sum(c[3] for c in cloud_counts)
    _cloud_max = max((c[3] for c in cloud_counts), default=1)
    cloud_rows = "\n".join(
        f'<span class="sb-tag cloud-row {cls}" data-tag="{tag}">'
        f'<span class="cloud-name">{name}</span>'
        f'<span class="cloud-bar"><span class="cloud-bar-fill" style="width:{100*n//_cloud_max}%"></span></span>'
        f'<span class="cloud-count">{n}</span></span>'
        for name, tag, cls, n in cloud_counts
    )
    # Only worth showing once there is more than one cloud to compare.
    cloud_widget = "" if len(cloud_counts) < 2 else f'''
    <div class="sidebar-card" id="clouds-widget">
      <div class="sidebar-title">Posts by cloud</div>
      <div class="cloud-list">
{cloud_rows}
      </div>
      <div class="svc-foot">{cloud_total} of {len(posts)} posts belong to a cloud series. Click one to filter.</div>
    </div>'''

    # ── The dataset behind filtering and search ───────────────
    # Filters run across every post, not just the page on screen, so blog.js
    # needs the whole set. Written once (from page 1, which sees the same full
    # `posts`) and fetched by the browser only when a reader actually filters,
    # so it stays off the critical path for the common case of landing on
    # /blog/ and reading the newest posts.
    if page == 1:
        cards_json = [
            {
                "slug": p["slug"],
                "title": p["title"],
                "excerpt": p["excerpt"],
                "tags": " ".join(p["tags"]).lower(),
                "tag1": p["tags"][0] if p["tags"] else "Tech",
                "date": p["date"].strftime("%Y-%m-%d"),
                "date_fmt": p["date_fmt"],
                "read_time": p["read_time"],
                "cloud": cloud_class(p["tags"]).strip(),
                "services": post_services.get(p["slug"], ""),
                "topics": "|".join(
                    x.lower() for x in topics_for(p["title"], p["tags"],
                                                  post_texts[i])),
            }
            for i, p in enumerate(posts)
        ]
        (BLOG_DIR / "cards.json").write_text(
            json.dumps(cards_json, separators=(",", ":")), encoding="utf-8")

    # The year pills are built at page load, before cards.json has arrived, so
    # they cannot be derived from the cards on screen -- page 3 would offer only
    # the years its own 24 posts happen to cover. Emit the full list instead.
    index_years = ",".join(sorted(
        {p["date"].strftime("%Y") for p in posts}, reverse=True))

    # ── Pagination nav ────────────────────────────────────────
    # Hidden by blog.js the moment a filter or search is active, because those
    # run across every post rather than the current page, so a page-2 link
    # would be meaningless while results are being shown.
    def page_href(n):
        return "/blog/" if n == 1 else f"/blog/page/{n}/"

    if total_pages > 1:
        bits = []
        if page > 1:
            bits.append(f'<a class="pg-link" href="{page_href(page-1)}" rel="prev">&#8592; Newer</a>')
        # First, last, and a window around the current page. A thousand posts
        # is forty pages; printing all forty is its own kind of clutter.
        window = {1, total_pages, page, page - 1, page + 1}
        shown = sorted(n for n in window if 1 <= n <= total_pages)
        prev_n = 0
        for n in shown:
            if prev_n and n - prev_n > 1:
                bits.append('<span class="pg-gap">&#8230;</span>')
            cls = "pg-num active" if n == page else "pg-num"
            bits.append(f'<a class="{cls}" href="{page_href(n)}">{n}</a>')
            prev_n = n
        if page < total_pages:
            bits.append(f'<a class="pg-link" href="{page_href(page+1)}" rel="next">Older &#8594;</a>')
        pagination = (
            '<nav class="pagination" id="pagination" aria-label="Blog pages">'
            + "".join(bits)
            + f'<span class="pg-of">Page {page} of {total_pages}</span></nav>'
        )
    else:
        pagination = ""

    # ── AWS service mention counts ─────────────────────────────
    # Two passes on purpose. The first reads every post to find out which
    # services are written about at all; the second counts them. It has to be
    # that order, because a service named properly in one post is then
    # recognisable by its bare name in another.
    known_services = KNOWN_SERVICES

    # Posts, not mentions. Mentions reward a long post that repeats a name --
    # S3 read 386 against Aurora's 48, which says more about how often the
    # letters "S3" appear in a paragraph about buckets than about how much of
    # this blog is about S3. One post counts once, however much it says.
    #
    # Reuses the per-post service sets already built for the card filter, so
    # the number on the bar is exactly the number of posts that clicking it
    # will show. Those two disagreeing is the bug this session just fixed on
    # the homepage; no reason to reintroduce it here.
    service_counts = {}
    for _p in aws_posts:
        for svc in filter(None, post_services.get(_p["slug"], "").split("|")):
            service_counts[svc] = service_counts.get(svc, 0) + 1
    # post_services is lower-cased for the DOM filter; restore display case.
    _display = {s.lower(): s for s in KNOWN_SERVICES}
    service_counts = {_display.get(k, k): v for k, v in service_counts.items()}

    # The catalogue is curated, so it can fall behind the writing. This is what
    # stops that happening silently: anything written about repeatedly that the
    # widget cannot show gets named here, at build time, every time.
    # Only the top few, and only if there is something worth acting on -- a
    # header with nothing under it trains you to skip the whole block.
    unlisted = find_unlisted_services(aws_texts)[:12]
    if unlisted:
        print("  NOTE: %d service(s) mentioned in posts but missing from "
              "SERVICE_DOMAIN (add them there to include them in the "
              "widgets):" % len(unlisted))
        for name, n in unlisted:
            print(f"        {name}  ({n} post-level mentions)")

    ranked = sorted(service_counts.items(), key=lambda x: (-x[1], x[0]))
    services_total = len(ranked)

    # A ranked bar list, not a bubble cloud.
    #
    # The bubbles were replaced after measuring them: the sidebar is 211px
    # wide, S3's circle came out 72px across, and only nine of eighteen could
    # be placed while 65% of the canvas sat empty. Circle packing needs room
    # this column does not have, and the counts were only readable on hover.
    #
    # Bars fit the shape of the space, so every service fits -- all of them,
    # scrolled, rather than a top slice that quietly drops two thirds of the
    # list under a heading claiming "across all posts". They are also built
    # here rather than by script: there is no layout to compute, so the widget
    # renders with JavaScript disabled and cannot mis-place anything.
    max_count = ranked[0][1] if ranked else 1
    def _service_row(s, c):
        desc, url = SERVICE_INFO.get(s, ("", ""))
        # The tooltip is AWS's own description, so a reader who does not know
        # what "Firehose" is gets an answer without leaving the page, and the
        # name links to AWS's own page for anyone who wants more than a line.
        tip = f"{s} — {desc}" if desc else f"{s} — {c} post{'' if c == 1 else 's'}"
        width = max(2, round(c / max_count * 100))
        # The name filters the posts on this page; the arrow leaves for AWS.
        # That way the primary click keeps the reader here -- "show me what you
        # wrote about Aurora" is the question the sidebar is really answering,
        # and the definition is already in the tooltip for the other one.
        out = (f'<button type="button" class="svc-name" '
               f'data-service="{escape(s.lower())}">{escape(s)}</button>')
        if url:
            out += (f'<a class="svc-link" href="{escape(url)}" target="_blank" '
                    f'rel="noopener noreferrer" title="{escape(s)} on aws.amazon.com" '
                    f'aria-label="{escape(s)} on aws.amazon.com">&#8599;</a>')
        else:
            out += '<span class="svc-link svc-link-empty" aria-hidden="true"></span>'
        # Name and count on one line, bar beneath. A single-line grid needed a
        # fixed name column to keep the bars comparable, and at sidebar width
        # that column truncated 37 of 132 names -- including Step Functions,
        # Secrets Manager and Transit Gateway. Stacking gives the name the full
        # width and the bar a longer, more readable run.
        return (f'<div class="svc-row" title="{escape(tip)}">'
                f'<span class="svc-head">{out}'
                f'<span class="svc-count">{c}</span></span>'
                f'<span class="svc-track"><span class="svc-fill" '
                f'style="width:{width}%"></span></span></div>')

    service_rows = "\n".join(_service_row(s, c) for s, c in ranked)
    described = sum(1 for s, _ in ranked if s in SERVICE_INFO)
    print(f"  {services_total} AWS services detected across {len(aws_posts)} AWS "
          f"post(s) ({described} with an AWS description and link); "
          f"{len(posts) - len(aws_posts)} non-AWS post(s) excluded")

    # ── Widget data ───────────────────────────────────────────

    # 1. Reading stats
    avg_mins = round(total_mins / total_posts, 1) if total_posts else 0
    total_hrs = round(total_mins / 60, 1)

    # 2. Domain donut — keyword mapping on title + tags
    # Classify each post by the AWS services it actually discusses, rather than
    # by keyword substrings in its title.
    #
    # The old version searched title+tags for substrings and took the first
    # match, in dict order, with "arc" among the Networking keywords. "arc" is
    # inside "Architecture", so every AWS Architecture Series post matched
    # Networking first and stopped there: 18 of the 25 posts counted as
    # Networking were really about IAM, KMS, Aurora, DynamoDB, Lambda and
    # Secrets Manager. "Archive MongoDB data in Azure" was Networking too.
    # Security read 5% because its posts had already been claimed.
    #
    # Services are detected dynamically now, so this maps those to domains and
    # lets the post's own content decide. The title is weighted heavily: a post
    # titled "DynamoDB capacity" belongs to Data even if it mentions VPC while
    # explaining something else.
    domain_counts = {}
    for p, text in aws_scope:
        title_hits = count_services(p["title"])
        body_hits = count_services(text)

        # A service with no domain mapping still counts, into "Other AWS".
        # Ignoring it would quietly shrink a post's AWS-ness to zero and file
        # it under Non-AWS, which is how a widget starts lying as the
        # catalogue grows past what anyone has classified by hand.
        scores = {}
        for svc, n in body_hits.items():
            d = SERVICE_DOMAIN.get(svc, "Other AWS")
            scores[d] = scores.get(d, 0) + n
        for svc, n in title_hits.items():
            d = SERVICE_DOMAIN.get(svc, "Other AWS")
            scores[d] = scores.get(d, 0) + n * 25

        if scores:
            domain = max(scores.items(), key=lambda kv: (kv[1], kv[0]))[0]
        else:
            # Health, life and career posts. They are not a classification
            # failure, so they get an honest label rather than "Other".
            domain = "Non-AWS"
        domain_counts[domain] = domain_counts.get(domain, 0) + 1

    domain_counts = dict(sorted(domain_counts.items(), key=lambda kv: -kv[1]))
    domain_total = sum(domain_counts.values()) or 1
    domain_json = json.dumps([
        {"name": d, "count": c, "pct": round(c / domain_total * 100)}
        for d, c in domain_counts.items() if c > 0
    ])

    # 3. Arch series for progress tracker + mini-feed
    arch_posts = [p for p in posts if "AWS Architecture Series" in p["tags"]]

    # Lab series for progress tracker — extract week number from slug
    import re as _re
    def _week_num(p):
        m = _re.search(r'week-(\d+)', p["slug"])
        return int(m.group(1)) if m else 999
    lab_posts = sorted([p for p in posts if "AWS Weekly Lab" in p["tags"]], key=_week_num)
    lab_series_json = json.dumps([
        {"n": _week_num(p), "slug": p["slug"],
         "title": _re.sub(r'^Week \d+\s*[-–—]\s*', '', p["title"]),
         "date": p["date_fmt"], "y": p["date"].year}
        for p in lab_posts
    ])
    arch_series_json = json.dumps([
        {"n": i+1, "slug": p["slug"], "title": p["title"].split(" — ", 1)[-1] if " — " in p["title"] else p["title"], "date": p["date_fmt"], "y": p["date"].year}
        for i, p in enumerate(reversed(arch_posts))
    ])
    # Azure Architecture Series. Numbered from "#N" in the title rather than by
    # position, which is what the arch series does above: position is only
    # correct while no post is ever backfilled or reordered, and the number is
    # in the reader's URL and in their localStorage read-list, so it cannot be
    # allowed to shift under them. The title format is fixed in AZURE-ROADMAP.md.
    az_posts = [p for p in posts if "Azure Architecture Series" in p["tags"]]

    def _az_num(p):
        m = _re.search(r'#(\d+)', p["title"])
        return int(m.group(1)) if m else 0

    def _az_title(p):
        return _re.sub(r'^Azure Architecture Series\s*#\d+\s*[-–—]\s*', '', p["title"])

    az_series_json = json.dumps([
        {"n": _az_num(p), "slug": p["slug"], "title": _az_title(p),
         "date": p["date_fmt"], "y": p["date"].year}
        for p in sorted(az_posts, key=_az_num)
    ])

    # GCP Architecture Series. Numbered from "#N" in the title, exactly as the
    # Azure series above and for the same reason — the number is in the URL and
    # in the reader's saved read-list, so it must not depend on ordering.
    # The title format is fixed in GCP-ROADMAP.md.
    gcp_posts = [p for p in posts if "GCP Architecture Series" in p["tags"]]

    def _gcp_num(p):
        m = _re.search(r'#(\d+)', p["title"])
        return int(m.group(1)) if m else 0

    def _gcp_title(p):
        return _re.sub(r'^GCP Architecture Series\s*#\d+\s*[-–—]\s*', '', p["title"])

    gcp_series_json = json.dumps([
        {"n": _gcp_num(p), "slug": p["slug"], "title": _gcp_title(p),
         "date": p["date_fmt"], "y": p["date"].year}
        for p in sorted(gcp_posts, key=_gcp_num)
    ])

    def _feed_item(p, n=None, title=None):
        return {"n": n, "slug": p["slug"], "title": title or p["title"],
                "date": p["date_fmt"], "rt": p["read_time"],
                "tag": p["tags"][0] if p["tags"] else ""}

    _arch_feed = [
        _feed_item(p, len(arch_posts)-i,
                   p["title"].split(" — ", 1)[-1] if " — " in p["title"] else p["title"])
        for i, p in enumerate(arch_posts[:3])
    ]
    _lab_feed = [
        _feed_item(p, _week_num(p), _re.sub(r'^Week \d+\s*[-–—]\s*', '', p["title"]))
        for p in sorted(lab_posts, key=_week_num, reverse=True)[:3]
    ]
    # Daily Intelligence — titles read "AWS Daily Intelligence #N - Topic"
    # (hyphen separator, unlike the arch series' em dash).
    daily_posts = [p for p in posts if "AWS Daily Intelligence" in p["tags"]]

    def _daily_num(p):
        m = _re.search(r'#(\d+)', p["title"])
        return int(m.group(1)) if m else 0

    _daily_feed = [
        _feed_item(p, _daily_num(p) or None,
                   _re.sub(r'^AWS Daily Intelligence\s*#\d+\s*[-–—]\s*', '', p["title"]))
        for p in sorted(daily_posts, key=_daily_num, reverse=True)[:3]
    ]
    # Weekly Intelligence — titles read "AWS Weekly Intelligence #N - 3-9 August
    # 2026". Same #N convention as the daily series. Note the slug deliberately
    # avoids the pattern "week-<digits>", which _week_num() above matches when
    # numbering Weekly Lab posts.
    weekly_posts = [p for p in posts if "AWS Weekly Intelligence" in p["tags"]]

    def _weekly_num(p):
        m = _re.search(r'#(\d+)', p["title"])
        return int(m.group(1)) if m else 0

    _weekly_feed = [
        _feed_item(p, _weekly_num(p) or None,
                   _re.sub(r'^AWS Weekly Intelligence\s*#\d+\s*[-–—]\s*', '', p["title"]))
        for p in sorted(weekly_posts, key=_weekly_num, reverse=True)[:3]
    ]
    _az_feed = [
        _feed_item(p, _az_num(p) or None, _az_title(p))
        for p in sorted(az_posts, key=_az_num, reverse=True)[:3]
    ]
    _gcp_feed = [
        _feed_item(p, _gcp_num(p) or None, _gcp_title(p))
        for p in sorted(gcp_posts, key=_gcp_num, reverse=True)[:3]
    ]
    _all_feed = [_feed_item(p) for p in posts[:3]]

    feed_data_json = json.dumps({
        "arch":   {"items": _arch_feed,   "count": len(arch_posts),
                   "href": "/blog/?tag=aws+architecture+series"},
        "az":     {"items": _az_feed,     "count": len(az_posts),
                   "href": "/blog/?tag=azure+architecture+series"},
        "gcp":    {"items": _gcp_feed,    "count": len(gcp_posts),
                   "href": "/blog/?tag=gcp+architecture+series"},
        "lab":    {"items": _lab_feed,    "count": len(lab_posts),
                   "href": "/blog/?tag=aws+weekly+lab"},
        "daily":  {"items": _daily_feed,  "count": len(daily_posts),
                   "href": "/blog/?tag=aws+daily+intelligence"},
        "weekly": {"items": _weekly_feed, "count": len(weekly_posts),
                   "href": "/blog/?tag=aws+weekly+intelligence"},
        "all":    {"items": _all_feed,    "count": len(posts), "href": "/blog/"},
    })

    # 3b. Per-cloud series progress widgets.
    #
    # Built as a string rather than written into the page template because it
    # must not render at all until the series exists: a progress card reading
    # "0 of 0 posts read" is worse than no card. It appears with post #1 and
    # disappears again if the series is ever withdrawn.
    #
    # The markup is the lab/arch widget with its own id prefix and its own
    # localStorage key per series, so a reader's Azure progress is independent of
    # their GCP progress and both are independent of their AWS progress. Ids are
    # what keep several of these on one page from writing into each other's DOM.
    # One card, one tab per cloud. Series with no posts are dropped so a cloud
    # that has not started yet contributes no tab rather than an empty one.
    progress_widget_html = tabbed_progress_widget([
        e for e in [
            {"id": "aws", "name": "AWS", "key": "arch-read-v1",
             "cls": "cloud-aws", "accent": "#C4A484",
             "posts": json.loads(arch_series_json)},
            {"id": "azure", "name": "Azure", "key": "az-read-v1",
             "cls": "cloud-azure", "accent": "#5B7B9A",
             "posts": json.loads(az_series_json)},
            {"id": "gcp", "name": "GCP", "key": "gcp-read-v1",
             "cls": "cloud-gcp", "accent": "#8A9A5B",
             "posts": json.loads(gcp_series_json)},
        ] if e["posts"]
    ])

    # 4. Publishing heatmap — posts per month per year
    from collections import defaultdict
    import calendar
    hm_data = defaultdict(lambda: defaultdict(int))
    for p in posts:
        hm_data[p["date"].year][p["date"].month] += 1
    MONTH_ABBR = [calendar.month_abbr[m] for m in range(1, 13)]
    heatmap_json = json.dumps({
        str(yr): [{"m": MONTH_ABBR[mo-1], "n": hm_data[yr].get(mo, 0)} for mo in range(1, 13)]
        for yr in sorted(hm_data.keys(), reverse=True)
    })
    heatmap_years_json = json.dumps(sorted(hm_data.keys(), reverse=True))

    # ── Blog-extracted quiz questions ──────────────────────────
    blog_questions = []
    for p in posts[:15]:
        text = soup_text(p["body_html"])
        for svc in known_services:
            if svc.lower() in text.lower() and len(blog_questions) < 10:
                title_words = p["title"].split()
                if len(title_words) > 4:
                    blog_questions.append({
                        "q": f"Which AWS post covers: \"{p['title'][:60]}...\"?",
                        "a": p["date_fmt"],
                        "opts": [p["date_fmt"]] + ["Jan 2025", "Mar 2024", "Dec 2023"],
                        "e": f"Published {p['date_fmt']} — {p['excerpt'][:100]}",
                        "source": "blog"
                    })
                    break

    all_questions = [dict(q, source="aws") for q in AWS_QUIZ_BANK] + blog_questions
    quiz_json = json.dumps(all_questions)

    return f"""{html_head(
        "Blog | Jayanth Katta",
        "AWS Platform Engineer writing about cloud infrastructure, Terraform, Kubernetes, and life.",
        f"{BLOG_URL}/"
    )}
<body>
{nav_html(show_audio=True)}
<section class="hero">
  <video id="hero-video" class="hero-video" autoplay muted loop playsinline></video>
  <div class="hero-overlay"></div>
  <span class="hero-eyebrow">Engineering &amp; Life</span>
  <h1>Jayanth's Blog</h1>
  <p class="hero-sub">Thoughts on AWS, Terraform, Kubernetes, platform engineering, and the quieter things in life.</p>
  <div class="hero-stats">
    <div class="hero-stat"><span class="hero-stat-n">{total_posts}</span><span class="hero-stat-l">Posts</span></div>
    <div class="hero-stat"><span class="hero-stat-n">{unique_tags}</span><span class="hero-stat-l">Topics</span></div>
    <div class="hero-stat"><span class="hero-stat-n">{total_mins}</span><span class="hero-stat-l">Min of reading</span></div>
    <div class="hero-stat"><span class="hero-stat-n">{posts[0]["date_fmt"] if posts else ""}</span><span class="hero-stat-l">Latest</span></div>
  </div>
  <div class="hero-typer">$ <span id="hero-typer-text"></span><span class="hero-typer-cursor">|</span></div>
</section>
<div class="search-bar-wrap" id="search-bar-wrap">
  <div class="search-bar-inner">
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
    <input id="blog-search" type="search" placeholder="I'm looking for…" autocomplete="off"/>
  </div>
</div>
<div class="filters">
  {filter_pills}
</div>
<div class="results-count" id="results-count">{total_posts} posts</div>
<div class="layout">
  <div>
    <div class="posts-grid" id="posts-grid" data-page="{page}" data-total-pages="{total_pages}" data-years="{index_years}">
      {"".join(cards_html)}
      <div class="empty-state" id="empty-state" style="display:none">
        <h3>No posts found</h3><p>Try a different search term or topic filter.</p>
      </div>
    </div>
    {pagination}
  </div>
  <aside class="sidebar">
    {cloud_widget}
    <div class="sidebar-card" id="services-widget">
      <div class="sidebar-title">AWS services across all posts</div>
      <div class="svc-filter-note" id="svc-filter-note" style="display:none"></div>
      <div class="svc-list">
{service_rows}
      </div>
      <div class="svc-foot">All {services_total} AWS services covered, across {len(aws_posts)} AWS posts, by number of posts. Click one to filter; hover for what it does.</div>
    </div>
    <div class="sidebar-card" id="quiz-widget">
      <div class="sidebar-title" style="display:flex;justify-content:space-between;align-items:center">
        <span>AWS quiz</span>
        <span id="quiz-score" style="font-size:11px;color:var(--orange);font-weight:500"></span>
      </div>
      <div id="quiz-badge" style="display:inline-block;font-size:11px;padding:2px 10px;border-radius:20px;background:rgba(196,164,132,.12);color:#7A5C3E;margin-bottom:10px"></div>
      <div style="height:3px;background:var(--border);border-radius:4px;margin-bottom:12px">
        <div id="quiz-progress" style="height:100%;background:var(--orange);border-radius:4px;width:0%;transition:width .3s"></div>
      </div>
      <div id="quiz-qnum" style="font-size:11px;color:var(--text-muted);margin-bottom:6px"></div>
      <div id="quiz-q" style="font-size:14px;font-weight:500;line-height:1.5;margin-bottom:14px;min-height:42px"></div>
      <div id="quiz-opts" style="display:flex;flex-direction:column;gap:6px"></div>
      <div id="quiz-feedback" style="display:none;margin-top:10px;padding:10px 12px;border-radius:8px;font-size:12px;line-height:1.5"></div>
      <button id="quiz-next" onclick="quizNext()" style="display:none;margin-top:10px;width:100%;padding:8px;border-radius:8px;background:var(--orange);border:none;color:#fff;font-size:13px;font-weight:500;cursor:pointer">Next →</button>
      <div id="quiz-result" style="display:none;text-align:center;padding:1rem 0">
        <div id="quiz-result-emoji" style="font-size:32px;margin-bottom:6px"></div>
        <div id="quiz-result-score" style="font-size:22px;font-weight:500;color:var(--text)"></div>
        <div id="quiz-result-msg" style="font-size:12px;color:var(--text-muted);margin:4px 0 12px"></div>
        <button onclick="quizStart()" style="padding:6px 20px;border-radius:8px;background:var(--orange);border:none;color:#fff;font-size:12px;font-weight:500;cursor:pointer">Try again</button>
      </div>
    </div>
    <script>
    var QUIZ_BANK = {quiz_json};
    var qz = {{questions:[],current:0,score:0,answered:false}};
    function quizShuffle(a){{return a.slice().sort(function(){{return Math.random()-.5;}});}}
    function quizStart(){{
      qz.questions=quizShuffle(QUIZ_BANK).slice(0,5);
      qz.current=0;qz.score=0;qz.answered=false;
      document.getElementById('quiz-result').style.display='none';
      document.getElementById('quiz-q').style.display='';
      document.getElementById('quiz-opts').style.display='';
      document.getElementById('quiz-qnum').style.display='';
      document.getElementById('quiz-badge').style.display='';
      quizShow();
    }}
    function quizShow(){{
      var q=qz.questions[qz.current];
      qz.answered=false;
      document.getElementById('quiz-feedback').style.display='none';
      document.getElementById('quiz-next').style.display='none';
      document.getElementById('quiz-qnum').textContent='Question '+(qz.current+1)+' of '+qz.questions.length;
      document.getElementById('quiz-q').textContent=q.q;
      document.getElementById('quiz-progress').style.width=((qz.current/qz.questions.length)*100)+'%';
      document.getElementById('quiz-score').textContent=qz.score+' / '+qz.current;
      var badge=document.getElementById('quiz-badge');
      if(q.source==='blog'){{badge.textContent="From my blog";badge.style.background='rgba(196,164,132,.12)';badge.style.color='#7A5C3E';}}
      else{{badge.textContent="AWS fundamentals";badge.style.background='rgba(55,138,221,.12)';badge.style.color='#185FA5';}}
      var opts=document.getElementById('quiz-opts');
      opts.innerHTML='';
      quizShuffle(q.opts).forEach(function(opt){{
        var btn=document.createElement('button');
        btn.textContent=opt;
        btn.style.cssText='width:100%;text-align:left;padding:8px 12px;border-radius:8px;border:0.5px solid var(--border);background:var(--surface);color:var(--text);font-size:12px;cursor:pointer;transition:border-color .15s';
        btn.onmouseenter=function(){{if(!qz.answered)btn.style.borderColor='var(--orange)';}};
        btn.onmouseleave=function(){{if(!qz.answered)btn.style.borderColor='var(--border)';}};
        btn.onclick=function(){{quizAnswer(opt,btn,q);}};
        opts.appendChild(btn);
      }});
    }}
    function quizAnswer(opt,btn,q){{
      if(qz.answered)return;
      qz.answered=true;
      var correct=opt===q.a;
      if(correct)qz.score++;
      Array.from(document.getElementById('quiz-opts').children).forEach(function(b){{
        b.style.cursor='default';
        if(b.textContent===q.a){{b.style.background='rgba(76,175,80,.12)';b.style.borderColor='#4CAF50';b.style.color='#1B5E20';}}
        else if(b===btn&&!correct){{b.style.background='rgba(226,75,74,.1)';b.style.borderColor='#E24B4A';b.style.color='#A32D2D';}}
      }});
      var fb=document.getElementById('quiz-feedback');
      fb.style.display='';
      fb.style.background=correct?'rgba(76,175,80,.08)':'rgba(226,75,74,.08)';
      fb.style.borderLeft=correct?'3px solid #4CAF50':'3px solid #E24B4A';
      fb.style.color='var(--text)';
      fb.innerHTML='<strong>'+(correct?'Correct!':'Not quite.')+' </strong>'+q.e;
      document.getElementById('quiz-score').textContent=qz.score+' / '+(qz.current+1);
      if(qz.current<qz.questions.length-1){{
        document.getElementById('quiz-next').style.display='';
      }}else{{
        setTimeout(quizResult,1200);
      }}
    }}
    function quizNext(){{qz.current++;quizShow();}}
    function quizResult(){{
      document.getElementById('quiz-q').style.display='none';
      document.getElementById('quiz-opts').style.display='none';
      document.getElementById('quiz-qnum').style.display='none';
      document.getElementById('quiz-feedback').style.display='none';
      document.getElementById('quiz-next').style.display='none';
      document.getElementById('quiz-badge').style.display='none';
      var pct=qz.score/qz.questions.length;
      var res=document.getElementById('quiz-result');
      res.style.display='';
      document.getElementById('quiz-result-emoji').textContent=pct===1?'🏆':pct>=0.8?'⭐':pct>=0.6?'👍':'💡';
      document.getElementById('quiz-result-score').textContent=qz.score+' / '+qz.questions.length;
      document.getElementById('quiz-result-msg').textContent=pct===1?'Perfect — you know your AWS!':pct>=0.8?'Strong work.':pct>=0.6?'Good foundation.':'Keep reading 👆';
    }}
    quizStart();
    </script>
    <div class="sidebar-card" style="border-color:rgba(226,75,74,.3)">
      <div style="display:flex;align-items:center;gap:.5rem;margin-bottom:.6rem">
        <span style="width:8px;height:8px;border-radius:50%;background:#E24B4A;display:inline-block;animation:sb-pulse 1s infinite"></span>
        <span style="font-size:.68rem;font-weight:600;letter-spacing:.08em;color:#E24B4A">INCIDENT SIMULATOR</span>
      </div>
      <div style="font-size:.88rem;font-weight:600;color:var(--text);margin-bottom:.4rem">Production is down.</div>
      <div style="font-size:.78rem;color:var(--text-muted);line-height:1.55;margin-bottom:.85rem">12,500 users impacted. Can you find the root cause before it costs thousands? 50 real AWS incidents.</div>
      <a href="/blog/simulator/" class="ask-cta-btn" style="display:block;text-align:center;background:#E24B4A;text-decoration:none">Respond to incident →</a>
    </div>
    <style>@keyframes sb-pulse{{0%,100%{{opacity:1}}50%{{opacity:.3}}}}</style>

    {progress_widget_html}

    <!-- ① Lab Series Progress -->
    <div class="sidebar-card" id="lab-progress-widget">
      <div class="sidebar-title">Weekly lab progress</div>
      <div id="lp-years" style="display:none;gap:4px;margin-bottom:10px;flex-wrap:wrap"></div>
      <div id="lp-dots" style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:12px"></div>
      <div style="height:4px;background:var(--border);border-radius:4px;margin-bottom:9px;overflow:hidden">
        <div id="lp-bar" style="height:100%;background:var(--orange);border-radius:4px;width:0%;transition:width .4s ease"></div>
      </div>
      <div style="display:flex;justify-content:space-between;align-items:center;font-size:11px;color:var(--text-muted)">
        <span><strong id="lp-count" style="color:var(--text)">0</strong> of <span id="lp-total">{len(lab_posts)}</span> <span id="lp-unit">weeks done</span></span>
        <a id="lp-next" href="#" style="color:var(--orange);text-decoration:none;font-size:11px"></a>
      </div>
      <div style="font-size:10.5px;color:var(--text-muted);margin-top:9px;padding-top:9px;border-top:0.5px solid var(--border)">Stored in your browser · picks up where you left off</div>
    </div>
    <script>
    (function(){{
      var LAB = {lab_series_json};
      var KEY = 'lab-read-v1';
      function load(){{ try{{ return JSON.parse(localStorage.getItem(KEY)||'[]'); }}catch(e){{ return []; }} }}
      function save(r){{ try{{ localStorage.setItem(KEY,JSON.stringify(r)); }}catch(e){{}} }}
      var COMPACT_AT = 24;
      function dotStyle(isRead, compact){{
        if(compact){{
          return 'width:13px;height:13px;border-radius:3px;display:block;'
            +'border:1px solid '+(isRead?'var(--orange)':'var(--border)')+';'
            +'background:'+(isRead?'var(--orange)':'transparent')+';'
            +'text-decoration:none;flex-shrink:0;transition:all .15s;cursor:pointer';
        }}
        return 'width:26px;height:26px;border-radius:50%;display:flex;align-items:center;'
          +'justify-content:center;font-size:10px;font-weight:700;'
          +'border:1.5px solid '+(isRead?'var(--orange)':'var(--border)')+';'
          +'color:'+(isRead?'#1D2322':'var(--text-muted)')+';'
          +'background:'+(isRead?'var(--orange)':'transparent')+';'
          +'text-decoration:none;flex-shrink:0;transition:all .15s;cursor:pointer';
      }}
      var YEARS = (function(){{
        var seen = {{}}, out = [];
        LAB.forEach(function(p){{ if(!seen[p.y]){{ seen[p.y]=1; out.push(String(p.y)); }} }});
        return out.sort().reverse();
      }})();
      var useTabs = YEARS.length > 1 && LAB.length > COMPACT_AT;
      var curYear = YEARS[0];
      function maxYearCount(){{
        var c = {{}}, m = 0;
        LAB.forEach(function(p){{ c[p.y] = (c[p.y]||0)+1; if(c[p.y] > m) m = c[p.y]; }});
        return m;
      }}
      function renderTabs(){{
        var tw = document.getElementById('lp-years');
        if(!tw) return;
        if(!useTabs){{ tw.style.display = 'none'; return; }}
        tw.style.display = 'flex';
        if(!tw.dataset.built){{
          YEARS.forEach(function(y){{
            var b = document.createElement('button');
            b.textContent = y; b.dataset.y = y;
            b.style.cssText = 'font-size:10.5px;padding:2px 8px;border-radius:10px;border:1px solid var(--border);cursor:pointer;background:transparent;color:var(--text-muted)';
            b.onclick = function(){{ curYear = y; render(); }};
            tw.appendChild(b);
          }});
          tw.dataset.built = '1';
        }}
        tw.querySelectorAll('button').forEach(function(b){{
          var on = String(b.dataset.y) === String(curYear);
          b.style.background = on ? 'var(--orange)' : 'transparent';
          b.style.color = on ? '#1D2322' : 'var(--text-muted)';
          b.style.borderColor = on ? 'var(--orange)' : 'var(--border)';
          b.style.fontWeight = on ? '600' : '400';
        }});
      }}
      function render(){{
        var read = load();
        var wrap = document.getElementById('lp-dots');
        if(!wrap) return;
        var shown = useTabs ? LAB.filter(function(q){{ return String(q.y) === String(curYear); }}) : LAB;
        var compact = (useTabs ? maxYearCount() : LAB.length) > COMPACT_AT;
        wrap.style.gap = compact ? '4px' : '6px';
        wrap.innerHTML = '';
        renderTabs();
        shown.forEach(function(p){{
          var d = document.createElement('a');
          d.href = '/blog/'+p.slug+'/';
          d.title = 'Week '+p.n+': '+p.title;
          var isRead = read.includes(p.n);
          d.style.cssText = dotStyle(isRead, compact);
          if(!compact) d.textContent = p.n;
          d.addEventListener('click',function(e){{
            e.preventDefault();
            var r=load(); var i=r.indexOf(p.n);
            if(i>-1)r.splice(i,1); else r.push(p.n);
            save(r); render();
          }});
          wrap.appendChild(d);
        }});
        var inScope = shown.filter(function(q){{ return read.includes(q.n); }}).length;
        var pct = shown.length ? Math.round(inScope/shown.length*100) : 0;
        document.getElementById('lp-bar').style.width = pct+'%';
        document.getElementById('lp-count').textContent = inScope;
        document.getElementById('lp-total').textContent = shown.length;
        document.getElementById('lp-unit').textContent = useTabs ? ('weeks in '+curYear) : 'weeks done';
        var next = null;
        for(var i=0;i<LAB.length;i++){{ if(!read.includes(LAB[i].n)){{ next=LAB[i]; break; }} }}
        var el = document.getElementById('lp-next');
        if(next){{ el.href='/blog/'+next.slug+'/'; el.textContent='Wk '+next.n+' Next →'; }}
        else{{ el.textContent='✓ All done!'; el.removeAttribute('href'); }}
      }}
      render();
    }})();
    </script>
    <!-- ② Domain Donut -->
    <div class="sidebar-card" id="domain-donut-widget">
      <div class="sidebar-title">Posts by AWS domain</div>
      <div style="display:flex;gap:16px;align-items:center">
        <svg id="dd-svg" width="88" height="88" viewBox="0 0 88 88" style="flex-shrink:0"></svg>
        <div id="dd-legend" style="flex:1;display:flex;flex-direction:column;gap:6px"></div>
      </div>
    </div>
    <script>
    (function(){{
      var DATA = {domain_json};
      var COLORS = ['#4A90D9','#C4A484','#3D9970','#8E6DBE','#E24B4A','#C4A484'];
      var svg = document.getElementById('dd-svg');
      var legend = document.getElementById('dd-legend');
      if(!svg||!legend) return;
      var total = DATA.reduce(function(s,d){{return s+d.count;}},0);
      var R=32, cx=44, cy=44, stroke=13;
      var circ = 2*Math.PI*R;
      var offset = 0;
      DATA.forEach(function(d,i){{
        var len = (d.count/total)*circ;
        var c = document.createElementNS('http://www.w3.org/2000/svg','circle');
        c.setAttribute('cx',cx); c.setAttribute('cy',cy); c.setAttribute('r',R);
        c.setAttribute('fill','none'); c.setAttribute('stroke',COLORS[i%COLORS.length]);
        c.setAttribute('stroke-width',stroke);
        c.setAttribute('stroke-dasharray',len+' '+(circ-len));
        c.setAttribute('stroke-dashoffset',-offset);
        c.setAttribute('transform','rotate(-90 '+cx+' '+cy+')');
        svg.appendChild(c);
        offset += len;
        var row = document.createElement('div');
        row.style.cssText='display:flex;align-items:center;gap:6px;font-size:11.5px';
        row.innerHTML='<span style="width:8px;height:8px;border-radius:50%;background:'+COLORS[i%COLORS.length]+';flex-shrink:0"></span>'
          +'<span style="flex:1;color:var(--text)">'+d.name+'</span>'
          +'<span style="color:var(--text-muted);font-variant-numeric:tabular-nums">'+d.pct+'%</span>';
        legend.appendChild(row);
      }});
      var txt1=document.createElementNS('http://www.w3.org/2000/svg','text');
      txt1.setAttribute('x',cx);txt1.setAttribute('y',cy-3);txt1.setAttribute('text-anchor','middle');
      txt1.setAttribute('font-size','13');txt1.setAttribute('font-weight','700');txt1.setAttribute('fill','var(--text)');
      txt1.textContent=total;
      var txt2=document.createElementNS('http://www.w3.org/2000/svg','text');
      txt2.setAttribute('x',cx);txt2.setAttribute('y',cy+10);txt2.setAttribute('text-anchor','middle');
      txt2.setAttribute('font-size','8');txt2.setAttribute('fill','var(--text-muted)');
      txt2.textContent='posts';
      svg.appendChild(txt1);svg.appendChild(txt2);
    }})();
    </script>

    <!-- ③ Reading Stats -->
    <div class="sidebar-card" id="reading-stats-widget">
      <div class="sidebar-title">Reading stats</div>
      <div style="display:flex;gap:10px;margin-bottom:12px">
        <div style="flex:1;background:rgba(196,164,132,.1);border-radius:8px;padding:11px;text-align:center">
          <div style="font-size:26px;font-weight:800;color:var(--orange);line-height:1;letter-spacing:-1px">{total_posts}</div>
          <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:.06em;margin-top:3px">posts</div>
        </div>
        <div style="flex:1;background:rgba(196,164,132,.1);border-radius:8px;padding:11px;text-align:center">
          <div style="font-size:26px;font-weight:800;color:var(--orange);line-height:1;letter-spacing:-1px">{total_hrs}</div>
          <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:.06em;margin-top:3px">hrs total</div>
        </div>
        <div style="flex:1;background:rgba(196,164,132,.1);border-radius:8px;padding:11px;text-align:center">
          <div style="font-size:26px;font-weight:800;color:var(--orange);line-height:1;letter-spacing:-1px">{avg_mins}</div>
          <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:.06em;margin-top:3px">min avg</div>
        </div>
      </div>
      <div id="rs-personal" style="font-size:11px;color:var(--text-muted);text-align:center;min-height:16px"></div>
    </div>
    <script>
    (function(){{
      var read = (function(){{ try{{ return JSON.parse(localStorage.getItem('arch-read-v1')||'[]'); }}catch(e){{ return []; }} }})();
      var el = document.getElementById('rs-personal');
      if(el && read.length>0){{
        var mins = read.length * {avg_mins};
        el.innerHTML = 'You’ve read <strong style="color:var(--text)">'+read.length+' post'+(read.length!==1?'s':'')+
          '</strong> · <span style="color:var(--orange)">~'+Math.round(mins)+' min</span> invested';
      }}
    }})();
    </script>

    <!-- ④ Latest posts feed (switchable) -->
    <div class="sidebar-card" id="series-feed-widget">
      <div class="sidebar-title">Latest posts</div>
      <div id="sf-tabs" style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:10px"></div>
      <div id="sf-list"></div>
      <a id="sf-all" href="/blog/" style="display:block;margin-top:10px;font-size:11.5px;color:var(--orange);text-decoration:none;text-align:right">See all posts →</a>
    </div>
    <script>
    (function(){{
      var FEEDS = {feed_data_json};
      var TABS = [
        ['arch','Arch',     'AWS Architecture Series — one enterprise pattern at a time, with the decisions and trade-offs behind it'],
        ['az','Azure',      'Azure Architecture Series — the same treatment, on Azure, from the basics upward'],
        ['gcp','GCP',       'GCP Architecture Series — the same treatment, on Google Cloud, from the basics upward'],
        ['lab','Lab',       'AWS Weekly Lab — one production-grade platform capability built end to end each week'],
        ['daily','Daily',   'AWS Daily Intelligence — what AWS shipped, and whether it actually changes anything'],
        ['weekly','Weekly', 'AWS Weekly Intelligence — everything AWS shipped that week, ranked, in one place'],
        ['all','All',       'Every post, newest first, across all series and topics']
      ];
      var list = document.getElementById('sf-list');
      var tabWrap = document.getElementById('sf-tabs');
      var allLink = document.getElementById('sf-all');
      if(!list||!tabWrap||!allLink) return;
      function render(key){{
        var f = FEEDS[key];
        if(!f) return;
        list.innerHTML='';
        if(!f.items.length){{
          list.innerHTML='<div style="font-size:11.5px;color:var(--text-muted);padding:6px 0">No posts yet.</div>';
        }}
        f.items.forEach(function(p,i){{
          var row=document.createElement('a');
          row.href='/blog/'+p.slug+'/';
          row.style.cssText='display:flex;gap:10px;align-items:flex-start;padding:9px 0;border-bottom:0.5px solid var(--border);text-decoration:none;'+(i===f.items.length-1?'border-bottom:none;padding-bottom:0':'');
          var badge=p.n?('#'+p.n):'•';
          var meta=p.date+' · '+p.rt+' min'+((!p.n&&p.tag)?(' · '+p.tag):'');
          row.innerHTML='<div style="width:22px;height:22px;border-radius:50%;background:rgba(196,164,132,.12);color:var(--orange);font-size:10px;font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0;margin-top:1px">'+badge+'</div>'
            +'<div style="flex:1;min-width:0"><div style="font-size:12.5px;font-weight:600;color:var(--text);line-height:1.35;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden">'+p.title+'</div>'
            +'<div style="font-size:10.5px;color:var(--text-muted);margin-top:2px">'+meta+'</div></div>'
            +'<div style="color:var(--orange);font-size:14px;margin-top:2px">›</div>';
          list.appendChild(row);
        }});
        allLink.href=f.href;
        allLink.textContent='See all '+f.count+' post'+(f.count===1?'':'s')+' →';
        tabWrap.querySelectorAll('button').forEach(function(b){{
          var on=b.dataset.k===key;
          b.style.background=on?'var(--orange)':'transparent';
          b.style.color=on?'#1D2322':'var(--text-muted)';
          b.style.borderColor=on?'var(--orange)':'var(--border)';
          b.style.fontWeight=on?'600':'400';
        }});
        try{{localStorage.setItem('sf-tab',key);}}catch(e){{}}
      }}
      TABS.forEach(function(t){{
        var btn=document.createElement('button');
        btn.textContent=t[1]; btn.dataset.k=t[0];
        btn.title=t[2];                 // native tooltip on hover
        btn.setAttribute('aria-label', t[2]);
        btn.style.cssText='font-size:10.5px;padding:2px 8px;border-radius:10px;border:1px solid var(--border);cursor:pointer;background:transparent;color:var(--text-muted)';
        btn.onclick=function(){{render(t[0]);}};
        tabWrap.appendChild(btn);
      }});
      var saved='arch';
      try{{saved=localStorage.getItem('sf-tab')||'arch';}}catch(e){{}}
      if(!FEEDS[saved]||!FEEDS[saved].items.length) saved='arch';
      render(saved);
    }})();
    </script>

    <!-- ⑤ Publishing Heatmap -->
    <div class="sidebar-card" id="heatmap-widget">
      <div class="sidebar-title">Publishing activity</div>
      <div id="hm-yr-tabs" style="display:flex;gap:4px;margin-bottom:10px"></div>
      <div>
        <div id="hm-grid" style="display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:3px"></div>
      </div>
      <div id="hm-tip" style="font-size:10.5px;color:var(--text-muted);margin-top:6px;min-height:15px">Hover a month</div>
      <div style="display:flex;align-items:center;gap:4px;margin-top:8px;font-size:10px;color:var(--text-muted)">
        <span>Less</span>
        <span style="width:10px;height:10px;border-radius:2px;background:var(--border);display:inline-block"></span>
        <span style="width:10px;height:10px;border-radius:2px;background:rgba(196,164,132,.25);display:inline-block"></span>
        <span style="width:10px;height:10px;border-radius:2px;background:rgba(196,164,132,.55);display:inline-block"></span>
        <span style="width:10px;height:10px;border-radius:2px;background:var(--orange);display:inline-block"></span>
        <span>More</span>
      </div>
    </div>
    <script>
    (function(){{
      var HM = {heatmap_json};
      var YEARS = {heatmap_years_json};
      var tabWrap = document.getElementById('hm-yr-tabs');
      var grid = document.getElementById('hm-grid');
      var tip = document.getElementById('hm-tip');
      if(!tabWrap||!grid) return;
      function showYear(yr){{
        var data = HM[yr];
        var max = Math.max.apply(null,data.map(function(d){{return d.n;}}));
        grid.innerHTML='';
        data.forEach(function(d){{
          var col=document.createElement('div');
          col.style.cssText='display:flex;flex-direction:column;gap:3px';
          var lbl=document.createElement('div');
          lbl.style.cssText='font-size:8.5px;color:var(--text-muted);text-align:center;margin-bottom:2px;overflow:hidden';
          lbl.textContent=d.m;
          var cell=document.createElement('div');
          var lvl=d.n===0?0:d.n<=max*.25?1:d.n<=max*.6?2:3;
          var bg=['var(--border)','rgba(196,164,132,.25)','rgba(196,164,132,.55)','var(--orange)'][lvl];
          cell.style.cssText='aspect-ratio:1;border-radius:3px;background:'+bg+';cursor:default;transition:transform .1s';
          cell.onmouseenter=function(){{tip.textContent=d.m+' '+yr+' — '+(d.n===0?'no posts':d.n+' post'+(d.n!==1?'s':''));cell.style.transform='scale(1.2)';}};
          cell.onmouseleave=function(){{tip.textContent='Hover a month';cell.style.transform='';}};
          col.appendChild(lbl);col.appendChild(cell);grid.appendChild(col);
        }});
        tabWrap.querySelectorAll('button').forEach(function(b){{
          b.style.background=b.dataset.yr==yr?'var(--orange)':'transparent';
          b.style.color=b.dataset.yr==yr?'#1D2322':'var(--text-muted)';
          b.style.borderColor=b.dataset.yr==yr?'var(--orange)':'var(--border)';
          b.style.fontWeight=b.dataset.yr==yr?'600':'400';
        }});
      }}
      YEARS.forEach(function(yr,i){{
        var btn=document.createElement('button');
        btn.textContent=yr; btn.dataset.yr=yr;
        btn.style.cssText='font-size:10.5px;padding:2px 8px;border-radius:10px;border:1px solid var(--border);cursor:pointer;background:transparent;color:var(--text-muted)';
        btn.onclick=function(){{showYear(yr);}};
        tabWrap.appendChild(btn);
        if(i===0) showYear(yr);
      }});
    }})();
    </script>

    <style>@keyframes sb-pulse{{0%,100%{{opacity:1}}50%{{opacity:.3}}}}</style>
  </aside>
</div>
{FEEDBACK_WIDGET_HTML}
{ASK_WIDGET_HTML}
{back_top_html()}
{footer_html()}
<audio id="beach-audio" loop preload="none"></audio>
<script src="{ASSETS_URL}/hero-media.js?v={JS_VERSION}"></script>
<script src="{ASSETS_URL}/blog.js?v={JS_VERSION}"></script>
<script>
/* hero rotation moved to blog/assets/hero-media.js — see that file */

function toggleBlogAudio(){{
  var audio=document.getElementById('beach-audio');
  var btn=document.getElementById('audio-toggle');
  if(!audio)return;
  if(audio.paused){{
    audio.play().then(function(){{
      if(btn)btn.textContent='🔊';
    }}).catch(function(){{}});
  }}else{{
    audio.pause();
    if(btn)btn.textContent='🎻';
  }}
}}
</script>
</body></html>"""


# ── Build drafts index page ────────────────────────────────────
def build_drafts_page(draft_posts):
    """A small, itself-unlisted page at /blog/drafts/ that just links to
    whatever posts currently have draft: true — a single memorable URL so
    the author doesn't need to remember/type each draft's own slug on every
    device. Not linked from anywhere public (nav, homepage, sitemap) and
    noindex'd, same unlisted principle as the individual draft posts."""
    if draft_posts:
        rows = "\n".join(
            f'<li><a href="/blog/{p["slug"]}/">{escape(p["title"])}</a> '
            f'<span style="color:#6c757d;font-size:0.85rem">— {p["date_fmt"]}</span></li>'
            for p in draft_posts
        )
        body = f'<ul style="line-height:2;">{rows}</ul>'
    else:
        body = '<p style="color:#6c757d;">No drafts pending right now.</p>'

    extra = '<meta name="robots" content="noindex,nofollow"/>'
    return f"""{html_head("Drafts | Jayanth Katta Blog", "Pending draft posts, not publicly listed.", f"{BLOG_URL}/drafts/", extra)}
<body>
{nav_html(show_search=False)}
<main class="post-page-layout">
  <article>
    <header class="post-header">
      <h1>Pending Drafts</h1>
      <p class="post-description">Not linked anywhere public — bookmark this page's URL for a quick way back in.</p>
    </header>
    <div class="post-divider"></div>
    <div class="post-body">{body}</div>
  </article>
</main>
{footer_html()}
</body></html>"""


# ── Main ──────────────────────────────────────────────────────
def build_rss_feed(posts, max_items=None):
    # max_items=None means "all posts" — this feed is also the only source
    # the blog-search RAG indexer reads from (see blog-search/README.md), so
    # capping it silently makes older posts unsearchable, not just absent
    # from a "latest posts" list. The profile README's blog-posts.yml action
    # already applies its own max_post_count limit independently, so there's
    # no downstream reason to truncate here too.
    from email.utils import format_datetime
    from datetime import timezone

    items = []
    for p in posts[:max_items] if max_items else posts:
        link = f"{BLOG_URL}/{p['slug']}/"
        pub_date = format_datetime(p["date"].replace(tzinfo=timezone.utc))
        items.append(f"""    <item>
      <title>{escape(p['title'])}</title>
      <link>{escape(link)}</link>
      <guid>{escape(link)}</guid>
      <pubDate>{pub_date}</pubDate>
      <description>{escape(p['excerpt'])}</description>
    </item>""")

    items_xml = "\n".join(items)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Jayanth Katta — Blog</title>
    <link>{BLOG_URL}/</link>
    <description>AWS Platform Engineering Lab — building one production-grade AWS pattern every week.</description>
{items_xml}
  </channel>
</rss>
"""


def check_branch_is_current():
    """Refuse to run from a checkout that is behind origin/main.

    sync_blog.py regenerates blog/index.html, posts.json, rss.xml, stats.json
    and every post page from whatever is in posts/. Run it from a stale
    checkout and the rebuild omits any post committed since — the post's page
    survives on disk but is unlinked from the index, filter pills, RSS and the
    RAG index, and nothing errors. Two worktrees publish to main, so this is
    reachable in normal use; see "Publishing in parallel" in CLAUDE.md.

    Skipped in CI (fresh checkout at the tip) and when git or the network is
    unavailable. Override locally with --skip-freshness-check.
    """
    import subprocess

    if "--skip-freshness-check" in sys.argv:
        print("  Freshness check skipped (--skip-freshness-check)")
        return
    if os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"):
        return

    def git(*args):
        return subprocess.run(
            ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, timeout=30
        )

    try:
        if git("rev-parse", "--git-dir").returncode != 0:
            return  # not a git checkout
        git("fetch", "--quiet", "origin", "main")
        behind = git("rev-list", "--count", "HEAD..origin/main")
        if behind.returncode != 0:
            return  # no origin/main to compare against
        count = int((behind.stdout or "0").strip() or 0)
    except Exception:
        return  # offline, git missing, timeout — never block on the check

    if count:
        print(
            f"\nERROR: this checkout is {count} commit(s) behind origin/main.\n"
            "\n"
            "Syncing now would regenerate the site index from a stale posts/\n"
            "directory, silently unlinking any post committed since. Rebase\n"
            "first:\n"
            "\n"
            "    git rebase origin/main\n"
            "\n"
            "Then run this again. To bypass (you almost never want to):\n"
            "\n"
            "    python scripts/sync_blog.py --skip-freshness-check\n",
            file=sys.stderr,
        )
        sys.exit(1)


def main():
    check_branch_is_current()

    print("Reading posts from posts/...")
    raw_posts = fetch_local_posts()
    print(f"  {len(raw_posts)} posts found")

    # Architecture Series posts are built outside this script, from
    # _templates/ — load whatever's already committed for them so
    # this script can reuse it verbatim instead of recomputing (and thereby
    # drifting from) their live card text. See fetch_local_posts()'s
    # "externally_built" note for the full story.
    existing_posts_json = {}
    posts_json_path = BLOG_DIR / "posts.json"
    if posts_json_path.exists():
        try:
            for item in json.loads(posts_json_path.read_text(encoding="utf-8")):
                existing_posts_json[item["url"]] = item
        except (json.JSONDecodeError, KeyError):
            pass

    posts = []
    for entry in raw_posts:
        title    = entry["title"]
        url      = entry.get("url", "")
        body_html, embedded_title, embedded_subtitle = clean_html(entry["html"], title)
        plain_text = soup_text(body_html)
        tags     = detect_tags(title + " " + plain_text, entry.get("labels"))
        dt       = parse_date(url, entry.get("published"))
        slug     = entry.get("slug") or slugify(title)
        # Only show a description when there's a genuinely separate embedded
        # subtitle — falling back to the excerpt would just repeat the post's
        # own opening line right below the title.
        description = embedded_subtitle

        summary, takeaway = generate_summary(
            title,
            body_html,
            entry.get("summary"),
            entry.get("takeaway"),
        )

        cached = existing_posts_json.get(f"/blog/{slug}/") if entry.get("externally_built") else None
        if cached:
            title = cached.get("title", title)
            # Always re-derive tags from labels in the source file so the pill
            # counts stay accurate if labels are added or corrected later.
            # Only fall back to cached tags if the source file has no labels.
            if not entry.get("labels"):
                tags = cached["tags"].split(" · ") if cached.get("tags") else tags
            excerpt_text = cached.get("excerpt") or excerpt(body_html)
        else:
            excerpt_text = excerpt(body_html)

        posts.append({
            "slug":          slug,
            "title":         title,
            "display_title": embedded_title or title,
            "url":           url,
            "date":          dt,
            "date_fmt":      dt.strftime("%b %d, %Y").replace(" 0", " "),
            "tags":          tags,
            "read_time":     reading_time(body_html),
            "excerpt":       excerpt_text,
            "description":   description,
            "summary":       summary,
            "takeaway":      takeaway,
            "problem":       entry.get("problem"),
            "builds":        entry.get("builds"),
            "catch":         entry.get("catch"),
            "body_html": body_html,
            "draft":         entry.get("draft", False),
            # Carried through from the front matter so verification_html() can
            # render the accuracy badge. This dict — not the one built during
            # the initial posts/ scan — is what reaches build_post_page().
            "verified":      entry.get("verified"),
            "externally_built": entry.get("externally_built", False),
        })

    posts.sort(key=lambda p: p["date"], reverse=True)

    # Draft mode: a post with `draft: true` in its front matter still gets a
    # real page built at its normal URL (so the author can preview/share the
    # exact link), but is left out of everything that makes a post
    # discoverable — the homepage list, posts.json, stats.json, and rss.xml
    # (which is also what the separate blog-search RAG indexer reads, so
    # drafts are automatically excluded from "Ask my blog" too). Its page
    # also gets a noindex meta tag (see build_post_page) so search engines
    # don't pick it up even if crawled directly. Flip `draft: true` to
    # `draft: false` (or remove the field) and re-run this script to publish
    # it everywhere at once — same one-line toggle every time.
    visible_posts = [p for p in posts if not p.get("draft")]
    for i, post in enumerate(visible_posts):
        post["_prev"] = visible_posts[i + 1] if i + 1 < len(visible_posts) else None
        post["_next"] = visible_posts[i - 1] if i > 0 else None

    draft_count = len(posts) - len(visible_posts)
    externally_built_count = sum(1 for p in posts if p.get("externally_built"))
    own_pages = [p for p in posts if not p.get("externally_built")]
    print(
        f"Building {len(own_pages)} post pages ({draft_count} draft, unlisted; "
        f"{externally_built_count} Architecture Series pages left untouched)..."
    )
    for post in own_pages:
        out_dir = BLOG_DIR / post["slug"]
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "index.html").write_text(
            build_post_page(
                post,
                prev_post=post.get("_prev"),
                next_post=post.get("_next"),
            ),
            encoding="utf-8",
        )

    # ── The index, paginated ──────────────────────────────────
    # Page 1 stays at /blog/ so no existing link breaks; the rest live at
    # /blog/page/N/. Every page carries the full sidebar and filter pills,
    # which are computed from the whole post set rather than the page.
    total_pages = max(1, math.ceil(len(visible_posts) / POSTS_PER_PAGE))
    for page in range(1, total_pages + 1):
        chunk = visible_posts[(page - 1) * POSTS_PER_PAGE: page * POSTS_PER_PAGE]
        html = build_index_page(visible_posts, page_posts=chunk,
                                page=page, total_pages=total_pages)
        if page == 1:
            (BLOG_DIR / "index.html").write_text(html, encoding="utf-8")
        else:
            d = BLOG_DIR / "page" / str(page)
            d.mkdir(parents=True, exist_ok=True)
            (d / "index.html").write_text(html, encoding="utf-8")

    # Stale page directories from a shrinking archive would otherwise linger and
    # keep answering 200 with posts that have moved to another page.
    page_root = BLOG_DIR / "page"
    if page_root.is_dir():
        for d in page_root.iterdir():
            if d.is_dir() and (not d.name.isdigit() or int(d.name) > total_pages):
                shutil.rmtree(d)


    # /blog/drafts/ — unlisted index of currently-pending drafts, so there's
    # one memorable URL instead of needing each draft's own slug on hand.
    draft_posts = [p for p in posts if p.get("draft")]
    drafts_dir = BLOG_DIR / "drafts"
    drafts_dir.mkdir(parents=True, exist_ok=True)
    (drafts_dir / "index.html").write_text(build_drafts_page(draft_posts), encoding="utf-8")

    # posts.json — used by portfolio homepage to render latest posts
    posts_json = [
        {
            "title":   p["title"],
            "url":     f"/blog/{p['slug']}/",
            "date":    p["date"].strftime("%b %d, %Y").replace(" 0", " "),
            "tags":    " · ".join(p["tags"][:2]) if p["tags"] else "",
            "excerpt": p["excerpt"],
            # So the home page can tint these cards the same way the blog does.
            # Without it an Azure post and an AWS post looked identical there,
            # which is the one place a reader sees all three series side by side.
            "cloud":   cloud_class(p["tags"]).strip(),
        }
        for p in visible_posts[:7]
    ]
    (BLOG_DIR / "posts.json").write_text(json.dumps(posts_json, indent=2), encoding="utf-8")

    # stats.json — used by portfolio homepage for the writing streak counter,
    # the writing-section filter pills, and the "currently writing" cards.
    # SERIES/TOP TAGS are emitted so the homepage never hardcodes a taxonomy
    # that drifts every time a new series starts.
    dates = [p["date"] for p in visible_posts]

    def _series_entry(label, short, tag_url, total=None):
        members = [p for p in visible_posts if label in p["tags"]]
        latest = max((p["date"] for p in members), default=None)
        entry = {
            "label": label,
            "short": short,
            "count": len(members),
            "href": "/blog/?tag=" + tag_url,
            "latest_post_date": latest.strftime("%Y-%m-%d") if latest else None,
        }
        if total:
            entry["total"] = total
        return entry

    # The short names name their cloud. "Architecture Series" was unambiguous
    # while there was one; with three it tells a reader nothing, and the pills
    # sit next to each other. Entries with a zero count are dropped below, so a
    # series can be listed here before its first post without showing an empty
    # pill on the home page.
    series = [
        _series_entry("AWS Architecture Series", "AWS Architecture", "aws+architecture+series"),
        _series_entry("Azure Architecture Series", "Azure Architecture", "azure+architecture+series"),
        _series_entry("GCP Architecture Series", "GCP Architecture", "gcp+architecture+series"),
        _series_entry("AWS Weekly Lab", "Weekly Lab", "aws+weekly+lab", total=52),
        _series_entry("AWS Daily Intelligence", "AWS Daily", "aws+daily+intelligence"),
        _series_entry("AWS Weekly Intelligence", "AWS Weekly", "aws+weekly+intelligence"),
    ]

    series_labels = {s["label"] for s in series}
    tag_counts = {}
    for p in visible_posts:
        for t in p["tags"]:
            if t not in series_labels:
                tag_counts[t] = tag_counts.get(t, 0) + 1
    top_tags = [
        {"name": t, "count": c, "href": "/blog/?tag=" + t.lower().replace(" ", "+")}
        for t, c in sorted(tag_counts.items(), key=lambda kv: -kv[1])
    ]

    topic_hits = {}
    for name, (aliases, group) in TOPIC_VOCAB.items():
        n = sum(1 for p in visible_posts
                if name in topics_for(p["title"], p["tags"],
                                      soup_text(p["body_html"])))
        if n:
            topic_hits.setdefault(group, []).append(
                # Link by canonical topic, not by a search for the first alias.
                # The blog filters on the same data topics_for() produced, so
                # the number on the badge is the number the reader sees.
                {"name": name, "count": n,
                 "href": "/blog/?topic=" + quote_plus(name.lower())})

    skills = []
    for group in sorted(topic_hits, key=lambda g: -sum(i["count"] for i in topic_hits[g])):
        items = sorted(topic_hits[group], key=lambda i: -i["count"])[:6]
        skills.append({"group": group, "items": items})

    # AWS services for the homepage, grouped by domain. Same numbers and the
    # same links as the blog sidebar, because both are built from one pass over
    # the posts -- the homepage having its own idea of the counts is exactly
    # the failure "Tools I work with" shipped with, where a badge said 2 and
    # clicking showed none.
    svc_by_post = {}
    for _p in visible_posts:
        _hits = set(count_services(soup_text(_p["body_html"]))) |                 set(count_services(_p["title"]))
        for _h in _hits:
            svc_by_post[_h] = svc_by_post.get(_h, 0) + 1

    svc_groups = {}
    for _name, _n in svc_by_post.items():
        _domain = SERVICE_DOMAIN.get(_name, "Other AWS")
        _desc, _url = SERVICE_INFO.get(_name, ("", ""))
        svc_groups.setdefault(_domain, []).append({
            "name": _name,
            "count": _n,
            "href": "/blog/?service=" + quote_plus(_name.lower()),
            "aws": _url,
            "desc": _desc,
        })
    services_stats = [
        {"group": g, "items": sorted(v, key=lambda i: (-i["count"], i["name"]))}
        # Tie-break on the group name, as the items inside a group already do.
        # Without it two groups on the same total swap places between runs --
        # "AI & ML" and "Apps & Front-end" both sum to 5 -- and every sync
        # produces a 52-line diff in stats.json that changes no data at all.
        for g, v in sorted(svc_groups.items(),
                           key=lambda kv: (-sum(i["count"] for i in kv[1]), kv[0]))
    ]

    # The parts of this work that are not an AWS service -- Terraform, GitOps,
    # Kubernetes, the practices. They belong in the same list: the section is
    # "what I work with", and splitting it into an AWS half and a non-AWS half
    # left the same service showing two different numbers on one page.
    _svc_names = set(SERVICE_DOMAIN) | set(SERVICE_ALIASES)
    _tooling = []
    for _name, (_aliases, _grp) in TOPIC_VOCAB.items():
        if _name in _svc_names or _name in svc_by_post:
            continue
        _n = sum(1 for _p in visible_posts
                 if _name in topics_for(_p["title"], _p["tags"],
                                        soup_text(_p["body_html"])))
        if _n:
            _tooling.append({"name": _name, "count": _n,
                             "href": "/blog/?topic=" + quote_plus(_name.lower()),
                             "aws": "", "desc": ""})
    if _tooling:
        services_stats.append({
            "group": "Tooling & practice",
            "items": sorted(_tooling, key=lambda i: (-i["count"], i["name"])),
        })

    stats_json = {
        "total_posts": len(visible_posts),
        "services": services_stats,
        "services_total": len(svc_by_post),
        "first_post_date": min(dates).strftime("%Y-%m-%d") if dates else None,
        "latest_post_date": max(dates).strftime("%Y-%m-%d") if dates else None,
        "series": [s for s in series if s["count"]],
        "top_tags": top_tags,
        "skills": skills,
    }
    (BLOG_DIR / "stats.json").write_text(json.dumps(stats_json, indent=2), encoding="utf-8")

    # rss.xml — feed for external consumers (e.g. the GitHub profile README's
    # blog-post-workflow action, which needs a feed since the old Blogger one
    # was retired) — and the blog-search RAG indexer, so drafts must stay out
    (BLOG_DIR / "rss.xml").write_text(build_rss_feed(visible_posts), encoding="utf-8")

    # PWA: re-stamp asset tokens on hand-maintained pages, then emit sw.js
    stamp_static_pages()
    write_service_worker()

    print(f"Done — {len(visible_posts)} public posts built at blog/ ({draft_count} draft)")


if __name__ == "__main__":
    main()
