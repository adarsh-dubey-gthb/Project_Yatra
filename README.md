# SmartBus Delhi: Real-Time Bus Tracking & Predictive ETA

## Project Overview

Welcome to **SmartBus Delhi**, an innovative project designed to revolutionize the public bus transit experience in Delhi. This application provides real-time bus tracking, highly accurate Estimated Times of Arrival (ETAs) powered by machine learning, and an intelligent trip planning system that accounts for live traffic conditions.

Traditional bus tracking often relies solely on static schedules, leading to commuter frustration due to unpredictable delays. SmartBus Delhi addresses this by integrating real-time vehicle data with predictive analytics, offering a dynamic and reliable solution for urban mobility.

## Unique Value Proposition

SmartBus Delhi stands out by combining multiple layers of intelligence to deliver a superior user experience:

* **Predictive, Not Just Scheduled:** We leverage a **Machine Learning model** (LightGBM) trained on historical and real-time data to predict *actual* arrival times, accounting for real-world traffic and operational nuances.
* **Dynamic & Live:** ETAs are continuously updated based on the bus's live GPS location, ensuring predictions dynamically react to traffic jams, detours, or unexpected stops.
* **"Live-Aware" Trip Planning:** Our system intelligently filters potential routes, only showing users options that currently have *active buses in service*. This eliminates the frustration of waiting for a ghost bus.
* **Comprehensive Data Insights:** Provides a system-wide dashboard for transit authorities to monitor active buses, on-time performance, and average delays in real-time.

## Proposed Solution

Our solution is a robust, full-stack application comprising a Python-based machine learning backend and a Node.js web application for a seamless user interface.

* **Intelligent Backend (Python/Flask):** This microservice handles all data processing, real-time GTFS-RT ingestion, geospatial calculations, and machine learning model inference to generate highly accurate ETAs and filtered trip plans.
* **Interactive Frontend (Node.js/Express.js + EJS):** Provides a user-friendly web interface where commuters can search for routes between two points, view live bus positions on a map, and see dynamic ETA predictions. It dynamically updates results without page reloads for a fluid experience.

## Impact and Benefits

SmartBus Delhi aims to deliver substantial benefits across the transit ecosystem:

* **For Commuters:** Eliminates waiting anxiety, saves time with accurate ETAs, and makes public transport a more reliable and attractive choice.
* **For Transit Authorities:** Offers a live "health check" dashboard for the entire bus network, providing actionable insights for service improvement and operational efficiency.
* **For the Community:** Promotes public transport usage, leading to reduced traffic congestion and a lower carbon footprint for the city.

## Technology Stack

### Current Stack

* **Backend:** Python (Flask), Node.js (Express.js)
* **Machine Learning:** LightGBM, Pandas, NumPy, Scikit-learn
* **Database:** MongoDB (with Mongoose for Node.js)
* **Frontend:** EJS (Embedded JavaScript), Client-Side JavaScript (`fetch` API)
* **Mapping:** Mapbox GL JS (for interactive maps and geocoding)
* **Data Formats:** GTFS Static, GTFS-Realtime (Protocol Buffers .pb), JSON
* **Deployment (Local/Dev):** Python `venv`, `nohup`
* **Cloud Platform (Conceptual):** Google Cloud Platform (GCP)

### Future Stack (Proposed Upgrades)

To enhance scalability, performance, and add advanced features, we plan to evolve our stack with:

* **Containerization (Docker):** For consistent and reliable deployment of both Python and Node.js services.
* **Orchestration (Kubernetes/GKE):** For automated scaling and management of containerized applications under heavy load.
* **Real-Time Communication (WebSockets):** To enable smooth, continuous updates of bus positions on the map and proactive alerts.
* **Advanced ML Models (TensorFlow/PyTorch):** For future features like bus crowding prediction.
* **Caching (Redis):** To reduce API costs (e.g., for Mapbox geocoding) and improve response times.

## Installation and Setup

To get this project up and running locally, follow these steps:

### Prerequisites

* Node.js (LTS version recommended)
* Python 3.8+
* MongoDB installed and running
* A Mapbox Access Token (free tier available)
* Access to the Delhi OTD GTFS static and GTFS-Realtime API endpoints.

.....


Research and References
Our project is built upon rigorous research and utilization of established standards and tools:

Delhi Open Transit Data (OTD) Portal: https://otd.delhi.gov.in/

General Transit Feed Specification (GTFS): https://developers.google.com/transit/gtfs

GTFS-Realtime: https://developers.google.com/transit/gtfs-realtime

Mapbox Geocoding API: https://docs.mapbox.com/api/search/geocoding/

LightGBM Official Documentation: https://lightgbm.readthedocs.io/

Scikit-learn User Guide: https://scikit-learn.org/stable/user_guide.html

Pandas & NumPy Documentation: https://pandas.pydata.org/docs/ | https://numpy.org/doc/

Flask Documentation: https://flask.palletsprojects.com/

Express.js Official Website: https://expressjs.com/

LightGBM Academic Paper: https://proceedings.neurips.cc/paper/2017/file/6449f44a102fde848669bdd9eb6b76fa-Paper.pdf

Haversine Formula: https://en.wikipedia.org/wiki/Haversine_formula

Microservice Architecture: https://martinfowler.com/articles/microservices.html

Contributing
We welcome contributions to the SmartBus Delhi project! If you have suggestions for improvements, new features, or bug fixes, please open an issue or submit a pull request.

License
This project is open-source and available under the MIT License.


