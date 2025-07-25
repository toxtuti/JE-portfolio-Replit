
import os
from notion_client import Client

def main():
    # Initialize the Notion client
    # You'll need to set your Notion API token as a secret
    notion_token = os.environ.get('NOTION_TOKEN')
    
    if not notion_token:
        print("Please set your NOTION_TOKEN in the Secrets tab")
        print("You can get your token from: https://www.notion.so/my-integrations")
        return
    
    notion = Client(auth=notion_token)
    
    # Example: List all databases
    try:
        # This will list databases that your integration has access to
        databases = notion.search(filter={"property": "object", "value": "database"})
        print("Available databases:")
        for db in databases["results"]:
            print(f"- {db['title'][0]['plain_text'] if db['title'] else 'Untitled'}")
            print(f"  ID: {db['id']}")
    
    except Exception as e:
        print(f"Error connecting to Notion: {e}")
        print("Make sure your NOTION_TOKEN is correct and your integration has proper permissions")

if __name__ == "__main__":
    main()
