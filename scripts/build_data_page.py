#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build /data/ -- the data platform, measured rather than described.

    python scripts/build_data_page.py

Six stages down the page -- ingest, store, transform, govern, serve, decide --
and for each one what the three clouds actually shipped into it, what the
engines underneath it released, and who in a team owns it.

WHY THIS PAGE EXISTS AND WHY IT IS NOT AN ESSAY
-----------------------------------------------
Every "modern data stack" article is a list of tools someone liked in the
quarter they wrote it, and it is wrong within a year with nothing to say so.
This page carries counts from feeds that refresh themselves, so the shape of
the argument survives the tools changing underneath it.

THREE THINGS THAT WOULD MAKE THIS PAGE LIE
------------------------------------------
1. THE DENOMINATOR. Azure's raw store holds 11,870 rows, of which 9,771 are
   MSRC security bulletins -- Windows and Chromium CVEs that have nothing to
   do with Azure shipping anything. Measuring against that denominator makes
   Azure look like it does almost no data work. This page reads
   intelligence/news.json, the curated store, where Azure is 604 rows, and
   uses share-of-own-output for the same reason /intelligence/services/ does.

2. ONE SERVICE CAN DROWN A STAGE. Looker alone is 259 of GCP's rows in a
   year. Counting raw rows would make "decide" look like a Google speciality
   when it is one product's release-note habit. Counts are rolled up on the
   normalised headline, so a note repeated across versions counts once.

3. ATTENTION IS NOT ADOPTION. A stage with few announcements is a stage the
   vendors are not talking about, which is worth knowing and is not the same
   as a stage nobody uses. Governance is the clearest case and the page says
   so in its own words rather than letting the number imply it.

THE STAGE MAPPING IS EDITORIAL AND MUST STAY VISIBLE AS SUCH
-------------------------------------------------------------
Nothing in the data says Kinesis and Pub/Sub answer the same question. That
is a judgement. It is also the part most likely to rot in silence: a service
rename empties a cell, and an empty cell reads as "this cloud does not do
that". check_data_page.py refuses that.
"""
import collections
import datetime
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

NEWS = os.path.join(ROOT, "intelligence", "news.json")
RELEASES = os.path.join(ROOT, "data", "releases.json")
ECONOMICS = os.path.join(ROOT, "data", "economics.json")
POSTS = os.path.join(ROOT, "posts")
OUT = os.path.join(ROOT, "data", "index.html")

WINDOW_DAYS = 365
CLOUDS = [("aws", "AWS"), ("azure", "Azure"), ("gcp", "Google Cloud")]

# key, title, what it means, who owns it, {cloud: [tagged service names]}
# The service names are the literal tags in intelligence/news.json. They are
# checked, not trusted -- see check_data_page.py.
STAGES = [
    ("ingest", "Ingest", "Getting data out of the systems that produce it and "
     "into somewhere you can work on it &mdash; in batches, or as a stream "
     "that never stops.",
     "Data engineers, mostly. This is the stage that wakes people up.",
     {"aws": ["Kinesis", "Amazon MSK", "Amazon MSK Standard Brokers",
              "Amazon MSK Express Brokers", "Amazon MSK Replicator", "Kafka",
              "DataSync", "Kinesis Video Streams", "DynamoDB Streams",
              "OpenSearch Ingestion", "AWS DMS Schema Conversion",
              "Storage Gateway"],
      "azure": ["Azure Event Hubs", "Azure Database Migration",
                "Azure Storage Mover", "Azure Data Share",
                "Azure Stream Analytics", "Stream Analytics"],
      "gcp": ["Datastream", "Google Cloud Managed Service for Apache Kafka",
              "Pub/Sub", "Storage Transfer Service",
              "Cloud Database Migration Service", "Cloud Data Fusion"]}),

    ("store", "Store", "Where it lands and what it costs to keep. Object "
     "storage for the lake, operational databases for the systems still "
     "running, and increasingly an open table format over the top.",
     "Data engineers and the platform people formerly known as DBAs.",
     {"aws": ["S3", "S3 Tables", "S3 Vectors", "S3 Express", "S3 Files",
              "RDS", "Aurora", "Aurora DSQL", "DynamoDB",
              "DynamoDB Accelerator (DAX)", "Amazon DocumentDB",
              "DocumentDB (with MongoDB compatibility)",
              "Amazon DocumentDB Serverless", "Neptune", "ElastiCache",
              "Amazon Timestream", "Timestream for InfluxDB",
              "Timestream for InfluxDB 3"],
      "azure": ["Azure Blob Storage", "Azure Blob", "Azure Storage",
                "Azure Data Lake Storage", "Azure Disk Storage",
                "Microsoft OneLake", "Azure Database for PostgreSQL",
                "Azure PostgreSQL Flexible Server", "Azure Database for MySQL",
                "Azure SQL Database", "Azure SQL Managed Instance",
                "Azure Arc-enabled SQL Server", "Azure Cosmos DB", "Cosmos DB",
                "Azure DocumentDB", "Azure Managed Redis",
                "Azure Cache for Redis", "Azure Storage Discovery",
                "Azure Storage Actions"],
      "gcp": ["Cloud Storage", "Cloud SQL for MySQL",
              "Cloud SQL for PostgreSQL", "Cloud SQL for SQL Server",
              "AlloyDB for PostgreSQL", "Spanner", "Bigtable",
              "Firestore with MongoDB compatibility",
              "Firestore in Datastore mode", "Memorystore for Valkey",
              "Memorystore for Redis", "Memorystore for Redis Cluster",
              "Oracle Database@Google Cloud", "Database Center"]}),

    ("transform", "Transform", "Turning what arrived into something a person "
     "can answer a question with: joined, de-duplicated, typed, and modelled "
     "into tables that mean something to the business.",
     "Data engineers build the pipelines; analytics engineers own the models.",
     {"aws": ["Glue", "Glue DataBrew", "EMR", "EMR Serverless",
              "Managed Workflows for Apache Airflow"],
      "azure": ["Azure Databricks", "Azure Synapse Link for Azure Cosmos",
                "Azure Data Factory", "Data Factory"],
      "gcp": ["Managed Service for Apache Airflow",
              "Managed Service for Apache Spark", "Dataflow", "Dataform",
              "Dataproc", "Dataproc Metastore", "Google Cloud Dataproc",
              "Google Cloud Composer"]}),


    ("serve", "Serve", "The query engine a person or a dashboard actually "
     "hits. Separating this from storage is the whole lakehouse idea: one "
     "copy of the data, several engines over it.",
     "Data engineers and analytics engineers, with platform teams on the bill.",
     {"aws": ["Redshift", "Athena", "OpenSearch"],  # noqa: E501
      "azure": ["Microsoft Fabric", "Azure AI Search", "Log Analytics"],
      "gcp": ["BigQuery", "Vertex AI Search"]}),

    ("decide", "Decide", "The part that justifies the other five. A dashboard "
     "somebody reads on a Monday, a forecast, a model in production &mdash; "
     "or a decision that gets made the same way it always was.",
     "Data analysts and data scientists, and the people they report to.",
     {"aws": ["QuickSight", "SageMaker"],
      "azure": ["Azure Power Bi Embedded", "Power Bi Embedded"],
      "gcp": ["Looker", "Data Studio", "Looker Studio"]}),
    ("govern", "Govern", "Knowing what you have, where it came from, who may "
     "see it, and whether it is still correct. The stage everyone agrees "
     "matters and nobody budgets for.",
     "Data stewards and governance leads, where those roles exist at all.",
     {"aws": ["Lake Formation", "DataZone", "Clean Rooms"],
      # Microsoft Purview is Azure's answer here and is NOT in the Azure
      # service catalogue, so it cannot be tagged and this cell cannot see
      # it. That is a gap in my tooling, not in Azure, and the page says so.
      "azure": [],
      "gcp": ["Knowledge Catalog", "Sensitive Data Protection", "Dataplex",
              "Data Catalog"]}),
]

# Checks that can actually fail a pipeline, as opposed to data-quality advice.
# Phrased as assertions because that is what they are, and because it is the
# same discipline this repository's own publishing checks run on.
# Six checks, each written as a query that RETURNS ROWS ONLY WHEN IT FAILS.
# That shape is the point: a check that returns a number needs someone to
# decide whether the number is bad, and nobody ever does. ANSI SQL, so they
# read the same on Snowflake, BigQuery, Redshift or Postgres; the interval
# syntax is the one thing that varies by engine.
QUALITY = [
    ("Freshness",
     "The newest row is younger than the interval that is supposed to "
     "produce it.",
     "A feed that stops looks exactly like a quiet week. This is the check "
     "that notices.",
     """SELECT MAX(loaded_at) AS newest
FROM   orders
HAVING MAX(loaded_at) &lt; CURRENT_TIMESTAMP - INTERVAL '2' HOUR;"""),

    ("Row-count delta",
     "Today&rsquo;s load is within a band of the trailing average.",
     "Catches the half-written load and the duplicated one, which are the "
     "two common shapes of a broken job.",
     """WITH daily AS (
  SELECT load_date, COUNT(*) AS n
  FROM   orders GROUP BY load_date
), recent AS (
  SELECT AVG(n) AS avg_n FROM daily
  WHERE  load_date &gt;= CURRENT_DATE - 7
    AND  load_date &lt;  CURRENT_DATE
)
SELECT d.n, r.avg_n
FROM   daily d, recent r
WHERE  d.load_date = CURRENT_DATE
  AND  d.n NOT BETWEEN 0.8 * r.avg_n
                   AND 1.2 * r.avg_n;"""),

    ("Null rate",
     "A column that is never null stays never null.",
     "An upstream rename usually arrives as a column going entirely null "
     "rather than as an error.",
     """SELECT COUNT(*) AS missing_customer_id
FROM   orders
WHERE  load_date = CURRENT_DATE AND customer_id IS NULL
HAVING COUNT(*) &gt; 0;"""),

    ("Referential",
     "Every foreign key resolves.",
     "The join that silently drops rows is a wrong number, not a failed job.",
     """SELECT o.order_id
FROM   orders o
LEFT   JOIN customers c ON c.customer_id = o.customer_id
WHERE  o.load_date = CURRENT_DATE
  AND  c.customer_id IS NULL;"""),

    ("Schema drift",
     "Columns and types are the ones the model expects.",
     "A widened type or a reordered column breaks a consumer downstream, "
     "later, with no trace back to here.",
     """SELECT column_name, data_type
FROM   information_schema.columns
WHERE  table_name = 'orders'
EXCEPT
SELECT column_name, data_type FROM orders_contract;"""),

    ("Distribution",
     "The shape of the data has not moved more than it should.",
     "The only one that catches a correct pipeline carrying wrong data, "
     "which is the failure nobody notices for a quarter.",
     """WITH today AS (
  SELECT AVG(amount) AS a FROM orders WHERE load_date = CURRENT_DATE
), baseline AS (
  SELECT AVG(amount) AS a, STDDEV(amount) AS s FROM orders
  WHERE load_date BETWEEN CURRENT_DATE - 30 AND CURRENT_DATE - 1
)
SELECT today.a AS today_avg, baseline.a AS baseline_avg
FROM today, baseline
WHERE ABS(today.a - baseline.a) &gt; 3 * baseline.s;"""),
]

ROLES = [
    ("Data engineer", "ingest &middot; store &middot; transform",
     "Moves and shapes data, owns the pipelines and whatever wakes up at "
     "3am. Lives in SQL, Python and Spark, and increasingly in Terraform."),
    ("Analytics engineer", "transform &middot; serve",
     "The role that did not exist ten years ago. Owns the models between the "
     "raw tables and the dashboard &mdash; dbt, tests, documentation, "
     "semantics. Closer to software engineering than to analysis."),
    ("Data analyst", "serve &middot; decide",
     "Answers the question that was asked and, usefully, the one that should "
     "have been. SQL and a BI tool, and more influence on decisions than the "
     "org chart suggests."),
    ("Data scientist", "decide",
     "Statistics and modelling where an answer has to be inferred rather "
     "than queried. The part of the field that AI tooling has changed most "
     "in two years."),
    ("Platform engineer / DBA", "store &middot; govern",
     "Still here, under a different title. Capacity, recovery, cost, "
     "security and the question of whether that restore has ever actually "
     "been tested."),
]


def load(path, default=None):
    if not os.path.exists(path):
        return default
    with io.open(path, encoding="utf-8") as f:
        return json.load(f)


def norm(title):
    """Roll up on the normalised headline, so one note repeated counts once."""
    return re.sub(r"[^a-z0-9 ]", " ", (title or "").lower())[:70].strip()


def measure(items, today):
    cut = (today - datetime.timedelta(days=WINDOW_DAYS)).isoformat()
    win = [i for i in items if (i.get("d") or "") >= cut]
    totals = collections.Counter()
    for i in win:
        totals[i.get("c")] += 1

    table, newest, counted = {}, {}, {}
    for key, _t, _m, _r, svc in STAGES:
        for cloud, _label in CLOUDS:
            names = set(svc.get(cloud) or [])
            hits = [i for i in win if i.get("c") == cloud
                    and names & set(i.get("s") or [])]
            rolled = {norm(h.get("t")) for h in hits}
            table[(key, cloud)] = {
                "n": len(rolled),
                "share": 100.0 * len(rolled) / max(1, totals[cloud]),
                "raw": len(hits),
            }
            # Which of the mapped names actually carried anything. The
            # mapping is the editorial judgement this page rests on, and
            # until now it was only visible by reading the source.
            seen = collections.Counter()
            for h in hits:
                for n in (names & set(h.get("s") or [])):
                    seen[n] += 1
            counted[(key, cloud)] = seen
            if hits:
                top = max(hits, key=lambda h: h.get("d") or "")
                newest[(key, cloud)] = top
    return table, newest, counted, totals, cut, len(win)


def format_counts(items, today):
    """Mentions of each open table format, by quarter, across all three feeds.

    The one place a reader can watch an argument being settled in public:
    Iceberg, Delta and Hudi are solving the same problem and the vendors'
    own release notes say which one they are building against.
    """
    FORMATS = [("Iceberg", r"\biceberg\b"), ("Delta Lake", r"\bdelta lake\b"),
               ("Hudi", r"\bhudi\b"), ("Parquet", r"\bparquet\b")]
    cut = (today - datetime.timedelta(days=WINDOW_DAYS)).isoformat()
    out = {}
    for name, pat in FORMATS:
        rx = re.compile(pat, re.I)
        seen = set()
        for i in items:
            d = i.get("d") or ""
            if d < cut:
                continue
            if rx.search((i.get("t") or "") + " " + (i.get("st") or "")):
                seen.add((d[:7], norm(i.get("t"))))
        per = collections.Counter(m for m, _ in seen)
        out[name] = {"total": len(seen), "months": per}
    return out


def dba_posts():
    """His own database-era writing, read from posts/ rather than listed.

    A hand-kept list here would be a second place to update and would go
    stale the first time one is added, which is exactly the failure this
    repository keeps finding in its own pages.
    """
    found = []
    if not os.path.isdir(POSTS):
        return found
    for name in sorted(os.listdir(POSTS)):
        if not name.endswith(".html"):
            continue
        with io.open(os.path.join(POSTS, name), encoding="utf-8") as f:
            head = f.read(2500)
        if "Databases & Ops" not in head:
            continue
        m = re.search(r"^title:\s*(.+)$", head, re.M)
        s = re.search(r"^slug:\s*(.+)$", head, re.M)
        d = re.search(r"^date:\s*'?([0-9-]{10})", head, re.M)
        if not m:
            continue
        title = m.group(1).strip().strip("'\"")
        slug = (s.group(1).strip().strip("'\"") if s
                else os.path.splitext(name)[0])
        found.append({"title": title, "slug": slug,
                      "date": d.group(1) if d else ""})
    found.sort(key=lambda p: p["date"], reverse=True)
    return found


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))

CSS = """
<style>
.dt-wrap { max-width: 1040px; margin: 0 auto; padding: 0 20px 80px; }
.dt-head { padding: 34px 0 10px; }
.dt-head h1 { font-family: var(--serif); font-weight: 600; font-size: 34px;
  line-height: 1.18; margin: 0 0 12px; letter-spacing: -.01em; }
.dt-head .dt-lede { font-size: 17px; line-height: 1.7; color: var(--text);
  max-width: 68ch; margin: 0 0 10px; }
.dt-head .dt-sub { font-size: 14px; line-height: 1.65; color: var(--text-muted);
  max-width: 68ch; margin: 0; }
.dt-hero { margin: 26px 0 8px; padding: 22px 24px 20px;
  border: 1px solid var(--border); border-left: 3px solid var(--accent);
  border-radius: 12px; background: var(--card); }
.dt-hero-kick { margin: 0 0 10px; font-size: 11px; letter-spacing: .1em;
  text-transform: uppercase; color: var(--text-muted); }
.dt-hero-num { margin: 0 0 12px; display: flex; align-items: baseline;
  gap: 14px; font-family: var(--serif); }
.dt-hero-num b { font-size: 60px; line-height: 1; font-weight: 600;
  color: var(--text); letter-spacing: -.02em; }
.dt-hero-num i { font-style: normal; font-family: var(--sans); font-size: 13px;
  letter-spacing: .08em; text-transform: uppercase; color: var(--text-muted); }
.dt-hero-say { margin: 0 0 8px; font-size: 15.5px; line-height: 1.65;
  color: var(--text); max-width: 64ch; }
.dt-hero-say b { font-weight: 600; }
.dt-hero-fine { margin: 0; font-size: 12.5px; line-height: 1.6;
  color: var(--text-muted); max-width: 64ch; }
@media (max-width: 620px) { .dt-hero-num b { font-size: 44px; } }
.dt-sec { margin: 44px 0 0; }
.dt-sec > h2 { font-family: var(--serif); font-weight: 600; font-size: 22px;
  margin: 0 0 6px; }
.dt-fold { border-top: 1px solid var(--border); margin: 0; padding: 18px 0 0; }
.dt-fold + .dt-fold { margin-top: 18px; }
.dt-fold > summary { list-style: none; cursor: pointer; display: flex;
  align-items: center; justify-content: space-between; gap: 14px; }
.dt-fold > summary::-webkit-details-marker { display: none; }
.dt-fold > summary > h2 { margin: 0; }
.dt-chev { flex: none; width: 10px; height: 10px; border-right: 1.6px solid
  var(--text-muted); border-bottom: 1.6px solid var(--text-muted);
  transform: rotate(45deg); transform-origin: center; margin-right: 4px;
  transition: transform .15s ease; }
.dt-fold[open] > summary .dt-chev { transform: rotate(-135deg); }
.dt-fold > summary:hover .dt-chev { border-color: var(--text); }
.dt-fold > *:not(summary):first-of-type { margin-top: 14px; }
.dt-sec > p.dt-note { font-size: 14px; line-height: 1.7;
  color: var(--text-muted); max-width: 72ch; margin: 0 0 16px; }
.dt-stages { display: grid; gap: 12px;
  grid-template-columns: repeat(auto-fit, minmax(290px, 1fr)); }
.dt-stage { border: 1px solid var(--border); border-radius: 10px;
  padding: 15px 16px 14px; background: var(--card); }
.dt-stage h3 { margin: 0 0 3px; font-size: 15px; font-weight: 600; }
.dt-stage .dt-n { font-size: 11px; text-transform: uppercase;
  letter-spacing: .09em; color: var(--text-muted); margin: 0 0 7px; }
.dt-stage p { margin: 0 0 10px; font-size: 13.5px; line-height: 1.6;
  color: var(--text); }
.dt-stage .dt-who { font-size: 12.5px; line-height: 1.55;
  color: var(--text-muted); margin: 0 0 11px; }
.dt-latest { margin: 11px 0 0; padding-top: 10px;
  border-top: 1px solid var(--border); font-size: 12.5px; line-height: 1.55;
  color: var(--text); }
.dt-latest i { font-style: normal; font-size: 10.5px; letter-spacing: .09em;
  text-transform: uppercase; color: var(--text-muted); margin-right: 6px; }
.dt-latest a { color: var(--accent); }
.dt-counted { margin: 6px 0 0; font-size: 11.5px; line-height: 1.5;
  color: var(--text-muted); }
.dt-bars { display: flex; flex-direction: column; gap: 5px; }
.dt-bar { display: grid; grid-template-columns: 74px 1fr 46px; gap: 8px;
  align-items: center; font-size: 11.5px; color: var(--text-muted); }
.dt-bar i { font-style: normal; }
.dt-bar .dt-track { height: 7px; border-radius: 4px; background: var(--border);
  overflow: hidden; }
.dt-bar .dt-fill { display: block; height: 100%; border-radius: 4px; }
.dt-bar b { font-weight: 600; text-align: right; color: var(--text);
  font-variant-numeric: tabular-nums; }
.dt-aws .dt-fill { background: var(--aws); }
.dt-azure .dt-fill { background: var(--azure); }
.dt-gcp .dt-fill { background: var(--gcp); }
.dt-scroll { overflow-x: auto; border: 1px solid var(--border);
  border-radius: 10px; }
table.dt-tbl { width: 100%; border-collapse: collapse; font-size: 13.5px;
  min-width: 620px; }
table.dt-tbl th, table.dt-tbl td { text-align: left; padding: 9px 13px;
  border-bottom: 1px solid var(--border); vertical-align: top; }
table.dt-tbl thead th { font-size: 10.5px; letter-spacing: .08em;
  text-transform: uppercase; color: var(--text-muted); font-weight: 600; }
table.dt-tbl tbody th { font-weight: 600; color: var(--text); }
table.dt-tbl td { color: var(--text-muted); }
table.dt-tbl td.dt-num { text-align: right; font-variant-numeric: tabular-nums;
  color: var(--text); white-space: nowrap; }
table.dt-tbl tr:last-child th, table.dt-tbl tr:last-child td {
  border-bottom: 0; }
.dt-up { color: #3F7A52; } .dt-down { color: #A8503C; }
body.dark .dt-up { color: #86C79A; } body.dark .dt-down { color: #E08C76; }
.dt-fmt { display: flex; flex-direction: column; gap: 7px; margin: 0 0 4px; }
.dt-fmt-row { display: grid; grid-template-columns: 96px 1fr 38px; gap: 10px;
  align-items: center; font-size: 13px; }
.dt-fmt-row .dt-track { height: 10px; border-radius: 5px;
  background: var(--border); overflow: hidden; }
.dt-fmt-row .dt-fill { display: block; height: 100%; background: var(--accent);
  border-radius: 5px; }
.dt-fmt-row b { text-align: right; font-variant-numeric: tabular-nums; }
.dt-diagram { margin: 0 0 18px; }
.dt-diagram img { width: 100%; max-width: 860px; height: auto; display: block; }
.dt-list { list-style: none; padding: 0; margin: 0; display: grid; gap: 9px; }
.dt-list li { border-left: 2px solid var(--border); padding: 1px 0 1px 13px;
  font-size: 13.5px; line-height: 1.65; color: var(--text-muted); }
.dt-list li b { color: var(--text); font-weight: 600; }
.dt-role-at { color: var(--text-muted); font-size: 12px; letter-spacing: .04em; }
.dt-checks { display: grid; gap: 12px;
  grid-template-columns: repeat(auto-fit, minmax(330px, 1fr)); }
.dt-check { border: 1px solid var(--border); border-radius: 10px;
  padding: 14px 15px 12px; background: var(--card); }
.dt-check h3 { margin: 0 0 6px; font-size: 14.5px; font-weight: 600; }
.dt-check .dt-assert { margin: 0 0 5px; font-size: 13.5px; line-height: 1.55;
  color: var(--text); }
.dt-check .dt-catch { margin: 0 0 10px; font-size: 12.5px; line-height: 1.55;
  color: var(--text-muted); }
.dt-check pre { margin: 0; overflow-x: auto; border-radius: 7px;
  background: rgba(0, 0, 0, .22); padding: 10px 12px; }
body.light .dt-check pre { background: rgba(0, 0, 0, .05); }
.dt-check code { font-family: var(--mono); font-size: 11.5px; line-height: 1.6;
  color: var(--text); white-space: pre; }
.dt-gap { border: 1px solid var(--border); border-left: 3px solid var(--accent);
  border-radius: 8px; padding: 13px 15px; font-size: 13.5px; line-height: 1.7;
  color: var(--text-muted); margin: 14px 0 0; }
.dt-gap b { color: var(--text); font-weight: 600; }
.dt-foot { margin: 20px 0 0; font-size: 12.5px; line-height: 1.75;
  color: var(--text-muted); }
.dt-tick { color: var(--text-muted); font-weight: 400; }
@media (max-width: 620px) {
  .dt-head h1 { font-size: 27px; }
  .dt-wrap { padding: 0 16px 60px; }
  .dt-bar { grid-template-columns: 62px 1fr 42px; }
}
</style>
"""


def bars(table, key):
    """One bar per cloud: share of that cloud's own output, scaled to the
    biggest of the three so a thin stage is still readable."""
    out = ['<div class="dt-bars">']
    peak = max(table[(key, c)]["share"] for c, _ in CLOUDS) or 1.0
    for cloud, label in CLOUDS:
        cell = table[(key, cloud)]
        width = 100.0 * cell["share"] / peak
        shown = ("%.1f%%" % cell["share"]) if cell["n"] else "&mdash;"
        # A bar you can only compare is half a chart. The title carries the
        # counts the percentage is derived from, so a reader can find out
        # what is in it without leaving the card.
        tip = ("%s: %d announcements after roll-up (%d before), "
               "%.1f%% of its own output in the window"
               % (label, cell["n"], cell["raw"], cell["share"]))             if cell["n"] else             ("%s: nothing tagged in this window" % label)
        out.append('<div class="dt-bar dt-%s" title="%s"><i>%s</i>'
                   '<span class="dt-track"><span class="dt-fill" '
                   'style="width:%.1f%%"></span></span><b>%s</b></div>'
                   % (cloud, esc(tip), label, width, shown))
    out.append("</div>")
    return "".join(out)


def fold(title, open_=False):
    """A section a reader opens, rather than one they have to scroll past.

    Reported as the page being overwhelming: eight sections, four tables, all
    the same size, nothing saying which to read first. Collapsing deletes
    nothing and makes the page answer one question on arrival instead of
    nine. <details> does it with no script, so it works before the JS lands
    and with JS off.
    """
    return ('<details class="dt-sec dt-fold"%s><summary><h2>%s</h2>'
            '<span class="dt-chev" aria-hidden="true"></span></summary>'
            % (" open" if open_ else "", title))


def build():
    from asset_version import JS_VERSION
    import build_news_page as bnp
    import build_events_page as bep

    today = datetime.date.today()
    news = load(NEWS, {"items": []})
    items = news.get("items", [])
    table, newest, counted, totals, cut, nwin = measure(items, today)
    fmts = format_counts(items, today)
    rel = load(RELEASES, {"releases": [], "sources": [], "no_feed": []})
    eco = load(ECONOMICS, {"firms": [], "private": []})
    posts = dba_posts()

    head = bnp.PAGE[:bnp.PAGE.index("</head>")]
    head = re.sub(r"<title>.*?</title>",
                  "<title>The data platform, measured &mdash; ingest, store, "
                  "transform, govern, serve, decide | Jayanth Katta</title>",
                  head, count=1, flags=re.S)
    head = re.sub(r'<meta name="description" content=".*?">',
                  '<meta name="description" content="Six stages of the data '
                  'lifecycle, what AWS, Azure and Google Cloud actually '
                  'shipped into each one over a year, what the open-source '
                  'engines released, and what the independent data platforms '
                  'earn. Measured, not described.">',
                  head, count=1, flags=re.S)
    head = re.sub(r'<link rel="canonical" href=".*?">',
                  '<link rel="canonical" href="https://jayanthkatta.com/data/">',
                  head, count=1, flags=re.S)
    head = head.replace("__JSV__", JS_VERSION)
    head = head.replace("__RESERVE_WIDE__", "0").replace("__RESERVE__", "0")
    head = re.sub(r"__[A-Z_]+__", "", head)

    nav = bnp.PAGE[bnp.PAGE.index("<nav>"):
                   bnp.PAGE.index("</nav>") + len("</nav>")]
    nav = nav.replace('<li><a href="/intelligence/whats-new/" class="active" '
                      'aria-current="page">What&rsquo;s new</a></li>',
                      '<li><a href="/intelligence/whats-new/">What&rsquo;s '
                      'new</a></li>')
    # This page is the Data section, so its own entry carries the active
    # state -- the same markup every other page uses for its own tab.
    nav = nav.replace('<li><a href="/data/">Data</a></li>',
                      '<li><a href="/data/" class="active" '
                      'aria-current="page">Data</a></li>')

    b = [CSS, '<main class="dt-wrap">']

    b.append('<div class="dt-head">')
    b.append("<h1>The data platform, measured</h1>")
    b.append('<p class="dt-lede">I started as a database administrator '
             "&mdash; Oracle, SQL Server, MariaDB and MongoDB across more "
             "than a hundred production instances &mdash; then moved to "
             "Azure, and then to AWS. The clouds changed. The thing "
             "underneath them did not: somebody still has to get the data "
             "in, keep it, make it mean something, and answer for it when "
             "the number is wrong.</p>")
    b.append('<p class="dt-sub">Six stages of that work, measured against '
             "what the three clouds actually shipped over the last %d days. "
             "Everything with a number refreshes itself; everything that is "
             "my judgement says so.</p>" % WINDOW_DAYS)
    b.append("</div>")

    # One finding, before anything else.
    #
    # Reported as the page being overwhelming -- eight sections all the same
    # size, nothing saying which mattered. A reader arriving at a reference
    # page needs one thing to carry away; the rest is for the reader who
    # decided to stay. Generated from the counts rather than written down,
    # so it cannot quietly stop being true.
    top = sorted(fmts.items(), key=lambda x: -x[1]["total"])
    if top and top[0][1]["total"] > 0:
        lead, rest = top[0], top[1]
        b.append('<div class="dt-hero">')
        b.append('<p class="dt-hero-kick">The finding, from %s announcements '
                 "across all three clouds</p>" % "{:,}".format(nwin))
        b.append('<p class="dt-hero-num"><b>%d</b><i>against</i><b>%d</b></p>'
                 % (lead[1]["total"], rest[1]["total"]))
        b.append('<p class="dt-hero-say">Mentions of <b>%s</b> against '
                 "mentions of <b>%s</b>. Two formats solving the same "
                 "problem &mdash; transactional tables over object storage "
                 "&mdash; and the argument about which one wins is being "
                 "settled in the vendors&rsquo; own release notes while "
                 "everyone else is still having it in meetings.</p>"
                 % (esc(lead[0]), esc(rest[0])))
        b.append('<p class="dt-hero-fine">Vendor attention, not installed '
                 "base. It says what the clouds are building against; it "
                 "does not say what is running in your warehouse.</p>")
        b.append("</div>")

    b.append(fold("The six stages", True))
    b.append('<p class="dt-note">Every data platform does these six things, '
             "whatever it is called this year and whoever sells it. The bars "
             "are each cloud&rsquo;s share of its <em>own</em> announcements "
             "in the window &mdash; not raw counts, which are not "
             "comparable: Google&rsquo;s feed is day-granular and carries "
             "{:,} rows against AWS&rsquo;s {:,}.</p>".format(
                 totals.get("gcp", 0), totals.get("aws", 0)))
    b.append('<div class="dt-diagram"><img src="/blog/assets/diagrams/'
             'data-lifecycle.svg" alt="Diagram: the six stages of a data '
             'platform, ingest, store, transform, serve and decide drawn '
             'left to right, with govern running underneath all of them." '
             'width="860" height="300"></div>')
    b.append('<div class="dt-stages">')
    for n, (key, title, meaning, who, _svc) in enumerate(STAGES, 1):
        b.append('<div class="dt-stage">')
        b.append('<p class="dt-n">Stage %d</p>' % n)
        b.append("<h3>%s</h3>" % title)
        b.append("<p>%s</p>" % meaning)
        b.append('<p class="dt-who">%s</p>' % who)
        b.append(bars(table, key))

        # The most recent thing anyone actually shipped into this stage.
        # A share tells a reader how much attention a stage gets; this tells
        # them what the attention WAS, which is the part worth clicking.
        recent = [(c, newest[(key, c)]) for c, _l in CLOUDS
                  if (key, c) in newest]
        if recent:
            cloud, item = max(recent, key=lambda r: r[1].get("d") or "")
            label = dict(CLOUDS)[cloud]
            title = esc((item.get("t") or "")[:96])
            link = ('<a href="%s" rel="noopener">%s</a>'
                    % (esc(item.get("u") or ""), title)) if item.get("u") \
                else title
            b.append('<p class="dt-latest"><i>Latest</i> %s '
                     '<span class="dt-tick">%s &middot; %s</span></p>'
                     % (link, esc(label), esc(item.get("d") or "")))

        every = collections.Counter()
        for c, _l in CLOUDS:
            every.update(counted.get((key, c)) or {})
        if every:
            top = [n for n, _c in every.most_common(5)]
            more = len(every) - len(top)
            b.append('<p class="dt-counted">Counted from %s%s</p>'
                     % (", ".join(esc(t) for t in top),
                        (" and %d more" % more) if more > 0 else ""))
        b.append("</div>")
    b.append("</div>")
    b.append('<div class="dt-gap"><b>Two cells are blank, and they mean '
             "different things.</b> Azure is blank under govern because "
             "Microsoft Purview is not in the Azure service catalogue this "
             "site tags against, so no announcement about it can be counted "
             "&mdash; a gap in my tooling, not in Azure. Azure is blank "
             "under decide because Power BI Embedded, which <em>is</em> in "
             "the catalogue, had no announcement in the window. A measured "
             "zero and an inability to measure are different claims, and "
             "printing both as &ldquo;0&rdquo; would make them look like "
             "one.</div>")
    b.append("</details>")

    ranked = sorted(fmts.items(), key=lambda x: -x[1]["total"])
    peak = max(v["total"] for _, v in ranked) or 1
    b.append(fold("The format question, being answered in public", True))
    b.append('<p class="dt-note">Iceberg, Delta Lake and Hudi solve the same '
             "problem: transactional tables over object storage, so several "
             "engines can read one copy without trampling each other. Which "
             "one wins is usually argued about. It can also just be counted "
             "&mdash; mentions across all three clouds&rsquo; own "
             "announcements in the window, rolled up so a repeated note "
             "counts once.</p>")
    b.append('<div class="dt-fmt">')
    for name, v in ranked:
        b.append('<div class="dt-fmt-row"><i>%s</i><span class="dt-track">'
                 '<span class="dt-fill" style="width:%.1f%%"></span></span>'
                 "<b>%d</b></div>"
                 % (esc(name), 100.0 * v["total"] / peak, v["total"]))
    b.append("</div>")
    b.append('<p class="dt-foot">Vendor attention, not installed base. It '
             "says what the clouds are building against; it does not say "
             "what is running in your warehouse.</p>")
    b.append("</details>")

    by_vendor = collections.Counter()
    latest, kinds = {}, {}
    for r in rel.get("releases", []):
        by_vendor[r["vendor"]] += 1
        kinds[r["vendor"]] = r["kind"]
        if r["date"] > latest.get(r["vendor"], {"date": ""})["date"]:
            latest[r["vendor"]] = r
    b.append(fold("What the engines shipped"))
    b.append('<p class="dt-note">The clouds rent you a platform; these are '
             "the parts it is built out of. A tagged release is a fact with "
             "a date, which is why this reads release feeds rather than "
             "company blogs wherever a project publishes them. Release "
             "candidates and nightly build tags are excluded &mdash; "
             "counting those makes a project&rsquo;s cadence a measure of "
             "how publicly it tests.</p>")
    b.append('<div class="dt-scroll"><table class="dt-tbl"><thead><tr>'
             "<th>Project</th><th>Stage</th><th>Held</th>"
             "<th>Most recent</th></tr></thead><tbody>")
    stage_title = dict((k, t) for k, t, _m, _w, _s in STAGES)
    # Releases first, then blogs. Sorting on count alone puts MongoDB's
    # 150 blog posts above Iceberg's 3 tagged releases, which argues the
    # opposite of what this section says about why releases are read.
    def rank(item):
        vendor, n = item
        return (0 if kinds.get(vendor) == "release" else 1, -n)

    for vendor, n in sorted(by_vendor.items(), key=rank):
        r = latest[vendor]
        tag = "" if kinds.get(vendor) == "release" else " <em>(blog)</em>"
        link = ('<a href="%s" rel="noopener">%s</a>'
                % (esc(r["url"]), esc(r["title"][:62]))) if r.get("url") \
            else esc(r["title"][:62])
        b.append('<tr><th>%s%s</th><td>%s</td><td class="dt-num">%d</td>'
                 '<td>%s <span class="dt-tick">&middot; %s</span></td></tr>'
                 % (esc(vendor), tag, esc(stage_title.get(r["layer"],
                                                          r["layer"])),
                    n, link, esc(r["date"])))
    b.append("</tbody></table></div>")
    gaps = rel.get("no_feed") or []
    if gaps:
        b.append('<div class="dt-gap"><b>Two names are missing on purpose.'
                 "</b> " + " ".join("%s &mdash; %s." % (esc(g["vendor"]),
                                                        esc(g["why"]))
                                    for g in gaps)
                 + " They are named rather than dropped, because a vendor "
                 "absent from a table reads as a vendor doing nothing.</div>")
    b.append("</details>")

    b.append(fold("What the independents earn"))
    b.append('<p class="dt-note">Total company revenue for the most recent '
             "quarter each firm has filed, read from its own 10-Q or 10-K at "
             "the SEC. Not a data-platform segment &mdash; none of them "
             "break one out, and inventing a split would be the error that "
             "makes a page like this worthless.</p>")
    b.append('<div class="dt-scroll"><table class="dt-tbl"><thead><tr>'
             "<th>Firm</th><th>What the revenue covers</th><th>Quarter</th>"
             "<th>Revenue</th><th>Year on year</th></tr></thead><tbody>")
    for f in eco.get("firms", []):
        yoy = f.get("yoy_pct")
        shown = "&mdash;"
        if yoy is not None:
            shown = ('<span class="%s">%+.0f%%</span>'
                     % ("dt-up" if yoy >= 0 else "dt-down", yoy))
        b.append('<tr><th>%s <span class="dt-tick">%s</span></th><td>%s</td>'
                 '<td class="dt-num">%s</td><td class="dt-num">$%.2fB</td>'
                 '<td class="dt-num">%s</td></tr>'
                 % (esc(f["name"]), esc(f["ticker"]), esc(f["covers"]),
                    esc(f["quarter_end"]), f["revenue_usd"] / 1e9, shown))
    for p in eco.get("private", []):
        last = "&mdash;"
        if p.get("last_quarter_end"):
            last = ("$%.2fB at %s" % (p["last_revenue_usd"] / 1e9,
                                      p["last_quarter_end"]))
        b.append('<tr><th>%s</th><td>%s</td><td class="dt-num">&mdash;</td>'
                 '<td class="dt-num">%s</td><td class="dt-num">&mdash;</td>'
                 "</tr>" % (esc(p["name"]), esc(p["why"]), last))
    b.append("</tbody></table></div>")
    b.append('<div class="dt-gap">The row worth sitting with is '
             "<b>Teradata</b>, and it is here precisely because it is "
             "shrinking. A table that printed only the firms going up would "
             "be making its argument by choosing the rows.</div>")
    b.append("</details>")

    b.append(fold("Who does what"))
    b.append('<p class="dt-note">Editorial, and the titles vary by company. '
             "What does not vary is the work, which is why the stages come "
             "first and the titles hang off them.</p>")
    b.append('<ul class="dt-list">')
    for title, stages, what in ROLES:
        b.append('<li><b>%s</b> <span class="dt-role-at">&mdash; %s</span>'
                 "<br>%s</li>" % (esc(title), stages, what))
    b.append("</ul></details>")

    b.append(fold("Data quality, as checks that can fail"))
    b.append('<p class="dt-note">&ldquo;Ensure data quality&rdquo; is not a '
             "plan. These six are, because each is an assertion a pipeline "
             "can run and stop on. Same discipline this site&rsquo;s own "
             "publishing checks use: a check that cannot fail is worse than "
             "no check.</p>")
    b.append('<div class="dt-checks">')
    for name, assertion, catches, sql in QUALITY:
        b.append('<div class="dt-check">'
                 "<h3>%s</h3>"
                 '<p class="dt-assert">%s</p>'
                 '<p class="dt-catch">%s</p>'
                 "<pre><code>%s</code></pre>"
                 "</div>" % (esc(name), assertion, catches, sql))
    b.append("</div>")
    b.append('<p class="dt-foot">Each one returns rows <em>only when it '
             "fails</em>, which is the whole design: a check that returns a "
             "number needs somebody to decide whether the number is bad, and "
             "nobody ever does. ANSI SQL &mdash; they read the same on "
             "Snowflake, BigQuery, Redshift or Postgres, and the interval "
             "syntax is the one thing your engine will argue with.</p>")
    b.append("</details>")

    if posts:
        b.append(fold("Before any of this was a platform"))
        b.append('<p class="dt-note">The database writing on this site, from '
                 "the years when the storage layer was a machine you could "
                 "walk up to. Read out of the archive, not a list I keep by "
                 "hand.</p>")
        b.append('<ul class="dt-list">')
        for p in posts:
            when = (' <span class="dt-tick">&middot; %s</span>' % p["date"]) \
                if p["date"] else ""
            b.append('<li><b><a href="/blog/%s/">%s</a></b>%s</li>'
                     % (esc(p["slug"]), esc(p["title"]), when))
        b.append("</ul></details>")

    ok = [s for s in rel.get("sources", []) if s.get("status") == "ok"]
    b.append(fold("Where every number here came from"))
    b.append('<div class="dt-scroll"><table class="dt-tbl"><thead><tr>'
             "<th>Section</th><th>Source</th><th>Refreshed</th></tr></thead>"
             "<tbody>")
    for what, src, when in [
        ("The six stages, the format question",
         "The three clouds&rsquo; own announcement feeds, held in this "
         "site&rsquo;s store &mdash; {:,} rows in the window".format(nwin),
         "three times a day"),
        ("What the engines shipped",
         "{} release and blog feeds, {:,} items held".format(
             len(ok), len(rel.get("releases", []))),
         "weekly, Mondays"),
        ("What the independents earn",
         "SEC EDGAR company facts (XBRL) &mdash; each firm&rsquo;s own "
         "10-Q or 10-K", "weekly"),
        ("The stage mapping, the roles, the quality checks",
         "Mine. Editorial, and checked by <code>check_data_page.py</code> "
         "on every push", "when I change it"),
    ]:
        b.append("<tr><th>%s</th><td>%s</td><td>%s</td></tr>"
                 % (what, src, when))
    b.append("</tbody></table></div>")
    b.append('<p class="dt-foot">Window %s to %s. Cloud announcements are '
             "counted as a share of each cloud&rsquo;s own output and rolled "
             "up on the normalised headline, so one note repeated counts "
             "once. What this method cannot see is written down in "
             "<code>scripts/build_data_page.py</code>.</p>"
             % (cut, today.isoformat()))
    b.append("</details>")
    b.append("</main>")

    doc = (head + "</head>\n<body>\n" + nav + "\n" + "\n".join(b)
           + bep.tail_html(JS_VERSION, page_id="data"))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8") as f:
        f.write(doc)
    print("wrote %s (%d bytes)" % (os.path.relpath(OUT, ROOT), len(doc)))
    print("window %s..%s  %d rows | %d engine items | %d firms | %d posts"
          % (cut, today, nwin, len(rel.get("releases", [])),
             len(eco.get("firms", [])), len(posts)))


if __name__ == "__main__":
    build()
