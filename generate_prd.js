const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  HeadingLevel, AlignmentType, BorderStyle, WidthType, ShadingType,
  PageNumber, LevelFormat, TableOfContents, PageBreak
} = require('docx');
const fs = require('fs');

const BLUE = "1F4E79";
const LIGHT_BLUE = "2E75B6";
const ACCENT = "00B0F0";
const LIGHT_GRAY = "F2F7FB";
const MED_GRAY = "D0E4F5";
const WHITE = "FFFFFF";

const border = { style: BorderStyle.SINGLE, size: 1, color: "BBCFE0" };
const borders = { top: border, bottom: border, left: border, right: border };

function heading1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    children: [new TextRun({ text, bold: true, size: 32, color: BLUE, font: "Arial" })],
    spacing: { before: 360, after: 160 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: ACCENT, space: 4 } }
  });
}

function heading2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    children: [new TextRun({ text, bold: true, size: 26, color: LIGHT_BLUE, font: "Arial" })],
    spacing: { before: 280, after: 120 }
  });
}

function heading3(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_3,
    children: [new TextRun({ text, bold: true, size: 22, color: "444444", font: "Arial" })],
    spacing: { before: 200, after: 80 }
  });
}

function body(text, opts = {}) {
  return new Paragraph({
    children: [new TextRun({ text, size: 22, font: "Arial", ...opts })],
    spacing: { after: 100 },
    alignment: AlignmentType.JUSTIFIED
  });
}

function bullet(text, level = 0) {
  return new Paragraph({
    numbering: { reference: "bullets", level },
    children: [new TextRun({ text, size: 22, font: "Arial" })],
    spacing: { after: 80 }
  });
}

function numbered(text, level = 0) {
  return new Paragraph({
    numbering: { reference: "numbers", level },
    children: [new TextRun({ text, size: 22, font: "Arial" })],
    spacing: { after: 80 }
  });
}

function spacer(lines = 1) {
  return new Paragraph({ children: [new TextRun("")], spacing: { after: lines * 80 } });
}

function pageBreak() {
  return new Paragraph({ children: [new PageBreak()] });
}

function headerRow(cells, colWidths) {
  return new TableRow({
    tableHeader: true,
    children: cells.map((text, i) => new TableCell({
      borders,
      width: { size: colWidths[i], type: WidthType.DXA },
      shading: { fill: BLUE, type: ShadingType.CLEAR },
      margins: { top: 80, bottom: 80, left: 140, right: 140 },
      children: [new Paragraph({
        children: [new TextRun({ text, bold: true, size: 20, color: WHITE, font: "Arial" })]
      })]
    }))
  });
}

function dataRow(cells, colWidths, shade = false) {
  return new TableRow({
    children: cells.map((text, i) => new TableCell({
      borders,
      width: { size: colWidths[i], type: WidthType.DXA },
      shading: { fill: shade ? LIGHT_GRAY : WHITE, type: ShadingType.CLEAR },
      margins: { top: 80, bottom: 80, left: 140, right: 140 },
      children: [new Paragraph({
        children: [new TextRun({ text, size: 20, font: "Arial" })]
      })]
    }))
  });
}

function makeTable(headers, rows, colWidths) {
  const total = colWidths.reduce((a, b) => a + b, 0);
  return new Table({
    width: { size: total, type: WidthType.DXA },
    columnWidths: colWidths,
    rows: [
      headerRow(headers, colWidths),
      ...rows.map((row, i) => dataRow(row, colWidths, i % 2 === 1))
    ]
  });
}

// ─── Cover Page ───────────────────────────────────────────────────────────────
const coverPage = [
  spacer(4),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "FINAL YEAR PROJECT", size: 24, color: "888888", font: "Arial", allCaps: true })],
    spacing: { after: 160 }
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "Product Requirements Document", size: 40, bold: true, color: BLUE, font: "Arial" })],
    spacing: { after: 200 }
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    border: { bottom: { style: BorderStyle.SINGLE, size: 12, color: ACCENT, space: 4 } },
    children: [new TextRun({ text: "", size: 40 })],
    spacing: { after: 240 }
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "IoT-Based Smart Campus Security System", size: 48, bold: true, color: LIGHT_BLUE, font: "Arial" })],
    spacing: { after: 120 }
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "Secure IoT Infrastructure with Real-Time Threat Detection", size: 26, color: "555555", font: "Arial", italics: true })],
    spacing: { after: 480 }
  }),
  spacer(2),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "Version 1.0  •  2026", size: 22, color: "888888", font: "Arial" })],
    spacing: { after: 80 }
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "Computer Science / Information Technology", size: 22, color: "888888", font: "Arial" })],
    spacing: { after: 80 }
  }),
  pageBreak()
];

// ─── Section 1: Overview ──────────────────────────────────────────────────────
const section1 = [
  heading1("1. Project Overview"),
  heading2("1.1 Executive Summary"),
  body("This document defines the product requirements for an IoT-Based Smart Campus Security System, developed as a final year undergraduate project in Computer Science/Information Technology. The system simulates a real-world smart campus environment where distributed IoT devices — including motion sensors, door lock controllers, temperature monitors, and IP cameras — transmit data to a centralised web-based security platform."),
  spacer(),
  body("The platform provides real-time monitoring, JWT-based device and user authentication, secure HTTPS communication, and an AI-assisted risk assessment engine that analyses incoming sensor data to detect, classify, and flag potential security threats."),
  spacer(),

  heading2("1.2 Problem Statement"),
  body("University and institutional campuses face growing challenges in physical and digital security management. Traditional security infrastructure relies on isolated, manually-monitored systems that cannot scale efficiently or respond to threats in real time. Key problems include:"),
  bullet("No centralised visibility across campus facilities and buildings"),
  bullet("Delayed or missed threat detection due to lack of automated analysis"),
  bullet("Insecure or unauthenticated communication between campus devices"),
  bullet("High operational cost of fully manual security monitoring"),
  bullet("Lack of actionable, data-driven security intelligence for administrators"),
  spacer(),

  heading2("1.3 Proposed Solution"),
  body("The Smart Campus Security System (SCSS) is a full-stack web application that addresses these challenges by:"),
  numbered("Providing a central dashboard with real-time visibility of all campus IoT devices"),
  numbered("Simulating IoT devices (motion, door, temperature, cameras) that continuously send sensor data"),
  numbered("Securing all communication using HTTPS, JWT authentication, and API keys"),
  numbered("Running a risk assessment engine that scores and classifies incoming data as Safe, Low Risk, Medium Risk, High Risk, or Critical"),
  numbered("Generating and logging threat alerts for administrator review and action"),
  spacer(),

  heading2("1.4 Project Scope"),
  body("This is a prototype system built for academic demonstration. It does not connect to physical hardware — all IoT devices are simulated in software. The system is fully deployable as a live web application."),
  spacer(),
  makeTable(
    ["Area", "In Scope", "Out of Scope"],
    [
      ["Hardware", "Simulated IoT devices (Python scripts)", "Physical sensors, microcontrollers, Arduino/Raspberry Pi"],
      ["Deployment", "Web hosting on Render, Railway, or VPS", "Mobile native app (iOS/Android)"],
      ["Authentication", "JWT user auth + device API keys", "OAuth, SSO, biometric login"],
      ["Data Storage", "SQLite (local), upgradeable to PostgreSQL", "Cloud data lakes, enterprise DBs"],
      ["AI/ML", "Rule-based risk engine", "Trained ML models, predictive analytics"],
      ["Communication", "REST API + WebSockets", "MQTT, CoAP, LoRaWAN (IoT protocols)"],
    ],
    [2200, 3200, 3960]
  ),
  spacer(),
  pageBreak()
];

// ─── Section 2: Goals & Objectives ───────────────────────────────────────────
const section2 = [
  heading1("2. Goals & Objectives"),
  heading2("2.1 Academic Objectives"),
  bullet("Demonstrate competency in full-stack web development (backend API + frontend dashboard)"),
  bullet("Apply security engineering principles: authentication, authorisation, encrypted communication"),
  bullet("Design and implement a rule-based threat detection algorithm"),
  bullet("Simulate an IoT ecosystem using software-based device clients"),
  bullet("Produce a deployable, demonstrable prototype for examination and viva defence"),
  spacer(),

  heading2("2.2 Technical Objectives"),
  bullet("Build a RESTful API server capable of handling concurrent device data submissions"),
  bullet("Implement JWT-based authentication for human users and API key authentication for devices"),
  bullet("Create a WebSocket-powered real-time data feed for the monitoring dashboard"),
  bullet("Develop a risk engine that evaluates sensor readings against configurable thresholds"),
  bullet("Persist all device data, user accounts, and threat alerts in a relational database"),
  bullet("Provide an admin dashboard with live charts, device status, and alert management"),
  spacer(),

  heading2("2.3 Success Criteria"),
  makeTable(
    ["Objective", "Metric", "Target"],
    [
      ["Authentication Security", "JWT expiry + device API key validation", "100% of unauthenticated requests rejected"],
      ["Real-time Data Feed", "WebSocket update latency", "< 2 seconds from data submission to dashboard"],
      ["Risk Detection Accuracy", "Correct classification of injected test scenarios", "≥ 90% classification accuracy on test cases"],
      ["System Uptime", "Application availability during demo", "≥ 99% during 1-hour live demo"],
      ["Device Simulation", "Number of concurrent simulated devices", "≥ 10 devices simultaneously active"],
      ["Threat Alerts", "Alerts generated for flagged scenarios", "100% of critical events produce alerts"],
    ],
    [2800, 3200, 3360]
  ),
  spacer(),
  pageBreak()
];

// ─── Section 3: System Architecture ──────────────────────────────────────────
const section3 = [
  heading1("3. System Architecture"),
  heading2("3.1 Architecture Overview"),
  body("The SCSS follows a three-tier architecture: a simulation layer (IoT device clients), a backend application server, and a browser-based frontend dashboard. All layers communicate over HTTP/HTTPS, with real-time updates handled via WebSocket connections."),
  spacer(),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "[ IoT Device Simulators ] ──HTTPS──> [ FastAPI Backend ] <──WebSocket──> [ React Dashboard ]", size: 20, font: "Courier New", color: "333333" })],
    spacing: { before: 160, after: 160 }
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "                                              |", size: 20, font: "Courier New", color: "333333" })],
    spacing: { after: 0 }
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "                                    [ SQLite Database ]", size: 20, font: "Courier New", color: "333333" })],
    spacing: { after: 160 }
  }),
  spacer(),

  heading2("3.2 Component Breakdown"),
  makeTable(
    ["Component", "Technology", "Responsibility"],
    [
      ["API Server", "Python FastAPI", "Handles all HTTP requests, WebSocket connections, business logic"],
      ["Database", "SQLite + SQLAlchemy ORM", "Persists users, devices, sensor data, threat alerts"],
      ["Authentication Module", "JWT (python-jose) + bcrypt", "Issues and validates user tokens and device API keys"],
      ["Risk Assessment Engine", "Python (custom rule engine)", "Analyses sensor readings and classifies threats"],
      ["Device Simulator", "Python asyncio scripts", "Simulates 10+ IoT devices sending data at intervals"],
      ["Frontend Dashboard", "HTML5 + CSS3 + Vanilla JS", "Real-time monitoring UI, charts, alerts, device management"],
      ["WebSocket Server", "FastAPI WebSockets", "Pushes live sensor data and alerts to connected browsers"],
    ],
    [2200, 2600, 4560]
  ),
  spacer(),

  heading2("3.3 Data Flow"),
  numbered("An IoT device simulator authenticates with the server using its registered API key"),
  numbered("The device sends a POST request to /api/data with its sensor reading (e.g. temperature: 78°C)"),
  numbered("The server validates the API key, stores the reading in the database"),
  numbered("The Risk Assessment Engine analyses the reading against configured thresholds and rules"),
  numbered("If a threat is detected, a ThreatAlert record is created with severity and description"),
  numbered("The server broadcasts the new reading and any alert to all connected WebSocket clients"),
  numbered("The dashboard updates in real time — device cards, live charts, and the alert feed refresh"),
  spacer(),
  pageBreak()
];

// ─── Section 4: Functional Requirements ──────────────────────────────────────
const section4 = [
  heading1("4. Functional Requirements"),

  heading2("4.1 User Authentication Module"),
  makeTable(
    ["Req ID", "Requirement", "Priority"],
    [
      ["FR-AU-01", "The system shall allow administrators to register with username, email, and password", "High"],
      ["FR-AU-02", "Passwords shall be hashed using bcrypt before storage — plaintext passwords must never be stored", "High"],
      ["FR-AU-03", "Registered users shall be able to log in and receive a signed JWT access token", "High"],
      ["FR-AU-04", "JWT tokens shall expire after 24 hours; expired tokens shall be rejected", "High"],
      ["FR-AU-05", "All protected API endpoints shall require a valid Bearer token in the Authorization header", "High"],
      ["FR-AU-06", "The system shall return HTTP 401 for all requests with missing or invalid tokens", "Medium"],
    ],
    [1440, 6120, 1800]
  ),
  spacer(),

  heading2("4.2 Device Management Module"),
  makeTable(
    ["Req ID", "Requirement", "Priority"],
    [
      ["FR-DM-01", "Administrators shall be able to register new IoT devices with a name, location, and device type", "High"],
      ["FR-DM-02", "Each registered device shall be assigned a unique API key upon registration", "High"],
      ["FR-DM-03", "Devices shall authenticate all data submissions using their API key in the request header", "High"],
      ["FR-DM-04", "The system shall track the last_seen timestamp of every device", "Medium"],
      ["FR-DM-05", "A device shall be marked Offline if no data is received within 5 minutes", "Medium"],
      ["FR-DM-06", "Administrators shall be able to deactivate or remove devices from the system", "Low"],
    ],
    [1440, 6120, 1800]
  ),
  spacer(),

  heading2("4.3 Sensor Data Ingestion Module"),
  makeTable(
    ["Req ID", "Requirement", "Priority"],
    [
      ["FR-SD-01", "The system shall accept sensor data via POST /api/data from authenticated devices", "High"],
      ["FR-SD-02", "Accepted data types: temperature (°C), motion (boolean), door_state (0/1), access_attempt (0/1)", "High"],
      ["FR-SD-03", "All sensor readings shall be timestamped and persisted to the database", "High"],
      ["FR-SD-04", "The system shall support ingesting data from at least 10 concurrent simulated devices", "Medium"],
      ["FR-SD-05", "Data submissions from unregistered devices shall be rejected with HTTP 403", "High"],
    ],
    [1440, 6120, 1800]
  ),
  spacer(),

  heading2("4.4 Risk Assessment Module"),
  makeTable(
    ["Req ID", "Requirement", "Priority"],
    [
      ["FR-RA-01", "Every sensor reading shall be evaluated by the risk engine immediately upon receipt", "High"],
      ["FR-RA-02", "The engine shall classify each reading as: Safe, Low, Medium, High, or Critical", "High"],
      ["FR-RA-03", "Temperature readings above 50°C shall trigger a High alert; above 80°C shall trigger Critical", "High"],
      ["FR-RA-04", "Motion detected in a restricted zone between 10 PM and 6 AM shall trigger a Medium alert", "High"],
      ["FR-RA-05", "More than 5 failed door access attempts within 60 seconds shall trigger a Critical alert", "High"],
      ["FR-RA-06", "More than 10 data submissions from a single device within 30 seconds shall flag a Medium anomaly", "Medium"],
      ["FR-RA-07", "A cumulative risk score (0–100) shall be maintained per device and updated on each reading", "Medium"],
      ["FR-RA-08", "All generated alerts shall be stored with: device ID, alert type, severity, description, timestamp", "High"],
    ],
    [1440, 6120, 1800]
  ),
  spacer(),

  heading2("4.5 Dashboard & Monitoring Module"),
  makeTable(
    ["Req ID", "Requirement", "Priority"],
    [
      ["FR-DB-01", "The dashboard shall display a real-time summary: total devices, active devices, alerts today, risk level", "High"],
      ["FR-DB-02", "Each device shall be shown as a card with: name, location, type, status, last reading, risk score", "High"],
      ["FR-DB-03", "The dashboard shall include a live alert feed showing the 20 most recent threat alerts", "High"],
      ["FR-DB-04", "A real-time line chart shall display sensor readings over the last 30 minutes per device", "Medium"],
      ["FR-DB-05", "Administrators shall be able to mark alerts as Resolved from the dashboard", "Medium"],
      ["FR-DB-06", "The dashboard shall update in real time via WebSocket without requiring page refresh", "High"],
      ["FR-DB-07", "The system shall support filtering alerts by severity (Critical, High, Medium, Low)", "Low"],
    ],
    [1440, 6120, 1800]
  ),
  spacer(),
  pageBreak()
];

// ─── Section 5: Non-Functional Requirements ───────────────────────────────────
const section5 = [
  heading1("5. Non-Functional Requirements"),

  heading2("5.1 Security"),
  bullet("All API communication shall occur over HTTPS in production deployment"),
  bullet("Passwords shall never be stored in plaintext — bcrypt hashing is mandatory"),
  bullet("JWT tokens shall be signed using HS256 with a secret key stored as an environment variable"),
  bullet("Device API keys shall be randomly generated (UUID4 or equivalent) and unique per device"),
  bullet("The application shall not expose internal error stack traces in HTTP responses"),
  spacer(),

  heading2("5.2 Performance"),
  bullet("The server shall handle at least 50 concurrent device data submissions per minute"),
  bullet("Dashboard WebSocket updates shall appear within 2 seconds of data submission"),
  bullet("API response time for data ingestion endpoints shall be < 500ms under normal load"),
  bullet("The risk engine evaluation shall complete within 100ms per sensor reading"),
  spacer(),

  heading2("5.3 Reliability & Availability"),
  bullet("The application shall be deployable and accessible via a public URL for demonstration"),
  bullet("The system shall gracefully handle invalid or malformed sensor data without crashing"),
  bullet("Database writes shall be atomic — partial writes must not corrupt existing data"),
  spacer(),

  heading2("5.4 Usability"),
  bullet("The dashboard shall be usable in modern browsers: Chrome, Firefox, Edge (latest versions)"),
  bullet("The interface shall be responsive and usable on screens ≥ 768px width"),
  bullet("Threat alerts shall be visually distinguished by colour coding (green/yellow/orange/red)"),
  bullet("All dashboard data shall be understandable without prior training by a technical examiner"),
  spacer(),

  heading2("5.5 Maintainability"),
  bullet("The codebase shall be modular — backend organised into separate files per concern (auth, models, risk engine, routes)"),
  bullet("All environment-sensitive values (secret keys, DB path) shall be stored in a .env file"),
  bullet("The project shall include a README.md with setup and run instructions"),
  spacer(),
  pageBreak()
];

// ─── Section 6: Tech Stack ────────────────────────────────────────────────────
const section6 = [
  heading1("6. Technology Stack"),
  makeTable(
    ["Layer", "Technology", "Version", "Justification"],
    [
      ["Backend Framework", "Python FastAPI", "0.110+", "Async-first, auto-docs (Swagger UI), ideal for real-time IoT APIs"],
      ["Database ORM", "SQLAlchemy", "2.0+", "Clean ORM abstraction; easy migration to PostgreSQL"],
      ["Database", "SQLite", "3.x", "Zero-config for development; file-based; upgradeable"],
      ["Authentication", "python-jose (JWT)", "3.3+", "Industry-standard JWT library for Python"],
      ["Password Hashing", "passlib + bcrypt", "Latest", "Secure, adaptive password hashing"],
      ["WebSockets", "FastAPI WebSockets", "Built-in", "Native WebSocket support for real-time feeds"],
      ["Frontend", "HTML5 + CSS3 + JS", "Vanilla", "No framework dependency; easy to deploy and demo"],
      ["Charts", "Chart.js", "4.x", "Lightweight, declarative charting library"],
      ["Device Simulation", "Python asyncio", "3.10+", "Concurrent simulation of multiple IoT devices"],
      ["Deployment", "Render / Railway", "—", "Free-tier compatible PaaS platforms for live demo"],
    ],
    [2200, 2200, 1400, 3560]
  ),
  spacer(),
  pageBreak()
];

// ─── Section 7: Device Types ──────────────────────────────────────────────────
const section7 = [
  heading1("7. Simulated IoT Device Specifications"),
  body("The following device types will be simulated. Each device runs as an independent Python process that sends data to the server at configurable intervals."),
  spacer(),
  makeTable(
    ["Device Type", "Data Sent", "Frequency", "Risk Triggers"],
    [
      ["Motion Sensor", "motion: true/false, zone: restricted/open", "Every 5 sec", "Motion in restricted zone after 10 PM"],
      ["Door Lock Controller", "state: locked/unlocked, access_result: success/fail", "On event", "≥ 5 failed attempts in 60 seconds"],
      ["Temperature Monitor", "temperature: float (°C), location: string", "Every 30 sec", "Temp > 50°C (High), > 80°C (Critical)"],
      ["IP Camera (simulated)", "status: active/offline, motion_detected: bool", "Every 10 sec", "Camera offline + motion at same location"],
      ["Access Card Reader", "card_id: string, result: granted/denied", "On event", "Multiple denied attempts, unknown card IDs"],
      ["Perimeter Sensor", "breach: bool, confidence: float (0–1)", "Every 15 sec", "Breach confidence > 0.8"],
    ],
    [2200, 2600, 1440, 3120]
  ),
  spacer(),
  pageBreak()
];

// ─── Section 8: API Endpoints ─────────────────────────────────────────────────
const section8 = [
  heading1("8. API Endpoint Specifications"),
  makeTable(
    ["Method", "Endpoint", "Auth Required", "Description"],
    [
      ["POST", "/api/auth/register", "None", "Register a new administrator account"],
      ["POST", "/api/auth/login", "None", "Login and receive a JWT access token"],
      ["GET", "/api/auth/me", "JWT", "Get current authenticated user details"],
      ["POST", "/api/devices/register", "JWT", "Register a new IoT device; returns API key"],
      ["GET", "/api/devices", "JWT", "List all registered devices with status"],
      ["DELETE", "/api/devices/{id}", "JWT", "Deactivate and remove a device"],
      ["POST", "/api/data", "Device API Key", "Submit sensor reading from an IoT device"],
      ["GET", "/api/data/{device_id}", "JWT", "Retrieve recent readings for a specific device"],
      ["GET", "/api/threats", "JWT", "List all threat alerts (filterable by severity)"],
      ["PATCH", "/api/threats/{id}/resolve", "JWT", "Mark a threat alert as resolved"],
      ["GET", "/api/dashboard/stats", "JWT", "Get summary stats for the dashboard"],
      ["WS", "/ws/live", "JWT (query param)", "WebSocket connection for real-time data stream"],
    ],
    [1000, 2600, 1800, 4960]
  ),
  spacer(),
  pageBreak()
];

// ─── Section 9: Project Milestones ────────────────────────────────────────────
const section9 = [
  heading1("9. Project Milestones & Deliverables"),
  makeTable(
    ["Phase", "Milestone", "Deliverables", "Est. Duration"],
    [
      ["Phase 1", "Foundation", "Project structure, DB models, basic FastAPI setup, .env config", "3–4 days"],
      ["Phase 2", "Authentication", "User registration/login, JWT middleware, device API key generation", "2–3 days"],
      ["Phase 3", "Data Ingestion", "Sensor data endpoints, device validation, data storage", "2–3 days"],
      ["Phase 4", "Risk Engine", "Rule-based threat classifier, alert generation, device risk scoring", "3–4 days"],
      ["Phase 5", "WebSocket Feed", "Real-time broadcast of sensor data and alerts to dashboard", "2 days"],
      ["Phase 6", "Device Simulators", "Python scripts simulating 10+ device types concurrently", "2–3 days"],
      ["Phase 7", "Frontend Dashboard", "Full monitoring UI: device cards, charts, alert feed, auth pages", "4–5 days"],
      ["Phase 8", "Deployment", "Live deployment, README documentation, demo preparation", "2 days"],
    ],
    [1300, 2000, 4000, 2060]
  ),
  spacer(),
  pageBreak()
];

// ─── Section 10: Risks ────────────────────────────────────────────────────────
const section10 = [
  heading1("10. Risks & Mitigations"),
  makeTable(
    ["Risk", "Likelihood", "Impact", "Mitigation"],
    [
      ["Hosting platform downtime during demo", "Low", "High", "Deploy to two platforms (Render + Railway) as backup; also prepare a localhost demo"],
      ["WebSocket not working on free hosting tier", "Medium", "Medium", "Test polling fallback; short-poll /api/data every 3s if WebSocket fails"],
      ["Risk engine false positives confusing examiner", "Medium", "Low", "Add a Test Mode that injects known scenarios with expected outcomes for demonstration"],
      ["SQLite limitations under load", "Low", "Low", "Scope is academic prototype; SQLite handles the expected load easily"],
      ["Scope creep adding features beyond deadline", "High", "High", "Strict MVP definition: complete all Phase 1–6 features before adding extras"],
    ],
    [2600, 1300, 1200, 4260]
  ),
  spacer(),
  pageBreak()
];

// ─── Section 11: Glossary ─────────────────────────────────────────────────────
const section11 = [
  heading1("11. Glossary"),
  makeTable(
    ["Term", "Definition"],
    [
      ["IoT", "Internet of Things — physical devices embedded with sensors and software that connect and exchange data over a network"],
      ["JWT", "JSON Web Token — a compact, signed token used to securely transmit authentication information between parties"],
      ["API Key", "A unique secret string assigned to each IoT device, used to authenticate data submissions to the server"],
      ["WebSocket", "A full-duplex communication protocol that enables real-time, bidirectional data streaming between server and browser"],
      ["Risk Engine", "The module that analyses incoming sensor data against defined rules and assigns threat severity classifications"],
      ["bcrypt", "A password-hashing function designed to be computationally expensive, making brute-force attacks impractical"],
      ["FastAPI", "A modern Python web framework for building APIs, featuring automatic documentation and async support"],
      ["SQLAlchemy", "A Python SQL toolkit and Object Relational Mapper (ORM) that provides a Pythonic interface to databases"],
      ["HTTPS", "HyperText Transfer Protocol Secure — HTTP with TLS encryption to protect data in transit"],
      ["REST API", "Representational State Transfer — an architectural style for designing networked applications using HTTP methods"],
    ],
    [2200, 7160]
  ),
  spacer()
];

// ─── Assemble Document ────────────────────────────────────────────────────────
const doc = new Document({
  numbering: {
    config: [
      {
        reference: "bullets",
        levels: [{
          level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } }
        }]
      },
      {
        reference: "numbers",
        levels: [{
          level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } }
        }]
      }
    ]
  },
  styles: {
    default: { document: { run: { font: "Arial", size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, font: "Arial" },
        paragraph: { spacing: { before: 360, after: 160 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 26, bold: true, font: "Arial" },
        paragraph: { spacing: { before: 280, after: 120 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 22, bold: true, font: "Arial" },
        paragraph: { spacing: { before: 200, after: 80 }, outlineLevel: 2 } },
    ]
  },
  sections: [{
    properties: {
      page: {
        size: { width: 11906, height: 16838 }, // A4
        margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 }
      }
    },
    children: [
      ...coverPage,
      ...section1,
      ...section2,
      ...section3,
      ...section4,
      ...section5,
      ...section6,
      ...section7,
      ...section8,
      ...section9,
      ...section10,
      ...section11,
    ]
  }]
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync("/mnt/user-data/outputs/SmartCampus_IoT_PRD.docx", buffer);
  console.log("PRD created successfully.");
});
