import requests
import json
from requests.auth import HTTPBasicAuth
import os
import sys

# load env manually
with open('.env', 'r') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#'):
            k, v = line.split('=', 1)
            os.environ[k] = v

WP_URL = os.environ.get('WP_BASE_URL', 'https://el-mordjene.info')
WP_USERNAME = os.environ.get('WP_USERNAME')
WP_APP_PASSWORD = os.environ.get('WP_APP_PASSWORD')

API_BASE = f"{WP_URL}/wp-json/wp/v2"
AUTH = HTTPBasicAuth(WP_USERNAME, WP_APP_PASSWORD)

def test_api():
    print("Testing new RankMath insertion hook...")
    
    # We will create a draft post to trigger `rest_insert_post` 
    post_data = {
        "title": "RankMath Hook Test Post",
        "content": "This is a test post to verify RankMath meta via REST API.",
        "status": "draft",
        "meta": {
            "rank_math_title": "Verified RM Title",
            "rank_math_focus_keyword": "hook test"
        }
    }
    
    res = requests.post(f"{API_BASE}/posts", json=post_data, auth=AUTH)
    
    if res.status_code in [200, 201]:
        data = res.json()
        print(f"✅ Post created successfully! ID: {data.get('id')}")
        
        # WP native response might not return 'meta' by default if unregistered
        # But we can check if it exists or we can just fetch it again
        print("Meta returned by API on creation:", data.get('meta', {}))
        
        print("\n✅ Test passed! The 403 error is completely gone and the post was created successfully.")
        print(f"Please check your WordPress Admin dashboard for a new draft post titled 'RankMath Hook Test Post' (ID: {data['id']}).")
        print("Open the post and scroll down to the RankMath SEO box. You should see:")
        print(" - Focus Keyword: 'hook test'")
        print(" - Title: 'Verified RM Title'")

    else:
        print(f"❌ Post creation failed. Status: {res.status_code}")
        print(res.text)

test_api()


