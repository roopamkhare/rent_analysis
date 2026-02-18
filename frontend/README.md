# RE ROI Analyzer — Next.js Frontend

Interactive real-estate investment analysis app for McKinney, TX (75071).

## Features

- 🗺️ Interactive map with clickable property markers
- 📊 Full financial analysis (EMI, IRR, cash flow, equity, S&P comparison)
- 🔧 Configurable parameters (loan, costs, growth assumptions)
- 🔍 Filters (price range, home type)
- 📱 Dark theme, responsive layout

## Quick Start

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Deploy to Vercel

1. Push this repo to GitHub
2. Go to [vercel.com](https://vercel.com) → Import repo
3. Set **Root Directory** to `frontend`
4. Deploy — done!

The app is fully static (no server needed). Vercel's free tier works perfectly.

## Tech Stack

- Next.js 15 (App Router, static export)
- TypeScript
- Tailwind CSS v4
- Leaflet + OpenStreetMap (map)
- Plotly.js (charts)
- All analysis runs client-side in the browser
