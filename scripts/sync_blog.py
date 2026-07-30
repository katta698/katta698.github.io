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
import os
import re
import sys
from datetime import datetime
from html import escape
from pathlib import Path

import markdown
import yaml
from bs4 import BeautifulSoup

# ── Paths (relative to repo root) ─────────────────────────────
REPO_ROOT   = Path(__file__).parent.parent
BLOG_DIR    = REPO_ROOT / "blog"
POSTS_DIR   = REPO_ROOT / "posts"
ASSETS_URL  = "/blog/assets"

# Cache-bust blog.css with a short content hash, so a CSS change is
# guaranteed to bypass any stale browser/CDN cache instead of relying on
# everyone hitting a hard refresh.
def _css_version():
    css_path = REPO_ROOT / "blog" / "assets" / "blog.css"
    return hashlib.md5(css_path.read_bytes()).hexdigest()[:8]

CSS_VERSION = _css_version()

SITE_URL    = "https://jayanthkatta.com"
BLOG_URL    = f"{SITE_URL}/blog"
DISQUS_ID   = "jayanthkatta"
API_URL     = "https://37arp5b92a.execute-api.us-east-1.amazonaws.com/search"
SUMMARY_API_URL = "https://37arp5b92a.execute-api.us-east-1.amazonaws.com/summary"

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
MAX_TAGS = 3
CATEGORY_ORDER = ["All", "AWS", "Architecture", "Terraform", "Kubernetes", "GitOps", "AI", "Tech", "Career", "Health", "Life"]

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
            # Architecture Series posts (arch-NNN-*.html) are built by a
            # completely separate pipeline (.github/workflows/publish-draft.yml),
            # which uses its own template-substitution logic, not this script's
            # clean_html()/generate_summary()/excerpt(). Reprocessing them here
            # produces genuinely different card text/excerpts than what's live
            # (confirmed live 2026-07-30) -- so main() must treat them as
            # read-only pass-through: never rewrite their individual page, never
            # recompute their display metadata, just reuse whatever's already
            # committed in blog/posts.json for their card.
            "externally_built": post_file.name.startswith("arch-"),
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
def html_head(title, description, canonical, extra=""):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{escape(title)}</title>
<meta name="description" content="{escape(description)}"/>
<link rel="canonical" href="{canonical}"/>
<link rel="icon" href="/favicon-transparent.png" type="image/png"/>
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
    <li><a href="/blog/digests/">Digests</a></li>
    <li><a href="/resume.html">Resume</a></li>
    <li><a href="/blog/dashboard/" style="color:var(--accent-gold);opacity:0.6;font-size:0.75rem;">⬡ Insights</a></li>
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
  <a href="/blog/digests/">Digests</a>
  <a href="/resume.html">Resume</a>
  <a href="/blog/dashboard/">⬡ Insights</a>
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

    return f"""{html_head(title + " | Jayanth Katta Blog", post["excerpt"], post_url, extra)}
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
    <div class="posts-grid" id="posts-grid">
      {"".join(cards_html)}
      <div class="empty-state" id="empty-state" style="display:none">
        <h3>No posts found</h3><p>Try a different search term or topic filter.</p>
      </div>
    </div>
  </div>
  <aside class="sidebar">
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
        var textColor = opacity>0.5?'#2E2113':'#7A5C3E';
        var fs = r>32?12:r>22?10:9;
        var div=document.createElement('div');
        div.title=s.name+': ~'+s.count+' mentions';
        div.style.cssText='position:absolute;left:'+(x-r)+'px;top:'+(y-r)+'px;width:'+(r*2)+'px;height:'+(r*2)+'px;border-radius:50%;background:rgba(196,164,132,'+opacity+');display:flex;align-items:center;justify-content:center;text-align:center;cursor:default;transition:transform .15s';
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
  </aside>
</div>
{FEEDBACK_WIDGET_HTML}
{ASK_WIDGET_HTML}
{back_top_html()}
{footer_html()}
<audio id="beach-audio" loop preload="none"></audio>
<script src="{ASSETS_URL}/blog.js"></script>
<script>
(function(){{
  var VIDEOS=[
    '/blog/assets/videos/sun.mp4',
    '/blog/assets/videos/mon.mp4',
    '/blog/assets/videos/tue.mp4',
    '/blog/assets/videos/wed.mp4',
    '/blog/assets/videos/thu.mp4',
    '/blog/assets/videos/fri.mp4',
    '/blog/assets/videos/sat.mp4'
  ];
  var AUDIO=[
    '/blog/assets/audio/sun.mp3',
    '/blog/assets/audio/mon.mp3',
    '/blog/assets/audio/tue.mp3',
    '/blog/assets/audio/wed.mp3',
    '/blog/assets/audio/thu.mp3',
    '/blog/assets/audio/fri.mp3',
    '/blog/assets/audio/sat.mp3'
  ];
  var day=new Date().getDay();
  var vid=document.getElementById('hero-video');
  var aud=document.getElementById('beach-audio');
  if(vid){{
    vid.src=VIDEOS[day];
    var _tryPlay=function(){{if(vid.paused)vid.play().catch(function(){{}});}};
    vid.addEventListener('loadeddata',_tryPlay,{{once:true}});
    vid.addEventListener('canplay',_tryPlay,{{once:true}});
    document.addEventListener('visibilitychange',function(){{if(!document.hidden)_tryPlay();}});
    window.addEventListener('pageshow',_tryPlay);
    document.addEventListener('touchstart',_tryPlay,{{once:true}});
    var _n=0,_iv=setInterval(function(){{_tryPlay();if(++_n>=4||!vid.paused)clearInterval(_iv);}},2000);
  }}
  if(aud)aud.src=AUDIO[day];
}})();

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


def main():
    print("Reading posts from posts/...")
    raw_posts = fetch_local_posts()
    print(f"  {len(raw_posts)} posts found")

    # Architecture Series posts are built by a separate pipeline
    # (publish-draft.yml) — load whatever's already committed for them so
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
        plain_text = BeautifulSoup(body_html, "html.parser").get_text()
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
            "date_fmt":      dt.strftime("%b %Y"),
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
        f"{externally_built_count} Architecture Series pages left untouched, built by publish-draft.yml)..."
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

    (BLOG_DIR / "index.html").write_text(build_index_page(visible_posts), encoding="utf-8")

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
        }
        for p in visible_posts[:7]
    ]
    (BLOG_DIR / "posts.json").write_text(json.dumps(posts_json, indent=2), encoding="utf-8")

    # stats.json — used by portfolio homepage for the writing streak counter
    dates = [p["date"] for p in visible_posts]
    stats_json = {
        "total_posts": len(visible_posts),
        "first_post_date": min(dates).strftime("%Y-%m-%d") if dates else None,
        "latest_post_date": max(dates).strftime("%Y-%m-%d") if dates else None,
    }
    (BLOG_DIR / "stats.json").write_text(json.dumps(stats_json, indent=2), encoding="utf-8")

    # rss.xml — feed for external consumers (e.g. the GitHub profile README's
    # blog-post-workflow action, which needs a feed since the old Blogger one
    # was retired) — and the blog-search RAG indexer, so drafts must stay out
    (BLOG_DIR / "rss.xml").write_text(build_rss_feed(visible_posts), encoding="utf-8")

    print(f"Done — {len(visible_posts)} public posts built at blog/ ({draft_count} draft)")


if __name__ == "__main__":
    main()
