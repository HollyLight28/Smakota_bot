import os
import subprocess
import logging

# Конфігурація
WEBAPP_PATH = os.path.abspath("webapp")
REPO_URL = "https://github.com/HollyLight28/smakota-telegram-app.git"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def deploy_webapp():
    """
    Автоматично пушить вміст папки webapp у публічний репозиторій.
    """
    try:
        logging.info("🚀 Починаємо деплой веб-апки на GitHub Pages...")
        
        # Перевіряємо чи є папка .git у webapp, якщо ні - ініціалізуємо
        if not os.path.exists(os.path.join(WEBAPP_PATH, ".git")):
            logging.info("Ініціалізація Git у папці webapp...")
            subprocess.run(["git", "init"], cwd=WEBAPP_PATH, check=True)
            subprocess.run(["git", "remote", "add", "origin", REPO_URL], cwd=WEBAPP_PATH, check=True)
            subprocess.run(["git", "branch", "-M", "main"], cwd=WEBAPP_PATH, check=True)

        # Додаємо зміни та відправляємо
        # УВАГА: Якщо GitHub спитає пароль в терміналі, можливо знадобиться SSH ключ або Personal Access Token
        subprocess.run(["git", "add", "."], cwd=WEBAPP_PATH, check=True)
        subprocess.run(["git", "commit", "-m", "Auto-update menu data"], cwd=WEBAPP_PATH, check=True)
        
        # Використовуємо push -f для впевненості (force push)
        # Примітка: Це спрацює якщо у вас налаштований Git (credential helper чи SSH)
        result = subprocess.run(["git", "push", "-u", "origin", "main", "-f"], cwd=WEBAPP_PATH)
        
        if result.returncode == 0:
            logging.info("✅ Веб-апку успішно оновлено на GitHub Pages!")
        else:
            logging.warn("⚠️ Не вдалося автоматично пушнути. Можливо, потрібна авторизація Git.")
            logging.info("Ви можете зробити це вручну: cd webapp && git push")

    except Exception as e:
        logging.error(f"❌ Помилка під час деплою: {e}")

if __name__ == "__main__":
    deploy_webapp()
