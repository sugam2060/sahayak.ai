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
    """Render a card using Jinja2 SVG template and Pillow."""
    # Format price
    try:
        formatted_price = f"{int(product.price):,} {product.currency}"
    except Exception:
        formatted_price = f"{product.price} {product.currency}"
    
    # Render template via Jinja2
    template = Template(SVG_TEMPLATE)
    svg_content = template.render(
        image_url=product.image or "",
        name=product.name,
        description=product.description or "No description provided.",
        price=formatted_price
    )
    
    # Parse rendered XML
    root = ET.fromstring(svg_content)
    
    # Get overall size
    width = int(root.attrib.get("width", 1000))
    height = int(root.attrib.get("height", 1500))
    
    # Create Pillow image
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    
    # Fonts cache
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
                    fonts[key] = ImageFont.load_default()
        return fonts[key]

    for elem in root:
        tag = elem.tag.split("}")[-1]
        if tag == "rect":
            x = int(elem.attrib.get("x", 0))
            y = int(elem.attrib.get("y", 0))
            w = int(elem.attrib.get("width", 0))
            h = int(elem.attrib.get("height", 0))
            rx = int(elem.attrib.get("rx", 0))
            fill = elem.attrib.get("fill", "#FFFFFF")
            stroke = elem.attrib.get("stroke", None)
            stroke_width = float(elem.attrib.get("stroke_width", 1))
            
            if rx > 0:
                draw.rounded_rectangle([x, y, x + w, y + h], radius=rx, fill=fill, outline=stroke, width=int(stroke_width))
            else:
                draw.rectangle([x, y, x + w, y + h], fill=fill, outline=stroke, width=int(stroke_width))
                
        elif tag == "image":
            href = elem.attrib.get("href", "")
            x = int(elem.attrib.get("x", 0))
            y = int(elem.attrib.get("y", 0))
            w = int(elem.attrib.get("width", 0))
            h = int(elem.attrib.get("height", 0))
            
            # Draw a soft background for the image slot
            draw.rectangle([x, y, x + w, y + h], fill="#F8FAFC")
            
            if href:
                try:
                    with httpx.Client() as client:
                        resp = client.get(href, timeout=5.0)
                        if resp.status_code == 200:
                            prod_img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
                            # Aspect ratio cover resize
                            prod_img.thumbnail((w, h))
                            offset_x = x + (w - prod_img.width) // 2
                            offset_y = y + (h - prod_img.height) // 2
                            image.paste(prod_img, (offset_x, offset_y), prod_img)
                except Exception as ex:
                    logger.error(f"Failed to fetch image: {ex}")
                    
        elif tag == "text":
            x = int(elem.attrib.get("x", 0))
            y = int(elem.attrib.get("y", 0))
            fill = elem.attrib.get("fill", "#000000")
            font_size = int(elem.attrib.get("font_size", 20))
            font_weight = elem.attrib.get("font_weight", "normal")
            text_content = elem.text or ""
            
            bold = font_weight in ("bold", "black")
            font = get_font(font_size, bold)
            
            max_width = width - x - 50 # 50px right margin
            is_badge = "Quick Details" in text_content or font_size < 22
            
            if not is_badge and max_width > 100:
                lines = wrap_text(text_content, font, max_width)
                curr_y = y
                line_height = font_size + int(font_size * 0.3)
                max_lines = 6 if font_size <= 28 else 2
                for line in lines[:max_lines]:
                    draw.text((x, curr_y), line, fill=fill, font=font)
                    curr_y += line_height
            else:
                draw.text((x, y), text_content, fill=fill, font=font)
                
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
