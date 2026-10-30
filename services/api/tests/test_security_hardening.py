from pathlib import Path

import yaml

ROOT = Path(__file__).parents[3]


def test_every_compose_host_port_is_loopback_only() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    published = [
        port
        for service in compose["services"].values()
        for port in service.get("ports", [])
    ]
    assert published
    assert all(str(port).startswith("127.0.0.1:") for port in published)


def test_python_runtime_images_drop_root_privileges() -> None:
    backend = (ROOT / "services" / "Dockerfile").read_text()
    mcp = (ROOT / "mcps" / "company_tools" / "Dockerfile").read_text()
    assert "USER trackflow" in backend
    assert "USER trackflow" in mcp


def test_sshd_policy_disables_root_and_password_login() -> None:
    policy = (ROOT / "deploy" / "hardening" / "60-trackflow.conf").read_text()
    assert "PermitRootLogin no" in policy
    assert "PasswordAuthentication no" in policy
    assert "AllowUsers trackflow" in policy
