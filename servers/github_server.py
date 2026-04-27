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

# Global variables for lazy initialization
gh = None
_user = None

def get_gh_client():
    global gh, _user
    if gh is None:
        if not GITHUB_TOKEN:
            return None
        try:
            gh = Github(auth=Auth.Token(GITHUB_TOKEN))
            _user = gh.get_user()
            # Test connection with a light call
            _user.login
            return gh
        except Exception as e:
            logging.error(f"GitHub client initialization failed: {e}")
            gh = None # Reset
            return None
    return gh


@mcp.tool()
def get_global_activity(days: int = 7, page: int = 1, per_page: int = 10) -> str:
    """
    Scan all repositories for recent commit activity across the entire account.
    Returns a paginated list of commits sorted by date.

    Args:
        days: How many days back to scan for commits (default 7).
        page: The page number to retrieve (default 1).
        per_page: Number of commits per page (default 10).
    """
    client = get_gh_client()
    if not client:
        return "GitHub Token tidak tersedia atau koneksi gagal. Silakan cek koneksi internet dan .env"
    
    try:
        user = client.get_user()
        since_date = datetime.now() - timedelta(days=days)
        
        # Scan top 15 most recently pushed repos to find commits
        # We limit repos scanned to 15 to balance between coverage and API speed
        repos = user.get_repos(sort="pushed", direction="desc")[:15]

        all_commits = []
        for repo in repos:
            try:
                commits = repo.get_commits(since=since_date)
                for c in commits:
                    all_commits.append({
                        "repo": repo.name,
                        "sha": c.sha[:7],
                        "message": c.commit.message.split("\n")[0][:80],
                        "date": c.commit.author.date,
                        "author": c.commit.author.name
                    })
            except Exception:
                continue

        if not all_commits:
            return f"Tidak ada aktivitas commit terdeteksi dalam {days} hari terakhir."

        # Sort globally by date descending
        all_commits.sort(key=lambda x: x["date"], reverse=True)

        # Pagination logic
        total_commits = len(all_commits)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_commits = all_commits[start_idx:end_idx]

        if not paginated_commits and page > 1:
            return f"Halaman {page} kosong. Total hanya ada {total_commits} commit."

        results = []
        for c in paginated_commits:
            date_str = c["date"].strftime("%d/%m %H:%M")
            results.append(f"• 📦 **{c['repo']}** [`{c['sha']}`]: {c['message']} ({date_str})")

        header = f"**Aktivitas GitHub — {days} hari terakhir (Hal {page}):**\n"
        footer = f"\n\n*Menampilkan {len(paginated_commits)} dari {total_commits} commit.*"
        
        if total_commits > end_idx:
            footer += f" Ketik 'lihat halaman {page + 1}' untuk lebih banyak."

        return header + "\n".join(results) + footer

    except Exception as e:
        return f"Gagal scan aktivitas: {str(e)}"
      
@mcp.tool()
def get_commit_details(repo_name: str, commit_sha: str) -> str:
    """
    Retrieves technical details of a specific commit, including changed files.
    Use this only when the user explicitly asks for details or specific changes.
    """
    client = get_gh_client()
    if not client:
        return "GitHub client tidak tersedia."

    try:
        user = client.get_user()
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