"""
Email Template Renderer

Renders email templates with Jinja2.
"""

from typing import Any, Dict, Optional

from jinja2 import BaseLoader, Environment, TemplateError, TemplateSyntaxError


class DatabaseLoader(BaseLoader):
    """
    Jinja2 loader that loads templates from database.
    
    Templates are passed directly, not loaded from filesystem.
    """
    
    def get_source(self, environment, template):
        # Not used - we render directly from string
        raise TemplateError("Direct string rendering only")


class EmailTemplateRenderer:
    """
    Renders email templates with Jinja2.
    
    Features:
    - Variable substitution
    - Default filters (date formatting, etc.)
    - HTML escaping by default
    - Safe rendering (graceful error handling)
    """
    
    def __init__(self):
        self.env = Environment(
            loader=DatabaseLoader(),
            autoescape=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        
        # Add custom filters
        self.env.filters["dateformat"] = self._dateformat
        self.env.filters["default"] = self._default
    
    def render(
        self,
        template_html: str,
        variables: Dict[str, Any],
        template_text: Optional[str] = None,
    ) -> tuple[str, Optional[str]]:
        """
        Render email template.
        
        Args:
            template_html: HTML template content
            variables: Variables to substitute
            template_text: Optional plain text template
            
        Returns:
            Tuple of (rendered_html, rendered_text)
        """
        # Render HTML
        html_template = self.env.from_string(template_html)
        rendered_html = html_template.render(**variables)
        
        # Render text if provided
        rendered_text = None
        if template_text:
            text_template = self.env.from_string(template_text)
            rendered_text = text_template.render(**variables)
        
        return rendered_html, rendered_text
    
    def render_subject(self, subject: str, variables: Dict[str, Any]) -> str:
        """Render email subject line."""
        template = self.env.from_string(subject)
        return template.render(**variables)
    
    def validate_template(self, template: str) -> tuple[bool, Optional[str]]:
        """
        Validate template syntax.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            self.env.from_string(template)
            return True, None
        except TemplateSyntaxError as e:
            return False, f"Syntax error at line {e.lineno}: {e.message}"
        except Exception as e:
            return False, str(e)
    
    def extract_variables(self, template: str) -> list[str]:
        """
        Extract variable names from template.
        
        Note: This is a basic extraction that finds {{ variable }} patterns.
        It won't catch all Jinja2 expressions but handles common cases.
        """
        import re
        
        # Match {{ variable }} patterns
        pattern = r'\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)'
        matches = re.findall(pattern, template)
        
        # Remove duplicates and built-in names
        builtins = {'loop', 'self', 'true', 'false', 'none'}
        return list(set(m for m in matches if m.lower() not in builtins))
    
    @staticmethod
    def _dateformat(value, format: str = "%Y-%m-%d") -> str:
        """Format a datetime value."""
        if value is None:
            return ""
        try:
            return value.strftime(format)
        except AttributeError:
            return str(value)
    
    @staticmethod
    def _default(value, default_value=""):
        """Return default if value is None or empty."""
        return value if value else default_value


# Global renderer instance
renderer = EmailTemplateRenderer()


def render_email(
    template_html: str,
    variables: Dict[str, Any],
    template_text: Optional[str] = None,
) -> tuple[str, Optional[str]]:
    """Convenience function to render email."""
    return renderer.render(template_html, variables, template_text)


def render_subject(subject: str, variables: Dict[str, Any]) -> str:
    """Convenience function to render subject."""
    return renderer.render_subject(subject, variables)


# =============================================================================
# Default Email Templates
# =============================================================================

DEFAULT_TEMPLATES = {
    "verification": {
        "name": "Email Verification",
        "slug": "verification",
        "subject": "Verify your email for {{ event_name }}",
        "body_html": """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #1a1a1a; }
        .container { max-width: 600px; margin: 0 auto; padding: 40px 20px; }
        .header { text-align: center; margin-bottom: 30px; }
        .content { background: #f8f9fa; padding: 30px; border-radius: 8px; }
        .button { display: inline-block; background: #18181b; color: #ffffff !important; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: 500; }
        .footer { text-align: center; margin-top: 30px; font-size: 14px; color: #6b7280; }
        .code { font-family: monospace; font-size: 24px; letter-spacing: 4px; color: #18181b; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{{ event_name }}</h1>
        </div>
        <div class="content">
            <p>Hello <strong>{{ username }}</strong>,</p>
            <p>Thank you for registering. Please verify your email address by clicking the button below:</p>
            <p style="text-align: center; margin: 30px 0;">
                <a href="{{ verification_url }}" class="button">Verify Email</a>
            </p>
            <p>Or copy and paste this link into your browser:</p>
            <p style="word-break: break-all; font-size: 14px; color: #6b7280;">{{ verification_url }}</p>
            <p>This link will expire in 24 hours.</p>
        </div>
        <div class="footer">
            <p>If you didn't register for this event, you can safely ignore this email.</p>
        </div>
    </div>
</body>
</html>
        """,
        "body_text": """
Hello {{ username }},

Thank you for registering for {{ event_name }}. Please verify your email address by visiting this link:

{{ verification_url }}

This link will expire in 24 hours.

If you didn't register for this event, you can safely ignore this email.
        """,
        "variables": ["event_name", "username", "verification_url"],
    },
    
    "welcome": {
        "name": "Welcome Email",
        "slug": "welcome",
        "subject": "Welcome to {{ event_name }}!",
        "body_html": """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #1a1a1a; }
        .container { max-width: 600px; margin: 0 auto; padding: 40px 20px; }
        .header { text-align: center; margin-bottom: 30px; }
        .content { background: #f8f9fa; padding: 30px; border-radius: 8px; }
        .button { display: inline-block; background: #18181b; color: #ffffff !important; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: 500; }
        .footer { text-align: center; margin-top: 30px; font-size: 14px; color: #6b7280; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Welcome to {{ event_name }}!</h1>
        </div>
        <div class="content">
            <p>Hello <strong>{{ username }}</strong>,</p>
            <p>Your email has been verified and your account is ready!</p>
            <p>You can now access the competition platform:</p>
            <p style="text-align: center; margin: 30px 0;">
                <a href="{{ ctfd_url }}" class="button">Go to CTF Platform</a>
            </p>
            <p><strong>Your credentials:</strong></p>
            <ul>
                <li>Username: {{ username }}</li>
                <li>Password: (the one you set during registration)</li>
            </ul>
            <p>Good luck and have fun!</p>
        </div>
        <div class="footer">
            <p>Questions? Join our Discord or contact the organizers.</p>
        </div>
    </div>
</body>
</html>
        """,
        "body_text": """
Welcome to {{ event_name }}!

Hello {{ username }},

Your email has been verified and your account is ready!

You can now access the competition platform at: {{ ctfd_url }}

Your credentials:
- Username: {{ username }}
- Password: (the one you set during registration)

Good luck and have fun!

Questions? Join our Discord or contact the organizers.
        """,
        "variables": ["event_name", "username", "ctfd_url"],
    },
    
    "prize_ready": {
        "name": "Prize Ready",
        "slug": "prize_ready",
        "subject": "Your prizes are ready! - {{ event_name }}",
        "body_html": """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #1a1a1a; }
        .container { max-width: 600px; margin: 0 auto; padding: 40px 20px; }
        .header { text-align: center; margin-bottom: 30px; }
        .content { background: #f8f9fa; padding: 30px; border-radius: 8px; }
        .button { display: inline-block; background: #18181b; color: #ffffff !important; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: 500; }
        .footer { text-align: center; margin-top: 30px; font-size: 14px; color: #6b7280; }
        .rank { font-size: 48px; font-weight: bold; color: #18181b; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Congratulations!</h1>
            <p class="rank">#{{ rank }}</p>
        </div>
        <div class="content">
            <p>Hello <strong>{{ name }}</strong>,</p>
            <p>Thank you for participating in <strong>{{ event_name }}</strong>!</p>
            <p>You finished at <strong>rank #{{ rank }}</strong> with <strong>{{ score }} points</strong>.</p>
            <p>Your prizes are ready to claim:</p>
            <p style="text-align: center; margin: 30px 0;">
                <a href="{{ claim_url }}" class="button">Claim Your Prizes</a>
            </p>
            <p>Log in with your registered email to view and download your prizes.</p>
        </div>
        <div class="footer">
            <p>Thank you for playing!</p>
        </div>
    </div>
</body>
</html>
        """,
        "body_text": """
Congratulations!

Hello {{ name }},

Thank you for participating in {{ event_name }}!

You finished at rank #{{ rank }} with {{ score }} points.

Your prizes are ready to claim. Visit {{ claim_url }} and log in with your registered email.

Thank you for playing!
        """,
        "variables": ["event_name", "name", "rank", "score", "claim_url"],
    },
}
