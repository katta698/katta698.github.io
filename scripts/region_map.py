#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pull region names out of incident text, and place them on a world map.

Two jobs, kept together because they share the vocabulary.

Extraction
----------
Only 33 of 906 incidents carried a region as a field: AWS puts one in its
history feed, Google's live feed lists affected locations, and Azure publishes
none at all. But the vendors write the region into the title constantly --
"Multiple products in us-central1-b", "Issues accessing resources in West US"
-- so 229 can be recovered by reading it.

That is a parse of the vendor's own words, not an inference: the string
"us-central1" in a Google incident title is Google naming the region. Nothing
is guessed from service names or blast radius.

Placement
---------
The coordinates are the published locations of the regions themselves -- AWS
says us-east-1 is Northern Virginia, Google says us-central1 is Iowa -- and
they are approximate city centroids, which is the resolution the vendors
themselves publish at. No datacentre is being pinpointed and the page says so.

A region with no entry here is NOT dropped. It is counted and listed under the
map, because silently omitting a location would make the map claim completeness
it does not have.

Regions still without a position are the ones no vendor states a city for --
AWS's GovCloud pair and its sovereign-cloud region, a handful of Google region
ids with no published location, and Azure's "non-regional" entries, which are
not places at all. Those are counted and named under the map rather than
dropped, because a map that silently omits a region claims a completeness it
does not have.
"""
import re

# Machine region ids: AWS and Google.
CODE = re.compile(
    r"\b((?:us|eu|ap|sa|me|af|ca|il|australia|asia|europe|northamerica|"
    r"southamerica)-[a-z]+\d*(?:-\d)?[a-z]?)\b", re.I)

# Azure writes place names rather than ids.
AZURE_NAMES = [
    "East US 2", "East US", "West US 3", "West US 2", "West US",
    "North Central US", "South Central US", "West Central US", "Central US",
    "North Europe", "West Europe", "UK South", "UK West",
    "Southeast Asia", "East Asia", "Japan East", "Japan West",
    "Australia East", "Australia Southeast", "Australia Central",
    "Brazil South", "Canada Central", "Canada East",
    "Central India", "South India", "West India",
    "France Central", "Germany West Central", "Norway East",
    "Switzerland North", "UAE North", "South Africa North",
    "Korea Central", "Sweden Central", "Poland Central", "Italy North",
    "Qatar Central", "Israel Central", "Spain Central",
]
AZURE = re.compile("|".join(re.escape(n) for n in AZURE_NAMES))

# lat, lon. Approximate centroids of the cities the vendors name for each
# region. Kept short and shared: several regions sit in the same city.
CITY = {
    "n-virginia": (38.95, -77.45), "ohio": (40.10, -83.10),
    "oregon": (45.85, -119.70), "n-california": (37.35, -121.95),
    "iowa": (41.26, -95.94), "s-carolina": (33.20, -80.05),
    "montreal": (45.50, -73.57), "toronto": (43.65, -79.38),
    "sao-paulo": (-23.55, -46.63), "santiago": (-33.45, -70.67),
    "dublin": (53.35, -6.26), "london": (51.51, -0.13),
    "frankfurt": (50.11, 8.68), "paris": (48.86, 2.35),
    "amsterdam": (52.37, 4.90), "stockholm": (59.33, 18.07),
    "milan": (45.46, 9.19), "zurich": (47.38, 8.54),
    "madrid": (40.42, -3.70), "warsaw": (52.23, 21.01),
    "oslo": (59.91, 10.75), "belgium": (50.85, 4.35),
    "finland": (60.17, 24.94),
    "mumbai": (19.08, 72.88), "delhi": (28.61, 77.21),
    "singapore": (1.35, 103.82), "tokyo": (35.68, 139.69),
    "osaka": (34.69, 135.50), "seoul": (37.57, 126.98),
    "hong-kong": (22.32, 114.17), "taiwan": (25.03, 121.57),
    "jakarta": (-6.21, 106.85), "sydney": (-33.87, 151.21),
    "melbourne": (-37.81, 144.96),
    "bahrain": (26.07, 50.56), "uae": (25.20, 55.27),
    "tel-aviv": (32.08, 34.78), "doha": (25.29, 51.53),
    "cape-town": (-33.92, 18.42), "johannesburg": (-26.20, 28.05),
    "calgary": (51.05, -114.07), "queretaro": (20.59, -100.39),
    "dallas": (32.78, -96.80), "phoenix": (33.45, -112.07),
    "san-antonio": (29.42, -98.49), "rio": (-22.91, -43.17),
    "beijing": (39.90, 116.40), "shanghai": (31.23, 121.47),
    "yinchuan": (38.49, 106.23), "hong-kong-2": (22.32, 114.17),
    "taipei": (25.03, 121.57), "kuala-lumpur": (3.14, 101.69),
    "auckland": (-36.85, 174.76), "bangkok": (13.76, 100.50),
    "busan": (35.18, 129.08), "nagpur": (21.15, 79.09),
    "jamnagar": (22.47, 70.06), "berlin": (52.52, 13.40),
    "turin": (45.07, 7.69), "marseille": (43.30, 5.37),
    "geneva": (46.20, 6.14), "stavanger": (58.97, 5.73),
    "malmo": (55.60, 13.00), "vienna": (48.21, 16.37),
    "copenhagen": (55.68, 12.57), "canberra": (-35.28, 149.13),
    "dammam": (26.43, 50.10),
}

# region id -> city key. Only regions the vendors actually name a city for.
REGION_CITY = {
    # AWS
    "us-east-1": "n-virginia", "us-east-2": "ohio", "us-west-1": "n-california",
    "us-west-2": "oregon", "ca-central-1": "montreal", "sa-east-1": "sao-paulo",
    "eu-west-1": "dublin", "eu-west-2": "london", "eu-west-3": "paris",
    "eu-central-1": "frankfurt", "eu-north-1": "stockholm",
    "eu-south-1": "milan", "eu-south-2": "madrid",
    "ap-south-1": "mumbai", "ap-south-2": "delhi",
    "ap-southeast-1": "singapore", "ap-southeast-2": "sydney",
    "ap-southeast-3": "jakarta", "ap-southeast-4": "melbourne",
    "ap-northeast-1": "tokyo", "ap-northeast-2": "seoul",
    "ap-northeast-3": "osaka", "ap-east-1": "hong-kong",
    "me-south-1": "bahrain", "me-central-1": "uae",
    "il-central-1": "tel-aviv", "af-south-1": "cape-town",
    # Google
    "us-central1": "iowa", "us-east1": "s-carolina", "us-east4": "n-virginia",
    "us-east5": "ohio", "us-west1": "oregon", "us-west2": "n-california",
    "us-west3": "n-california", "us-west4": "n-california",
    "northamerica-northeast1": "montreal", "northamerica-northeast2": "toronto",
    "southamerica-east1": "sao-paulo", "southamerica-west1": "santiago",
    "europe-west1": "belgium", "europe-west2": "london",
    "europe-west3": "frankfurt", "europe-west4": "amsterdam",
    "europe-west6": "zurich", "europe-west8": "milan",
    "europe-west9": "paris", "europe-north1": "finland",
    "europe-central2": "warsaw", "europe-southwest1": "madrid",
    "asia-south1": "mumbai", "asia-south2": "delhi",
    "asia-southeast1": "singapore", "asia-southeast2": "jakarta",
    "asia-east1": "taiwan", "asia-east2": "hong-kong",
    "asia-northeast1": "tokyo", "asia-northeast2": "osaka",
    "asia-northeast3": "seoul", "australia-southeast1": "sydney",
    "australia-southeast2": "melbourne", "me-west1": "tel-aviv",
    "me-central1": "doha", "africa-south1": "johannesburg",
    # Azure
    "East US": "n-virginia", "East US 2": "n-virginia",
    "Central US": "iowa", "North Central US": "iowa",
    "South Central US": "s-carolina", "West Central US": "oregon",
    "West US": "n-california", "West US 2": "oregon", "West US 3": "n-california",
    "North Europe": "dublin", "West Europe": "amsterdam",
    "UK South": "london", "UK West": "london",
    "France Central": "paris", "Germany West Central": "frankfurt",
    "Norway East": "oslo", "Switzerland North": "zurich",
    "Sweden Central": "stockholm", "Poland Central": "warsaw",
    "Italy North": "milan", "Spain Central": "madrid",
    "Southeast Asia": "singapore", "East Asia": "hong-kong",
    "Japan East": "tokyo", "Japan West": "osaka", "Korea Central": "seoul",
    "Central India": "mumbai", "South India": "mumbai", "West India": "mumbai",
    "Australia East": "sydney", "Australia Southeast": "melbourne",
    "Australia Central": "sydney", "Brazil South": "sao-paulo",
    "Canada Central": "toronto", "Canada East": "montreal",
    "UAE North": "uae", "Qatar Central": "doha", "Israel Central": "tel-aviv",
    "South Africa North": "johannesburg",
    # Newer regions, placed from the city each vendor names for them.
    # AWS
    "ap-east-2": "taipei", "ap-southeast-5": "kuala-lumpur",
    "ap-southeast-6": "auckland", "ap-southeast-7": "bangkok",
    "ca-west-1": "calgary", "cn-north-1": "beijing",
    "cn-northwest-1": "yinchuan", "eu-central-2": "zurich",
    "me-west-1": "tel-aviv", "mx-central-1": "queretaro",
    # Google
    "europe-west10": "berlin", "europe-west12": "turin",
    "europe-north2": "stockholm", "me-central2": "dammam",
    "us-south1": "dallas", "northamerica-south1": "queretaro",
    # Azure
    "Brazil Southeast": "rio", "France South": "marseille",
    "Switzerland West": "geneva", "Norway West": "stavanger",
    "Germany North": "berlin", "Sweden South": "malmo",
    "Australia Central 2": "canberra", "Korea South": "busan",
    "Jio India Central": "nagpur", "Jio India West": "jamnagar",
    "China East": "shanghai", "China East 2": "shanghai",
    "China North": "beijing", "China North 2": "beijing",
    "China North 3": "beijing", "South Africa West": "cape-town",
    "US Gov Arizona": "phoenix", "US Gov Texas": "san-antonio",
    "US Gov Virginia": "n-virginia", "Mexico Central": "queretaro",
    "New Zealand North": "auckland", "Indonesia Central": "jakarta",
    "Malaysia West": "kuala-lumpur", "Chile Central": "santiago",
    "Austria East": "vienna", "Denmark East": "copenhagen",
}


def regions_in(cloud, text):
    """Region names the vendor wrote in this incident's own text."""
    if not text:
        return []
    if cloud == "azure":
        found = AZURE.findall(text)
    else:
        found = [m for m in CODE.findall(text)]
    out = []
    for f in found:
        f = f.strip()
        # A zone is a region plus a letter: us-central1-a. Map it to its
        # region, since that is what has a published location.
        base = re.sub(r"-[a-f]$", "", f)
        if base not in out:
            out.append(base)
    return out


def place(region):
    """(lat, lon) for a region, or None when its location is not published."""
    city = REGION_CITY.get(region)
    return CITY.get(city) if city else None
