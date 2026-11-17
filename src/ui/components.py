"""GBA-style reusable UI components: Panels, TextBoxes, HPBars, EXPBars, Battle Platforms, and Menus."""
import pygame
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any, Union


# GBA Color Palette Constants
COLOR_BG_WHITE = (248, 248, 248)
COLOR_PANEL_BG = (240, 248, 248)
COLOR_CARD_BG = (248, 248, 240)      # Classic warm cream white for HP cards
COLOR_CARD_SHADOW = (168, 176, 184)  # 1px drop shadow for HP card frames
COLOR_BORDER_DARK = (32, 40, 64)     # Outer dark frame outline
COLOR_BORDER_MID = (96, 120, 160)
COLOR_BORDER_LIGHT = (184, 200, 224) # Inner highlight
COLOR_TEXT_DARK = (32, 32, 48)       # Primary readable retro text
COLOR_TEXT_SHADOW = (176, 184, 200)  # 1px text drop shadow

COLOR_HP_GREEN = (48, 208, 80)
COLOR_HP_YELLOW = (248, 192, 0)
COLOR_HP_RED = (248, 64, 48)
COLOR_HP_BG = (80, 80, 80)
COLOR_EXP_CYAN = (64, 168, 248)      # GBA experience bar cyan/blue

TYPE_COLORS = {
    "Normal": (168, 168, 120),
    "Fire": (240, 128, 48),
    "Water": (104, 144, 240),
    "Grass": (120, 200, 80),
    "Electric": (248, 208, 48),
    "Ice": (152, 216, 216),
    "Fighting": (192, 48, 40),
    "Poison": (160, 64, 160),
    "Ground": (224, 192, 104),
    "Flying": (168, 144, 240),
    "Psychic": (248, 88, 136),
    "Bug": (168, 184, 32),
    "Rock": (184, 160, 56),
    "Ghost": (112, 88, 152),
    "Dragon": (112, 56, 248),
}

STATUS_COLORS = {
    "PSN": (160, 64, 160),
    "POISON": (160, 64, 160),
    "PAR": (224, 176, 32),
    "PARALYZE": (224, 176, 32),
    "PARALYSIS": (224, 176, 32),
    "BRN": (240, 80, 32),
    "BURN": (240, 80, 32),
    "SLP": (136, 144, 152),
    "SLEEP": (136, 144, 152),
    "FRZ": (96, 192, 240),
    "FREEZE": (96, 192, 240),
    "FROZEN": (96, 192, 240),
}

FONTS_DIR = Path(__file__).resolve().parent.parent.parent / "assets" / "fonts"
_FONT_CACHE: Dict[Tuple[str, int], pygame.font.Font] = {}


def get_font(size: int = 10, font_name: Optional[str] = None) -> pygame.font.Font:
    """Return a crisp pixel font from assets/fonts/ with system fallback."""
    key = (font_name or "default", size)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]

    candidate_files = []
    if font_name:
        candidate_files.append(font_name)
    else:
        # Prioritize pokemon-font.ttf, then PressStart2P-Regular.ttf, then Silkscreen-Regular.ttf
        candidate_files.extend(["pokemon-font.ttf", "PressStart2P-Regular.ttf", "Silkscreen-Regular.ttf"])

    for fname in candidate_files:
        p = FONTS_DIR / fname if not Path(fname).is_absolute() else Path(fname)
        if p.is_file():
            try:
                f = pygame.font.Font(str(p), size)
                _FONT_CACHE[key] = f
                return f
            except (pygame.error, OSError):
                pass  # unreadable font file: try the next candidate

    # Fallback to retro system fonts
    try:
        for name in ["couriernew", "dejavusansmono", "monospace"]:
            matched = pygame.font.match_font(name)
            if matched:
                f = pygame.font.Font(matched, size)
                _FONT_CACHE[key] = f
                return f
    except (pygame.error, OSError, ImportError, AttributeError):
        pass  # system font lookup unavailable (seen with pygame.sysfont on Python 3.14)

    try:
        f = pygame.font.SysFont(None, size)
        _FONT_CACHE[key] = f
        return f
    except (pygame.error, OSError, ImportError, AttributeError):
        f = pygame.font.Font(None, size)
        _FONT_CACHE[key] = f
        return f


# Compact 5x7 bitmap representation for standard characters (embedded fallback)
_BITMAP_GLYPHS = {
    ' ': [0, 0, 0, 0, 0],
    'A': [0x7E, 0x11, 0x11, 0x11, 0x7E], 'B': [0x7F, 0x49, 0x49, 0x49, 0x36],
    'C': [0x3E, 0x41, 0x41, 0x41, 0x22], 'D': [0x7F, 0x41, 0x41, 0x22, 0x1C],
    'E': [0x7F, 0x49, 0x49, 0x49, 0x41], 'F': [0x7F, 0x09, 0x09, 0x09, 0x01],
    'G': [0x3E, 0x41, 0x49, 0x49, 0x7A], 'H': [0x7F, 0x08, 0x08, 0x08, 0x7F],
    'I': [0x00, 0x41, 0x7F, 0x41, 0x00], 'J': [0x20, 0x40, 0x41, 0x3F, 0x01],
    'K': [0x7F, 0x08, 0x14, 0x22, 0x41], 'L': [0x7F, 0x40, 0x40, 0x40, 0x40],
    'M': [0x7F, 0x02, 0x0C, 0x02, 0x7F], 'N': [0x7F, 0x04, 0x08, 0x10, 0x7F],
    'O': [0x3E, 0x41, 0x41, 0x41, 0x3E], 'P': [0x7F, 0x09, 0x09, 0x09, 0x06],
    'Q': [0x3E, 0x41, 0x51, 0x21, 0x5E], 'R': [0x7F, 0x09, 0x19, 0x29, 0x46],
    'S': [0x46, 0x49, 0x49, 0x49, 0x31], 'T': [0x01, 0x01, 0x7F, 0x01, 0x01],
    'U': [0x3F, 0x40, 0x40, 0x40, 0x3F], 'V': [0x1F, 0x20, 0x40, 0x20, 0x1F],
    'W': [0x7F, 0x20, 0x18, 0x20, 0x7F], 'X': [0x63, 0x14, 0x08, 0x14, 0x63],
    'Y': [0x07, 0x08, 0x70, 0x08, 0x07], 'Z': [0x61, 0x51, 0x49, 0x45, 0x43],
    '0': [0x3E, 0x51, 0x49, 0x45, 0x3E], '1': [0x00, 0x42, 0x7F, 0x40, 0x00],
    '2': [0x42, 0x61, 0x51, 0x49, 0x46], '3': [0x21, 0x41, 0x45, 0x4B, 0x31],
    '4': [0x18, 0x14, 0x12, 0x7F, 0x10], '5': [0x27, 0x45, 0x45, 0x45, 0x39],
    '6': [0x3C, 0x4A, 0x49, 0x49, 0x30], '7': [0x01, 0x71, 0x09, 0x05, 0x03],
    '8': [0x36, 0x49, 0x49, 0x49, 0x36], '9': [0x06, 0x49, 0x49, 0x29, 0x1E],
    '/': [0x20, 0x10, 0x08, 0x04, 0x02], ':': [0x00, 0x36, 0x36, 0x00, 0x00],
    '.': [0x00, 0x60, 0x60, 0x00, 0x00], '!': [0x00, 0x00, 0x5F, 0x00, 0x00],
    '?': [0x02, 0x01, 0x51, 0x09, 0x06], '-': [0x08, 0x08, 0x08, 0x08, 0x08],
}


def draw_bitmap_text(
    surface: pygame.Surface,
    text: str,
    x: int,
    y: int,
    color: Tuple[int, int, int] = COLOR_TEXT_DARK,
    shadow_color: Optional[Tuple[int, int, int]] = COLOR_TEXT_SHADOW,
) -> pygame.Rect:
    """Embedded 1-bit binary bitmap font fallback for guaranteed offline rendering."""
    cur_x = x
    max_h = 7
    total_w = 0

    if shadow_color is not None:
        s_cur_x = x + 1
        s_cur_y = y + 1
        for ch in text.upper():
            glyph = _BITMAP_GLYPHS.get(ch, _BITMAP_GLYPHS.get('?', [0x7F]*5))
            for col_idx, col in enumerate(glyph):
                for row_idx in range(7):
                    if (col >> row_idx) & 1:
                        px, py = s_cur_x + col_idx, s_cur_y + row_idx
                        if 0 <= px < surface.get_width() and 0 <= py < surface.get_height():
                            surface.set_at((px, py), shadow_color)
            s_cur_x += len(glyph) + 1

    for ch in text.upper():
        glyph = _BITMAP_GLYPHS.get(ch, _BITMAP_GLYPHS.get('?', [0x7F]*5))
        for col_idx, col in enumerate(glyph):
            for row_idx in range(7):
                if (col >> row_idx) & 1:
                    px, py = cur_x + col_idx, y + row_idx
                    if 0 <= px < surface.get_width() and 0 <= py < surface.get_height():
                        surface.set_at((px, py), color)
        cur_x += len(glyph) + 1
        total_w += len(glyph) + 1

    return pygame.Rect(x, y, max(1, total_w), max_h)


def draw_crisp_text(
    surface: pygame.Surface,
    text: str,
    x: int,
    y: int,
    font: Optional[pygame.font.Font] = None,
    color: Tuple[int, int, int] = COLOR_TEXT_DARK,
    shadow_color: Optional[Tuple[int, int, int]] = COLOR_TEXT_SHADOW,
) -> pygame.Rect:
    """Renders retro text with antialias=False and 1px drop shadow offset at (x+1, y+1)."""
    if font is None:
        font = get_font(10)

    try:
        if shadow_color is not None:
            shadow_surf = font.render(text, False, shadow_color)
            surface.blit(shadow_surf, (x + 1, y + 1))
        text_surf = font.render(text, False, color)
        surface.blit(text_surf, (x, y))
        return text_surf.get_rect(topleft=(x, y))
    except (pygame.error, AttributeError):
        # Font rendering unavailable: fall back to the embedded bitmap font
        return draw_bitmap_text(surface, text, x, y, color=color, shadow_color=shadow_color)


# ----------------------------------------------------------------------
# Text that must fit a box
# ----------------------------------------------------------------------
_OVERFLOW_LOG: List[Tuple[str, int, int]] = []


def reset_overflow_log() -> None:
    """Forget recorded overflows (tests call this before drawing a screen)."""
    _OVERFLOW_LOG.clear()


def overflow_log() -> List[Tuple[str, int, int]]:
    """(text, needed width, allowed width) for every string that didn't fit its box."""
    return list(_OVERFLOW_LOG)


def small_font() -> pygame.font.Font:
    """The compact pixel font used wherever space is tight."""
    return get_font(8, "Silkscreen-Regular.ttf")


def fit_font(text: str, max_width: int, font: pygame.font.Font) -> pygame.font.Font:
    """``font`` if ``text`` fits in ``max_width``, else the compact font."""
    if font.size(text)[0] <= max_width:
        return font
    return small_font()


def draw_fitted_text(
    surface: pygame.Surface,
    text: str,
    x: int,
    y: int,
    max_width: int,
    font: Optional[pygame.font.Font] = None,
    color: Tuple[int, int, int] = COLOR_TEXT_DARK,
    shadow_color: Optional[Tuple[int, int, int]] = COLOR_TEXT_SHADOW,
    align: str = "left",
) -> pygame.Rect:
    """Draw ``text`` inside ``max_width`` pixels.

    Uses ``font`` if it fits, otherwise the compact font. If even that is too
    wide the text is cut with ".." and the overflow is logged for the tests.
    """
    chosen = fit_font(text, max_width, font or get_font(10))
    shown = text
    if chosen.size(shown)[0] > max_width:
        _OVERFLOW_LOG.append((text, chosen.size(text)[0], max_width))
        while shown and chosen.size(shown + "..")[0] > max_width:
            shown = shown[:-1]
        shown += ".."
    width = chosen.size(shown)[0]
    if align == "right":
        x = x + max_width - width
    elif align == "center":
        x = x + (max_width - width) // 2
    return draw_crisp_text(surface, shown, x, y, chosen, color, shadow_color)


def wrap_text(text: str, max_width: int, font: pygame.font.Font) -> List[str]:
    """Split ``text`` into lines no wider than ``max_width`` (single long words are logged)."""
    lines: List[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if font.size(candidate)[0] <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    for line in lines:
        if font.size(line)[0] > max_width:
            _OVERFLOW_LOG.append((line, font.size(line)[0], max_width))
    return lines


def draw_gba_panel(
    surface: pygame.Surface,
    rect: pygame.Rect,
    fill_color: Tuple[int, int, int] = COLOR_PANEL_BG,
    border_dark: Tuple[int, int, int] = COLOR_BORDER_DARK,
    border_light: Tuple[int, int, int] = COLOR_BORDER_LIGHT,
) -> None:
    """Draw a classic double-bordered GBA dialog panel."""
    # Outer dark outline
    pygame.draw.rect(surface, border_dark, rect, border_radius=4)
    # Inner light highlight border
    inner_rect = rect.inflate(-2, -2)
    pygame.draw.rect(surface, border_light, inner_rect, border_radius=3)
    # Center fill
    fill_rect = inner_rect.inflate(-2, -2)
    pygame.draw.rect(surface, fill_color, fill_rect, border_radius=2)


def draw_status_pill(
    surface: pygame.Surface,
    x: int,
    y: int,
    status: str,
    font: Optional[pygame.font.Font] = None,
) -> pygame.Rect:
    """Draw a classic 22x9 colored GBA status badge (PSN, PAR, BRN, SLP, FRZ)."""
    if font is None:
        font = get_font(8, "pokemon-font.ttf")

    status_key = str(status).strip().upper()
    color = STATUS_COLORS.get(status_key, (128, 128, 128))
    label = status_key[:3]
    if status_key in ("POISON", "PSN"):
        label = "PSN"
    elif status_key in ("PARALYZE", "PARALYSIS", "PAR"):
        label = "PAR"
    elif status_key in ("BURN", "BRN"):
        label = "BRN"
    elif status_key in ("SLEEP", "SLP"):
        label = "SLP"
    elif status_key in ("FREEZE", "FROZEN", "FRZ"):
        label = "FRZ"

    pill_rect = pygame.Rect(x, y, 22, 9)
    # Dark outer frame
    pygame.draw.rect(surface, (32, 32, 48), pill_rect, border_radius=2)
    # Inner colored badge
    inner = pill_rect.inflate(-2, -2)
    pygame.draw.rect(surface, color, inner, border_radius=1)

    # Centered white label
    txt_surf = font.render(label, False, (255, 255, 255))
    tx = inner.centerx - txt_surf.get_width() // 2
    ty = inner.centery - txt_surf.get_height() // 2
    surface.blit(txt_surf, (tx, ty))
    return pill_rect


def draw_hp_badge(
    surface: pygame.Surface,
    x: int,
    y: int,
    font: Optional[pygame.font.Font] = None,
) -> pygame.Rect:
    """Draw classic GBA 'HP' pill badge (dark charcoal slot with gold HP lettering)."""
    badge_rect = pygame.Rect(x, y, 14, 7)
    pygame.draw.rect(surface, (32, 32, 32), badge_rect, border_radius=2)
    # Razor-sharp golden-yellow 3x5 'H' and 'P' pixel glyphs
    c = (248, 208, 48)
    hx = x + 3
    hy = y + 1
    # H
    for row in range(5):
        surface.set_at((hx, hy + row), c)
        surface.set_at((hx + 2, hy + row), c)
    surface.set_at((hx + 1, hy + 2), c)
    # P
    px = x + 7
    for row in range(5):
        surface.set_at((px, hy + row), c)
    surface.set_at((px + 1, hy), c)
    surface.set_at((px + 2, hy), c)
    surface.set_at((px + 2, hy + 1), c)
    surface.set_at((px + 1, hy + 2), c)
    surface.set_at((px + 2, hy + 2), c)
    return badge_rect


def draw_gba_hp_box(
    surface: pygame.Surface,
    rect: Union[pygame.Rect, Tuple[int, int, int, int]],
    name: str,
    level: int,
    current_hp: float,
    max_hp: int,
    exp_ratio: Optional[float] = None,
    status: Optional[str] = None,
) -> None:
    """Draw authentic GBA asymmetric notched HP card with HP badge, numeric readout, and EXP bar."""
    if isinstance(rect, tuple):
        rect = pygame.Rect(*rect)
    x, y, w, h = rect.x, rect.y, rect.width, rect.height
    is_player = (exp_ratio is not None)

    # 1. Asymmetric Notched Card Polygon
    notch = 7
    if not is_player:
        # Enemy HUD: Notched at bottom-right corner
        poly = [
            (x + 2, y),
            (x + w - 2, y),
            (x + w, y + 2),
            (x + w, y + h - notch),
            (x + w - notch, y + h),
            (x + 2, y + h),
            (x, y + h - 2),
            (x, y + 2),
        ]
        shadow_poly = [(px + 1, py + 1) for px, py in poly]
    else:
        # Player HUD: Notched at top-left corner
        poly = [
            (x + notch, y),
            (x + w - 2, y),
            (x + w, y + 2),
            (x + w, y + h - 2),
            (x + w - 2, y + h),
            (x + 2, y + h),
            (x, y + h - 2),
            (x, y + notch),
        ]
        shadow_poly = [(px + 1, py + 1) for px, py in poly]

    # Draw 1px card drop shadow
    pygame.draw.polygon(surface, COLOR_CARD_SHADOW, shadow_poly)
    # Draw card body
    pygame.draw.polygon(surface, COLOR_CARD_BG, poly)
    # Draw outer dark border
    pygame.draw.polygon(surface, COLOR_BORDER_DARK, poly, 1)

    # Inner highlight line
    if not is_player:
        pygame.draw.line(surface, COLOR_BORDER_LIGHT, (x + 2, y + 1), (x + w - 3, y + 1))
        pygame.draw.line(surface, COLOR_BORDER_LIGHT, (x + 1, y + 2), (x + 1, y + h - 3))
    else:
        pygame.draw.line(surface, COLOR_BORDER_LIGHT, (x + notch + 1, y + 1), (x + w - 3, y + 1))
        pygame.draw.line(surface, COLOR_BORDER_LIGHT, (x + 1, y + notch + 1), (x + 1, y + h - 3))

    # Font setup
    font = get_font(8, "Silkscreen-Regular.ttf")
    font_pk = get_font(8, "pokemon-font.ttf")

    # Row 1: Name and Level / Status Indicator
    name_x = x + (10 if is_player else 6)
    draw_crisp_text(surface, name.upper(), name_x, y + 3, font=font, color=COLOR_TEXT_DARK, shadow_color=COLOR_TEXT_SHADOW)

    has_status = status and str(status).strip().lower() not in ("none", "ok", "")
    if has_status:
        draw_status_pill(surface, x + w - 28, y + 3, str(status), font=font_pk)
    else:
        # Classic GBA Level badge: 'Lv' in amber/gold, number in dark
        lv_x = x + w - 30
        draw_crisp_text(surface, "Lv", lv_x, y + 3, font=font, color=(216, 128, 24), shadow_color=COLOR_TEXT_SHADOW)
        draw_crisp_text(surface, str(level), lv_x + 14, y + 3, font=font, color=COLOR_TEXT_DARK, shadow_color=COLOR_TEXT_SHADOW)

    # Row 2: HP Badge & HP Bar
    hp_badge_x = x + (12 if is_player else 7)
    hp_badge_y = y + 15
    draw_hp_badge(surface, hp_badge_x, hp_badge_y, font=font_pk)

    bar_x = hp_badge_x + 16
    bar_y = hp_badge_y + 1
    bar_w = w - (bar_x - x) - 8
    bar_h = 5

    hp_ratio = max(0.0, min(1.0, current_hp / max(1, max_hp)))
    pygame.draw.rect(surface, COLOR_HP_BG, (bar_x, bar_y, bar_w, bar_h))
    fill_w = int(bar_w * hp_ratio)
    if fill_w > 0:
        c = COLOR_HP_GREEN if hp_ratio > 0.5 else (COLOR_HP_YELLOW if hp_ratio > 0.2 else COLOR_HP_RED)
        pygame.draw.rect(surface, c, (bar_x, bar_y, fill_w, bar_h))
        # Top highlight line inside HP bar
        pygame.draw.line(surface, (255, 255, 255), (bar_x, bar_y), (bar_x + fill_w - 1, bar_y))
    pygame.draw.rect(surface, (32, 40, 48), (bar_x, bar_y, bar_w, bar_h), 1)

    # If player: Numeric HP readout and EXP Bar
    if is_player:
        hp_str = f"{int(current_hp):>2}/{int(max_hp):>2}"
        draw_crisp_text(surface, hp_str, x + w - 46, y + 23, font=font, color=COLOR_TEXT_DARK, shadow_color=COLOR_TEXT_SHADOW)

        # EXP Bar
        exp_y = y + 33
        draw_crisp_text(surface, "EXP", x + 12, exp_y - 2, font=font, color=(48, 80, 160), shadow_color=None)
        exp_bar_x = x + 30
        exp_bar_w = w - (exp_bar_x - x) - 8
        exp_bar_h = 3
        pygame.draw.rect(surface, (40, 48, 64), (exp_bar_x, exp_y, exp_bar_w, exp_bar_h))
        exp_fill = int(exp_bar_w * max(0.0, min(1.0, exp_ratio)))
        if exp_fill > 0:
            pygame.draw.rect(surface, COLOR_EXP_CYAN, (exp_bar_x, exp_y, exp_fill, exp_bar_h))
            pygame.draw.line(surface, (160, 224, 255), (exp_bar_x, exp_y), (exp_bar_x + exp_fill - 1, exp_y))
        pygame.draw.rect(surface, (24, 32, 48), (exp_bar_x, exp_y, exp_bar_w, exp_bar_h), 1)


def draw_battle_platform(
    surface: pygame.Surface,
    center_x: Any,
    center_y: Any = 0,
    width: int = 88,
    height: int = 26,
    is_player: bool = False,
) -> None:
    """Draw authentic tiered 3D GBA battle pedestal (grass top, dirt cliff, drop shadow)."""
    if isinstance(center_x, (pygame.Rect, tuple, list)):
        r = pygame.Rect(center_x) if isinstance(center_x, (tuple, list)) else center_x
        cx, cy, w, h = r.centerx, r.centery, r.width, r.height
        player = bool(center_y) if isinstance(center_y, bool) else is_player
    else:
        cx, cy, w, h = int(center_x), int(center_y), int(width), int(height)
        player = bool(is_player)

    # 1. Ground Drop Shadow (flattened ellipse on canvas)
    shadow_color = (176, 192, 168)
    shadow_rect = pygame.Rect(cx - w // 2 - 2, cy - h // 2 + (7 if player else 6), w + 4, h)
    pygame.draw.ellipse(surface, shadow_color, shadow_rect)

    # 2. 3D Layered Dirt Cliff Face / Bevel
    depth = 8 if player else 7
    dirt_dark = (88, 64, 32)
    dirt_mid = (136, 104, 56)
    dirt_light = (184, 152, 96)
    dirt_grain = (72, 48, 24)

    for d in range(depth, 0, -1):
        if d >= depth - 1:
            c = dirt_dark
        elif d > depth // 2:
            c = dirt_mid
        else:
            c = dirt_light
        layer_rect = pygame.Rect(cx - w // 2, cy - h // 2 + d, w, h)
        pygame.draw.ellipse(surface, c, layer_rect)

    # Dirt striations along the lower cliff rim
    rx = w // 2
    for offset_ratio in (-0.7, -0.4, -0.1, 0.2, 0.5, 0.7):
        px = int(cx + offset_ratio * (rx - 8))
        py = int(cy + h // 2 + (depth - 2) * (1.0 - abs(offset_ratio) * 0.4))
        if 0 <= px < surface.get_width() and 0 <= py < surface.get_height():
            surface.set_at((px, py), dirt_grain)
            if px + 1 < surface.get_width():
                surface.set_at((px + 1, py), dirt_grain)
            if px % 3 == 0 and py - 2 >= 0:
                surface.set_at((px, py - 2), (200, 168, 112))

    # 3. Grass Top Surface
    grass_dark = (48, 120, 48)
    grass_base = (72, 160, 64)
    grass_light = (112, 192, 88)
    fleck_light = (128, 208, 96)
    fleck_dark = (40, 96, 32)

    top_rect = pygame.Rect(cx - w // 2, cy - h // 2, w, h)
    pygame.draw.ellipse(surface, grass_dark, top_rect)

    # Front rim organic grass tufts breaking the ellipse boundary
    for step in range(-w // 2 + 6, w // 2 - 6, 6):
        tx = cx + step
        ty = cy + int((h // 2) * ((1.0 - (step / (w / 2.0)) ** 2) ** 0.5))
        if 0 <= tx < surface.get_width() and 0 <= ty + 2 < surface.get_height():
            pygame.draw.line(surface, grass_dark, (tx, ty), (tx + 1, ty + 2))
            pygame.draw.line(surface, grass_base, (tx - 1, ty - 1), (tx, ty + 1))

    # Main grass body
    inner_rect = top_rect.inflate(-2, -2)
    pygame.draw.ellipse(surface, grass_base, inner_rect)

    # Highlight crest at top of platform
    hl_rect = pygame.Rect(inner_rect.x + 4, inner_rect.y + 1, inner_rect.width - 8, max(4, inner_rect.height // 2))
    pygame.draw.ellipse(surface, grass_light, hl_rect)

    # Flecks of grass blades across top surface
    fleck_offsets = [
        (-0.5, -0.2), (-0.2, -0.3), (0.1, -0.25), (0.4, -0.15),
        (-0.6, 0.1), (-0.3, 0.15), (0.0, 0.2), (0.3, 0.1), (0.6, 0.05),
        (-0.1, -0.05), (0.2, 0.0), (-0.4, -0.1)
    ]
    for fx_r, fy_r in fleck_offsets:
        fx = int(cx + fx_r * (w // 2 - 6))
        fy = int(cy + fy_r * (h // 2 - 4))
        if 0 <= fx + 1 < surface.get_width() and 0 <= fy < surface.get_height():
            surface.set_at((fx, fy), fleck_light)
            surface.set_at((fx + 1, fy), fleck_dark)


class HPBar:
    """Animated smooth HP bar with GBA styling and color transitions."""

    def __init__(self, x: int, y: int, width: int = 50, height: int = 5):
        self.rect = pygame.Rect(x, y, width, height)
        self.display_hp: float = 1.0
        self.target_hp: float = 1.0
        self.max_hp: int = 100
        self.anim_speed: float = 2.0  # Fraction per second

    def set_hp(self, current: int, maximum: int, immediate: bool = False) -> None:
        self.max_hp = max(1, maximum)
        self.target_hp = max(0.0, min(1.0, current / self.max_hp))
        if immediate:
            self.display_hp = self.target_hp

    def update(self, dt: float) -> None:
        if self.display_hp != self.target_hp:
            diff = self.target_hp - self.display_hp
            step = self.anim_speed * dt
            if abs(diff) <= step:
                self.display_hp = self.target_hp
            else:
                self.display_hp += step if diff > 0 else -step

    def draw(self, surface: pygame.Surface) -> None:
        # Background slot
        pygame.draw.rect(surface, COLOR_HP_BG, self.rect)
        # HP Fill
        fill_width = max(0, int(self.rect.width * self.display_hp))
        if fill_width > 0:
            if self.display_hp > 0.5:
                color = COLOR_HP_GREEN
            elif self.display_hp > 0.2:
                color = COLOR_HP_YELLOW
            else:
                color = COLOR_HP_RED
            fill_rect = pygame.Rect(self.rect.x, self.rect.y, fill_width, self.rect.height)
            pygame.draw.rect(surface, color, fill_rect)
            # Top highlight line
            pygame.draw.line(surface, (255, 255, 255), (self.rect.x, self.rect.y), (self.rect.x + fill_width - 1, self.rect.y))

        # Border
        pygame.draw.rect(surface, (32, 40, 48), self.rect, 1)


class EXPBar:
    """Animated smooth EXP progress bar with GBA styling."""

    def __init__(self, x: int, y: int, width: int = 50, height: int = 3):
        self.rect = pygame.Rect(x, y, width, height)
        self.display_ratio: float = 0.0
        self.target_ratio: float = 0.0
        self.anim_speed: float = 2.0

    def set_ratio(self, ratio: float, immediate: bool = False) -> None:
        self.target_ratio = max(0.0, min(1.0, ratio))
        if immediate:
            self.display_ratio = self.target_ratio

    def update(self, dt: float) -> None:
        if self.display_ratio != self.target_ratio:
            diff = self.target_ratio - self.display_ratio
            step = self.anim_speed * dt
            if abs(diff) <= step:
                self.display_ratio = self.target_ratio
            else:
                self.display_ratio += step if diff > 0 else -step

    def draw(self, surface: pygame.Surface) -> None:
        # Background slot
        pygame.draw.rect(surface, (40, 48, 64), self.rect)
        fill_width = max(0, int(self.rect.width * self.display_ratio))
        if fill_width > 0:
            pygame.draw.rect(surface, COLOR_EXP_CYAN, (self.rect.x, self.rect.y, fill_width, self.rect.height))
            # 1px top highlight
            pygame.draw.line(surface, (160, 224, 255), (self.rect.x, self.rect.y), (self.rect.x + fill_width - 1, self.rect.y))
        pygame.draw.rect(surface, (24, 32, 48), self.rect, 1)


class TextBox:
    """Typewriter-effect bottom dialog box with pagination."""

    def __init__(self, rect: pygame.Rect):
        self.rect = rect
        self.font = get_font(8, "Silkscreen-Regular.ttf")
        self.message_queue: List[str] = []
        self.current_text = ""
        self.target_text = ""
        self.char_index = 0
        self.chars_per_second = 35.0
        self.timer = 0.0
        self.is_finished_typing = True

    def set_message(self, message: str) -> None:
        self.message_queue.clear()
        self.target_text = message
        self.current_text = ""
        self.char_index = 0
        self.is_finished_typing = False

    def _next_message(self) -> bool:
        if self.message_queue:
            self.target_text = self.message_queue.pop(0)
            self.current_text = ""
            self.char_index = 0
            self.is_finished_typing = False
            return True
        self.target_text = ""
        self.current_text = ""
        self.is_finished_typing = True
        return False

    def advance(self) -> bool:
        """User pressed confirm button to advance dialog."""
        if not self.is_finished_typing:
            # Instantly complete current line
            self.current_text = self.target_text
            self.char_index = len(self.target_text)
            self.is_finished_typing = True
            return True
        return self._next_message()

    def update(self, dt: float) -> None:
        if not self.is_finished_typing and self.target_text:
            self.timer += dt
            to_add = int(self.timer * self.chars_per_second)
            if to_add > 0:
                self.timer = 0.0
                self.char_index = min(len(self.target_text), self.char_index + to_add)
                self.current_text = self.target_text[:self.char_index]
                if self.char_index >= len(self.target_text):
                    self.is_finished_typing = True

    def draw(self, surface: pygame.Surface) -> None:
        if not self.target_text and not self.current_text:
            return

        draw_gba_panel(surface, self.rect)

        # Word wrap rendering (max 2 lines)
        words = self.current_text.split(" ")
        lines: List[str] = []
        cur_line = ""
        for w in words:
            test = (cur_line + " " + w).strip()
            if self.font.size(test)[0] < self.rect.width - 24:
                cur_line = test
            else:
                if cur_line:
                    lines.append(cur_line)
                cur_line = w
        if cur_line:
            lines.append(cur_line)

        y_offset = self.rect.y + 7
        for line in lines[:2]:
            draw_crisp_text(
                surface,
                line,
                self.rect.x + 10,
                y_offset,
                font=self.font,
                color=COLOR_TEXT_DARK,
                shadow_color=COLOR_TEXT_SHADOW,
            )
            y_offset += 14

        # Draw red advance triangle indicator if waiting for input
        if self.is_finished_typing and self.target_text:
            tri = [
                (self.rect.right - 14, self.rect.bottom - 12),
                (self.rect.right - 6, self.rect.bottom - 12),
                (self.rect.right - 10, self.rect.bottom - 7),
            ]
            pygame.draw.polygon(surface, (208, 48, 48), tri)
            pygame.draw.polygon(surface, (80, 20, 20), tri, 1)


class MenuBox:
    """Navigable menu box with GBA pointer arrow."""

    def __init__(self, rect: pygame.Rect, options: List[str], columns: int = 1,
                 visible_rows: Optional[int] = None):
        self.rect = rect
        self.options = options
        self.columns = columns
        self.selected_index = 0
        self.font = get_font(8, "Silkscreen-Regular.ttf")
        # When set, only this many rows are drawn and the list scrolls with the cursor.
        self.visible_rows = visible_rows
        self.scroll_row = 0

    def _keep_selection_visible(self) -> None:
        if not self.visible_rows:
            return
        row = self.selected_index // self.columns
        if row < self.scroll_row:
            self.scroll_row = row
        elif row >= self.scroll_row + self.visible_rows:
            self.scroll_row = row - self.visible_rows + 1

    def handle_input(self, key: int) -> Optional[int]:
        """Navigate menu. Returns selected index when Enter/Space/Z pressed."""
        num = len(self.options)
        if num == 0:
            return None

        if key in (pygame.K_UP, pygame.K_w):
            self.selected_index = (self.selected_index - self.columns) % num
        elif key in (pygame.K_DOWN, pygame.K_s):
            self.selected_index = (self.selected_index + self.columns) % num
        elif key in (pygame.K_LEFT, pygame.K_a):
            self.selected_index = (self.selected_index - 1) % num
        elif key in (pygame.K_RIGHT, pygame.K_d):
            self.selected_index = (self.selected_index + 1) % num
        elif key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_z):
            return self.selected_index
        self._keep_selection_visible()
        return None

    def draw(self, surface: pygame.Surface) -> None:
        draw_gba_panel(surface, self.rect)
        if not self.options:
            return

        total_rows = (len(self.options) + self.columns - 1) // self.columns
        rows = min(total_rows, self.visible_rows) if self.visible_rows else total_rows
        first_row = self.scroll_row if self.visible_rows else 0
        col_w = (self.rect.width - 12) // self.columns
        # With visible_rows the row height is fixed, so short lists don't spread out.
        row_h = (self.rect.height - 10) // max(1, self.visible_rows or rows)

        for i, opt in enumerate(self.options):
            r = i // self.columns - first_row
            c = i % self.columns
            if not 0 <= r < rows:
                continue
            x = self.rect.x + 8 + (c * col_w)
            y = self.rect.y + 6 + (r * row_h)

            if i == self.selected_index:
                # GBA pointer arrow polygon
                arrow_pts = [
                    (x, y + 2),
                    (x + 5, y + 5),
                    (x, y + 8),
                ]
                pygame.draw.polygon(surface, (216, 48, 32), arrow_pts)
                pygame.draw.polygon(surface, (120, 24, 16), arrow_pts, 1)

            draw_crisp_text(
                surface,
                opt,
                x + 9,
                y,
                font=self.font,
                color=COLOR_TEXT_DARK,
                shadow_color=COLOR_TEXT_SHADOW,
            )

        # Small scroll arrows when more rows are hidden above/below
        if self.visible_rows and total_rows > rows:
            cx = self.rect.right - 9
            if first_row > 0:
                pygame.draw.polygon(surface, (216, 48, 32),
                                    [(cx - 3, self.rect.y + 8), (cx + 3, self.rect.y + 8), (cx, self.rect.y + 4)])
            if first_row + rows < total_rows:
                by = self.rect.bottom - 8
                pygame.draw.polygon(surface, (216, 48, 32), [(cx - 3, by - 4), (cx + 3, by - 4), (cx, by)])
