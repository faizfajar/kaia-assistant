import os
import sys
import logging
from datetime import datetime, timedelta
from fastmcp import FastMCP
from github import Github, Auth, GithubException
from dotenv import load_dotenv

load_dotenv()

# Direct logs to stderr — keeps stdout clean for JSON-RPC stdio transport
logging.basicConfig(level=logging.ERROR, stream=sys.stderr)

mcp = FastMCP("GitHub-DevOps-Server")

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    raise ValueError("GITHUB_TOKEN missing in .env")

gh = Github(auth=Auth.Token(GITHUB_TOKEN))

# Validate token on startup
try:
    _user = gh.get_user()
    _username = _user.login
except GithubException as e:
    logging.error(f"GitHub auth failed: {e}")
    sys.exit(1)


@mcp.tool()
def get_global_activity(limit_repos: int = 5, days: int = 7) -> str:
    """
    Scan all repositories for recent commit activity.
    Returns the latest commit per repo, sorted by most recently pushed.

    Args:
        limit_repos: Maximum number of repositories to include (default 5).
        days: How many days back to scan for commits (default 7).
    """
    try:
        since_date = datetime.now() - timedelta(days=days)
        repos = _user.get_repos(sort="pushed", direction="desc")

        results = []
        count = 0

        for repo in repos:
            if count >= limit_repos:
                break

            try:
                commits = repo.get_commits(since=since_date)

                # totalCount can be unreliable — iterate safely
                commit_list = list(commits[:1])
                if not commit_list:
                    continue

                last_commit = commit_list[0]
                sha_short = last_commit.sha[:7]
                
                date_str = last_commit.commit.author.date.strftime("%d/%m %H:%M")

                # Only take first line of commit message
                message = last_commit.commit.message.split("\n")[0][:80]

                results.append(f"📦 **{repo.name}** [`{sha_short}`]: {message} ({date_str})")
                count += 1

            except GithubException:
                # Skip inaccessible or empty repos silently
                continue
            except Exception:
                continue

        if not results:
            return f"Tidak ada commit terdeteksi dalam {days} hari terakhir."

        header = f"**Aktivitas GitHub — {days} hari terakhir:**\n"
        return header + "\n".join(results)

    except GithubException as e:
        return f"GitHub API error: {str(e)}"
    except Exception as e:
        return f"Gagal scan aktivitas: {str(e)}"
      
@mcp.tool()
def get_commit_details(repo_name: str, commit_sha: str) -> str:
    """
    Retrieves technical details of a specific commit, including changed files.
    Use this only when the user explicitly asks for details or specific changes.
    """
    try:
        user = gh.get_user()
        repo = user.get_repo(repo_name)
        commit = repo.get_commit(commit_sha)

        files = commit.files
        # Build the structured output header
        total_files = len(files) if isinstance(files, list) else getattr(files, 'totalCount', 0)
        
        output = [
            f"***Commit Detail: {repo_name}***",
            f"Message: {commit.commit.message}",
            "\n**File Changes: ({total_files} total)**",
        ]

        # Limit to top 10 files to keep the context window efficient
        for f in files[:10]:
            status_emoji = (
                "📝"
                if f.status == "modified"
                else "➕"
                if f.status == "added"
                else "❌"
            )
            output.append(
                f"- {status_emoji} `{f.filename}` (+{f.additions} -{f.deletions})"
            )

        if total_files > 10:
            output.append(f"\n*...and {total_files - 10} more files.*")

        return "\n".join(output)
    except Exception as e:
        return f"Failed to retrieve details: {str(e)}"


if __name__ == "__main__":
    mcp.run(transport="stdio")