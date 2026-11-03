# monitor_and_apply.py
import json
import os
import requests
import time
from apply_basicfit import main as apply_to_job   # ton script Playwright adapté

# ============================================================
# CONFIGURATION WORKDAY (extraite de ton URL filtrée)
# ============================================================
TENANT = "basicfit"
CLUSTER = "wd103"
SITE = "BasicFit_Career_Site_france"
BASE_API = f"https://{TENANT}.{CLUSTER}.myworkdayjobs.com/wday/cxs/{TENANT}/{SITE}"

APPLIED_FACETS = {
    "timeType": ["630780aa199d014f505de6c27e025f00"],
    "locationHierarchy2": [
        "d9198d87ae6d018d34be580294011a1b",
        "d9198d87ae6d0115404fac039401e027",
    ],
}

STATE_FILE = "applied_jobs.json"

# ============================================================
# GESTION DE L'ÉTAT
# ============================================================
def load_state():
    if not os.path.exists(STATE_FILE):
        return {}
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

# ============================================================
# DÉTECTION DES OFFRES (API Workday)
# ============================================================
def fetch_all_jobs():
    jobs = []
    offset = 0
    limit = 20
    while True:
        body = {
            "appliedFacets": APPLIED_FACETS,
            "limit": limit,
            "offset": offset,
            "searchText": "",
        }
        r = requests.post(f"{BASE_API}/jobs", json=body, timeout=30)
        r.raise_for_status()
        data = r.json()
        page = data.get("jobPostings", [])
        if not page:
            break
        for p in page:
            ext = p.get("externalPath", "")
            if not ext:
                continue
            jobs.append({
                "title": p.get("title", ""),
                "external_path": ext,
                "job_url": f"https://{TENANT}.{CLUSTER}.myworkdayjobs.com/{SITE}{ext}",
            })
        offset += limit
        if offset >= data.get("total", 0):
            break
        time.sleep(0.3)
    # Dédoublonnage
    return list({j["external_path"]: j for j in jobs}.values())

# ============================================================
# LOGIQUE PRINCIPALE
# ============================================================
def main():
    state = load_state()
    jobs = fetch_all_jobs()
    print(f"📋 {len(jobs)} offre(s) trouvée(s) via l'API.")

    # On ne garde que les offres jamais postulées
    new_jobs = [j for j in jobs if j["external_path"] not in state]
    print(f"🆕 {len(new_jobs)} nouvelle(s) offre(s) à traiter.")

    if not new_jobs:
        print("✅ Aucune nouvelle offre. Fin.")
        return

    for job in new_jobs:
        print(f"\n🚀 Candidature : {job['title']}")
        try:
            success = apply_to_job(job["job_url"])
            if success:
                state[job["external_path"]] = {
                    "title": job["title"],
                    "applied_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                }
                save_state(state)   # sauvegarde immédiate après chaque succès
                print(f"  💾 État mis à jour pour {job['external_path']}")
            else:
                print(f"  ⚠️ Échec de la candidature, on réessaiera au prochain run.")
        except Exception as e:
            print(f"  ❌ Erreur sur {job['title']} : {e}")
        time.sleep(8)   # pause de politesse entre deux candidatures

    print("\n🏁 Terminé.")

if __name__ == "__main__":
    main()