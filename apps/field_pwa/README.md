# Field Agent PWA - CollectOS

Progressive Web App for field collection agents (FOS) to manage daily beat plans, visit accounts, and capture collections.

## Overview

The Field PWA is a mobile-first, offline-capable application that enables 1,500+ field agents to:
- View daily beat plans with optimized routes
- Access account details and collection insights
- Capture visit dispositions and payments
- Make Promise-to-Pay commitments
- Track personal performance metrics
- Work offline and sync when connected

## Architecture

**Frontend**: React 18 + React Router + IndexedDB (offline storage)
**UI**: Mobile-optimized, responsive design with Hindi/English support
**Offline**: Service Worker + IndexedDB for queue management
**Sync**: Background sync when network available
**Auth**: JWT tokens from FastAPI backend

## Screens

### 1. Login (`/login`)
- Agent ID + Password
- JWT token storage
- Remember me option
- Language selection (English/Hindi)

### 2. My Day (`/my-day`)
**Purpose**: Daily beat plan overview

**Features**:
- List of accounts to visit (ordered by priority/route)
- Map integration (Google Maps links)
- Expected collection target
- Progress tracking (visited/pending)
- Priority badges (HIGH/MEDIUM/LOW)

**Data**:
```javascript
{
  date: "2026-07-19",
  agent_id: "FOS001",
  total_stops: 12,
  visited: 3,
  pending: 9,
  expected_collection: 245000,
  stops: [
    {
      account_id: "ACC12345",
      customer_name: "Rajesh Kumar",
      address: "Shop 12, Main Market, Dwarka",
      dpd: 15,
      overdue_amt: 28500,
      priority: "HIGH",
      visit_reason: "Broken PTP - Due Rs. 28,500",
      lat: 28.5921,
      lon: 77.0460
    },
    ...
  ]
}
```

### 3. Account Card (`/account/:accountId`)
**Purpose**: Detailed account information

**Sections**:

**A. Account Summary**:
- Customer name, account ID, product type
- Vehicle details (asset description)
- Current DPD, bucket (X/B1/B2/B3)
- Total overdue amount
- EMI amount and cycle day

**B. Payment History** (sparkline chart):
- Last 12 months presentation/payment status
- Bounce reasons
- Payment modes

**C. Risk Insights** (top 3 SHAP reasons):
- "High 12-month bounce rate: 45%"
- "Overdue amount above average"
- "Recent broken PTP"

**D. Contact History**:
- Last 5 interactions (calls, visits, SMS)
- Dispositions and notes

**E. Active PTPs**:
- Promise date, amount, mode
- Status (open/kept/broken)

**F. Recommended Actions**:
- Suggested collection amount
- Recommended approach based on archetype
- Do's and Don'ts

### 4. Action Capture (`/account/:accountId/visit`)
**Purpose**: Record visit outcome

**Form Fields**:

**Visit Disposition** (required):
- ☑️ Customer Met
- ☐ Customer Not Found
- ☐ Address Issue
- ☐ Shop/Business Closed
- ☐ Refused to Meet

**If Met**:

**Collection Captured?**:
- Yes / No
- If Yes:
  - Amount: ₹ _____
  - Mode: Cash / UPI / NACH / Cheque
  - Reference: _____
  - Receipt photo (optional)

**Promise to Pay?**:
- Yes / No
- If Yes:
  - Promise Date: (date picker, max 7 days)
  - Promise Amount: ₹ _____
  - Mode: UPI / Bank Transfer / NACH

**Customer Response**:
- ☐ Cooperative
- ☐ Hardship (financial difficulty)
- ☐ Dispute (claims paid/wrong amount)
- ☐ Evasive
- ☐ Aggressive

**Notes** (optional):
- Free text field (max 500 characters)

**Geo-stamp** (automatic):
- Latitude, Longitude, Timestamp

**Submit Button**:
- Saves to IndexedDB if offline
- Syncs to API when online

### 5. My Scorecard (`/scorecard`)
**Purpose**: Personal performance metrics

**Sections**:

**A. Today's Performance**:
- Visits: 8 / 12 (67%)
- Collections: ₹45,000 / ₹245,000 (18%)
- PTPs: 3
- Strike Rate: 5/8 (62.5%)

**B. Month-to-Date**:
- Visits: 145
- Collections: ₹1,250,000
- PTPs Made: 45
- PTPs Kept: 32 (71%)
- Strike Rate: 68%
- Rank in Team: 3 / 15

**C. Trends** (7-day chart):
- Daily collections
- Visit strike rate

**D. Badges & Streaks**:
- 🏆 Top Performer (last week)
- 🔥 5-day strike (consecutive productive days)
- ⭐ 100% PTP Keep Rate (last month)

### 6. Team Lead View (`/team` - TL/ACM only)
**Purpose**: Monitor team performance

**Sections**:

**A. Team Overview**:
- Agents active today: 12 / 15
- Total visits: 89 / 180 (49%)
- Collections: ₹780,000 / ₹3,200,000
- Live progress map

**B. Agent List**:
- Agent ID, Name
- Today's progress (visits, collections)
- Status (active, offline, syncing)
- Last sync time

**C. Exception List**:
- Agents below target (< 50% visits)
- Zero collections (visited but not collected)
- Offline > 2 hours

**D. Actions**:
- Send message/reminder
- Reassign account
- Call agent

## Offline Functionality

### IndexedDB Schema

**Store: beatPlans**
```javascript
{
  id: "2026-07-19_FOS001",
  agent_id: "FOS001",
  date: "2026-07-19",
  stops: [...],  // Full beat plan
  synced: false,
  created_at: timestamp
}
```

**Store: visits (pending sync)**
```javascript
{
  id: "uuid",
  account_id: "ACC12345",
  agent_id: "FOS001",
  visit_date: "2026-07-19",
  visit_time: "14:30:00",
  disposition: "CUSTOMER_MET",
  collection: {
    amount: 25000,
    mode: "UPI",
    reference: "UTR123456"
  },
  ptp: {
    promise_date: "2026-07-22",
    amount: 10000,
    mode: "NACH"
  },
  notes: "Customer agreed to pay partial amount",
  geo: {
    lat: 28.5921,
    lon: 77.0460,
    accuracy: 10
  },
  synced: false,
  created_at: timestamp
}
```

**Store: accountDetails (cache)**
```javascript
{
  account_id: "ACC12345",
  data: {...},  // Full account card data
  cached_at: timestamp
}
```

### Sync Strategy

**On Network Available**:
1. POST all unsynced visits to `/api/v1/dispositions`
2. Mark synced visits
3. Fetch updated beat plan if needed
4. Update scorecard metrics

**Conflict Resolution**:
- Server wins (most recent timestamp)
- Flag conflicts for review

## Service Worker

**Cache Strategy**:
- App shell: Cache-first
- API calls: Network-first, fallback to cache
- Account details: Stale-while-revalidate (1 hour)

**Background Sync**:
- Register sync event when offline
- Retry failed uploads

## PWA Manifest

```json
{
  "name": "CollectOS Field",
  "short_name": "CollectOS",
  "description": "Field Agent Collections App",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#ffffff",
  "theme_color": "#1976d2",
  "orientation": "portrait",
  "icons": [
    {
      "src": "/icon-192.png",
      "sizes": "192x192",
      "type": "image/png"
    },
    {
      "src": "/icon-512.png",
      "sizes": "512x512",
      "type": "image/png"
    }
  ],
  "categories": ["finance", "productivity"],
  "lang": "en",
  "dir": "ltr",
  "prefer_related_applications": false
}
```

## Installation

**Prerequisites**:
- Node.js 20+ (for build)
- React 18
- Modern browser with Service Worker support

**Setup**:
```bash
cd apps/field_pwa
npm install
npm run dev   # Development server on http://localhost:5173
npm run build # Production build
npm run serve # Serve production build on http://localhost:3001
```

## Usage

### Agent Workflow

**Morning**:
1. Open app (works offline if preloaded)
2. View today's beat plan
3. Review account priorities
4. Start visiting (highest priority first)

**During Day**:
1. Navigate to account location
2. Meet customer
3. Capture visit details immediately
4. Take collection/PTP if applicable
5. Move to next account

**Evening**:
1. Sync all visits (if not already synced)
2. Review personal scorecard
3. Plan for tomorrow

### Team Lead Workflow

**Throughout Day**:
1. Monitor team progress
2. Check exception list
3. Support struggling agents
4. Reassign accounts if needed

## API Integration

**Endpoints Used**:

```javascript
// Fetch beat plan
GET /api/v1/beatplan/{agent_id}/{date}

// Get account details
GET /api/v1/accounts/{account_id}

// Submit visit disposition
POST /api/v1/dispositions
{
  account_id, agent_id, disposition_code,
  visit_date, visit_time, geo_lat, geo_lon, notes
}

// Submit collection
POST /api/v1/payments
{
  account_id, amount, mode, reference,
  collected_by, collected_at
}

// Submit PTP
POST /api/v1/ptp
{
  account_id, promise_date, promised_amount,
  promise_mode, made_by, channel: "FIELD"
}

// Get scorecard
GET /api/v1/scorecards/agent/{agent_id}

// Team view (TL/ACM only)
GET /api/v1/team/{team_id}/progress
```

## Security

**Authentication**:
- JWT tokens stored in localStorage
- Auto-refresh on expiry
- Logout on 401 response

**Authorization**:
- Agent can only access own beat plan
- TL/ACM can access team data
- Role-based route guards

**Data Protection**:
- HTTPS only in production
- Sensitive data encrypted in IndexedDB
- No PII in logs

## Testing on Mobile

**Android**:
1. Build production version
2. Deploy to HTTPS server (required for PWA)
3. Open in Chrome on phone
4. Chrome will prompt "Add to Home Screen"
5. Test offline by enabling Airplane mode

**iOS**:
1. Same as Android
2. Use Safari
3. "Add to Home Screen" from share menu

**Local Testing on Phone**:
```bash
# Get local IP
ifconfig | grep "inet " | grep -v 127.0.0.1

# Serve on LAN
npm run serve

# Access from phone: http://192.168.x.x:3001
```

## Performance

**Targets**:
- First Contentful Paint: < 1.5s
- Time to Interactive: < 3.5s
- Lighthouse Score: > 90

**Optimizations**:
- Code splitting by route
- Lazy load components
- Compress images
- Minimize bundle size
- Service worker caching

## Internationalization

**Supported Languages**:
- English (default)
- Hindi (हिंदी)

**Implementation**:
- Use React Context for language
- Separate translation files (en.json, hi.json)
- Number/date formatting per locale

## Future Enhancements

1. **Voice Notes**: Record audio notes during visit
2. **Photo Capture**: Capture receipts, business photos
3. **Route Optimization**: Real-time route updates
4. **Push Notifications**: High-priority accounts, team messages
5. **Biometric Auth**: Fingerprint/Face ID login
6. **Digital Signatures**: Customer signature on PTP
7. **WhatsApp Integration**: Send payment links to customers
8. **Offline Maps**: Cached map tiles for common areas

## Troubleshooting

**Issue**: "Add to Home Screen" not showing
- **Solution**: Ensure HTTPS is enabled, manifest.json is valid

**Issue**: Offline mode not working
- **Solution**: Check Service Worker registration, clear cache

**Issue**: Sync failing
- **Solution**: Check API endpoint, verify JWT token not expired

**Issue**: Location not captured
- **Solution**: Grant location permissions in browser settings

## Development Guide

**Component Structure**:
```
src/
├── components/
│   ├── BeatPlanCard.jsx
│   ├── AccountCard.jsx
│   ├── VisitForm.jsx
│   ├── CollectionForm.jsx
│   └── Scorecard.jsx
├── pages/
│   ├── Login.jsx
│   ├── MyDay.jsx
│   ├── AccountDetail.jsx
│   ├── CaptureVisit.jsx
│   └── MyScorecard.jsx
├── utils/
│   ├── api.js (API client)
│   ├── db.js (IndexedDB wrapper)
│   ├── sync.js (Background sync)
│   └── geo.js (Geolocation helpers)
├── App.jsx (Router + Auth)
└── index.jsx (Entry point)
```

**State Management**:
- React Context for auth and app state
- Local state for forms
- IndexedDB for persistence

**Styling**:
- CSS Modules or Tailwind CSS
- Mobile-first responsive design
- Touch-friendly controls (min 44px targets)

## License

Part of CollectOS, built as open-source collections operating system.
