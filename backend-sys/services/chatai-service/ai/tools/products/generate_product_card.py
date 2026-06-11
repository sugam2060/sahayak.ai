import io
import logging
import xml.etree.ElementTree as ET
import httpx
from typing import Annotated
from PIL import Image, ImageDraw, ImageFont
from jinja2 import Template
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

logger = logging.getLogger("chatai_service.ai.tools.products.generate_product_card")

SVG_TEMPLATE = """
<svg width="1000" height="1500">
  <!-- Background rect -->
  <rect x="0" y="0" width="1000" height="1500" rx="30" fill="#FFFFFF" stroke="#F1F5F9" stroke_width="3"/>
  
  <!-- Image -->
  <image href="{{ image_url }}" x="0" y="0" width="1000" height="900"/>
  
  <!-- Title -->
  <text x="50" y="960" fill="#0F172A" font_size="44" font_weight="bold">{{ name }}</text>
  
  <!-- Description -->
  <text x="50" y="1080" fill="#64748B" font_size="28" font_weight="normal">{{ description }}</text>
  
  <!-- Price -->
  <text x="50" y="1410" fill="#4F46E5" font_size="52" font_weight="black">{{ price }}</text>
  
  <!-- Badge -->
  <rect x="730" y="1360" width="220" height="60" rx="15" fill="#EEF2FF" stroke="#E0E7FF" stroke_width="1.5"/>
  <text x="760" y="1398" fill="#4F46E5" font_size="20" font_weight="bold">Quick Details</text>
</svg>
"""


def wrap_text(text, font, max_width):
    """Accurately wrap text based on font size measurements."""
    words = text.split()
    lines = []
    current_line = []
    for word in words:
        current_line.append(word)
        line_str = " ".join(current_line)
        try:
            bbox = font.getbbox(line_str)
            w = bbox[2] - bbox[0]
        except AttributeError:
            try:
                w = font.getsize(line_str)[0]
            except AttributeError:
                w = len(line_str) * (font.size // 2 if hasattr(font, "size") else 9)
        
        if w > max_width:
            current_line.pop()
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]
    if current_line:
        lines.append(" ".join(current_line))
    return lines


def _draw_pillow_card(product) -> bytes:
    """Render a card matching the frontend template layout exactly (800x1100)."""
    # Create Pillow image
    width, height = 800, 1100
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    
    # Draw background card (White with grey border and rounded corners)
    draw.rounded_rectangle(
        [0, 0, width, height],
        radius=24,
        fill="#FFFFFF",
        outline="#F1F5F9",
        width=2
    )
    
    # Fonts helper
    fonts = {}
    def get_font(size, bold=False):
        key = (size, bold)
        if key not in fonts:
            try:
                font_name = "arialbd.ttf" if bold else "arial.ttf"
                fonts[key] = ImageFont.truetype(font_name, size)
            except Exception:
                try:
                    font_path = "C:\\Windows\\Fonts\\arialbd.ttf" if bold else "C:\\Windows\\Fonts\\arial.ttf"
                    fonts[key] = ImageFont.truetype(font_path, size)
                except Exception:
                    try:
                        linux_font = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
                        fonts[key] = ImageFont.truetype(linux_font, size)
                    except Exception:
                        fonts[key] = ImageFont.load_default()
        return fonts[key]

    # Image Area: x=0, y=0, w=800, h=750
    draw.rectangle([2, 2, 798, 750], fill="#F8FAFC")
    
    if product.image:
        try:
            with httpx.Client() as client:
                resp = client.get(product.image, timeout=8.0)
                if resp.status_code == 200:
                    prod_img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
                    # Object cover resize & crop:
                    img_w, img_h = prod_img.size
                    aspect_ratio = img_w / img_h
                    target_ratio = 800 / 750
                    if aspect_ratio > target_ratio:
                        new_h = 750
                        new_w = int(750 * aspect_ratio)
                        prod_img = prod_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                        crop_x = (new_w - 800) // 2
                        prod_img = prod_img.crop((crop_x, 0, crop_x + 800, 750))
                    else:
                        new_w = 800
                        new_h = int(800 / aspect_ratio)
                        prod_img = prod_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                        crop_y = (new_h - 750) // 2
                        prod_img = prod_img.crop((0, crop_y, 800, crop_y + 750))
                    
                    # Create mask for rounded top corners
                    mask = Image.new("L", (800, 750), 0)
                    mask_draw = ImageDraw.Draw(mask)
                    mask_draw.rounded_rectangle([0, 0, 800, 1100], radius=24, fill=255)
                    
                    image.paste(prod_img, (0, 0), mask)
        except Exception as ex:
            logger.error(f"Failed to fetch and render cover image: {ex}")
            
    # Redraw the top border portion to keep corners rounded nicely
    draw.rounded_rectangle(
        [0, 0, width, height],
        radius=24,
        fill=None,
        outline="#F1F5F9",
        width=2
    )

    # Divider line
    draw.line([0, 750, width, 750], fill="#F1F5F9", width=2)
    
    # Title
    title_font = get_font(30, bold=True)
    title_text = product.name or "Unnamed Product"
    while True:
        bbox = title_font.getbbox(title_text)
        w = bbox[2] - bbox[0]
        if w <= 720 or len(title_text) <= 3:
            break
        title_text = title_text[:-4] + "..."
    draw.text((40, 790), title_text, fill="#0F172A", font=title_font)
    
    # Description
    desc_font = get_font(16, bold=False)
    desc_text = product.description or "No description provided."
    lines = wrap_text(desc_text, desc_font, 720)
    
    if len(lines) > 3:
        lines = lines[:3]
        last_line = lines[2]
        while True:
            bbox = desc_font.getbbox(last_line + "...")
            w = bbox[2] - bbox[0]
            if w <= 720 or len(last_line) <= 3:
                break
            last_line = last_line[:-1]
        lines[2] = last_line + "..."
        
    curr_y = 846
    for line in lines:
        draw.text((40, curr_y), line, fill="#64748B", font=desc_font)
        curr_y += 26
        
    # Price formatting
    currency_upper = (product.currency or "NPR").upper()
    symbol_map = {
        "USD": "$",
        "EUR": "€",
        "GBP": "£",
        "INR": "₹",
        "CAD": "CA$",
        "AUD": "A$",
        "JPY": "¥",
    }
    symbol = symbol_map.get(currency_upper, f"{currency_upper}\u00a0")
    try:
        val = float(product.price)
        formatted_num = f"{val:,.2f}"
    except Exception:
        formatted_num = str(product.price)
    price_text = f"{symbol}{formatted_num}"
    
    # Draw Price
    price_font = get_font(36, bold=True)
    draw.text((40, 1010), price_text, fill="#4F46E5", font=price_font)
    
    # Quick Details button
    btn_font = get_font(14, bold=True)
    btn_text = "Quick Details"
    
    btn_bbox = btn_font.getbbox(btn_text)
    btn_w = btn_bbox[2] - btn_bbox[0]
    rect_w = btn_w + 32
    rect_h = 38
    rect_x = width - 40 - rect_w
    rect_y = 1012
    
    draw.rounded_rectangle(
        [rect_x, rect_y, rect_x + rect_w, rect_y + rect_h],
        radius=12,
        fill="#EEF2FF",
        outline="#E0E7FF",
        width=1
    )
    
    text_x = rect_x + 16
    text_y = rect_y + (rect_h - 14) // 2 - 2
    draw.text((text_x, text_y), btn_text, fill="#4F46E5", font=btn_font)
    
    # Save to bytes
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format="PNG")
    return img_byte_arr.getvalue()


@tool
def generate_product_card(
    product_ids: list[str],
    organization_id: Annotated[str, InjectedState("organization_id")] = ""
) -> str:
    """Generate visual product cards (PNG images) for the specified product UUIDs.
    Call this tool automatically whenever a customer expresses interest in purchasing a product,
    asks about pricing/availability, wants to buy an item (e.g. 'I want to buy a headset'),
    or when listing product recommendations, so they get a clean visual summary of the products.
    Do not wait for them to explicitly ask for a card or image.
    
    Args:
        product_ids: List of product UUIDs to generate cards for.
        organization_id: The organization ID (injected from state).
    """
    return f"Generating product cards for {product_ids}"
