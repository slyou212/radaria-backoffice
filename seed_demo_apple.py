# -*- coding: utf-8 -*-
"""
Seed d'un compte demo dedie pour la review Apple (Guideline 2.1a).
Cree un client 'apple.review' pre-rempli : installation online (6 cameras),
alertes d'exemple, historique de sinistres, et images cameras.

Appele par la route /admin/seed-demo-apple du backoffice.
Idempotent : re-executable (supprime puis recree le client demo).
"""
import json, base64, secrets
from pathlib import Path
from datetime import datetime, timedelta

DEMO_USERNAME = "apple.review"
DEMO_PASSWORD = "RadarIA-Review-2026"
DEMO_MAGASIN  = "Boutique Demo (Apple Review)"

CAMS = ["Caisse", "Alcools", "Fond gauche", "Fond droite", "Allee centre", "Couloir Reserve"]

# (type, camera, minutes_avant_maintenant, nb_personnes)
ALERTES = [
    ("Vol",       "Alcools",         8,   1),
    ("Vol",       "Caisse",          47,  2),
    ("Intrusion", "Couloir Reserve", 95,  1),
    ("Vol",       "Fond droite",     160, 1),
    ("Vol",       "Allee centre",    240, 3),
    ("Intrusion", "Fond gauche",     380, 1),
    ("Vol",       "Alcools",         520, 2),
    ("Vol",       "Caisse",          700, 1),
]


def run_seed(get_db, snap_dir, hash_password):
    """get_db: fabrique de connexion (RealDictCursor). snap_dir: SNAP_DIR (Path).
    hash_password: fonction de hachage du backoffice. Retourne un dict recap."""
    imgs = json.loads((Path(__file__).parent / "seed_demo_apple_images.json").read_text())
    conn = get_db(); cur = conn.cursor()

    # 1) Nettoyage d'un eventuel compte demo existant
    cur.execute("SELECT id FROM clients WHERE username=%s", (DEMO_USERNAME,))
    row = cur.fetchone()
    if row:
        cid = row["id"]
        cur.execute("DELETE FROM alertes_centrales WHERE client_id=%s", (cid,))
        cur.execute("DELETE FROM installations   WHERE client_id=%s", (cid,))
        cur.execute("DELETE FROM sinistres        WHERE client_id=%s", (cid,))
        cur.execute("DELETE FROM clients          WHERE id=%s",        (cid,))

    # 2) Client demo
    lic = secrets.token_hex(16)
    cur.execute(
        """INSERT INTO clients
           (nom_magasin, contact_nom, contact_email, activite,
            username, password_hash, license_key, statut, prix_mensuel)
           VALUES (%s,%s,%s,%s,%s,%s,%s,'actif',0) RETURNING id""",
        (DEMO_MAGASIN, "Apple Reviewer", "contact@radaria.fr", "Commerce de detail",
         DEMO_USERNAME, hash_password(DEMO_PASSWORD), lic))
    cid = cur.fetchone()["id"]

    now = datetime.now()

    # 3) Installation "online" (6 cameras actives)
    cur.execute(
        """INSERT INTO installations
           (client_id, pc_hostname, ip_locale, os_info, version_radaria,
            nb_cameras, cameras_actives, last_seen, statut)
           VALUES (%s,%s,%s,%s,%s,6,6,%s,'online')""",
        (cid, "RADARIA-DEMO-PC", "192.168.1.50", "Windows 11", "4.7.0",
         now.strftime("%Y-%m-%dT%H:%M:%S")))

    # 4) Alertes d'exemple
    for k, (typ, cam, mago, nb) in enumerate(ALERTES):
        t = now - timedelta(minutes=mago)
        cur.execute(
            """INSERT INTO alertes_centrales
               (client_id, alert_id, type, camera, date, heure,
                image_path, feedback, suspect_id, nb_personnes)
               VALUES (%s,%s,%s,%s,%s,%s,'','','',%s)""",
            (cid, f"demo_{k}_{t.strftime('%H%M%S')}", typ, cam,
             t.strftime("%Y-%m-%d"), t.strftime("%H:%M:%S"), nb))

    # 5) Historique de sinistres (1 ouvert + 1 resolu)
    cur.execute(
        """INSERT INTO sinistres (client_id, type, origine, description, statut)
           VALUES (%s,'Vol','client',%s,'ouvert')""",
        (cid, "Vol a l'etalage au rayon alcools — declare depuis l'application."))
    cur.execute(
        """INSERT INTO sinistres (client_id, type, origine, description, statut, date_resolution)
           VALUES (%s,'Intrusion','client',%s,'resolu',NOW())""",
        (cid, "Intrusion detectee apres la fermeture — dossier resolu."))

    conn.commit()

    # 6) Images cameras (lues par /api/mobile/snapshots)
    d = Path(snap_dir) / str(cid)
    d.mkdir(parents=True, exist_ok=True)
    ts = now.strftime("%Y%m%d_%H%M%S")
    written = []
    for cam in CAMS:
        fname = f"{ts}_{cam.replace(' ', '_')}.jpg"
        (d / fname).write_bytes(base64.b64decode(imgs[cam]))
        written.append(fname)

    cur.close(); conn.close()
    return {"client_id": cid, "username": DEMO_USERNAME, "password": DEMO_PASSWORD,
            "license_key": lic, "nb_alertes": len(ALERTES), "snapshots": written}
