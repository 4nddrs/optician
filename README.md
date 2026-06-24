# Optical Store Management System

![Optical Store Management](images/image1.png)


A modern web-based management system for optical stores, featuring client management, work order tracking, and branch administration. Built with Flask and Firebase Firestore, the application offers a sleek dark-mode interface with violet tones.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Database Structure](#database-structure)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [Features](#features)
- [API Endpoints](#api-endpoints)
- [Deployment](#deployment)
- [Technologies](#technologies)

## Overview

This system provides comprehensive management capabilities for optical stores, including:

- **Client Management**: Register and track clients with order history
- **Work Order Management**: Create, track, and manage prescription orders with detailed specifications
- **Branch Management**: Multi-branch support with correlative order numbering
- **Real-time Database**: Firebase Firestore integration for instant data synchronization
- **Modern UI**: Responsive dark-mode design with smooth animations and violet color scheme

## Architecture

### Application Structure

```
app/
├── app.py                 # Main Flask application with routes
├── firebase_config.py     # Firebase initialization and database operations
├── requirements.txt       # Python dependencies
├── Dockerfile            # Docker configuration
├── .env.example          # Environment variables template
├── templates/            # Jinja2 HTML templates
│   ├── base.html         # Base layout template
│   ├── index.html        # Dashboard
│   ├── clientes.html     # Client list view
│   ├── nuevo_cliente.html # Client creation form
│   ├── ver_cliente.html  # Client detail view
│   ├── ordenes.html      # Orders list view
│   ├── nueva_orden.html  # Order creation form
│   ├── ver_orden.html    # Order detail view
│   ├── sucursales.html   # Branches list view
│   └── error.html        # Error page
└── static/               # Static assets
    ├── css/             # Stylesheets
    └── js/              # JavaScript files
```

### Technology Stack

**Backend:**
- Flask 3.0.0 - Web framework
- Firebase Admin SDK 6.4.0 - Database integration
- Gunicorn 21.2.0 - WSGI HTTP server
- Python Dotenv 1.0.0 - Environment variable management

**Frontend:**
- HTML5 with Jinja2 templating
- CSS3 with custom dark theme
- Vanilla JavaScript
- Font Awesome 6.4.0 - Icons

**Database:**
- Firebase Firestore - NoSQL cloud database

### Design Patterns

- **MVC Pattern**: Separation of concerns with Flask routes (Controllers), Jinja2 templates (Views), and Firebase operations (Model)
- **Repository Pattern**: `firebase_config.py` acts as a data access layer
- **Caching Strategy**: In-memory caching for frequently accessed data (clients, branches) with configurable TTL

## Database Structure

### Firestore Collections

#### Collection: `clientes` (Clients)

Stores customer information and order history.

```json
{
  "ci": "45781102",
  "nombre_completo": "Juan Baldez",
  "telefono": "78952216",
  "historial_ordenes": [1, 2, 5]
}
```

**Fields:**
- `ci` (string): National ID number
- `nombre_completo` (string): Full name
- `telefono` (string): Phone number
- `historial_ordenes` (array): List of order correlative numbers

**Indexes Required:**
- `ci` (ascending) - for client lookup by ID

---

#### Collection: `sucursales` (Branches)

Stores branch/location information.

```json
{
  "nombre": "Downtown Branch",
  "direccion": "123 Main Street",
  "telefono": "555-0100",
  "ciudad": "Santa Cruz"
}
```

**Fields:**
- `nombre` (string): Branch name
- `direccion` (string): Physical address
- `telefono` (string): Contact phone
- `ciudad` (string): City location

**Document ID:** Auto-generated (e.g., `S1`, `S2`)

---

#### Collection: `ordenes_trabajo` (Work Orders)

Stores prescription orders with complete specifications.

```json
{
  "id_orden": "S1_3268",
  "nro_correlativo": 3268,
  "id_sucursal": "S1",
  "id_cliente": "CLI_98765",
  "fecha_creacion": "2026-02-03T11:24:00Z",
  "fecha_entrega": "2026-02-10",
  "estado": "pendiente",
  "especificaciones": {
    "material_base": "organico",
    "material_detalle": "antireflex",
    "material_otro": "",
    "tipo_lente": "multifocal",
    "diseno_bifocal": "",
    "marca_multifocal": "varilux",
    "modelo_multifocal": "physio_30",
    "tratamientos": ["antireflex", "blue_blocker"]
  },
  "graduacion": {
    "lejos": {
      "od": {
        "esf": -1.5,
        "cil": -0.5,
        "eje": 180
      },
      "oi": {
        "esf": -1.25,
        "cil": null,
        "eje": null
      },
      "di": 62
    },
    "cerca": {
      "adicion": 2.0
    }
  },
  "montura": {
    "modelo": "Ray-Ban Aviator",
    "observaciones": "Adjust nose pads"
  },
  "pagos": {
    "total": 1200.00,
    "adelanto": 500.00,
    "saldo": 700.00,
    "metodo_pago": "QR"
  }
}
```

**Fields:**
- `id_orden` (string): Unique order ID (format: `{branch_id}_{correlative}`)
- `nro_correlativo` (number): Sequential number per branch
- `id_sucursal` (string): Reference to branch document ID
- `id_cliente` (string): Reference to client document ID
- `fecha_creacion` (string): Creation timestamp (ISO 8601)
- `fecha_entrega` (string): Expected delivery date
- `estado` (string): Order status (`pendiente`, `en_proceso`, `listo`, `entregado`)
- `especificaciones` (object): Lens specifications
  - `material_base` (string): Base material (`organico`, `policarbonato`, `vidrio`, `otro`)
  - `material_detalle` (string): Material variant (e.g. `blanco`, `antireflex`, `blue_blocker`, `blue_care`, `blue_verde`, `fotocr_ar`, `fotocr_blue`, `transitions`, `fotocromatico`)
  - `material_otro` (string): Custom material text (when `material_base` is `otro`)
  - `tipo_lente` (string): Lens type (`bifocal`, `multifocal`)
  - `diseno_bifocal` (string): Bifocal design (`flap_top`, `invisible`)
  - `marca_multifocal` (string): Multifocal brand (`kodak`, `varilux`, `evolution_xperience`)
  - `modelo_multifocal` (string): Multifocal model (`unique_hd`, `easy`, `precise`, `physio_30`, `physio`, `confort`, `dynamic`, `evolution_essential`, `evolution_pro`, `evolution_pro_2_0`, `xperience_ia`)
  - `tratamientos` (array): Applied treatments
- `graduacion` (object): Prescription details
  - `lejos.od` (object): Right eye distance (OD = Oculus Dexter)
    - `esf` (number): Sphere power
    - `cil` (number, nullable): Cylinder power
    - `eje` (number, nullable): Axis (0-180)
  - `lejos.oi` (object): Left eye distance (OI = Oculus Sinister)
  - `lejos.di` (number): Pupillary distance
  - `cerca.adicion` (number, nullable): Reading addition
- `montura` (object): Frame information
  - `modelo` (string): Frame model
  - `observaciones` (string): Additional notes
- `pagos` (object): Payment details
  - `total` (number): Total amount
  - `adelanto` (number): Advance payment
  - `saldo` (number): Balance due
  - `metodo_pago` (string): Payment method

**Document ID:** Same as `id_orden` field

**Indexes Required:**
- `id_sucursal` (ascending), `fecha_creacion` (descending) - for branch filtering
- `estado` (ascending) - for status filtering
- `fecha_creacion` (descending) - for recent orders

## Prerequisites

- **Python**: 3.8 or higher
- **Firebase Account**: With Firestore database enabled
- **Firebase Service Account**: JSON credentials file

## Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd app
```

### 2. Create Virtual Environment

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**Linux/macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

**Dependencies installed:**
- Flask 3.0.0
- firebase-admin 6.4.0
- python-dotenv 1.0.0
- gunicorn 21.2.0

## Configuration

### Firebase Setup

#### Option 1: Service Account File (Development)

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Select your project
3. Go to **Project Settings** → **Service Accounts**
4. Click **Generate New Private Key**
5. Save the JSON file as `key.json` in the project root
6. Ensure `key.json` is in `.gitignore` (already configured)

#### Option 2: Environment Variables (Production)

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your Firebase credentials:
   ```env
   FLASK_SECRET_KEY=your-secret-key-here
   FLASK_ENV=production
   
   # Firebase Configuration
   FIREBASE_USE_DEFAULT_CREDENTIALS=false
   FIREBASE_TYPE=service_account
   FIREBASE_PROJECT_ID=your-project-id
   FIREBASE_PRIVATE_KEY_ID=your-private-key-id
   FIREBASE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
   FIREBASE_CLIENT_EMAIL=your-service-account@project.iam.gserviceaccount.com
   FIREBASE_CLIENT_ID=your-client-id
   FIREBASE_AUTH_URI=https://accounts.google.com/o/oauth2/auth
   FIREBASE_TOKEN_URI=https://oauth2.googleapis.com/token
   FIREBASE_AUTH_PROVIDER_CERT_URL=https://www.googleapis.com/oauth2/v1/certs
   FIREBASE_CLIENT_CERT_URL=https://www.googleapis.com/robot/v1/metadata/x509/...
   
   # Application Settings
   CACHE_DURATION=60
   MAX_ORDERS_LIMIT=100
   ```

**Configuration Options:**
- `FLASK_SECRET_KEY`: Session encryption key (change in production)
- `CACHE_DURATION`: Cache TTL in seconds for clients/branches (default: 60)
- `MAX_ORDERS_LIMIT`: Maximum orders fetched from database (default: 100)

### Firestore Database Setup

1. Create the following collections in Firestore:
   - `clientes`
   - `sucursales`
   - `ordenes_trabajo`

2. Add at least one branch document to `sucursales`:
   ```json
   {
     "nombre": "Main Branch",
     "direccion": "123 Main St",
     "telefono": "555-0100",
     "ciudad": "Your City"
   }
   ```

## Running the Application

### Development Mode

```bash
python app.py
```

The application will start on `http://localhost:5000`

### Production Mode with Gunicorn

```bash
gunicorn -b 0.0.0.0:8080 app:app
```

### Docker Deployment

1. Build the image:
   ```bash
   docker build -t optica-app .
   ```

2. Run the container:
   ```bash
   docker run -p 8080:8080 --env-file .env optica-app
   ```

## Features

### Dashboard (`/`)
- Overview statistics (total orders, pending, delivered)
- Recent orders list (last 10)
- Quick action buttons
- Status breakdown

### Client Management

**List Clients** (`/clientes`)
- View all registered clients
- Search and filter capabilities

**Create Client** (`/clientes/nuevo`)
- Register new clients
- Fields: CI, full name, phone
- Automatic validation

**View Client** (`/clientes/<id>`)
- Client details
- Order history
- Contact information

**Search Client API** (`/api/clientes/buscar?ci=<ci>`)
- Search by national ID
- Returns client data or 404

### Order Management

**List Orders** (`/ordenes`)
- View all work orders
- Filter by status and branch
- Sort by date

**Create Order** (`/ordenes/nueva`)
- Client search by CI
- Prescription entry (distance and near)
- Lens specifications
- Frame details
- Payment information
- Automatic order number generation

**View Order** (`/ordenes/<id>`)
- Complete order details
- Client and branch information
- Prescription display
- Payment status

**Update Order Status** (`/api/ordenes/<id>/estado`)
- Change order status
- Available states: `pendiente`, `en_proceso`, `listo`, `entregado`

**Delete Order** (`/api/ordenes/<id>`)
- Remove order from system
- Confirmation required

### Branch Management

**List Branches** (`/sucursales`)
- View all branches
- Contact information
- Location details

## API Endpoints

### Client Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/clientes` | List all clients |
| GET | `/clientes/nuevo` | Client creation form |
| POST | `/clientes/nuevo` | Create new client |
| GET | `/clientes/<id>` | View client details |
| GET | `/api/clientes/buscar?ci=<ci>` | Search client by CI |

### Order Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/ordenes` | List all orders |
| GET | `/ordenes/nueva` | Order creation form |
| POST | `/ordenes/nueva` | Create new order |
| GET | `/ordenes/<id>` | View order details |
| PUT | `/api/ordenes/<id>/estado` | Update order status |
| DELETE | `/api/ordenes/<id>` | Delete order |

### Branch Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/sucursales` | List all branches |

## Deployment

### Fly.io

The application includes a `fly.toml` configuration file for deployment to Fly.io.

1. Install Fly CLI:
   ```bash
   curl -L https://fly.io/install.sh | sh
   ```

2. Login to Fly:
   ```bash
   fly auth login
   ```

3. Deploy:
   ```bash
   fly deploy
   ```

4. Set environment variables:
   ```bash
   fly secrets set FIREBASE_PROJECT_ID=your-project-id
   fly secrets set FIREBASE_PRIVATE_KEY="your-private-key"
   # ... set all other secrets
   ```

### Other Platforms

The Dockerfile makes this application compatible with any platform supporting Docker containers:
- Google Cloud Run
- AWS Elastic Beanstalk
- Azure Container Instances
- Heroku
- Railway

## Technologies

**Backend Framework:**
- Flask 3.0.0 - Lightweight WSGI web application framework

**Database:**
- Firebase Firestore - NoSQL document database with real-time synchronization

**Frontend:**
- HTML5 - Semantic markup
- CSS3 - Custom dark theme with violet color scheme
- JavaScript - Client-side interactions
- Font Awesome 6.4.0 - Icon library

**Deployment:**
- Docker - Containerization
- Gunicorn - WSGI HTTP Server
- Python 3.12 - Runtime environment

**Development Tools:**
- python-dotenv - Environment variable management
- Git - Version control

## Security Considerations

- **Credentials**: Never commit `key.json` or `.env` files to version control
- **Secret Key**: Change `FLASK_SECRET_KEY` in production
- **HTTPS**: Always use HTTPS in production
- **Firebase Rules**: Configure Firestore security rules appropriately
- **Input Validation**: All user inputs are validated server-side

## Troubleshooting

**Firebase Connection Issues:**
- Verify `key.json` exists and has correct permissions
- Check Firebase project ID matches
- Ensure Firestore is enabled in Firebase Console

**Port Already in Use:**
```bash
# Change port in app.py or use environment variable
export PORT=5001
python app.py
```

**Cache Issues:**
- Adjust `CACHE_DURATION` in `.env`
- Clear cache by restarting the application

## License

This project is proprietary and confidential. Unauthorized copying, distribution, or use is strictly prohibited.

---

**Built with Flask and Firebase** | Dark Theme by Design
