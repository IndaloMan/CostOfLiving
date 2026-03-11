#!/bin/bash
# setup_vm.sh — one-time setup for CostOfLiving on the SkyCam VM
# Run as: bash setup_vm.sh
set -e

APP_DIR="/opt/costofliving"
REPO_URL="https://github.com/IndaloMan/CostOfLiving.git"
SERVICE_USER="nhorncastle"
DOMAIN="receipts.ego2.net"

echo "=== 1. System packages ==="
sudo apt-get update -q
sudo apt-get install -y python3-pip python3-venv nginx certbot python3-certbot-nginx git

echo "=== 2. Clone repo ==="
sudo mkdir -p $APP_DIR
sudo chown $SERVICE_USER:$SERVICE_USER $APP_DIR
git clone $REPO_URL $APP_DIR
cd $APP_DIR

echo "=== 3. Python virtualenv + dependencies ==="
python3 -m venv venv
venv/bin/pip install --upgrade pip -q
venv/bin/pip install -r requirements.txt -q

echo "=== 4. Create .env (fill in values after setup) ==="
if [ ! -f "$APP_DIR/.env" ]; then
cat > $APP_DIR/.env << 'EOF'
ANTHROPIC_API_KEY=your-key-here
SECRET_KEY=change-me-to-a-long-random-string
ADMIN_EMAIL=your-email@example.com
ADMIN_FULL_NAME=Your Name
ADMIN_NICKNAME=Admin
ADMIN_PASSWORD=change-me
EOF
echo ">>> .env created — edit it now: nano $APP_DIR/.env"
else
echo ">>> .env already exists, skipping"
fi

echo "=== 5. Create Receipts folder ==="
mkdir -p $APP_DIR/Receipts

echo "=== 6. systemd service ==="
sudo tee /etc/systemd/system/costofliving.service > /dev/null << EOF
[Unit]
Description=Cost of Living Flask App
After=network.target

[Service]
User=$SERVICE_USER
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/venv/bin/gunicorn -w 2 -b 127.0.0.1:5000 "app:create_app()" --timeout 120 --access-logfile $APP_DIR/access.log --error-logfile $APP_DIR/error.log
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable costofliving
sudo systemctl start costofliving
echo ">>> Service status:"
sudo systemctl status costofliving --no-pager

echo "=== 7. nginx config ==="
sudo tee /etc/nginx/sites-available/costofliving > /dev/null << EOF
server {
    listen 80;
    server_name $DOMAIN;

    client_max_body_size 25M;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 120s;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/costofliving /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

echo "=== 8. Let's Encrypt SSL ==="
echo ">>> Make sure DNS A-record for $DOMAIN points to this VM's external IP before running certbot"
echo ">>> Then run: sudo certbot --nginx -d $DOMAIN"

echo ""
echo "=== Setup complete ==="
echo "Next steps:"
echo "  1. Edit .env:         nano $APP_DIR/.env"
echo "  2. Restart service:   sudo systemctl restart costofliving"
echo "  3. Point DNS:         receipts.ego2.net -> $(curl -s ifconfig.me)"
echo "  4. Get SSL cert:      sudo certbot --nginx -d $DOMAIN"
