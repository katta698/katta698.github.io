"""
Sync blog: fetch from Blogger → clean → build static pages at blog/
Run locally or via GitHub Actions (nightly cron).

Usage:
  python scripts/sync_blog.py
"""

import json
import math
import os
import re
import sys
from datetime import datetime
from html import escape
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ── Paths (relative to repo root) ─────────────────────────────
REPO_ROOT   = Path(__file__).parent.parent
BLOG_DIR    = REPO_ROOT / "blog"
ASSETS_URL  = "/blog/assets"

# ── Blogger config ────────────────────────────────────────────
FEED_BASE   = "https://blog.jayanthkatta.com/feeds/posts/default"
SITE_URL    = "https://jayanthkatta.com"
BLOG_URL    = f"{SITE_URL}/blog"
DISQUS_ID   = "jayanthkatta"
API_URL     = "https://37arp5b92a.execute-api.us-east-1.amazonaws.com/search"

# ── AWS service names to detect in post content ───────────────
AWS_SERVICES = [
    "EC2","S3","IAM","VPC","RDS","EKS","ECS","Lambda","CloudWatch",
    "CloudFront","Route 53","ALB","NLB","SSM","Glue","Step Functions",
    "DynamoDB","SQS","SNS","Kinesis","Redshift","EMR","Athena",
    "Secrets Manager","KMS","WAF","Shield","GuardDuty","Config",
    "Organizations","Control Tower","Transit Gateway","NAT Gateway",
    "Internet Gateway","Auto Scaling","Elastic Beanstalk","CodePipeline",
    "CodeBuild","CodeDeploy","ECR","Fargate","API Gateway","EventBridge",
]

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

# ── ChatGPT CodeMirror markers ────────────────────────────────
CHATGPT_MARKERS = [
    "q9tKkq_viewer", "cm-editor", "lxnfua_", "cm-scroller",
    "cm-content", "q9tKkq_readonly", "border-token-border-light",
    "ͼd", "ͼr", "ͼm", "ͼg",
]

# ── Tag detection ─────────────────────────────────────────────
TAG_RULES = [
    ("AI",         ["rag", "bedrock", "llm", "amazon nova", "titan embed",
                    "vector embed", "semantic search"]),
    ("Kubernetes", ["kubernetes", "k8s", "helm", "kubectl", "pod manifest",
                    "namespace", "eks cluster"]),
    ("GitOps",     ["gitops", "argocd", "flux", "git ops", "drift detection"]),
    ("Terraform",  ["terraform", "hcl", "tfstate", "workspace", "terraform module",
                    "terraform import", "terraform cloud"]),
    ("AWS",        ["aws", "ec2", "s3 bucket", "rds mysql", "iam role", "lambda",
                    "cloudwatch", "cloudfront", "route 53", "vpc", "beanstalk",
                    "ssm", "glue", "fleet intelligence", "servicenow", "eks"]),
    ("Health",     ["sugar", "wheat", "longevity", "turning 40", "diet ",
                    "refined carbs", "i reduced"]),
    ("Career",     ["platform engineer", "enterprise platform", "self-service",
                    "ticket to ec2", "postgresql provisioning"]),
    ("Life",       ["daughter", "my child", "patience", "quiet promise",
                    "the conversations", "i stopped competing", "beautiful"]),
    ("Tech",       ["oracle", "mariadb", "mongodb", "azure log", "ansible",
                    "studio 3t", "asm integrity", "lock tables"]),
]
MAX_TAGS = 3
CATEGORY_ORDER = ["All", "AWS", "Terraform", "Kubernetes", "GitOps", "AI", "Tech", "Career", "Health", "Life"]

NAV_SVG = """<svg width="30" height="30" viewBox="0 0 80 80" xmlns="http://www.w3.org/2000/svg">
  <rect width="80" height="80" rx="16" fill="#0f1923"/>
  <text x="36" y="52" font-family="monospace" font-size="36" font-weight="700" fill="#FF9900" text-anchor="middle">J</text>
  <polygon points="54,12 46,28 52,28 44,44" fill="#FF9900" opacity="0.9"/>
</svg>"""


# ── Blogger fetch ─────────────────────────────────────────────
def fetch_all_posts():
    posts = []
    url = f"{FEED_BASE}?alt=json&max-results=50"
    while url:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        feed = data.get("feed", {})
        for entry in feed.get("entry", []):
            link = next(
                (l["href"] for l in entry.get("link", []) if l.get("rel") == "alternate"), None
            )
            title = entry.get("title", {}).get("$t", "Untitled")
            content_html = entry.get("content", {}).get("$t", "")
            posts.append({"title": title, "url": link, "html": content_html})
        next_link = next(
            (l["href"] for l in feed.get("link", []) if l.get("rel") == "next"), None
        )
        url = next_link
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


def clean_html(html):
    soup = BeautifulSoup(html, "html.parser")
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
    for tag in soup.find_all(["h2", "h3", "p"]):
        if tag.get("style"):
            del tag["style"]
    for code in soup.find_all("code"):
        for span in code.find_all("span"):
            span.unwrap()
        for br in code.find_all("br"):
            br.replace_with("\n")
    return str(soup)


# ── Post metadata helpers ─────────────────────────────────────
def detect_tags(text):
    text_lower = text.lower()
    tags = []
    for tag, keywords in TAG_RULES:
        if any(kw in text_lower for kw in keywords):
            tags.append(tag)
    return (tags or ["Tech"])[:MAX_TAGS]


def reading_time(html):
    text = BeautifulSoup(html, "html.parser").get_text()
    return max(1, math.ceil(len(text.split()) / 200))


def excerpt(html, max_chars=160):
    soup = BeautifulSoup(html, "html.parser")
    for p in soup.find_all("p"):
        txt = p.get_text(strip=True)
        if len(txt) > 30:
            return txt[:max_chars].rstrip() + ("…" if len(txt) > max_chars else "")
    text = soup.get_text(" ", strip=True)
    return text[:max_chars].rstrip() + "…"


def parse_date(url):
    m = re.search(r"/(\d{4})/(\d{2})/", url or "")
    if m:
        return datetime(int(m.group(1)), int(m.group(2)), 1)
    return datetime(2024, 1, 1)


def slugify(title):
    s = re.sub(r"[^a-z0-9]+", "-", title.lower())
    return s.strip("-")[:60]


# ── HTML templates ────────────────────────────────────────────
def html_head(title, description, canonical, extra=""):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{escape(title)}</title>
<meta name="description" content="{escape(description)}"/>
<link rel="canonical" href="{canonical}"/>
<link rel="icon" href="/favicon.svg" type="image/svg+xml"/>
<link rel="stylesheet" href="{ASSETS_URL}/blog.css"/>
{extra}
</head>"""


def nav_html():
    return f"""<nav class="nav">
  <a class="nav-logo" href="/blog/">{NAV_SVG}<span>Jayanth Katta</span></a>
  <div class="nav-spacer"></div>
  <ul class="nav-links">
    <li><a href="/">Home</a></li>
    <li><a href="/blog/" class="active">Blog</a></li>
    <li><a href="/resume.html">Resume</a></li>
  </ul>
  <button class="nav-icon-btn" id="nav-search-btn" aria-label="Search" title="Search posts">
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
  </button>
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
  <p>&copy; {datetime.now().year} Jayanth Katta &mdash; <a href="{SITE_URL}">jayanthkatta.com</a></p>
</footer>"""


def back_top_html():
    return '<button class="back-top" id="back-top" aria-label="Back to top">↑</button>'


# ── Build individual post page ────────────────────────────────
def build_post_page(post, prev_post, next_post):
    slug     = post["slug"]
    title    = post["title"]
    tags     = post["tags"]
    post_url = f"{BLOG_URL}/{slug}/"

    tags_html = " ".join(f'<span class="tag-badge">{t}</span>' for t in tags)

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

    return f"""{html_head(title + " | Jayanth Katta Blog", post["excerpt"], post_url, extra)}
<body>
{nav_html()}
<main class="post-page-layout">
  <div class="post-breadcrumb">
    <a href="/">Home</a><span class="post-breadcrumb-sep">›</span>
    <a href="/blog/">Blog</a><span class="post-breadcrumb-sep">›</span>
    <span>{escape(title[:50])}{"…" if len(title)>50 else ""}</span>
  </div>
  <article>
    <header class="post-header">
      <div class="post-header-meta">{tags_html}</div>
      <h1>{escape(title)}</h1>
      <div class="post-info">
        <span>{post["date_fmt"]}</span>
        <span class="post-info-dot"></span>
        <span>{post["read_time"]} min read</span>
        <span class="post-info-dot"></span>
        <a href="https://blog.jayanthkatta.com" target="_blank" rel="noopener" style="color:inherit;opacity:.6;font-size:.72rem;">Originally on Blogger</a>
      </div>
    </header>
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
{back_top_html()}
{footer_html()}
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
<script src="{ASSETS_URL}/blog.js"></script>
<script>
  hljs.highlightAll();
</script>
</body></html>"""


# ── Build index page ──────────────────────────────────────────
def build_index_page(posts):
    tag_counts = {}
    for p in posts:
        for t in p["tags"]:
            tag_counts[t] = tag_counts.get(t, 0) + 1

    cats = [c for c in CATEGORY_ORDER if c == "All" or tag_counts.get(c, 0) > 0]

    filter_pills = "\n".join(
        f'<button class="filter-pill {"active" if c=="All" else ""}" data-tag="{c.lower()}">'
        f'{c}{" ("+str(tag_counts.get(c,0))+")" if c!="All" else " ("+str(len(posts))+")"}'
        f'</button>'
        for c in cats
    )

    total_posts = len(posts)
    total_mins  = sum(p["read_time"] for p in posts)
    unique_tags = len([c for c in CATEGORY_ORDER if tag_counts.get(c, 0) > 0])

    cards_html = []
    for p in posts:
        tag1 = p["tags"][0] if p["tags"] else "Tech"
        tags_data = " ".join(p["tags"]).lower()
        cards_html.append(
            f'<a href="/blog/{p["slug"]}/" class="post-card"'
            f' data-title="{escape(p["title"])}"'
            f' data-excerpt="{escape(p["excerpt"])}"'
            f' data-tags="{escape(tags_data)}">'
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

    # ── AWS service mention counts ─────────────────────────────
    service_counts = {}
    for p in posts:
        text = BeautifulSoup(p["body_html"], "html.parser").get_text().lower()
        for svc in AWS_SERVICES:
            count = text.count(svc.lower())
            if count:
                service_counts[svc] = service_counts.get(svc, 0) + count
    top_services = sorted(service_counts.items(), key=lambda x: x[1], reverse=True)[:20]
    services_json = json.dumps([{"name": s, "count": c} for s, c in top_services])

    # ── Blog-extracted quiz questions ──────────────────────────
    blog_questions = []
    for p in posts[:15]:
        text = BeautifulSoup(p["body_html"], "html.parser").get_text()
        for svc in AWS_SERVICES:
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
{nav_html()}
<section class="hero">
  <span class="hero-eyebrow">Engineering &amp; Life</span>
  <h1>Jayanth's Blog</h1>
  <p class="hero-sub">Thoughts on AWS, Terraform, Kubernetes, platform engineering, and the quieter things in life.</p>
  <div class="hero-stats">
    <div class="hero-stat"><span class="hero-stat-n">{total_posts}</span><span class="hero-stat-l">Posts</span></div>
    <div class="hero-stat"><span class="hero-stat-n">{unique_tags}</span><span class="hero-stat-l">Topics</span></div>
    <div class="hero-stat"><span class="hero-stat-n">{total_mins}</span><span class="hero-stat-l">Min of reading</span></div>
  </div>
</section>
<div class="search-bar-wrap" id="search-bar-wrap">
  <div class="search-bar-glow"></div>
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
    <div class="posts-grid" id="posts-grid">
      {"".join(cards_html)}
      <div class="empty-state" id="empty-state" style="display:none">
        <h3>No posts found</h3><p>Try a different search term or topic filter.</p>
      </div>
    </div>
  </div>
  <aside class="sidebar">
    <div class="sidebar-card">
      <div class="sidebar-title">Stats</div>
      <div class="sidebar-stats">
        <div class="sb-stat"><span class="sb-stat-n">{total_posts}</span><span class="sb-stat-l">Posts</span></div>
        <div class="sb-stat"><span class="sb-stat-n">{unique_tags}</span><span class="sb-stat-l">Topics</span></div>
        <div class="sb-stat"><span class="sb-stat-n">{total_mins}</span><span class="sb-stat-l">Min</span></div>
        <div class="sb-stat"><span class="sb-stat-n">{posts[0]["date_fmt"] if posts else ""}</span><span class="sb-stat-l">Latest</span></div>
      </div>
    </div>
    <div class="sidebar-card" id="services-widget">
      <div class="sidebar-title">AWS services across all posts</div>
      <div id="svc-bubble-area" style="position:relative;height:220px;width:100%"></div>
      <div style="display:flex;gap:10px;margin-top:10px;padding-top:10px;border-top:0.5px solid var(--border)">
        <span style="font-size:11px;color:var(--text-muted);display:flex;align-items:center;gap:4px"><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:var(--orange);opacity:.9"></span>high</span>
        <span style="font-size:11px;color:var(--text-muted);display:flex;align-items:center;gap:4px"><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:var(--orange);opacity:.45"></span>medium</span>
        <span style="font-size:11px;color:var(--text-muted);display:flex;align-items:center;gap:4px"><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:var(--orange);opacity:.2"></span>low</span>
      </div>
    </div>
    <div class="sidebar-card" id="quiz-widget">
      <div class="sidebar-title" style="display:flex;justify-content:space-between;align-items:center">
        <span>AWS quiz</span>
        <span id="quiz-score" style="font-size:11px;color:var(--orange);font-weight:500"></span>
      </div>
      <div id="quiz-badge" style="display:inline-block;font-size:11px;padding:2px 10px;border-radius:20px;background:rgba(255,153,0,.12);color:#854F0B;margin-bottom:10px"></div>
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
    (function(){{
      var SERVICES = {services_json};
      var area = document.getElementById('svc-bubble-area');
      if(!area) return;
      var W = area.offsetWidth || 240, H = 220;
      var maxC = Math.max.apply(null, SERVICES.map(function(s){{return s.count;}}));
      var placed = [];
      function overlap(a,b){{var dx=a.x-b.x,dy=a.y-b.y;return Math.sqrt(dx*dx+dy*dy)<a.r+b.r+3;}}
      SERVICES.slice().sort(function(a,b){{return b.count-a.count;}}).forEach(function(s){{
        var r = 14 + (s.count/maxC)*28;
        var tries=0,x,y;
        do{{x=r+Math.random()*(W-2*r);y=r+Math.random()*(H-2*r);s.x=x;s.y=y;s.r=r;tries++;}}
        while(tries<400 && placed.some(function(p){{return overlap(s,p);}}));
        placed.push({{x:s.x,y:s.y,r:r}});
        var opacity = 0.15+(s.count/maxC)*0.8;
        var textColor = opacity>0.5?'#412402':'#854F0B';
        var fs = r>32?12:r>22?10:9;
        var div=document.createElement('div');
        div.title=s.name+': ~'+s.count+' mentions';
        div.style.cssText='position:absolute;left:'+(x-r)+'px;top:'+(y-r)+'px;width:'+(r*2)+'px;height:'+(r*2)+'px;border-radius:50%;background:rgba(255,153,0,'+opacity+');display:flex;align-items:center;justify-content:center;text-align:center;cursor:default;transition:transform .15s';
        div.innerHTML='<span style="font-size:'+fs+'px;font-weight:500;color:'+textColor+';padding:2px;line-height:1.2">'+s.name+'</span>';
        div.onmouseenter=function(){{div.style.transform='scale(1.08)';}};
        div.onmouseleave=function(){{div.style.transform='scale(1)';}};
        area.appendChild(div);
      }});
    }})();

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
      if(q.source==='blog'){{badge.textContent="From my blog";badge.style.background='rgba(255,153,0,.12)';badge.style.color='#854F0B';}}
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
  </aside>
</div>
{FEEDBACK_WIDGET_HTML}
{ASK_WIDGET_HTML}
{back_top_html()}
{footer_html()}
<script src="{ASSETS_URL}/blog.js"></script>
</body></html>"""


# ── Main ──────────────────────────────────────────────────────
def main():
    print("Fetching posts from Blogger...")
    raw_posts = fetch_all_posts()
    print(f"  {len(raw_posts)} posts found")

    posts = []
    for entry in raw_posts:
        title    = entry["title"]
        url      = entry.get("url", "")
        body_html = clean_html(entry["html"])
        plain_text = BeautifulSoup(body_html, "html.parser").get_text()
        tags     = detect_tags(title + " " + plain_text)
        dt       = parse_date(url)
        slug     = slugify(title)

        posts.append({
            "slug":      slug,
            "title":     title,
            "url":       url,
            "date":      dt,
            "date_fmt":  dt.strftime("%b %Y"),
            "tags":      tags,
            "read_time": reading_time(body_html),
            "excerpt":   excerpt(body_html),
            "body_html": body_html,
        })

    posts.sort(key=lambda p: p["date"], reverse=True)

    print(f"Building {len(posts)} post pages...")
    for i, post in enumerate(posts):
        out_dir = BLOG_DIR / post["slug"]
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "index.html").write_text(
            build_post_page(
                post,
                prev_post=posts[i + 1] if i + 1 < len(posts) else None,
                next_post=posts[i - 1] if i > 0 else None,
            ),
            encoding="utf-8",
        )

    (BLOG_DIR / "index.html").write_text(build_index_page(posts), encoding="utf-8")

    # posts.json — used by portfolio homepage to render latest posts
    posts_json = [
        {
            "title":   p["title"],
            "url":     f"/blog/{p['slug']}/",
            "date":    p["date"].strftime("%b %d, %Y").replace(" 0", " "),
            "tags":    " · ".join(p["tags"][:2]) if p["tags"] else "",
            "excerpt": p["excerpt"],
        }
        for p in posts[:6]
    ]
    (BLOG_DIR / "posts.json").write_text(json.dumps(posts_json, indent=2), encoding="utf-8")

    print(f"Done — {len(posts)} posts built at blog/")


if __name__ == "__main__":
    main()
