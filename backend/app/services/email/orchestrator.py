"""
Email Orchestration Service

The crown jewel of ZeroPool - intelligent multi-provider email routing
with rate limiting, failover, and circuit breaker patterns.
"""

import asyncio
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

import aiosmtplib
import httpx
from redis import asyncio as aioredis

from app.config import get_settings
from app.utils.security import decrypt_data

settings = get_settings()


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class EmailMessage:
    """Email message to send."""
    to: str
    subject: str
    body_html: str
    body_text: Optional[str] = None
    from_name: Optional[str] = None
    from_address: Optional[str] = None
    reply_to: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    
    # Tracking
    participant_id: Optional[UUID] = None
    campaign_id: Optional[UUID] = None
    template_slug: Optional[str] = None


@dataclass
class SendResult:
    """Result of sending an email."""
    success: bool
    provider_id: Optional[UUID] = None
    provider_name: Optional[str] = None
    message_id: Optional[str] = None
    error: Optional[str] = None
    attempts: int = 0


class ProviderHealth(Enum):
    """Provider health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class ProviderStatus:
    """Current status of an email provider."""
    provider_id: UUID
    name: str
    health: ProviderHealth
    
    # Current usage
    daily_used: int
    daily_limit: Optional[int]
    hourly_used: int
    hourly_limit: Optional[int]
    minute_used: int
    minute_limit: Optional[int]
    
    # Circuit breaker
    circuit_open: bool
    circuit_open_until: Optional[datetime]
    failure_count: int
    
    # Availability
    available: bool
    unavailable_reason: Optional[str]


# =============================================================================
# Provider Interface
# =============================================================================


class EmailProviderInterface(ABC):
    """Abstract interface for email providers."""
    
    @abstractmethod
    async def send(
        self,
        message: EmailMessage,
        config: Dict[str, Any],
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Send an email.
        
        Args:
            message: The email to send
            config: Provider-specific configuration
            
        Returns:
            Tuple of (success, message_id, error_message)
        """
        pass
    
    @abstractmethod
    async def health_check(self, config: Dict[str, Any]) -> bool:
        """
        Check if provider is healthy.
        
        Args:
            config: Provider-specific configuration
            
        Returns:
            True if provider is healthy
        """
        pass


# =============================================================================
# Gmail Provider
# =============================================================================


class GmailProvider(EmailProviderInterface):
    """Gmail SMTP provider with App Password support."""
    
    async def send(
        self,
        message: EmailMessage,
        config: Dict[str, Any],
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Send email via Gmail SMTP."""
        # Transform Gmail config to SMTP config
        smtp_config = {
            "host": "smtp.gmail.com",
            "port": 587,
            "username": config.get("email"),
            "password": config.get("password"),
            "use_tls": False,
            "start_tls": True,
        }
        
        # Override from address to use Gmail email
        if not message.from_address:
            message.from_address = config.get("email")
        
        smtp = SMTPProvider()
        return await smtp.send(message, smtp_config)
    
    async def health_check(self, config: Dict[str, Any]) -> bool:
        """Check Gmail SMTP connectivity."""
        smtp_config = {
            "host": "smtp.gmail.com",
            "port": 587,
            "username": config.get("email"),
            "password": config.get("password"),
            "use_tls": False,
            "start_tls": True,
        }
        
        smtp = SMTPProvider()
        return await smtp.health_check(smtp_config)


# =============================================================================
# SMTP Provider
# =============================================================================


class SMTPProvider(EmailProviderInterface):
    """Generic SMTP provider."""
    
    async def send(
        self,
        message: EmailMessage,
        config: Dict[str, Any],
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Send email via SMTP."""
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        
        try:
            # Build email
            msg = MIMEMultipart("alternative")
            msg["Subject"] = message.subject
            msg["From"] = f"{message.from_name or settings.email_from_name} <{message.from_address or settings.email_from_address}>"
            msg["To"] = message.to
            
            if message.reply_to:
                msg["Reply-To"] = message.reply_to
            
            # Add custom headers
            if message.headers:
                for key, value in message.headers.items():
                    msg[key] = value
            
            # Attach text parts
            if message.body_text:
                msg.attach(MIMEText(message.body_text, "plain", "utf-8"))
            msg.attach(MIMEText(message.body_html, "html", "utf-8"))
            
            # Get SMTP settings
            host = config.get("host", "localhost")
            port = config.get("port", 587)
            username = config.get("username")
            password = config.get("password")
            use_tls = config.get("use_tls", True)
            start_tls = config.get("start_tls", True)
            
            # Decrypt password if encrypted
            if password and password.startswith("gAAAAA"):
                password = decrypt_data(password)
            
            # Send
            smtp = aiosmtplib.SMTP(
                hostname=host,
                port=port,
                use_tls=use_tls,
                start_tls=start_tls,
            )
            
            await smtp.connect()
            
            if username and password:
                await smtp.login(username, password)
            
            result = await smtp.send_message(msg)
            await smtp.quit()
            
            # Extract message ID from response
            message_id = None
            if result and len(result) > 0:
                message_id = str(result)
            
            return True, message_id, None
            
        except aiosmtplib.SMTPException as e:
            return False, None, f"SMTP error: {str(e)}"
        except Exception as e:
            return False, None, f"Error: {str(e)}"
    
    async def health_check(self, config: Dict[str, Any]) -> bool:
        """Check SMTP connectivity."""
        try:
            host = config.get("host", "localhost")
            port = config.get("port", 587)
            use_tls = config.get("use_tls", True)
            
            smtp = aiosmtplib.SMTP(
                hostname=host,
                port=port,
                use_tls=use_tls,
                timeout=10,
            )
            
            await smtp.connect()
            await smtp.quit()
            return True
            
        except Exception:
            return False


# =============================================================================
# Brevo (Sendinblue) API Provider
# =============================================================================


class BrevoProvider(EmailProviderInterface):
    """Brevo (formerly Sendinblue) API provider."""
    
    API_URL = "https://api.brevo.com/v3/smtp/email"
    
    async def send(
        self,
        message: EmailMessage,
        config: Dict[str, Any],
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Send email via Brevo API."""
        try:
            api_key = config.get("api_key")
            if api_key and api_key.startswith("gAAAAA"):
                api_key = decrypt_data(api_key)
            
            if not api_key:
                return False, None, "API key not configured"
            
            payload = {
                "sender": {
                    "name": message.from_name or settings.email_from_name,
                    "email": message.from_address or settings.email_from_address,
                },
                "to": [{"email": message.to}],
                "subject": message.subject,
                "htmlContent": message.body_html,
            }
            
            if message.body_text:
                payload["textContent"] = message.body_text
            
            if message.reply_to:
                payload["replyTo"] = {"email": message.reply_to}
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.API_URL,
                    json=payload,
                    headers={
                        "api-key": api_key,
                        "Content-Type": "application/json",
                    },
                    timeout=30,
                )
            
            if response.status_code in (200, 201):
                data = response.json()
                return True, data.get("messageId"), None
            else:
                return False, None, f"API error {response.status_code}: {response.text}"
            
        except Exception as e:
            return False, None, f"Error: {str(e)}"
    
    async def health_check(self, config: Dict[str, Any]) -> bool:
        """Check Brevo API connectivity."""
        try:
            api_key = config.get("api_key")
            if api_key and api_key.startswith("gAAAAA"):
                api_key = decrypt_data(api_key)
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.brevo.com/v3/account",
                    headers={"api-key": api_key},
                    timeout=10,
                )
            
            return response.status_code == 200
            
        except Exception:
            return False


# =============================================================================
# Mailgun API Provider
# =============================================================================


class MailgunProvider(EmailProviderInterface):
    """Mailgun API provider."""
    
    async def send(
        self,
        message: EmailMessage,
        config: Dict[str, Any],
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Send email via Mailgun API."""
        try:
            api_key = config.get("api_key")
            domain = config.get("domain")
            region = config.get("region", "us")  # 'us' or 'eu'
            
            if api_key and api_key.startswith("gAAAAA"):
                api_key = decrypt_data(api_key)
            
            if not api_key or not domain:
                return False, None, "API key and domain required"
            
            base_url = (
                "https://api.eu.mailgun.net/v3" if region == "eu"
                else "https://api.mailgun.net/v3"
            )
            
            from_address = f"{message.from_name or settings.email_from_name} <{message.from_address or settings.email_from_address}>"
            
            data = {
                "from": from_address,
                "to": message.to,
                "subject": message.subject,
                "html": message.body_html,
            }
            
            if message.body_text:
                data["text"] = message.body_text
            
            if message.reply_to:
                data["h:Reply-To"] = message.reply_to
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{base_url}/{domain}/messages",
                    data=data,
                    auth=("api", api_key),
                    timeout=30,
                )
            
            if response.status_code == 200:
                result = response.json()
                return True, result.get("id"), None
            else:
                return False, None, f"API error {response.status_code}: {response.text}"
            
        except Exception as e:
            return False, None, f"Error: {str(e)}"
    
    async def health_check(self, config: Dict[str, Any]) -> bool:
        """Check Mailgun API connectivity."""
        try:
            api_key = config.get("api_key")
            domain = config.get("domain")
            region = config.get("region", "us")
            
            if api_key and api_key.startswith("gAAAAA"):
                api_key = decrypt_data(api_key)
            
            base_url = (
                "https://api.eu.mailgun.net/v3" if region == "eu"
                else "https://api.mailgun.net/v3"
            )
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{base_url}/domains/{domain}",
                    auth=("api", api_key),
                    timeout=10,
                )
            
            return response.status_code == 200
            
        except Exception:
            return False


# =============================================================================
# AWS SES Provider
# =============================================================================


class AWSSESProvider(EmailProviderInterface):
    """AWS SES provider using SMTP interface."""
    
    # SES SMTP endpoints by region
    ENDPOINTS = {
        "us-east-1": "email-smtp.us-east-1.amazonaws.com",
        "us-west-2": "email-smtp.us-west-2.amazonaws.com",
        "eu-west-1": "email-smtp.eu-west-1.amazonaws.com",
        "eu-central-1": "email-smtp.eu-central-1.amazonaws.com",
        "ap-southeast-1": "email-smtp.ap-southeast-1.amazonaws.com",
        "ap-south-1": "email-smtp.ap-south-1.amazonaws.com",
    }
    
    async def send(
        self,
        message: EmailMessage,
        config: Dict[str, Any],
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Send email via AWS SES SMTP."""
        # Use SMTP provider with SES settings
        smtp_config = {
            "host": self.ENDPOINTS.get(config.get("region", "us-east-1")),
            "port": 587,
            "username": config.get("smtp_username"),
            "password": config.get("smtp_password"),
            "use_tls": False,
            "start_tls": True,
        }
        
        smtp = SMTPProvider()
        return await smtp.send(message, smtp_config)
    
    async def health_check(self, config: Dict[str, Any]) -> bool:
        """Check SES SMTP connectivity."""
        smtp_config = {
            "host": self.ENDPOINTS.get(config.get("region", "us-east-1")),
            "port": 587,
            "use_tls": False,
        }
        
        smtp = SMTPProvider()
        return await smtp.health_check(smtp_config)


# =============================================================================
# Provider Registry
# =============================================================================


PROVIDER_REGISTRY: Dict[str, EmailProviderInterface] = {
    "smtp": SMTPProvider(),
    "gmail": GmailProvider(),  # Gmail with App Password
    "brevo": BrevoProvider(),
    "sendinblue": BrevoProvider(),  # Alias
    "mailjet": BrevoProvider(),  # Uses similar API pattern
    "mailgun": MailgunProvider(),
    "aws_ses": AWSSESProvider(),
    "ses": AWSSESProvider(),  # Alias
}


def get_provider_instance(provider_type: str) -> Optional[EmailProviderInterface]:
    """Get provider instance by type."""
    return PROVIDER_REGISTRY.get(provider_type.lower())


# =============================================================================
# Rate Limiter
# =============================================================================


class RateLimiter:
    """
    Redis-based rate limiter with multiple time windows.
    
    Tracks per-second, per-minute, per-hour, and per-day limits.
    """
    
    def __init__(self, redis: aioredis.Redis):
        self.redis = redis
    
    async def check_limits(
        self,
        provider_id: str,
        daily_limit: Optional[int] = None,
        hourly_limit: Optional[int] = None,
        minute_limit: Optional[int] = None,
        second_limit: Optional[int] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if provider is within rate limits.
        
        Returns:
            Tuple of (can_send, blocked_reason)
        """
        windows = [
            ("second", second_limit, 1),
            ("minute", minute_limit, 60),
            ("hourly", hourly_limit, 3600),
            ("daily", daily_limit, 86400),
        ]
        
        for window_name, limit, ttl in windows:
            if limit is None:
                continue
            
            key = f"ratelimit:{provider_id}:{window_name}"
            current = await self.redis.get(key)
            current = int(current) if current else 0
            
            if current >= limit:
                return False, f"{window_name}_limit_exceeded"
        
        return True, None
    
    async def increment(self, provider_id: str) -> None:
        """
        Increment rate limit counters for all windows.
        
        Uses Redis pipeline for atomic operations.
        """
        windows = [
            ("second", 1),
            ("minute", 60),
            ("hourly", 3600),
            ("daily", 86400),
        ]
        
        pipe = self.redis.pipeline()
        
        for window_name, ttl in windows:
            key = f"ratelimit:{provider_id}:{window_name}"
            pipe.incr(key)
            pipe.expire(key, ttl)
        
        await pipe.execute()
    
    async def get_usage(self, provider_id: str) -> Dict[str, int]:
        """Get current usage for all windows."""
        windows = ["second", "minute", "hourly", "daily"]
        usage = {}
        
        for window in windows:
            key = f"ratelimit:{provider_id}:{window}"
            value = await self.redis.get(key)
            usage[window] = int(value) if value else 0
        
        return usage


# =============================================================================
# Circuit Breaker
# =============================================================================


class CircuitBreaker:
    """
    Circuit breaker pattern for provider health.
    
    Opens circuit after N failures, allowing recovery time.
    """
    
    def __init__(
        self,
        redis: aioredis.Redis,
        failure_threshold: int = 3,
        recovery_timeout: int = 300,  # 5 minutes
    ):
        self.redis = redis
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
    
    async def is_open(self, provider_id: str) -> bool:
        """Check if circuit is open (provider disabled)."""
        key = f"circuit:{provider_id}:open_until"
        open_until = await self.redis.get(key)
        
        if open_until:
            open_until_ts = float(open_until)
            if datetime.utcnow().timestamp() < open_until_ts:
                return True
            else:
                # Circuit timeout expired, reset
                await self.reset(provider_id)
        
        return False
    
    async def record_success(self, provider_id: str) -> None:
        """Record successful send, reset failure count."""
        key = f"circuit:{provider_id}:failures"
        await self.redis.delete(key)
    
    async def record_failure(self, provider_id: str) -> bool:
        """
        Record failed send.
        
        Returns:
            True if circuit was opened
        """
        key = f"circuit:{provider_id}:failures"
        failures = await self.redis.incr(key)
        await self.redis.expire(key, 600)  # Reset after 10 minutes of no failures
        
        if failures >= self.failure_threshold:
            # Open circuit
            open_until = datetime.utcnow() + timedelta(seconds=self.recovery_timeout)
            await self.redis.set(
                f"circuit:{provider_id}:open_until",
                str(open_until.timestamp()),
                ex=self.recovery_timeout,
            )
            return True
        
        return False
    
    async def reset(self, provider_id: str) -> None:
        """Reset circuit breaker state."""
        await self.redis.delete(f"circuit:{provider_id}:failures")
        await self.redis.delete(f"circuit:{provider_id}:open_until")
    
    async def get_failure_count(self, provider_id: str) -> int:
        """Get current failure count."""
        key = f"circuit:{provider_id}:failures"
        count = await self.redis.get(key)
        return int(count) if count else 0


# =============================================================================
# Email Orchestrator
# =============================================================================


class EmailOrchestrator:
    """
    Main orchestrator for sending emails.
    
    Handles:
    - Provider selection based on priority and availability
    - Rate limit checking and enforcement
    - Circuit breaker pattern for unhealthy providers
    - Automatic failover to backup providers
    - Logging and metrics
    """
    
    def __init__(self, redis: aioredis.Redis):
        self.redis = redis
        self.rate_limiter = RateLimiter(redis)
        self.circuit_breaker = CircuitBreaker(redis)
    
    async def send(
        self,
        message: EmailMessage,
        providers: List[Dict[str, Any]],
        max_attempts: int = 5,
        retry_delay: float = 1.0,
    ) -> SendResult:
        """
        Send an email using available providers.
        
        Tries providers in priority order, failing over on errors.
        
        Args:
            message: The email to send
            providers: List of provider configs from database
            max_attempts: Maximum number of total attempts
            retry_delay: Delay between attempts in seconds
            
        Returns:
            SendResult with success status and details
        """
        attempts = 0
        last_error = None
        
        for attempt in range(max_attempts):
            attempts = attempt + 1
            
            # Find available provider
            provider_config = await self._find_available_provider(providers)
            
            if not provider_config:
                # All providers exhausted, wait and retry
                if attempt < max_attempts - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))
                    continue
                else:
                    return SendResult(
                        success=False,
                        error="All providers exhausted or rate limited",
                        attempts=attempts,
                    )
            
            provider_id = provider_config["id"]
            provider_name = provider_config["name"]
            provider_type = provider_config["type"]
            config = provider_config["config"]
            
            # Get provider instance
            provider = get_provider_instance(provider_type)
            if not provider:
                last_error = f"Unknown provider type: {provider_type}"
                continue
            
            # Try to send
            try:
                print(f"[EMAIL] Attempting to send via {provider_name} ({provider_type})")
                success, message_id, error = await provider.send(message, config)
                print(f"[EMAIL] Result: success={success}, error={error}")
                
                if success:
                    # Record success
                    await self.rate_limiter.increment(str(provider_id))
                    await self.circuit_breaker.record_success(str(provider_id))
                    
                    return SendResult(
                        success=True,
                        provider_id=provider_id,
                        provider_name=provider_name,
                        message_id=message_id,
                        attempts=attempts,
                    )
                else:
                    # Record failure
                    last_error = error
                    circuit_opened = await self.circuit_breaker.record_failure(str(provider_id))
                    
                    if circuit_opened:
                        # Remove this provider from consideration
                        providers = [p for p in providers if p["id"] != provider_id]
                    
            except Exception as e:
                last_error = str(e)
                await self.circuit_breaker.record_failure(str(provider_id))
        
        return SendResult(
            success=False,
            error=last_error or "Failed to send after all attempts",
            attempts=attempts,
        )
    
    async def _find_available_provider(
        self,
        providers: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """
        Find the first available provider.
        
        Checks:
        1. Circuit breaker status
        2. Rate limits
        
        Returns provider config or None if all exhausted.
        """
        # Sort by priority
        sorted_providers = sorted(providers, key=lambda p: p.get("priority", 10))
        
        for provider in sorted_providers:
            provider_id = str(provider["id"])
            
            # Check circuit breaker
            if await self.circuit_breaker.is_open(provider_id):
                continue
            
            # Check rate limits
            can_send, _ = await self.rate_limiter.check_limits(
                provider_id,
                daily_limit=provider.get("daily_limit"),
                hourly_limit=provider.get("hourly_limit"),
                minute_limit=provider.get("minute_limit"),
                second_limit=provider.get("second_limit"),
            )
            
            if can_send:
                return provider
        
        return None
    
    async def get_provider_statuses(
        self,
        providers: List[Dict[str, Any]],
    ) -> List[ProviderStatus]:
        """Get current status of all providers."""
        statuses = []
        
        for provider in providers:
            provider_id = str(provider["id"])
            
            # Get usage
            usage = await self.rate_limiter.get_usage(provider_id)
            
            # Check circuit
            circuit_open = await self.circuit_breaker.is_open(provider_id)
            failure_count = await self.circuit_breaker.get_failure_count(provider_id)
            
            # Get circuit open until time
            open_until_key = f"circuit:{provider_id}:open_until"
            open_until_ts = await self.redis.get(open_until_key)
            circuit_open_until = None
            if open_until_ts:
                circuit_open_until = datetime.fromtimestamp(float(open_until_ts))
            
            # Determine health
            if circuit_open:
                health = ProviderHealth.UNHEALTHY
            elif failure_count > 0:
                health = ProviderHealth.DEGRADED
            else:
                health = ProviderHealth.HEALTHY
            
            # Check availability
            available = True
            unavailable_reason = None
            
            if circuit_open:
                available = False
                unavailable_reason = "Circuit breaker open"
            else:
                # Check rate limits
                can_send, reason = await self.rate_limiter.check_limits(
                    provider_id,
                    daily_limit=provider.get("daily_limit"),
                    hourly_limit=provider.get("hourly_limit"),
                    minute_limit=provider.get("minute_limit"),
                    second_limit=provider.get("second_limit"),
                )
                if not can_send:
                    available = False
                    unavailable_reason = reason
            
            statuses.append(ProviderStatus(
                provider_id=provider["id"],
                name=provider["name"],
                health=health,
                daily_used=usage["daily"],
                daily_limit=provider.get("daily_limit"),
                hourly_used=usage["hourly"],
                hourly_limit=provider.get("hourly_limit"),
                minute_used=usage["minute"],
                minute_limit=provider.get("minute_limit"),
                circuit_open=circuit_open,
                circuit_open_until=circuit_open_until,
                failure_count=failure_count,
                available=available,
                unavailable_reason=unavailable_reason,
            ))
        
        return statuses
