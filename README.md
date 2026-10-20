# Plex Discord Stats

Lightweight Discord voice-channel counters backed by Tautulli. Runs once on startup and hourly thereafter. Uses only Python's standard library, no bot gateway, no database, no exposed ports.

## Requirements

- Tautulli reachable from the Docker host/container (use a LAN URL, not `localhost`).
- Discord bot added to your server with **Manage Channels** permission for the three voice channels.
- Three existing **voice channels** under the specified Discord category.

## Setup

1. Create a Discord application and bot at https://discord.com/developers/applications . Copy the **bot token** (not application ID). Under OAuth2 URL Generator select `bot`, permission `Manage Channels`, and invite it to your server. Grant access to the relevant category/channels.
2. In Discord, enable **Developer Mode** (User Settings > Advanced), then right-click the server, category and each voice channel to **Copy ID**.
3. In Tautulli, get the API key under Settings > Web Interface > API. Set TAUTULLI_URL to a URL accessible from the container, e.g. `http://192.168.1.30:8181`.
4. Create a GitHub repository named `plex-discord-stats`, upload these files including `.github/workflows/docker-publish.yml`, and push to `main`. The GitHub Action builds and publishes `ghcr.io/USERNAME/plex-discord-stats:latest`. In GitHub package settings, set visibility to public for anonymous pulls, or authenticate Docker/your stack manager to GHCR.
5. In Dockhand or Portainer, create a stack from `compose.yaml`, replace the image username and all placeholder variables, and deploy. For a public repository, keep tokens out of GitHub; configure secrets only in your stack manager. If you store the compose file in GitHub, replace literal secrets with `${VARIABLE}` references and configure them in your deployment environment.
6. Check container logs for `Library totals` and `Updated Movies: ...` etc.

## Behavior

- Totals are summed across all Tautulli movie and show libraries. Series use `count`, episodes use `child_count` in Tautulli's `get_libraries` response.
- The bot verifies that channel IDs belong to the configured server and category, and that they are voice channels.
- No updates occur if names already match; a failed Tautulli request leaves current names untouched.
- Each channel update is independent. Discord rate limiting may defer updates until a later cycle.
- Interval minimum: 900 seconds; default: 3600 seconds.

## Troubleshooting

- `Tautulli get_libraries did not succeed`: verify the API key and URL.
- `did not return both movie and show libraries`: Tautulli must report at least one movie and one TV library in this version.
- HTTP 403: bot needs Manage Channels permission.
- HTTP 404: wrong channel ID or bot has no access.
- If Docker cannot reach Tautulli, check host IP, Docker networking and Tautulli binding/firewall.
