```markdown
# Fabric 2.5 + Chaincode Deployment — Reproducible Setup

Copy-paste safe. Do not skip steps. Tested on Ubuntu 26.04 (resolute).

---

## 1. Prerequisites

```bash
sudo apt update
sudo apt install -y curl git tar jq
```

---

## 2. Install Docker 24.0.9 (static binaries)

Fabric 2.5 requires Docker API 1.41. Docker 29 only supports 1.44+. **Do not use the Ubuntu `docker.io` package.**

```bash
sudo systemctl stop docker docker.socket containerd 2>/dev/null
sudo systemctl disable docker docker.socket containerd 2>/dev/null

sudo mkdir -p /opt/docker-backup
for f in docker dockerd containerd containerd-shim-runc-v2 ctr runc docker-proxy docker-init; do
  sudo mv /usr/bin/$f /opt/docker-backup/ 2>/dev/null
done

cd /tmp
curl -LO https://download.docker.com/linux/static/stable/x86_64/docker-24.0.9.tgz
tar -xzf docker-24.0.9.tgz
sudo cp docker/* /usr/bin/
sudo chmod +x /usr/bin/docker /usr/bin/dockerd /usr/bin/containerd /usr/bin/runc \
  /usr/bin/ctr /usr/bin/docker-proxy /usr/bin/docker-init
rm -rf /tmp/docker-24.0.9.tgz /tmp/docker
```

Create systemd units (static binaries don't ship them):

```bash
sudo tee /etc/systemd/system/containerd.service > /dev/null <<'EOF'
[Unit]
Description=containerd
After=network.target

[Service]
ExecStart=/usr/bin/containerd
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo tee /etc/systemd/system/docker.service > /dev/null <<'EOF'
[Unit]
Description=Docker
After=network.target containerd.service
Requires=containerd.service

[Service]
ExecStart=/usr/bin/dockerd
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable containerd docker
sudo systemctl start containerd
sudo systemctl start docker
```

Verify:

```bash
docker version
```

Must show **Server Engine Version 24.0.9** and **API version 1.43 (minimum version 1.12)**.

Add yourself to the docker group:

```bash
sudo usermod -aG docker $USER
newgrp docker
```

Pin versions to prevent apt from overwriting:

```bash
sudo apt-mark hold docker.io containerd runc 2>/dev/null
```

---

## 3. Install docker-compose v2 shim

Fabric 2.4/2.5 scripts call `docker-compose` (with a hyphen).

```bash
sudo curl -SL https://github.com/docker/compose/releases/download/v2.24.5/docker-compose-linux-x86_64 \
  -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
docker-compose --version
```

---

## 4. Install Go 1.20 (for local vendoring)

```bash
cd /tmp
curl -LO https://go.dev/dl/go1.20.14.linux-amd64.tar.gz
sudo mkdir -p /usr/local/go1.20
sudo tar -C /usr/local/go1.20 --strip-components=1 -xzf go1.20.14.linux-amd64.tar.gz
rm go1.20.14.linux-amd64.tar.gz

grep -q '/usr/local/go1.20/bin' ~/.bashrc || \
  echo 'export PATH=/usr/local/go1.20/bin:$PATH' >> ~/.bashrc
export PATH=/usr/local/go1.20/bin:$PATH
go version
```

Expected: `go version go1.20.14 linux/amd64`.

---

## 5. Clone fabric-samples at v2.4.9

**Not `main`.** The `main` branch uses `/v2` SDKs that require Go 1.21+, which break the Fabric 2.5 Go 1.20 builder.

```bash
mkdir -p ~/Documents/project
cd ~/Documents/project
git clone --branch v2.4.9 --depth 1 https://github.com/hyperledger/fabric-samples.git
cd fabric-samples
git describe --tags
```

Expected: `v2.4.9`.

Verify chaincode `go.mod`:

```bash
cat asset-transfer-basic/chaincode-go/go.mod
```

Must contain `go 1.17`, `github.com/hyperledger/fabric-chaincode-go` (no `/v2`), `google.golang.org/grpc v1.48.0`. If it doesn't, the clone is wrong — redo step 5.

---

## 6. Install Fabric 2.5.0 binaries AND config

The tarball contains **two** folders: `bin/` and `config/`. Both are required.

```bash
cd ~/Documents/project
mkdir -p fabric-dl
cd fabric-dl

curl -L -o fabric.tar.gz \
  https://github.com/hyperledger/fabric/releases/download/v2.5.0/hyperledger-fabric-linux-amd64-2.5.0.tar.gz
curl -L -o fabric-ca.tar.gz \
  https://github.com/hyperledger/fabric-ca/releases/download/v1.5.7/hyperledger-fabric-ca-linux-amd64-1.5.7.tar.gz

tar -xzf fabric.tar.gz
tar -xzf fabric-ca.tar.gz
rm fabric.tar.gz fabric-ca.tar.gz

cp -r bin     ~/Documents/project/fabric-samples/bin
cp -r config  ~/Documents/project/fabric-samples/config
cd ~/Documents/project
rm -rf fabric-dl
```

Verify:

```bash
~/Documents/project/fabric-samples/bin/peer version
ls ~/Documents/project/fabric-samples/config/configtx.yaml
```

Add to PATH (idempotent — safe to rerun):

```bash
grep -q 'fabric-samples/bin' ~/.bashrc || \
  echo 'export PATH=$HOME/Documents/project/fabric-samples/bin:$PATH' >> ~/.bashrc

grep -q 'FABRIC_CFG_PATH' ~/.bashrc || \
  echo 'export FABRIC_CFG_PATH=$HOME/Documents/project/fabric-samples/config' >> ~/.bashrc

source ~/.bashrc
which peer
```

---

## 7. Bring the network up

```bash
cd ~/Documents/project/fabric-samples/test-network
./network.sh down
./network.sh up createChannel -c screening-channel -ca
```

Wait for `Channel 'screening-channel' joined`.

Verify peer is alive:

```bash
docker ps --filter "name=peer0.org1.example.com"
```

Must show status `Up`.

---

## 8. Deploy the chaincode

```bash
./network.sh deployCC \
  -c screening-channel \
  -ccn screening \
  -ccp ../asset-transfer-basic/chaincode-go \
  -ccl go
```

Must end with:

```
Committed chaincode definition for chaincode 'screening' on channel 'screening-channel':
Version: 1.0, Sequence: 1, Endorsement Plugin: escc, Validation Plugin: vscc, Approvals: [Org1MSP: true, Org2MSP: true]
```

---

## 9. Test — invoke and query

```bash
cd ~/Documents/project/fabric-samples/test-network
export FABRIC_CFG_PATH=$PWD/../config
source scripts/envVar.sh
setGlobals 1

ORG1_TLS=organizations/peerOrganizations/org1.example.com/tlsca/tlsca.org1.example.com-cert.pem
ORG2_TLS=organizations/peerOrganizations/org2.example.com/tlsca/tlsca.org2.example.com-cert.pem

peer chaincode invoke \
  -o localhost:7050 \
  --ordererTLSHostnameOverride orderer.example.com \
  --tls --cafile "$ORDERER_CA" \
  -C screening-channel -n screening \
  --peerAddresses localhost:7051 --tlsRootCertFiles "$ORG1_TLS" \
  --peerAddresses localhost:9051 --tlsRootCertFiles "$ORG2_TLS" \
  -c '{"Args":["InitLedger"]}'

sleep 3

peer chaincode query -C screening-channel -n screening -c '{"Args":["GetAllAssets"]}'
```

Expected: JSON array with 6 sample assets.

---

## 10. Daily workflow

**Start (after reboot):**

```bash
# After reboot
sudo systemctl start containerd docker
docker start orderer.example.com peer0.org1.example.com peer0.org2.example.com couchdb0 couchdb1 cli
```

```bash
sudo systemctl start containerd docker
cd ~/Documents/project/fabric-samples/test-network
docker start orderer.example.com peer0.org1.example.com peer0.org2.example.com couchdb0 couchdb1 cli
```

**Stop:**

```bash
./network.sh down
```

**After editing chaincode:** increment version and sequence.

```bash
./network.sh deployCC \
  -c screening-channel \
  -ccn screening \
  -ccp ../asset-transfer-basic/chaincode-go \
  -ccl go \
  -ccv 2.0 -cseq 2
```

---

## Never do these

| Don't | Why |
|---|---|
| `apt install docker.io docker-ce` | Upgrades to Docker 29, breaks chaincode build |
| Clone `fabric-samples` from `main` | Requires Go 1.21+, breaks Fabric 2.5 builder |
| Run `go mod tidy` in the chaincode folder | Upgrades gRPC, breaks the `/v2` compile |
| Copy only `bin/` from the Fabric tarball | `network.sh` checks for `config/` and exits |
| Invoke from host without `FABRIC_CFG_PATH` | Peer fails with `Config File "core" Not Found` |
| Use the same TLS cert for both `--peerAddresses` | Org2 peer rejects Org1's cert |
| `docker system prune -a --volumes` while Fabric is up | Wipes Fabric volumes and chaincode images |

---

## Error → fix quick table

| Error | Fix |
|---|---|
| `docker-compose: command not found` | Install v2.24.5 shim (step 3) |
| `Peer binary and configuration files not found` | Copy `config/` from Fabric tarball (step 6) |
| `go: errors parsing go.mod: invalid go version '1.2x.0'` | Wrong `fabric-samples` tag — use v2.4.9 (step 5) |
| `undefined: grpc.NewClient` / `grpc.BidiStreamingClient` | Wrong `fabric-samples` tag — use v2.4.9 (step 5) |
| `write unix @->/run/docker.sock: write: broken pipe` | Docker 29 in use — install 24.0.9 (step 2) |
| `connection refused` on `localhost:7051` | Peer container died — rerun `./network.sh up` (step 7) |
| `Config File "core" Not Found` | `export FABRIC_CFG_PATH=$PWD/../config` |
| `x509: certificate signed by unknown authority` | Wrong TLS cert for one of the peers (step 9) |
| `channel '<json>' not found` | You passed `-c '{"Args":...}'` to `network.sh` — that's the channel flag |
| `chaincode install failed ... docker build failed` | Check `df -h /` for disk, then `docker builder prune -a -f` |

---

## Known-good versions

| Component | Version |
|---|---|
| Ubuntu | 26.04 (resolute) |
| Docker | 24.0.9 (static binaries) |
| docker-compose | 2.24.5 (shim) |
| Fabric binaries | 2.5.0 |
| Fabric CA | 1.5.7 |
| fabric-samples | v2.4.9 |
| Go (local) | 1.20.14 |
| Chaincode SDK | fabric-chaincode-go (no `/v2`) |
| Chaincode gRPC | v1.48.0 |
| Chaincode `go.mod` version | `go 1.17` |
| Channel | `screening-channel` |
| Chaincode name | `screening` |
```