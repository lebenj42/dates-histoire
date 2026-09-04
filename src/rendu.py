"""Fabrication des slides du carrousel (1080 x 1350, format 4:5 Instagram)."""
from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from .images import credit_court
from .texte import date_longue

log = logging.getLogger("rendu")

RACINE = Path(__file__).resolve().parent.parent
POLICES = RACINE / "assets" / "fonts"
SECOURS = ["/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
           "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]


def police(nom: str, taille: int) -> ImageFont.FreeTypeFont:
    p = POLICES / nom
    if p.exists():
        return ImageFont.truetype(str(p), taille)
    serif = "Playfair" in nom
    for s in SECOURS:
        if Path(s).exists() and (("Serif" in s) == serif):
            return ImageFont.truetype(s, taille)
    return ImageFont.load_default(taille)


def _rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _recadrer(img: Image.Image, l: int, h: int, biais: float = 0.38) -> Image.Image:
    """Recadrage 'cover' avec un cadrage haut : on ne coupe pas les visages."""
    r_cible, r_src = l / h, img.width / img.height
    if r_src > r_cible:
        nh = img.height
        nl = int(nh * r_cible)
        x = (img.width - nl) // 2
        img = img.crop((x, 0, x + nl, nh))
    else:
        nl = img.width
        nh = int(nl / r_cible)
        y = int((img.height - nh) * biais)
        img = img.crop((0, y, nl, y + nh))
    return img.resize((l, h), Image.LANCZOS)


def _degrade_bas(calque: Image.Image, depart: int, fin: int, fond: tuple[int, int, int]) -> None:
    """Fond opaque en bas de la photo, pour que le texte reste lisible."""
    l = calque.width
    voile = Image.new("RGBA", (1, max(fin - depart, 1)))
    px = voile.load()
    for i in range(voile.height):
        t = i / max(voile.height - 1, 1)
        px[0, i] = (*fond, int(255 * (t ** 1.6)))
    calque.alpha_composite(voile.resize((l, voile.height)), (0, depart))


def _fleche(draw, x: int, y: int, couleur, taille: int = 26) -> None:
    """Fleche dessinee : le sous-ensemble latin des polices web n'a pas le glyphe U+2192."""
    draw.line([(x, y), (x + taille, y)], fill=couleur, width=3)
    draw.line([(x + taille - 9, y - 8), (x + taille, y), (x + taille - 9, y + 8)],
              fill=couleur, width=3, joint="curve")


def _voile(calque: Image.Image, fond: tuple[int, int, int], alpha: int) -> None:
    calque.alpha_composite(Image.new("RGBA", calque.size, (*fond, alpha)))


def _lignes(texte: str, font, largeur: int, draw) -> list[str]:
    mots, lignes, courante = texte.split(), [], ""
    for m in mots:
        essai = (courante + " " + m).strip()
        if draw.textlength(essai, font=font) <= largeur or not courante:
            courante = essai
        else:
            lignes.append(courante)
            courante = m
    if courante:
        lignes.append(courante)
    return lignes


def _bloc(draw, texte, font, xy, largeur, interligne, couleur, max_lignes=None):
    x, y = xy
    lignes = _lignes(texte, font, largeur, draw)
    if max_lignes and len(lignes) > max_lignes:
        lignes = lignes[:max_lignes]
        lignes[-1] = lignes[-1].rstrip(" ,;:") + "…"
    for ligne in lignes:
        draw.text((x, y), ligne, font=font, fill=couleur)
        y += interligne
    return y


def _espace(draw, texte, font, xy, couleur, ecart=6):
    x, y = xy
    for c in texte:
        draw.text((x, y), c, font=font, fill=couleur)
        x += draw.textlength(c, font=font) + ecart
    return x


def _fond_typographique(l, h, annee, fond, accent):
    img = Image.new("RGBA", (l, h), (*fond, 255))
    d = ImageDraw.Draw(img)
    f = police("PlayfairDisplay-ExtraBold.ttf", 420)
    t = str(abs(annee))
    d.text(((l - d.textlength(t, font=f)) / 2, h * 0.18), t, font=f, fill=(*accent, 26))
    for i in range(0, h, 6):
        d.line([(0, i), (l, i)], fill=(255, 255, 255, 4))
    return img


# ─────────────────────────────────────────────────────────────────────────────

def slide_couverture(jour, evenements, cfg) -> Image.Image:
    d_ = cfg["design"]
    L, H = d_["largeur"], d_["hauteur"]
    fond, txt, accent, doux = map(_rgb, (d_["fond"], d_["texte"], d_["accent"], d_["texte_doux"]))

    vedette = next((e for e in evenements if e.photo.get("fichier")), None)
    if vedette:
        base = Image.open(vedette.photo["fichier"]).convert("RGB")
        base = _recadrer(base, L, H, 0.32).filter(ImageFilter.GaussianBlur(1.6))
        base = ImageEnhance.Color(base).enhance(0.30)
        base = ImageEnhance.Brightness(base).enhance(0.62)
        base = ImageEnhance.Contrast(base).enhance(0.92)
        img = base.convert("RGBA")
    else:
        img = _fond_typographique(L, H, jour.year, fond, accent)
    _degrade_bas(img, int(H * 0.38), H, fond)
    _voile(img, fond, 45)

    d = ImageDraw.Draw(img)
    d.line([(90, 250), (250, 250)], fill=accent, width=3)
    _espace(d, cfg["page"]["baseline"].upper(), police("Inter-SemiBold.ttf", 27), (90, 285), accent, 7)

    f_date = police("PlayfairDisplay-ExtraBold.ttf", 118)
    y = 820
    for ligne in date_longue(jour).split(" "):
        d.text((90, y), ligne, font=f_date, fill=txt)
        y += 122
    d.line([(92, y + 26), (92 + 120, y + 26)], fill=accent, width=4)
    d.text((90, y + 60), f"{len(evenements)} événements qui ont marqué le monde",
           font=police("Inter-Regular.ttf", 35), fill=doux)

    d.text((90, H - 96), cfg["page"]["handle"], font=police("Inter-SemiBold.ttf", 30), fill=txt)
    fl = police("Inter-SemiBold.ttf", 30)
    libelle = "faites glisser"
    xf = L - 90 - d.textlength(libelle, font=fl) - 46
    d.text((xf, H - 96), libelle, font=fl, fill=accent)
    _fleche(d, L - 122, H - 82, accent)
    return img.convert("RGB")


def slide_evenement(ev, index, total, cfg) -> Image.Image:
    d_ = cfg["design"]
    L, H = d_["largeur"], d_["hauteur"]
    fond, txt, accent, doux = map(_rgb, (d_["fond"], d_["texte"], d_["accent"], d_["texte_doux"]))
    marge = 90
    largeur_txt = L - 2 * marge

    mesure = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    f_annee = police("PlayfairDisplay-ExtraBold.ttf", 86)
    f_titre = police("PlayfairDisplay-Bold.ttf", 52)
    f_res = police("Inter-Regular.ttf", 31)

    n_titre = min(len(_lignes(ev.titre, f_titre, largeur_txt, mesure)), 3)
    n_res = min(len(_lignes(ev.resume, f_res, largeur_txt, mesure)), 6)
    hauteur_texte = 96 + 30 + n_titre * 62 + 26 + n_res * 44
    photo_h = max(470, min(880, H - hauteur_texte - 150))

    img = Image.new("RGBA", (L, H), (*fond, 255))
    if ev.photo.get("fichier"):
        photo = Image.open(ev.photo["fichier"]).convert("RGB")
        photo = ImageEnhance.Color(_recadrer(photo, L, photo_h)).enhance(0.72)
        photo = ImageEnhance.Brightness(photo).enhance(0.86)
        img.paste(photo.convert("RGBA"), (0, 0))
    else:
        img.paste(_fond_typographique(L, photo_h, ev.annee, fond, accent), (0, 0))
    _degrade_bas(img, int(photo_h * 0.55), photo_h, fond)

    d = ImageDraw.Draw(img)
    # pastille de progression
    f_idx = police("Inter-SemiBold.ttf", 26)
    etq = f"{index}/{total}"
    w = d.textlength(etq, font=f_idx)
    d.rounded_rectangle([L - marge - w - 30, 60, L - marge + 2, 112], radius=26,
                        fill=(0, 0, 0, 110), outline=(*accent, 150), width=2)
    d.text((L - marge - w - 14, 71), etq, font=f_idx, fill=txt)

    y = photo_h - 30
    d.text((marge, y), str(ev.annee), font=f_annee, fill=accent)
    y += 96 + 12
    d.line([(marge + 2, y), (marge + 90, y)], fill=(*doux, 120), width=2)
    y += 18
    y = _bloc(d, ev.titre, f_titre, (marge, y), largeur_txt, 62, txt, 3)
    y += 26
    _bloc(d, ev.resume, f_res, (marge, y), largeur_txt, 44, doux, 6)

    credit = credit_court(ev.photo)
    if credit:
        f_c = police("Inter-Regular.ttf", 19)
        d.text((marge, H - 58), f"Photo : {credit}"[:96], font=f_c, fill=(*doux, 165))
    return img.convert("RGB")


def slide_finale(jour, cfg) -> Image.Image:
    d_ = cfg["design"]
    L, H = d_["largeur"], d_["hauteur"]
    fond, txt, accent, doux = map(_rgb, (d_["fond"], d_["texte"], d_["accent"], d_["texte_doux"]))
    img = Image.new("RGBA", (L, H), (*fond, 255))
    d = ImageDraw.Draw(img)
    d.rectangle([44, 44, L - 44, H - 44], outline=(*accent, 90), width=2)

    _espace(d, cfg["page"]["baseline"].upper(), police("Inter-SemiBold.ttf", 27), (110, 250), accent, 7)
    y = _bloc(d, "Chaque matin, une date qui a changé le monde.",
              police("PlayfairDisplay-ExtraBold.ttf", 76), (110, 470), L - 220, 92, txt)
    y += 40
    y = _bloc(d, "Enregistre ce carrousel pour le relire, et abonne-toi pour la date de demain.",
              police("Inter-Regular.ttf", 34), (110, y), L - 220, 48, doux)
    d.line([(112, y + 60), (232, y + 60)], fill=accent, width=4)
    d.text((110, y + 100), cfg["page"]["handle"], font=police("PlayfairDisplay-Bold.ttf", 54), fill=txt)
    d.text((110, H - 150), "Sources : Wikipédia · photos libres de droit créditées sur chaque slide",
           font=police("Inter-Regular.ttf", 22), fill=(*doux, 170))
    return img.convert("RGB")


def carrousel(jour, evenements, cfg, dossier: Path) -> list[Path]:
    dossier.mkdir(parents=True, exist_ok=True)
    total = len(evenements) + 2
    slides = [slide_couverture(jour, evenements, cfg)]
    slides += [slide_evenement(e, i + 2, total, cfg) for i, e in enumerate(evenements)]
    slides.append(slide_finale(jour, cfg))
    chemins = []
    for i, s in enumerate(slides):
        p = dossier / f"{i + 1:02d}.jpg"
        s.save(p, "JPEG", quality=90, optimize=True, progressive=True)
        chemins.append(p)
    log.info("%s slides generees dans %s", len(chemins), dossier)
    return chemins
