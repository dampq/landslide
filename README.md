# Ashtaraksha
Smart India Hackathon demo for an AI-based early-warning and landslide risk monitoring system for North East India.

## Run
```bash
npm install
npm run dev:all
```
Run the command from the project root. It starts the frontend at `http://127.0.0.1:5173` and the backend at `http://127.0.0.1:8000`. Stop both with `Ctrl+C`.

Before the first run, extract `ashtaraksha-backend.zip` into `backend`, then set up the backend once:

```powershell
cd backend\RayaproluSamiksha-ashtaraksha-backend-f48cca4
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
cd ..\..
```

Visit `/login` for the demo-login experience. Any credentials are accepted in the UI.

## Included
React + Vite + TypeScript, Tailwind CSS, shadcn-style reusable UI primitives, React Router, Lucide icons, Recharts, React Leaflet/OpenStreetMap, realistic NER mock data, LocalStorage reports, offline-sync simulation, alert workflows, deploy-team interactions, responsive mobile bottom navigation, and the Mawsynram SIH simulation.

## Integration seams
Replace `src/data/mock.ts` with API adapters later for IMD/weather, satellite imagery, sensor telemetry, terrain/history, ML inference, GIS services, citizen reports, SMS/public warning, authentication and emergency response systems. No API keys or backend are required for this demo.
