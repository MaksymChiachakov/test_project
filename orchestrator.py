# orchestrator.py
import requests
import time
from tracker import init_db, should_apply, mark_applied
from apply_basicfit import main as apply_to_job

# ============================================================
# PARAMÈTRES WORKDAY (extraits de ton URL)
# ============================================================
TENANT = "basicfit"
CLUSTER = "wd103"
SITE = "BasicFit_Career_Site_france"
BASE_API = f"https://{TENANT}.{CLUSTER}.myworkdayjobs.com/wday/cxs/{TENANT}/{SITE}"

# Filtres appliqués (timeType + locationHierarchy2)
# ⚠️ Vérifie bien que ces hash correspondent à tes filtres actuels.
APPLIED_FACETS = {
    "timeType": ["630780aa199d014f505de6c27e025f00"],
    "locationHierarchy2": [
        "d9198d87ae6d018d34be580294011a1b",
        "d9198d87ae6d0115404fac039401e027",
    ],
}


def fetch_all_jobs():
    """Récupère TOUTES les offres correspondant aux filtres appliqués."""
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
            external_path = p.get("externalPath", "")
            if not external_path:
                continue
            job_url = f"https://{TENANT}.{CLUSTER}.myworkdayjobs.com/{SITE}{external_path}"
            jobs.append({
                "title": p.get("title", ""),
                "external_path": external_path,
                "job_url": job_url,
            })

        offset += limit
        total = data.get("total", 0)
        if offset >= total:
            break

        time.sleep(0.5)

    # Dédoublonnage par external_path
    unique = {j["external_path"]: j for j in jobs}
    return list(unique.values())


def run():
    init_db()
    jobs = fetch_all_jobs()
    print(f"📋 {len(jobs)} offre(s) trouvée(s) via l'API Workday.")

    applied_count = 0
    skipped_count = 0

    for job in jobs:
        path = job["external_path"]
        if not should_apply(path):
            skipped_count += 1
            print(f"  ⏭️  Déjà postulé il y a moins de 48h : {job['title']}")
            continue

        print(f"\n🚀 Candidature : {job['title']}")
        try:
            success = apply_to_job(job["job_url"])
            if success:
                mark_applied(path, job["job_url"], job["title"])
                applied_count += 1
            else:
                print(f"  ⚠️ Échec de la candidature pour {job['title']}")
        except Exception as e:
            print(f"  ❌ Erreur sur {job['title']} : {e}")

        # Pause de politesse entre deux candidatures
        time.sleep(10)

    print(f"\n✅ Terminé. {applied_count} candidature(s) envoyée(s), "
          f"{skipped_count} ignorée(s) (cooldown 48h).")


if __name__ == "__main__":
    run()