"""generate pdf/png certificates from templates with text zones and qr codes."""

import io
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

import qrcode
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from app.config import get_settings
from app.utils.security import generate_certificate_code

settings = get_settings()


@dataclass
class TextZone:
    id: str
    field: str  # 'name', 'team', 'rank', 'date', 'verification_code'
    x: float
    y: float
    width: float
    height: float
    font_family: str = "Helvetica"
    font_size: int = 24
    font_color: str = "#000000"
    alignment: str = "center"  # 'left', 'center', 'right'
    rotation: float = 0  # Degrees
    is_percentage: bool = True  # If True, x/y/width/height are percentages


@dataclass
class QRZone:
    x: float
    y: float
    size: float
    is_percentage: bool = True


@dataclass
class CertificateData:
    participant_id: UUID
    display_name: str
    team_name: Optional[str] = None
    rank: Optional[int] = None
    score: Optional[float] = None
    event_name: str = ""
    issued_at: datetime = None
    
    def __post_init__(self):
        if self.issued_at is None:
            self.issued_at = datetime.utcnow()


@dataclass
class CertificateResult:
    success: bool
    file_path: Optional[str] = None
    verification_code: Optional[str] = None
    error: Optional[str] = None


class CertificateGenerator:
    def __init__(self, fonts_dir: str = None, output_dir: str = None):
        self.fonts_dir = Path(fonts_dir or settings.fonts_dir)
        self.output_dir = Path(output_dir or settings.certs_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self._fonts: Dict[str, str] = {}
        self._load_fonts()
    
    def _load_fonts(self) -> None:
        if not self.fonts_dir.exists():
            return
        
        for font_file in self.fonts_dir.glob("*.ttf"):
            font_name = font_file.stem
            self._fonts[font_name.lower()] = str(font_file)
        
        for font_file in self.fonts_dir.glob("*.otf"):
            font_name = font_file.stem
            self._fonts[font_name.lower()] = str(font_file)
    
    def get_available_fonts(self) -> List[str]:
        return list(self._fonts.keys())
    
    def _get_font_path(self, font_family: str) -> Optional[str]:
        return self._fonts.get(font_family.lower())
    
    def _hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        hex_color = hex_color.lstrip("#")
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def generate_verification_code(
        self,
        participant_id: UUID,
        cert_type: str = "participation",
        issued_at: datetime = None,
    ) -> str:
        if issued_at is None:
            issued_at = datetime.utcnow()
        
        return generate_certificate_code(
            str(participant_id),
            cert_type,
            issued_at,
        )
    
    def _create_qr_code(
        self,
        verification_url: str,
        size: int = 150,
    ) -> Image.Image:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=2,
        )
        qr.add_data(verification_url)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        return img.resize((size, size), Image.Resampling.LANCZOS)
    
    def generate_png(
        self,
        template_path: str,
        data: CertificateData,
        text_zones: List[TextZone],
        qr_zone: Optional[QRZone] = None,
        verification_url_base: str = "",
    ) -> CertificateResult:
        try:
            template = Image.open(template_path)
            template = template.convert("RGBA")
            width, height = template.size
            
            draw = ImageDraw.Draw(template)
            
            verification_code = self.generate_verification_code(
                data.participant_id,
                "participation" if not data.rank or data.rank > 15 else "winner",
                data.issued_at,
            )
            
            # field values under both naming conventions
            field_values = {
                # short names (legacy)
                "name": data.display_name,
                "team": data.team_name or "",
                "rank": f"#{data.rank}" if data.rank else "",
                "score": str(int(data.score)) if data.score else "",
                "event": data.event_name,
                "date": data.issued_at.strftime("%B %d, %Y"),
                "verification_code": verification_code,
                # full names (frontend uses these)
                "participant_name": data.display_name,
                "team_name": data.team_name or "",
                "event_name": data.event_name,
            }
            
            for zone in text_zones:
                text = field_values.get(zone.field, "")
                if not text:
                    continue
                
                if zone.is_percentage:
                    x = int(zone.x / 100 * width)
                    y = int(zone.y / 100 * height)
                    max_width = int(zone.width / 100 * width)
                else:
                    x = int(zone.x)
                    y = int(zone.y)
                    max_width = int(zone.width)
                
                font_path = self._get_font_path(zone.font_family)
                font = None
                
                if font_path:
                    font = ImageFont.truetype(font_path, zone.font_size)
                else:
                    # fallback fonts (reportlab's vera.ttf is reliable)
                    fallback_fonts = [
                        "/usr/local/lib/python3.11/site-packages/reportlab/fonts/Vera.ttf",
                        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                        "arial.ttf",
                        "/usr/share/fonts/TTF/DejaVuSans.ttf",
                    ]
                    for fallback in fallback_fonts:
                        try:
                            font = ImageFont.truetype(fallback, zone.font_size)
                            break
                        except:
                            continue
                    
                    if font is None:
                        # last resort; default font doesn't support sizing
                        font = ImageFont.load_default()
                
                color = self._hex_to_rgb(zone.font_color)
                
                bbox = draw.textbbox((0, 0), text, font=font)
                text_width = bbox[2] - bbox[0]
                
                if zone.alignment == "center":
                    x = x - text_width // 2
                elif zone.alignment == "right":
                    x = x - text_width
                
                draw.text((x, y), text, font=font, fill=color)
            
            if qr_zone and verification_url_base:
                verification_url = f"{verification_url_base}?code={verification_code}"
                
                if qr_zone.is_percentage:
                    qr_x = int(qr_zone.x / 100 * width)
                    qr_y = int(qr_zone.y / 100 * height)
                    qr_size = int(qr_zone.size / 100 * min(width, height))
                else:
                    qr_x = int(qr_zone.x)
                    qr_y = int(qr_zone.y)
                    qr_size = int(qr_zone.size)
                
                qr_img = self._create_qr_code(verification_url, qr_size)
                template.paste(qr_img, (qr_x, qr_y))
            
            output_filename = f"{verification_code}.png"
            output_path = self.output_dir / output_filename
            template.save(output_path, "PNG", quality=95)
            
            return CertificateResult(
                success=True,
                file_path=str(output_path),
                verification_code=verification_code,
            )
            
        except Exception as e:
            return CertificateResult(
                success=False,
                error=str(e),
            )
    
    def generate_pdf(
        self,
        template_path: str,
        data: CertificateData,
        text_zones: List[TextZone],
        qr_zone: Optional[QRZone] = None,
        verification_url_base: str = "",
    ) -> CertificateResult:
        """uses reportlab to render the template as the pdf background."""
        try:
            template_img = Image.open(template_path)
            img_width, img_height = template_img.size
            
            verification_code = self.generate_verification_code(
                data.participant_id,
                "participation" if not data.rank or data.rank > 15 else "winner",
                data.issued_at,
            )
            
            output_filename = f"{verification_code}.pdf"
            output_path = self.output_dir / output_filename
            
            # pixels to points (72pt = 1in at 96 dpi)
            scale = 72 / 96
            page_width = img_width * scale
            page_height = img_height * scale
            
            c = canvas.Canvas(str(output_path), pagesize=(page_width, page_height))
            
            c.drawImage(
                template_path,
                0, 0,
                width=page_width,
                height=page_height,
            )
            
            # field values under both naming conventions
            field_values = {
                # short names (legacy)
                "name": data.display_name,
                "team": data.team_name or "",
                "rank": f"#{data.rank}" if data.rank else "",
                "score": str(int(data.score)) if data.score else "",
                "event": data.event_name,
                "date": data.issued_at.strftime("%B %d, %Y"),
                "verification_code": verification_code,
                # full names (frontend uses these)
                "participant_name": data.display_name,
                "team_name": data.team_name or "",
                "event_name": data.event_name,
            }
            
            for zone in text_zones:
                text = field_values.get(zone.field, "")
                if not text:
                    continue
                
                # pdf origin is bottom-left
                if zone.is_percentage:
                    x = zone.x / 100 * page_width
                    y = page_height - (zone.y / 100 * page_height)
                else:
                    x = zone.x * scale
                    y = page_height - (zone.y * scale)
                
                font_name = zone.font_family
                # reportlab built-in fonts
                if font_name.lower() not in ["helvetica", "times-roman", "courier"]:
                    font_path = self._get_font_path(zone.font_family)
                    if font_path:
                        from reportlab.pdfbase import pdfmetrics
                        from reportlab.pdfbase.ttfonts import TTFont
                        try:
                            pdfmetrics.registerFont(TTFont(zone.font_family, font_path))
                            font_name = zone.font_family
                        except:
                            font_name = "Helvetica"
                    else:
                        font_name = "Helvetica"
                
                c.setFont(font_name, zone.font_size)
                
                rgb = self._hex_to_rgb(zone.font_color)
                c.setFillColorRGB(rgb[0]/255, rgb[1]/255, rgb[2]/255)
                
                if zone.alignment == "center":
                    c.drawCentredString(x, y, text)
                elif zone.alignment == "right":
                    c.drawRightString(x, y, text)
                else:
                    c.drawString(x, y, text)
            
            if qr_zone and verification_url_base:
                verification_url = f"{verification_url_base}?code={verification_code}"
                
                if qr_zone.is_percentage:
                    qr_x = qr_zone.x / 100 * page_width
                    qr_y = page_height - (qr_zone.y / 100 * page_height)
                    qr_size = qr_zone.size / 100 * min(page_width, page_height)
                else:
                    qr_x = qr_zone.x * scale
                    qr_y = page_height - (qr_zone.y * scale)
                    qr_size = qr_zone.size * scale
                
                qr_img = self._create_qr_code(verification_url, int(qr_size / scale))
                
                # pil image to bytes for reportlab
                qr_buffer = io.BytesIO()
                qr_img.save(qr_buffer, format="PNG")
                qr_buffer.seek(0)
                
                c.drawImage(
                    ImageReader(qr_buffer),
                    qr_x,
                    qr_y - qr_size,  # adjust for top-left origin
                    width=qr_size,
                    height=qr_size,
                )
            
            c.save()
            
            return CertificateResult(
                success=True,
                file_path=str(output_path),
                verification_code=verification_code,
            )
            
        except Exception as e:
            return CertificateResult(
                success=False,
                error=str(e),
            )
    
    def generate(
        self,
        template_path: str,
        data: CertificateData,
        text_zones: List[Dict[str, Any]],
        qr_zone: Optional[Dict[str, Any]] = None,
        output_format: str = "pdf",
        verification_url_base: str = "",
    ) -> CertificateResult:
        """main entry point; builds zones from raw config and dispatches to png or pdf."""
        zones = [
            TextZone(
                id=z.get("id", str(i)),
                field=z["field"],
                x=z["x"],
                y=z["y"],
                width=z.get("width", 100),
                height=z.get("height", 50),
                font_family=z.get("font_family", "Helvetica"),
                font_size=z.get("font_size", 24),
                font_color=z.get("font_color", "#000000"),
                alignment=z.get("alignment", "center"),
                rotation=z.get("rotation", 0),
                is_percentage=z.get("is_percentage", True),
            )
            for i, z in enumerate(text_zones)
        ]
        
        qr = None
        if qr_zone:
            qr = QRZone(
                x=qr_zone["x"],
                y=qr_zone["y"],
                size=qr_zone.get("size", 10),
                is_percentage=qr_zone.get("is_percentage", True),
            )
        
        if output_format.lower() == "png":
            return self.generate_png(
                template_path, data, zones, qr, verification_url_base
            )
        else:
            return self.generate_pdf(
                template_path, data, zones, qr, verification_url_base
            )
    
    def preview(
        self,
        template_path: str,
        text_zones: List[Dict[str, Any]],
        qr_zone: Optional[Dict[str, Any]] = None,
    ) -> bytes:
        """render a preview with sample data; returns png bytes for the admin ui."""
        sample_data = CertificateData(
            participant_id=UUID("00000000-0000-0000-0000-000000000000"),
            display_name="John Doe",
            team_name="Sample Team",
            rank=1,
            score=1337,
            event_name="Sample Event 2025",
        )
        
        result = self.generate(
            template_path,
            sample_data,
            text_zones,
            qr_zone,
            output_format="png",
            verification_url_base="https://verify.example.com",
        )
        
        if result.success and result.file_path:
            with open(result.file_path, "rb") as f:
                return f.read()
        
        return b""
