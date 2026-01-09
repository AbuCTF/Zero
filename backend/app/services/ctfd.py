"""
CTFd Integration Service

Handles:
- User provisioning to CTFd
- Team sync after event
- Scoreboard/results sync
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

import httpx

from app.utils.security import decrypt_data


@dataclass
class CTFdUser:
    """User data from CTFd."""
    id: int
    name: str
    email: str
    team_id: Optional[int] = None
    score: int = 0
    place: Optional[int] = None


@dataclass
class CTFdTeam:
    """Team data from CTFd."""
    id: int
    name: str
    score: int = 0
    place: Optional[int] = None
    members: List[CTFdUser] = None
    
    def __post_init__(self):
        if self.members is None:
            self.members = []


@dataclass
class CTFdSyncResult:
    """Result of syncing with CTFd."""
    success: bool
    users_synced: int = 0
    teams_synced: int = 0
    error: Optional[str] = None


class CTFdClient:
    """
    Client for interacting with CTFd API.
    
    Supports CTFd v3.x API.
    """
    
    def __init__(self, base_url: str, api_key: str):
        """
        Initialize CTFd client.
        
        Args:
            base_url: CTFd instance URL (e.g., https://ctf.example.com)
            api_key: CTFd API key (Admin token)
        """
        self.base_url = base_url.rstrip("/")
        
        # Decrypt if encrypted
        if api_key and api_key.startswith("gAAAAA"):
            api_key = decrypt_data(api_key)
        
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Token {api_key}",
            "Content-Type": "application/json",
        }
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Make API request to CTFd."""
        url = f"{self.base_url}/api/v1{endpoint}"
        
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method,
                url,
                headers=self.headers,
                timeout=30,
                **kwargs,
            )
            response.raise_for_status()
            return response.json()
    
    async def health_check(self) -> bool:
        """Check if CTFd is accessible."""
        try:
            await self._request("GET", "/users/me")
            return True
        except Exception:
            return False
    
    # -------------------------------------------------------------------------
    # User Operations
    # -------------------------------------------------------------------------
    
    async def create_user(
        self,
        name: str,
        email: str,
        password: str,
        verified: bool = True,
        hidden: bool = False,
        banned: bool = False,
        user_type: str = "user",
    ) -> Dict[str, Any]:
        """
        Create a new user in CTFd.
        
        Args:
            name: Username
            email: Email address
            password: Plain text password
            verified: Whether email is verified
            hidden: Whether user is hidden from scoreboard
            banned: Whether user is banned
            user_type: 'user' or 'admin'
            
        Returns:
            Created user data
        """
        data = {
            "name": name,
            "email": email,
            "password": password,
            "verified": verified,
            "hidden": hidden,
            "banned": banned,
            "type": user_type,
        }
        
        result = await self._request("POST", "/users", json=data)
        return result.get("data", {})
    
    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user by ID."""
        try:
            result = await self._request("GET", f"/users/{user_id}")
            return result.get("data")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise
    
    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email."""
        result = await self._request("GET", "/users", params={"q": email, "field": "email"})
        users = result.get("data", [])
        return users[0] if users else None
    
    async def get_users(self, page: int = 1, per_page: int = 100) -> List[Dict[str, Any]]:
        """Get all users with pagination."""
        result = await self._request(
            "GET",
            "/users",
            params={"page": page, "per_page": per_page},
        )
        return result.get("data", [])
    
    async def delete_user(self, user_id: int) -> bool:
        """Delete a user."""
        try:
            await self._request("DELETE", f"/users/{user_id}")
            return True
        except httpx.HTTPStatusError:
            return False
    
    # -------------------------------------------------------------------------
    # Team Operations
    # -------------------------------------------------------------------------
    
    async def create_team(
        self,
        name: str,
        password: str,
        captain_id: Optional[int] = None,
        hidden: bool = False,
        banned: bool = False,
    ) -> Dict[str, Any]:
        """Create a new team in CTFd."""
        data = {
            "name": name,
            "password": password,
            "hidden": hidden,
            "banned": banned,
        }
        
        if captain_id:
            data["captain_id"] = captain_id
        
        result = await self._request("POST", "/teams", json=data)
        return result.get("data", {})
    
    async def get_team(self, team_id: int) -> Optional[Dict[str, Any]]:
        """Get team by ID."""
        try:
            result = await self._request("GET", f"/teams/{team_id}")
            return result.get("data")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise
    
    async def get_teams(self, page: int = 1, per_page: int = 100) -> List[Dict[str, Any]]:
        """Get all teams with pagination."""
        result = await self._request(
            "GET",
            "/teams",
            params={"page": page, "per_page": per_page},
        )
        return result.get("data", [])
    
    async def get_team_members(self, team_id: int) -> List[Dict[str, Any]]:
        """Get members of a team."""
        result = await self._request("GET", f"/teams/{team_id}/members")
        return result.get("data", [])
    
    async def add_user_to_team(self, team_id: int, user_id: int) -> bool:
        """Add a user to a team."""
        try:
            await self._request(
                "POST",
                f"/teams/{team_id}/members",
                json={"user_id": user_id},
            )
            return True
        except httpx.HTTPStatusError:
            return False
    
    # -------------------------------------------------------------------------
    # Scoreboard Operations
    # -------------------------------------------------------------------------
    
    async def get_scoreboard(self) -> List[Dict[str, Any]]:
        """Get the current scoreboard."""
        result = await self._request("GET", "/scoreboard")
        return result.get("data", [])
    
    async def get_standings(self, count: int = 100) -> List[Dict[str, Any]]:
        """
        Get top N standings.
        
        CTFd API: GET /scoreboard/top/{count}
        Returns dict with keys like "1", "2", etc. for each position
        Each position contains: id, name, solves, score, (and members for teams)
        """
        result = await self._request(
            "GET",
            f"/scoreboard/top/{count}",  # Path param, not query param
        )
        # CTFd returns {"1": {...}, "2": {...}, ...} format
        data = result.get("data", {})
        
        # Convert dict format to list sorted by position
        standings = []
        for pos in sorted(data.keys(), key=lambda x: int(x) if x.isdigit() else 999):
            entry = data[pos]
            entry["_position"] = int(pos) if pos.isdigit() else 999
            standings.append(entry)
        return standings
    
    # -------------------------------------------------------------------------
    # Challenges (for stats)
    # -------------------------------------------------------------------------
    
    async def get_challenges(self) -> List[Dict[str, Any]]:
        """Get all challenges."""
        result = await self._request("GET", "/challenges")
        return result.get("data", [])
    
    async def get_submissions(
        self,
        user_id: Optional[int] = None,
        challenge_id: Optional[int] = None,
        type_filter: str = "correct",
    ) -> List[Dict[str, Any]]:
        """Get submissions."""
        params = {"type": type_filter}
        if user_id:
            params["user_id"] = user_id
        if challenge_id:
            params["challenge_id"] = challenge_id
        
        result = await self._request("GET", "/submissions", params=params)
        return result.get("data", [])


class CTFdSyncService:
    """
    Service for syncing data between ZeroPool and CTFd.
    
    This service handles:
    1. Provisioning ZeroPool participants to CTFd
    2. Syncing final rankings/scores from CTFd back to ZeroPool
    """
    
    def __init__(self, ctfd_url: str, api_key: str, db=None):
        """
        Initialize sync service.
        
        Args:
            ctfd_url: CTFd instance URL
            api_key: CTFd API key (decrypted)
            db: Optional database session for updates
        """
        self.client = CTFdClient(ctfd_url, api_key)
        self.db = db
    
    async def provision_user(
        self,
        username: str,
        email: str,
        password: str,
    ) -> tuple[bool, Optional[int], Optional[str]]:
        """
        Provision a new user to CTFd.
        
        Args:
            username: Username
            email: Email address
            password: Plain text password
            
        Returns:
            Tuple of (success, ctfd_user_id, error_message)
        """
        try:
            # Check if user already exists
            existing = await self.client.get_user_by_email(email)
            if existing:
                return True, existing.get("id"), None
            
            # Create user
            user = await self.client.create_user(
                name=username,
                email=email,
                password=password,
                verified=True,
            )
            
            return True, user.get("id"), None
            
        except httpx.HTTPStatusError as e:
            return False, None, f"CTFd API error: {e.response.status_code}"
        except Exception as e:
            return False, None, str(e)
    
    async def sync_results_for_event(self, event_id: UUID) -> List[Dict]:
        """
        Sync final results from CTFd and update participant rankings.
        
        This fetches the scoreboard from CTFd and updates each participant's
        rank and score in the ZeroPool database.
        
        CTFd /scoreboard/top/{count} returns format:
        {
            "data": {
                "1": {"id": 1, "name": "Team A", "score": 500, "members": [...]},
                "2": {"id": 2, "name": "Team B", "score": 400, "members": [...]}
            }
        }
        
        Args:
            event_id: The event ID to sync
            
        Returns:
            List of updated participant info dicts
        """
        from sqlalchemy import select
        from app.models import Participant, Team, Event
        
        if not self.db:
            raise ValueError("Database session required for sync")
        
        try:
            # Get event settings to determine team mode
            result = await self.db.execute(
                select(Event).where(Event.id == event_id)
            )
            event = result.scalar_one_or_none()
            if not event:
                raise ValueError("Event not found")
            
            is_team_mode = event.settings.get("team_mode", False) if event.settings else False
            
            # Get scoreboard from CTFd
            standings = await self.client.get_standings(count=1000)
            
            updated = []
            
            for entry in standings:
                rank = entry.get("_position", 0)
                score = entry.get("score", 0)
                account_id = entry.get("id")
                account_name = entry.get("name", "")
                
                if is_team_mode:
                    # Team mode - match by team name or id
                    # CTFd returns team info directly in standings for team mode
                    team_result = await self.db.execute(
                        select(Team).where(
                            Team.event_id == event_id,
                            Team.name == account_name,
                        )
                    )
                    team = team_result.scalar_one_or_none()
                    
                    if team:
                        # Get all participants in this team
                        members_result = await self.db.execute(
                            select(Participant).where(
                                Participant.event_id == event_id,
                                Participant.team_id == team.id,
                            )
                        )
                        team_members = members_result.scalars().all()
                        
                        for participant in team_members:
                            participant.rank = rank
                            participant.score = score
                            updated.append({
                                "id": str(participant.id),
                                "name": participant.name,
                                "team": team.name,
                                "rank": rank,
                                "score": score,
                            })
                else:
                    # User mode - try to match by ctfd_user_id or name
                    participant = None
                    
                    # First try by ctfd_user_id
                    if account_id:
                        result = await self.db.execute(
                            select(Participant).where(
                                Participant.event_id == event_id,
                                Participant.ctfd_user_id == account_id,
                            )
                        )
                        participant = result.scalar_one_or_none()
                    
                    # If not found, try by name match
                    if not participant and account_name:
                        result = await self.db.execute(
                            select(Participant).where(
                                Participant.event_id == event_id,
                                Participant.name == account_name,
                            )
                        )
                        participant = result.scalar_one_or_none()
                    
                    if participant:
                        participant.rank = rank
                        participant.score = score
                        updated.append({
                            "id": str(participant.id),
                            "name": participant.name,
                            "rank": rank,
                            "score": score,
                        })
            
            await self.db.flush()
            return updated
            
        except Exception as e:
            raise RuntimeError(f"CTFd sync failed: {str(e)}")
    
    async def provision_users_for_event(self, event_id: UUID) -> int:
        """
        Provision all verified participants to CTFd.
        
        Args:
            event_id: The event ID
            
        Returns:
            Number of users provisioned
        """
        import secrets
        from sqlalchemy import select
        from app.models import Participant
        
        if not self.db:
            raise ValueError("Database session required")
        
        # Get verified participants without ctfd_user_id
        result = await self.db.execute(
            select(Participant).where(
                Participant.event_id == event_id,
                Participant.email_verified == True,
                Participant.ctfd_user_id == None,
            )
        )
        participants = result.scalars().all()
        
        provisioned = 0
        for p in participants:
            # Generate a random password
            password = secrets.token_urlsafe(12)
            
            success, ctfd_id, error = await self.provision_user(
                username=p.name,
                email=p.email,
                password=password,
            )
            
            if success and ctfd_id:
                p.ctfd_user_id = ctfd_id
                p.ctfd_password = password  # Store for user reference
                provisioned += 1
        
        await self.db.flush()
        return provisioned
    
    async def get_user_rank(self, ctfd_user_id: int) -> Optional[tuple[int, int]]:
        """
        Get a user's final rank and score.
        
        Returns:
            Tuple of (rank, score) or None if not found
        """
        standings = await self.client.get_standings(count=1000)
        
        for idx, entry in enumerate(standings, 1):
            account_id = entry.get("account_id") or entry.get("user_id")
            if account_id == ctfd_user_id:
                return idx, entry.get("score", 0)
            
            # Check team members
            if "team" in entry:
                team_data = entry["team"]
                members = await self.client.get_team_members(team_data["id"])
                for member in members:
                    if member.get("id") == ctfd_user_id:
                        return idx, entry.get("score", 0)
        
        return None
    
    # Keep old method for backwards compatibility
    async def sync_results(self) -> CTFdSyncResult:
        """
        Sync final results from CTFd (legacy method without DB update).
        
        Returns:
            CTFdSyncResult with sync statistics
        """
        try:
            standings = await self.client.get_standings(count=1000)
            users_synced = 0
            teams_synced = 0
            
            for idx, entry in enumerate(standings, 1):
                if "team" in entry:
                    teams_synced += 1
                else:
                    users_synced += 1
            
            return CTFdSyncResult(
                success=True,
                users_synced=users_synced,
                teams_synced=teams_synced,
            )
            
        except Exception as e:
            return CTFdSyncResult(
                success=False,
                error=str(e),
            )
