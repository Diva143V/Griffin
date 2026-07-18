import os
import requests
from urllib.parse import urlparse
from typing import List, Dict, Any, Optional

def is_safe_eln_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        hostname = parsed.hostname
        if not hostname:
            return False
        # Allow localhost and 127.0.0.1
        if hostname.lower() in ("localhost", "127.0.0.1"):
            return True
        # Allow specific domains from env
        allowed_domains = os.environ.get("ALLOWED_ELN_DOMAINS", "").split(",")
        allowed_domains = [d.strip().lower() for d in allowed_domains if d.strip()]
        if hostname.lower() in allowed_domains:
            return True
        return False
    except Exception:
        return False

class IndigoELNClient:
    def __init__(self, base_url: str = "http://localhost:9000"):
        if not is_safe_eln_url(base_url):
            raise ValueError(f"Insecure or unauthorized ELN URL: {base_url}. Connection refused.")
        self.base_url = base_url
        self.session = requests.Session()
        self.authenticated = False

    def login(self, username: str = "admin", password: str = "admin") -> bool:
        """Authenticate with the Indigo-ELN instance to obtain a JSESSIONID cookie."""
        login_data = {
            "j_username": username,
            "j_password": password
        }
        try:
            resp = self.session.post(f"{self.base_url}/api/authentication", data=login_data, timeout=5)
            self.authenticated = (resp.status_code == 200)
            return self.authenticated
        except Exception:
            self.authenticated = False
            return False

    def list_projects(self) -> List[Dict[str, Any]]:
        """List all projects available for creation or viewing."""
        try:
            # We can use sub-creations to find projects we can view/access
            resp = self.session.get(f"{self.base_url}/api/projects/sub-creations", timeout=5)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            return [{"error": str(e)}]

    def list_notebooks(self) -> List[Dict[str, Any]]:
        """List all notebooks available for experiment creation."""
        try:
            resp = self.session.get(f"{self.base_url}/api/notebooks/sub-creations", timeout=5)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            return [{"error": str(e)}]

    def list_experiments(self, project_id: str, notebook_id: str) -> List[Dict[str, Any]]:
        """List all experiments in a specific notebook."""
        try:
            url = f"{self.base_url}/api/projects/{project_id}/notebooks/{notebook_id}/experiments/notebook-summary"
            resp = self.session.get(url, timeout=5)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            return [{"error": str(e)}]

    def create_experiment(self, project_id: str, notebook_id: str, experiment_name: str) -> Dict[str, Any]:
        """Create a new experiment in a specific notebook."""
        payload = {
            "name": experiment_name,
            "parentId": notebook_id
        }
        try:
            url = f"{self.base_url}/api/projects/{project_id}/notebooks/{notebook_id}/experiments"
            resp = self.session.post(url, json=payload, timeout=5)
            if resp.status_code in [200, 201]:
                return resp.json()
            return {"error": f"Failed with status code {resp.status_code}", "detail": resp.text}
        except Exception as e:
            return {"error": str(e)}

    def get_experiment(self, project_id: str, notebook_id: str, experiment_id: str) -> Dict[str, Any]:
        """Retrieve details of a specific experiment."""
        try:
            url = f"{self.base_url}/api/projects/{project_id}/notebooks/{notebook_id}/experiments/{experiment_id}"
            resp = self.session.get(url, timeout=5)
            if resp.status_code == 200:
                return resp.json()
            return {"error": f"Failed with status code {resp.status_code}", "detail": resp.text}
        except Exception as e:
            return {"error": str(e)}

    def update_experiment_comments(self, project_id: str, notebook_id: str, experiment_id: str, comments: str) -> Dict[str, Any]:
        """Update comments/description of a specific experiment."""
        try:
            # 1. Fetch current experiment state first (required by PUT request to maintain other fields)
            get_url = f"{self.base_url}/api/projects/{project_id}/notebooks/{notebook_id}/experiments/{experiment_id}"
            get_resp = self.session.get(get_url, timeout=5)
            if get_resp.status_code != 200:
                return {"error": f"Failed to retrieve experiment before update (HTTP {get_resp.status_code})"}
            
            exp_data = get_resp.json()
            exp_data["comments"] = comments

            # 2. PUT updated experiment
            put_url = f"{self.base_url}/api/projects/{project_id}/notebooks/{notebook_id}/experiments"
            put_resp = self.session.put(put_url, json=exp_data, timeout=5)
            if put_resp.status_code in [200, 201]:
                return {"success": True, "data": put_resp.json()}
            return {"error": f"Failed to update experiment comments (HTTP {put_resp.status_code})", "detail": put_resp.text}
        except Exception as e:
            return {"error": str(e)}
