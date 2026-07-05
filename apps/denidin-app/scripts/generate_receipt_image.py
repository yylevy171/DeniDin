"""
Generate a simple receipt image for testing.
"""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path


def create_receipt_image():
    """Create a simple receipt image with Hebrew text (RTL)."""
    # Create image
    width, height = 800, 1000
    img = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(img)
    
    # Use Arial font (supports Hebrew)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 32)
        small_font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 24)
    except:
        font = ImageFont.load_default()
        small_font = ImageFont.load_default()
    
    # Draw receipt content
    y = 50
    line_height = 40
    
    # Header (Hebrew - centered)
    draw.text((width//2, y), "קפה ישראלי", fill='black', font=font, anchor='mm')
    y += line_height * 2
    
    draw.text((width//2, y), "רחוב דיזנגוף 123, תל אביב", fill='black', font=small_font, anchor='mm')
    y += line_height * 2
    
    # Date (Hebrew)
    draw.text((width//2, y), "תאריך: 25/01/2026  שעה: 14:30", fill='black', font=small_font, anchor='mm')
    y += line_height * 2
    
    # Line
    draw.line([(100, y), (700, y)], fill='black', width=2)
    y += line_height
    
    # Items (Hebrew - RTL: price on left, item on right)
    items = [
        ("אספרסו", "12.00"),
        ("קפוצ'ינו", "15.00"),
        ("קרואסון", "18.00"),
        ("עוגה", "22.00"),
    ]
    
    for item, price in items:
        # RTL: Item name on RIGHT
        draw.text((650, y), item, fill='black', font=small_font, anchor='rm')
        # Price on LEFT
        draw.text((150, y), f"{price} ₪", fill='black', font=small_font, anchor='lm')
        y += line_height
    
    y += line_height // 2
    draw.line([(100, y), (700, y)], fill='black', width=2)
    y += line_height
    
    # Total (Hebrew - RTL)
    draw.text((650, y), "סה\"כ:", fill='black', font=font, anchor='rm')
    draw.text((150, y), "67.00 ₪", fill='black', font=font, anchor='lm')
    y += line_height * 2
    
    # Payment (Hebrew)
    draw.text((width//2, y), "אמצעי תשלום: מזומן", fill='black', font=small_font, anchor='mm')
    y += line_height
    
    draw.text((width//2, y), "תודה רבה!", fill='black', font=small_font, anchor='mm')
    
    # Save
    output_path = Path(__file__).parent.parent / "tests" / "fixtures" / "media" / "receipt_cafe.jpg"
    img.save(output_path, 'JPEG', quality=85)
    print(f"✅ Created: {output_path}")


if __name__ == "__main__":
    create_receipt_image()
