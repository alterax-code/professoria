#!/usr/bin/env python3
"""Etat persistant de Professoria : profil eleve, maitrise, rappels espaces, choix de la notion suivante."""
import argparse
import datetime
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

HOME = Path(os.environ.get("PROFESSORIA_HOME", Path.home() / ".professoria"))
TEMPLATES = Path(__file__).resolve().parent.parent / "templates"

INTERVALLES_RAPPEL = [1, 3, 7, 14, 30, 60]
SEUIL_MAITRISE = 80
SEUIL_FRAGILE = 50
SEUIL_PREREQUIS = 70
SEUIL_BLOQUE = 3
MAX_ERREURS = 12
MAX_RAPPELS_SESSION = 3


def today():
    return datetime.date.today()


def slugify(texte):
    t = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-zA-Z0-9]+", "-", t.lower()).strip("-")
    return t or "sujet"


def chemins(slug):
    base = HOME / slug
    return base, base / "curriculum.json", base / "learner.json"


def charger(p):
    if not p.exists():
        sys.exit(f"ERREUR: fichier introuvable: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def sauver(p, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)


def sortie(data):
    print(json.dumps(data, ensure_ascii=False, indent=2))


def etat_vide(niveau_base=1):
    return {
        "maitrise": 0,
        "statut": "nouveau",
        "difficulte": max(1, min(5, niveau_base)),
        "tentatives": 0,
        "echecs_consecutifs": 0,
        "derniere_eval": None,
        "prochain_rappel": None,
        "etape_rappel": 0,
        "erreurs": [],
    }


def iter_notions(cur):
    for m in cur.get("modules", []):
        for n in m.get("notions", []):
            yield m, n


def statut_de(maitrise, echecs):
    if echecs >= SEUIL_BLOQUE:
        return "bloque"
    if maitrise >= SEUIL_MAITRISE:
        return "maitrise"
    if maitrise >= SEUIL_FRAGILE:
        return "en_cours"
    return "fragile"


def charger_tout(slug):
    base, pc, pl = chemins(slug)
    ln = charger(pl)
    cur = json.loads(pc.read_text(encoding="utf-8")) if pc.exists() else None
    if cur:
        for _, n in iter_notions(cur):
            ln["notions"].setdefault(n["id"], etat_vide(n.get("niveau_base", 1)))
    return base, pc, pl, cur, ln


def planifier_rappel(e):
    if e["statut"] == "maitrise":
        jours = INTERVALLES_RAPPEL[min(e["etape_rappel"], len(INTERVALLES_RAPPEL) - 1)]
        e["prochain_rappel"] = (today() + datetime.timedelta(days=jours)).isoformat()
    else:
        e["prochain_rappel"] = None


def cmd_slug(a):
    print(slugify(a.sujet))


def sujets_proches(slug):
    if not HOME.exists():
        return []
    mots = set(slug.split("-"))
    proches = []
    for d in HOME.iterdir():
        if d.is_dir() and d.name != slug and (d / "learner.json").exists():
            autres = set(d.name.split("-"))
            if mots & autres or d.name.startswith(slug[:4]) or slug.startswith(d.name[:4]):
                proches.append(d.name)
    return sorted(proches)


def cmd_init(a):
    slug = slugify(a.sujet)
    base, pc, pl = chemins(slug)
    existe = pl.exists()
    if not existe and not a.creer:
        proches = sujets_proches(slug)
        if proches:
            sortie({"slug": slug, "deja_existant": False, "sujets_proches": proches,
                    "action": "demander a l'eleve s'il veut reprendre un de ces sujets ou en creer un nouveau (relancer avec --creer)"})
            return
    if not existe:
        ln = json.loads((TEMPLATES / "learner.json").read_text(encoding="utf-8"))
        ln["sujet"] = a.sujet
        ln["slug"] = slug
        sauver(pl, ln)
    for d in ("contenu", "brouillon"):
        (base / d).mkdir(parents=True, exist_ok=True)
    sortie({
        "slug": slug,
        "dossier": str(base),
        "deja_existant": existe,
        "curriculum_present": pc.exists(),
        "template_curriculum": str(TEMPLATES / "curriculum.json"),
    })


def cmd_profil(a):
    base, pc, pl, cur, ln = charger_tout(a.slug)
    for kv in a.set or []:
        cle, _, val = kv.partition("=")
        if cle == "preferences":
            ln["profil"].setdefault("preferences", [])
            if val and val not in ln["profil"]["preferences"]:
                ln["profil"]["preferences"].append(val)
        else:
            ln["profil"][cle] = val
    sauver(pl, ln)
    sortie(ln["profil"])


def cmd_valider_curriculum(a):
    base, pc, pl, cur, ln = charger_tout(a.slug)
    if not cur:
        sys.exit("ERREUR: curriculum.json absent")
    ids = [n["id"] for _, n in iter_notions(cur)]
    erreurs = []
    if len(ids) != len(set(ids)):
        erreurs.append("identifiants de notions en double")
    vus = set()
    for _, n in iter_notions(cur):
        for p in n.get("prerequis", []):
            if p not in ids:
                erreurs.append(f"{n['id']}: prerequis inconnu {p}")
            elif p not in vus:
                erreurs.append(f"{n['id']}: prerequis {p} place apres la notion")
        vus.add(n["id"])
        if not n.get("objectifs"):
            erreurs.append(f"{n['id']}: aucun objectif")
    if erreurs:
        sortie({"valide": False, "erreurs": erreurs})
        sys.exit(1)
    cur["verifie"] = True
    cur.setdefault("cree_le", today().isoformat())
    sauver(pc, cur)
    sauver(pl, ln)
    sortie({"valide": True, "notions": len(ids), "modules": len(cur["modules"])})


def prerequis_ok(n, ln):
    return all(ln["notions"].get(p, {}).get("maitrise", 0) >= SEUIL_PREREQUIS for p in n.get("prerequis", []))


def resume_notion(m, n, e, raison):
    return {
        "id": n["id"],
        "titre": n["titre"],
        "module": m["titre"],
        "raison": raison,
        "maitrise": e["maitrise"],
        "statut": e["statut"],
        "difficulte": e["difficulte"],
        "erreurs_recentes": e["erreurs"][-5:],
        "objectifs": n.get("objectifs", []),
        "prerequis": n.get("prerequis", []),
    }


def cmd_suivant(a):
    base, pc, pl, cur, ln = charger_tout(a.slug)
    if not cur or not cur.get("verifie"):
        sortie({"etape": "initialisation", "message": "curriculum absent ou non verifie"})
        return
    t = today().isoformat()
    rappels, bloques, a_renforcer, nouvelles = [], [], [], []
    for m, n in iter_notions(cur):
        e = ln["notions"][n["id"]]
        if e["statut"] == "maitrise" and e["prochain_rappel"] and e["prochain_rappel"] <= t:
            rappels.append(resume_notion(m, n, e, "rappel espace"))
        elif e["statut"] == "bloque":
            bloques.append((m, n, e))
        elif e["statut"] in ("fragile", "en_cours"):
            a_renforcer.append((m, n, e))
        elif e["statut"] == "nouveau" and prerequis_ok(n, ln):
            nouvelles.append((m, n, e))

    focus = None
    if bloques:
        m, n, e = bloques[0]
        manquants = [p for p in n.get("prerequis", [])]
        focus = resume_notion(m, n, e, "bloquee : reprendre autrement, verifier les prerequis " + ", ".join(manquants))
    elif a_renforcer:
        m, n, e = min(a_renforcer, key=lambda x: x[2]["maitrise"])
        focus = resume_notion(m, n, e, "renforcement des points non acquis")
    elif nouvelles:
        m, n, e = nouvelles[0]
        focus = resume_notion(m, n, e, "nouvelle notion")

    total = len(ln["notions"])
    acquis = sum(1 for e in ln["notions"].values() if e["statut"] == "maitrise")
    sortie({
        "etape": "termine" if not focus and not rappels else "boucle",
        "focus": focus,
        "rappels": rappels[:MAX_RAPPELS_SESSION],
        "progression": f"{acquis}/{total} notions maitrisees",
        "niveau_global": ln["niveau_global"],
        "profil": ln["profil"],
        "cours_en_cache": sorted(p.name for p in (base / "contenu" / focus["id"]).glob("cours_d*.md")) if focus else [],
    })


def cmd_noter(a):
    base, pc, pl, cur, ln = charger_tout(a.slug)
    if a.notion not in ln["notions"]:
        sys.exit(f"ERREUR: notion inconnue {a.notion}")
    e = ln["notions"][a.notion]
    s = max(0, min(100, a.score))
    ancien = e["maitrise"]
    nouvelles_erreurs = [x.strip() for x in (a.erreurs or "").split(";") if x.strip()]

    if a.type == "diagnostic":
        e["maitrise"] = s
        e["difficulte"] = max(1, min(5, 1 + s // 25))
        e["echecs_consecutifs"] = 0
    elif a.type == "evaluation":
        e["maitrise"] = s if e["tentatives"] == 0 else round(0.6 * s + 0.4 * ancien)
        e["tentatives"] += 1
        e["derniere_eval"] = today().isoformat()
        if s >= 85:
            e["difficulte"] = min(5, e["difficulte"] + 1)
            e["erreurs"] = []
        elif s < SEUIL_FRAGILE:
            e["difficulte"] = max(1, e["difficulte"] - 1)
        e["echecs_consecutifs"] = e["echecs_consecutifs"] + 1 if s < SEUIL_FRAGILE else 0
    elif a.type == "rappel":
        if s >= 70:
            e["etape_rappel"] += 1
            e["maitrise"] = max(ancien, round(0.8 * ancien + 0.2 * s))
        else:
            e["etape_rappel"] = 0
            e["maitrise"] = min(SEUIL_MAITRISE - 1, round(0.5 * ancien + 0.5 * s))
    elif a.type == "exercice":
        pass

    for err in nouvelles_erreurs:
        if err not in e["erreurs"]:
            e["erreurs"].append(err)
    e["erreurs"] = e["erreurs"][-MAX_ERREURS:]

    avant = e["statut"]
    e["statut"] = statut_de(e["maitrise"], e["echecs_consecutifs"])
    if e["statut"] == "maitrise" and avant != "maitrise":
        e["etape_rappel"] = 0
    if a.type != "exercice":
        planifier_rappel(e)

    tentes = [x["difficulte"] for x in ln["notions"].values() if x["statut"] != "nouveau"]
    if tentes:
        ln["niveau_global"] = round(sum(tentes) / len(tentes))
    ln["historique"].append({
        "date": today().isoformat(),
        "notion": a.notion,
        "type": a.type,
        "score": s,
        "erreurs": nouvelles_erreurs,
    })
    ln["historique"] = ln["historique"][-500:]
    ln["derniere_session"] = today().isoformat()
    sauver(pl, ln)
    sortie({"notion": a.notion, "avant": {"maitrise": ancien, "statut": avant}, "apres": e})


def cmd_debloquer(a):
    base, pc, pl, cur, ln = charger_tout(a.slug)
    e = ln["notions"][a.notion]
    e["echecs_consecutifs"] = 0
    e["statut"] = statut_de(e["maitrise"], 0)
    sauver(pl, ln)
    sortie({"notion": a.notion, "statut": e["statut"]})


def cmd_bilan(a):
    base, pc, pl, cur, ln = charger_tout(a.slug)
    lignes = [f"Sujet : {ln['sujet']}  |  niveau global : {ln['niveau_global']}/5"]
    if cur:
        for m in cur["modules"]:
            lignes.append(f"\n[{m['id']}] {m['titre']}")
            for n in m["notions"]:
                e = ln["notions"][n["id"]]
                r = f"  rappel le {e['prochain_rappel']}" if e["prochain_rappel"] else ""
                lignes.append(f"  {n['id']:<8} {e['statut']:<9} {e['maitrise']:>3}%  d{e['difficulte']}  {n['titre']}{r}")
    erreurs = [(nid, x) for nid, e in ln["notions"].items() for x in e["erreurs"][-3:]]
    if erreurs:
        lignes.append("\nErreurs recentes :")
        lignes += [f"  {nid} : {x}" for nid, x in erreurs[-10:]]
    print("\n".join(lignes))


def cmd_liste(a):
    res = []
    if HOME.exists():
        for d in sorted(HOME.iterdir()):
            pl = d / "learner.json"
            if pl.exists():
                ln = json.loads(pl.read_text(encoding="utf-8"))
                total = len(ln["notions"])
                acquis = sum(1 for e in ln["notions"].values() if e["statut"] == "maitrise")
                res.append({"slug": d.name, "sujet": ln["sujet"], "progression": f"{acquis}/{total}"})
    sortie(res)


def main():
    p = argparse.ArgumentParser(prog="state.py")
    sp = p.add_subparsers(dest="cmd", required=True)

    x = sp.add_parser("slug"); x.add_argument("sujet"); x.set_defaults(f=cmd_slug)
    x = sp.add_parser("init"); x.add_argument("sujet"); x.add_argument("--creer", action="store_true"); x.set_defaults(f=cmd_init)
    x = sp.add_parser("profil"); x.add_argument("slug"); x.add_argument("--set", action="append"); x.set_defaults(f=cmd_profil)
    x = sp.add_parser("valider-curriculum"); x.add_argument("slug"); x.set_defaults(f=cmd_valider_curriculum)
    x = sp.add_parser("suivant"); x.add_argument("slug"); x.set_defaults(f=cmd_suivant)
    x = sp.add_parser("noter"); x.add_argument("slug"); x.add_argument("notion")
    x.add_argument("type", choices=["diagnostic", "evaluation", "rappel", "exercice"])
    x.add_argument("score", type=int); x.add_argument("--erreurs", default="")
    x.set_defaults(f=cmd_noter)
    x = sp.add_parser("debloquer"); x.add_argument("slug"); x.add_argument("notion"); x.set_defaults(f=cmd_debloquer)
    x = sp.add_parser("bilan"); x.add_argument("slug"); x.set_defaults(f=cmd_bilan)
    x = sp.add_parser("liste"); x.set_defaults(f=cmd_liste)

    a = p.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
