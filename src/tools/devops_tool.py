import os
from github import Github
from langchain_core.tools import tool

# Initialize GitHub Client
g = Github(os.getenv("GITHUB_TOKEN"))

@tool
def get_recent_github_activity(limit: int = 5) -> str:
    """
    Fetches the most recent activity across all repositories for the authenticated user.
    Useful for answering: "What was my last commit and in which project?"
    """
    try:
        user = g.get_user()
        events = user.get_events()
        
        activity_summary = []
        count = 0
        
        for event in events:
            if count >= limit:
                break
            
            # Focus on PushEvents (Commits)
            if event.type == "PushEvent":
                repo_name = event.repo.name
                # Get the latest commit message in this push
                last_commit = event.payload['commits'][-1]['message']
                created_at = event.created_at.strftime("%Y-%m-%d %H:%M")
                
                activity_summary.append(
                    f"- **Project:** {repo_name}\n"
                    f"  **Commit:** {last_commit}\n"
                    f"  **Time:** {created_at}"
                )
                count += 1
        
        if not activity_summary:
            return "No recent push activity found."
            
        return "### Your Recent GitHub Activity:\n" + "\n".join(activity_summary)
    except Exception as e:
        return f"Error retrieving activity: {str(e)}"