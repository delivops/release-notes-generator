# Release Notes Generator

A GitHub Action that automatically generates and posts release notes to Slack by analyzing merged pull requests across multiple repositories using AI (OpenAI or Claude).

## Features

- 🔍 **Multi-repository analysis**: Process multiple repositories in a single run
- 🤖 **AI-powered summaries**: Uses OpenAI GPT-4o-mini or Claude to generate concise, professional release notes
- 📱 **Slack integration**: Posts formatted release notes directly to Slack channels
- ⏰ **Flexible time windows**: Configurable lookback period (default: 7 days)
- 📊 **Comprehensive coverage**: Analyzes all merged PRs, not just tagged releases

## Quick Start

### 1. Create a GitHub Personal Access Token

1. Go to GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Generate a new token with `repo` scope (or `public_repo` for public repositories only)
3. Copy the token for use in the action

### 2. Set up Slack Integration

1. Create a Slack app at https://api.slack.com/apps
2. Add the `chat:write` OAuth scope
3. Install the app to your workspace
4. Copy the Bot User OAuth Token

### 3. Choose an AI Provider

**Option A: OpenAI**
1. Get an API key from https://platform.openai.com/api-keys
2. Use `ai_provider: openai` in the action

**Option B: Claude**
1. Get an API key from https://console.anthropic.com/
2. Use `ai_provider: claude` in the action

### 4. Create the Workflow

Create `.github/workflows/release-notes.yml`:

```yaml
name: Generate Release Notes

on:
  schedule:
    # Run every Monday at 9 AM UTC
    - cron: '0 9 * * 1'
  workflow_dispatch:
    inputs:
      repos:
        description: 'Repositories to analyze'
        required: true
        default: 'myorg/frontend,myorg/backend'
      days_back:
        description: 'Days to look back'
        required: false
        default: '7'

jobs:
  generate-notes:
    runs-on: ubuntu-latest
    steps:
      - name: Generate Release Notes
        uses: your-org/release-notes@v1
        with:
          repos: ${{ github.event.inputs.repos || 'myorg/frontend,myorg/backend' }}
          github_token: ${{ secrets.GITHUB_TOKEN }}
          slack_bot_token: ${{ secrets.SLACK_BOT_TOKEN }}
          slack_channel: '#release-notes'
          ai_provider: openai
          openai_api_key: ${{ secrets.OPENAI_API_KEY }}
          days_back: ${{ github.event.inputs.days_back || 7 }}
```

### 5. Add Secrets

Add these secrets to your repository:

| Secret | Description |
|--------|-------------|
| `GITHUB_TOKEN` | GitHub Personal Access Token with repo access |
| `SLACK_BOT_TOKEN` | Slack Bot User OAuth Token |
| `OPENAI_API_KEY` | OpenAI API key (if using OpenAI) |
| `ANTHROPIC_API_KEY` | Anthropic API key (if using Claude) |

## Action Inputs

| Input | Required | Description | Default |
|-------|----------|-------------|---------|
| `repos` | Yes | Comma-separated list of repositories (e.g., "org1/repo1,org2/repo2") | - |
| `github_token` | Yes | GitHub Personal Access Token with repo access | - |
| `slack_bot_token` | Yes | Slack Bot Token | - |
| `slack_channel` | Yes | Slack channel to post to (e.g., #release-notes) | - |
| `ai_provider` | No | AI provider to use (openai or claude) | openai |
| `openai_api_key` | Yes* | OpenAI API key (required if ai_provider is openai) | - |
| `anthropic_api_key` | Yes* | Anthropic API key (required if ai_provider is claude) | - |
| `days_back` | No | Number of days to look back for PRs | 7 |

*Either `openai_api_key` OR `anthropic_api_key` is required, depending on the chosen provider.

## Action Outputs

| Output | Description |
|--------|-------------|
| `message` | The generated release notes message |
| `timestamp` | Timestamp of when the notes were generated |

## Example Output

The action generates release notes in the following format:

```
🗞 Release Notes

*myorg/frontend*: Added new user dashboard with improved navigation and performance optimizations.
• Add user dashboard with real-time data visualization
• Fix navigation menu responsiveness on mobile devices
• Optimize bundle size by 15% through code splitting

*myorg/backend*: Enhanced API performance and added new authentication features.
• Add JWT token refresh mechanism
• Fix database connection pooling issues
• Implement rate limiting for API endpoints

Dependency Updates: 3 dependency update(s) merged
```

## Publishing the Action

To make this action available for other organizations:

1. **Create a new repository** named `release-notes` in your organization
2. **Push the code** to the repository
3. **Create a release** with a semantic version tag (e.g., `v1.0.0`)
4. **Update the action reference** in the `action.yml` file to use your organization name

The action can then be used by other organizations as:
```yaml
uses: your-org/release-notes@v1
```

## Local Testing

### Quick Setup

For the easiest local testing experience:

```bash
# 1. Run the setup script
./setup_local.sh

# 2. Edit the .env file with your actual values
# 3. Run the script directly
python scripts/generate_release_notes.py --repos "your-org/your-repo" --days-back 7
```

### Manual Setup

If you prefer to set up manually:

#### 1. Create Environment File

Copy the example environment file and edit it with your values:

```bash
cp env.example .env
# Edit .env with your actual values
```

Required environment variables in `.env`:
```bash
# GitHub Configuration
GITHUB_TOKEN=your_github_personal_access_token

# AI Provider Configuration (choose one)
OPENAI_API_KEY=your_openai_api_key
# ANTHROPIC_API_KEY=your_anthropic_api_key

# Slack Configuration
SLACK_BOT_TOKEN=your_slack_bot_token
SLACK_CHANNEL=your_slack_channel

# Optional
DAYS_BACK=7                      # Default: 7
AI_PROVIDER=openai               # Default: openai
```

#### 2. Set Up Virtual Environment

```bash
# Create virtual environment
python3 -m venv .venv

# Activate it
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

#### 3. Run the Script

```bash
# Activate virtual environment first
source .venv/bin/activate

# Run the script directly
python scripts/generate_release_notes.py \
  --repos "myorg/repo1,myorg/repo2" \
  --days-back 7
```

## Dependencies

The action uses the following Python packages:

- `PyGithub`: GitHub API client
- `openai`: OpenAI API client
- `anthropic`: Claude API client
- `slack_sdk`: Slack API client

These are automatically installed during workflow execution.

## Error Handling

The action includes comprehensive error handling:

- **API Connection Tests**: Validates all API connections at startup
- **Graceful Degradation**: Falls back to basic summaries if AI provider fails
- **Repository-level Errors**: Continues processing other repositories if one fails
- **Detailed Logging**: Provides clear error messages for debugging

## Artifacts

The action creates artifacts containing the generated release notes message

These are stored for audit purposes and have a 30-day retention period.

## Troubleshooting

### Common Issues

1. **GitHub API Rate Limits**: Ensure your GitHub token has sufficient permissions and rate limits
2. **Slack Channel Access**: Verify the bot is added to the target channel
3. **AI API Limits**: Check your AI provider API usage and billing status
4. **Repository Access**: Ensure the GitHub token has access to all specified repositories

### Debug Mode

To enable debug logging, you can modify the Python script to use `logging.DEBUG` level:

```python
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test locally
5. Submit a pull request

## License

This project is licensed under the MIT License. 