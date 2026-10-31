import pytest
from fastapi.testclient import TestClient
from fastapi_migr.api.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_root_and_static():
    root_resp = client.get("/")
    assert root_resp.status_code == 200
    assert "AirFareX" in root_resp.text
    assert "main-navigation" in root_resp.text

    css_resp = client.get("/static/css/dashboard.css")
    assert css_resp.status_code == 200
    assert ".top-shell" in css_resp.text

    js_resp = client.get("/static/js/dashboard.js")
    assert js_resp.status_code == 200
    assert "FORMAL_LABELS" in js_resp.text

    img_resp = client.get("/static/aircraft.png")
    assert img_resp.status_code == 200
    assert len(img_resp.content) > 100000


def test_dashboard_bootstrap():
    resp = client.get("/api/dashboard/bootstrap")
    assert resp.status_code == 200
    data = resp.json()
    assert "headline_index" in data
    assert "routes_count" in data
    assert "lead_windows_count" in data
    assert "publication_status" in data
    assert isinstance(data["routes"], list)
    assert isinstance(data["airlines"], list)
    assert isinstance(data["sources"], list)


def test_dashboard_overview():
    resp = client.get("/api/dashboard/overview")
    assert resp.status_code == 200
    data = resp.json()
    assert "kpis" in data
    assert "overall_chart" in data
    assert "overall_table" in data
    assert "route_pulse_chart" in data
    assert "lead_chart" in data
    assert "source_chart" in data
    assert "quality" in data


def test_dashboard_index_analytics():
    resp = client.get("/api/dashboard/index-analytics")
    assert resp.status_code == 200
    data = resp.json()
    assert not data.get("empty", True)
    assert "chart" in data
    assert "index_table" in data
    assert "weekly_table" in data
    assert "monthly_table" in data
    assert "audit_trail" in data


def test_dashboard_route_intelligence():
    resp = client.get("/api/dashboard/route-intelligence")
    assert resp.status_code == 200
    data = resp.json()
    assert not data.get("empty", True)
    assert "kpis" in data
    assert "route_chart" in data
    assert "explorer_routes" in data
    assert "ranking_table" in data
    assert "heatmap_chart" in data
    assert "coverage_table" in data


def test_dashboard_route_explorer():
    resp = client.get("/api/dashboard/route-explorer")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert len(data["items"]) > 0


def test_dashboard_lead_time():
    resp = client.get("/api/dashboard/lead-time")
    assert resp.status_code == 200
    data = resp.json()
    assert not data.get("empty", True)
    assert "chart" in data
    assert "snapshot_table" in data
    assert "distribution_table" in data


def test_dashboard_lead_time_explorer():
    resp = client.get("/api/dashboard/lead-time-explorer")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert len(data["items"]) > 0


def test_dashboard_data_quality():
    resp = client.get("/api/dashboard/data-quality")
    assert resp.status_code == 200
    data = resp.json()
    assert "kpis" in data
    assert "anomalies" in data
    assert data["kpis"]["status"] in ["Healthy", "Review", "Attention"]


def test_dashboard_source_health():
    resp = client.get("/api/dashboard/source-health")
    assert resp.status_code == 200
    data = resp.json()
    assert not data.get("empty", True)
    assert "kpis" in data
    assert "chart" in data
    assert "coverage_table" in data


def test_dashboard_automation():
    resp = client.get("/api/dashboard/automation")
    assert resp.status_code == 200
    data = resp.json()
    assert "gates" in data
    assert len(data["gates"]) == 6
    assert "publication_status" in data
    assert "latest_audit" in data
    assert "pipeline_stages" in data
    assert len(data["pipeline_stages"]) == 10
    assert "resilience_policy" in data


def test_raw_observations_pagination():
    resp = client.get("/api/observations?page=1&page_size=25")
    assert resp.status_code == 200
    data = resp.json()
    assert data["page"] == 1
    assert data["page_size"] == 25
    assert len(data["items"]) == 25
    assert data["total"] > 0


def test_dashboard_refresh():
    resp = client.post("/api/dashboard/refresh")
    assert resp.status_code == 200
    assert resp.json()["status"] == "refreshed"

