#!/usr/bin/env python3
"""
Release Notes Generator

This script generates release notes by:
1. Querying GitHub for merged PRs in specified repositories
2. Filtering and processing PR data
3. Using AI to summarize changes
4. Posting results to Slack

Usage:
    python generate_release_notes.py --repos "org1/repo1,org2/repo2" --days-back 7
"""

import argparse
import os
import sys
import re
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import logging

# Third-party imports
try:
    from github import Github
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError
except ImportError as e:
    print(f"Missing required dependency: {e}")
    print("Please install with: pip install PyGithub slack_sdk")
    sys.exit(1)

# Local imports
try:
    from ai_provider import create_ai_provider
except ImportError:
    # Fallback for when running as module
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from ai_provider import create_ai_provider

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class PullRequest:
    """Data class for pull request information."""
    title: str
    body: str
    number: int
    url: str
    merged_at: datetime
    labels: List[str]
    repo_name: str

class ReleaseNotesGenerator:
    """Main class for generating release notes."""
    
    def __init__(self, slack_bot_token: str, slack_channel: str, 
                 ai_provider: str, ai_api_key: str, github_token: str, 
                 ai_model: Optional[str] = None):
        """
        Initialize the generator with required tokens.
        
        Args:
            slack_bot_token: Slack Bot Token
            slack_channel: Slack channel to post to (e.g., #release-notes)
            ai_provider: AI provider to use ('openai' or 'claude')
            ai_api_key: API key for the AI provider
            github_token: GitHub Personal Access Token
            ai_model: Optional model name to override default
        """
        self.slack_client = WebClient(token=slack_bot_token)
        self.slack_channel = slack_channel
        self.ai_provider = create_ai_provider(ai_provider, ai_api_key, ai_model)
        self.github_client = Github(github_token)
        
        # Test API connections
        self._test_connections()
    
    def _test_connections(self):
        """Test that all API connections are working."""
        try:
            # Test GitHub connection
            user = self.github_client.get_user()
            logger.info(f"GitHub connection successful (authenticated as: {user.login})")
        except Exception as e:
            logger.error(f"GitHub connection failed: {e}")
            raise
            
        try:
            # Test Slack connection
            self.slack_client.auth_test()
            logger.info("Slack connection successful")
        except Exception as e:
            logger.error(f"Slack connection failed: {e}")
            raise
            
        try:
            # Test AI provider connection
            if self.ai_provider.test_connection():
                logger.info("AI provider connection successful")
            else:
                raise Exception("AI provider connection failed")
        except Exception as e:
            logger.error(f"AI provider connection failed: {e}")
            raise
    
    def get_merged_prs(self, repo_name: str, since_date: datetime) -> List[PullRequest]:
        """
        Get merged pull requests for a repository since a given date.
        
        Args:
            repo_name: Repository name in format 'org/repo'
            since_date: Date to look back from
            
        Returns:
            List of PullRequest objects
        """
        try:
            repo = self.github_client.get_repo(repo_name)
            logger.info(f"Fetching PRs for {repo_name} since {since_date.isoformat()}")
            
            # Query for merged PRs
            query = f"repo:{repo_name} is:pr is:merged merged:>={since_date.strftime('%Y-%m-%d')}"
            prs = self.github_client.search_issues(query=query, sort='updated', order='desc')
            
            pull_requests = []
            for pr in prs:
                # Get full PR details
                full_pr = repo.get_pull(pr.number)
                
                # Ensure merged_at is not None
                merged_at = full_pr.merged_at
                if merged_at is None:
                    logger.warning(f"PR #{full_pr.number} has no merged_at date, skipping")
                    continue
                
                pull_request = PullRequest(
                    title=full_pr.title,
                    body=full_pr.body or "",
                    number=full_pr.number,
                    url=full_pr.html_url,
                    merged_at=merged_at,
                    labels=[label.name for label in full_pr.labels],
                    repo_name=repo_name
                )
                pull_requests.append(pull_request)
                
            logger.info(f"Found {len(pull_requests)} merged PRs in {repo_name}")
            return pull_requests
            
        except Exception as e:
            logger.error(f"Error fetching PRs for {repo_name}: {e}")
            raise
    
    def filter_prs(self, prs: List[PullRequest]) -> Dict[str, List[PullRequest]]:
        """
        Filter pull requests and separate dependency updates.
        
        Args:
            prs: List of all pull requests
            
        Returns:
            Dictionary with 'regular' and 'deps' PRs
        """
        regular_prs = []
        deps_prs = []
        
        # Regex pattern for dependency update PRs
        deps_pattern = re.compile(r'^chore\(deps\)', re.IGNORECASE)
        
        for pr in prs:
            if deps_pattern.match(pr.title):
                deps_prs.append(pr)
            else:
                regular_prs.append(pr)
        
        logger.info(f"Filtered {len(regular_prs)} regular PRs and {len(deps_prs)} dependency PRs")
        
        return {
            'regular': regular_prs,
            'deps': deps_prs
        }
    
    def format_prs_for_summary(self, prs: List[PullRequest]) -> str:
        """
        Format pull requests for AI summarization.
        
        Args:
            prs: List of pull requests
            
        Returns:
            Formatted string for AI processing
        """
        if not prs:
            return "No pull requests found."
        
        formatted_prs = []
        for pr in prs:
            # Clean up the title and body
            title = pr.title.strip()
            body = pr.body.strip() if pr.body else ""
            
            # Include labels if available
            labels_text = f"Labels: {', '.join(pr.labels)}" if pr.labels else ""
            
            # Format the PR information
            pr_info = f"PR #{pr.number}: {title}"
            if body:
                pr_info += f"\nDescription: {body}"
            if labels_text:
                pr_info += f"\n{labels_text}"
            if pr.url:
                pr_info += f"\nURL: {pr.url}"
            
            formatted_prs.append(pr_info)
        
        return "\n\n".join(formatted_prs)
    
    def summarize_with_ai(self, repo_name: str, prs_text: str) -> str:
        """
        Use AI to summarize pull requests for a repository.
        
        Args:
            repo_name: Repository name
            prs_text: Formatted pull requests text
            
        Returns:
            AI-generated summary
        """
        if not prs_text or prs_text == "No pull requests found.":
            return f"*{repo_name}*: No changes in the specified time period."
        
        try:
            release_notes_prompt = """
You are an expert technical writer creating user-facing release notes. Your task is to transform pull request data into clear, benefit-focused release notes.

CRITICAL RULES:
1. NEVER list individual PR numbers or titles
2. NEVER include repository names in the output (they will be added automatically)
3. SYNTHESIZE all changes into coherent features and improvements
4. Focus on WHY changes matter to users/developers, but include relevant technical context
5. Group related technical changes together

INPUT: You'll receive PR titles, descriptions, and commit messages for multiple repositories.

OUTPUT FORMAT (JSON):
```json
{
  "categories": [
    {
      "name": "Feature Category",
      "items": [
        "Specific improvement with clear benefit and technical context",
        "Another improvement with impact described"
      ]
    },
    {
      "name": "Bug Fixes", 
      "items": [
        "Fixed [issue] that [what it was causing for users/developers]"
      ]
    },
    {
      "name": "Technical Improvements",
      "items": [
        "[Technical enhancement] that [benefit/impact]"
      ]
    }
  ]
}
```

IMPORTANT: Return ONLY valid JSON, no other text or formatting.

TRANSFORMATION EXAMPLES:
- "chore/add_user_settings_field" → "Added new user settings field for improved customization options"
- "fix-dashboard-loading-performance" → "Optimized dashboard queries for improved loading performance"
- "upgrade-ai-model" → "Upgraded AI model for improved response accuracy and context understanding"
- "enhance-api-integration" → "Enhanced API integration with webhook support and improved error handling"
- "db-optimization" → "Database query optimization for improved API response times"
- "auth-refactor" → "Refactored authentication system to support OAuth2 and improve security"

GUIDELINES:
- Extract the actual feature from vague PR titles
- Combine related PRs into single, comprehensive bullet points
- Include relevant technical details that developers would care about
- Prioritize changes by impact (user-facing first, then technical improvements)
- Use active voice and specific benefits
- For technical improvements, explain both the technical change and its benefit
- Skip truly internal-only changes with no impact
- NEVER include specific performance claims (like "5x faster", "40% improvement") unless explicitly proven in the PR
- Use general terms like "improved performance", "optimized", "enhanced" instead of specific metrics
- Focus on what was changed rather than unproven performance claims

Analyze all PRs holistically and create a cohesive narrative of improvements, balancing user benefits with technical context.
"""

            system_prompt = release_notes_prompt
            
            user_prompt = f"""Repository: {repo_name}

Pull Requests to analyze:
{prs_text}

Create user-facing release notes following the format and guidelines above."""
            
            summary_json = self.ai_provider.generate_summary(system_prompt, user_prompt)
            
            # Parse JSON and format for Slack
            try:
                import json
                import re
                
                # Clean up the response - remove "json" prefix and code block markers
                cleaned_json = summary_json.strip()
                cleaned_json = re.sub(r'^json\s*', '', cleaned_json)
                cleaned_json = re.sub(r'^```json\s*', '', cleaned_json)
                cleaned_json = re.sub(r'\s*```$', '', cleaned_json)
                
                data = json.loads(cleaned_json.strip())
                
                # Create formatted Slack message with better visual separation
                formatted_summary = f"*{repo_name}*\n"
                
                for category in data.get('categories', []):
                    category_name = category.get('name', '')
                    items = category.get('items', [])
                    
                    if items:
                        formatted_summary += f"\n• *{category_name}*:\n"
                        for item in items:
                            formatted_summary += f"  ◦ {item}\n"
                
                # Add visual separator at the end
                formatted_summary += "\n" + "─" * 50 + "\n"
                
                return formatted_summary
                
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                logger.warning(f"Failed to parse JSON for {repo_name}, falling back to raw text: {e}")
                # Fallback to raw text if JSON parsing fails
                return f"*{repo_name}*:\n\n{summary_json}"
            
        except Exception as e:
            logger.error(f"AI provider error for {repo_name}: {e}")
            # Fallback to basic summary
            return f"*{repo_name}*: {len(prs_text.split('PR #')) - 1} pull requests merged. See individual PRs for details."
    
    def post_to_slack(self, message: str, date_range: Optional[str] = None) -> None:
        """
        Post message to Slack channel with beautiful formatting.
        
        Args:
            message: Message to post
            date_range: Date range string to include in header
        """
        try:
            # Create a simple text version for accessibility
            text_version = message.replace('*', '').replace('•', '-').replace('◦', '  -').replace('─', '-')
            
            # Split message into repository sections (separated by the visual divider)
            sections = message.split('─' * 50)
            
            # Create header with date range if provided
            header_text = "📰 Release Notes"
            if date_range:
                header_text += f" ({date_range})"
            
            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": header_text,
                        "emoji": True
                    }
                },
                {
                    "type": "divider"
                }
            ]
            
            for section in sections:
                section = section.strip()
                if section:
                    # Split section into lines to extract repo name
                    lines = section.split('\n')
                    if lines and lines[0].startswith('*') and lines[0].endswith('*'):
                        # Extract repo name and create a header
                        repo_name = lines[0].strip('*')
                        
                        # Add repository header
                        blocks.append({
                            "type": "header",
                            "text": {
                                "type": "plain_text",
                                "text": repo_name,
                                "emoji": False
                            }
                        })
                        
                        # Add the rest of the content
                        content = '\n'.join(lines[1:]).strip()
                        if content:
                            blocks.append({
                                "type": "section",
                                "text": {
                                    "type": "mrkdwn",
                                    "text": content
                                }
                            })
                        
                        # Add divider between repositories
                        blocks.append({
                            "type": "divider"
                        })
            
            response = self.slack_client.chat_postMessage(
                channel=self.slack_channel,
                text=text_version,  # Required for accessibility
                blocks=blocks,
                unfurl_links=False
            )
            logger.info(f"Message posted to Slack channel {self.slack_channel}: {response['ts']}")
            
        except SlackApiError as e:
            logger.error(f"Slack API error: {e.response['error']}")
            raise
        except Exception as e:
            logger.error(f"Error posting to Slack: {e}")
            raise
    
    def generate_release_notes(self, repos: List[str], days_back: int) -> None:
        """
        Main method to generate and post release notes.
        
        Args:
            repos: List of repository names
            days_back: Number of days to look back
        """
        # Calculate time window
        window_start = datetime.now(timezone.utc) - timedelta(days=days_back)
        window_end = datetime.now(timezone.utc)
        
        # Format date range for display
        date_range = f"{window_start.strftime('%d %b %Y')} - {window_end.strftime('%d %b %Y')}"
        
        logger.info(f"Looking for PRs merged since {window_start.isoformat()}")
        
        if not repos:
            logger.error("No repositories provided")
            return
        
        all_summaries = []
        
        # Process each repository
        for repo in repos:
            repo = repo.strip()
            if not repo:
                continue
                
            try:
                # Get merged PRs
                prs = self.get_merged_prs(repo, window_start)
                
                if not prs:
                    all_summaries.append(f"*{repo}*: No changes in the specified time period.")
                    continue
                
                # Format regular PRs
                regular_prs_text = self.format_prs_for_summary(prs)
                
                # Generate summary
                summary = self.summarize_with_ai(repo, regular_prs_text)
                all_summaries.append(summary)
                
            except Exception as e:
                logger.error(f"Error processing repository {repo}: {e}")
                all_summaries.append(f"*{repo}*: Error processing repository - {str(e)}")
        
        # Combine all summaries
        if all_summaries:
            full_message = "\n\n".join(all_summaries)
            
            # Post to Slack
            self.post_to_slack(full_message, date_range)
            
            # Save message to file for action output
            with open("generated_message.txt", "w") as f:
                f.write(full_message)
            
            logger.info("Release notes generation completed successfully")
        else:
            logger.warning("No summaries generated")

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate release notes from GitHub PRs")
    parser.add_argument("--repos", required=True, help="Comma-separated list of <org>/<repo> strings")
    parser.add_argument("--days-back", type=int, default=7, help="Number of days to look back (default: 7)")
    
    args = parser.parse_args()
    
    # Get environment variables
    slack_bot_token = os.getenv("SLACK_BOT_TOKEN")
    slack_channel = os.getenv("SLACK_CHANNEL")
    ai_provider = os.getenv("AI_PROVIDER", "openai").lower()
    openai_api_key = os.getenv("OPENAI_API_KEY")
    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
    github_token = os.getenv("GITHUB_TOKEN")
    
    # Validate required inputs
    if not slack_bot_token:
        logger.error("SLACK_BOT_TOKEN environment variable is required")
        sys.exit(1)
    
    if not slack_channel:
        logger.error("SLACK_CHANNEL environment variable is required")
        sys.exit(1)
    
    if not github_token:
        logger.error("GITHUB_TOKEN environment variable is required")
        sys.exit(1)
    
    # Validate AI provider configuration
    if ai_provider == "openai":
        if not openai_api_key:
            logger.error("OPENAI_API_KEY environment variable is required for OpenAI provider")
            sys.exit(1)
        ai_api_key = openai_api_key
    elif ai_provider == "claude":
        if not anthropic_api_key:
            logger.error("ANTHROPIC_API_KEY environment variable is required for Claude provider")
            sys.exit(1)
        ai_api_key = anthropic_api_key
    else:
        logger.error(f"Unsupported AI provider: {ai_provider}. Supported providers: openai, claude")
        sys.exit(1)
    
    # Parse repositories
    repos = [repo.strip() for repo in args.repos.split(",") if repo.strip()]
    if not repos:
        logger.error("No valid repositories provided in --repos argument")
        sys.exit(1)
    
    logger.info(f"Using repositories: {repos}")
    
    try:
        # Initialize generator with PAT authentication
        generator = ReleaseNotesGenerator(
            slack_bot_token=slack_bot_token,
            slack_channel=slack_channel,
            ai_provider=ai_provider,
            ai_api_key=ai_api_key,
            github_token=github_token
        )
        
        # Generate release notes
        generator.generate_release_notes(repos, args.days_back)
        
    except Exception as e:
        logger.error(f"Failed to generate release notes: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 