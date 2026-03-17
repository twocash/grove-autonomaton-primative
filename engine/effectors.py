"""
effectors.py - MCP Effector Layer

External actions (Calendar, Gmail, etc.) are handled exclusively via
Model Context Protocol (MCP) servers. Every MCP action is strictly
governed by Zone classification.

CRITICAL: The most restrictive zone always wins.
"""

import yaml
from pathlib import Path
from typing import Optional, Any
from dataclasses import dataclass

from engine.telemetry import log_event
from engine.ux import ask_jidoka
from engine.profile import get_config_dir


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
    def reset_cache(cls) -> None:
        """Reset configuration cache (useful when switching profiles)."""
        cls._mcp_config = None
        cls._zones_schema = None
        cls._config_dir = None


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

        Sprint 2: Stub implementation returns mock success.
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

        # Sprint 2: Return stub success
        return {
            "success": True,
            "stub": True,
            "server": self.server,
            "capability": capability,
            "payload": payload,
            "message": f"[STUB] Would execute {capability} on {self.server}"
        }

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
    Execute an MCP action with full zone governance.

    CRITICAL GOVERNANCE LOGIC:
    1. Get the zone for the server+capability
    2. Get the zone for the domain
    3. The most restrictive zone wins
    4. If Yellow or Red, trigger Jidoka for user approval
    5. Log all outcomes to telemetry

    Args:
        server: MCP server name (e.g., 'google_calendar', 'gmail')
        capability: The capability to invoke (e.g., 'create_event', 'send_email')
        payload: Data to pass to the capability
        domain: The domain context (e.g., 'lessons', 'money')

    Returns:
        MCPActionResult with execution outcome
    """
    # Step 1: Compute effective zone
    server_zone = ConfigLoader.get_capability_zone(server, capability)
    domain_zone = ConfigLoader.get_domain_zone(domain)
    effective_zone = compute_effective_zone(server_zone, domain_zone)

    # Log the governance decision
    log_event(
        source="effector_governance",
        raw_transcript=f"MCP action: {server}.{capability}",
        zone_context=effective_zone,
        inferred={
            "server": server,
            "capability": capability,
            "domain": domain,
            "server_zone": server_zone,
            "domain_zone": domain_zone,
            "effective_zone": effective_zone
        }
    )

    # Step 2: Zone-based approval
    approved = False
    action_description = format_action_description(server, capability, payload)

    if effective_zone == "green":
        # Green zone: Auto-approve
        approved = True

    elif effective_zone == "yellow":
        # Yellow zone: One-thumb Jidoka approval
        result = ask_jidoka(
            context_message=f"YELLOW ZONE - External Action Requires Approval:\n\n{action_description}",
            options={
                "1": "Approve and execute",
                "2": "Reject and cancel"
            }
        )
        approved = (result == "1")

    elif effective_zone == "red":
        # Red zone: Explicit approval with full context
        result = ask_jidoka(
            context_message=(
                f"RED ZONE - High-Stakes Action Requires Explicit Approval:\n\n"
                f"{action_description}\n\n"
                f"Server: {server}\n"
                f"Capability: {capability}\n"
                f"Domain: {domain}\n"
                f"Payload: {payload}"
            ),
            options={
                "1": "I understand the risks - APPROVE",
                "2": "REJECT and cancel"
            }
        )
        approved = (result == "1")

    # Step 3: Handle rejection
    if not approved:
        log_event(
            source="effector_rejection",
            raw_transcript=f"User rejected MCP action: {server}.{capability}",
            zone_context=effective_zone,
            inferred={
                "server": server,
                "capability": capability,
                "domain": domain,
                "reason": "user_rejected"
            }
        )
        return MCPActionResult(
            success=False,
            server=server,
            capability=capability,
            payload=payload,
            effective_zone=effective_zone,
            approved=False,
            error="Action rejected by user"
        )

    # Step 4: Execute the action
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
                approved=True,
                error=f"Failed to connect to {server}"
            )

    execution_result = client.execute(capability, payload)

    # Step 5: Log execution outcome
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
        approved=True,
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
