# Study Planner Agent (Docker + EC2 + GitHub Actions)

This repo contains a Flask web app (simple chat UI) + a Gemini-backed agent with optional DuckDuckGo web search, packaged for:

- **Local dev with Docker Compose**
- **CI build/test + Docker image push**
- **CD deploy to an AWS EC2 instance via SSH (GitHub Actions)**

## 1) What you run locally

### Prereqs
- Docker Desktop

### Quick start
```bash
# from repo root
cp .env.example .env
# edit .env and set GEMINI_API_KEY (required for real answers)
docker compose -f docker-compose.local.yml up --build
```

Open:
- http://localhost:8080

> Tip: Use `search: your query` or `/search your query` to trigger web search.

Stop:
```bash
docker compose -f docker-compose.local.yml down
```

## 2) What you do once in AWS (EC2)

### Create EC2
- Ubuntu 22.04 (or 24.04)
- Security Group inbound:
  - TCP **22** from *your IP*
  - TCP **80** from `0.0.0.0/0` (public)
- Create/download a keypair (`.pem`)

### Install Docker on EC2
SSH in:
```bash
ssh -i your-key.pem ubuntu@YOUR_EC2_PUBLIC_IP
```

Run:
```bash
sudo apt-get update -y
sudo apt-get install -y ca-certificates curl gnupg

sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
| sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update -y
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker ubuntu
newgrp docker
docker --version
docker compose version
```

## 3) Configure GitHub Secrets (repo → Settings → Secrets and variables → Actions)

Add these secrets:

### Docker Hub (for image push)
- `DOCKERHUB_USERNAME`
- `DOCKERHUB_TOKEN` (create a Docker Hub access token)

### EC2 SSH deploy
- `EC2_HOST` (public IP or DNS)
- `EC2_USER` (usually `ubuntu`)
- `EC2_SSH_KEY` (private key content from your `.pem`)

### App secrets
- `GEMINI_API_KEY` (from Google AI Studio)
- `FLASK_SECRET_KEY` (any random long string)

After that, every push to `main` will:
1) run tests
2) build & push docker image
3) ssh into EC2 and run `docker compose pull` + `up -d`

## 4) Verify in production

After workflow finishes, open:
- http://YOUR_EC2_PUBLIC_IP/

(Port 80 is mapped to the container’s Gunicorn port.)

## Notes
- Redis is used to store conversation history per browser session (cookie-based session id).
- If `GEMINI_API_KEY` is missing, the UI loads but the agent replies with a configuration message.
