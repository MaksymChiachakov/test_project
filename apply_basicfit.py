# apply_basicfit.py
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import time
import os
import requests
from config import PROFILE, CV_PATH, LM_PATH, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID


def send_telegram_photo(photo_path, caption):
    """Envoie une photo via l'API HTTP Telegram (synchrone)."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    try:
        with open(photo_path, "rb") as photo:
            r = requests.post(
                url,
                data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption},
                files={"photo": photo},
                timeout=30,
            )
        if r.status_code != 200:
            print(f"⚠️ Telegram HTTP {r.status_code}: {r.text[:200]}")
        else:
            print("📲 Photo envoyée sur Telegram.")
    except Exception as e:
        print(f"⚠️ Telegram error: {e}")


def fill_select(page, field_id, value, max_retries=3):
    for attempt in range(1, max_retries + 1):
        print(f"  -> Sélection '{value}' pour '{field_id}' (essai {attempt})...")
        button = page.locator(f'#{field_id}')
        
        try:
            button.scroll_into_view_if_needed()
            button.wait_for(state="visible", timeout=10000)
        except PlaywrightTimeoutError:
            print(f"  ⚠️ Champ '{field_id}' introuvable.")
            continue

        try:
            button.click()
            page.wait_for_selector('li[role="option"]', state="visible", timeout=5000)
            
            option = page.locator('li[role="option"]').filter(has_text=value).first
            option.wait_for(state="visible", timeout=5000)
            option.click()
            time.sleep(1) # Laisser le temps à React de mouliner

            current_text = button.inner_text().strip()
            
            # VÉRIFICATION CRUCIALE : Lire la valeur de l'input caché de Workday
            hidden_input_val = page.evaluate(f'''() => {{
                const btn = document.getElementById('{field_id}');
                const input = btn.nextElementSibling; // Workday met l'input juste après le bouton
                return input && input.tagName === 'INPUT' ? input.value : '';
            }}''')

            if value.lower() in current_text.lower() and hidden_input_val != "":
                print(f"  ✅ '{value}' sélectionné et validé (ID React: {hidden_input_val[:5]}...).")
                return True
            else:
                print(f"  ⚠️ Valeur affichée mais React n'a pas enregistré (input: '{hidden_input_val}').")
        except Exception as e:
            print(f"  ⚠️ Échec pour '{field_id}': {e}")
            page.keyboard.press("Escape")
            time.sleep(1)
    return False

def fill_input(page, selector, value):
    try:
        locator = page.locator(selector)
        locator.wait_for(state="visible", timeout=5000)
        locator.fill(value)
        locator.press("Tab") # TRÈS IMPORTANT : force React à valider le champ
        time.sleep(0.3)
    except Exception as e:
        print(f"⚠️ Impossible de remplir '{selector}': {e}")

def click_next(page):
    """Clique sur Suivant, vérifie les erreurs et attend la transition."""
    page.click('[data-automation-id="pageFooterNextButton"]')
    time.sleep(3) 

    error_banner = page.locator('text="Errors Found"')
    if error_banner.is_visible():
        print("🚨 ERREUR DE VALIDATION WORKDAY !")
        err_msg = "Erreur inconnue"
        try:
            errors = page.locator('[data-automation-id="errorBanner"] li').all_inner_texts()
            err_msg = "\n".join(errors)
            print(f"   - {err_msg}")
        except:
            pass
        
        # On envoie l'erreur sur Telegram pour la voir directement
        page.screenshot(path="screenshot_error.png")
        send_telegram_photo("screenshot_error.png", f"🚨 Validation Workday échouée :\n{err_msg}")
        
        # On lève l'exception pour arrêter
        raise Exception(f"Validation échouée : {err_msg}")
        
    return True

def main(job_url: str) -> bool:
    """
    Postule à UNE offre.
    Retourne True si la candidature a été soumise avec succès, False sinon.
    """
    with sync_playwright() as p:
        # browser = p.chromium.launch(headless=False, slow_mo=300)
        # Dans apply_basicfit.py, ligne du lancement du navigateur :
        browser = p.chromium.launch(headless=True, slow_mo=400)   # headless pour CI
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()
        success = False

        try:
            print(f"\n🌐 Ouverture de l'offre : {job_url}")
            page.goto(job_url, wait_until="load", timeout=60000)
            page.set_default_timeout(60000)  # 60 secondes par défaut
            page.set_default_navigation_timeout(60000)
            page.wait_for_selector('[data-automation-id="adventureButton"]', timeout=60000)

            print("👆 Clic sur Postuler...")
            page.click('[data-automation-id="adventureButton"]')
            time.sleep(5)

            print("📄 Clic sur 'Renseigner automatiquement à partir du CV'...")
            page.click('[data-automation-id="autofillWithResume"]')
            time.sleep(5)

            # ============ PAGE 1 : RENSEIGNER AUTOMATIQUEMENT ============
            print("📤 Upload du CV...")
            try:
                page.set_input_files('input[type="file"]', CV_PATH)
                time.sleep(10)
            except Exception as e:
                print(f"⚠️ Upload CV: {e}")

            click_next(page)
            print("⏳ Attente du chargement de la page 'Mes données personnelles'...")
            page.wait_for_selector('[data-automation-id="applyFlowMyInfoPage"]', timeout=60000)
            time.sleep(2)

            # ============ PAGE 2 : MES DONNÉES PERSONNELLES ============
            print("📝 Remplissage des données personnelles...")
            fill_select(page, "source--source", PROFILE["how_known"])

          # Dans la PAGE 2, remplace le bloc try/except du worked_before par :
            try:
                # On clique sur le label textuel au lieu de l'input
                page.locator(f'#previousWorker--candidateIsPreviousWorker label:has-text("{PROFILE["worked_before"]}")').click()
                time.sleep(0.5)
            except Exception as e:
                print(f"⚠️ Radio worked_before: {e}")

            fill_select(page, "name--legalName--title", PROFILE["title"])
            fill_select(page, "address--countryRegion", PROFILE["department"])
            fill_select(page, "country--country", PROFILE["country"])


            fill_input(page, '#name--legalName--firstName', PROFILE["first_name"])
            fill_input(page, '#name--legalName--lastName', PROFILE["last_name"])
            fill_input(page, '#address--addressLine1', PROFILE["address_line1"])
            fill_input(page, '#address--addressLine2', PROFILE["address_line2"])
            fill_input(page, '#address--city', PROFILE["city"])
            fill_input(page, '#address--postalCode', PROFILE["postal_code"])
            fill_input(page, '#emailAddress--emailAddress', PROFILE["email"])
            fill_input(page, '#phoneNumber--phoneNumber', PROFILE["phone"])

            click_next(page)
            time.sleep(5)

            # ============ PAGE 3 : MON EXPÉRIENCE (upload LM) ============
            print("📤 Upload de la lettre de motivation...")
            page.wait_for_selector('[data-automation-id="applyFlowMyExpPage"]', timeout=30000)
            try:
                page.set_input_files('input[type="file"]', LM_PATH)
                time.sleep(5)
            except Exception as e:
                print(f"⚠️ Upload LM: {e}")

            click_next(page)
            time.sleep(5)

            # ============ PAGE 4 : QUESTIONS DE CANDIDATURE ============
            print("❓ Remplissage des questions de candidature...")
            page.wait_for_selector('[data-automation-id="applyFlowPrimaryQuestionsPage"]', timeout=30000)
            time.sleep(2)

            fill_select(page, "primaryQuestionnaire--51dfd5d6fbe510064f7bc8c8cdc40000", PROFILE["available_immediately"])
            fill_select(page, "primaryQuestionnaire--51dfd5d6fbe510064f7bc962514e0003", PROFILE["over_18"])
            fill_select(page, "primaryQuestionnaire--51dfd5d6fbe510064f7bc9fbe1340000", PROFILE["eligible_to_work"])
            fill_select(page, "primaryQuestionnaire--51dfd5d6fbe510064f7bc9fbe1340005", PROFILE["commute_distance"])
            fill_select(page, "primaryQuestionnaire--51dfd5d6fbe510064f7bcb2f09a10000", PROFILE["disability"])

            fill_input(page, '#primaryQuestionnaire--51dfd5d6fbe510064f7bcbc8e09c0000', PROFILE["autonomy_answer"])
            fill_input(page, '#primaryQuestionnaire--51dfd5d6fbe510064f7bcbc8e09c0001', PROFILE["why_basicfit_answer"])

            click_next(page)
            time.sleep(5)

            # ============ PAGE 5 : CONDITIONS GÉNÉRALES ============
            print("📜 Acceptation des CGU...")
            page.wait_for_selector('[data-automation-id="applyFlowVoluntaryDisclosuresPage"]', timeout=30000)
            try:
                page.check('#termsAndConditions--acceptTermsAndAgreements')
            except Exception as e:
                print(f"⚠️ Checkbox CGU: {e}")

            click_next(page)
            time.sleep(5)

            # ============ PAGE 6 : RÉVISER ET SOUMETTRE ============
            print("🔍 Page de révision atteinte. Capture d'écran...")
            page.wait_for_selector('[data-automation-id="applyFlowReviewPage"]', timeout=30000)
            page.screenshot(path="screenshot_review.png", full_page=True)
            send_telegram_photo("screenshot_review.png", "📋 Récapitulatif avant soumission.")

            print("⏳ Soumission automatique dans 3 secondes...")
            time.sleep(5)
            page.click('[data-automation-id="pageFooterNextButton"]')
            time.sleep(5)

            # Vérifier qu'on n'est plus sur la page de review (soumission effectuée)
            try:
                page.wait_for_selector('[data-automation-id="applyFlowReviewPage"]', timeout=5000)
                # Si on retrouve la page de review, c'est probablement un échec
                print("⚠️ Toujours sur la page de révision après clic → échec probable.")
                page.screenshot(path="screenshot_final.png")
                send_telegram_photo("screenshot_final.png", "⚠️ Soumission incertaine, vérifie manuellement.")
                success = False
            except PlaywrightTimeoutError:
                # On n'est plus sur la page de review → succès
                print("🎉 Candidature soumise avec succès !")
                page.screenshot(path="screenshot_final.png")
                send_telegram_photo("screenshot_final.png", "🎉 Candidature soumise avec succès !")
                success = True

        except PlaywrightTimeoutError as e:
            print(f"⏱️ Timeout: {e}")
            page.screenshot(path="screenshot_error.png")
            send_telegram_photo("screenshot_error.png", f"⚠️ Timeout : {str(e)[:200]}")
            success = False
        except Exception as e:
            print(f"❌ Erreur : {e}")
            page.screenshot(path="screenshot_error.png")
            send_telegram_photo("screenshot_error.png", f"⚠️ Erreur : {str(e)[:200]}")
            success = False
        finally:
            browser.close()

    return success


if __name__ == "__main__":
    # Test manuel d'une seule offre
    TEST_URL = "https://basicfit.wd103.myworkdayjobs.com/fr-FR/BasicFit_Career_Site_france/job/Argenteuil/Agent-d-accueil--H-F-N-_R57096"
    main(TEST_URL)