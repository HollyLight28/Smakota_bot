# Active Context

## Current Focus
- WebApp deployed to GitHub Pages: https://hollylight28.github.io/smakota-telegram-app/
- WebApp repo: https://github.com/HollyLight28/smakota-telegram-app.git (public)
- Bot repo: https://github.com/HollyLight28/Smakota_bot.git (private)
- Updated keyboards.py with real GitHub Pages URL.
- Created deploy_webapp.py for automated deployment.

## Recent Actions
- Redesigned webapp with premium UI (Outfit font, gradients, animations).
- Fixed image cropping: now uses object-fit: contain with 4:3 aspect ratio.
- Made responsive grid: 2 cols mobile, 3 cols tablet, 4 cols desktop.
- Created deploy_webapp.py script.
- User needs to re-upload updated index.html to GitHub (old version currently live).

## Next Steps
- User to re-upload index.html + data.js to smakota-telegram-app repo.
- Set up cron for hourly menu sync (Mon-Fri 9-17, Sat 9-16, Sun off).
- Set up bot working hours (Mon-Fri 9-17, Sat 9-16, Sun off).
- Refactor bot.py into modular structure.
- Write tests for database and cart logic.
