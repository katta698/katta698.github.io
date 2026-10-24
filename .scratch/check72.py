import urllib.request, re, html, sys, time

def page_text(url):
    last = None
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            raw = urllib.request.urlopen(req, timeout=180).read().decode("utf-8", "replace")
            break
        except Exception as e:
            last = e
            print("  retry %d for %s (%s)" % (attempt + 1, url, type(e).__name__))
            time.sleep(2 ** attempt)
    else:
        raise last
    t = re.sub(r"(?is)<(script|style|svg)[^>]*>.*?</\1>", " ", raw)
    t = re.sub(r"(?s)<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", html.unescape(t))

A = "https://docs.cloud.google.com/firewall/docs/firewalls"
B = "https://docs.cloud.google.com/firewall/docs/quotas"

CLAIMS = [
    # What a target is
    (A, "Targets identify the network interfaces of instances to which the firewall rule applies"),
    (A, "The target parameter identifies the network interfaces of the Compute Engine instances, including GKE nodes and App Engine flexible environment instances"),
    (A, "When you omit a target specification, the firewall rule applies to all instances in the VPC network"),
    (A, "The firewall rule only applies to instances with network interfaces in the firewall rule's VPC network if the instances have a network tag that matches at least one of the firewall rule's target network tags"),
    (A, "The firewall rule only applies to instances with network interfaces in the firewall rule's VPC network if the instances use a service account that matches at least one of the firewall rule's target service accounts"),
    # The security argument
    (A, "If you need strict control over how firewall rules are applied to VMs, use target service accounts and source service accounts instead of target network tags and source network tags"),
    (A, "A network tag is an arbitrary attribute"),
    (A, "One or more network tags can be associated with an instance by any Identity and Access Management (IAM) principal who has permission to edit it"),
    (A, "IAM principals with the Compute Engine Instance Admin role to a project have this permission"),
    (A, "IAM principals who can edit an instance can change its network tags, which could change the set of applicable firewall rules for that instance"),
    (A, "A service account represents an identity associated with an instance"),
    (A, "Only one service account can be associated with an instance"),
    (A, "You control access to the service account by controlling the grant of the Service Account User role for other IAM principals"),
    (A, "For an IAM principal to start an instance by using a service account, that principal must have the Service Account User role to at least use that service account and appropriate permissions to create instances"),
    # The no-mixing rule
    (A, "You cannot mix and match service accounts and network tags in any firewall rule"),
    (A, "You cannot use target service accounts and target network tags together in any firewall rule (ingress or egress)"),
    (A, "If you specify targets by target network tag or target service account, the following are invalid sources for ingress firewall rules"),
    (A, "Combination of source IP ranges and source service accounts"),
    (A, "Combination of source IP ranges and source network tags"),
    # Operational considerations
    (A, "Changing a service account for an instance requires stopping and restarting it"),
    (A, "Adding or removing network tags can be done while the instance is running"),
    (A, "If you identify instances by network tag, the firewall rule applies to the primary internal IP address of the instance"),
    (A, "Service account firewall rules apply to the GKE node, not the GKE Pod"),
    # Sources for ingress rules
    (A, "Other instances in your VPC network identified by network tags"),
    (A, "Other instances in your VPC network identified by service account"),
    (A, "Other instances in your VPC network identified by range of IPv4 or IPv6 address and by network tag"),
    (A, "Other instances in your VPC network identified by range of IPv4 or IPv6 addresses and by service account"),
    (A, "The default source is any IPv4 address ( 0.0.0.0/0 )"),
    # Permissions
    (A, "compute.firewalls.create"),
    (A, "Compute Security Admin role ( roles/compute.securityAdmin )"),
    (A, "Compute Network Viewer role ( roles/compute.networkViewer )"),
    # Limits
    (B, "Maximum number of source network tags per ingress VPC firewall rule 30"),
    (B, "Maximum number of target network tags per VPC firewall rule 70"),
    (B, "Maximum number of source service accounts per ingress VPC firewall rule 10"),
    (B, "Maximum number of target service accounts per firewall rule 10"),
    (B, "This limit cannot be increased"),
    (B, "Maximum number of source secure tags per ingress firewall policy rule 256"),
    (B, "Maximum number of target secure tags per firewall policy rule 256"),
]

cache = {}
fails = []
for url, claim in CLAIMS:
    if url not in cache:
        cache[url] = page_text(url)
        print("FETCHED %s  (%d chars)" % (url, len(cache[url])))
    ok = claim in cache[url]
    if not ok:
        fails.append(claim)
    print("%s  %s" % ("ok  " if ok else "FAIL", claim[:100]))

print("\n%d claims, %d failures" % (len(CLAIMS), len(fails)))
for f in fails:
    print("  FAILED: " + f)
sys.exit(1 if fails else 0)
