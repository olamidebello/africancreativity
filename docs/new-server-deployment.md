# Deploy to a new server

Use Debian 12/13 or Ubuntu 22.04/24.04 with systemd. Point the A record for
`africancreativity.io` to the new server, remove conflicting AAAA records unless
IPv6 is configured, and allow inbound TCP 80/443. Back up and migrate existing
application data separately if replacing a production server; this creates a new
installation and does not copy accounts, media, or engine models from another host.

Run as root:

```bash
apt-get update
apt-get install -y git ansible ca-certificates
ansible-pull \
  -U https://github.com/olamidebello/africancreativity.git \
  -C main -d /opt/africancreativity-bootstrap \
  -i localhost, -c local \
  ansible/pull-and-deploy.yml
```

This pulls current source, runs integration tests, creates the application
service, backs up an existing installation before replacement, checks local
health, configures Nginx, obtains HTTPS, enables certificate renewal, and checks
the public health endpoint. Repeating the command updates the installation;
application updates are not scheduled automatically.

Sign in as `platformadmin`. Read the generated initial password locally as root:

```bash
cat /etc/africancreativity/bootstrap-password
```

The password is generated once and never printed in deployment logs. Existing
account passwords are preserved, so this file is not a password reset mechanism.
To supply your own password, pass a protected Ansible vars file using `-e @/root/creativity.yml`
containing `creativity_admin_password` (at least 12 characters).

Override `creativity_domain`, `creativity_admin`, or `creativity_port` with `-e`
on first deployment. The gateway file is preserved on reruns to retain Certbot's
TLS configuration; edit it explicitly when changing domain or port afterward,
then run `nginx -t` before reload. Check other enabled sites for duplicate domain
names before deployment. A certificate failure leaves HTTP available for fixing
DNS and rerunning; secure cookies require HTTPS for login. For HTTP-only testing,
set both `-e creativity_tls=false -e creativity_secure_cookie=false`.

For private repositories configure server-side Git credentials or a deploy key;
do not put access tokens in command URLs. Optional AI/GPU engines and provider
credentials are configured separately using the existing engine playbooks.

Diagnostics:

```bash
systemctl status africancreativity nginx
journalctl -u africancreativity -n 100 --no-pager
nginx -t
systemctl status certbot.timer
```
