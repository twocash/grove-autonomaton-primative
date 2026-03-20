"""
effectors.py - MCP Effector Layer

External actions (Calendar, Gmail, etc.) are handled exclusively via
Model Context Protocol (MCP) servers. Every MCP action is strictly
governed by Zone classification.

CRITICAL: The most restrictive zone always wins.

Sprint 3: Real Google API integration via google-api-python-client.
OAuth tokens are stored in profiles/{profile}/config/auth/
"""

import yaml
import os
import base64
from pathlib import Path
from typing import Optional, Any
from dataclasses import dataclass
from email.mime.text import MIMEText

from engine.telemetry import log_event
from engine.profile import get_config_dir
# Note: ask_jidoka removed in Sprint 3.5 - Zone governance now handled by pipeline Stage 4


# Zone priority (higher = more restrictive)
ZONE_PRIORITY = {
    "green": 1,
    "yellow": 2,
    "red": 3
}


@dataclass
class MCPActionResult:
    """Result of an MCP action execution."""
    success: bool
    server: str
    capability: str
    payload: dict
    effective_zone: str
    approved: bool
    result: Any = None
    error: Optional[str] = None


class ConfigLoader:
    """
    Loads and caches configuration from YAML files.
    """
    _mcp_config: Optional[dict] = None
    _zones_schema: Optional[dict] = None
    _config_dir: Optional[Path] = None

    @classmethod
    def _get_config_dir(cls) -> Path:
        """Get the config directory for the active profile."""
        if cls._config_dir is None:
            cls._config_dir = get_config_dir()
        return cls._config_dir

    @classmethod
    def load_mcp_config(cls) -> dict:
        """Load MCP server configuration."""
        if cls._mcp_config is None:
            mcp_path = cls._get_config_dir() / "mcp.config"
            if mcp_path.exists():
                with open(mcp_path, "r", encoding="utf-8") as f:
                    cls._mcp_config = yaml.safe_load(f) or {}
            else:
                cls._mcp_config = {}
        return cls._mcp_config

    @classmethod
    def load_zones_schema(cls) -> dict:
        """Load zone governance schema."""
        if cls._zones_schema is None:
            zones_path = cls._get_config_dir() / "zones.schema"
            if zones_path.exists():
                with open(zones_path, "r", encoding="utf-8") as f:
                    cls._zones_schema = yaml.safe_load(f) or {}
            else:
                cls._zones_schema = {}
        return cls._zones_schema

    @classmethod
    def get_server_config(cls, server: str) -> Optional[dict]:
        """Get configuration for a specific MCP server."""
        config = cls.load_mcp_config()
        return config.get("servers", {}).get(server)

    @classmethod
    def get_domain_config(cls, domain: str) -> Optional[dict]:
        """Get configuration for a specific domain."""
        schema = cls.load_zones_schema()
        return schema.get("domains", {}).get(domain)

    @classmethod
    def get_capability_zone(cls, server: str, capability: str) -> str:
        """Get the zone for a specific server capability."""
        server_config = cls.get_server_config(server)
        if not server_config:
            return "red"  # Unknown server = most restrictive

        # Check capability-specific zone first
        governance = server_config.get("governance", {})
        cap_governance = governance.get(capability, {})
        if "zone" in cap_governance:
            return cap_governance["zone"]

        # Fall back to server default zone
        return server_config.get("zone", "yellow")

    @classmethod
    def get_domain_zone(cls, domain: str) -> str:
        """Get the default zone for a domain."""
        domain_config = cls.get_domain_config(domain)
        if not domain_config:
            return "yellow"  # Unknown domain = cautious default
        return domain_config.get("default_zone", "yellow")

    @classmethod
    def get_server_scopes(cls, server: str) -> list:
        """Load OAuth scopes for a server from mcp.config.

        Returns list of scope strings, or empty list if not configured.
        """
        if cls._mcp_config is None:
            cls.load_mcp_config()
        if cls._mcp_config is None:
            return []
        servers = cls._mcp_config.get("servers", {})
        server_config = servers.get(server, {})
        return server_config.get("auth", {}).get("scopes", [])

    @classmethod
    def get_configured_servers(cls) -> list:
        """Return list of server names from mcp.config."""
        if cls._mcp_config is None:
            cls.load_mcp_config()
        if cls._mcp_config is None:
            return []
        return list(cls._mcp_config.get("servers", {}).keys())

    @classmethod
    def get_server_status(cls, server: str) -> str:
        """Return server status from mcp.config (active/stub/not_implemented)."""
        if cls._mcp_config is None:
            cls.load_mcp_config()
        if cls._mcp_config is None:
            return "unknown"
        servers = cls._mcp_config.get("servers", {})
        return servers.get(server, {}).get("status", "unknown")

    @classmethod
    def reset_cache(cls) -> None:
        """Reset configuration cache (useful when switching profiles)."""
        cls._mcp_config = None
        cls._zones_schema = None
        cls._config_dir = None


# =========================================================================
# Google API Service Management
# =========================================================================


def get_auth_dir() -> Path:
    """Get the auth directory for OAuth token storage."""
    auth_dir = get_config_dir() / "auth"
    auth_dir.mkdir(parents=True, exist_ok=True)
    return auth_dir


def get_google_calendar_service():
    """
    Get authenticated Google Calendar service.

    Uses OAuth2 credentials stored in profiles/{profile}/config/auth/.
    If no valid token exists, initiates OAuth flow.

    Returns:
        Google Calendar API service object or None if auth fails
    """
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError:
        # Google API libraries not installed
        return None

    # Load scopes from config (fallback for missing config)
    scopes = ConfigLoader.get_server_scopes("google_calendar")
    if not scopes:
        scopes = ['https://www.googleapis.com/auth/calendar']

    token_path = get_auth_dir() / "calendar_token.json"
    credentials_path = get_auth_dir() / "credentials.json"

    creds = None

    # Load existing token
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), scopes)

    # Refresh or get new token
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None

        if not creds:
            if not credentials_path.exists():
                # No credentials file - cannot authenticate
                return None

            flow = InstalledAppFlow.from_client_secrets_file(
                str(credentials_path), scopes
            )

            # Use console flow for headless environments
            if is_headless_environment():
                creds = flow.run_console()
            else:
                creds = flow.run_local_server(port=0)

        # Save the token
        with open(token_path, 'w') as token_file:
            token_file.write(creds.to_json())

    return build('calendar', 'v3', credentials=creds)


def get_gmail_service():
    """
    Get authenticated Gmail service.

    Uses OAuth2 credentials stored in profiles/{profile}/config/auth/.
    If no valid token exists, initiates OAuth flow.

    Returns:
        Gmail API service object or None if auth fails
    """
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError:
        # Google API libraries not installed
        return None

    # Load scopes from config (fallback for missing config)
    scopes = ConfigLoader.get_server_scopes("gmail")
    if not scopes:
        scopes = ['https://www.googleapis.com/auth/gmail.modify']

    token_path = get_auth_dir() / "gmail_token.json"
    credentials_path = get_auth_dir() / "credentials.json"

    creds = None

    # Load existing token
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), scopes)

    # Refresh or get new token
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None

        if not creds:
            if not credentials_path.exists():
                # No credentials file - cannot authenticate
                return None

            flow = InstalledAppFlow.from_client_secrets_file(
                str(credentials_path), scopes
            )

            # Use console flow for headless environments
            if is_headless_environment():
                creds = flow.run_console()
            else:
                creds = flow.run_local_server(port=0)

        # Save the token
        with open(token_path, 'w') as token_file:
            token_file.write(creds.to_json())

    return build('gmail', 'v1', credentials=creds)


# =========================================================================
# Zone Computation
# =========================================================================

def compute_effective_zone(server_zone: str, domain_zone: str) -> str:
    """
    Compute the effective zone by taking the most restrictive.

    Zone priority: red > yellow > green
    """
    server_priority = ZONE_PRIORITY.get(server_zone, 3)
    domain_priority = ZONE_PRIORITY.get(domain_zone, 3)

    # Most restrictive wins
    if server_priority >= domain_priority:
        return server_zone
    return domain_zone


def format_action_description(server: str, capability: str, payload: dict) -> str:
    """
    Format a human-readable action description for Jidoka prompts.
    Uses templates from mcp.config if available.
    """
    server_config = ConfigLoader.get_server_config(server)
    if not server_config:
        return f"Execute {capability} on {server}"

    governance = server_config.get("governance", {})
    cap_governance = governance.get(capability, {})
    template = cap_governance.get("template")

    if template:
        try:
            return template.format(**payload)
        except KeyError:
            pass

    # Fallback to generic description
    server_name = server_config.get("name", server)
    return f"{capability} via {server_name}: {payload}"


def is_headless_environment() -> bool:
    """
    Detect if running in a headless environment (Docker, SSH, etc.).

    Returns True if no display is available for browser OAuth.
    """
    import os

    # Check common headless indicators
    if os.environ.get("DOCKER_CONTAINER"):
        return True
    if os.environ.get("SSH_CLIENT") or os.environ.get("SSH_TTY"):
        return True
    if not os.environ.get("DISPLAY") and os.name != "nt":
        return True

    return False


@dataclass
class AuthState:
    """Tracks authentication state for an MCP server."""
    authenticated: bool = False
    auth_url: Optional[str] = None
    requires_user_action: bool = False
    error: Optional[str] = None


class MCPClient:
    """
    Generic MCP client wrapper.

    In Sprint 2, this is a stub that simulates MCP connections.
    Future sprints will implement actual MCP protocol communication.

    OAUTH HANDLING:
    When running in headless environments (Docker, SSH), the client
    will output an auth URL to the console rather than attempting
    to open a browser. The Operator can then present this to the user.
    """

    def __init__(self, server: str):
        self.server = server
        self.config = ConfigLoader.get_server_config(server)
        self.connected = False
        self.auth_state = AuthState()
        self.headless = is_headless_environment()

    def connect(self) -> bool:
        """
        Initialize connection to the MCP server.

        Sprint 2: Stub implementation.
        For OAuth servers in headless mode, generates auth URL.
        """
        if not self.config:
            return False

        status = self.config.get("status", "stub")
        auth_config = self.config.get("auth", {})

        if status == "stub":
            # Check if this would require OAuth in production
            if auth_config.get("type") == "oauth2" and self.headless:
                # Simulate OAuth URL generation for headless environments
                self.auth_state = self._generate_headless_auth()
                if self.auth_state.requires_user_action:
                    self._print_auth_instructions()

            # Simulate successful connection for stub servers
            self.connected = True
            return True

        # Future: Actual MCP connection logic with real OAuth
        return False

    def _generate_headless_auth(self) -> AuthState:
        """
        Generate OAuth auth state for headless environments.

        In production, this would generate a real OAuth URL.
        Sprint 2: Returns stub auth state.
        """
        server_name = self.config.get("name", self.server)
        scopes = self.config.get("auth", {}).get("scopes", [])

        # Stub: Simulate that auth is already complete
        # In production, this would check token validity
        return AuthState(
            authenticated=True,  # Stub assumes auth is done
            auth_url=None,
            requires_user_action=False
        )

    def _generate_real_auth_url(self) -> AuthState:
        """
        Generate a real OAuth authorization URL.

        This would be called in production when tokens are missing/expired.
        Returns an AuthState with the URL for user action.

        Sprint 2: Stub - shows what production would do.
        """
        server_name = self.config.get("name", self.server)
        scopes = self.config.get("auth", {}).get("scopes", [])

        # In production, this would call the actual OAuth library
        # to generate a proper authorization URL
        mock_url = f"https://accounts.google.com/oauth/authorize?scope={'+'.join(scopes)}&client_id=STUB"

        return AuthState(
            authenticated=False,
            auth_url=mock_url,
            requires_user_action=True
        )

    def _print_auth_instructions(self) -> None:
        """
        Print OAuth instructions for headless environments.

        This allows Docker/SSH users to authenticate via external browser.
        """
        if not self.auth_state.auth_url:
            return

        server_name = self.config.get("name", self.server)
        print()
        print("=" * 60)
        print(f"  AUTHENTICATION REQUIRED: {server_name}")
        print("=" * 60)
        print()
        print(f"  I need permission to access your {server_name}.")
        print("  Please click this link to authorize:")
        print()
        print(f"  {self.auth_state.auth_url}")
        print()
        print("  After authorizing, the session will continue.")
        print("=" * 60)
        print()

    def request_auth(self) -> AuthState:
        """
        Request authentication for servers that need it.

        Call this when you need to prompt the user for OAuth.
        Returns AuthState with URL if user action is required.
        """
        if self.auth_state.authenticated:
            return self.auth_state

        self.auth_state = self._generate_real_auth_url()
        if self.auth_state.requires_user_action:
            self._print_auth_instructions()

        return self.auth_state

    def execute(self, capability: str, payload: dict) -> dict:
        """
        Execute a capability on the MCP server.

        Sprint 3: Real Google API integration for supported servers.
        Falls back to stub for unsupported capabilities.
        """
        if not self.connected:
            return {
                "success": False,
                "error": "Not connected to MCP server"
            }

        # Verify capability is supported
        capabilities = self.config.get("capabilities", [])
        if capability not in capabilities:
            return {
                "success": False,
                "error": f"Capability '{capability}' not supported by {self.server}"
            }

        # Service implementation registry — maps server names to methods.
        # The registry is internal to the effector layer. The server NAMES
        # come from mcp.config. The IMPLEMENTATIONS are engine code.
        _service_registry = {
            "google_calendar": self._execute_calendar,
            "gmail": self._execute_gmail,
        }

        handler = _service_registry.get(self.server)
        if handler:
            return handler(capability, payload)

        # Fallback to stub for unimplemented servers
        return {
            "success": True,
            "stub": True,
            "server": self.server,
            "capability": capability,
            "payload": payload,
            "message": f"[STUB] Would execute {capability} on {self.server}"
        }

    def _execute_calendar(self, capability: str, payload: dict) -> dict:
        """
        Execute Google Calendar API operations.
        """
        service = get_google_calendar_service()

        if service is None:
            # Fall back to stub if API not available
            return {
                "success": True,
                "stub": True,
                "message": f"[STUB - No Google API] Would execute {capability}",
                "payload": payload
            }

        try:
            if capability == "create_event":
                # Build event from payload
                event = {
                    'summary': payload.get('summary', 'Untitled Event'),
                    'start': payload.get('start', {}),
                    'end': payload.get('end', {}),
                }
                if payload.get('location'):
                    event['location'] = payload['location']
                if payload.get('description'):
                    event['description'] = payload['description']

                result = service.events().insert(
                    calendarId='primary',
                    body=event
                ).execute()

                return {
                    "success": True,
                    "server": self.server,
                    "capability": capability,
                    "event_id": result.get('id'),
                    "html_link": result.get('htmlLink'),
                    "message": f"Created event: {result.get('summary')}"
                }

            elif capability == "list_events":
                # List upcoming events
                from datetime import datetime
                now = datetime.utcnow().isoformat() + 'Z'
                max_results = payload.get('max_results', 10)

                result = service.events().list(
                    calendarId='primary',
                    timeMin=now,
                    maxResults=max_results,
                    singleEvents=True,
                    orderBy='startTime'
                ).execute()

                events = result.get('items', [])
                return {
                    "success": True,
                    "server": self.server,
                    "capability": capability,
                    "events": events,
                    "count": len(events),
                    "message": f"Retrieved {len(events)} events"
                }

            elif capability == "delete_event":
                event_id = payload.get('event_id')
                if not event_id:
                    return {"success": False, "error": "Missing event_id"}

                service.events().delete(
                    calendarId='primary',
                    eventId=event_id
                ).execute()

                return {
                    "success": True,
                    "server": self.server,
                    "capability": capability,
                    "event_id": event_id,
                    "message": f"Deleted event: {event_id}"
                }

            elif capability == "update_event":
                event_id = payload.get('event_id')
                if not event_id:
                    return {"success": False, "error": "Missing event_id"}

                # Get existing event
                event = service.events().get(
                    calendarId='primary',
                    eventId=event_id
                ).execute()

                # Update fields from payload
                for key in ['summary', 'location', 'description', 'start', 'end']:
                    if key in payload:
                        event[key] = payload[key]

                result = service.events().update(
                    calendarId='primary',
                    eventId=event_id,
                    body=event
                ).execute()

                return {
                    "success": True,
                    "server": self.server,
                    "capability": capability,
                    "event_id": event_id,
                    "message": f"Updated event: {result.get('summary')}"
                }

        except Exception as e:
            return {
                "success": False,
                "server": self.server,
                "capability": capability,
                "error": str(e)
            }

        return {"success": False, "error": f"Unknown capability: {capability}"}

    def _execute_gmail(self, capability: str, payload: dict) -> dict:
        """
        Execute Gmail API operations.
        """
        service = get_gmail_service()

        if service is None:
            # Fall back to stub if API not available
            return {
                "success": True,
                "stub": True,
                "message": f"[STUB - No Google API] Would execute {capability}",
                "payload": payload
            }

        try:
            if capability == "send_email":
                # Build email message
                to = payload.get('to', '')
                subject = payload.get('subject', '')
                body = payload.get('body', '')

                message = MIMEText(body)
                message['to'] = to
                message['subject'] = subject

                raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
                send_message = {'raw': raw}

                result = service.users().messages().send(
                    userId='me',
                    body=send_message
                ).execute()

                return {
                    "success": True,
                    "server": self.server,
                    "capability": capability,
                    "message_id": result.get('id'),
                    "thread_id": result.get('threadId'),
                    "message": f"Sent email: {subject}"
                }

            elif capability == "draft_email":
                # Create email draft
                to = payload.get('to', '')
                subject = payload.get('subject', '')
                body = payload.get('body', '')

                message = MIMEText(body)
                message['to'] = to
                message['subject'] = subject

                raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
                draft_body = {'message': {'raw': raw}}

                result = service.users().drafts().create(
                    userId='me',
                    body=draft_body
                ).execute()

                return {
                    "success": True,
                    "server": self.server,
                    "capability": capability,
                    "draft_id": result.get('id'),
                    "message": f"Created draft: {subject}"
                }

            elif capability == "list_threads":
                max_results = payload.get('max_results', 10)

                result = service.users().threads().list(
                    userId='me',
                    maxResults=max_results
                ).execute()

                threads = result.get('threads', [])
                return {
                    "success": True,
                    "server": self.server,
                    "capability": capability,
                    "threads": threads,
                    "count": len(threads),
                    "message": f"Retrieved {len(threads)} threads"
                }

        except Exception as e:
            return {
                "success": False,
                "server": self.server,
                "capability": capability,
                "error": str(e)
            }

        return {"success": False, "error": f"Unknown capability: {capability}"}

    def disconnect(self) -> None:
        """Disconnect from the MCP server."""
        self.connected = False
        self.auth_state = AuthState()


# Client connection pool
_client_pool: dict[str, MCPClient] = {}


def get_mcp_client(server: str) -> MCPClient:
    """Get or create an MCP client for the given server."""
    if server not in _client_pool:
        _client_pool[server] = MCPClient(server)
    return _client_pool[server]


def execute_mcp_action(
    server: str,
    capability: str,
    payload: dict,
    domain: str
) -> MCPActionResult:
    """
    Execute an MCP action (post-approval).

    CRITICAL ARCHITECTURAL CHANGE (Sprint 3.5):
    - Zone governance moved to pipeline Stage 4
    - This function only handles authentication and execution
    - Approval is already granted by the pipeline before this is called

    The effector layer responsibility is:
    1. Authentication (OAuth token handling)
    2. API execution
    3. Execution telemetry

    Zone computation and Jidoka prompts are handled by Stage 4.

    Args:
        server: MCP server name (e.g., 'google_calendar', 'gmail')
        capability: The capability to invoke (e.g., 'create_event', 'send_email')
        payload: Data to pass to the capability
        domain: The domain context (for telemetry only)

    Returns:
        MCPActionResult with execution outcome
    """
    # Compute effective zone for telemetry (NOT for governance)
    server_zone = ConfigLoader.get_capability_zone(server, capability)
    domain_zone = ConfigLoader.get_domain_zone(domain)
    effective_zone = compute_effective_zone(server_zone, domain_zone)

    # Log the execution attempt (governance already handled by Stage 4)
    log_event(
        source="effector_execution_start",
        raw_transcript=f"MCP action: {server}.{capability}",
        zone_context=effective_zone,
        inferred={
            "server": server,
            "capability": capability,
            "domain": domain,
            "effective_zone": effective_zone
        }
    )

    # Step 1: Connect to MCP server (handles OAuth if needed)
    client = get_mcp_client(server)
    if not client.connected:
        if not client.connect():
            log_event(
                source="effector_error",
                raw_transcript=f"Failed to connect to MCP server: {server}",
                zone_context=effective_zone,
                inferred={"server": server, "error": "connection_failed"}
            )
            return MCPActionResult(
                success=False,
                server=server,
                capability=capability,
                payload=payload,
                effective_zone=effective_zone,
                approved=True,  # Approval was handled by pipeline
                error=f"Failed to connect to {server}"
            )

    # Step 2: Execute the action
    try:
        execution_result = client.execute(capability, payload)
    except Exception as e:
        # Log execution failure
        log_event(
            source="effector_error",
            raw_transcript=f"MCP execution failed: {server}.{capability}",
            zone_context=effective_zone,
            inferred={
                "server": server,
                "capability": capability,
                "error": str(e)
            }
        )
        return MCPActionResult(
            success=False,
            server=server,
            capability=capability,
            payload=payload,
            effective_zone=effective_zone,
            approved=True,
            error=str(e)
        )

    # Step 3: Log execution outcome
    log_event(
        source="effector_execution",
        raw_transcript=f"Executed MCP action: {server}.{capability}",
        zone_context=effective_zone,
        inferred={
            "server": server,
            "capability": capability,
            "domain": domain,
            "success": execution_result.get("success", False),
            "stub": execution_result.get("stub", False)
        }
    )

    return MCPActionResult(
        success=execution_result.get("success", False),
        server=server,
        capability=capability,
        payload=payload,
        effective_zone=effective_zone,
        approved=True,  # Approval was handled by pipeline Stage 4
        result=execution_result,
        error=execution_result.get("error")
    )


def list_available_servers() -> list[str]:
    """List all configured MCP servers."""
    config = ConfigLoader.load_mcp_config()
    return list(config.get("servers", {}).keys())


def list_server_capabilities(server: str) -> list[str]:
    """List capabilities for a specific MCP server."""
    server_config = ConfigLoader.get_server_config(server)
    if not server_config:
        return []
    return server_config.get("capabilities", [])
