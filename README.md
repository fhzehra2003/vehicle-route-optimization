# 🚗 Fuel Optimizer API

A Django REST API that calculates **optimal fuel stops** along a driving route to minimize total fuel costs. Uses greedy optimization with lookahead strategy.

---

## 📋 Table of Contents

1. [Features](#-features)
2. [Tech Stack](#-tech-stack)
3. [Project Structure](#-project-structure)
4. [Prerequisites](#-prerequisites)
5. [Setup Instructions](#-setup-instructions)
6. [Running the Server](#-running-the-server)
7. [API Usage](#-api-usage)
8. [How It Works](#-how-it-works)
9. [Configuration](#-configuration)
10. [Sample Output](#-sample-output)

---

## ✨ Features

- **Route Optimization** - Fetches routes using OpenRouteService API
- **Geocoding** - Converts location names to coordinates using Nominatim
- **Fuel Station Data** - Uses OPIS fuel price dataset
- **Greedy + Lookahead** - Optimizes fuel stops with intelligent lookahead
- **Single-Pass Simulation** - Efficient algorithm runs in one pass
- **Realistic Modeling** - Tracks actual fuel consumption along route
- **Alternative Stations** - Suggests nearby alternatives at each stop

---

## 🛠 Tech Stack

| Component | Technology                |
| --------- | ------------------------- |
| Framework | Django 6.0                |
| API       | Django REST Framework     |
| Routing   | OpenRouteService API      |
| Geocoding | Nominatim (OpenStreetMap) |
| Database  | SQLite (default)          |
| Data      | OPIS Fuel Price Dataset   |

---

## 📁 Project Structure

```
fuel_optimizer/
├── fuel_optimizer/              # Django project
│   ├── api/                     # Main API app
│   │   ├── models.py            # FuelStation model
│   │   ├── serializers.py       # Request serializers
│   │   ├── views.py             # API views
│   │   ├── urls.py              # URL routing
│   │   └── services/
│   │       ├── optimizer.py     # Fuel optimization engine
│   │       ├── route_service.py # Route & geocoding
│   │       └── fuel_service.py  # Fuel data utilities
│   ├── fuel_optimizer/
│   │   ├── settings.py          # Django settings
│   │   └── urls.py              # Root URLs
│   └── manage.py                # Django management
├── data/
│   ├── fuel_prices.csv          # Fuel station data
│   └── uscities.csv             # US cities for reference
├── env/                         # Virtual environment
├── requirements.txt             # Python dependencies
└── README.md                    # This file
```

---

## 🔧 Prerequisites

- Python 3.8+
- OpenRouteService API key (free)
- Internet connection (for routing & geocoding)

---

## 🚀 Setup Instructions

### 1. Clone & Navigate

```bash
cd fuel_optimizer
```

### 2. Create Virtual Environment

```bash
# Windows
python -m venv env
env\Scripts\activate

# Linux/Mac
python -m venv env
source env/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

Or install individually:

```bash
pip install Django djangorestframework requests python-dotenv polyline
```

### 4. Set Up Environment Variables

Create a `.env` file in the project root:

```env
ORS_API_KEY=your_openrouteservice_api_key_here
```

**Get free API key:** https://openrouteservice.com/dev/#/signup

### 5. Run Migrations

```bash
cd fuel_optimizer
python manage.py migrate
```

### 6. Load Fuel Station Data

```bash
python manage.py load_fuel_data
```

> **Note:** If you don't have the management command, manually populate the `FuelStation` model with your CSV data.

### 7. Create Superuser (Optional)

```bash
python manage.py createsuperuser
```

---

## ▶️ Running the Server

```bash
cd fuel_optimizer
python manage.py runserver
```

Server runs at: **http://127.0.0.1:8000**

---

## 📡 API Usage

### Endpoint

```
POST /api/optimize-route/
```

### Request Body

```json
{
  "start": "Los Angeles, CA",
  "end": "Phoenix, AZ"
}
```

### Test with cURL

```bash
curl -X POST http://127.0.0.1:8000/api/optimize-route/ \
  -H "Content-Type: application/json" \
  -d "{\"start\": \"Los Angeles, CA\", \"end\": \"Phoenix, AZ\"}"
```

### Test with Postman

1. Method: `POST`
2. URL: `http://127.0.0.1:8000/api/optimize-route/`
3. Headers: `Content-Type: application/json`
4. Body:
   ```json
   {
     "start": "Los Angeles, CA",
     "end": "Phoenix, AZ"
   }
   ```

### Test in Browser

1. Open: `http://127.0.0.1:8000/api/optimize-route/`
2. You'll see a form with `start` and `end` fields
3. Enter locations and click POST

---

## 🧠 How It Works

### 1. Geocoding

Converts location names to coordinates using Nominatim.

### 2. Route Fetching

Gets route geometry from OpenRouteService API.

### 3. Station Filtering

- Bounding box filter (fast)
- Haversine distance filter (accurate)
- Stations within 15 miles of route

### 4. Single-Pass Optimization

```
current_fuel = 500 miles (full tank)

For each route segment:
  1. current_fuel -= segment_distance

  2. IF current_fuel <= 50 (buffer):
     - Find reachable stations ahead
     - Look ahead 150 miles for cheaper station
     - IF cheaper reachable → WAIT
     - ELSE → REFUEL at cheapest reachable
```

### 5. Output

Returns optimized fuel stops with alternatives.

---

## ⚙️ Configuration

| Parameter         | Default | Description                     |
| ----------------- | ------- | ------------------------------- |
| `MAX_RANGE_MILES` | 500     | Vehicle tank range              |
| `MPG`             | 10.0    | Miles per gallon                |
| `MIN_FUEL_BUFFER` | 50      | Minimum fuel reserve            |
| `LOOKAHEAD_MILES` | 150     | Lookahead distance              |
| `THRESHOLD_MILES` | 15      | Max station distance from route |

Edit in: `fuel_optimizer/api/services/optimizer.py`

---

## 📊 Sample Output

```json
{
  "start": "Los Angeles, CA",
  "end": "Phoenix, AZ",
  "route_summary": {
    "total_distance": 372.5,
    "fuel_capacity": 500,
    "mpg": 10,
    "fuel_required_total": 37.25
  },
  "fuel_stops": [
    {
      "station_name": "Costco Gas",
      "city": "Blythe",
      "state": "CA",
      "price": 3.459,
      "distance_from_start": 180.2,
      "fuel_left_before": 45.0,
      "gallons_filled": 45.5,
      "cost": 157.38,
      "location": [33.712, -114.593],
      "reason": "Cheapest reachable station - no better option ahead",
      "alternatives": [
        {
          "name": "Shell",
          "city": "Blythe",
          "state": "CA",
          "price": 3.529,
          "distance_from_stop": 2.5
        }
      ]
    }
  ],
  "total_cost": 157.38,
  "remaining_fuel_at_destination": 125.0,
  "total_stops": 1,
  "message": "Route optimized successfully"
}
```

---

## 🔑 API Keys

### OpenRouteService (Required)

- Sign up: https://openrouteservice.com/dev/#/signup
- Free tier: 2,000 requests/day
- Get API key from dashboard

### Nominatim (Free, No Key)

- Uses OpenStreetMap data
- Rate limited but free

---

## 🐛 Troubleshooting

### "Invalid locations" error

- Check that location is valid (e.g., "Los Angeles, CA")
- Ensure internet connection for geocoding

### "CSRF Failed" error

- Use the Browsable API form in browser
- Or use cURL/Postman with correct headers

### No fuel stations found

- Ensure fuel station data is loaded in database
- Check database has records: `python manage.py shell`
  ```python
  from api.models import FuelStation
  print(FuelStation.objects.count())
  ```

### Routing API errors

- Verify `ORS_API_KEY` in `.env`
- Check API key has sufficient quota

---

## 📝 License

MIT License

---

## 👤 Author

Built by Fatima Zehra with Django REST Framework + algorithmic optimization
